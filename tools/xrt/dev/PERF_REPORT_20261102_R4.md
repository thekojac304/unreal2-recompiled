# Unreal II static recompilation: performance round 4 (runtime efficiency, exception handling, small caches), 2026-11-02

**Summary.** Four accepted changes cut the game thread's CPU time per frame by 10-26% on the V-Cache die (measured thread
CPU, strict staging) and its frame time by 13-31% on the 32 MB die, against the round-3 build R3, in the same TutA
benchmark: (1) **D3D8/monitor runtime** — range hints for
staging blocks in slots of their own (the 100-220 buffer Locks of a frame no longer evict the guest-stack hints, which
cost two `VirtualQuery` calls per D3D8 call afterwards) and quiet-profile fast paths that skip building monitor
records the quiet profile drops anyway; (2) **C++ EH landing pads without `setjmp`** (new `xlift --opt ehframe`: a
catch lands by `RtlUnwindEx` to the pad's host frame plus a small trampoline, the pad records the monitor depth instead
of a mark/forget pair) — CS_Intro +33%, pause menu +23%, gameplay +2-7% on top of (1); (3) a **clustered multi-scene
link order** (fewer code pages for every scene's hot set; FPS effect within noise on TutA on both dies); (4) **quiet fast
paths in the generated monitor wrappers** and one window check per device call (+5-13% on the 32 MB die, two runs each,
noisy). **Guard staging** passes a new strict-versus-guard differential test (identical guest-observable traces over
120,800 operations), a level-transition soak and the final verification run, and is worth another +1-5%: it is ready to
become the play-build default, which remains the owner's decision (strict stays the default and the reference). The
recommended build is save point **`perf-r4d-20261102`** (exe `618B07D1…`), strict by default, `--staging guard`
recommended for play. All 24 authorized launches were used (6,454 s of 12,000 s); no fatal, no watchdog kill.

Scope and rules: R3 (`out/dev-init-savepoints/perf-r3-20261102`, exe `812C13BA…`, commit `a3238a6`) is the baseline and
was preserved untouched; its runtime, generated sources (overflow `generated-perf-c3c-20261102`) and the current
`out/dev-init/build` were verified identical before work started. Every game launch went through `dev.py run`
(contained harness, watchdog, background mode, fresh sandbox per run) under the owner's round-4 budget (24 launches,
600 s each, 12,000 s). No supervisor, policy, ledger, original asset or personal save was touched; the uncommitted
`experiments/xrt` edits of another actor were left alone (commits are path-limited). Machine: Ryzen 9 9950X3D (CCD0 =
LPs 0-15 with 96 MB L3, CCD1 = LPs 16-31 with 32 MB), DXVK 3.1.1; the owner's other tasks kept ~19-21% of the machine
busy during every benchmark (recorded per run).

## A. Accepted changes and what each one measured

Benchmark (unchanged from rounds 1-3): `bench_tuta.ps1 -NoCapture -Delay 50 -Res 3840x2160`, uncapped, quiet trace,
background, sound off, strict staging unless noted, interleaved runs; group median of 2 runs per build unless noted.
Ratios below come from independent comparisons and are **not** additive.

