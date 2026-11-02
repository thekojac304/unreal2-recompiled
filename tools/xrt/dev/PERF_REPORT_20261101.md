# Unreal II translated runtime: performance and portability batch (2026-11-01/02)

Owner brief: determine how efficient the static recompilation can realistically become, implement measured
optimizations, and establish a path to weaker Windows PCs, Linux and ARM64/Android. This report covers what was
measured, what was changed, what was rejected, and what remains unknown. All game figures were taken while the owner's
other tasks kept 12-27% of the 32 logical CPUs busy (package power 65-88 W against 62 W idle in the earlier batches), so
absolute numbers are 20-30% below the earlier batches and only interleaved, repeated A/B pairs are compared. The game
figures are from the existing developer harness in background mode (3840x2160 Vulkan swapchain in a window larger than
the display, not native 4K output; quiet trace profile; no sampler unless stated).

## 1. Preserved alpha and build identities

- Known-good alpha: `out/dev-init-savepoints/perf-baseline-20261101` (exe sha256 `1f25c656…`, byte-identical to
  `interactive-20261101/build`, the owner-played build after commits up to `4a6f170`): exe, PDB, helper, runtime, port
  package, hashes of all 247 generated units (copies in `C:\Users\lawma\Unreal2-dev-sandbox-overflow\perf-baseline-20261101-generated`)
  and of the 4 audio lifts, tool hashes, git HEAD and working-tree status. Codex's uncommitted `experiments/xrt/runtime`
  edits (Oct 25-30) were left untouched and are not part of any commit here.
- Reproducibility: every input of the build (sources, flags, lift options) is preserved and hashed; the link itself is
  not bit-reproducible (PDB GUID/timestamp), so identity is "same inputs", not "same bytes".
- Candidate C1: `perf-c1-20261101` (translator options cflags, rdtsc, lazypc, addr64 added; lean entry; inline
  world-floor check; MSVC), generated sources in `…overflow\perf-c1-20261101-generated`. **C1 is the recommended build.**
- Candidate C2: `perf-c2-20261101` (the C1 lift compiled by clang-cl 23): within noise of C1 in the game (section 5).
- Commits: `7143ee5` (translator, runtime patch, harness, tests, kernel benchmark), plus the final commit of this report,
  the journal and the affinity option.

## 2. Baselines (current alpha, TutA benchmark `bench_tuta.ps1 -Delay 50 -NoCapture`)

Windows are script seconds after Init: CS_Intro 30-60, TutA cutscene 96-210, its slow subsection 158-177, spawn 220-230,
movement 230-245.5, pause menu. FPS (p95 frame ms). Game thread 94-99% of one core in every window; GPU 10-16% busy.

| window | L1 reuse staging | L2 strict staging | L4 strict, sound path muted |
|---|---|---|---|
| CS_Intro 30-60 | 126.2 (11.6) | 138.9 (11.4) | 138.3 (11.3) |
| cutscene 96-210 | 108.6 (14.5) | 114.4 (14.7) | 106.9 (15.4) |
| slow 158-177 | 72.7 (15.7) | 69.6 (17.2) | 72.0 (17.0) |
| spawn | 103.0 (11.1) | 108.3 (11.5) | 116.1 (10.6) |
| movement | 146.2 (10.4) | 158.4 (9.7) | 157.1 (9.9) |
| pause menu | 249 (4.8) | 252 (5.2) | 255 (5.1) |

Strict staging (the owner's default) shows as 15-22% kernel time on the game thread (page commit/decommit per buffer
Lock/Unlock) against 5-9% with reuse; in this host state the FPS difference between the two modes is inside the noise.
The sound path (lifted ALAudio/Vorbis, OpenAL adapter on XAudio2) issued only 11 plays in the TutA windows (menus and the
opening cutscene use DirectMusic in the helper process), so its cost here is unmeasurably small; a voice-heavy level would
be the place to measure it.

## 3. Translation overhead in isolation: the kernel benchmark

`experiments/xrt/tests/perf_kernels` (new; owned code only): five kernels shaped like the engine's hot paths (bone chains
with per-kind dispatch, vertex transforms with compares, polymorphic actor ticks with a jump table, string hashing and
compares, BSP traversal), compiled by the x86 compiler with x87 code, run natively and as lifted C from the same bytes;
every translated checksum must equal the native one. Geomean of translated/native time (lower is better):

