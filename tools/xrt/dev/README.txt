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

iflags batch (2026-10-31 night, 10 launches, 3066 s; commit 3587077 + this note). Selection from the slow-subsection
profile of the x87v build (matching PDB/sources): full flag helpers (fl_add/fl_sub/fl_logic) 10.6% of samples, x87
reloads from c->st 0.5%; 76% of the sampled full-flag work existed only because calls/returns read every flag.
Implemented xlift --opt iflags (needs flags): module-wide least fixed point of reads(T)/preserved(T) for direct
calls and of return liveness for functions entered only by the module's own direct calls/tail jumps/fall-through;
indirect calls/jumps, imports, jump tables, marks, watches, int3/hlt/ud2 stay "all flags"; EH-frame registration and
statically untranslatable instructions (fatal traps) are not reads. Rejected: indirect calls as non-reads - the union
of entry reads over address-taken functions is all five flags (MMX/SSE trap paths, import thunks in vtables).
Static: full flag helpers GlmLib 30101 -> 12348, Engine 41122 -> 26891, Core 10171 -> 5353; code 81.7 -> 76.5 MB.
Tests: opt_diff t_asm_iflags + 6 mutations (42000 cases, 18/18 detected). Builds switched by copying each variant's
saved exe/PDB into out/dev-init/build (baseline floor-cap-20261031/build-relink, candidate iflags-20261031/build).
4K, --staging reuse, -NoCapture, unsampled; 3 baseline vs 5 candidate runs (interleaved B/C, then 2 confirmations),
medians FPS (p95 ms):
  window          baseline 221443/222648/223849   iflags 220829/222050/223248/225710/230314
  CS_Intro 30-60  167.3 (9.15)                    172.9 (9.00)
  cutscene full   134.1 (12.04)                   139.0 (11.83)
  cut 150-210     107.3 (12.66)                   110.2 (12.46)
  slow 158-177    90.0 (13.80), p99 15.86         91.9 (13.58), p99 15.37; range 88.6-98.2 vs 88.4-91.3
  spawn           138.3 (9.22)                    146.0 (8.75)
  movement        190.5 (8.17)                    199.4 (7.83)
Strict compatibility run 20261031-225116 (iflags, --staging strict): slow 77.8, spawn 133.6, movement 178.2.
Diagnostic sampled run 20261031-224507 (not a headline): in 158-177 s translated code ~73% (guest loads/stores
20.5%, x87 lines 8.1%, full flag helpers 7.3%, reduced flag stores 4.0%, prologue/epilogue 5.0%, push/pop 3.1%,
XRT_ENTER 1.9%, RET 1.6%), runtime ~27% (staging copies 2.3%, memset 1.8%, draw-validation memchr 1.7%,
dispatch 1.6%, setjmp 1.2%, D3D8 evidence 1.2%, isnan helper 1.1%). Timing: probe run 20261031-225710 (185 FPS) ends
at the same running position and collision as run 20261031-163246 (98 FPS); jump unverified. Shots match baseline
(menu identical, scenes < 4% pixels apart; end-of-walk heading varies as between two baseline runs).
Remaining gap: slow subsection p95 13.58 ms vs 8.33 (needs 39% less frame time), 0/19 seconds at >= 120 FPS.

Guest-memory batch (2026-11-01, 10 launches, 3063 s; this commit). Line-level split of the iflags slow-subsection profile
(run 20261031-224507, 158-177 s): the "guest memory" share was mostly x87 lines with guest operands, and the x64 of the
hottest functions showed two MSVC artifacts that survive /O2 /fp:strict: (1) every fst/fstp to guest memory
(wrf32b/wrf64b, memcpy of a float) went movss/movsd to a stack temporary, integer reload, integer store - a
store-forwarding round trip, often on the fstp -> fld chain (those lines: 7.0% of all samples); (2) isnan() in
XFCOMPARE/fcompare compiled to two out-of-line _dclass calls per x87 compare (1.1% leaf, clobbering xmm0-5 mid x87
block; 118 calls in f_30b6e10 alone). Third: x87v wrote every x87 result through to c->st[(ft_+k)&7] (index math +
store per op). Implemented (opt-in, default lift unchanged; re-lift with the old options reproduces all 247 iflags
chunks byte for byte):
  xlift --opt sse   final rename (after every analysis) to xrt.h twins wrf32s/wrf64s (_mm_store_ss/_mm_storel_pd)
                    and XFCOMPAREO/fcompareo (a < b, a == b, !(a > b): exactly the unordered case without isnan)
  xlift --opt x87w  x87v write-back: a written slot is marked dirty and stored once, before a cache end, a goto/
                    return/RET/switch and at the end of a block before a label (never more stores than write-through)
Static: f_30995e0 5456 -> 3899 x64 instructions, f_30b6e10 22212 -> 17372, f_2fd7d20 1361 -> 1038; exe 81.8 -> 80.3 MB;
GlmLib x87 write-through stores 47154 -> 8387; GlmLib_020 (forced inline) compiles in < 2 min instead of ~11, a full
build ~2 min. Tests: opt_diff t_asm_sse, t_asm_x87w; mutations sse x4, x87w x3 (final option set 48000 cases, 25/25;
--opt flags,pc,base,sse 9/9; previous option set 18/18); forms_equiv.py twins 6 M cases, 4/4 mutations.
Rejected: --opt pf (PF from a 256-entry table; flag-heavy functions -10% instructions) measured 105.3 / 101.4 FPS in
the slow subsection vs 102.7 median: within noise, not kept (save point pf-20261101 has it and its tests).
4K, --staging reuse, -NoCapture, unsampled; medians FPS (median / p95 / p99 ms, % frames > 8.33 ms):
  window          iflags (7 runs)               sse (233753)   sse+x87w FINAL (4 runs)       sse+x87w+pf (2)
  CS_Intro 30-60  172.9 (5.42/9.00/11.74, 7.7%)  180.6 (8.33)  183.3 (5.09/8.22/10.89, 4.6%)   176.5 (8.64)
  cutscene full   140.4 (7.91/11.58/13.58, 44%)  145.5 (11.01) 154.2 (7.27/10.42/12.17, 32%)   153.2 (10.42)
  cut 150-210     110.9 (12.26)                  116.2 (11.59) 122.7 (10.88)                   123.3 (10.90)
  slow 158-177    91.9 (10.60/13.55/15.24, 100%) 96.1 (12.64)  102.7 (9.50/12.01/13.70, 96%)   103.3 (11.97)
  spawn           146.0 (6.65/8.75/9.98, 6.8%)   151.6 (8.05)  158.6 (6.08/7.94/9.14, 3.0%)    158.4 (7.96)
  movement        199.4 (4.53/7.83/9.53, 3.3%)   201.5 (7.61)  212.5 (4.24/7.14/8.60, 1.4%)    211.7 (7.20)
