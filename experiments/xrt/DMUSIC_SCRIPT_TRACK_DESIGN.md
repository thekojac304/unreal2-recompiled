# DirectMusic script-track dispatch in the helper — design

2026-10-31. Developer CS_Intro scope. **Proposed, not implemented.** Needs owner approval because it makes
the bridge perform work that native DirectMusic is supposed to do (see "Fidelity position").

## Problem (observed)

Sustained-intro batch, final run `out/dev-init/runs/20261031-020258-785db452`: 1949 world frames, 112 s
after Init, music playing, clean stop. From ~36 s the intro holds in a white phase and never progresses.

The intro music is a DirectMusic container (`Music/Intro.con`) with a VBScript `Script1` and seven
infinitely repeating segments. Each segment carries one script-track event that calls `dmPlayNext`,
which plays the next segment (`Intro01 → 05 → 07 → 11 → 15 → 19 → 23_end`). Segments `Intro07` onward
carry the `beginscene` lyric cues that drive the scene changes, and `Intro23_end` carries `FinalEvent`.

On this host **no script-track event ever invokes its routine**. The music therefore loops `Intro01`
forever, `beginscene` never arrives and the scenes stop advancing. Evidence:

| Check | Result |
|---|---|
| Genuine run 9: helper reads `Script1.TrackIndex` every 2 s | 0 → 1 (game's `a001_start`), never 2 over 4 loops |
| `dmusic_chain_probe.c`, no game: STA sleeping / STA pumping / MTA | TrackIndex stays 1 for 40 s in every mode; no window messages posted |
| Same probe, manual `CallRoutine("dmPlayNext")` at 5 s | TrackIndex 2, music changes (routine works); then `Intro05`'s own event never fires (55 s) |
| Event timing patched in a scratch copy to PREPARE (1) or ATTIME (4) | Still never fires |
| Segment's `DMRF` reference (GUID a1dd7c49-…, `Script1`, `Script1.spt`) | Resolves to the same object the game initializes |
| Script track class {4108FA85-…} (32-bit) | Registered, `dmscript.dll` 10.0.26100.9549, ThreadingModel Both |
| Track config (`trkx`) | `0x10` PLAY_ENABLED, identical to the lyric tracks that do play |

Conclusion: the defect is inside native `dmscript.dll` script-track playback on this Windows build. It is
not caused by the translation, the IPC bridge, apartment choice or message pumping. The native game run
on this host would presumably show the same white-phase hold (not verified: native execution is outside
the authorized scope).

## Data (parsed from Intro.con)

All events use flags `0x2` = `DMUS_IO_SCRIPTTRACKF_QUEUE`, logical = physical time, routine `dmPlayNext`,
script reference GUID a1dd7c49-870b-994f-9837-2a748f46891f. 768 ticks per beat; measured ~1540 ticks/s.

| Segment | Repeats | Length | Loop | Event time | ≈ s from segment start |
|---|---|---|---|---|---|
| Intro01 | infinite | 24576 | 0–24537 | 21504 | 14 |
| Intro05 | infinite | 12288 | 0–12280 | 9216 | 6 |
| Intro07 | infinite | 24576 | 0–24548 | 21504 | 14 |
| Intro11 | infinite | 27648 | 0–24621 | 21504 | 14 |
| Intro15 | infinite | 24576 | 0–24531 | 21504 | 14 |
| Intro19 | infinite | 24576 | 0–24522 | 21504 | 14 |
| Intro23_end | 0 | 12288 | — | 6144 | 4 |
| IntroFadeout | 0 | 6144 | — | none | — |

Expected music length with working events: roughly 80 s plus the `AtMarker` waits, i.e. about 1.5–2 min.

## Options

| | Option | Verdict |
|---|---|---|
| A | **Helper dispatches script-track events** from the container's own data, on the native performance clock | **Recommended** |
| B | Root-cause `dmscript.dll` (disassemble the script track's Play path) and work around the specific defect | Optional time-boxed Phase 0; may reveal a narrower fix, but could cost days and still end in A |
| C | Ship or load an older `dmscript.dll` | Rejected: system-component replacement, licensing, untrusted binaries |
| D | Make the game call `dmPlayNext` (timer, scene hook, patched script) | Rejected: forces script progression; changes game behaviour |
| E | Rewrite the segments' events into another track type | Rejected: modifies game assets |

## Design (option A)

### Principle

The helper performs exactly the call that native DirectMusic's script track would make: the routine
named in the asset, on the script the asset references, when that event's occurrence reaches the queue
time of the native performance. Nothing is invented: no routine, time or target exists outside the
container data, and the native performance still decides what `dmPlayNext` plays and when it sounds.

### Components (helper only; runtime and guest untouched)

1. **Event table.** At `DMB_LOAD` success (currently only `Intro.con` is admitted), the helper reopens the
   same sandbox file through its existing file guard and parses each `DMSG` form: segment GUID/name,
   `segh` (repeats, length, play start, loop points), and every `scrt/scrl/scre` event (`scrh` flags,
   logical/physical time, `DMRF` script reference, `scrn` routine). Strict parser: any unmodelled chunk
   shape, flag other than QUEUE, reference to anything except the container's script, or more than 64
   events fails closed (`die`), never silently skipped.
2. **Segment identity.** Native segment objects are matched to table rows by
   `IDirectMusicObject::GetDescriptor` (`guidObject`), queried once per newly seen segment.
3. **Occurrence tracking.** On the helper STA's idle loop (already polling every 1 ms between requests),
   at most every 10 ms: query the primary segment state at the performance's queue time
   (`GetQueueTime` → `ReferenceToMusicTime`; `GetSegmentState`), and for that state read
   `GetSegment`, `GetStartTime`, `GetStartPoint`, `GetRepeats`. Occurrence *k* of an event at time *t*
   inside loop [L0, L1) plays at `start + (t − startpoint)` for the first pass and
   `+ k·(L1 − L0)` for loop passes; events outside the loop fire only on the first pass.
   Secondary segment states are out of scope (the intro uses only primary plays) and fail closed if a
   tracked event's segment ever plays as secondary.
4. **Dispatch.** When the queue time reaches an occurrence's music time, the STA calls
   `IDirectMusicScript::CallRoutine(routine)` on the referenced script (loader `GetObject` with the
   event's own `DMRF` descriptor; identity must equal the game's `Script1` object, else fail closed).
   Exactly once per (segment state, repeat index, event). A stopped or replaced segment state discards
   its pending occurrences, as native playback would.
5. **Observability.** One line per dispatch: segment, repeat, event time, queue time at call,
   lateness in ticks, routine, HRESULT; plus the `TrackIndex` probe already in the helper.
   A `DMUS_E_*` result from the routine is logged and returned nowhere (natively the track ignores it).

### Concurrency and fidelity position

* Dispatch runs only on the helper STA between IPC requests, so it never interleaves with a guest
  `CallRoutine` or other request. Native script tracks would call from a DirectMusic thread,
  concurrently; serializing is safer and the only observable difference is up to one request's
  latency (bounded by the existing IPC deadline, normally < 1 frame). Lateness is logged.
* Re-entry: the routine's `Intro05.play` may trigger tool callbacks; those already travel on the async
  channel (sequence 0 on the STA), the same path as the game's own `a001_start`.
* Double execution: if native script tracks work on another host, both would fire. The dispatcher is
  therefore **opt-in** (`XRT_DMUSIC_SCRIPT_TRACK=helper`, passed by `dev.py --music-script-track`),
  documented as a host workaround, and `dmusic_chain_probe.c` is the gate that shows a host needs it.
  Strict supervisor, production policy and the qualification baseline are unchanged.
* This is a declared **non-equivalence**: the bridge implements a native DirectMusic feature that the
  host fails to provide. It must be reported as such in any result built on it.

### Size estimate

Helper: ~200 lines (parser ~90, occurrence tracking ~70, dispatch/logging ~40). `dev.py`: one flag.
No runtime, guest-visible or protocol changes.

## Verification plan

1. **Parser test (owned, no game):** parse `Intro.con` from a sandbox copy; expect exactly the table above.
   Negative cases on scratch copies: unknown event flag, foreign script reference, truncated `scre` → die.
2. **Chain test (owned, no game):** extend `dmusic_chain_probe.c` to host the dispatcher. Expect
   TrackIndex 1 → 2 at ≈ 14 s, → 3 after `Intro05`'s event, … → 8 (`dmAllStop`), each dispatch's
   lateness logged and within one idle tick, lyric names changing per segment (e.g. `BassTom01`,
   `beginscene`, `FinalEvent`).
3. **Async regression:** existing `dmusic_async_test.exe` still 11/11.
4. **Genuine run (needs a new authorization):** one launch with the flag. Success means `beginscene`
   lyrics reach the game, captures show the scenes advancing past the white phase, and the intro reaches
   `FinalEvent` and its natural next state (stopped by the existing map-transition stop if it loads a
   map). The intro may need more than the current 180 s cap: Init takes 52–58 s and the music ~1.5–2 min.

## Decisions requested from the owner

1. Approve option A as a declared, opt-in host workaround (or ask for the Phase 0 investigation, B, first).
2. For the genuine verification: authorize launches with a cap of about 240 s per run, or accept that
   a 180 s run may end before `FinalEvent`.
3. Optional: keyboard input reached the focused game window in run 8 (DirectInput reads the real
   keyboard). Decide whether runs should prevent the game window from taking focus.
