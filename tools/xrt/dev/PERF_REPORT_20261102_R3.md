# Unreal II static recompilation: performance round 3 (frame-cost attribution, V-cache, D3D8 HLE), 2026-11-02

**Summary.** One frame of Unreal II on C3c is about half translated game code and half runtime. In the slowest TutA
subsection (9.2 ms per frame, game thread 98% of one core) translated code takes 4.6 ms (Golem animation 2.2, engine
0.9, renderer 0.7, script/core 0.6) and the runtime 4.4 ms, of which the D3D8 HLE layer alone is 3.1 ms: its strict
buffer staging (fresh committed block per Lock, `VirtualQuery`, four copies, byte-per-byte validity map, decommit per
Unlock) and per-call validation/evidence work, not Direct3D or the driver (0.13 ms). V-cache sensitivity is explained by
footprint: the translated code is ≥6.6x denser than the original on the hot path and the runtime copies every staged
byte through several buffers, so a frame touches ~59 MB of pages — beyond a 32 MB L3, within 96 MB. The standard die
runs 25-31% slower than the V-cache die despite a higher clock; packing the hot code recovers 10-17% there and nothing on
the V-cache die; taking L3 away on the same die costs 7-12%. Accepted: **S2** (exact-answer fixes in the strict staging
and evidence path: +3-5% FPS on CCD0, every window, both runs) and the **hot-code link order** (+10-17% on CCD1, neutral
on CCD0); measured as an opt-in: **guard staging** (strict's stale-pointer trap with the block kept committed but
`PAGE_NOACCESS`; +3-6% over strict on the same binary). The recommended build is save point `perf-r3-20261102` (all
three, strict staging by default). The original executable could not be benchmarked inside the authorized harness; a
historical traced run bounds native CS_Intro at ≥1.4x C3c. Normal shutdown, combat (hits both ways), sound, music,
saves, resize and UI scale were exercised on the final build. 20 of 24 launches used (5,394 s of 12,000 s).

Scope and rules: C3c (`out/dev-init-savepoints/perf-c3c-20261102`, exe SHA-256 `57dde851…`, HEAD `776fb8c`) is the
baseline; every game launch went through the existing contained developer harness (`tools/xrt/dev/dev.py run`, background
mode, fresh sandbox per run) inside the owner's round-3 budget (24 launches, 600 s each, 12,000 s total). No supervisor,
policy, ledger, original asset or personal save was touched; the uncommitted `experiments/xrt` runtime edits of another
actor (Oct 25-30) were left alone. All numbers are from this machine (Ryzen 9 9950X3D: CCD0 = LPs 0-15 with the 96 MB
V-cache L3, CCD1 = LPs 16-31 with 32 MB; RTX GPU under DXVK 3.1.1) while the owner's other tasks kept 14-23% of the
machine busy, so only interleaved runs under recorded host load are compared.

## A. How fast is the original game?

**No valid native benchmark could be made inside the authorized boundary.** The developer harness accepts only its own
translated executable (`dev.py run` refuses anything else). The only existing tool that starts the original
`Unreal2.exe` (`tools/xrt/graphics_reference.py`, the strict-pipeline graphics investigation) runs it in a fresh sandbox
copy under the `uctrace` debugger with breakpoints on `UGameEngine::Tick`, `ULevel::Tick`, the Present calls and
`AActor::eventTick`, caps a run at 120 s and has no input path, so it can neither reach TutA (New Game needs menu input)
nor time frames without the debugger's per-event round trips. Building a new launcher for the original was outside
the authorization ("no new supervisor / launch system"), so the original was not launched in this round.

What exists is one historical traced run of the original client in CS_Intro (`experiments/xrt/results/raw/
graphics-startup/f54e61270742-dgvoodoo`, 2026-10-22: dgVoodoo 2.87.5 D3D8 -> D3D11, `CS_Intro.un2 -windowed -nosound
-NOMMX -NOSSE`, 30 s time limit): **9,016 frames presented within 30 s of process start** (startup, Init and map load
included), i.e. at least 300 frames/s on average and roughly 350/s after a few seconds of startup, *while* the debugger
took six breakpoint events per frame. The translated C3c presents 5,380-5,680 CS_Intro frames in the first 25 s after
its Init returns (215-227/s; runs `20261102-124315`, `-041107`, `-035334`). Qualified reading: in this scene the native
game is **at least ~1.4-1.6x as fast as C3c, probably more** (the original was slowed by the tracer, the scenes are the
first seconds of the same map but music timing differs, and the original draws through dgVoodoo/D3D11 instead of DXVK;
both are CPU-bound at these rates). The kernel benchmark of rounds 1-2 (translated code 1.3-1.5x native on owned
kernels) and section B (half of the game thread is runtime, not translated code) are consistent with a native-vs-C3c
factor of roughly 2x in gameplay.