Baseline = iflags runs 220829 222050 223248 225710 230314 + interleaved 20261031-234345 / 20261101-000455 (93.3 FPS,
p95 13.08 in the slow subsection). Final runs 20261031-235819, 20261101-001020, -003928, -005436 (-TimingProbe).
Spawn, movement and CS_Intro 30-60 now have p95 <= 8.33 ms; the cutscene does not: slow subsection p95 12.01 ms
(needs 31% less frame time), 0/19 seconds at >= 120 FPS. Sampled run 20261101-001903 (158-177 s, not a headline):
translated code 68% - call machinery ~22% (ICALLI 7.2%, CALL 2.6%, XRT_ENTER 2.1%, RET 1.7%, prologue/epilogue/
spills ~8%), flags ~14% (full helpers 7.8%, reduced stores 4.3%, flag branches 2.1%), c->pc store lines 6.7%, guest
loads/stores/push/pop/rep ~11%, x87 ~12% (now mostly the FP arithmetic itself); runtime 32% (memset 2.2%, draw
validation memchr 1.6%, dispatch 1.5%, staging copies 1.5%, setjmp 1.3%, d8_semantic_checkpoint 1.3%, recorder ~2.3%,
xrt_world_return 1.0%, xrt_rdtsc 0.9%, xrt_icall_after 0.8%). Timing: probe shots of 20261101-005436 (~182 FPS) match
probe run 20261031-225710 (iflags): same running distance (250.1 s) and collision with the console (258.5 s); menus
identical; scene shots < 2.5% pixels apart; end-of-walk heading varies as between two baseline runs (both 29-34%).
Scripted Space still shows no jump: jump timing unverified. Save points sse-20261031, x87w-20261031 (final), pf-20261101;
generated sources C:\Users\lawma\Unreal2-dev-sandbox-overflow\{sse,x87w}-20261031-generated.

