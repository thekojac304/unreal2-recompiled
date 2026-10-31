# Asynchronous DirectMusic tool callbacks — design

2026-10-31. Developer first-scene scope. **Implemented and verified** in the dev tree
(patches `tools/xrt/dev/patches/first-scene-runtime.patch`, `dmusic-helper-async.patch`,
`dmusic-async-test.patch`). Run `out/dev-init/runs/20261031-005707-42ac125a`: lyric PMSGs delivered on the
runtime callback thread, retained by the game's tool, freed by the game thread; 64 CS_Intro world frames.
Deviations found during implementation: native `StampPMsg` calls the tool's Release/AddRef
recursively on the same thread (served recursively while a nested reply is awaited), and DirectMusic
delivers PMSGs whose `pGraph` is a graph the bridge had not wrapped (now wrapped on first sight, held
by the bridge until shutdown). After stamping, `pTool` usually points at an internal native tool; the
guest copy then holds 0 there (counted as "unmapped"; the game never reads it).

## Problem (observed)

Run `out/dev-init/runs/20261031-003038-903c8da9` stopped at CS_Intro world frame ~10:

    DirectMusic IPC seq 16 op 15 id 7 ... (CallRoutine, named, dev helper)
    DirectMusic helper fatal: tool callback outside STA
    XRT FATAL (exit 76): DirectMusic IPC disconnected (Win32 109)

After the intro music script starts, native DirectMusic calls the game's own
`IDirectMusicTool` from its performance/realtime threads. The x86 helper only
services tool callbacks on its main STA thread during an active request, and
it does not support `ProcessPMsg` or `Flush` at all.

## What the game's tool actually does (Engine_035.c)

Insertion-time answers (from the run's `dmusic_tool_callback` events) match
the translated code:

| Slot | Guest function | Behaviour |
|---|---|---|
| 1 AddRef | `f_10481a20` | `InterlockedIncrement` |
| 3 Init | `f_10481a40` | `E_NOTIMPL` |
| 4 GetMsgDeliveryType | `f_10481a50` | `0x10` = `DMUS_PMSGF_TOOL_ATTIME` |
| 5/6 media types | `f_10481a60`/`a70` | 2 types: 13 `LYRIC`, 14 `SCRIPTLYRIC` |
| 7 ProcessPMsg | `f_10481aa0` | `pmsg->pGraph->StampPMsg(pmsg)`; then, under the tool's guest CRITICAL_SECTION at `this+8`, appends the **raw PMSG pointer** to a 16-entry queue (`this+0x20`, count byte `this+0x60`); returns `S_OK` (tool keeps ownership). Queue full: message dropped, not freed (as natively). |
| 8 Flush | `f_10481af0` | `E_NOTIMPL` |

Consumer `f_10480f50` runs on the **game thread** (music manager tick):
under the same critical section it copies the queue and zeroes the count; for
each message it builds an `FString` from the lyric at `pmsg+0x38`, calls
`AGameInfo::eventDispatchMusicEvent`, then `IDirectMusicPerformance::FreePMsg(pmsg)`
(vtable `+0x44`, slot 17).

So correctness requires:
1. Guest code runs on a thread other than the game thread, concurrently with it
   (the game protects its queue with its own critical section).
2. The guest receives a PMSG in **guest memory** that remains valid until the
   guest frees it. That's lyric header plus string; it can stay alive for many frames.
3. `StampPMsg` on the graph from inside the callback, and `FreePMsg` on the
   performance later from the game thread, both reach the **native** message.

## Rejected alternatives

* Swallowing or auto-freeing PMSGs in the helper, or answering callbacks from the
  helper: that fakes the game's music events (`DispatchMusicEvent` is what lyric
  scripts drive).
* Disabling music: the game has no switch for it (`-nosound` is already passed and
  DirectMusic still initializes); changing ini/content is out of scope.
* Running DirectMusic in-process: the host is x64, native DirectMusic is x86.
* Forcing callbacks onto the helper STA: native delivery is ATTIME on the realtime
  thread; marshalling it to the STA would change the timing model and can deadlock
  against STA calls that wait on that thread (Stop/CloseDown).

## Design

### 1. Runtime: release the baton across IPC waits (prerequisite)

`dm_backend_invoke` holds the guest execution baton for the whole
`dmb_exchange`. With a second guest thread that needs the baton for a tool
callback, a blocking request such as Stop/CloseDown waiting on DirectMusic
threads, or a long `CallRoutine`, would deadlock. Release it exactly like the
other blocking imports:

* `dm_backend_invoke`: `xrt_baton_release()` before the exchange,
  `xrt_baton_acquire()` after.
* The existing synchronous callback path (`dmi_callback`, run inside the
  exchange on the game thread) re-acquires the baton before `xrt_call_guest` and
  releases it after.

This doesn't change single-threaded behaviour, because the baton is uncontended
without other guest threads.

### 2. Transport: a second, callback-only channel

`dmb_connect` creates a second anonymous pipe pair (helper → host callbacks,
host → helper replies), passed as `--async-pipes in out`. The protocol version
goes 1 → 2, so a v1 helper or runtime refuses the pair at HELLO.

Frames reuse `DmbMessage` with their own sequence space:

* `DMB_ASYNC_CALLBACK` (helper → host): `op` = tool slot, `object` = tool ID,
  `v[0..]` arguments. For ProcessPMsg the frame also carries the copied message
  (see 4) plus a helper-assigned **PMSG handle**.
* `DMB_ASYNC_NESTED` / `DMB_ASYNC_NESTED_REPLY`: requests issued *by guest code
  inside the callback*, executed by the waiting helper thread. That's the same
  native thread, as natively. Only `DMB_STAMP_PMSG` is admitted.
* `DMB_ASYNC_REPLY` (host → helper): HRESULT and outputs.

The helper serializes async callbacks with one critical section. Native
DirectMusic may run tools concurrently, but this guest tool serializes on its
own CS anyway; serialization only adds latency. Each async round trip has a 10 s
deadline; when it expires the helper exits and the host reports a fatal
error. The harness timeout stays the outer bound.

### 3. Helper (`out/dev-init/dmusic_helper`, dev copy)

* `tool_callback`: on the owner thread with an active request, keep the
  existing synchronous path. Otherwise use the async channel; this replaces
  "tool callback outside STA" `die()`.
* `tool_message` (ProcessPMsg): validate the PMSG.
  * `dwType` must be 13 or 14.
  * `dwSize` must lie in [56+2, 56+1024] and the string must be NUL-terminated within it.
  * `punkUser` must be NULL.
  * `pTool` must be this proxy, and `pGraph` must be a known wrapped `DMB_TOOLGRAPH` object (identity lookup, no added reference).

  Anything else is a fatal error that reports the field. Then register `{handle → native pmsg, perf}` in a
  table (bounded at 256), send the callback, and service nested Stamp requests
  until the reply arrives. Map the guest HRESULT back:
  * `S_OK`: ownership stays with the tool. The native PMSG is retained until
    `DMB_FREE_PMSG`.
  * `DMUS_S_FREE` / `DMUS_S_REQUEUE` / failure: return them unchanged and drop the
    handle (DirectMusic frees or requeues it natively). The guest copy is then
    invalid; the host frees it.
* `tool_flush`: same channel. The guest returns `E_NOTIMPL`, which is returned unchanged.
* `DMB_STAMP_PMSG` (nested only): native `IDirectMusicGraph::StampPMsg(native)`
  on the callback thread, then return the updated header.
* `DMB_FREE_PMSG` (ordinary request, performance object): look up the handle and
  call native `IDirectMusicPerformance::FreePMsg`. Return the HRESULT and remove the handle.
  An unknown handle returns `DMB_BAD_HANDLE` (the host turns that into a fatal error).
* `DMB_SHUTDOWN`/disconnect: retained PMSGs are freed natively before releasing objects
  (as the performance would on CloseDown).

### 4. Guest-visible PMSG

The host allocates `dwSize` bytes on the **guest heap** (`xrt_heap_alloc`, freeable)
and fills it as follows:

* the 56-byte header with the native values for `dwSize`, `rtTime`, `mtTime`, `dwFlags`,
  `dwPChannel`, `dwVirtualTrackID`, `dwType`, `dwVoiceID` and `dwGroupID`;
* `pTool` set to the guest tool object, and `pGraph` set to the guest proxy of that graph ID;
* `punkUser` set to 0;
* the lyric string copied verbatim to `+0x38`.

The host table maps `guest address ↔ PMSG handle`. Natively the
game reads only `+0x38`, `pGraph` and the vtables, but every field holds a faithful value or a
mapped identity.

After a nested Stamp, the host re-copies the changed scalar header fields and
re-maps `pTool`/`pGraph`; it is a fatal error if they point at objects the guest
cannot represent.