Requirements for a defensible native comparison (for an owner decision, not done here): an owner-authorized launch
path for the original `Unreal2.exe` from an isolated copy (same sandbox snapshot, its own `System\*.ini` and `-windowed`
at 3840x2160, DXVK 3.1.1 x86 `d3d8.dll`/`d3d9.dll` pinned exactly as the port uses them, `-nosound` or the same sound
setting), *without* a debugger attached, with the same scripted input (the harness's input verbs would need an external
injector for a native process) and a frame log (DXVK's own `DXVK_HUD`/frame-time CSV would do), run on the same pinned
cores. The original's timer is `appSeconds` on RDTSC with no engine frame cap observed (≈350 FPS under a tracer), so an
uncapped comparison is possible once such a launch path exists.

## B. Where frame time goes (C3c)

Method: one sampled benchmark launch of a profiling build that has exactly C3c's 265 generated units (hash-verified
against the C3c overflow copy) plus round-3 diagnostics: game-thread host stacks at 250 Hz with 128 frames (was 24),
classified once per sample (no double counting) by *phase* (outermost engine stage on the stack) and by *category*
(where the thread is); per-frame cost counters (`perf_counters.h`: D3D calls, draws, buffer/texture Locks, bytes,
rdtsc time in the HLE, staging alloc/free); and a working-set probe. The profiled run is within 1-2% of an unprofiled
C3c run in every window (sampling overhead small). Same benchmark as rounds 1-2 (`bench_tuta.ps1 -NoCapture -Delay 50
-Res 3840x2160`, uncapped), strict staging, process pinned to CCD0 (`--affinity 0xFFFF`), sound off.

Mean frame time split by cost group (sample share x mean frame time; run `20261102-124315-253eb8ad`, profiling save
point `perf-c3c-profws-20261102`; game thread 97-99% of a core in every gameplay window, so wall time ≈ CPU time):

| cost group | CS_Intro (195 FPS) | cutscene (167 FPS) | slow subsection (108 FPS) | spawn (170 FPS) | movement (230 FPS) | pause menu (341 FPS) |
|---|---|---|---|---|---|---|
| translated: animation (GlmLib) | 0.16 ms (3%) | 1.13 ms (19%) | 2.24 ms (24%) | 0.77 ms (13%) | 0.23 ms (5%) | 0.00 ms (0%) |
| translated: engine (Engine) | 0.22 ms (4%) | 0.80 ms (13%) | 0.88 ms (10%) | 0.88 ms (15%) | 0.65 ms (15%) | 0.04 ms (1%) |
| translated: script VM + core (Core) | 0.31 ms (6%) | 0.45 ms (8%) | 0.62 ms (7%) | 0.62 ms (11%) | 0.60 ms (14%) | 0.33 ms (11%) |
| translated: renderer (D3DDrv) | 0.17 ms (3%) | 0.52 ms (9%) | 0.72 ms (8%) | 0.49 ms (8%) | 0.37 ms (9%) | 0.08 ms (3%) |
| translated: UI | 1.16 ms (23%) | 0.03 ms (0%) | 0.04 ms (0%) | 0.13 ms (2%) | 0.13 ms (3%) | 0.78 ms (27%) |
| translated: other modules | 0.32 ms (6%) | 0.16 ms (3%) | 0.12 ms (1%) | 0.14 ms (2%) | 0.13 ms (3%) | 0.08 ms (3%) |
| **D3D8 HLE: buffer/texture staging** | 0.74 ms (14%) | 0.98 ms (16%) | **2.08 ms (23%)** | 0.84 ms (14%) | 0.72 ms (17%) | 0.63 ms (22%) |
| **D3D8 HLE: per-call validation/evidence** | 0.18 ms (4%) | 0.85 ms (14%) | **1.08 ms (12%)** | 0.84 ms (14%) | 0.50 ms (12%) | 0.05 ms (2%) |
| graphics driver (DXVK/Vulkan/NV) on the game thread | 0.03 ms (1%) | 0.10 ms (2%) | 0.13 ms (1%) | 0.08 ms (1%) | 0.07 ms (2%) | 0.02 ms (1%) |
| EH pads + monitor marks (setjmp, register/pop, mark/forget) | 1.24 ms (24%) | 0.26 ms (4%) | 0.36 ms (4%) | 0.28 ms (5%) | 0.29 ms (7%) | 0.54 ms (18%) |
| import/indirect dispatch | 0.10 ms (2%) | 0.33 ms (6%) | 0.45 ms (5%) | 0.40 ms (7%) | 0.30 ms (7%) | 0.13 ms (5%) |
| x87/libm helpers | 0.02 ms (0%) | 0.08 ms (1%) | 0.15 ms (2%) | 0.10 ms (2%) | 0.02 ms (0%) | 0.00 ms (0%) |
| blocked waits (Present, baton) | 0.34 ms (7%) | 0.14 ms (2%) | 0.08 ms (1%) | 0.11 ms (2%) | 0.17 ms (4%) | 0.17 ms (6%) |
| OS calls, other runtime | 0.14 ms (3%) | 0.16 ms (3%) | 0.26 ms (3%) | 0.19 ms (3%) | 0.16 ms (4%) | 0.08 ms (3%) |
| **mean frame** | **5.13 ms** | **5.99 ms** | **9.22 ms** | **5.87 ms** | **4.35 ms** | **2.93 ms** |

Phases: rendering (`UGameEngine::Draw` and below, including the skinned-mesh animation that `ULegendMeshInstance::Render`
evaluates) is 70-91% of every window; the world tick (`ULevel::Tick`: actors, script, physics) 14-24%; Present 1-6%.
Audio (lifted ALAudio + OpenAL adapter) was off in this benchmark; the combat run (section B.2) covers it.

Per-frame counters (same run):

| window | D3D8 calls | draws | buffer Locks (bytes) | DISCARD Locks (valid-map bytes cleared) | texture Locks | HLE time (of which Lock / Unlock / pool commit+decommit) |
|---|---|---|---|---|---|---|
| cutscene | 2,957 | 240 | 94.6 (0.78 MB) | 5.9 (0.62 MB) | 1.1 (295 KB) | 1.89 ms (0.52 / 0.30 / 0.34) |
| slow subsection | 4,163 | 317 | 215.5 (1.70 MB) | 11.8 (1.30 MB) | 1.1 (279 KB) | 3.12 ms (1.14 / 0.65 / 0.73) |
| movement | 1,871 | 178 | 72.8 (0.51 MB) | 5.5 (0.59 MB) | 1.1 (282 KB) | 1.35 ms (0.38 / 0.21 / 0.23) |
| pause menu | 384 | 51 | 101.8 (0.70 MB) | 6.3 (0.76 MB) | 0 | 1.01 ms (0.52 / 0.28 / 0.29) |