| change | build | where measured | FPS effect (group medians) |
|---|---|---|---|
| D3D8/monitor runtime, part 1 (staging hint slots, quiet fast paths in `xm_scope`/`xm_native`/`xm_resource`/`xm_values`/`xm_d8_resource`, `xm_quiet_drop` without `strcmp`) | R4a vs R3 | CCD0, 2+2 | cutscene x1.054, slow subsection x1.106, spawn x1.059, movement x1.067, pause menu x1.068, CS_Intro x1.011 |
| EH pads without `setjmp` (`--opt ehframe`) | R4b vs R4a | CCD0, 1+2 (one R4b run excluded, see G) | CS_Intro x1.334, pause menu x1.233, spawn x1.066, movement x1.085, cutscene x1.046, slow x0.982 |
| EH, confirmed with the order change included (order neutral on CCD0, next row) | R4c vs R4a | CCD0, 2+2 | CS_Intro x1.325, pause x1.234, movement x1.072, spawn x1.069, cutscene x1.057, slow x1.019 |
| multi-scene link order | R4c vs R4b | CCD0, 2+1 | 0.99-1.04 (neutral) |
| multi-scene link order | R4c vs R4b | CCD1, 2+2 | 0.92-1.06 (within the ±7-13% run-to-run spread on CCD1; see B.3) |
| D3D8/monitor runtime, part 2 (generated monitor wrappers, one window check) | R4d vs R4c | CCD1, 2+2 | CS_Intro x1.086, cutscene x1.110, slow x1.129, spawn x1.127, movement x1.093, pause x1.051 |
| guard staging (same binary) | R4c guard vs strict | CCD0, 2+2 | x1.012-1.046 (slow x1.024, pause x1.046) |
| **all, strict** | **R4c vs R3** | **CCD0, 2+2** | CS_Intro **x1.339**, cutscene **x1.114**, slow **x1.127**, spawn **x1.132**, movement **x1.144**, pause **x1.318** |
| **all + guard** | **R4c guard vs R3 strict** | **CCD0, 2+2** | CS_Intro x1.371, cutscene x1.134, slow x1.154, spawn x1.145, movement x1.174, pause x1.379 |
| **all, strict** | **R4d vs R3** | **CCD1, 2+2** | CS_Intro **x1.443**, cutscene **x1.173**, slow **x1.148**, spawn **x1.218**, movement **x1.224**, pause **x1.364** |

Work per frame is the same in every build: slow subsection 3,870-3,948 D3D8 calls, 202-204 buffer Locks and 203-205
staging blocks per frame in all nine CCD0 runs (counters.csv); draws, primitives, C++ throws (11,100 per run, all caught)
and the scene captures are unchanged. Nothing was gained by omitting work.

### A.1 D3D8/monitor runtime (R4a, R4d)

Measured cost first (round-3 combat profile of R3, M08A1, 5,338 samples): buffer `Lock`/`Unlock` 13.3% of the game
thread, of which `NtQueryVirtualMemory` 1.9%; monitor request building on every import adapter, resource lookup and
monitored Win32/COM call (`memset` of a 264-byte request 1.8%, `strcmp` against `"UGameEngine.Init"` 0.6%, `xm_scope`
0.5%); window checks 0.8-1.2%.

- **Staging hint slots** (`xrt_mem.c` `xrt_is_committed`/`xrt_hint_committed`, `hle_d3d8_device.inc`
  `d8_staging_hint`/`d8_device_memory`): S2 (round 3) seeded every new staging block into the same 8-entry hint rings that
  hold the guest stack and the heap blocks that carry D3D8 arguments, so each Lock evicted one of them and the next
  argument check paid `VirtualQuery` twice. The blocks now go to two slots of their own. Same answers: every hint is
  validated against the decommit log as before.
- **Quiet-profile fast paths**: under `--trace-profile quiet` (every benchmark and the recommended play setting) the
  monitor drops BEGIN/END/DATA/RESOURCE/OMITTED records in `xm_probe_gated`. `xm_scope`, `xm_native`, `xm_resource`,
  `xm_values`, `xm_blob` and `xm_d8_resource` now return before building the request, `xm_quiet_drop` tests the first
  character before its `strcmp`, and (R4d) the 215 generated wrappers in `monitor_windows.inc`/`monitor_com.inc` start
  with `if(xm_quiet)return <native call>;` where the native call takes the wrapper's arguments unchanged (16 DirectInput
  COM wrappers that do not were left alone; `scripts/quiet_wrappers.py`). Exactly the records the quiet profile already
  dropped; development and forensic profiles are unchanged.
- **One window check per device call** (`d8_render_ready`): the focus window and the device window are usually the same
  token; the second identical check ran on the same thread with nothing in between (only the owner thread can destroy
  the window), so it could only repeat the answer. It is skipped when the tokens are equal. Window validity itself is
  still checked on every call (not cached).
- D3D8 HLE time per frame (rdtsc from API entry to guest return, sampled runs, strict): TutA, C3c (round-3 P1) → R4d:
  CS_Intro 1.03 → 0.67 ms, cutscene 1.89 → 1.16, slow subsection 3.12 → 1.94, spawn 1.84 → 0.99, movement 1.35 → 0.81,
  pause menu 1.01 → 0.52 ms (C3c lacks S2, which round 3 credited with 3-5% FPS; R3 itself was not sampled in TutA).
  M08A1 combat, R3 (P3) → R4d, same script: 1.41 → 1.09 ms/frame, 0.85 → 0.70 µs per D3D8 call; staging part
  (Lock+Unlock) 0.74 → 0.66 ms.

