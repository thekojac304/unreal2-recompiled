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
Intro-completion batch (2026-10-31 night, 10 launches, ~1930 s): BLOCKER RESOLVED by the opt-in
script-track fallback (--music-script-track; experiments/xrt/DMUSIC_SCRIPT_TRACK_DESIGN.md; helper
source patches/dmusic-script-track.patch + dmusic-helper-async.patch). Run 20261031-024122-65bd52c2:
full music chain twice, beginscene x4 then FinalEvent at +118 s (title card), then the game itself
restarts the intro (a001_start again: attract loop behind "PRESS ESCAPE TO BEGIN"; no map load).
Owned tests: chain_probe parse/dispatch (TrackIndex 1..8 without the game, negative cases fail closed),
dmusic_async_test 11/11, selftest 28/28. Defaults now: --timeout up to 360 (contain.exe cap 360),
physical input isolated (XRT_DEV_NO_INPUT; --allow-input to disable), time stop on any present,
--allow-map FILE.un2, captures at beginscene/FinalEvent cues and sparse non-world presents.
Performance (frames to FinalEvent, same music-timed section): 946 -> 1129 (recorder CRC slice-by-8)
-> 1798 (buffer Lock staging from host shadow, no GPU-visible reads) -> 2103 (indirect-call target
cache, world-return fast path): 8.0 -> 18.3 fps average. Legend logo scene stays ~2 fps:
AFluidSurfaceInfo::UpdateSimulation -> appRound -> msvcr70 floor was 48% of recorded calls; floor/ceil/
_CIfmod are now quiet leaves (UNMEASURED: final launch hit a host WM_NCPAINT region at startup, fixed
by 32-bit handle pass-through, also not yet run).
Menu-to-gameplay batch (2026-10-31 midday, 10 launches, ~1980 s): startup -> attract loop -> Escape ->
main menu -> NEW GAME -> NORMAL -> CS_Titles -> TutA (the normal new-game path) -> opening cutscene ->
PLAYER CONTROL (run 20261031-124244-4ab5c107: walk, turn, strafe, look, jump, back; walking into the
window blocks movement while W stays held). Quiet math verified (run 20261031-115841-514cd54e): Legend
scene 2.1 -> 12.6 fps, Init->FinalEvent 18.3 -> 22.0 fps. Gameplay ~11 fps (90 ms/frame), titles 37 fps,
TutA cutscene 6.5 fps. Options: --input "T:verb[:args];..." (key/move/click/shot, T = ms after Init,
max 256 steps) delivers WM_KEY*/WM_MOUSE* posted to the game's own D3D focus window (exact-match
allow-list through isolation), DirectInput mouse records only when the device reports success, a
virtual cursor for Get/SetCursorPos/ClipCursor under isolation, and pauses while the game process
is not foreground (never takes focus). --campaign-assets copies install content missing from the
first-world snapshot (never Save/System) into the sandbox. Fixed: x87 ffree st(i) (xlift.py; dev copy
out/dev-init/generated/D3DDrv_002.c), SendMessage WM_NCACTIVATE, kernel32 IsBadReadPtr.

TutA performance batch (2026-10-31 afternoon, 10+1 launches, 2789 s; 8 complete benchmarks, 3 stopped by the
owner's desktop activity / a full E: drive). Benchmark: tools/xrt/dev/bench_tuta.ps1 (normal New Game path;
window A 220-230 s standing at the TutA spawn view, window B 230-245.5 s fixed walk/turn/strafe), analysed
with perf_report.py RUN --window 220000:230000 --window 230000:245500 (frames.csv = QPC time of every
present; --sample-hz game-thread stack sampler; thread CPU at shots). Game thread is CPU-bound (97-98% of a
core) in every run; GPU/Present is not the limit. FPS spawn/movement (median frame ms):
  run 20261031-131008 baseline 13f007f, development diagnostics   8.5 (117) / 13.2 (75)
  run 20261031-131752 same code, --trace-profile quiet            22.9 (43) / 32.5 (30)
  run 20261031-133029 + generated code /O2, runtime fast paths   59.9 (16) / 89.8 (10)
  run 20261031-141217 + forced-inline xrt.h helpers, draw checks 76.8 (13) / 98.4 (9.5)
  run 20261031-142925 + scheduler race fixes, baton statistics   76.1 (13) / 101.0 (9.2)
  run 20261031-145028 final build bc44046 (11th, owner-approved) 78.1 (12.7) / 103.3 (9.0)
