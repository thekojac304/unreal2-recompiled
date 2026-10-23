# Current status: X1 translated runtime, including Editor.dll / ucc make on Windows x64

Updated 2026-10-22 (US Eastern), compiler recovery and acceptance gates. Details and limitations:
[experiments/xrt/README.md](experiments/xrt/README.md). Component differential tests:
[experiments/xrt/tests/README.md](experiments/xrt/tests/README.md).

## Working commands (from the workspace root)

```bat
rem 1. lift (generated C is git-ignored: machine translation of proprietary code); marks.json is applied.
rem    Any fresh sandbox copy works as the source (the runtime checks every file's SHA-256 against the lift).
.venv\Scripts\python -I tools\xrt\make_sandbox.py sandbox_cmp\lift --probe
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\UCC.exe --out experiments\xrt\gen\ucc
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\Core.dll --out experiments\xrt\gen\core
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\Engine.dll --out experiments\xrt\gen\engine
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\GlmLib.dll --out experiments\xrt\gen\glmlib --base 0x02f40000
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\Editor.dll --out experiments\xrt\gen\editor --base 0x02de0000
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\Window.dll --out experiments\xrt\gen\window
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\plugins\UnrImp.gpi --out experiments\xrt\gen\unrimp --base 0x036d0000
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\lift\System\Fire.dll --out experiments\xrt\gen\fire --base 0x03710000
.venv\Scripts\python -I tools\xrt\lift_sse2.py sandbox_cmp\lift\System\msvcr70.dll 0x7c00ae08 xrt_msvcr70_pow_sse2 --error-handler 0x7c036052 --out experiments\xrt\gen\msvcr70\pow_sse2.c
rem 2. build (about 10 min with Engine/GlmLib; "runtime" rebuilds only the host runtime); the tracer of the original
experiments\xrt\build_xrt.cmd
experiments\xrt\tracer\build.cmd
rem 3. acceptance: registered cases (tools\xrt\cases.py), fresh original reference per run, same sandbox path;
rem    hello and badclass (C++ exception cases) always run the original under uctrace with EH event points
.venv\Scripts\python -I tools\xrt\run_xrt.py hellofull hello_noargs hellonew hellofull_nosse simple arraytest hello badclass --repeat 3
rem    the same with the original run under uctrace (function-entry cross-check of the evidence)
.venv\Scripts\python -I tools\xrt\run_xrt.py hellofull hello_noargs hellonew hellofull_nosse simple arraytest --trace
rem    gate F: VMProbe through the translated Engine.dll and GlmLib.dll (traced: Engine/GlmLib function sets compared)
.venv\Scripts\python -I tools\xrt\run_xrt.py vmprobe --repeat 3
.venv\Scripts\python -I tools\xrt\run_xrt.py vmprobe --trace
rem 4. compiler milestone: 16 compiles + 12 executions, fresh isolated sandboxes
.venv\Scripts\python -I tools\xrt\compile_xrt.py
rem 5. tests: lifter, runner (logic layer always; XRT_E2E=1 adds end-to-end tamper tests, XRT_FULL=1 fails on a
rem    missing real-data layer)
.venv\Scripts\python -I -m unittest discover -s tools\xrt\tests -v
set XRT_E2E=1& set XRT_FULL=1& .venv\Scripts\python -I -m unittest discover -s tools\xrt\tests -p test_run_xrt.py -v
rem 6. C++ exception probe (native msvcr70 vs translated) and FGlobalMath sine table (hardware x87 vs model)
tools\xrt\tests\ehprobe\build_and_run.cmd
tools\xrt\tests\x87_sintab\build_and_run.cmd aae4923
.venv\Scripts\python -I tools\xrt\tests\x87_sintab\check_sintab.py
rem 7. gate-F CRT adapters vs the real msvcr70 (qsort, atof, _CIpow, _CIfmod, _isnan, toupper, strchr, _stricmp,
rem    atoi); --inputs replays operands recorded from a real run (set XRT_MATH_LOG=<file> for xrt_ucc.exe)
tools\xrt\tests\crt_gatef\build.cmd
.venv\Scripts\python -I tools\xrt\tests\crt_gatef\compare.py --json tools\xrt\tests\crt_gatef\results.json
.venv\Scripts\python -I tools\xrt\tests\crt_gatef\compare.py --seed 7 --scale 3
```