### A.2 Exception handling without `setjmp` (R4b)

Round 3 found the bookkeeping of Unreal's `guard`/`unguard` C++ try frames (7,908 translated functions register an EH
node) at 4-7% of gameplay and 18-24% of UI-heavy frames: per guarded call a `setjmp` (≈25 stores into a 256-byte
`jmp_buf`), `xrt_eh_register`/`xrt_eh_pop` and a monitor mark/forget pair. Design (`xlift --opt ehframe`, runtime
`xrt.h` `XRT_EH_FRAMES`, `xrt_eh.c`, `xrt_eh_land.asm`):

- Registration only links the pad (node, host-call depth, monitor depth); no `setjmp`, no landing branch in the
  function, no `jmp_buf` (pad 288 → 40 bytes per guarded frame). Pad functions are `XRT_EH_FN` (`__declspec(noinline)`)
  so the pad's frame is always the translated function's own (without `setjmp` MSVC could otherwise inline them).
- A completed catch of a function frame: `land_frame` walks the host stack (`RtlVirtualUnwind`) to the frame whose
  extent holds the pad, then `RtlUnwindEx` to that frame (as MSVC's `longjmp` does; termination handlers in between would
  run) with `xrt_eh_land_tramp` as target. The trampoline restores the return address of the call in progress in that
  frame and enters `xrt_eh_land_entry` as if the function had called it from there; it runs the continuation
  (`xrt_eh_landed`: the rest of the function, then the pad is popped) and returns from the function to its caller with
  the continuation's result by unwinding the function's frame (`RtlVirtualUnwind` + `RtlRestoreContext`). A further catch
  of the same frame lands on that frame again, so repeated catches use bounded host stack.
- Catch-block resume points (dispatcher-internal) keep `setjmp`; the monitor marks are replaced by the depth stored in
  the pad (`xm_unwind` to it at landing, which is what `xm_restore` did). Unchanged: the guest SEH chain, VC7 type
  matching, unwind funclets, CatchGuard handling, rethrow, object destruction, guest stack state, the "host adapter that
  called guest code" refusal and all fatal diagnostics.
- The setjmp form stays the default without the option (and the portable form); the protos header of an ehframe lift
  references `xrt_eh_abi_frames`, which only an `XRT_EH_FRAMES` runtime defines, and `dev.py build` refuses generated and
  sound lifts that disagree.

Verification before any launch: all 17 generated modules and the 4 sound modules were re-lifted with the C3c option set
plus `ehframe`; `scripts/lift_diff.py` shows the only differences from C3c are the option tag, 7,908 `XRT_EH_FN`
prefixes and the two protos lines. The C++ EH probe (`tools/xrt/tests/ehprobe`, now also built against the developer
runtime and option set by `build_and_run_dev.cmd frames|setjmp`) compares the translated runs with the game's own
`msvcr70.dll` handler: 9 positive probes identical in both forms, including three new ones (a catch six guarded frames
above the throw with destructors in every abandoned frame; 200 catches inside a callee while the caller keeps its state
in callee-saved registers; the normal path only), 211 resumptions in the owning function, rethrows, a resumption inside an
active catch block, abandoned catch blocks; both negative probes stop with explicit diagnostics. Game: the smoke launch
and every later run (11,034-11,129 throws and catches each, all landing through the new path) behave as before.

Normal-path cost (owned microbenchmark, 50 M calls of a small guarded function, one CCD1 core): `setjmp` pads 17.2 ns,
ehframe pads 13.5 ns per call (native x86: 3.0 ns); removing registration entirely would give 11.8 ns, so ~1.7 ns
remain in `xrt_eh_register`/`xrt_eh_pop`. `.text` shrank 57.31 → 55.18 MB (−3.7%), and the full generated rebuild fell
from ~7.5-11 min to ~1 min 40 s (MSVC spent that time on the `setjmp` functions). EH bookkeeping in the frame (sampled):

