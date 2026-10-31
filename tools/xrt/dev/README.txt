Unreal II developer loop
=======================

Build -> Run -> Observe -> Fix -> Repeat. Ask one technical question per run.
This is a separate development harness, not a replacement qualification system.
No game execution was performed while implementing the tracing update below.

What actually blocks progress
----------------------------
First-scene batch (2026-10-31; journal in out/dev-init/init-batch-20261030.txt):
  run --authorize-init --authorize-first-scene --first-scene N --timeout 120 ...
continues past the Init-return checkpoint (still recorded) and stops with exit 11 after N
presented frames whose draws were issued inside FLevelSceneNode/FCameraSceneNode::Render,
reading back the presented back buffer to scene-frame-NNNN.bmp at frames 1,2,4,...,N.
Last run 20261031-001207-98574d76: first Tick done, Present 2 = 555 draws / 396846 prims,
then a second IDirect3D8::CreateDevice was refused. Scene-node renders read 0 because
Engine_026 (the Render functions) is not compiled with world_observer.h: fix that first.
Runtime changes: patches/first-scene-runtime.patch.
Capture batch (2026-10-31): Engine_026 now built with the observer; run 20261031-003038-903c8da9
captured world frames 1..8 of CS_Intro (fading in; frame 8 shows letterbox, HUD and a dim nebula).
Blocked at frame ~10 by asynchronous DirectMusic tool callbacks (helper: "tool callback outside STA").
FIRST SCENE CONFIRMED (run 20261031-005707-42ac125a, scene-frame-0064.bmp/.png): CS_Intro space scene,
with asynchronous DirectMusic tool callbacks (protocol v2; experiments/xrt/DMUSIC_ASYNC_TOOL_DESIGN.md).
Focused test: out/dev-init/build/dmusic_async_test.exe <dev helper> <sandbox root> [deadline].
Dev DirectMusic helper: out/dev-init/dmusic_helper (patches/dmusic-helper-named-routine.patch), built x86
to out/dev-init/build/dmusic_helper.exe and preferred by run when present.
Sustained-intro batch (2026-10-31, 10 launches): run --first-scene 100000 --scene-seconds S --timeout 180
stops cleanly (exit 11) at the first world frame S seconds after Init, or at a post-Init .un2 open
(map transition). Captures: powers of two, then every 256th world frame. --draw-dump N logs each draw
of world frame N. Final run 20261031-020258-785db452: 1949 world frames, 112 s post-Init, music playing.
Fixed: D3D8 slot exhaustion (retired slots recycled, fresh guest tokens), monitor identity table
overflow (dead identities recycled), helper deadlock (DirectMusic-thread tool AddRef/Release waited on
the channel owner whose nested StampPMsg needed the performance lock; now an ordered deferred queue),
scalar WM_DEVICECHANGE in dialog callbacks.
OPEN BLOCKER (host DirectMusic, not the translation): segment script-track events (QUEUE-timed
dmPlayNext) never run on this Windows build, so Intro01 loops forever (helper "script TrackIndex" stays 1)
and the beginscene cues in Intro07+ never arrive; the intro holds in its white phase from ~36 s.
Reproduced without the game: dmusic_chain_probe.c (x86; build like the helper; usage in its header).
Run 20261031-014918-2bf1b6b4 reached UIScripts\NormalCredits.ui only after real keyboard input reached
the focused window (GetKeyState key-down): not a natural transition.

The third developer run (20261030-221937-21570264) reached successful window
creation and continued file-backed loading. Its last completed ReadFile returned
TRUE, its last SetFilePointer returned 0x6c560, and _vsnwprintf returned 12.
The monitor then exhausted its 131072-record limit: 0xE04D0005, not a demonstrated
guest failure. There is no recorded UGameEngine.Init or Init-return checkpoint.
See FLIGHT_RECORDER_REPORT.txt and out/dev-init/third-run-analysis.json.
The older renderer run is separate evidence; neither it nor these owned fixtures
establishes that this developer candidate returns from Init.

First experiment: does UGameEngine::Init (guest 0x1038F460) return to its caller
at 0x1090ED5C? The private generated caller invokes xrt_dev_init_return AFTER the
existing checked indirect call and BEFORE that next guest instruction. This
always terminates with status 10. It cannot continue into the main loop through
the normal run command. The checkpoint flushes tracing without pretending that
outer guest calls or normal shutdown completed.

First debugging target: d8_device_SetMaterial, then the remainder of SetRes and
OpenWindow. Inspect its 17 material words, HRESULT and guest caller. Continue
to Init return or the FIRST real fatal/missing operation. Fix that concrete
failure before adding speculative renderer support. Next after a successful
Init experiment: separately scope the first selected-world tick/scene draw.

Usable preparation
------------------
From E:\Unreal2-Port-Investigation, in PowerShell:

  .venv/Scripts/python.exe -B -I tools/xrt/dev/dev.py build
  .venv/Scripts/python.exe -B -I tools/xrt/dev/dev.py selftest