What the numbers say:

1. **Half of the game thread is not translated game code.** In the slowest subsection 4.6 ms of 9.2 ms is translated code
   (animation 2.2, engine 0.9, renderer 0.7, script/core 0.6) and 4.4 ms is runtime: the D3D8 HLE layer alone is 3.1 ms
   (34%), import dispatch 0.45, EH bookkeeping 0.36, x87 helpers 0.15. The graphics driver itself costs the game thread
   0.13 ms; DXVK's own threads use 5-10% of other cores; the GPU is never the limit (frame time is resolution-independent).
2. **The D3D8 cost is the safety design, not D3D work.** Per buffer Lock/Unlock (5.3 + 3.0 µs in the slow subsection) the
   strict staging path commits a fresh guest block, queries it twice with `VirtualQuery`, copies shadow -> block (first
   touch faults zero-filled pages), scans a byte-per-byte "valid" map, then at Unlock heap-allocates a snapshot, copies
   three times, sets the valid map and decommits the block; a DISCARD Lock clears the *whole* buffer's valid map. Leaf
   samples under Lock/Unlock: `NtFreeVirtualMemory` 4.2-6.0%, `NtQueryVirtualMemory` 2.1-4.7%,
   `NtAllocateVirtualMemory` 2.0-3.4%, copies 2.8-4.6%, pool scans 1.3-2.1%. Every other D3D8 call (≈0.34 µs each) pays
   argument-range checks, two window identity checks (`IsWindow`, `GetWindowThreadProcessId`, registry scan), four
   evidence checkpoints with MXCSR/LastError save-restore, and a monitor scope; draws additionally scan the valid map
   over every vertex and index range they read (`memchr` 1.7%) and query the native stream/index bindings.
3. **EH registration is the UI's main cost.** Unreal's `guard/unguard` puts a C++ try frame in 7,908 of the 60,042
   translated functions; each entry costs a `setjmp` (≈25 stores), a landing-pad push and a monitor mark. In gameplay
   that is 4-7%; in the UI-heavy CS_Intro and pause menu it is 18-24% of the frame.
4. **Translated code: animation dominates the slow frames.** `ULegendMeshInstance::Render` -> `RefreshVertexCache` /
   `RefreshScriptProcesses` (Golem skeletal animation and CPU skinning, then the dynamic vertex-buffer uploads that drive
   the Lock count) is 31.6% inclusive in the slow subsection; the single hottest leaf is GLM `RObject::Cast` (2.4%).

### B.2 Combat and audio (M08A1, sound on)

Sampled launch `20261102-143132-0723caeb` of the final candidate R3 (section D; strict staging, CCD0, `--sound on`,
250 Hz), from the round-1 checkpoint before the Puppeteer fight: the player faces the Puppeteer Izarian and fires in
1.5 s bursts for 24 s, is attacked by the Izarian pack and dies; then 9 s of death camera with the level running.

| cost group | combat 22-46 s (154 FPS, median 6.18 / p95 7.64 ms) | after the fight (164 FPS) |
|---|---|---|
| translated: animation / engine / script+core / renderer / other | 1.06 / 1.05 / 0.78 / 0.31 / 0.30 ms (53%) | 0.86 / 1.41 / 1.04 / 0.25 / 0.35 ms (64%) |
| D3D8 HLE: staging / per-call | 0.90 / 0.44 ms (21%) | 0.68 / 0.34 ms (17%) |
| import dispatch / EH pads / x87 helpers | 0.44 / 0.30 / 0.08 ms (13%) | 0.33 / 0.25 / 0.06 ms (10%) |
| audio on the game thread (lifted ALAudio + Vorbis + OpenAL adapter) | 0.02 ms (0.4%) | 0.06 ms (1%) |
| graphics driver, waits, OS/other runtime | 0.80 ms (12%) | 0.50 ms (8%) |

The world tick is 35-49% here (TutA: 14-24%): combat AI and script. Audio is negligible on the game thread even with
the known ALAudio re-trigger churn (77,090 OpenAL plays in the 73 s combat launch `-142701`, 18 voices playing, mix
peak 0.25, 0 glitches); XAudio2 mixes on its own threads. Per frame: 1,659 D3D8 calls, 124 draws, 134 buffer Locks
(0.72 MB), HLE time 1.41 ms.

## C. Why V-cache helps

No hardware counters were available: the session is not elevated, so WPR/ETW PMC sampling is impossible, and no
driver was installed. The conclusions below come from four direct measurements plus controlled launches; what is
inferred is marked.

**C.1 Footprint of one frame (measured).** A working-set probe (`ws:0` empties the process working set at a frame
boundary, `ws:1` 110 ms later counts the pages touched again, by region) in the slow subsection: translated + runtime
code (`.text`) 6.5 MB, other image sections 2.6 MB, guest memory 14.0 MB, DXVK/driver/system DLL images 3.3 MB, host
heaps and driver mappings 32.3 MB — **≈59 MB of pages per ~10 frames; over a full second only ≈68 MB**, i.e. nearly the
same pages are touched every frame. Page granularity over-counts lines, so this is an upper bound per page, but it
places the per-frame working set between the standard die's L3 (32 MB) and the V-cache die's (96 MB). Pause menu:
code 2.4 MB, guest 5.7 MB, other 22.4 MB.