| lift / compiler | ratio |
|---|---|
| plain lift (no options), cl | 6.5x |
| 2026-10-31 game option set, cl | 1.8x |
| + cflags, rdtsc, lean entry | 1.6x |
| + lazypc | 1.5x |
| + addr64 (= the full set), cl | 1.3x |
| full set, clang-cl /O2 /fp:strict | 1.3x |
| full set, clang-cl /O2 /fp:precise | 1.2x |
| plain lift, clang-cl | 4.1x |

Call-heavy kernels stay at 1.7-1.9x, loop-heavy ones at 1.0-1.4x: the call protocol (8 register loads at entry, spills
before and reloads after every call, the return-address check, the call-target cache probe, the EH pad `setjmp`) is the
floor now, not per-instruction overhead. The per-kernel table, the cross-build procedure and the AArch64 results are in
the benchmark's README.

## 4. Optimizations implemented (translator `tools/xrt/xlift.py`; all opt-in, default lift unchanged)

| option / change | what it removes | soundness argument and test |
|---|---|---|
| `cflags` | full flag materialisation at indirect calls, imports and returns of address-taken functions (no x86 calling convention passes flags) | per-module static audit after the iflags fixed point: an address-taken function reading a flag at entry, or a call site reading a flag right after an indirect call, makes the module keep the iflags rules; marks/watches are not flag boundaries (they record no flags); fatal traps read nothing; `cflags_allow.json` lists data mis-lifted as code (GlmLib rva 0x1c9790: 0 executions in 197 runs), lifted as a fatal trap. opt_diff: both deliberate violations are reported, the audit-disabled mutation is detected |
| `rdtsc` | the runtime call plus a full register spill/reload at the 350 `rdtsc` sites (`appCycles`) | the intrinsic yields the same EAX/EDX |
| `lazypc` | 1.97 M of 2.6 M remaining `c->pc` stores (kept only before calls, traps, marks and pc-reading helpers) | a guest memory fault's instruction is recovered from the host pc through per-chunk source-line tables (`XrtPcLine`, registered at start-up) and the PDB (`xrt_pc_from_host`, xrt_diag.c); all 1.97 M entries verified statically, and every sampled instruction of a 70 k-sample run mapped into its function; the fault report says when the recovery was used |
| `addr64` | one `lea` per `[reg + disp]` guest access (the displacement folds into the x64 addressing mode) | exact because the guest never maps below 0x10000 or at/above 0x80000000 (layout, now asserted by `xrt_commit`) and a 2 GB guard is reserved below the window: a wrapped address faults in both forms; indexed and far forms keep the 32-bit computation |
| inline world-floor check | one runtime call per cached indirect call | `world_floor` is a 32-bit `CPU` field in the padding hole (`sizeof(CPU)` stays 416 for the monitor records) |
| `build --lean` | the per-entry history ring (3 memory ops per call) | fatal dumps keep the guest-stack scan; the preemption check stays |
| `build --cc clang-cl` | compiler codegen (10% on the kernels, 20% less code) | same C, MSVC linker; bit-identical kernel checksums; within noise in the game |
| audio modules lifted with the full set | they were plain lifts (6.5x class) | same translator, same tests |

Validation: `experiments/xrt/tests/opt_diff` with the full option set, 48,000 cases per DLL variant (the standard DLL whose
hand-written cases violate the cflags assumptions on purpose, and a `CFLAGS_CLEAN` variant), 0 mismatches, 47/47
mutations detected; `forms_equiv.py` 6 M cases PASS; translator unit tests 21/21; owned runtime tests `staging_reuse`,
`quit_message`, `fps_cap` PASS against the modified runtime. Code size: `.text` 75.2 MB (baseline) → 61.8 MB (C1) → 49.6 MB
(C2); `.rdata` +15 MB (line tables).

## 5. Whole-game A/B (4K swapchain, reuse staging, uncapped, background mode, interleaved, same host state)

FPS (median / p95 frame ms), group medians; baseline 2 runs, C1 3 runs, C2 2 runs.