| window | C3c (round-3 P1) | R4d |
|---|---|---|
| CS_Intro | 1.24 ms (24%) | 0.33 ms (9%) |
| cutscene / slow / spawn / movement | 0.26 / 0.36 / 0.28 / 0.29 ms | 0.07 / 0.09 / 0.09 / 0.07 ms |
| pause menu | 0.54 ms (18%) | 0.10 ms (5%) |
| M08A1 combat (R3 P3 → R4d) | 0.30 ms (5%) | 0.07 ms (1%) |

### A.3 Code layout: clustered multi-scene order (R4c)

`scripts/order_multi.py` reads existing evidence only: the sampled windows of round 3 (CS_Intro, main menu, TutA
cinematic and gameplay, pause menu from P1; M08A1 combat and after the fight from P3) and the executed-function sets of
128 runs since 2026-11-01 (TutA, TutB, Atlantis, M08A1, menus). `scripts/order_eval.py` lays candidate orders out with
the PDB's function sizes and counts the 4 KB pages that hold each scene's 95% sample set; the clustered order (functions
hot in two or more scene groups first, then each group's own set, then other executed functions by coverage) beat the
max-share and summed-share orders and R3's TutA-only order for every scene. Pages in the linked executables:

| scene | R3 (TutA order) | R4b (TutA order) | R4c/R4d (clustered) |
|---|---|---|---|
| CS_Intro / main menu / pause menu | 357 / 220 / 194 | 353 / 214 / 184 | 328 / 169 / 160 |
| TutA cinematic / gameplay | 672 / 656 | 671 / 647 | 654 / 607 |
| M08A1 combat / after the fight | 1,560 / 1,704 | 1,528 / 1,684 | 1,222 / 1,388 |

In FPS the order is neutral on the V-Cache die (R4c vs R4b 0.99-1.04) and not resolved on the 32 MB die: R4c vs R4b
0.92-1.06 with runs of the same build differing by up to 12% there (R4b movement 247/218, pause 465/404; R4c CS_Intro
260/228). The combat working-set probe (`ws:0/ws:1`, ~11 frames) shows 1,623 → 1,629 `.text` pages: no measurable change.
Kept because it is no measurable loss on the benchmark and reduces the code-page footprint of the menus by 13-23% and of
combat by 18-20%; it is the only layout input built from more than one scene. It is not claimed as an FPS gain.

## B. Guard staging: compatibility, safety and readiness

Strict staging gives each buffer Lock a fresh guest block and decommits it at Unlock, so a guest pointer kept past
Unlock faults. Guard keeps the block committed but `PAGE_NOACCESS` between uses and re-opens it for the next Lock of its
64 KiB size class (zero past the locked bytes); textures stay strict in both.

**Defect found and fixed this round:** `xrt_is_committed`, which 27 runtime adapters use to admit guest pointers,
answered "committed" for a guarded block (`VirtualQuery` reports `MEM_COMMIT` for `PAGE_NOACCESS` pages), whereas strict's
decommitted block answers "not committed". A stale staging pointer passed to e.g. a CRT adapter would have produced a
host fault in the adapter instead of strict's refusal. It now treats `PAGE_NOACCESS`/`PAGE_GUARD` as not committed —
only guard blocks are ever reprotected, so strict mode is unaffected (`d8_device_memory` and `IsBadReadPtr` already
checked protection).

**Differential test** (`experiments/xrt/tests/staging_guard/diff.c`, run by `run.cmd`; the real `xrt_mem.c` and
`d8_valid_bits.h`, the buffer path of `d8_resource_Lock`/`d8_unlock` mirrored step by step): the same pseudo-random
sequence runs once per mode in separate processes and every guest-observable outcome is printed without addresses. Two
seeds × 60,400 operations: **traces identical** (54,195 and 54,322 lines). Covered, per required case:

| case | evidence |
|---|---|
| stale guest pointers | after each of ~9,300 Unlocks a read and a write through a stale pointer fault in both modes; adapters see it uncommitted; `d8_device_memory` refuses it |
| staging-buffer lifetime, reclamation | a guarded block is never handed to ordinary `VirtualAlloc`; pool pressure (reclaim) decommits guarded blocks like strict's free blocks; 400 Lock/Unlock operations after the reclaim (test.c: 21 checks) |
| Lock/Unlock, DISCARD, NOOVERWRITE | DISCARD clears the validity bitmap, NOOVERWRITE passes; staging bytes = shadow bytes at Lock (hash), bytes past the request up to the page end zero, the page after the committed range faults |
| partial writes, unwritten bytes | random partial guest writes; shadow and validity map hashes after every Unlock identical; 4,221 Locks with D3D-undefined bytes counted alike |
| invalid ranges, double unlock | out-of-range Locks, Lock of a mapped buffer, Unlock without Lock: same refusals (the HLE stops with the same fatal) |
| destruction and re-creation | buffers released while mapped and re-created with another length |
| host-shadow synchronization | final shadow and validity hashes of every buffer identical |
| memory pressure | outcomes identical; the pool layout differs (strict 3 reclaims, guard 1-7) — addresses, not behaviour |
| save/load, level transitions | game: launch 22 (TutB → PD_Avalon → Atlantis, guard), launch 23 (F5/F8, resize, UI scale, guard), benchmarks 6 and 11 |

What differs, and why it is not a weaker guarantee: guest-visible **addresses** of staging and ordinary blocks may differ
(not semantics; a guest that compared addresses across runs would already see ASLR-like variation in strict mode's pool),
guard holds committed memory for one block per concurrently locked size class, and a stale pointer is trapped **at
least** as long as in strict (strict's freed block can be handed to an ordinary `VirtualAlloc` of the same size, after
which a stale pointer silently aliases live memory; a guarded block cannot). Faults raise the same access violation with
the same diagnostic (the VEH reports by address, not by page state).

**Game evidence under guard:** 2 TutA benchmarks (+1-5% over strict on the same binary), the level-transition run
(TutB farewell dialogue → PD_Avalon cinematic → Atlantis, F5, menu, clean exit; two full resource tear-downs and
re-creations, music and 18,699 OpenAL plays with 0 glitches) and the final verification run (load, walk, F5/F8,
resize to 2560x1440 and back, UI scale 150 via the menu, in-game menu): no fatal, no refusal, no difference in behaviour.

**Assessment: guard is ready to become the play-build default.** Externally observable behaviour and the protection
guarantee are equivalent across every required case, with the one gap found (adapter commit checks) closed. Not
changed automatically: `dev.py run` still defaults to strict, as decided after round 3; switching is one argument
(`--staging guard`). Strict remains the diagnostic/reference mode. Missing evidence, stated plainly: no hours-long play
session in guard mode; one pool weakness affects both modes equally (G).

## C. Whole-game results

CCD0 (V-Cache die, `--affinity 0xFFFF`), group medians: FPS | median / p95 / p99 frame time (ms).

| window | R3 | R4a | R4b (1 run) | R4c | R4c guard |
|---|---|---|---|---|---|
| CS_Intro | 204.4 \| 4.53 / 7.36 / 10.64 | 206.6 \| 4.47 / 7.34 / 10.39 | 275.5 \| 3.34 / 5.61 / 8.48 | 273.7 \| 3.38 / 5.56 / 8.39 | 280.3 \| 3.31 / 5.45 / 8.34 |
| cutscene | 178.7 \| 6.20 / 8.81 / 9.80 | 188.3 \| 5.90 / 8.06 / 8.97 | 197.0 \| 5.56 / 8.08 / 9.09 | 199.0 \| 5.53 / 7.86 / 8.85 | 202.6 \| 5.44 / 7.68 / 8.53 |
| slow subsection | 115.6 \| 8.58 / 9.98 / 11.04 | 127.9 \| 7.72 / 9.03 / 10.11 | 125.7 \| 7.89 / 9.29 / 10.51 | 130.3 \| 7.58 / 8.99 / 10.01 | 133.4 \| 7.43 / 8.63 / 9.63 |
| spawn | 188.2 \| 5.22 / 6.18 / 7.20 | 199.4 \| 4.93 / 5.81 / 6.47 | 212.6 \| 4.62 / 5.47 / 6.04 | 213.1 \| 4.60 / 5.49 / 6.30 | 215.6 \| 4.55 / 5.39 / 6.12 |
| movement | 243.9 \| 3.79 / 6.09 / 6.83 | 260.3 \| 3.52 / 5.74 / 6.46 | 282.5 \| 3.25 / 5.33 / 6.06 | 279.1 \| 3.29 / 5.34 / 5.98 | 286.4 \| 3.20 / 5.29 / 5.86 |
| pause menu | 374.1 \| 2.60 / 3.23 / 3.76 | 399.6 \| 2.42 / 3.09 / 3.66 | 492.7 \| 1.99 / 2.50 / 2.83 | 493.0 \| 1.99 / 2.51 / 2.83 | 515.7 \| 1.90 / 2.39 / 2.72 |

Game-thread CPU per frame on CCD0 (thread CPU time / frames; the thread is 95-99% busy in every window): R3 → R4c strict
→ R4c guard: CS_Intro 4.51 → 3.33 → 3.25 ms, cutscene 5.38 → 4.84 → 4.75, slow 8.39 → 7.43 → 7.27, spawn 5.10 → 4.53 →
4.49, movement 3.93 → 3.43 → 3.35, pause menu 2.54 → 1.92 → 1.83 ms (−10% to −26% strict, −12% to −28% guard).

CCD1 (32 MB L3 die, `--affinity 0xFFFF0000`), group medians, DCBAABCD order:

| window | R3 | R4b | R4c | R4d |
|---|---|---|---|---|
| CS_Intro | 183.5 \| 5.14 / 8.15 / 10.48 | 259.7 \| 3.54 / 6.03 / 7.99 | 243.9 \| 3.78 / 6.56 / 8.63 | 264.8 \| 3.51 / 5.83 / 7.97 |
| cutscene | 154.7 \| 7.21 / 10.60 / 11.90 | 172.5 \| 6.46 / 9.54 / 10.76 | 163.5 \| 6.78 / 10.21 / 11.44 | 181.5 \| 6.09 / 9.13 / 10.39 |
| slow subsection | 99.6 \| 9.88 / 12.12 / 13.39 | 110.3 \| 8.94 / 10.96 / 12.27 | 101.3 \| 9.82 / 11.69 / 12.78 | 114.4 \| 8.59 / 10.62 / 11.71 |
| spawn | 159.6 \| 6.10 / 7.81 / 8.59 | 171.5 \| 5.74 / 7.26 / 8.31 | 172.6 \| 5.79 / 7.05 / 7.81 | 194.5 \| 5.03 / 6.37 / 7.10 |
| movement | 213.3 \| 4.34 / 7.09 / 8.13 | 232.6 \| 3.98 / 6.82 / 7.67 | 238.8 \| 3.89 / 6.58 / 7.65 | 261.0 \| 3.54 / 5.93 / 6.88 |
| pause menu | 353.2 \| 2.70 / 3.62 / 3.98 | 434.6 \| 2.27 / 2.81 / 3.18 | 458.4 \| 2.18 / 2.68 / 2.92 | 481.7 \| 1.99 / 2.59 / 2.89 |

The standard die gains about as much as the V-Cache die from the same objects (R4b vs R3: CCD1 x1.08-1.42, CCD0 —
R4c, order-neutral there — x1.11-1.34; R4d adds part 2 on top: x1.15-1.44 on CCD1): the removed work (EH frames, monitor requests, hint re-queries) also removed code and stack footprint
(pads 288 → 40 bytes per guarded frame, `.text` −2.1 MB). The CCD1 deficit against CCD0 remains (R4d slow subsection
114 on CCD1 vs R4c 130 on CCD0, −12%).

M08A1 combat, sampled, sound on, same script as round-3 P3 (AI not deterministic): 154 → 181 FPS in the fight
(6.48 → 5.54 ms), 145 → 159 FPS after it. Per category (R3 → R4d): EH 0.30 → 0.07 ms, D3D8 per-call 0.44 → 0.29 ms,
staging 0.90 → 0.82 ms (strict), import dispatch 0.44 → 0.35 ms, translated code about unchanged (animation 1.06 → 0.86,
engine 1.05 → 1.07, script 0.78 → 0.82 ms). TutA after (R4d, sampled; `evidence/analysis/C01-table.md`): slow subsection
7.69 ms = translated 4.42 (animation 2.16) + D3D8 HLE 2.07 (staging 1.56, per-call 0.51) + dispatch 0.36 + EH 0.09 +
x87 0.20 + other 0.55.

## D. Gameplay regression of the final build (R4d)

| check | result (runs) |
|---|---|
| startup, CS_Intro, main menu, New Game path | pass: every benchmark run except A08, whose scripted menu clicks did not register (G) |
| save/load | pass: F8 load of seeded checkpoints (L01, L21-L24), F5 quicksave with Save0/Save1 rotation and F8 quickload (L01, L23), F5 in Atlantis (L22) |
| movement and collision | pass: walking into the lift-corridor wall stops at the same views as round 3 (L01 R4b, L23 R4d guard) |
| UI scaling | pass: UI scale 150 set through the menu → "UI drawn from a 2560x1440 frame on the 3840x2160 viewport (x1.5)" (L23) |
| walking-speed setting | partial: 150% from the profile applied (L01, L23); the live `PORTSET WalkingSpeed 75` was not reached (the scripted console was still open from the previous console use - the round-3 console-state issue) |
| windowed presentation, resize | pass: 3840x2160 windowed, resize to 2560x1440 and back (L01, L23); **fullscreen/borderless not exercised** this round (background mode; owner-verified earlier, presentation code unchanged) |
| audio and DirectMusic | pass: OpenAL mixing with peaks 0.17-0.19 and 0 glitches, 18,699 plays in the transition run, DirectMusic IPC and level music (L21, L22, L24) |
| weapons and combat | pass: in M08A1 the player fires, the Izarian pack attacks and hits the player (damage indicator), and an Izarian at the crosshair sprays blue blood at 33.0 s (L24 `scene-frame-9787`); the player dies later (L21, L24) |
| dialogue and scripting | pass: Raff's farewell dialogue → `dlgEndLevel` → PD_Avalon intro cinematic → Atlantis with Aida (L22) |
| level transition | pass: TutB → PD_Avalon (+24.7 s) → Atlantis (+70.7 s), under guard staging (L22) |
| clean shutdown | pass: console `exit` → the game's own shutdown, ExitProcess(0) (L01 R4b, L21, L22 R4d) |
| C++ exceptions | 11,034-11,129 throws per run, all caught through the new landing path, 0 unhandled |
| stability | 24 launches: no fatal, no watchdog, no runtime failure |

## E. Rejected, unsuccessful or not pursued

- **Inlining `xrt_eh_register`/`xrt_eh_pop` into generated code**: bounded at ~1.7 ns per guarded call by the
  microbenchmark and 0.33 ms (9%) of CS_Intro frames by the profile; it needs `XrtThread` layout exposure in `xrt.h` and
  a separate launch pair. Not done for lack of launch budget; first next step for UI-heavy scenes.
- **Multi-scene order as an FPS gain**: not demonstrated (A.3); kept for footprint, not claimed.
- **Caching window validity**: rejected again (mutable OS state); only the provably identical second check was removed.
- **Fewer protection changes in guard mode** (pre-opening or batching re-protection): rejected — it would shorten the
  window in which a stale pointer faults, so it would no longer match strict.
- **Pool block splitting**: found by the differential test (G), not changed: it alters guest-visible addresses after a
  reclaim in both modes and needs its own game evidence.
- **D3D8 per-call evidence restructuring beyond the quiet paths** (checkpoint calls, `InterlockedIncrement` of the
  evidence serial): left as is; checkpoints already early-return once the timeline is full.

## F. Remaining bottlenecks (R4d, TutA slow subsection, 7.69 ms sampled)

1. **Translated code, 57%** (4.4 ms): Golem animation and skinning 2.2 ms (`RefreshScriptProcesses`, bone evaluation,
   `RObject::Cast`), engine 0.9, renderer 0.65, script/core 0.5. Code density (≥6.6x the native bytes on the hot path)
   is the main lever left: translator-level inlining of small direct callees, slimmer leaf entry/exit, cold-path
   outlining; native replacements for the few hottest pure GLM functions (`dev.py build --native`).
2. **D3D8 buffer staging, 20%** (1.56 ms strict; guard −2-5% of the frame): the remaining cost is two protection
   changes per Lock/Unlock (guard) or commit + decommit (strict) plus the shadow ↔ staging copies that strict semantics
   require. Beyond guard, only the `reuse` policy (no stale-pointer trap) is cheaper.
3. **Import/indirect dispatch 5%, D3D8 per-call 7%**, EH registration 1-9% (UI scenes), x87 helpers 3%.
4. **Footprint on small caches**: CCD1 is still 12% slower than CCD0 in the slow subsection.

## G. Findings outside the accepted changes

- **Pool exhaustion after a reclaim (both staging modes):** once the 224 MB bump region is used up, the guest
  `VirtualAlloc` pool reuses free blocks whole (best fit, no splitting), so a tail of new allocation sizes can consume
  large merged blocks and end in "bounded client pool exhausted". The differential test hit it with synthetic sizes and
  keeps its post-reclaim tail short; the game has not hit it in any run, but a long session with many level loads could.
  Recommended follow-up: split the best-fit block, with an owned test and a level-transition soak.
- **One benchmark run invalid (A08, R4b, CCD0):** the scripted NEW GAME/NORMAL clicks did not register and the run
  measured the main menu; excluded (scripted navigation, not a runtime failure). R4b's EH effect is confirmed by R4c (same
  objects, order neutral on CCD0) and by both R4b runs on CCD1.
- **Launch 21's combat script ended with a console exit**, so no sample file was written (samples are written only at a
  scene stop); launch 24 repeated it without the exit (and with re-aiming) for the combat profile.