**C.2 Code density (measured).** 9,770 of the 60,534 translated functions execute in a whole run; they are 16.0 MB of
host code for at most 1.86 MB of original x86 (≥8.6x). The functions on sampled stacks in the slow subsection are
3.0 MB of host code (90% of the translated leaf samples sit in 192 functions, 1.6 MB); sample-weighted expansion of the
hottest functions against their x86 bytes is 6.6x (7.4x by bytes; small functions worst: GLM `RObject::Cast`, 64 B of
x86, 655 B translated). In the current link layout the executed functions occupy 5,687 pages (23.3 MB) although they
would fit in 3,932 packed. The native game's hot code fits in an L2; the translation's does not.

**C.3 What each die does with such footprints (owned microbenchmark, `experiments/xrt/tests/cache_sweep`, one core,
repeated twice).** Random 64-byte data loads stay at 10-15 ns up to 32 MB on the V-cache die (17 ns at 48 MB, 23 at
64 MB, 50 at 96 MB) but jump to 36-74 ns at 16 MB and 84-87 ns at 24-32 MB on the standard die; random calls into
256-byte code blocks cost ≈30 ns up to 32 MB on CCD0 but 56-112 ns from 24 MB on CCD1. The standard die clocks
3-4% higher (5.56-5.63 vs 5.41-5.48 GHz on a dependent ALU chain). So for a 15-60 MB working set the V-cache die serves
from L3 what the standard die must fetch from DRAM (~6x the latency), while for anything below ~12 MB the standard
die is slightly faster.

**C.4 Controlled launches (same benchmark, strict staging, uncapped 3840x2160).**

| experiment | runs | result |
|---|---|---|
| cross-die: C3c on 8 cores of CCD1 vs 8 cores of CCD0 | `-132204` vs `-125714`, `-130818` | CCD1 slower by 25-31% FPS in cutscene/slow/spawn/movement (median frame +36 to +47%, p95 +39 to +43%), 17% in the pause menu, 7% in CS_Intro, although its cores clock 3-4% higher; the loss follows the window's footprint (C.1: the pause menu touches about half the pages of the slow subsection) |
| code locality: S2 with/without the hot-code order, both dies (D.2) | ABBA on CCD1; one order run on CCD0 vs two S2 runs | packing the hot functions recovers **+10-17%** on CCD1 and **0%** on CCD0: on the small L3 a large part of the penalty is instruction-side (lines and pages of scattered translated code); with the order the CCD1 deficit in the slow subsection falls from 31% to 21% (79 -> 91 vs 115 FPS) |
| same-die capacity: C3c on cores 0-3 of CCD0, without/with three 20 MB hot pointer-chase loops on cores 4-6 of CCD0 | `-140322` vs `-140855` | **-7 to -12% FPS** in the gameplay windows (slow subsection 114.8 -> 101.5, median 8.64 -> 9.79 ms, p95 +14%), -4% in the pause menu. Validation without the game: those polluters cut one core's effective L3 on CCD0 from ~80 MB to ~24-32 MB; they also lower its clock 1-4% and add L3 traffic, so part of the 7-12% is not capacity |
| migration (round 1, not repeated) | C1, unpinned vs 2 LPs of CCD0 | unpinned 13-19% slower than pinned to 2 LPs of the V-cache die |

**Conclusion.** Established: (1) the translated game's per-frame working set (≈59 MB of pages, re-touched every frame)
is larger than a 32 MB L3 and smaller than 96 MB; (2) on the 32 MB die it runs 25-31% slower than on the V-cache die
despite the higher clock, and the loss scales with the scene's footprint; (3) instruction-side locality is a large,
directly demonstrated part of that loss (hot-code packing removes about a third of the gap on CCD1 and does nothing on
CCD0); (4) taking L3 capacity away on the *same* die and clock costs 7-12%, so capacity itself, not only die or clock
differences, matters. Plausible but not isolated: the remaining CCD1 deficit is data-side capacity (14 MB of guest data
and ~32 MB of host heaps, staging blocks, shadows and driver mappings per frame) plus 12-17% higher DRAM latency
measured from that die; thread migration when unpinned adds another 13-19% (round 1). The root causes are the
translation's code density (≥6.6x the native bytes on the hot path) and the runtime's data traffic (each staged byte is
copied 4-5 times through distinct buffers, and strict staging cycles fresh zeroed pages), not the game's own data:
the original game's hot code fits in an L2. So the V-cache gain is mainly **cache capacity for an inflated instruction
and data footprint**, with **migration** as a separate, configuration-level cost; memory bandwidth was not found to
matter (the game thread is latency-bound at 95-99% of one core).

## D. What was optimized

### D.1 S2: strict D3D8 staging and evidence path made cheaper with identical answers (accepted)

Save point `perf-s2-20261102` (exe `CDC63D40…`): the C3c generated code (hash-verified identical) with the runtime patch
`tools/xrt/dev/patches/perf-batch3-runtime.patch` (against the C3c runtime). Strict staging keeps its definition — a
fresh guest block per buffer/texture Lock, decommitted at Unlock, so a guest pointer kept past Unlock faults — and
every check keeps its answer:

| change | what it removes | why the answer is the same |
|---|---|---|
| validity bitmap (`d8_valid_bits.h`): one bit per buffer byte instead of one byte | 7/8 of the valid-map traffic at Lock (undefined-byte evidence), at every draw (vertex/index ranges) and at every DISCARD Lock (whole-buffer clear) | `d8_valid_all`/`d8_valid_set` are the bit forms of `memchr(...,0,n)`/`memset(...,1,n)`; owned test `experiments/xrt/tests/staging_bitmap` compares both forms over 110,380 random range checks and 109,620 set/clear operations on 11 buffer sizes, every bit equal, guard bytes around the map intact |
| Unlock snapshot straight into the host shadow (buffers) | a `HeapAlloc`/`HeapFree` and one full copy per buffer Unlock | the guest range is revalidated first as before; the native buffer is then filled from the shadow, so shadow and native buffer hold the same snapshot bytes as before (textures, which have no shadow, keep the heap snapshot) |
| LockRect zero-fills only each row's pitch padding | a `memset` of the whole staging block before the row copies | every byte outside the padding is overwritten by the row copy right after |
| staging-block range hints seeded at commit | two `VirtualQuery` calls per Lock (`xrt_is_committed` + `d8_device_memory`) | the HLE has just committed the block read-write (`xrt_commit` exits on failure); a later overlapping decommit still invalidates the hint through the decommit log |
| decommit log 64 -> 1,024 entries | re-queries of stack/heap argument ranges after every 64 unrelated staging decommits (a frame makes 100-220) | a hint is still dropped when any logged decommit overlaps it; more history only means fewer false invalidations |
| evidence checkpoints skip their MXCSR/LastError save-restore once the event timeline is full | 4 `ldmxcsr` + `Get/SetLastError` pairs per D3D8 call | with a full timeline `xrt_event` only counts the event; `xrt_event_skip` does exactly that (the dropped-event count in the runtime report stays exact) |

Tests before any launch: `staging_bitmap` PASS, `staging_reuse` PASS (22 checks of the guest VirtualAlloc pool against the
modified `xrt_mem.c`), `dev.py selftest` PASS.

Whole-game A/B, interleaved C3c, S2, C3c, S2 (runs `20261102-125714`, `-130246`, `-130818`, `-131349`), strict staging,
uncapped 3840x2160, process pinned to CCD0 (`--affinity 0xFFFF`), sound off; FPS per run -> group median, median/p95 ms:

| window | C3c | S2 | S2 / C3c |
|---|---|---|---|
| CS_Intro 30-60 s | 187.7, 193.8 -> 190.7 (4.90 / 7.69) | 199.5, 201.4 -> 200.5 (4.63 / 7.44) | FPS x1.051, median ms x0.946, p95 x0.967 |
| cutscene 96-210 s | 168.3, 171.5 -> 169.9 (6.51 / 9.18) | 173.7, 176.9 -> 175.3 (6.29 / 8.94) | x1.032, x0.966, x0.973 |
| cut 150-210 s | 134.1, 137.0 -> 135.5 (7.47 / 9.68) | 139.9, 141.5 -> 140.7 (7.12 / 9.48) | x1.038, x0.953, x0.979 |
| slow 158-177 s | 110.8, 113.1 -> 112.0 (8.84 / 10.35) | 114.8, 115.9 -> 115.4 (8.58 / 10.30) | x1.030, x0.970, x0.994 |
| spawn 220-230 s | 173.6, 178.5 -> 176.1 (5.61 / 6.66) | 183.3, 186.6 -> 184.9 (5.34 / 6.33) | x1.050, x0.951, x0.950 |
| movement 230-245.5 s | 225.9, 233.3 -> 229.6 (4.04 / 6.52) | 238.3, 243.5 -> 240.9 (3.86 / 6.19) | x1.049, x0.954, x0.949 |
| pause menu | 348.4, 365.2 -> 356.8 (2.71 / 3.43) | 366.7, 368.8 -> 367.7 (2.62 / 3.39) | x1.031, x0.965, x0.988 |

In every window both S2 runs are faster than both C3c runs (the two C3c runs differ by 1.9-4.8%), and the S2 runs had
the *heavier* host load (machine utility 22.1% and 27.4% vs 18.8% and 18.3%; package 86-98 W vs 81-83 W), so
**+3-5% FPS, median frame time -3 to -5%** is a conservative reading. Mechanism, from the S2 run's counters (slow
subsection, per frame): valid-map bytes scanned 1.70 MB -> 0.20 MB, cleared 1.30 MB -> 0.15 MB, one heap block and one
copy fewer per Unlock (215 per frame), two `VirtualQuery` per Lock fewer. The game thread stays CPU-bound (95-97% of a
core); its kernel share in the cutscene fell from 9.1-9.5% to 8.5-8.7%. Portability: all six changes are plain C on the
runtime's existing abstractions (bit operations, `memcpy`, the decommit log); none depends on Windows beyond what the
staging path already uses, and the bitmap halves the work on any CPU with small caches.

### D.2 Hot-code link order (accepted: large gain on the 32 MB die, neutral on the V-cache die)

Hypothesis from C.2: the ~3-6.5 MB of hot translated code is scattered over 57 MB of `.text` (the linker keeps unit
order, i.e. guest address order), so a frame touches ~2,300 code pages and their L2/L3/TLB entries; packing the hot
functions should matter where the cache cannot hold everything (CCD1) and not where it can (CCD0). Change: `dev.py build
--order FILE` links with `/ORDER:@FILE` (the generated units are `/O2`, which implies `/Gy`: every translated function is
its own COMDAT); the order file `tools/xrt/dev/order-c3c-tuta.txt` lists the 1,359 translated functions found on sampled
stacks in the P1 TutA windows (by leaf samples, then stack samples) followed by the other 8,305 functions the run
executed. Result in the image (save point `perf-s2order-20261102`, same objects as S2): the hot set spans 6.5 MB on 1,591
pages instead of 56.7 MB on 2,295; all executed functions sit on 3,950 pages instead of 5,688. No code changes, so
correctness is the object files' (same as S2).