Causes, in order: the development recorder (xm_probe/xm_emit, routine snapshot CRC + writes, VirtualQuery
per record, per-D3D8-call evidence hex encoding of events the full timeline then dropped) ~60% of game
thread time; generated code built /O1 (no /Oi: every 4-byte guest load/store was a call to memcpy;
23288 calls in 750 symbolized functions -> 0 in 60075); VirtualQuery per D3D8 argument check; baton
hand-overs to Core's FFileStream Sleep(1) poller (~500/s); byte-at-a-time draw validation. Fixes keep every
check (patches/tuta-performance-runtime.patch; dev.py GEN_OPT /O2, GEN_NO_FORCE_INLINE, source-hash guard;
savepoint out/dev-init-savepoints/tuta-performance-20261031). --trace-profile quiet = development stream
minus routine BEGIN/END/DATA/RESOURCE records (OPEN/CLOSE, checkpoints, FATAL/GAP/ABORT, UGameEngine.Init kept).
Sampler note: plain Sleep-paced sampling aliases with the 1 ms timer and over-reports baton waits; it is now
QPC-deadline jittered (run 20261031-145028: baton no longer appears in the profile). Baton statistics (run 20261031-142925): game thread
waited 136667 times, 559 ms total in ~300 s. Host messages the runtime still refuses (fail closed, fatal 76):
WM_DEVICECHANGE 0x8004 with DEV_BROADCAST data, WM_APPCOMMAND 0x319 (media key) - keep the desktop idle.

Translator optimization batch (2026-10-31 evening): tools/xrt/xlift.py --opt LIST (default: none, byte-identical
output). dev.py lift --opt LIST MODULE... re-lifts shared gen/ modules into developer copies (out/dev-init/generated,
compiled instead of the shared units; Unreal2_001.c keeps its endpoint hooks; protos/tables must stay identical).
  flags  per-function flag liveness: only flags some path can read are stored (all live at every call, return,
         tail/indirect jump, trap, mark, watch, EH registration)
  pc     no c->pc store before instructions that cannot fault or reach the runtime
  base   guest memory through a per-function local copy of xrt_g (xrt.h rd32b ...)
  regs   guest registers in C locals, spilled to CPU before calls/returns/runtime helpers and reloaded after calls
Correctness: experiments/xrt/tests/opt_diff (owned DLL, native vs plain vs optimized, with mutations) and
insn_diff run.py --live-random (reduced flag updates against the CPU). Benchmark windows as below plus the
TutA opening cutscene 150-210 s; bench_tuta.ps1 -TimingProbe adds jump/collision shots after 245.5 s.
  run 20261031-151325 baseline build d644511 (re-measured)        cutscene 56.5 / spawn 77.1 / movement 104.3
  run 20261031-153538 Fire.dll only, --opt flags,pc                59.6 / 80.5 / 114.5
  run 20261031-154954 all 17 modules, --opt flags,pc               62.5 / 85.6 / 121.8
  run 20261031-160243 + base                                       65.4 / 89.7 / 131.3
  run 20261031-161455 + regs (-TimingProbe)                        66.0 / 94.5 / 134.7
  run 20261031-163246 baseline rebuilt from shared gen/ (-TimingProbe) 57.0 / 76.6 / 103.6
  run 20261031-164525 regs spills limited to written registers      66.6 / 94.7 / 140.1
  run 20261031-170016 + GlmLib_020 forced inline (1800 s limit)     71.4 / 98.4 / 140.3  (220-245.5 s: 123.6)
Batch: 8 launches, 2099 s. Save point out/dev-init-savepoints/translator-final-20261031.
Frame-rate check: the scripted shots (60-245.5 s, probe 247-258.5 s) show the same scene/cutscene state at the
same times and the same end position and collision outcome (walk into the console) at 77-135 FPS; small heading
differences after the scripted mouse turns also occur between two runs of one build. The scripted Space press
produced no visible jump in either build, so jump timing is not covered. perf_report symbolizes a run with the
CURRENT build's PDB: analyse a run before rebuilding (save points keep each measured exe + PDB).
dev.py build now records each object's source (.src): switching a unit back from a developer copy to the shared
source used to keep the stale object, because the copy is newer than the shared file.