## H. Weaker PCs and ARM64/Android

Known: every accepted change removes work rather than moving it — fewer syscalls (`VirtualQuery` re-queries), fewer
stores per guarded call and 248 fewer stack bytes per guarded frame, no record building in the monitor, 2.1 MB less
code — so the benefit does not depend on the large L3; the 32 MB die gained at least as much as the V-Cache die. A
smaller-cache desktop or laptop CPU should see gains of the same order (no such machine was measured; not claimed).
For ARM64/Android: the staging hints, the quiet fast paths and guard staging are portable C (guard uses `mprotect`
semantics, cheaper than munmap/mmap per Lock on mobile kernels); the ehframe landing is Windows x64-specific
(`RtlUnwindEx`), while the `setjmp` form remains available and portable — a Linux/Android equivalent would land with
libunwind (`unw_init_local`/`unw_step`/`unw_resume`) or keep `setjmp` and inline the registration. The link order maps to
`-ffunction-sections` plus lld `--symbol-ordering-file`.

## I. Commits, save points, evidence, launches

Commits (branch `codex/level-initialization`, not pushed): `ba195ec` (xlift `--opt ehframe`, `dev.py` ehframe support and
regex fixes, runtime patch `tools/xrt/dev/patches/perf-batch4-runtime.patch` = R4d runtime against the R3 runtime,
`order-r4-multi.txt`, ehprobe developer variant and new probes, staging_guard differential test) and the report commit.