FPS per run, same benchmark, CCD1 = `--affinity 0xFFFF0000` (8 cores of the 32 MB-L3 die), runs in ABBA order
(`-132736` S2order, `-133310` S2, `-135209` S2, `-135746` S2order); machine utility in brackets:

| window | S2 on CCD1 | S2 + order on CCD1 | ratio (group medians) | S2 + order vs S2 on CCD0 |
|---|---|---|---|---|
| CS_Intro | 146 (29%), 144 (30%) | 156 (24%), 170 (30%) | x1.12 | x1.025 |
| cutscene | 122 (30%), 118 (32%) | 139 (20%), 143 (30%) | x1.17 | x0.994 |
| slow subsection | 80 (29%), 79 (31%) | 90 (18%), 91 (29%) | x1.14 (median ms x0.88) | x0.997 |
| spawn | 125 (30%), 124 (31%) | 134 (24%), 143 (32%) | x1.11 | x0.995 |
| movement | 167 (31%), 168 (32%) | 176 (25%), 192 (31%) | x1.10 | x1.000 |
| pause menu | 290 (30%), 293 (30%) | 292 (26%), 331 (31%) | x1.07 | x0.999 |

The second order run (`-135746`) had the same heavy host load as both S2 runs and is 13-21% faster in every gameplay
window, so the gain is not a load artefact: **+10-17% FPS, median frame time -8 to -14% on the standard die; no change
(±1%) on the V-cache die** (`-133849` vs the two S2 CCD0 runs). It costs nothing at run time and nothing in
correctness; the order file must be regenerated when the lift changes (names are guest addresses) and should be built
from several scenes (TutA alone is the measured basis). Portable form: `-ffunction-sections` plus an ordering file
(lld `--symbol-ordering-file`) on Linux/Android, so the same profile can drive the ARM64 build.

### D.3 The price of the strict staging policy (measured, not changed)

Same S2 executable with `--staging reuse` (the existing, explicitly labelled developer mode: per-size warm blocks, stale
pointers not trapped), run `20261102-134421`, CCD0, utility 21.7%, against the two S2 strict runs: CS_Intro x1.09,
cutscene x1.07, slow subsection x1.11 (p95 x0.89), spawn x1.05, movement x1.07, pause menu x1.14. After S2, the
strict policy itself (commit, first-touch zero fill and decommit of a fresh block per Lock) still costs 5-14% of the
frame rate. Whether that diagnostic guarantee is worth it in a play build is the owner's decision; section D.4 measures
a cheaper way to keep it.

### D.4 Opt-in `guard` staging: strict's guarantee at about half of strict's price (measured; default unchanged)

`dev.py run --staging guard` (new; `strict` stays the default and is untouched; save point `perf-r3-20261102`): at
Unlock the buffer's staging block is kept committed but set `PAGE_NOACCESS` instead of being decommitted, and the
range is logged in the decommit log so every range hint over it is dropped; a later buffer Lock of the same 64 KiB size
class re-opens only the pages it needs read-write, zeroes them past the locked bytes, and receives the shadow bytes as
always. A guest pointer kept past Unlock therefore faults exactly as in strict mode (same access violation, same
`d8_device_memory` refusal), and a Lock sees exactly what a fresh strict block shows; what goes away is the page-fault
zero-fill of fresh pages and the decommit's page freeing (the two protection changes remain). Reclaim under pool
pressure decommits guarded blocks like reuse mode's warm blocks; ordinary guest `VirtualAlloc` and reuse mode never
receive one. Owned test `experiments/xrt/tests/staging_guard` (20 checks: NOACCESS after put, fault on a stale pointer,
hint invalidation, exact re-open size, zero past the request, commit growth, isolation from VirtualAlloc/reuse, reclaim)
PASS; `staging_reuse` still PASS. Textures/surfaces stay strict.

Same R3 binary, CCD0, matched host load (machine utility 28.9% vs 29.4%; runs `20261102-141557` strict,
`-142130` guard): CS_Intro x1.055, cutscene x1.047, slow subsection x1.058 (median 8.93 -> 8.42 ms, p95 10.64 -> 9.84),
spawn x1.042, movement x1.029, pause menu x1.063. One pair only, but every window moves the same way and the host load
was equal; `reuse` (no stale-pointer trap) is still a further ~5% ahead. Recommendation: offer `guard` as the play
setting if the owner wants the trap without most of its cost; keep `strict` for diagnosis.

## E. What did not work, or was not pursued, and why

- **S2 on the 32 MB die alone**: within noise of C3c there (one run each, the S2 run under 29-31% host load); the S2
  gain is measured on CCD0, the order gain on CCD1. Not a rejection, an unresolved measurement.
- **Caching the D3D8 window checks** (`IsWindow`, `GetWindowThreadProcessId`, registry scan on two windows per call,
  ~1.5% of the cutscene): not done. Window validity is OS state that can change outside the runtime (e.g.
  `DefWindowProc` destroying a window without the GUI adapter seeing a `DestroyWindow`), so a cache cannot give the
  same answer by construction.
- **Skipping the shadow->staging copy for bytes D3D defines as undefined** (84-95% of buffer Locks include such bytes):
  rejected; it would change guest-visible bytes compared with strict staging, which promises the shadow's bytes.