Efficiency batch (2026-11-01, 9 of 10 authorized launches, 2847 s; commits 34c94d2, 5bdabe8). Phase 1: after the storage cleanup the asset
manifest still listed three protected files under sandbox_cmp/graphics-client/dc9cc5ddd1c5-dxvk (U2Player_A.uax,
HUD_Fonts.utx, UI_Fonts.utx) that the cleanup had removed, so every run would refuse; restored byte-identical from the
install (sha256 equal to the manifest). Measurement: bench_tuta.ps1 -NoCapture -SampleHz 0 -Profile quiet -Res 3840x2160
-Delay 50 -Staging reuse -PauseProbe -Monitor [-FpsCap N]. threads.csv: per-thread CPU (whole process as tid 0, guest
threads with their Sleep/preemption counts, host threads named by description or start address), taken by capture-free
"cpu" input steps at the window bounds (xrt.log's 50000-line budget used to drop them) plus baton statistics; frames.csv
gains cap_wait_us; -Monitor runs typeperf (\Energy Meter(RAPL_Package0_PKG)\Power = CPU package power, 1 s) and nvidia-smi
(GPU utilization/power, 0.5 s) beside the run; perf_report.py reads all of it (--json). -PauseProbe: Escape at 247 s,
in-game menu 248.5-256.5 s. Idle desktop without the game: package 62-63 W, GPU 0.4% at ~50 W.
Frame limiter (dev.py --fps-cap N; the engine's MaxClientTickRate is used by GetMaxTickRate only for network clients,
standalone returns 0): after each post-Init Present the game thread waits for the next 1/N s deadline on a high-resolution
waitable timer with the baton released (as Sleep), once per UGameEngine::Tick (EnforceTickRate's place); late frames keep
the phase, a deadline more than a period behind is re-anchored. Test experiments/xrt/tests/fps_cap (pacing within 1%, the
wait costs ~0.1% of a core, baton balanced, overrun, phase, stall, loading, uncapped). Launch 2 (run 20261101-025451) also
paced loading-screen presents: the TutA load (509 presents inside one tick) took 9.3 s instead of 1.1 s and shifted the
cutscene; fixed by the per-tick rule (later runs load in 1.1 s). FPS (p95 ms) / process CPU (% of one core) / package W /
GPU W; runs 024147 uncapped, 030402 60, 030956 90, 031540 120:
  window       uncapped                     60                         90                         120
  CS_Intro     175.4 (8.47) 107% 71.0 88.8  60.0 (20.54) 46% 61.6 62.3  90.0 (13.74) 63% 62.9 68.6  118.8 (10.90) 81% 67.2 82.4
  main menu    162.2 (8.12)  99% 70.5 81.2  60.1 (19.50) 45% 62.2 60.4  90.1 (13.88) 68% 65.0 66.3  119.6 (10.46) 84% 65.0 78.1
  cutscene     147.4 (10.80) 109% 70.1 88.0 59.9 (18.86) 59% 62.4 65.6  89.8 (13.16) 84% 66.4 79.7  112.5 (11.13) 99% 69.6 88.4
  slow 158-177  99.2 (12.54) 105% 69.2 82.3 60.0 (19.15) 72% 63.2 66.9  89.5 (13.36) 99% 67.9 82.0  100.6 (12.27) 108% 69.1 87.2
  spawn        151.3 (8.30) 104% 70.2 89.7  60.0 (18.43) 51% 61.2 62.7  90.0 (12.86) 72% 65.1 81.5  120.0 (9.93) 93% 68.5 83.7
  movement     203.1 (7.54) 109% 70.9 98.5  60.0 (18.29) 39% 60.3 63.1  90.0 (12.65) 55% 62.8 80.9  120.0 (9.77) 74% 67.4 82.4
  pause menu   336.1 (3.91) 109% 69.8 94.5  60.1 (17.91) 25% 59.0 55.5  90.1 (12.40) 34% 60.8 67.2  120.1 (9.48) 46% 62.8 73.1
The game thread is 94-98% of a core uncapped in every window (the menus too); 120 FPS holds everywhere except the cutscene
(slow subsection 100.6 FPS with no limiter wait). nvidia-smi utilization stays 10-17% at every cap (the GPU clocks down
instead). Background threads: Core's FFileStream worker (guest thread 1, a Sleep(1) poll loop) uses 0.0-4.3% of a core at
600-640 Sleep/s in every window and cap (2.5% paused at 60 FPS, mostly baton spin while the game thread's slice runs; baton
waits 7.7 s per run at 60 FPS, 5.4 s uncapped); dxvk-submit/dxvk-cs 1-5% each. The "~43% polling thread" of earlier
reports is the --sample-hz stack sampler (sampler_main sleeps, then spins with YieldProcessor to each deadline; 41-48% of a
core in sampled runs 20261031-145028 and 20261101-040617). No scheduler change: a sleeping background waiter would save at
most ~2% of a core and add a kernel wake to each of the game thread's ~640 hand-overs/s uncapped.
Native C proof of concept (dev.py build --native, tools/xrt/dev/native/glm_xform.c; NOT in the default build): GlmLib
f_2fd7d20, the virtual Node::GetTransform(out, world) (scale/rotation/translation composed up the parent chain, ancestors
called through ICALLI), 3.8% self in the slow subsection. The guest's x87 order is kept in doubles with float rounding at
its stores. experiments/xrt/tests/native_glm_xform: 120000 cases (realistic chains depth 0-6, IEEE specials, random bits,
a synthetic ancestor class, out aliasing the input; MXCSR default and FTZ|DAZ): every NaN-free case bit-identical in
registers, flags, all 8 x87 registers including stale popped slots, TOP/FSW, call order and guest memory; inputs with
NaNs differ only in NaN payloads (which NaN survives depends on MSVC's operand order; the translation already differs from
x87 hardware there); 6/6 mutations detected; --native-verify 64 in game: >= 131072 calls compared, 0 differ (run
20261101-034834). 15-30% faster per call (microbenchmark), in-game self share 3.8% -> 2.0% (sampled run 040617), but the
FPS A/B (baseline runs 024147 + 035425 vs native 034834 + 040015) is within noise: slow subsection -0.2%, cutscene +0.4%,
spawn +1.1%, movement +2.2%, while two baseline runs differ by up to 4%. Not retained (no measurable benefit; the
translated C is as portable). Save points fps-cap-20261101 (default, translated), native-glm-20261101 (native).

Gameplay batch (2026-11-01 afternoon, 20 owner-authorized launches, see the final report in the session; all runs in background
mode at 3840x2160, --fps-cap 90, --staging reuse, quiet profile, behind the owner's desktop):
  - TutA controls confirmed from frames + camera log: mouse look, walk/strafe/turn, jump (camera rise), crouch, collision,
    F4 objectives, dialogue choice by number key (1 Tutorial / 2 Return to ship), Escape pause menu and resume.
  - Save/load: F5 quicksave writes Save\Save0.usa (7.4 MB) with the game's own backup rotation (Save1); F8 "REALLY LOAD?" Ok
    restores it in a fresh sandbox (world state and objectives). Fixed for it: kernel32 CreateDirectoryW, CopyFileW (sandboxed).
  - Navigation: map actors read with UELib (third_party/Unreal-Library); "DEV camera" lines (view transform, read-only) give the
    player's world position/yaw; 4.22 mouse units per degree. TutA route to the lift worked out and walked; the lift ride
    (console, ~18 s descent) loads TutB (run 20261101-133834).
  - TutB load first hit "VirtualAlloc: bounded client pool exhausted": blocks were re-used only at their exact size, warm
    staging blocks never; xrt_mem.c now reclaims under pressure (release warm, merge adjacent free, best fit);
    experiments/xrt/tests/staging_reuse covers it (21 checks).
  - Desktop robustness: zero-argument registered broadcasts (ShellFileOpened), WM_SETTINGCHANGE string, scalar theme/colour/
    font/time/power broadcasts, WM_SIZING/WM_MOVING RECTs no longer fatal. Window resize (size:W:H) works through the game's
    own device re-creation (genuine 2560x1440 back buffer); IDirect3DDevice8::Reset implemented but not exercised by the game.
  - Diagnostic: dev.py build --diag-move + run --diag-move logs what ULevel::MoveActor reports as blocking the player.
  - Performance at the 90 FPS cap: every explored TutA area median 11.1 ms, p95 12.5-13.2 ms, 35-52% limiter wait.
  - Lifted-image gap: the pool's bump region also ended at a lifted module image inside the pool range (UI.dll at
    0x19100000; fatal on the second TutB attempt); xrt_mem.c now steps over such images.
Follow-up batch (owner-authorized, 5 launches): the default build enters the TutA lift exactly like the --diag-move build
(launch 13's block was its approach angle), TutB loads with both pool fixes (run 20261101-134656: two lifted images skipped,
no reclaim needed), TutB arrival/lift/quicksave and loading TutB saves in fresh sandboxes work, ~88 FPS at the cap.
TutB route: the arrival corridor (x~1515) leads to an east-west passage at y~-1300; RaffDoor (1010,-1221) at its west end
is under a staircase; checkpoints in out/dev-init/saves/20261101-13*-checkpoint-tutb-*.

TutB training/combat batch (2026-11-01 evening, 14 of 15 owner-authorized launches, 2603 s of 7200; journal and key PNGs in
out/dev-init/tutb-evidence-20261101, helper sources in its helpers/ folder). TutB completed through normal play, then the
natural transition TutB -> PD_Avalon (intro cinematic) -> Atlantis (player control, Aida's first conversation).
  - Navigation blocker resolved from map data, not by trial walks: brush polygons (UELib UPolys of each Brush model) and
    static-mesh bounds (UPrimitive bounding box) showed the earlier runs had walked off the hallway grating into a 64-unit
    trench under leadingstairs1 (eye z1098 = floor 992 + 106), blocked by the stair side at x1144. Not a collision defect.
    From the arrival save: W 1500 + W 1345 to x981, then north up the stairs through RaffDoor and the ramp (launch 1).
  - Walk calibration: distance ~ 0.397 * hold_ms + 8 uu (W, S, A, D alike); 4.16-4.18 mouse units per degree yaw, 4.14 pitch
    (+dy looks down). Turns repeat only to +-1-2 deg (mouse smoothing) and AR/GL firing kicks the view, so long legs keep
    one view direction and move by strafing; aim deltas are computed from the previous run's camera log (same inputs from
    the same save reproduce positions within ~10 uu).
  - Verified by subtitles/HUD/camera: Raff welcome chain and OpenTutorialDoor; RaffHUD scan sequence; Use on the hologram ->
    numbered dialogue options -> option 1; exit button; obstacle course: jump (eye +74 uu), mantle (holding Space at the
    MantleMover face, eye 1096 -> 1266), crouch (~118 uu/s) -> ObstacleCourseFinished; weapons from inside booths (x-880 /
    -1296 / -1872, railing stop y~-808; lanes along y-450 clear of the support pillars): DP primary and charged alt,
    CAR swept bursts and alt bolts, GL fragment and incendiary hits each fired their damage-type target triggers and
    Raff's next stage (WT4/WT5/WT7/WT9/WT11/WT13); TakeAwayWeapons, DM intro, loadout (real AR 75+90).
  - Deathmatch: StartDMDispatcher ("Bring it, Dalton."), RaffTrainingBot hunted and hit the player (HUD 100/300 -> 12/120,
    resets on "death", knockback, score Raff 1 at 68 s, 2 at 78 s), match over before 100 s (Raff most likely won 5-0; the
    result line fell between shots), "No" to "Wanna go again?" -> ExitDM. Player hits on the bot were NOT demonstrated.
  - Stations room (both stations), PlayerFinishedTutorial, Raff's farewell, dlgEndLevel -> PD_Avalon (+55.9 s); PD_Avalon
    opens Atlantis.un2 ~46 s later. Atlantis: in-map F5, walk/turn, F8 restored the saved view exactly.
  - Save/load: every launch started by quick-loading the previous run's quicksave in a fresh sandbox; position/facing, HUD
    health/shield and ammo (100/300 AR 75/90; 31/134 no weapons) and the script stage were restored. Bookkeeping trap: the
    game keeps two quicksaves (Save0 newest, Save1 previous); count every F5 of a run before picking one (launch 7 was lost
    to a mislabelled checkpoint).
  - Fixed: right-button release -> DefWindowProc -> WM_CONTEXTMENU (0x7b) was refused by the GUI callback admission (fatal
    76 on the first DP alt fire); hle_gui.c now handles it like WM_SETCURSOR (patches/tutb-combat-runtime.patch). New input
    verb rclick[:HOLD] (experiments/xrt/tests/bg_input 15/15). Save point out/dev-init-savepoints/tutb-combat-20261101.
  - Performance at the 90 FPS cap, 3840x2160: every new area median 11.1 ms, p95 12.0-13.1 ms; game-thread work per frame
    median 4-7 ms (p95 6-11) except the deathmatch (median 10.7, p95 13.5 ms, limiter wait ~0.6 ms). No area below 60 FPS.
  - Not covered: sound (still -nosound; ALAudio/OpenAL has no runtime adapter), maximize/borderless, Unreal2.log beyond its
    first 4 KB (file-writer buffer is lost at the endpoint stop).

Audio / campaign / Windows batch (2026-11-01 night, 26 of 30 owner-authorized launches, 3496 s of 12000; journal, maps,
helpers and key images in out/dev-init/campaign-evidence-20261101):
  - SOUND: AudioDevice=ALAudio.ALAudioSubsystem (OpenAL). ALAudio.dll and its/Core's Ogg Vorbis DLLs (vorbisfile, ogg, vorbis)
    are lifted (dev.py lift-audio; bases fill the gap below U2.dll) and registered with XRT_WITH_AUDIO; the OpenAL driver
    DefOpenAL32.dll (Creative's mixer: DirectSound3D/waveOut + timer thread) is replaced by runtime hle_openal.c, an OpenAL 1.0
    adapter on XAudio2 behind a DefOpenAL32.dll module identity (exports checked against the game file; unimplemented = trap).
    run --sound off|muted|on (default off = -nosound; muted runs everything with the mastering volume at 0, the meter is on the
    submix). Owned tests: experiments/xrt/tests/openal_bridge (adapter through guest calls, real XAudio2, mixed output measured),
    crt_memcpy (lifted static-CRT memcpy, 10616 cases). In game: UI sounds, ambient loops, Atlantis dialogue (109 AL buffers
    during the briefing), PA_Sanctuary streamed voice/music (2-buffer queues), M08A1 sounds; mix peaks 0.05-0.20, 0 glitches.
    Translator: rcl/rcr (insn_diff 441696/0); discovery of the CRT memcpy tables (index-register bound, and-mask bound, unused
    overlapping slot, neg-indexed table) + xlift fallback dispatch to the function's own case labels.
    Adapters added: HeapReAlloc, DisableThreadLibraryCalls, GetOEMCP/GetStringTypeA/LCMapStringA/GetLocaleInfoA, _wfopen, ftell,
    ldexp. Open: ALAudio's Update stops and replays ~1000 ambient plays/s (stops from its ambient range check
    dist^2 > (slot radius * GAudioMaxRadiusMultiplier)^2, multiplier 100 live, slot radius = SoundRadius * zone multiplier;
    lifted compare checked; not ref-distance-0 sources) - cause not resolved, audibility not assessed (runs were muted).
  - CAMPAIGN (normal play, no cheats): Atlantis: Aida's welcome conversation (choices by number keys), "Briefing" -> Aida walks
    to the briefing room; Use on her (crosshair target within TalkRadius 96: U2UseManagerPlayer.LookingAt / HasDialog) ->
    "Ready?" -> 1 Yes -> full console + holotank briefing with subtitles; walk back to the dropship; Use on Trigger37
    (TriggerType 5) -> PA_Sanctuary (arrival cinematic) -> M08A1 (Sanctuary mission; the M08 maps, not m01) -> intro cutscene ->
    player control at the landing pad, assault rifle. Navigation from the maps' own ReachSpecs (helpers/route.py); Atlantis:
    5.2 mouse units/deg, walk 0.243 uu/ms; M08A1: 4.2 units/deg, ~0.27 uu/ms. Save/load: every run quick-loaded the previous
    checkpoint in a fresh sandbox (saves/20261101-1706-*-tobriefing, 1752-*-postbriefing, 1814-checkpoint-m08a1-start).
    Combat continuation (launches 19-26, 26 of 30 launches, 3496 s in total): ENEMY HIT AND KILL DEMONSTRATED in M08A1 (run
    20261101-185046-6936236b): the first Izarians near the start are an inert scripted scare (Stabber1-3, gone after the pod
    cutscene); the first real fight is the Puppeteer (U2Izarian17, TESTPuppeteer: inert with 999 health while puppeting a
    corpse; line of sight or damage -> Attack, health 50; death -> IzarianPackcallsOut). Route via the use-opened door
    m08adoor1, the seal door's Use panel (Trigger6) and the nav route to (1628,1400); facing it, it attacked; assault-rifle
    fire: blue blood from its torso, collapse, gibbing (campaign-evidence 26-l26-*.png, frames-l26/), then the Izarian pack
    attacked and killed the player. New input steps (dev_support.c): goto:X:Y[:R] walks to a point closed-loop on the camera
    pose (waypoints from the map's ReachSpecs; 36-40 uu accuracy over 22 legs) and face:X:Y turns only; bg_input still PASS.
    Checkpoints saves/20261101-1843-*-puppeteer-fight (mid-fight, lost position) and 20261101-1853-*-before-puppeteer.
    Open: the DirectMusic helper crashed silently in 2 of 9 M08A1 loads right after the level's music routine (dmM08A001);
    the developer helper now reports unhandled exceptions (code, module+offset) on stderr for the next occurrence.
  - DirectMusic helper: levels load their own music containers (M08.con); the developer helper admitted only Intro.con
    (FATAL 76 on the M08A1 load). Now any plain *.con name (patches/dmusic-helper-level-containers.patch); dmusic_async_test
    11/11. Campaign runs drop --music-script-track (an intro-only workaround).
  - WINDOWS: opt-in run --borderless (viewport window as WS_POPUP at the monitor origin; --windowed-res = monitor size gives a
    borderless full-screen window); resize 2560x1440 -> 1920x1080 -> 2560x1440 with genuine back buffers (Vulkan swapchain
    reset, no GDI). Maximize/restore NOT exercised: Windows has no non-activating maximize and background runs must not take
    the owner's foreground. Foreground interactive play not exercised (needs the owner at the machine).
  - PERFORMANCE (3840x2160, 90 FPS cap): PA_Sanctuary cinematic, M08A1 cutscene/start/advance/rifle fire, Atlantis briefing all
    ~90 FPS median, p95 12.1-13.2 ms (p99 20 ms during rifle fire); least headroom in the briefing (2.5 ms limiter wait).
    No area below 60 FPS. Maxima ~100-128 ms are the scripted screenshot readbacks.

Interactive desktop batch (2026-11-01 evening; code and owned tests only, no game launch): fixes for the owner's three
interactive runs 20261101-191847-7aea43cf / -191912-be757706 / -192029-eed53121 (evidence kept in place), port settings.
Runtime patch patches/interactive-desktop-runtime.patch (base: save point interactive-20261101/runtime-base = the
audio-campaign runtime plus the committed WM_APPCOMMAND hunk); helper patch patches/dmusic-helper-heartbeat.patch.
  - EXIT (run -192029, fatal 75): menu Quit -> ConsoleCommand EXIT -> UGameEngine::Exec -> Core appRequestExit(0) ->
    user32 PostQuitMessage, which had no adapter. Now message_pump.inc hle_PostQuitMessage: the native call on the calling
    guest thread's own host thread (refused, fatal 76, for any other pairing), so the next guest PeekMessage returns WM_QUIT
    (hwnd 0, wParam = code) after the messages already queued; the game then runs its own shutdown (main loop ends,
    appPreExit, engine/viewport/device/audio teardown, CRT exit, ExitProcess -> runtime DLL detach). dev.py prints "the game
    exited normally" for exit 0 + outcome "exited". Static audit: PostQuitMessage was Core's only unbound import on that
    path (the others are error dialogs, clipboard, editor UI). The shutdown after WM_QUIT has never run: UNTESTED in game.
    Owned test experiments/xrt/tests/quit_message (9 checks: shape, WM_QUIT once with the code, ordering after posted
    messages, per-thread queues, refused cross-thread use).
  - MAXIMIZE (runs -191847 Maximize button, -191912 Alt+Enter; fatal 76 "CreateDevice fullscreen requires separate display
    scope"): WinDrv's ViewportWndProc maps WM_SYSCOMMAND SC_MAXIMIZE (0xF030; also caption double-click 0xF032, window menu)
    and VK_RETURN key-down with Alt held to UWindowsViewport::ToggleFullscreen = TryRenderDevice(RenderDevice,-1,-1,
    Fullscreen=1) followed by "set ...ViewportManager StartupFullscreen true". viewport_window.inc (called first in
    hle_gui_classes.inc class_dispatch) performs these two requests for the top-level viewport window as native WINDOWED
    maximize/restore (DefWindowProc / ShowWindow) and does not pass them on: the guest sees the ordinary
    WM_GETMINMAXINFO/WM_WINDOWPOSCHANGED/WM_SIZE sequence (monitor work area, actual client) and resizes its back buffer as
    for any resize; StartupFullscreen is not touched. SC_RESTORE and dragging reach the game unchanged. Exclusive fullscreen
    stays unsupported (the CreateDevice guard is unchanged): console TOGGLEFULLSCREEN still ends fatal 76; the video options
    Fullscreen checkbox (SetFullscreen = TOGGLEFULLSCREEN + StartupFullscreen) is replaced by UI Scale (below).
    Owned test experiments/xrt/tests/viewport_maximize (13 checks, window on the second monitor: client 2560x1369 inside that
    monitor's work area, exact restore, caption double-click, Alt+Enter toggle, auto-repeat, child/other class untouched).
    In-game maximize/restore/drag-resize, device and resource counts after resizing: UNTESTED.
  - PORT SETTINGS (tools/xrt/dev/port.py; dev.py port-build, applied to every run sandbox): script package U2Port.u
    (port/U2Port/Classes/PortSettings.uc, a UI.UIHelper compiled by the ORIGINAL UCC make in sandbox_cmp/u2port-make; 0
    errors) holds config(User) WalkingSpeed (75..200, step 5) and UIScale (0 Auto, 100, 125, 150, 200) in User.ini
    [U2Port.PortSettings]; anchored edits to the sandbox's own U2Menus.ui/.int add Options > Game > Walking Speed (slider,
    row 11) and Options > Video > UI Scale (selector, row 10, in place of Fullscreen). The helper's Set functions SaveConfig
    and send "PORTSET <Key> <Value>"; the runtime (port_settings.c) answers it in UWindowsViewport::Exec (dispatch flag
    CALL_PORT_EXEC) and reads the same section from System\User.ini at startup. --profile NAME carries User.ini between
    interactive runs (out/dev-init/profiles/NAME); without it every run starts from the snapshot's User.ini, as before.
    Owned test experiments/xrt/tests/port_overlay (14 checks).
  - WALKING SPEED: native/walk_speed.c wraps APawn::calcVelocity (f_103e24d0, dev.py PORT: only the definition is renamed,
    so physWalking's call in the same unit reaches the wrapper; verified with dumpbin). Applied only for the call from
    physWalking (return Engine+0xe61da) of a pawn whose Controller IsA PlayerController: MaxSpeed, AccelRate (+0x470) and
    Acceleration (+0x148) are scaled for that one call, AccelRate restored and Acceleration returned unscaled - nothing is
    stored, so respawn/save/load/script GroundSpeed changes cannot compound it. Falling/jumping, swimming, flying, ladders,
    NPCs and scripted controllers are untouched; collision stays the engine's swept move. Owned test
    experiments/xrt/tests/walk_speed (9 checks: exact x0.75/x1.5/x2 at every step, clamp path, scope, 1000-call compounding).
    In game (100/150/200%, stairs, doors, triggers, transitions): UNTESTED.
  - UI SCALE: UUIConsole::PostRender sizes the root from the viewport times the config UIConsole ScaleX/ScaleY and calls
    Root->Update(Frame, FUIRenderer) (UComponentHandle::Update, return UI+0x7f82b). For that call (dispatch flag
    CALL_PORT_UI_ROOT) the root is resized/moved to 1/S and the renderer's own PushScale(S)/PopScale (vtable +0x18/+0x1c, as
    UScaleContainer uses) wraps it, so layout (parent-relative alignment, HardCenter, margins), cursor and hit-testing stay
    in one virtual space; UScaleContainer::Update gets PushScale(1/S) (it already scales to the whole viewport). Auto =
    largest offered S with 768*S <= 0.75*client height (1080 -> 100, 1369/1440 -> 125, 1600 -> 150, 2160 -> 200). Default
    100% = original drawing (hooks pass through). Pivot of the renderer scale, cursor clamping and the HUD/subtitle
    result: UNTESTED in game.
  - AUDIO: (1) ambient churn still present (run -192029: 125871 plays / 125856 stops, ~1160/s): ORIGINAL ALAudio logic -
    PlaySoundW stores the occlusion-reduced radius in the source (+0x20) when the line of sight is blocked, the Update stop
    pass compares the distance with that reduced radius, the start pass with the actor's full SoundRadius, so every occluded
    ambient sound inside its full radius is stopped and replayed each frame. Not a translation or adapter defect; not
    changed. Adapter cost measured by experiments/xrt/tests/openal_churn: 11700 stop/play pairs, no measurable extra CPU
    (0.7% vs 1.0% of a core steady). (2) DirectMusic helper exit at M08A1 music init: the helper's diagnostic heartbeat thread
    kept the raw pointer of each performance it was started for and kept calling it after CloseDown + final Release (heartbeats
    turn to GetTime 88781170 first, then an execute fault in freed memory). Reproduced deterministically by the owned test
    experiments/xrt/tests/dmusic_heartbeat (old helper: exception c0000005 on cycle 1); fixed (one heartbeat following the
    current open performance, cleared before CloseDown/last release/shutdown, own reference while querying): 4/4 cycles,
    dmusic_async_test 11/11 + deadline.
Regressions run: dev.py selftest PASS, bg_input, openal_bridge, staging_reuse, quit_message, viewport_maximize, walk_speed,
port_overlay, openal_churn, dmusic_heartbeat, dmusic_async_test. Save point out/dev-init-savepoints/interactive-20261101
(build-before = the owner-played exe; build = this batch; runtime, runtime-base, dmusic_helper).

Interactive follow-up (2026-11-01 late evening, owner playing; commits ea8349a..a0c5713, same save point):
  - Confirmed by the owner in game: Maximize/Restore/drag-resize windowed; Alt+Enter and Video > Fullscreen enter and
    leave BORDERLESS fullscreen (d3d8_borderless.inc: monitor-sized window and back buffer, the game's resolution in a
    render-target texture, scaled with aspect kept; 2560x1440, 1920x1080, 720x480 seen); UI Scale through a virtual
    viewport size during UUIConsole::PostRender (kept >= a 640x480 layout frame); Walking Speed; F1 (WM_KEYF1/WM_HELP
    answered); X button (WM_CLOSE); system cursor hidden over the game; Video > Resolution follows the mode (window
    size via PORTSET WindowSize, fullscreen render resolution; list keeps display-mode indices stable).
  - Quit: PostQuitMessage, IsZoomed/IsIconic, WM_DESTROY forwarding, msvcr70 swprintf, DestroyWindow before the device
    release and device/resource calls afterwards are handled. Run 20261101-222923: menu Quit -> the game's complete shutdown (engine, viewport, device, audio, DirectMusic helper SHUTDOWN, every DLL_PROCESS_DETACH) -> ExitProcess(0), outcome "exited".
  - DXVK 3.1.1 presents through GDI whenever the back buffer differs from the window client (run 211738): every mode
    keeps them equal. Open: one fullscreen entry asked 800x600 although 720x480 was stored (source unidentified);
    one silent helper exit during a level load (exit code now reported).

Background developer mode (2026-11-01, gameplay batch): dev.py run --background (bench_tuta.ps1 -Background), only with
input isolation. The owner keeps using the desktop; the game window never takes focus and only the --input script reaches it.
  - GUI (hle_gui.c, xrt_dev_background): visible top-level windows are created hidden and shown SW_SHOWNOACTIVATE at
    HWND_BOTTOM; visible top-level dialogs (the startup splash) are created from a template copy without WS_VISIBLE and their
    nonzero WM_INITDIALOG is reported FALSE to the dialog manager (its default focus assignment activates even a hidden
    dialog); ShowWindow activating commands become non-activating; SetWindowPos gets SWP_NOACTIVATE|SWP_NOZORDER;
    SetForegroundWindow is not passed on; SetActiveWindow/SetFocus stay virtual while another process owns the foreground
    (GetFocus/GetForegroundWindow report the guest's own window). Reason (experiments/xrt/tests/bg_input, BG_PROBE=a/d):
    with the owner idle past the foreground lock timeout, a real SetActiveWindow or a dialog's default focus TOOK the
    foreground. No activation messages are synthesized: WinDrv captures the mouse at the first click, so the menu path
    clicks once first (bench_tuta.ps1 -Background).
  - DirectInput (dinput_lifecycle.inc): host cooperative level NONEXCLUSIVE|BACKGROUND instead of the guest's
    FOREGROUND|EXCLUSIVE (which cannot be acquired without the foreground); physical records are still dropped by isolation.
  - Input script (dev_support.c): never pauses for the foreground; a foreground change is still logged ("FOCUS TAKEN" =
    our process became the foreground - e.g. Windows activates the next window when the owner minimizes theirs).
  - Rendering continues behind other windows (DXVK Vulkan swapchain, D3D back-buffer readback for captures, not the desktop).
Owned test: experiments/xrt/tests/bg_input/run.cmd (run with another application in front): 13 checks.
Also new: dev.py --seed-save FILE.usa (a save written by an earlier developer run's sandbox, copied into this run's Save),
input verb size:W:H (window resize inside the guest's PeekMessage), per-launch limit 600 s (owner-authorized batch),
IDirect3DDevice8::Reset (windowed, same window), WM_SIZING/WM_MOVING RECT and WM_SETTINGCHANGE string marshalling.

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

Performance / portability batch (2026-11-01 late evening to 2026-11-02 early morning; commits 7143ee5 and the commit of this note;
owner authorized 20 launches, 600 s each, 9000 s total; used 19 launches / 5421 s, all background-mode scene stops, no fatal).
The owner's other tasks kept 12-27% of the machine busy throughout (package 65-88 W vs 62 W idle in the earlier batches), so every
comparison is an interleaved A/B on the same host state and absolute numbers are 20-30% below the earlier batches'. Full report:
PERF_REPORT_20261101.md. Save points: perf-baseline-20261101 (= the owner-played interactive-20261101 exe, sha256 1f25c656...),
perf-c1-20261101 (recommended), perf-c2-20261101 (clang-cl), perf-final-20261102 (C1 + the --affinity hook).
  - Translation overhead in isolation: experiments/xrt/tests/perf_kernels (five owned kernels shaped like the hot paths, x87 code
    from the x86 compiler, native vs lifted, checksums must match): plain lift 6.5x native, the 2026-10-31 set 1.8x, the new full
    set 1.3x (cl) / 1.3x (clang-cl /fp:strict) / 1.2x (clang-cl /fp:precise, admits FMA on FMA targets: not for the game). Call-heavy
    kernels 1.7-1.9x, loop-heavy 1.0-1.4x: the call protocol is the floor now.
  - xlift --opt cflags (flags dead at indirect/import calls and at returns of address-taken functions; per-module audit with a sound
    fallback; marks/watches and fatal traps are not flag reads; tools/xrt/cflags_allow.json: GlmLib data table at rva 0x1c9790 lifted
    as a trap, 0 executions in 197 runs), rdtsc (inline), lazypc (c->pc stored only before calls/traps/marks/pc-reading helpers; chunk
    source-line tables + xrt_pc_from_host recover a fault's guest pc through the PDB; 1.97 M of 2.6 M stores gone), addr64 ([reg+disp]
    as 64-bit sums, 2 GB guard below the window, xrt_commit asserts the 32-bit user layout). Runtime (patches/perf-batch1-runtime.patch):
    world_floor as a 32-bit CPU field read inline after cached indirect calls (sizeof(CPU) stays 416), XRT_LEAN_ENTER, XRT_RDTSC,
    line-table registration, 6 GB reservation. dev.py: build --lean, build --cc clang-cl, protos/table developer copies when discovery's
    function set changed (Engine -3, UnrImp -30 never-executed memcpy jump-table slots since fb06f2a), run --affinity MASK; the audio
    modules are lifted with the full set (they were plain). Tests: opt_diff full set, two DLL variants, 48000 cases each, 0 mismatches,
    47/47 mutations; forms_equiv; unit tests; staging_reuse, quit_message, fps_cap.
  - Game A/B (bench_tuta -NoCapture -SampleHz 0 -Profile quiet -Res 3840x2160 -Delay 50 -Staging reuse -Background -Monitor; exe swapped
    by copying a save point's exe/pdb/build-state and refreshing its timestamp), group medians, FPS (p95 ms):
      window           baseline (2)    C1 (3)          C1/B    C2 clang-cl (2)   C1 pinned to 2 LPs of CCD0 / of CCD1
      CS_Intro 30-60   156.0 (9.50)    181.0 (8.25)    x1.16   179.0             185.8 / 170.3
      cutscene 96-210  120.3 (13.37)   148.4 (10.89)   x1.23   140.8             173.5 / 143.2
      slow 158-177      82.9 (14.88)    99.3 (12.70)   x1.20    92.3             119.7 / 90.9
      spawn            130.6 (9.63)    147.7 (8.19)    x1.13   143.2             181.7 / 151.0
      movement         180.9 (8.76)    206.7 (7.67)    x1.14   199.5             238.4 / 202.0
      pause menu       297.5 (4.36)    366.4 (3.50)    x1.23   358.9             392.0 / 372.4
    Presents in the 308 s script 58.4 k -> 70.7 k / 76.9 k. clang-cl: within noise in the game (its runs were under heavier host
    load), code .text 75.2 (baseline) -> 61.8 (C1) -> 49.6 MB (C2), compile 95 -> 47 s. 1080p equals 4K within noise. 120 FPS still not
    met in the slow subsection. Profile (sampled C2, slow subsection): translated code 92.6% of leaves (GlmLib animation, D3DDrv
    submission path), runtime self memset 2.4 / dispatch 2.1 / memchr 1.9 / setjmp 1.6 / d8_semantic_checkpoint 1.5 / EH-pad marks 1.5%.
  - CPU sensitivity: the whole process pinned from outside. One core (2 LPs) of the V-cache CCD: +15-23% over unpinned; 2 LPs of the
    other CCD: -10-25%. The translated game is L3-bound and Windows' migration between the dies costs ~20%: dev.py run --affinity 0xFFFF
    (per-process) keeps it on CCD0. For weaker CPUs code size and cache misses come on top of lower single-thread speed; no clock
    reduction is possible here, so no midrange/mobile FPS is claimed.
  - Regressions on C1 (strict staging, 90 FPS cap, sound path on and muted): TutB farewell -> PD_Avalon -> Atlantis -> quicksave OK;
    M08A1 replays reproduce the original route to the millimetre until an NPC in the doorway (first replay) or a Use that misses the
    seal-door panel by the route's 20-30 uu position spread (repeat); the baseline exe stalls identically (last launch): route-script
    brittleness, not a build difference. Combat was therefore not re-exercised in this batch.
  - ARM64/Linux: the exported kernel lift builds with gcc 13 (Linux x86-64, native run) and the local aarch64 gcc 8.3 cross image
    (static), runs under QEMU in arm64 Alpine with all checksums identical to native x86; clang -S: AArch64 0.94x the x86-64
    instruction count. Runtime inventory: 19.9 k lines, 991 Win32/intrinsic references; xrt.h/xrt_cpu.c/xrt_fmt.c/xrt_msvcr70img.c
    portable, the rest Windows-bound (D3D8 HLE on DXVK, GUI/DirectInput/DirectMusic, kernel32/msvcr70, scheduler, memory, diagnostics).
  - Gotchas: the game window becomes the foreground when no other window is active ("FOCUS TAKEN" in background mode, harmless here);
    PowerShell Out-File writes UTF-16 logs; the perf_kernels output dir is shared (one job at a time); Bash heredocs mangle backslashes
    (write patch scripts with the editor); sizeof(CPU) must stay 416 (monitor record image); Unreal2_001.c's line table is renumbered
    after the endpoint hooks (dev.py renumber_pclines).

Performance round 2 (2026-11-02, call/return protocol; PERF_REPORT_20261102.md, save point perf-c3c-20261102 recommended):
  - xlift --opt rv (lifted functions return their return address; protos define XRT_RV_ABI, xrt.h switches the lifted-function
    type and CALL/ICALL/ICALLI/RET; runtime dispatch, EH landing, port wrapper and world observer use XRT_CALL_LIFTED/XRT_TAIL),
    --opt regcache (per-call reload of the live registers only, dirty-only spills; liveness + may-dirty/must-valid passes with a
    conflict fix), --opt restrict (CPU* __restrict). Static: reload loads after calls 1.24 M -> 0.63 M (50.9%), .text 61.8 -> 54.7 MB.
    dev.py: --ltcg, /DXRT_RV_ABI on every unit (a forced include reads xrt.h before the protos header), rv/restrict-aware port
    rename and line-table renumbering, developer-copy units include their own directory (the port-src copy saw the shared protos).
  - Two regcache defects reached the game although opt_diff was green (both fixed, both now owned cases + mutations):
    (1) the synthetic "falls through into the next function" tail got an empty spill set (all 31 such tails stored nothing);
    (2) self-spilling groups (idiv with xrt_div0, marked instructions) write registers after their spill and were treated as
    "nothing dirty afterwards", so a quotient/remainder reaching a call or ret unchanged was never stored. Both showed as
    "D3D8 draw: buffer range outside owned upload" at the first UI label draw. Structural check over UI/D3DDrv/Core (13,666
    functions): spill always first in its group, reload always last, no stray program points. Final suite: 43 functions,
    57,000 cases per DLL variant, 0 mismatches, 28 mutations per variant detected.
  - Game A/B (same method as round 1, uncapped 4K, 2 C1 + 2 C3c + 1 C3Lc runs): matched host load C3c = +3-6% FPS over C1
    (slow subsection 116.2 -> 122.9, p95 10.6 -> 10.1 ms; pause menu +8%); the loaded first C1 run inflates group medians to
    +7-14%. C3Lc (LTCG) = C3c within noise -> LTCG rejected. Kernels: C1 = C3 within noise; call-heavy strings 1.58x -> 1.04x
    native only under /GL (cross-function inlining is the lever; the game's dispatch structure defeats the compiler's).
  - Smoke test of C3c with --affinity 0xFFFF (2 launches): affinity, load, movement, port settings, sound (audible OpenAL mix),
    quicksave (Save0.usa rotation), quickload all pass; the scripted QUIT clicks in the in-game menu did not register twice,
    so a normal shutdown is NOT verified this round. Combat route not re-exercised (budget); v2 route prepared.
  - Launch ledger: owner granted 10 launches / 4,500 s; used 10, 1,846 s (2 fatals of defective builds, 1 bisection, 5 A/B,
    2 smoke). Save points perf-c3-20261102, perf-c3l, perf-c3b, perf-c3lb (defective, marked), perf-c3c (recommended, with an
    evidence/ folder: kernel JSON, suite logs, perf JSONs, ledger, scripts, smoke shots), perf-c3lc. Generated sources in
    C:\Users\lawma\Unreal2-dev-sandbox-overflow\generated-perf-c3*-20261102 (SHA256SUMS). Runtime patch patches/perf-batch2-runtime.patch.
  - Gotchas: a play profile's WindowsClient.ini forces a 2560x1440 viewport (recorded 4K cursor paths miss); a non-default UIScale
    changes the menu geometry; the tutb-farewell save opens with a ~90 s cinematic (use the lift-corridor save for smoke tests);
    Start-Process powershell sessions wrote empty Get-FileHash results (hash in pwsh or Python); PowerShell *> logs are UTF-16.