| window | baseline | C1 | C1 / baseline | C2 |
|---|---|---|---|---|
| CS_Intro 30-60 | 156.0 (6.07 / 9.50) | 181.0 (5.25 / 8.25) | x1.16 | 179.0 |
| cutscene 96-210 | 120.3 (9.43 / 13.37) | 148.4 (7.52 / 10.89) | x1.23 | 140.8 |
| slow 158-177 | 82.9 (11.80 / 14.88) | 99.3 (9.86 / 12.70) | x1.20 | 92.3 |
| spawn | 130.6 (7.48 / 9.63) | 147.7 (6.64 / 8.19) | x1.13 | 143.2 |
| movement | 180.9 (5.03 / 8.76) | 206.7 (4.42 / 7.67) | x1.14 | 199.5 |
| pause menu | 297.5 (3.23 / 4.36) | 366.4 (2.64 / 3.50) | x1.23 | 358.9 |

The first two C1 runs against the first two baseline runs (closest host state) read x1.16-x1.28; presents in the 308 s
script went from 58.4 k to 70.7 k / 76.9 k. C2's runs landed under heavier host load (25.7% and 17.9% machine utility
against 12-18%) and match C1's third run taken at similar load: no measurable game difference from clang-cl, so C1 (the
established MSVC toolchain) is the recommended build. A 1920x1080 swapchain run of C1 equals its 4K runs within noise in
every window (frame time is CPU-bound and resolution-independent). The 120 FPS target is still not met in the cutscene's
slow subsection (99 FPS median, p95 12.7 ms).

Where the time goes now (sampled C2 run, slow subsection, 4,231 samples): translated code 92.6% of leaf samples, led by
GlmLib animation (`f_2fb4cc0` 3.9%, `f_2fd7d20` 2.8%, `f_30995e0` 2.1%, `f_30b6e10` 2.0%) and the D3DDrv render-submission
path (`f_6978410` 11.4% innermost); runtime self time: `memset` 2.4% (texture staging zero-fill and the per-DISCARD-Lock
clearing of the byte-per-byte "valid" map), `dispatch` 2.1% (import calls), `memchr` 1.9% (undefined-byte evidence and
draw validation), `setjmp` 1.6% (EH pads), `d8_semantic_checkpoint` 1.5%, EH-pad monitor marks 1.5%, `xrt_world_return`
0.9%, `__security_check_cookie` 0.8%.

## 6. Experiments rejected or inconclusive

- cl `/arch:AVX2`, `/GS-`, `/GL` (LTCG), `/fp:precise`: a few percent on the kernels, not adopted.
- clang-cl `/fp:precise`: faster on the kernels but admits FMA contraction on FMA-capable targets (the default x86-64
  target has none, which is why the checksums matched): not for the game build.
- clang-cl for the game build: no measurable frame-time change; kept as an option (`build --cc clang-cl`) because the
  code is 20% smaller and compiles twice as fast, which should matter more on cache-limited CPUs (section 7).
- Audio cost in the TutA benchmark: within noise (11 plays).

## 7. Weaker hardware: CPU-sensitivity experiments

Pinning the whole process (game thread, DXVK workers, baton ticker, helper) from outside the harness; C1, 4K reuse
uncapped, FPS (median / p95 ms):

| window | unpinned (3 runs) | 2 logical CPUs, CCD0 (V-cache) | 4 logical CPUs, CCD0 | 2 logical CPUs, CCD1 |
|---|---|---|---|---|
| cutscene 96-210 | 148.4 (7.52 / 10.89) | 173.5 (6.46 / 8.56) | 170.5 (6.54 / 8.90) | 143.2 (7.80 / 11.53) |
| slow 158-177 | 99.3 (9.86 / 12.70) | 119.7 (8.26 / 9.52) | 117.5 (8.34 / 10.21) | 90.9 (10.60 / 13.99) |
| spawn | 147.7 (6.64 / 8.19) | 181.7 (5.40 / 6.24) | 181.1 (5.37 / 6.78) | 151.0 (6.39 / 8.26) |
| movement | 206.7 (4.42 / 7.67) | 238.4 (3.84 / 6.21) | 234.2 (3.85 / 6.44) | 202.0 (4.52 / 7.59) |

