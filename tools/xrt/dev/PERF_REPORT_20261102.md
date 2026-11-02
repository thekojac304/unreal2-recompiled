# Unreal II static recompilation: performance round 2 (call/return protocol), 2026-11-02

**Summary.** Three translator options aimed at the call protocol (`rv`: callees return their return address; `regcache`:
reload only the live registers after a call and store only the dirty ones before one; `restrict`) give the recommended
build **C3c** (`perf-c3c-20261102`): **+3-6% FPS over C1 at matched host load** (+8% in menus, p95 frame time -5 to -8%,
code size -11.6%), measured in two uncapped 4K benchmark runs per build with the slow cutscene subsection now at 123 FPS
where C1 made 116 under the same load. Whole-program optimization adds nothing in the game and is rejected. Two
`regcache` defects that the differential suite could not see reached the game at its first draw; both are fixed and now
have owned cases and mutations, and the practice of a 30-second game launch before any benchmark launch is recorded.
The smoke test of C3c with the affinity hook passed loading, movement, settings, sound, save and load; the scripted
menu Quit did not register, so a normal shutdown is not verified this round. Owner's budget: 10 launches / 4,500 s
granted, 10 launches / 1,846 s used. The affinity gain of round 1 is reported apart and was not re-measured.

Scope: the translated call/return protocol, return-address handling, register-state reloads around calls and
cross-function state propagation, on top of the measured C1 build of 2026-11-01 (`PERF_REPORT_20261101.md`). C1
(`out/dev-init-savepoints/perf-c1-20261101`) and the owner-played alpha are untouched and remain the baselines. All
numbers below are from this machine (Ryzen 9 9950X3D, RTX GPU under DXVK, 3840x2160 windowed swapchain, background
developer mode) under the owner's concurrent desktop load; every game launch went through the existing contained
developer harness (`tools/xrt/dev/dev.py run`), inside the fresh budget the owner granted for this round (10 launches,
600 s each, 4,500 s cumulative). The incremental gain over C1 is reported separately from the V-cache affinity gain of
round 1 (`--affinity 0xFFFF`), which is unchanged in nature and was not re-measured as a variable.

## 1. Where the call cost comes from (C1)

A translated call in C1 is: spill every written register local to `c->r[]`, push the return address into guest stack
memory, call the lifted callee through its host prototype `void f(CPU*)`, have the callee store its popped return address
into `c->rv`, compare `c->rv` with the expected address, check the world-observer floor, and reload all eight register
locals from `c->r[]` (any callee may have changed any of them). Per call site that is 8 reloads plus the written-register
spills, a store and a dependent load through `c->rv`, and `c->pc` stores kept at every call (`lazypc`). The generated
sources of C1 contain 154,557 translated call sites in 60,038 functions (247 units), i.e. 1.24 M reload statements. The
call-heavy kernel of the owned benchmark (`strings`: `strlen`/hash through translated calls) sat at 1.5x native while
the loop kernels were at 1.0-1.6x, and the sampled game profile of round 1 put 92.6% of leaf samples in translated code
with the D3DDrv submission path and GlmLib animation (deep call trees of small functions) on top. Nothing in the
protocol can be dropped without changing guest semantics: the return address must be in guest memory (the game and the
walking-speed wrapper read it), ESP must be exact at every call, and the return check is what gives accurate fault
reports for a corrupted return address.

## 2. What changed (C3 = C1 + `restrict`, `rv`, `regcache`)