120 FPS / 4K batch (2026-10-31 night, 10 launches, 2775 s; commits 7d4e806, f7924c9). Target: consistent 120 FPS.
Resolution: dev.py run --windowed-res WxH rewrites WindowedViewportX/Y in the run's own sandbox Unreal2.ini;
bench_tuta.ps1 -Res WxH (menu targets are fixed pixel offsets from the screen centre: the menus keep their pixel size
at every resolution) and -Delay S (whole script shifted, so CS_Intro 0..10+S s is measured too; -Delay 50 below).
On this 2560x1440 desktop a requested 3840x2160 window is clamped by Windows (client 3840x1421) while D3DDrv keeps a
3840x2160 back buffer: DXVK logs "Using GDI for swapchain presentation" and presents through StretchBlt (run
20261031-172740: menu 133 -> 78 FPS, 35% of the game thread in Present). --windowed-res therefore also sets the
dev-only XRT_DEV_MAX_TRACK (runtime hle_gui.c dev_max_track raises the WM_GETMINMAXINFO tracking size), so the window
keeps its client: a genuine 3840x2160 Vulkan swapchain and capture, but a window larger than the display, not native
display output. Baseline translator-final code, FPS (median/p95 ms):
  run                       res        intro 0-10   intro 30-60        cutscene          spawn           movement
  20261031-170016 (old)     1540x945   135.2        -                  71.4 (14.4/18.8)  98.4 (9.9/12.2)  140.3 (6.5/10.9)
  20261031-180353           1920x1080  132.5        125.6 (7.4/12.3)   71.8 (14.3/18.7)  99.7 (9.8/11.9)  144.8 (6.2/11.1)
  20261031-180919           2560x1440  128.9        125.9 (7.3/12.3)   70.3 (14.6/18.9)  96.4 (10.1/12.5) 140.7 (6.3/11.5)
  20261031-175807           3840x2160  130.6        127.6 (7.2/12.3)   73.9 (13.7/18.1) 102.8 (9.4/11.8) 145.3 (6.2/10.4)
Frame time does not depend on resolution (RTX 5090): the game thread is CPU-bound; 4K BMP captures (25 MB, every
256th world frame) add the 30-40 ms maxima. Optimizations (all at 3840x2160, -Delay 50):
  run 20261031-182137  x87 locals + inline ICALL + guarded staging reuse   70.4 cutscene (REGRESSION) / 104.6 / 155.7
      five large functions (2400-3400 instructions, e.g. GlmLib f_30b6e10 160 -> 525 KB) crossed MSVC's optimization
      budget; staging: NtProtectVirtualMemory 4.1% replaced Free+Alloc 4.6%, tail memset +1%: no gain, reverted
  run 20261031-185245  x87 + ICALLI only for functions <= 2000 instructions  77.2 / 106.1 / 154.0; intro 143.8 / 137.8
  run 20261031-192058  + x87v and comment-aware spill detection               90.3 / 122.6 / 167.4; intro 149.3 / 141.7
  run 20261031-192710  same build, unsampled, -TimingProbe (headline)          93.8 (10.6/14.6) / 126.3 (7.6/9.8) /
                       173.1 (5.2/8.7); combined 220-245.5 s 154.3 (6.1/9.1); intro 155.7 (5.9/8.5) / 140.1 (6.6/11.0)
xlift --opt x87: TOP/FSW in locals; x87v: ST values in locals within straight-line code (write-through to c->st);
icall: ICALLI per-site hit path of the call-target cache; LOCAL_MAX_INSNS 2000. called(): comments are not calls (the
comment 'fadd st(1)' had forced a register spill before every x87 register-operand instruction). Tests:
experiments/xrt/tests/opt_diff --opt flags,pc,base,regs,x87,x87v,icall --mutations (39000 cases, 14 mutations).
120 FPS NOT met: TutA cutscene 94 FPS (slowest seconds 158-177 s at 71-75 FPS); spawn p95 9.8 ms; CS_Intro 30-60 s
p95 11 ms. Cutscene costs (run 20261031-192058): translated code 62% (GlmLib animation, Engine), D3D8 HLE ~21% of which
Lock/Unlock staging ~12% (VirtualAlloc/VirtualFree/VirtualQuery per map for the use-after-unlock guard, plus copies),
recorder/evidence ~5%. Timing: shots at equal post-Init times match between 57-104 FPS (run 20261031-163246, 1540x945)
and 94-173 FPS (run 20261031-192710): cutscene frame and subtitle at 180 s, end position after the walk (245.5 s),
running distance (250.1 s), collision with the console (258.5 s); scripted Space still shows no jump. At 3840x2160 the
HUD, menus and subtitles keep their pixel size (tiny): original engine behaviour.
Resize/maximize (static; launch 10's maximize probe hit the 560x480 splash popup, not the game window, so no runtime
evidence): the viewport window already has WS_OVERLAPPEDWINDOW (style 14CF0000). Dragging sends WM_SIZING (RECT
pointer), which the GUI layer's message admission refuses (fatal 76); IDirect3DDevice8::Reset (slot 14) is a fatal
unsupported slot, and a client that differs from the back buffer makes DXVK present through GDI.