- **Indexing the guest VirtualAlloc pool** (linear scans in `xrt_virtual_alloc/free`, 1.3-2.1% in cutscenes): not done
  this round; it must keep the exact first-fit choice (guest-visible addresses), so it needs its own equivalence test.
- **EH landing pads without `setjmp`**: scoped, not implemented (translator + runtime change, see G.2).
- **Original executable benchmark**: not possible inside the authorized boundary (section A).
- **Hardware counters**: not available (not elevated; no driver installed by design).
- **Profiling-build artefacts, recorded**: the 128-frame sampler cannot unwind past `ULegendMeshInstance::Render` (its
  host frame is larger than the 64 KB stack copy; attributed to rendering by its only caller), and one
  `RtlVirtualUnwind` read past that copy raised a first-chance access violation that the sampler's own handler caught
  (the runtime's VEH wrote `crash.dmp` once; the game was unaffected). xrt.log's 50,000-line budget is consumed early by
  31,107 `_controlfp` lines, so late `port:` lines can be missing (counters.csv carries the round-3 data instead).

## F. What this implies for weaker hardware

Known: (1) the port needs one fast core — the game thread is 95-99% of a core in every window, other threads need a
fraction of a second core (DXVK 5-10%); (2) a third to a half of that core's time is runtime overhead that has nothing
to do with Unreal II (D3D8 HLE safety design, EH bookkeeping, dispatch); (3) the working set is ~60 MB of pages per
frame with ≥6.6x code expansion on the hot path, and a 32 MB L3 die already loses 25-31% against a 96 MB one at a
higher clock. Mainstream desktop CPUs have 16-36 MB of L3 shared by all cores (laptops 8-24 MB, phones 4-16 MB of
system-level cache with 0.5-2 MB L2 per big core): **on all of them the translated game will behave like, or worse
than, the CCD1 case**, so the measured CCD1 numbers (C3c slow subsection 81 FPS, with S2 + order 91 FPS at heavy host
load) are an optimistic ceiling for a mainstream desktop with a core of 9950X-class speed, not a prediction.
Not known, and not claimed: frame rates on any specific weaker CPU or on Android. No lower-end hardware was available,
clock reduction would need machine-wide settings, and affinity cannot emulate a weaker core (it only selects a die).
What the measurements do say for ARM64/Android: the two accepted changes are portable C/link-order techniques and help
most where caches are small (the order gain appears only on the small-L3 die); the D3D8 HLE cost would be paid on
every platform that keeps this HLE (DXVK runs on Linux/Android Vulkan, so the layer ports as is), and its strict staging
costs page-table work that is slower on mobile kernels — the guard or reuse staging policy matters more there.

## G. Next steps, ranked by expected whole-game benefit and risk

1. **D3D8 HLE production path** (benefit: up to ~25% of frame time; risk: low-medium; runtime only). The layer costs
   3.1 ms of a 9.2 ms slow frame. Concretely: (a) owner decision on the staging policy for play builds — strict costs
   5-14% FPS against reuse after S2; the opt-in guard mode (D.4) keeps strict's fault-on-stale-pointer guarantee at
   lower cost; (b) a per-device validated-state fast path for the state setters (texture stage, render state, stream
   source: ~0.25 µs of HLE work per call, ~3,000 calls per frame) that keeps the argument checks but drops the repeated
   window identity checks and evidence work per call, with invalidation on the GUI adapter's window events; (c) an
   exact index for the VirtualAlloc pool scans (1-2%).
2. **EH landing pads without `setjmp`** (benefit: 4-7% in gameplay, 18-24% in UI-heavy scenes and menus; risk:
   medium-high; translator + runtime). 7,908 functions register a guard/unguard frame. Replace the `setjmp` at
   registration with table-based host SEH (`__try/__except` around the function body after registration, landing by
   `RaiseException` from the EH dispatcher; MSVC/clang-cl support it in C), or a minimal assembly context save; keep
   the pad list and marks. Needs the EH differential tests (gate F, VC7 EH dispatch) before any launch.
3. **Code density for small caches** (benefit: largest on mainstream/mobile CPUs; risk: medium; translator). The
   hot-code order already shows the instruction side is worth 10-17% on a 32 MB L3. Next: profile-driven order from
   several scenes (TutA, TutB, M08A1, menus) as the default link input; then shrink small functions (GLM `RObject::Cast`
   is 64 B of x86 and 655 B translated): slimmer entry/exit for leaf functions, translator-level inlining of small
   direct callees (round 2's recommendation), and cold-path outlining (fault/trap/icall-miss paths) so hot functions
   pack tighter.
4. **Animation hot spots** (benefit: up to ~10% of cutscene frames; risk: low-medium). Golem animation
   (`RefreshScriptProcesses`, bone evaluation, `RObject::Cast`/`IsDerivedFrom`) is 19-24% of the cutscene frames. The
   native-replacement mechanism (`dev.py build --native`) could take the few hottest pure functions, verified by
   `--native-verify`.
5. **Measure on a real mainstream machine** before any claim about weaker hardware (a 16-32 MB L3 desktop and an ARM64
   board), using the same benchmark and the order file.

**Is the architecture appropriate?** Yes. Nothing measured points at the static-recompilation model itself: translated
code is half of the frame, within 1.3-1.5x of native on owned kernels (rounds 1-2), and its main cost on smaller CPUs is
code density, which the translator can address. The largest avoidable cost is the D3D8 HLE's validation and staging
design — a runtime policy, fixable without touching the translation model. A larger redesign (JIT, native rewrite, new
graphics backend) is not justified by these measurements.

## H. Game behaviour: C3c baseline and the final candidate

| check | C3c (exact exe `57dde851…`), run `20261102-123745` | R3 (`812c13ba…`), runs `-142701`, `-142829`, `-143132`, benchmarks |
|---|---|---|
| initialization, CS_Intro, menu path | pass (every benchmark run of C3c) | pass (benchmarks `-141557`, `-142130`) |
| save loading (F8, seeded checkpoint) | pass: TutB lift corridor loaded (camera jumps to (-634,2085,z3250)) | pass: same views at the same steps; M08A1 checkpoint loaded |
| movement and collision | pass: walk 553 uu in free space, 153 uu against a wall (blocked) | pass: identical views |
| quicksave / quickload | pass: F5 -> Save0.usa (Save1 rotation), F8 restores the saved position (-80,2176) after walking away | pass: same |
| window resize | pass: 2560x1440 capture after `size`, back to 3840x2160 | pass: same |
| UI scale | pass: live `PORTSET UIScale 150` through the console -> "UI drawn from a 2560x1440 frame on the 3840x2160 viewport (x1.5)"; in-game menu rendered | in-game menu rendered (scale 100) |
| walking-speed setting | pass: 150% read from the profile; live `PORTSET WalkingSpeed 75` accepted (its distance effect was not isolated: the walk after it hit the menu) | 150% read from the profile |
| sound effects / DirectMusic | pass: OpenAL 207 plays, 0 glitches; DirectMusic containers and segments | pass: TutB 209 plays, M08A1 77,090 plays, 0 glitches; `Intro.con`, `M08.con` |
| combat | not re-run on the exact C3c exe | pass: player hits an Izarian (blue blood on its torso), the pack's energy shots hit the player (purple flash), player dies; the Puppeteer kill of round 1 was not reproduced (timing after the load differs) |
| normal shutdown | not exercised (the console was toggled closed before `exit`) | **pass, twice**: console `exit` -> "the game exited normally (its own shutdown, ExitProcess(0))", outcome `exited`, exit code 0 |
| stability | 20 launches this round: no fatal, no watchdog kill, no bad return | — |

The generated code of R3 is byte-identical to C3c's (hash-verified), so the C3c behaviour checks carry to R3 except where
the runtime changed (staging, hints, checkpoints, order), which the R3 runs cover. Lessons for scripted input: VK 192
opens the console and Enter runs the command (and appears to close the console), so `exit` must be the first console
use or the console state must be known; the first Escape after a load is sometimes swallowed.

## Launch ledger, commits, save points, evidence

Budget: 24 launches, 600 s each, 12,000 s. **Used: 20 launches, 5,394 s of execution** (runtime-report mtime minus
command mtime, as in rounds 1-2), longest 317 s, all through `dev.py run` in background mode with fresh sandboxes; no
fatal, no watchdog, no emergency stop. 18 ended at their scripted scene stop (exit 11), 2 with the game's own shutdown
(exit 0).

| # | run | build | purpose | exec s |
|---|---|---|---|---|
| 1 | 20261102-123745 | C3c | baseline verification (V1) | 112 |
| 2 | -124315 | C3c + profiling runtime | sampled TutA attribution (P1) | 315 |
| 3-6 | -125714, -130246, -130818, -131349 | C3c, S2, C3c, S2 | S2 A/B, CCD0 | 4 x 315 |
| 7-9 | -132204, -132736, -133310 | C3c, S2order, S2 | CCD1 | 316, 316, 317 |
| 10 | -133849 | S2order | order on CCD0 | 315 |
| 11 | -134421 | S2, `--staging reuse` | staging policy price | 315 |
| 12-13 | -135209, -135746 | S2, S2order | order repeat, CCD1 | 317, 316 |
| 14-15 | -140322, -140855 | C3c 4 cores | without / with L3 polluters | 315, 316 |
| 16-17 | -141557, -142130 | R3 strict, R3 guard | guard A/B | 315, 315 |
| 18 | -142701 | R3 | combat + audio + console exit | 73 |
| 19 | -142829 | R3 | final verification + console exit | 87 |
| 20 | -143132 | R3 | sampled combat attribution (P3) | 71 |

Save points (`out/dev-init-savepoints/`, each with exe, PDB, build state, runtime copy, `dev_support.c`, git head and
status, SHA256SUMS; generated sources = the C3c set in `C:\Users\lawma\Unreal2-dev-sandbox-overflow\
generated-perf-c3c-20261102`, verified file by file before the first build): `perf-c3c-prof-20261102` and
`perf-c3c-profws-20261102` (profiling builds), `perf-s2-20261102` (S2, exe `CDC63D40…`), `perf-s2order-20261102`
(`D2D78B16…`), **`perf-r3-20261102` (recommended: exe `812C13BA…`, S2 + guard mode + hot-code order; its `evidence/`
holds the analysis scripts, tables, sheets and per-run JSON)**. C3c and C1 save points are untouched.
Runtime patch: `tools/xrt/dev/patches/perf-batch3-runtime.patch` (R3 runtime against the C3c runtime). Order file:
`tools/xrt/dev/order-c3c-tuta.txt`. Owned tests: `experiments/xrt/tests/staging_bitmap`, `staging_guard`,
`cache_sweep`. Harness additions: `dev.py build --order`, `dev.py run --staging guard`, `bench_tuta.ps1 -ExtraSteps`,
`dev_support.c` (128-frame sampled stacks, `counters.csv`, `ws:0/ws:1` working-set probe).