Three findings. (1) The port needs one core: confined to one core with its SMT sibling it is not slower but faster
(+15-23%). (2) The difference between the two dies (119.7 vs 90.9 FPS, p95 9.5 vs 14.0 ms) is the 96 MB versus 32 MB L3:
the translated game is cache-bound (62 MB of code plus the engine's data), and Windows' thread migration between the
dies costs the owner about 20% today; the new `dev.py run --affinity 0xFFFF` keeps the process on the V-cache die
(per-process, nothing system-wide). (3) For a weaker CPU this is the warning sign: a mobile or midrange core with a few
MB of L3 will pay for code size and cache misses on top of its lower single-thread speed, which these experiments cannot
quantify (no clock reduction is possible without system-wide settings). What can be said: the game thread needs 8-12 ms
of a 9950X3D core per frame in the worst cutscene subsection and 4-7 ms in gameplay, with the other threads needing a
fraction of a second core; a core with half the single-thread performance would put the worst subsection near 50-60 FPS
and gameplay above 100 FPS if its cache behaviour were similar, which it will not be. Reducing the instruction footprint
(section 9) is therefore the first lever for mainstream hardware.

## 8. Regression results on C1 (owner settings: strict staging, 90 FPS cap, sound path on and muted, background)

- TutB farewell checkpoint quick-load → Raff's farewell → PD_Avalon cinematic (+25.5 s) → Atlantis (+71.6 s) → in-map
  quicksave (Save0.usa, 11.5 MB): clean stop at the time limit, 90 FPS held (limiter wait 34-57%).
- M08A1 checkpoint quick-load → waypoint route → doors (Use) → Puppeteer fight: first replay reproduced the original run's
  first three waypoints to the millimetre (arrival times within 15 ms, positions within 2 units) and then walked into the
  marine NPC standing in the first doorway, a route-script brittleness also seen in the original batch (its launch 22); the
  scene, HUD and NPC animation were normal. The repeat reached 9 waypoints (through that door and the descent) and
  stalled at the seal-door panel: the closed-loop route ends 20-30 units from the original run's position, the computed
  facing put the crosshair on the wall edge beside the small Use panel, and the door stayed closed. The same script on
  the baseline executable (last launch) stalled at the first door exactly like the first replay (3 waypoints). So the
  stalls are the recorded route's run-to-run brittleness (NPC patrol timing, Use aim), not a build difference; combat
  itself was therefore not re-exercised on C1 in this batch (it is unchanged code paths, but that is an inference).
- TutA benchmark (every A/B run): menu path, New Game, opening cutscene with subtitles, player control, movement,
  pause menu; shots at the scripted times match the baseline's scene states.
- Game initialization, level loads (CS_Intro, CS_Titles, TutA, TutB, PD_Avalon, Atlantis, M08A1), DirectMusic helper,
  sound path, normal scene stop: no fatal in 19 launches. Not exercised here: the walking-speed and UI-scale settings in
  play, maximize/borderless, menu Quit (unchanged code, covered by the owner's earlier runs on the same runtime files),
  full campaign.

## 9. ARM64 / Linux

- The exported kernel lift (owned code) cross-compiled with the local AArch64 gcc 8.3 toolchain image and ran under QEMU
  (arm64 Alpine container) with all five checksums identical to native x86; the gcc 13 Linux x86-64 build ran natively
  with identical checksums. This validates the translated-code semantics (x87 double model, flags, the 64-bit addressing
  form, the call-target cache) on AArch64; it says nothing about AArch64 speed (emulation). No container image was pulled.
- clang 23 code generation for the same lifted C: AArch64 0.94x the x86-64 instruction count; the mix is dominated by
  CPU-struct loads/stores (register spills around calls) and float↔double conversions (the x87 model), the same costs as on x86.
- Runtime inventory (`out/dev-init/runtime` + dev support, 19,900 lines): 991 Win32/intrinsic references. Portable as is:
  `xrt.h` (guest memory, flags, x87 helpers, control transfer; intrinsics guarded with GCC/clang equivalents), `xrt_cpu.c`
  (5 guarded intrinsics), `xrt_fmt.c`, `xrt_msvcr70img.c`. Windows-bound: the D3D8 HLE layer (DXVK's D3D8 on Vulkan: on
  Linux/Android the same DXVK runs natively on Vulkan, so the layer ports as a client of DXVK, not a rewrite), GUI/input/
  DirectMusic adapters (DirectMusic has no non-Windows implementation: music needs a replacement player), kernel32/msvcr70
  adapters, the scheduler (SRW locks, condition variables, a 1 ms ticker thread), memory (`VirtualAlloc`/`VirtualQuery`;
  `mmap`/`mprotect` equivalents exist), diagnostics (VEH, dbghelp). No endianness assumptions; pointer widths already
  separated (32-bit guest addresses, host pointers). Android adds: a 4 GB + 2 GB virtual reservation (fine on 64-bit),
  JIT-free execution (this is AOT C, an advantage), and the page-protection cost of strict staging (worse on mobile kernels:
  use the reuse mode).

## 10. Recommendations, ranked by measured impact

1. Ship C1's option set and the lean entry as the default lift/build; play with `--affinity 0xFFFF` on this machine (+20%).
2. Attack the call protocol next (the kernel floor of 1.7-1.9x on call-heavy code, ~22% of game-thread time): return the
   popped return address in RAX instead of `c->rv` (one store and one load per call less, a register compare), reload only
   the registers a caller reads before redefining them (liveness over the promoted locals), and consider passing ESP/EAX/
   ECX/EDX in host registers for direct calls between translated functions (an ABI redesign of the generated code: large,
   but it is where the remaining 2x on call-heavy code lives).
3. Reduce instruction footprint for cache-limited CPUs: clang-cl (-20% code, neutral here, likely positive on small-L3
   parts), `/GS-` for generated units (0.8% cookie checks), and measuring on a real midrange machine before believing any
   extrapolation.
4. Runtime: bitmap instead of byte-per-byte "valid" map in buffer staging (memset/memchr 4-5% of game-thread time in
   gameplay, exact), write the Unlock snapshot into the host shadow instead of a fresh heap block (one copy and one
   allocation per Unlock less), an enum instead of `strcmp` in `xrt_world_return`, cheaper EH pad bookkeeping (the
   `setjmp` and monitor marks, 3%): together 5-8% of the game thread, no semantics change.
5. Strict versus reuse staging is a policy question for the owner: strict costs 15-22% of the game thread in kernel time
   for a diagnostic guarantee (stale pointers fault); reuse keeps every check and copy. A middle ground (decommit once per
   frame) would keep most of the diagnostic value at a fraction of the cost.
6. A major architectural change (a different translation model, a JIT, or a native rewrite of hot subsystems) is not
   justified by these measurements: the translated code is within 1.3x of native x86 on isolated kernels and the game is
   now CPU-bound mainly by call overhead and cache footprint, both addressable inside the current design. The owner's
   60 FPS at 1080p on a midrange PC is plausible for gameplay and uncertain for the cutscenes until measured on such a
   machine; Android 30 FPS depends first on code size and the DXVK/Vulkan path, which this batch did not test.

## 11. Launch ledger

19 genuine launches of the 20 authorized, 5,421 s cumulative execution of the 9,000 s authorized (execution = runtime
report mtime minus command mtime, which includes harness teardown), none longer than 391 s wall time, all through the
existing contained developer harness in background mode: 3 baselines (L1 reuse, L2 strict, L4 strict + sound), 7
interleaved A/B runs (2 baseline, 3 C1, 2 C2), 1 sampled profile (C2), 3 affinity runs (CCD0 x2, CCD1), 5 regressions
(TutB→PD_Avalon→Atlantis transition, 1080p benchmark, M08A1 x2 on C1, M08A1 on the baseline). Every run stopped cleanly
at its scripted time limit (exit 11); no fatal, no watchdog kill, no emergency cancellation.

Save points: `perf-baseline-20261101` (known-good alpha), `perf-c1-20261101` (the measured recommended build),
`perf-c2-20261101` (clang-cl variant), `perf-final-20261102` (C1 sources rebuilt with the `--affinity` hook in the
developer support file; the game code is identical to C1). Evidence: run directories `out/dev-init/runs/20261101-224852…`
through `…20261102-012447…` (frames.csv, threads.csv, power.csv, gpu.csv, xrt.log, shots), the kernel benchmark JSONs and
test logs in the session scratchpad are summarised in this report and in `tools/xrt/dev/README.txt`.