4K floor batch (2026-10-31 late, 10 launches, 2887 s; commits a532a34, ebe91b6 + this note). Goal: p95 <= 8.33 ms in each
window. Clean measurement: bench_tuta.ps1 -NoCapture (dev.py --capture shots: no periodic/cue/startup readbacks; shots
only at 15, 19.5, 60, 215, 246 s script time) -SampleHz 0 -Profile quiet -Res 3840x2160 -Delay 50. Script time = ms
after Init return (frames.csv) minus the delay; TutA loads at 93.8-95.4 s, its cutscene runs to ~210 s ("158-177 s"
is script time). Windows: CS_Intro 30-60 s after Init, cutscene 96-210 / 150-210 / slow 158-177, spawn 220-230,
movement 230-245.5. Every run: 3840x2160 Vulkan swapchain, no GDI fallback.
Hitch: the 87-108 ms frames were the scripted shots' 4K readback + BMP write (they sit exactly on shot times); without
captures no frame above 23.3 ms remains in any timed window (loads at 20.6 and 93.8-95.4 s are outside them).
Staging (resource_storage.inc): strict = fresh guest block per Lock, decommitted at Unlock (stale pointers fault);
it cost 13.2% of all game-thread time in the cutscene, 15.9% in 158-177 s (commit/decommit 7.0%, staging
re-validation 2.8%). dev.py --staging reuse keeps released buffer blocks committed for the next buffer Lock of the same
size class (xrt_staging_take/put); checks, confinement and copies unchanged, stale pointers no longer fault and may
alias another buffer's later Lock (test: experiments/xrt/tests/staging_reuse). A per-buffer variant exhausted the
224 MB guest VirtualAlloc pool (run 20261031-200351, fatal 76). Also: WM_DEVICECHANGE arrival/removal marshalling
(a host device removal killed run 20261031-195041). Translation: xlift x87/x87v/icall also for 2000-4000-instruction
functions with <= 150 spill points (f_30b6e10 141 -> 99 KB). Rejected: recorder fast paths (run 20261031-203446,
slow subsection not better), per-buffer staging. Final build (save point floor-cap-20261031), FPS (p95 ms):
  run              mode    intro30-60    cut 96-210    cut 150-210   slow 158-177  spawn         movement
  20261031-195815  strict  149.7 (10.65) 125.3 (13.30) 96.6 (14.25)  78.7 (15.68)  130.6 (9.86)  180.6 (8.58)  x87v build
  20261031-204816  strict  155.3 (9.77)  125.8 (13.21) 97.1 (14.10)  78.0 (15.57)  130.1 (9.50)  175.6 (8.72)
  20261031-210000  strict  153.4 (10.17) 122.7 (13.45) 95.5 (14.38)  76.7 (15.84)  127.6 (9.77)  171.9 (8.82)
  20261031-202714  reuse   171.0 (9.01)  139.2 (11.55) 111.3 (12.20) 93.8 (13.41)  143.9 (8.96)  196.2 (7.90)
  20261031-205407  reuse   168.2 (9.19)  135.7 (11.98) 107.1 (12.55) 91.3 (13.37)  141.0 (8.62)  187.8 (8.07)
  20261031-204115  reuse   167.5 (9.19)  127.9 (13.27) 99.3 (14.29)  79.8 (15.81)  141.4 (8.96)  190.9 (8.19)  probe
The probe run was uniformly 10-15% slower from 108 to 186 s with identical work per frame (host-side; HWiNFO64,
syncthing (E:\Launchbox), browsers were running): single-run cutscene comparisons carry about +-10%. The cap change's
own effect is within that noise. Target NOT met: slow subsection p95 13.4 ms (reuse) / 15.6-15.8 (strict).
Timing: probe shots (running distance 250.1 s, collision 258.5 s) match the 98 FPS run 20261031-163246 at ~190 FPS;
the cutscene's per-second pattern lines up at the same script times in every run; jump still not visible (unverified).

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