Runner exit status: 0 all PASS, 1 any FAIL, 2 usage error, 3 UNVERIFIED (no reference), 4 harness error,
5 re-evaluation of preserved artifacts (`--reevaluate <invocation dir>`, never counted as a fresh result).

## Gates of this phase

| Gate | Status | Evidence |
|---|---|---|
| A. reliable comparison runner | done | `tools/xrt/run_xrt.py` rewritten; adversarial review (4 lenses, 32 findings, 29 confirmed) fixed in `805e2fe` |
| B. milestone evidence as assertions | done | runtime event timeline + marks/watch from `tools/xrt/marks.json`; 7 evidence groups per Core case (+ engine_module_loading for vmprobe); 66 runner tests (+14 lifter tests) |
| C. fresh reconfirmation of M0-M5 | done, 18/18 PASS | invocation `20261022-183909-adefc8f0` (3 x 6 cases) and traced cross-check `20261022-184054-53367051` (6/6) |
| D. targeted differential tests | original scope done; expanded CRT scope has open findings below | x87 trig model replaced (pi66 reduction); instruction, CRT and x87 suites at 0 unexplained differences; claims scoped |
| E. measured C++ exception path | done | `hello`, `badclass` PASS with the original's throw/catch/resume sequence; probe 6/6 identical, 2/2 negatives fatal; 24/24 + 6/6 traced |
| F. Engine.dll / VMProbe | done, `vmprobe` 3/3 + traced 1/1 PASS | VMProbe runs through the translated Engine.dll and GlmLib.dll: stdout identical, Engine/GlmLib executed exactly the original's function sets (1429/981); requirements asserted as evidence |

### A. Runner (what changed and what it now refuses)