build never runs a candidate. First build copies the practical-init runtime
into out/dev-init/runtime and reuses its compiled generated-code objects.
It recompiles one private Unreal2 caller with the endpoint and debug symbols.
Runtime files compile /O2 /Z7 with /fp:strict (as the production client runtime); the generated caller uses /O1 /Z7.
Existing generated code remains optimized. build --full recompiles all generated
objects with symbols; it is required after xrt.h ABI or other generated-code
changes. Runtime .c edits rebuild affected units; .h/.inc edits rebuild runtime
units. The small launcher is rebuilt each time. Failed/stale builds refuse run.

Editable runtime: out/dev-init/runtime/
Private endpoint caller: out/dev-init/generated/Unreal2_001.c
Executable/PDB: out/dev-init/build/unreal2-dev.exe and unreal2-dev.pdb
Compiler/link errors: out/dev-init/build/*.txt

These working copies and game-derived outputs stay in ignored out/, not source
control. Setup is repeatable and never overwrites existing development edits.
Keep durable runtime fixes as patches before deliberately replacing that tree.
Do not edit retained evidence runtimes or production sources for this workflow.

Proposed game command -- ONLY after separate explicit owner authorization
------------------------------------------------------------------------
The owner must authorize this separate development Init scope beyond 0x0696F292,
ending before 0x1090ED5C, on their active Windows desktop. Existing strict grants
do not authorize this workflow. Historical strict x87, WNDPROC and DirectInput
differences remain failed; development execution does not claim equivalence.
The --authorize-init flag acknowledges that authorization; it does not obtain it.
There is no new grant database, seal, one-shot ledger or queue.

  .venv/Scripts/python.exe -B -I tools/xrt/dev/dev.py run --authorize-init --question "Does UGameEngine::Init return after the implemented SetMaterial/SetRes tail?" --change "Use the isolated practical-init runtime and Init-return endpoint" --timeout 60

Add --attach to wait before runtime/guest initialization. The launcher prints a
PID; attach Visual Studio (Native) or WinDbg to unreal2-dev.exe, then continue
the initial DebugBreak. Useful source/function breakpoints:
  xrt_fatal; xm_failure; d8_device_SetMaterial; xrt_icall; xrt_dev_init_return
In xrt_icall, a conditional breakpoint at site == 0x1090ED59 targets the Init
call. Inspect CPU *c, c->pc, c->rv, registers and history. No debugger owns a
reserved hardware slot. The outside deadline continues while paused; choose
--timeout 180 (maximum 300) only within the separately authorized run scope.

  .venv/Scripts/python.exe -B -I tools/xrt/dev/dev.py observe

Each run gets out/dev-init/runs/<time-id>/ and a NEW independent snapshot copy
under sandbox_cmp/dev-init-<time-id>/. observe displays the five-part iteration
report, console failure and readable tail of the binary monitor trace. Edit
iteration.txt with the diagnosis/next fix. Inspect xrt.log, runtime-report.json,
monitor.bin, monitor-tail.txt and crash.dmp in the same directory. Fatal runtime
logs include guest PC, registers and recent function history. Open dumps with
the matching PDB in Visual Studio/WinDbg. Minidumps are diagnostic, not full
guest-memory snapshots. Old runs are retained, never silently overwritten.

Minimum safeguards versus formal qualification
----------------------------------------------
Retained for development: snapshot/protected-asset checks; fresh independent
sandbox copies; clean host environment; existing memory, file, COM and graphics
argument guards; pinned DXVK pair and explicit DirectMusic helper; windowed-only
device creation; active Default desktop; one concurrent developer run; suspended
process creation and Job assignment BEFORE resume; no breakaway; kill-on-close
process-tree containment; external wall timeout; cursor/StickyKeys restoration;
fixed Init-return endpoint; explicit separate authorization. Do not run this and
the strict game supervisor concurrently. Ctrl+C cancels; no automatic retries.

Not prerequisites for ordinary development builds: whole-environment resealing,
full pointer-payload inventories, all-thread hardware breakpoint qualification,
three-way byte equality, immutable build/hash inventories or consuming a strict
one-shot slot. Those remain in the untouched strict pipeline for its own claims.
No supervisor module is imported and no supervisor state/ledger is read or written.
The harness accepts only its dedicated developer executable, not an old candidate.

Limits: Jobs contain process lifetime, not arbitrary hostile native filesystem
access; asset safety also depends on the retained runtime/file adapters. An
abrupt launcher kill kills descendants, but cannot run desktop-state restoration.
Development tracing now rolls routine detail; it has no cumulative record-count
termination. Forensic mode retains the original 131072-record ceiling.
Unflushed trace tails can be lost on a forced kill. No renderer success is inferred from
an exit code or fixture alone. Host exceptions/fatals attempt a minidump; OS
termination, severe stack corruption and hard deadlines may prevent a dump.

Preparation tested
------------------
Developer executable and PDB built, including a second incremental build.
Owned native tests: normal exit, endpoint exit, unhandled-exception minidump,
descendant timeout, debugger-attach timeout, launcher-death child cleanup, and
missing-authorization rejection. No game/generated objects are linked into
fixtures. Monitor tests link only the private monitor and owned native code.
The endpoint fixture tests the shared termination routine; execution
of the actual game caller and its Init-return hook remains untested by design.

No genuine executable or new game-derived candidate was launched. The strict
supervisor, its authorization mechanisms, original candidate and one-shot ledger
were not modified. The remaining prerequisite is explicit authorization for the
concrete development experiment above, not another readiness audit.

Development flight recorder (v5)
-------------------------------
run defaults to --trace-profile development. All events roll through a fixed
512-record ring, independent of import name: I/O, CRT, native calls, callbacks,
resources and metadata. There is no development XM_LIMIT check. Routine
execution cannot terminate merely because cumulative diagnostic count grows.
Exception: without --trace-full/--trace-address, about 20 pure CRT leaves
(toupper, wcslen, _wcsicmp, wcscpy, timeGetTime...; stub_quiet in xrt_loader.c)
are counted in runtime-report import calls but not recorded: name lookups call
them millions of times and recording dominated run time. Any selection
restores full recording. Caught C++ exceptions are retained but batched, and
periodic .routine snapshots are written without forcing the disk.

monitor.bin is the sparse CRC-chained durable stream. It retains OPEN/CLOSE,
checkpoints, UGameEngine.Init BEGIN/END, every fatal/gap/abort, first classified
failure per operation, first unclassified return and first suspicious return.
Active ancestors are included once so the sparse stream remains understandable.
These diagnostics flush immediately. Routine detail remains in the ring.
--trace-full 'kernel32.dll!ReadFile' selects complete detail for that import.
--trace-address 0x109074d3 selects a guest PC or stack return address. Both can
be repeated; selection includes nested calls and existing typed payloads.
Selected detail uses the existing stream without the development record ceiling;
it can grow on disk, and disk I/O failures remain explicit. No file buffer is
inferred/copied by the recorder. Existing typed-span bounds still apply.

monitor.bin.routine is a fixed v2 snapshot (5,967,984 bytes): 512 recent records,
511 named operation summaries plus one overflow bucket, counts, result ranges,
error changes, first/last BEGIN/END and first classified failure. Ring sequence
is observed-event ordinal; durable stream sequence is its own CRC chain.
Counts include selected operations too. The overflow bucket counts names that
no longer fit individually; it does not stop execution or suppress fatal events.
Snapshot CRC detects torn writes; this is not an atomic journal.

The small semantic table now classifies results only; it does not grant rolling
eligibility. Known failures count separately from unclassified and suspicious
returns. Unknown return values are never labelled successes. Their first return
and first zero/high-bit/error-changing return are durable; repeated outcomes
remain counted and appear in recent/last examples. This heuristic is diagnostic,
not proof that every other return succeeded. Actual runtime fatal/unsupported
paths always emit and flush their fatal event independently of classification.
ReadFile/WriteFile summaries include requested/transferred bytes and successful
short/EOF counts; returned BOOL and host/guest LastError remain visible. Only
the checked scalar output pointer from the BEGIN arguments is read, never the
file buffer. SetFilePointer/GetFileSize use the ambiguous sentinel plus guest
LastError; stale LastError alone never makes a known success a failure.

Snapshot and pending durable detail flush every 16384 observed events, and at
close, checkpoint, first failure/anomaly, abort, fatal and gap. Normal Init stop
flushes through the unchanged dev.Init.return checkpoint before ExitProcess(10).
The observer explicitly reports ring overwrites, operation-table overflow,
unclassified outcomes, terminal state and unknown unflushed history after an
abrupt stop. A forced kill may lose events since the last flush (or tear the
snapshot while writing); no exact post-flush count can be recovered from disk.
Host exceptions attempt the existing dump, but cannot safely guarantee recorder
flush through a damaged or interrupted lock. No new worker/supervisor is used.

Endpoint success requires exit 10, the structured dev_init_return report event
with guest_next 0x1090ed5c, AND a checksum-validated dev.Init.return checkpoint.
An orderly close, missing trace, exit code alone or fixture never proves game Init.

--trace-profile forensic retains v3 exhaustive behavior and its original limit.
The retained strict sources, assembly probe, CPU ABI, dispatch/preemption,
adapters, containment, external deadline and fixed generated endpoint are unchanged.
selftest uses owned native code only: actual high-volume I/O, ring wrap, selected
names/addresses/subtrees, first failure/unsupported/fatal, ambiguous seek results,
unknown returns, table overflow, close/endpoint, abrupt/torn history, state
invariance, strict baseline comparison and existing launcher safeguards.