### 5. Host async callback thread

`dmb_connect` starts one host thread, registered as a **guest thread** through
the existing `new_thread` machinery: its own guest stack, TEB and `XrtThread`. It
gets DLL_THREAD_ATTACH/DETACH, because natively DirectMusic's threads are
in-process threads that guest DLLs see. It is not created through guest
`CreateThread`, and no guest handle is issued for it. Its loop:

1. Block on the async pipe **without** the baton.
2. Validate the frame and look up the tool by ID. Ownership checks use the async thread's
   own identity, not the game thread's.
3. Acquire the baton. Build arguments (`perf` = guest performance proxy for the
   message's performance; `pmsg` = guest copy), then `xrt_call_guest` the vtable slot.
   Guest re-entry happens through the existing typed HLE adapters (EnterCriticalSection,
   InterlockedIncrement, the DMI graph proxy).
4. While inside the callback, the DMI graph proxy method `StampPMsg` (graph vtable
   slot 3, today `DMI.Unsupported`) is admitted **only on this thread and only
   for the graph of the active message**. It goes over the async channel as
   `DMB_ASYNC_NESTED`. This is the one narrow exception to `dm_owner`.
5. Release the baton and send `DMB_ASYNC_REPLY`.

The performance proxy gets `FreePMsg` (slot 17) as an ordinary owner-thread DMI
method. It validates that the argument is a live guest PMSG copy, sends `DMB_FREE_PMSG`, and then
frees the guest copy.

Shutdown: when the process is exiting (`xrt_exiting`) or the pipe hits EOF, the thread exits without
taking the baton. A callback that is still pending at exit is never answered, and the
helper's Job kills the helper.

### 6. Evidence

* Events: `dmusic_async_callback` (slot, tool, PMSG handle, type, result),
  `dmusic_pmsg` (created, stamped, freed or dropped, guest address), and a counter of
  outstanding PMSGs in the runtime report.
* The monitor records the async thread's guest calls like any other guest thread's.
* The first-scene log line gains `music_events` (DispatchMusicEvent count).

### 7. Focused tests (owned, no game)

Extend the helper's existing `--test` hooks and `ipc_session` modes rather than
adding a suite:

* `async-lyric`: the helper allocates a real native LYRIC PMSG
  (`AllocPMsg` on the real performance) and calls `tool_message` from a new native
  thread. A small owned guest-tool fixture (host-side table standing in for the game
  tool) verifies the guest copy bytes, a nested Stamp, `S_OK` retention, a later
  `DMB_FREE_PMSG`, and the stale-handle refusal.
* `async-deadline`: an unanswered async callback ends within the deadline and
  produces a fatal error, not a hang.
* Baton regression: a fixture with two guest threads, where one is blocked in a DMI
  call, shows the other can run (the existing trace and launcher selftests stay as regression).

### 8. Limits that stay explicit

* Callback latency (IPC round trip, plus baton handover at function-entry
  granularity) delays at-time delivery. Audible timing is not claimed to be
  equivalent.
* Callbacks are serialized in the helper.
* Only LYRIC/SCRIPTLYRIC messages, StampPMsg and FreePMsg are modelled. Any
  other type, `punkUser`, or `SendPMsg`/`AllocPMsg` from guest code remains a
  fatal error that reports the exact field.

## Implementation plan and cost

| Step | Files | Size |
|---|---|---|
| Baton release around DMI IPC + sync callback re-acquire | `dmusic_backend_pipe.inc`, `hle_dmusic_guest.inc` | small |
| Protocol v2, second pipe, async frames | `dmusic_backend.h`, `dmusic_pipe.h` | medium |
| Helper async path, PMSG table, Stamp/Free | `out/dev-init/dmusic_helper/main.c` | medium |
| Host async guest thread + PMSG marshalling + DMI Stamp/FreePMsg | `hle_dmusic_guest.inc`, `xrt_thread.c` (internal thread start) | medium |
| Focused tests | `ipc_session.c` (dev copy), helper `--test` | small |

All of this goes in the dev tree, preserved as patches under `tools/xrt/dev/patches/`.
The shared helper, the strict pipeline and the supervisor are untouched.

Verification run: `--first-scene 64`, 120 s. It should show `dmusic_async_callback`
events, `dmusic_pmsg` freed by the game thread, `DispatchMusicEvent` calls,
and frames past 10 as the CS_Intro fade completes. The previous batch has
5 of 10 authorized launches remaining.