Each run is judged on four separate properties: **execution completed**, **output matches a fresh reference**,
**expected result** (the case's own exit code and stdout lines, also required of the reference) and **milestone
evidence valid**; PASS needs all four. Without a reference a run is at most UNVERIFIED (exit 3). Fixed gaps:
worker evidence now decides the verdict; a missing, malformed, stale (run id) or incomplete report, runtime log,
UCC.log or trace fails; results go to a fresh, exclusively created directory per invocation
(`experiments/xrt/results/raw/runs/<id>/`, git-ignored) and nothing is read from anywhere else; `--repeat 0`,
non-integer repeats, timeouts that are not finite or below 1 s, unregistered or path-like case ids and argument lists
that differ from the registry are usage errors; a tracer failure (exit status, run id, completeness, missing JSON) is
reported apart from a guest exit code; equal nonzero exit codes only pass an explicit negative case.
From the review: CRLF/LF differences in UCC.log are no longer normalised away; every file a run writes in its
sandbox is compared (so far only UCC.log is written); the traced original now receives exactly the candidate's
command line (uctrace forwarded unquoted arguments before); the build is bound to marks.json (SHA-256 embedded at
lift time, mark/watch addresses checked); malformed reports and harness exceptions become FAIL instead of crashing;
a per-case sandbox lock; ExitThread/ExitProcess/exit are no longer preemption points of the runtime's scheduler
(a runtime-only interleaving that made "worker exited before ExitProcess" timing dependent).
Not changed: the normalisation list (stdout script-warning seconds; UCC.log timestamps, CPU Speed, Purging-garbage
ms, CPU Features unless -NOMMX -NOSSE).

### B. Milestone evidence (Core commandlet profile)

Marks (instruction addresses, recorded with a global sequence number, thread and [esp]) and a watch on
`FFileStream::Destroyed` are compiled into the translated code from `tools/xrt/marks.json`; the generated function
bodies are otherwise identical (verified by diffing against the previous lift). The runner asserts, in order:
1. initialisation: Core `DllMain` attach returned TRUE < UCC entry < UCC main < `appInit` (called from UCC.exe)
   < `UObject::StaticInit` < `FFileStream::Init`;
2. package load and commandlet construction: `StaticLoadClass` (from UCC.exe) < `StaticLoadObject` <
   `GetPackageLinker` < `Core.u` opened from the sandbox < `StaticConstructObject` called from UCC.exe;
3. commandlet execution: `UCommandlet::Main` (from UCC.exe) < `eventMain` < `FindFunctionChecked` <
   `ProcessEvent` < `ProcessInternal` < each case native (those the original executes for the case) < `appPreExit`;
4. worker: thread 1 created by thread 0 at Core+5a520 after `FFileStream::Init`, started, entry executes on thread 1,
   no other threads;
5. flag: `Destroyed` 0 at arming; exactly two stores, 0->1 by thread 0 inside `FFileStream::Destroy`, then 1->2 by
   the worker inside its function; no change without a recorded store;
6. termination: worker `ExitThread(0)` after store 2, thread end, main leaves the wait loop (mark at 0x1013db08)
   after store 2, worker exited before process exit;
7. cleanup and exit: `appPreExit` < `StaticExit` < `appExit` < `Destroy` < wait finished < UCC main returned 0 <
   CRT `exit(0)` < `ExitProcess(0)` < Core `DLL_PROCESS_DETACH` < exit complete; outcome "exited"; nothing dropped.
No Sleep counts, durations or timing-dependent import counts are asserted. With `--trace` the runner also checks that
the original executed every function-entry milestone the evidence relies on. The error profile (`badclass`) asserts
groups 1 and 4-7, `StaticLoadClass` called from UCC.exe, and that `UCommandlet::Main` is never entered; cases marked
`cxx_exceptions` (`hello`, `badclass`) also assert the C++ exception sequence against the traced original.

Runner tests (`tools/xrt/tests/test_run_xrt.py`, 66 tests; `test_xlift.py` adds 14): synthetic schema-2 timelines
run through the real profiles (each removed event, misattributed or patched flag store, wrong caller, extra thread,
wrong exit value, malformed report, binding mismatch, written-file difference, command-line/input/sandbox mismatch,
tracer failures, C++ exception sequence altered/missing/extra); mutations of the newest real PASS runs (removed
report/worker/milestones, incomplete worker, altered stdout, warning text, bytecode offsets, UCC.log content and line
endings; timing fields still pass); end-to-end with a tampering candidate and a fake tracer (report removed or stale,
runtime log stale or missing, UCC.log omitted while old artifacts exist, no reference -> UNVERIFIED exit 3,
`--repeat 0` -> exit 2, hang -> timeout, fatal diagnostic, extra written file, documented timing differences
accepted).

### C. Fresh reconfirmation (strict runner)

Commands as in step 3 above, on a clean tree at `805e2fe`. Identity recorded in each summary
(`experiments/xrt/results/raw/runs/20261022-183909-adefc8f0/<case>.summary.json`): xrt_ucc.exe
`0c97bc17...52e5`, marks.json `2f0c2551...6ed0`, generated code digest `ecd8d6d9...8b04` (28 files), runtime
sources digest `5be0a285...fe1d`; inputs UCC.exe `84326806...b1ab`, Core.dll `51bdad4d...69cc`, Core.u
`8c649483...fe0f` (same for every run, original and translated).

| Case | Runs | Result |
|---|---|---|
| hellofull (`Core.HelloWorldCommandlet a b c`) | 3 + 1 traced | PASS 4/4 |
| hello_noargs | 3 + 1 traced | PASS 4/4 |
| hellonew (`x=1 -flag "two words" back\slash ÃƒÂ¼nÃƒÂ¯`) | 3 + 1 traced | PASS 4/4 |
| hellofull_nosse (scalar CPU policy matched, CPU Features line compared) | 3 + 1 traced | PASS 4/4 |
| simple (`Core.SimpleCommandlet`) | 3 + 1 traced | PASS 4/4 |
| arraytest (`Core.ArrayTest`) | 3 + 1 traced | PASS 4/4 |

The previous 18/18 result stands; the stricter rerun confirms it with evidence the old runner did not check. What the
stricter runner found on the way: (1) the runtime report embedded the ANSI guest command line, so hellonew's report
was invalid UTF-8 JSON - the old runner never parsed it as required evidence (fixed: ASCII-only JSON); (2) the
traced original received a differently quoted command line than the candidate (fixed in uctrace); (3) the old
committed `compare/hellofull.json` described a single later run, not the 3-run invocation of the 18/18 claim
(summaries are now per invocation, `compare/` keeps the latest per mode, `<case>.traced.json` for traced runs).

### D. Differential tests (native x86 / real msvcr70 / hardware x87 vs the translation)

Suites: `experiments/xrt/tests/` (instruction forms, CRT adapters, x87 helpers, review findings F1-F4; built and run
by the parallel validation session, results in its README) and `tools/xrt/tests/x87_sintab` (FGlobalMath table).

| Area | Found | Resolution | Measured now |
|---|---|---|---|
| fsin/fcos/fptan | the model evaluated the unreduced argument with host libm: FGlobalMath sine table entry 8192 (x = pi) 306 float ulp off the hardware; 20 instruction-diff failures (NaN/inf operands) | argument reduction with the hardware's 66-bit pi (128-bit integer arithmetic), SDM special-operand rules (NaN quiet, inf -> QNaN indefinite, \|x\| >= 2^63 -> C2 set, operand unchanged) | sine table float32-identical (16384/16384); exhaustive float32: sin 4 mismatches of 2^32 (1 ulp, double rounding), cos 0, tan in range 0 |
| fninit | left the control word at the engine's value | sets the full default state; FCW 0x037F (64-bit precision) is outside the model, so fninit is fatal by design | not on any measured path |
| instruction forms | - | - | 432,304 cases (seed 20261022) and 1,293,592 (seed 7, x3): 0 failures; 13/13 injected lifter bugs detected |
| wide printf (`_vsnwprintf`, `wprintf`) | earlier adapter diverged on flag/width/precision corners | rewritten as msvcr70's `_woutput` (`runtime/xrt_fmt.c`) | 178,398 + 281,898 cases vs real msvcr70: 0 mismatches |
| `_wtoi` (F1) | long inputs, NBSP, Unicode digits, overflow wrap differed | rewritten | 21/21 identical |
| `__getmainargs` MBCS (F2) | lead bytes not handled | **open** (documented limitation) | 6 differences, only under DBCS ANSI code pages; identical under 1252 |
| sandbox guard (F3), SetFilePointer last error (F4) | suspected | refuted | no escape; PASS x3 |

Claims revised in the README: "exact" now only for the IEEE basic operations within double range; trig, exp, log
and atan are "measured agreement" (float32-identical on the inputs above, not bit-identical at double precision, up
to ~1.3 double ulp). Not modelled and documented: the x87 tag word (stack underflow, e.g. `fptan` of \|x\| >= 2^63
followed by `fstp st(0)`), the 80-bit exponent range of intermediates, the 64-bit constants of `fldl2e`/`fldpi`...

### E. C++ exception path

`runtime/xrt_eh.c` dispatches `_CxxThrowException` with msvcr70's VC7 `__CxxFrameHandler` semantics (try blocks by
state and catch depth, TypeMatch, catch objects, unwind funclets, local unwind, CatchGuard nodes, rethrow out of a
catch block, resumption). Translated functions get a host landing pad where they register an EH node
(`mov fs:[0], esp`); a continuation inside an active catch funclet resumes through the catch block's pad. At lift
time every catch funclet, unwind action and continuation of UCC.exe and Core.dll is verified to be a translated
entry. The original's choreography is observable through `tools/xrt/eh_points.py` (FuncInfo decoder) and uctrace
`UCTRACE_EVENTS`, and the runner compares it for `cxx_exceptions` cases.