Save points (`out/dev-init-savepoints/`, each with exe, PDB, build state, runtime, `dev_support.c`, git head/status,
SHA256SUMS): `perf-r4a-20261102` (exe `CA033EBE…`), `perf-r4b-20261102` (`C5D515C2…`), `perf-r4c-20261102` (`DB222BC3…`),
**`perf-r4d-20261102` (recommended, `618B07D1…`; `evidence/` holds the scripts, analysis tables, contact sheets, per-run
logs and the ledger)**. Generated sources: R4a = the C3c set (`C:\Users\lawma\Unreal2-dev-sandbox-overflow\
generated-perf-c3c-20261102`); R4b-R4d = `generated-perf-r4b-20261102` (hash-verified against `out/dev-init/generated`
and `audio-lift`). `out/dev-init/build` holds R4d. R3 and earlier save points untouched. Recommended run: `dev.py run …
--trace-profile quiet --affinity 0xFFFF --staging guard` (strict remains the default).

Launch ledger (`evidence/analysis/ledger.txt`): **24 launches, 6,454 s of execution** (budget 24 / 12,000 s, ≤ 600 s
each; longest 316 s). 1 smoke (R4b, L01), 10 CCD0 benchmarks (L02-L11), 8 CCD1 benchmarks (L12-L19), 1 sampled TutA
profile (L20), 2 combat runs (L21, L24 sampled), the guard transition run (L22) and the guard verification run (L23).
Outcomes: 21 scene stops (exit 11) and 3 normal game exits (exit 0, the game's own shutdown); no fatal.
All sandboxes of this round were deleted after the runs (≈43 GB).