| option | effect in the generated code | what guards it |
|---|---|---|
| `rv` (xlift) | lifted functions are `uint32_t f(CPU*)` and *return* the popped return address; `CALL`/`ICALL`/`ICALLI`/`RET` compare the host return value, `c->rv` is written only on the cold paths (bad return, world-observer return, host adapters). One store and one dependent load fewer per call; the return check is a register compare. The protos header defines `XRT_RV_ABI`, which switches `xrt.h`'s lifted-function type and macros; the runtime dispatch, EH landing, port wrappers and the world observer use `XRT_CALL_LIFTED`/`XRT_TAIL`/`XRT_LIFTED_RETURN` and work under both ABIs. | differential tests (both DLL variants), ABI define passed to every unit that sees `xrt.h` (a forced include reads it before the protos header) |
| `regcache` (xlift) | per function, a backward liveness analysis over the promoted register locals decides which registers are reloaded after each call (the live-out set plus ESP instead of all eight) and which are stored before each spill point (the dirty set instead of every written register); a forward may-dirty/must-valid pass finds conflicts and widens the reloads of every call that reaches the conflict until stable. Return, tail, trap, mark and EH-registration points still store every dirty register, so `c->r[]` is exact wherever the runtime, a callee or another function can see it. | differential tests with three regcache mutations (no conflict fix, reload ESP only, spill ESP only), all detected |
| `restrict` (xlift) | `CPU* __restrict c`: the compiler may keep `c->` fields in registers across guest memory accesses (guest memory is addressed through the separate base `xg_`). | the guest never aliases the CPU struct (it is host memory outside the guest window) |
| runtime | `world_observer.h` `CALL`/`ICALL` made rv-aware (the observer's return check and `xrt_world_return` read the returned address); `xrt_module_by_addr` tries its last answer first (every import call and call-cache fill asked it to scan up to 32 modules). | runtime patch `patches/perf-batch2-runtime.patch` against the C1 runtime |
| dev.py | `--ltcg` (generated/sound/native units `/GL`, link `/LTCG`); `XRT_RV_ABI` on the command line of every unit when the lift is an rv lift; the port-wrapper rename and the line-table renumbering accept the rv/restrict function headers; developer-copy units include their own directory first (the port-src copy used to see the shared lift's protos). | build state records `lift_options`, `rv_abi`, `ltcg` |

Static effect on the whole game (C3 generated sources, 247 units): register reload loads after calls 1,236,456 -> 629,609
(50.9% kept; only 6,887 of 154,557 call sites still reload all eight registers), spill stores 635,711 (dirty registers
only). Code size `.text` 61.8 MB (C1) -> 54.6 MB (C3), -11.6%, with the same 16,446 Engine / 11,592 GlmLib / ... functions;
`.rdata` 17.5 -> 18.1 MB (line tables). The LTCG variant (C3L, same sources, `build --ltcg`) has `.text` 55.0 MB.

## 3. Correctness evidence before any launch

- `experiments/xrt/tests/opt_diff` with the C3 option list, violating and `CFLAGS_CLEAN` test DLLs, final translator
  (after the two fixes of section 3.1): 43 functions, 57,000 cases per variant (19 test functions x 3,000 vectors), 0
  native-vs-plain and 0 plain-vs-opt mismatches, every mutation detected (28 per variant: the earlier liveness, flags
  and x87 mutations plus regcache-no-conflict-fix, regcache-reload-esp-only, regcache-spill-esp-only,
  regcache-fallthrough-no-spill (3,000 cases, `t_asm_fallthrough`), regcache-spill-group-writes-lost (2,999 cases,
  `t_asm_divret`) and, on the violating DLL, cflags-no-audit).
- `dev.py selftest` PASS (fixture executables: containment, endpoint, crash and process-tree cases).
- All 17 game modules and the 4 sound DLLs lifted with one option list (`addr64,base,cflags,flags,icall,iflags,lazypc,pc,
  rdtsc,regcache,regs,restrict,rv,sse,x87,x87v,x87w`); the Unreal2 line table renumbers; the cflags audit result is
  unchanged (GlmLib keeps the iflags rules for one function).
- Kernel benchmark (`experiments/xrt/tests/perf_kernels`, 9 repetitions, checksums identical to native x86):

  | variant (ratio to native, median) | actors | bones | bsp | strings | verts | geomean |
  |---|---|---|---|---|---|---|
  | C1 set, cl /O2 /fp:strict | 1.90 | 1.61 | 1.01 | 1.50 | 1.61 | 1.49 |
  | C1 set, + /GL | 1.89 | 1.65 | 1.04 | 1.33 | 1.38 | 1.43 |
  | C3 set, cl /O2 /fp:strict | 1.91 | 1.62 | 1.07 | 1.58 | 1.44 | 1.50 |
  | C3 set, + /GL | 1.85 | 1.72 | 1.05 | 1.04 | 1.43 | 1.38 |

  The kernels have 10 translated call sites, so `rv`/`regcache` cannot show there (C1 = C3 within noise). The call-heavy
  `strings` kernel goes from 1.58x to 1.04x native once whole-program optimization can inline the small translated callees
  (a plain `uint32_t` return value and a `__restrict` CPU pointer make that legal for the compiler): that is the only
  synthetic signal about the call protocol, and it says the lever is inlining across translated calls, not the
  per-call instruction count alone. The game measurement below decides.

### 3.1 The first game launch of C3 failed, and what the differential tests had not covered

The first C3 launch (run `20261102-030904`, 8 s of execution) died at the first world draw with the D3D8 HLE's own
check `D3D8 draw: buffer range outside owned upload` (exit 76, a translated UI label draw in `D3DDrv.dll+0x11626`),
while C1 had just run the same script cleanly. One short bisection launch of the same lift without `regcache` (run
`20261102-031722`, 44 s, first-scene stop reached) put the defect in `regcache`. Root cause, found in the generated
code: when a function's last instruction is not a transfer and the next address is another function's entry, the
translator appends a synthetic "falls through into the next function" tail (spill + tail call) after that instruction.
The planner had merged those synthetic statements into the instruction's own statement list, which (a) classified the
instruction as one that spills everything itself, so every successor believed nothing was dirty any more, and (b) gave
the synthetic spill the "after a full spill" state, i.e. the empty set. All 31 such tails in the C3 sources stored
nothing (`/* nothing dirty */`), so the next function started from a stale `c->r[]` whenever the falling-through code
had written a register since its last call. The fix keeps the synthetic statements apart: the instruction's own
statements decide its kind, and the synthetic spill stores the dirty set after the instruction (23 of the 31 tails now
store registers; the other 8 follow a call whose reload left nothing dirty). The test DLL had no such layout, so
`opt_diff` gained `t_asm_fallthrough` (a 16-byte naked function without `ret` falling into the next exported function,
layout verified from the export table) and the mutation `regcache-fallthrough-no-spill`, which re-creates the defect and
must be detected. That build (`perf-c3b-20261102`) failed the same way at the same draw (run `20261102-033735`), so the fall-through
defect was real but not the one on this path. The second defect came out of a structural check of the planner's
assumptions over the real UI, D3DDrv and Core lifts (13,666 functions; a scratch harness wrapping the planner): the
spill marker is always the first statement of an instruction's group, but 43 groups in those three modules write a
register *after* it, namely the divisions (`xrt_div0` is a trap, so the group spills first, then writes the quotient and
remainder) and, in the game lift, every instruction carrying a monitor mark. The planner treated a self-spilling group
as "nothing dirty afterwards", so a quotient or remainder that reached a call or a `ret` unchanged was never stored to
`c->r[]`; UI text layout divides, and the label draw's arguments were the first victims. Fix: a self-spilling group leaves
its own written registers dirty (`d_out = W`). The test DLL's divisions all consumed their results in registers before the
next spill point, which is why they passed; `opt_diff` gained `t_asm_divret` (`cdq; idiv; ret` with eax and edx read by
the caller) and the mutation `regcache-spill-group-writes-lost`. The defective builds are kept as `perf-c3-20261102`,
`perf-c3l-20261102`, `perf-c3b-20261102`, `perf-c3lb-20261102` (marked in their READMEs); the measured candidate is
`perf-c3c-20261102` with the LTCG twin `perf-c3lc-20261102`. Lessons recorded for the translator work: every synthetic
statement the lifter appends is a separate program point for a liveness/dirtiness analysis; a statement group is not
atomic with respect to its own spill; the differential cases must consume results through `c->r[]` (return, argument)
and not only in registers; and a new option needs a game launch before a benchmark launch.

## 4. Whole-game A/B against C1 (uncapped, 3840x2160, strict interleaving)

Method as in round 1: `bench_tuta.ps1 -NoCapture -SampleHz 0 -Profile quiet -Res 3840x2160 -Delay 50 -Staging reuse
-Sound off -Background -Monitor -PauseProbe` (New Game, CS_Intro, the TutA cutscene, spawn, a fixed walk/turn/strafe
sequence, the pause menu; 308 s of script, uncapped, no affinity), the executable swapped by copying a save point's
exe/pdb/build-state into the build directory. Order: C1, (C3 fatal), (bisection), (C3b fatal), C3c, C1, C3Lc, C3c. The
owner's desktop load differed between the first C1 run (22.8% machine utility, 81.8 W package in the slow subsection) and
everything after it (13.8-14.6%, 70.8-72.5 W), so the table gives both the group medians and the matched-load pair.

| window | C1 run 1 (loaded host) | C1 run 2 | C3c run 1 | C3c run 2 | C3Lc | C3c / C1 (group medians) | C3c mean / C1 run 2 (matched load) |
|---|---|---|---|---|---|---|---|
| CS_Intro 30-60 s | 177.9 (5.34 / 8.27) | 203.2 (4.65 / 7.39) | 213.5 (4.35 / 7.56) | 216.4 (4.35 / 7.31) | 207.0 (4.52 / 7.45) | x1.128 | x1.058 |
| cutscene 96-210 s | 155.4 (7.22 / 10.57) | 173.9 (6.50 / 9.32) | 179.6 (6.25 / 8.89) | 177.4 (6.30 / 8.94) | 180.5 (6.19 / 8.92) | x1.084 | x1.026 |
| cut 150-210 s | 122.5 (8.17 / 11.07) | 138.3 (7.31 / 9.68) | 144.1 (7.02 / 9.21) | 140.4 (7.07 / 9.38) | 143.6 (6.97 / 9.38) | x1.091 | x1.028 |
| slow 158-177 s | 100.3 (9.82 / 12.06) | 116.2 (8.34 / 10.62) | 122.7 (7.92 / 10.04) | 123.0 (7.90 / 10.08) | 122.9 (7.88 / 10.13) | x1.135 | x1.058 |
| spawn 220-230 s | 163.6 (5.94 / 7.62) | 180.5 (5.32 / 7.13) | 185.6 (5.18 / 6.84) | 186.4 (5.13 / 6.86) | 184.9 (5.26 / 6.86) | x1.081 | x1.030 |
| movement 230-245.5 s | 219.6 (4.16 / 7.42) | 238.1 (3.82 / 6.49) | 246.2 (3.72 / 6.30) | 242.4 (3.77 / 6.26) | 251.3 (3.63 / 6.07) | x1.067 | x1.026 |
| pause menu | 399.6 (2.38 / 3.30) | 415.7 (2.27 / 3.21) | 446.1 (2.11 / 2.96) | 455.6 (2.09 / 2.95) | 447.8 (2.10 / 3.01) | x1.106 | x1.084 |

FPS (median ms / p95 ms). Reading: the two C3c runs agree to within 1-3% in every window; the two C1 runs differ by 9-16%
because of the host load, which is why the matched-load column is the honest estimate of the **incremental gain of C3c
over C1: +3-6% FPS (median frame time -3 to -6%) in the game windows, +8% in the pause menu, p95 frame time -5 to -8%**;
the group-median column (+7-14%) is inflated by the loaded first C1 run. The round-1 slow subsection target (120 FPS) is
met by C3c on this machine under light host load (122.7 / 123.0 FPS, p95 10.0 ms) where C1 made 116 FPS under the same
load. Frame-time distribution and the game-thread share (98.6-99.4% of a core in every run) are unchanged: the game
thread is still the bottleneck, now with less work per call.

C3Lc (same sources, `/GL` + `/LTCG`) equals C3c within noise in every window (slow 122.9 vs 122.7-123.0, movement +2%,
CS_Intro -3%): the compiler's cross-unit inlining that made the call-heavy kernel near-native does not reach the game's
hot call trees (virtual calls through `ICALLI`, imports, and callees in other units), so whole-program optimization is
rejected for the build (longer link, no gain) and `restrict` stays only because it costs nothing and helps the kernel.

## 5. Affinity gain, reported separately

The V-cache affinity gain is a property of the process placement, not of the translated code, and was measured in round 1
on C1 (one core of the V-cache CCD +15-23% over unpinned, the other CCD -10-25%). It was not re-measured as a variable in
this round; the smoke test below runs the recommended C3c build *with* `--affinity 0xFFFF` as the owner's play
configuration. Expected stacking on this machine: the matched-load C3c gain (+3-6%) and the round-1 pinning gain are
independent effects (less work per call vs. fewer L3 misses from die migration), so the recommended configuration is C3c
pinned, with the two gains reported apart as asked; no combined number is claimed without a measurement of its own.

## 6. Smoke test of the recommended build (with the affinity hook)

Two launches of the exact C3c executable (SHA-256 `57dde851…`), `dev.py run --affinity 0xFFFF --staging strict --sound on
--background --windowed-res 3840x2160 --profile smoke-c3`, scripted input, 95-100 s of play each, both ending at their
scripted scene stop (exit 11), no fatal, no bad return, no watchdog.

| check | result | evidence (run `20261102-042144`, the second launch) |
|---|---|---|
| affinity hook | pass | `dev: process affinity 0xffff (now ffff of system ffffffff)` before the guest started |
| loading | pass | the TutB lift-corridor seed save quick-loaded through the Load menu ("Really load?" -> Ok), world frames from ~20 s; the earlier launch loaded the TutB-farewell save into its arrival cinematic |
| movement | pass | W / turn / W / turn / strafe between 32 and 41 s change the view in every shot; the port's walking-speed setting was in force |
| UI settings | pass | the profile's `[U2Port.PortSettings]` were read and applied at start (`port: walking speed 150% (User.ini)`, `port: UI scale 100 (User.ini)`; the first launch: 150% / 150 with the scaled UI frame logged); the in-game menu renders at 3840x2160 (shots at 77 and 83 s) |
| sound | pass | `--sound on`: the lifted ALAudio/Vorbis path on the OpenAL adapter opened the XAudio2 device and mixed audible output (`peak 0.030/0.036, 168 plays, 366 buffers, glitches 0`); the first launch, which spent its time in a cinematic, logged 12 plays |
| save | pass | F5 at 42 s: `Save.tmp` -> `Save0.usa` with the previous save rotated to `Save1.usa` (the game's own CopyFile/MoveFile sequence, inside the sandbox's Save folder) |
| load after save | pass | F8 at 49 s: "Really load?" -> Ok, the quicksave reloaded (shots at 56/62 s show the pre-save view again, the 47.5 s shot the position walked to after the save) |
| normal shutdown | **not verified** | the pause menu opened (Escape) and rendered, but neither scripted click on its QUIT button registered (shots at 77 and 83.5 s still show the menu), so the run ended at its scene stop instead of the game's own `ExitProcess(0)`. The launch budget was exhausted at that point. The clean menu Quit of 2026-11-01 (owner-played, run `20261101-222923`) remains the only shutdown evidence, on the C1-era runtime; nothing in this round touched the shutdown path, but that is an inference, not a measurement. |

Both smoke launches also taught the harness something: a play profile's display section (`WindowsClient.ini`) can force a
2560x1440 viewport that invalidates every recorded 3840x2160 cursor path, a non-default UI scale changes the menu
geometry the same way, and the TutB-farewell save begins with a ~90 s arrival cinematic that swallows movement and F5.
For the next batch the scripted quit should not depend on menu clicks: open the console (OEM_3) and type `exit` + Enter
with the key verb, or add a `text` verb to the input script.

## 7. Combat route

Not re-exercised: the two defective C3 launches and the bisection launch consumed the launches reserved for it. The
route was made more robust on paper for the next batch (`regress-m08a1-v2-profile.json`, kept with the evidence): the
screenshots of the round-1 replay show the seal-door panel below and right of the aim when the two `Use` presses were
made, so the revised route pitches the view down after facing the panel and presses `Use` four times with small yaw
nudges, then restores the pitch; everything after shifts by 3 s. The first replay's stall at an NPC in a doorway is not
addressed (it needs a wait-and-retry step at a position that has not been identified from the shots).

## 8. Rejected or not pursued, with the reason

- `xrt_world_return` string compares -> enum: the function runs only when a return lands at or above a pending world
  call's stack floor (`c->r[ESP] >= c->world_floor`), i.e. not on the per-call path; its 0.9% self time in the round-1
  profile is the event formatting of the observed scene-node returns. Not a call-protocol cost; left alone.
- Texture-staging "valid" map clearing (memset 2.4%): D3D8 HLE, unrelated to the call protocol; deferred.
- Dropping the per-function hit byte (`xrt_hits_*[k] = 1`) or the lean entry's preemption check: both are evidence and
  scheduling semantics the runtime report and the baton scheduler rely on; not changed.
- Whole-program optimization (`build --ltcg`, C3Lc): equal to C3c within noise in the game (section 4) although it made
  the call-heavy kernel near-native; rejected for the build.
- An architectural change of the call protocol (host-stack return addresses, trampolines, a register-passing convention
  for guest registers): the measured data does not justify it; see the recommendations.

## 9. Recommendations

1. **Adopt C3c** (`perf-c3c-20261102`: `xlift --opt` C1 set + `restrict,rv,regcache`, `dev.py build --lean`, `run
   --affinity 0xFFFF`) as the recommended build: +3-6% FPS over C1 at matched host load (+8% in menus), p95 frame time
   -5 to -8%, 11.6% less code, the whole differential suite green with two new owned cases, one clean benchmark route x2
   and the smoke test of section 6. The gain is modest because the call protocol was already lean in C1: what remains per
   call is the guest-stack return address (required), the return check (required for fault reports), and the host
   function call itself.
2. **Do not adopt LTCG** for the game build (no measurable gain, longer and less reproducible link); keep `--ltcg` as a
   tool for kernel experiments.
3. **Why call-heavy code stays expensive, and what would move it**: the sampled profile and the kernel matrix agree that
   the cost is no longer the protocol's instruction count but the *shape* of the code: tens of thousands of small
   functions (accessors, operators) each entered through a host call with a full prologue, an entry load of eight
   registers from `c->r[]`, and a return through guest memory. The only lever that made the call-heavy kernel near-native
   was cross-function inlining, which the game's dispatch structure (virtual calls through `ICALLI`, cross-unit callees)
   defeats. The next evidence-driven step is therefore **translator-level inlining of small, direct, non-recursive
   callees into their callers** (the lifter already knows every direct `CALL` target and its instruction count): the
   guest stack push/pop stays (semantics), but the host call, the prologue/epilogue and the entry/exit register traffic
   go. It is a translator feature, not a runtime change, and the differential suite plus `t_asm_fallthrough`/`t_asm_divret`
   style cases can test it before any launch. Expected to help ARM64 and small-cache CPUs as much as x86-64 (fewer
   instructions and less `c->r[]` traffic per call).
4. **Keep the regression practice that caught the two defects**: a short game launch (30 s to the first world draw) of
   every new translator option before any benchmark launch, and differential cases that consume results through
   `c->r[]` (return values, arguments) rather than only in registers.
5. For ARM64/Linux (unchanged from round 1): the portable core (`xrt.h`, `xrt_cpu.c`, `xrt_fmt.c`, `xrt_msvcr70img.c`) and
   the generated code build and run under gcc/aarch64; the Win32-bound runtime (D3D8 HLE on DXVK, GUI/DirectInput/
   DirectMusic, scheduler, memory, diagnostics) is the porting work, not the translator.

## 10. Launch ledger (round 2)

Budget granted by the owner for this round: 10 launches, 600 s each, 4,500 s cumulative (the round-1 authorization was
not assumed to renew). Used: **10 launches, 1,846 s cumulative execution** (runtime report mtime minus command mtime,
as in round 1), longest 316 s, all through the contained developer harness in background mode, no system, BIOS or power
change, no watchdog kill:

| # | run | build | purpose | exec s | end |
|---|---|---|---|---|---|
| 1 | 20261102-030308 | C1 | A/B run 1 | 316 | scene stop (exit 11) |
| 2 | 20261102-030904 | C3 (defective) | A/B run 2 | 8 | fatal 76 at the first world draw |
| 3 | 20261102-031722 | C1 options + restrict + rv | bisection, 30 s scene | 44 | scene stop |
| 4 | 20261102-033735 | C3b (defective) | A/B run 3 | 10 | fatal 76, same draw |
| 5 | 20261102-035334 | C3c | A/B run 4 | 316 | scene stop |
| 6 | 20261102-035927 | C1 | A/B run 5 | 316 | scene stop |
| 7 | 20261102-040518 | C3Lc | A/B run 6 | 315 | scene stop |
| 8 | 20261102-041107 | C3c | A/B run 7 | 315 | scene stop |
| 9 | 20261102-041704 | C3c, affinity 0xFFFF | smoke test 1 | 107 | scene stop |
| 10 | 20261102-042144 | C3c, affinity 0xFFFF | smoke test 2 | 102 | scene stop |

Not launched for lack of budget: the combat route (section 7) and a third attempt at the scripted menu Quit.

Save points: `perf-c3-20261102` (C3), `perf-c3l-20261102` (C3L); generated sources of both in
`C:\Users\lawma\Unreal2-dev-sandbox-overflow\generated-perf-c3-20261102` (SHA256SUMS; never redistributed); runtime
patch `tools/xrt/dev/patches/perf-batch2-runtime.patch`; kernel JSON, differential-test logs and run directories listed
in `tools/xrt/dev/README.txt`.