| Check | Result |
|---|---|
| `hello` (`HelloWorld a b c`, short-name lookup) | PASS 3/3: 30 EH events identical to the traced original (14 throws, 14 catches, 2 resumptions; `catch(TCHAR*)` handlers rethrowing from inside the funclet; `GetPackageLinker` same-frame catch at depth 0) |
| `badclass` (`NoSuchCommandletXYZ`, unknown class) | PASS 3/3, same comparison, error profile |
| probe `tools/xrt/tests/ehprobe` (own DLL, real msvcr70 natively) | 6 positive scenarios with identical event logs (destructor cleanup, rethrow, nested, enclosing frame, throw in loop, rethrow from a callee); exercised: 7 unwind actions, 2 rethrows leaving a catch block, 1 resumption inside a catch block, 9 in the owning function, 1 abandoned catch, 2 exception objects destroyed, 1 catch at depth > 0 |
| negatives | unhandled exception (native: escapes to the host) and catch by value with a copy constructor (native: works) both stop the translation with an explicit diagnostic, exit 76 |
| acceptance after E | 24/24 (3 x 8 cases) + traced 6/6 on commit `0120005`, see "Latest acceptance" |

Not claimed: general SEH (`__try`), FuncInfo other than VC7, catch objects needing copy constructors or virtual-base
adjustment, a throw during unwinding, resumption across a host adapter that called guest code - all fatal.

### F. VMProbe through the translated Engine.dll and GlmLib.dll

`VMProbe.VMProbe` (a probe package compiled in phase 0 by the original compiler: 54 script tests over the VM) makes
Core load Engine.dll from `appGetDllHandle`. Engine.dll imports GlmLib.dll (82 imports), whose preferred base is
taken, so the original loader rebases it.

What the runtime gained (all fatal outside what is described):
- **Loader:** lifted modules mapped on demand from `LoadLibraryW` with their translated static imports (application
  directory), base relocations for a rebased lift (`xlift.py --base`, HIGHLOW only), `DllMain` attach in dependency
  order under a loader lock, `DLL_THREAD_ATTACH/DETACH` for guest threads, process detach in reverse initialisation
  order, stacks kept out of module ranges, FreeLibrary reference counts (unloading to zero is fatal).
- **CRT adapters** found by running and by a fresh trace: `qsort` (ported from the DLL: median of three, its
  equal-key skipping), `atof` (`__strgtold12`/`_ld12tod` ported: 25 kept digits with the DLL's 24th-digit rounding
  quirk, ties truncate), narrow `sprintf` (the `_output` build of the printf port), `strchr`, `_stricmp`, `atoi`,
  `toupper`, `_isnan`, `_msize`, `_CIfmod` (measured special-operand rules), `_CIpow` (the DLL's SSE2 core translated
  by `tools/xrt/lift_sse2.py`, tables read from the SHA-checked sandbox msvcr70.dll: host `pow` was 1 ulp off on 2 of
  VMProbe's 3073 real inputs), and `FreeConsole`, `GetSystemTimeAsFileTime`, `GetCurrentProcessId/ThreadId`,
  `QueryPerformanceCounter/Frequency`, `InterlockedIncrement/Decrement`.
- **Tracer:** uctrace handles `UNLOAD_DLL` (the original loader maps GlmLib.dll once without running it and maps it
  again; the old trace had set breakpoints only on the discarded mapping and reported 0 GlmLib functions).

| Check | Result |
|---|---|
| `vmprobe` 3 runs | PASS 3/3, invocation `20261022-203549-1128fedb`: stdout and UCC.log identical to a fresh original each run |
| `vmprobe` traced | PASS, invocation `20261022-203619-cf8b1ee3`: Engine.dll executed exactly the original's 1429 functions, GlmLib.dll exactly its 981 |
| evidence `engine_module_loading` | LoadLibraryW(Engine.dll) called from Core.dll returned 0x10300000; Engine mapped at its preferred base, GlmLib rebased 0x10000000 -> 0x02df0000; GlmLib `DllMain` TRUE before Engine `DllMain` TRUE; appInit < Engine loaded < `UCommandlet::Main`; no other module mapped; only translated modules loaded |
| evidence (all profiles) | worker: `DLL_THREAD_ATTACH` Core; at its exit `DLL_THREAD_DETACH` Engine, GlmLib, Core; process exit detaches Engine, GlmLib, Core |
| CRT adapters vs real msvcr70 (`tools/xrt/tests/crt_gatef`) | 57,707 cases incl. VMProbe's recorded `_CIpow`/`_isnan`/`_CIfmod`/`atof` operands: 0 mismatches; seed 7 x3: 146,583 cases, 0 |
| narrow `sprintf` vs real msvcr70 (parallel session, `experiments/xrt/tests/crt_diff`) | 31,175 narrow cases (17 mismatches found - negative precision on narrow strings - fixed), now 0; wide unchanged at 0 |
| inputs | UCC.exe `84326806...b1ab`, Core.dll `51bdad4d...69cc`, Engine.dll `f951becf...8499`, GlmLib.dll `85399770...bdf3`, msvcr70.dll `f68e4cdb...168a`, VMProbe.u `5d2c77d7...5991`; binary `e21eaf00...73fc`, runtime sources `5fcc4c9c...fa42` |

Known differences in executed functions, all explained (same in the Core-only cases): 6 Core/UCC "functions" the
original passes through are catch continuation addresses that the translation enters only when an exception resumes
there, and 2 are Core's MMX memcpy path, which the original also skips under `-NOMMX -NOSSE` (CPU policy).

Not claimed: Engine paths other than VMProbe's (rendering, audio, input, networking imports stay unbound and fatal),
loader notifications of system threads, a GlmLib.dll base other than 0x02df0000 (the original's varies), errno.

### Latest acceptance

After gate F, on the working tree with binary `e21eaf00...73fc` (runtime sources `5fcc4c9c...fa42`, generated code
`dcb0bb01...70ba` with all four modules and the msvcr70 pow core): Core-only **24/24 PASS**, invocation
`20261022-203729-b7c9f142`, and **traced 6/6**, invocation `20261022-204059-dea58fe2`; `vmprobe` 3/3 + traced 1/1 as above. The
earlier result on commit `0120005` (24/24 + 6/6, before the loader notifications existed) is superseded, not
invalidated. These sources are commit `f268996` (built before committing; later edits touched only docs and tests).
Tests: 80 unit tests OK; with `XRT_E2E=1 XRT_FULL=1` the 66 runner tests incl. end-to-end tampering OK. Install
integrity after all runs: 4757 files, content identical to `experiments/xrt/results/raw/install_before.json`; the
Save junction's names, sizes and timestamps unchanged (never opened).

## Milestones

| | Status | Evidence (strict runner) |
|---|---|---|
| M0 host enters translated code | done | evidence group 1 |
| M1 module + engine initialisation | done | group 1 |
| M2 package loaded, commandlet constructed | done | group 2 |
| M3 commandlet executes, correct output | done | group 3 + output comparison |
| M4 worker shutdown, cleanup, exit status | done | groups 4-7 |
| M5 repeated, multiple argument strings | done for Core-only cases, incl. the exception paths | 24/24 strict + 6/6 traced |
| F VMProbe through translated Engine.dll + GlmLib.dll | done | `vmprobe` 3/3 + traced (function sets identical) |

Highest gate passed: compiler milestone (after F); see the fresh acceptance below.

## Compiler milestone

Fresh invocation `20261023-013214-95746a9f` passed all four variants, with both compilers repeated twice:
12 successful compiles, 4 expected invalid-source failures, and 12 successful executions. The driver is
`tools/xrt/compile_xrt.py`; the compact evidence is
[compile_milestone.json](experiments/xrt/results/compare/compile_milestone.json). Raw stdout, logs, packages,
module hits, file hashes and process metadata remain local under `experiments/xrt/results/raw/compile/`.

| Compiler output | Execution engine | v1 | v2 (changed source) | v3 (four classes) |
|---|---|---|---|---|
| Original | Original (A) | PASS | PASS | PASS |
| Original | Translated (B) | PASS | PASS | PASS |
| Translated | Original (C) | PASS | PASS | PASS |
| Translated | Translated (D) | PASS | PASS | PASS |

Every compile starts without the probe package in a newly copied sandbox, at the same guest-visible path.
Only Core and the project-owned probe are EditPackages. v1/v2/v3 packages are 1528/1530/6924 bytes; all pairwise
comparisons within a variant differ only in header GUID bytes [36,52), including repeated original compiles.
Names, imports, exports and serialized object payloads match. Every GUID is distinct and RFC 4122 v4; translated
GUIDs match the recorded CoCreateGuid call. The shipped Golem.u header is also re-saved with a fresh GUID by both
compilers; all other bytes match the shipped package. No unexplained writes were accepted.

The v2 fixture changes constants/defaults. Its clean recompilations differ from v1 outside the GUID and every
engine combination prints the changed tag and greeting. This proves source-change propagation through a fresh
compile; an incremental build with a pre-existing output package has not been claimed. v3 exercises inheritance,
overrides, super, statics, defaults, arrays, out parameters and control flow. Expected output is checked against
handwritten fixtures, never copied from a run.

The invalid source fails at line 14 with `Bad or missing expression after '$'`, exit 1, matching diagnostic/history
lines, and no probe package on either side. Runtime failure is judged separately from a compiler diagnostic.
Translated reports execute 405 Editor.dll functions for v1/v2, 438 for v3 and 397 for invalid, including
UEditorEngine::InitEditor and MakeScripts. Source-open and package-save events are required. UnrImp.gpi is detached,
unmapped and removed from lookup on successful compiler cleanup; remaining DLLs detach in reverse initialization
order. The invalid path detaches at process exit, matching the original's error shutdown behavior.

Recovery base was `1c7aef2fd39e8348c16368449285259114bba0d7`, with unfinished changes. The pre-edit source snapshot
(321 project files, no ignored game/generated/binary files) is local at `out/recovery/codex-takeover-20261022`.
No active compiler/build workers or Git lock were found; the source hashes stayed stable during the snapshot.
Runtime-only rebuild succeeded using the existing generated objects (all present and newer than their C sources).
The acceptance binary SHA-256 is `99d8e9a4023f90c3d8372d0c478d7787dac0ac2405029c997c657638866a6697`;
runtime source digest `0a8bb57ecb631b0faeeccdba791885c7900514db5662e9bfada5414e5210948e`, generated-code digest
`ac5b6a3b266600efb8e7da389e82aae12791d3b4033f961f6e85e822b4c9d784`, and compiler-driver SHA-256
`8f6ae5b1cd6502afe5ec5910966b8b4b2f4ca810dd1289ea4bdd4890c27ef67c` identify the exact tested state.
Source and test revision: `b987eef37e408327756ebd2d854468f635cb103d`. All 139 Python tests pass with
`XRT_E2E=1 XRT_FULL=1`, with no skips. The v3 expected-output fixture intentionally retains its trailing
space on the grades line. Source/test file hashes and final validation are recorded in `experiments/xrt/results/compare/recovery_validation.json`.

## Recovery regressions and remaining failures

- Commandlets: invocation `20261023-013525-de49eb02`, 27/27 PASS (nine cases, repeat 3). Traced invocation
  `20261023-013948-b8073561`: 7/7 PASS, including matching Engine/GlmLib function sets.
- Instructions: 432,304 cases, zero failures; 13/13 mutations detected. Unsupported instructions remain explicit
  fatal-by-design cases, not successfully emulated instructions. Unchanged x87 runtime SHA-256 is
  `a39bf8c808a508d6e611b91a41b5187ebb37cd4bcfc12995ea18e15634214f8f`; the earlier exhaustive measurements remain
  applicable. Fresh sine-table check: 16,384 float32 entries and 13 edge cases match; double-bit differences remain.
- Gate-F CRT: 51,536 cases, zero mismatches. Exception probe: 6 positives identical; 2 negatives explicitly fatal.
- F1: 21 identical; F3: no write escapes, zero checked adapter failures; F4: three PASS results. F2 remains open:
  six ACP 932 differences; system ACP 1252 cases match. F2 now returns nonzero when differences exist.
- Expanded CRT: 244,110 cases, **110 mismatches, 1,796 PENDING**, exit 1. The reference reproduced all 189 filesystem
  cases. Mismatches: realloc(NULL,0) size (1), _fullpath last-error state (3), _findfirst (64), directory enumeration
  (20), fopen/fclose (22). These concern last-error values and FILE fields as well as heap size; they are preserved
  in `experiments/xrt/tests/crt_diff/repro/` and not counted as passes. The former four NULL-destination _vsnwprintf
  failures are fixed (all nine isolated wide cases now match). Missing narrow bounded adapters stay PENDING.
  Removing only `le=` values from the raw reproducer text makes all 87 _fullpath/find/enumeration pairs identical;
  the 22 fopen/fclose cases also differ in FILE fields. This broader component suite is not globally green;
  the measured compiler milestone above is green.
- Test harnesses were rebuilt against the added dependencies. Unexercised dependency stubs fail explicitly; F3
  validates the expected guard diagnostic and reports assertion failures through its exit status. Instruction
  comparison/mutation failures, missing mutation patterns and mutant build failures now propagate as failures.

## Fresh full-build checkpoint (2026-10-22 US Eastern)

Repository arrived clean at `a182f262a44b1afb86f2e398c2110b32336a90ba`, a documentation-only successor to
`b987eef37e408327756ebd2d854468f635cb103d`. Nothing was reset. `tools/xrt/fresh_checkpoint.py --system sandbox/System`
re-ran the current generators against an existing isolated copy, comparing every generated file and metadata
byte for byte, including marks and the declared relocation bases. All eight module lifts matched. The special
msvcr70 pow lift matched except its input-path provenance comment. No regeneration discrepancy was found.
Scratch translations were removed only after equality; assets were not copied for this check.

The script then built **all generated and runtime translation units against current headers** in a new, empty
`experiments/xrt/build/fresh-20261023-015722-b7ee8987` directory. It reused no objects from the recovery build.
`identity.json` there preserves generator commands, source/input/generated/object hashes and build logs.
The binary is `4582d6c66564015d4f8af19666475c242f591884e7ad25be91d7112cabd63a78`;
runtime sources `0a8bb57ecb631b0faeeccdba791885c7900514db5662e9bfada5414e5210948e`, generated code
`ac5b6a3b266600efb8e7da389e82aae12791d3b4033f961f6e85e822b4c9d784` (unchanged from recovery).
Tested source was `a182f26` plus the build-output-directory and `XRT_BINARY` runner overrides recorded in the
acceptance identities; runtime, lifter, headers and compiler driver were unchanged.

With `XRT_BINARY` set to that exact fresh binary and `XRT_COMPARE_DIR` inside its build directory:

- `run_xrt.py hellofull hello_noargs hellonew hellofull_nosse simple arraytest hello badclass vmprobe`:
  **9/9 PASS**, invocation `20261023-020348-3d5cd480`; exception cases used fresh traced originals.
- `run_xrt.py vmprobe --trace`: **PASS**, `20261023-020511-56569f29`.
- `compile_xrt.py`: **PASS**, `20261023-020602-5166a403`; 12 successful compiles, 4 expected invalid-source
  failures, 12 executions; all package and evidence comparisons passed.
- Default Python unit-test discovery: **139 tests, OK, 17 conditional tests skipped**. Full end-to-end tamper
  coverage was not rerun in this compact pass. Expensive unchanged numerical corpora were not rerun.

The 110 expanded CRT mismatches, 1,796 pending cases and six ACP 932 differences remain open as above.

### Module lift statistics

Engine.dll: 16,449 functions, 3521 static traps, 2326 EH frames; GlmLib.dll (`--base 0x02f40000`): 11,592
functions, 1758 static traps, 1137 EH frames, 31,885 relocation fixups at load; all EH funclets/continuations are
translated entries. msvcr70 `_CIpow` SSE2 core: 644 instructions translated.

## Next concrete task

Stop editor/toolchain expansion. Trace the original headless level-load path first, selecting the smallest shipped
level with the fewest native dependencies. Reuse the loader, translator and sandbox runner to reach
UGameEngine::Init/LoadMap, asserting the level package opened and actor construction/initialization completed.
Translate only native modules reached by that trace and implement the first reproducible missing import, keeping
render/audio/network paths explicit if they are not exercised. Then drive a fixed number of ticks with a fixed
clock and random seed, compare actor counts/transforms and a world-state digest against the original, and repeat
for determinism. A first real frame follows only after level initialization and headless simulation are measured.
No gameplay or graphics expansion was started during this recovery.

## Deliberate limitations

See [experiments/xrt/README.md](experiments/xrt/README.md#deliberate-limitations).
