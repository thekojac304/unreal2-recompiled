# Current status: X1 translated runtime (UCC.exe + Core.dll on Windows x64)

Updated 2026-10-22, phase 2 (acceptance gates). Details and limitations:
[experiments/xrt/README.md](experiments/xrt/README.md). Component differential tests:
[experiments/xrt/tests/README.md](experiments/xrt/tests/README.md).

## Working commands (from the workspace root)

```bat
rem 1. lift (generated C is git-ignored: machine translation of proprietary code); marks.json is applied
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\UCC.exe --out experiments\xrt\gen\ucc
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\Core.dll --out experiments\xrt\gen\core
rem 2. build (about 60 s; "runtime" rebuilds only the host runtime); the tracer of the original
experiments\xrt\build_xrt.cmd
experiments\xrt\tracer\build.cmd
rem 3. acceptance: registered cases (tools\xrt\cases.py), fresh original reference per run, same sandbox path;
rem    hello and badclass (C++ exception cases) always run the original under uctrace with EH event points
.venv\Scripts\python -I tools\xrt\run_xrt.py hellofull hello_noargs hellonew hellofull_nosse simple arraytest hello badclass --repeat 3
rem    the same with the original run under uctrace (function-entry cross-check of the evidence)
.venv\Scripts\python -I tools\xrt\run_xrt.py hellofull hello_noargs hellonew hellofull_nosse simple arraytest --trace
rem 4. tests: lifter, runner (logic layer always; XRT_E2E=1 adds end-to-end tamper tests, XRT_FULL=1 fails on a
rem    missing real-data layer)
.venv\Scripts\python -I -m unittest discover -s tools\xrt\tests -v
set XRT_E2E=1& set XRT_FULL=1& .venv\Scripts\python -I -m unittest discover -s tools\xrt\tests -p test_run_xrt.py -v
rem 5. C++ exception probe (native msvcr70 vs translated) and FGlobalMath sine table (hardware x87 vs model)
tools\xrt\tests\ehprobe\build_and_run.cmd
tools\xrt\tests\x87_sintab\build_and_run.cmd aae4923
.venv\Scripts\python -I tools\xrt\tests\x87_sintab\check_sintab.py
rem 6. gate F (in progress): Engine.dll at its preferred base, GlmLib.dll rebased where the original loader put it
.venv\Scripts\python -I tools\xrt\xlift.py sandbox\System\Engine.dll --out experiments\xrt\gen\engine
.venv\Scripts\python -I tools\xrt\xlift.py sandbox\System\GlmLib.dll --out experiments\xrt\gen\glmlib --base 0x02df0000
```

Runner exit status: 0 all PASS, 1 any FAIL, 2 usage error, 3 UNVERIFIED (no reference), 4 harness error,
5 re-evaluation of preserved artifacts (`--reevaluate <invocation dir>`, never counted as a fresh result).

## Gates of this phase

| Gate | Status | Evidence |
|---|---|---|
| A. reliable comparison runner | done | `tools/xrt/run_xrt.py` rewritten; adversarial review (4 lenses, 32 findings, 29 confirmed) fixed in `805e2fe` |
| B. milestone evidence as assertions | done | runtime event timeline + marks/watch from `tools/xrt/marks.json`; 7 evidence groups per Core case; 61 runner tests (+14 lifter tests) |
| C. fresh reconfirmation of M0-M5 | done, 18/18 PASS | invocation `20261022-183909-adefc8f0` (3 x 6 cases) and traced cross-check `20261022-184054-53367051` (6/6) |
| D. targeted differential tests | done | x87 trig model replaced (pi66 reduction); instruction, CRT and x87 suites at 0 unexplained differences; claims scoped |
| E. measured C++ exception path | done | `hello`, `badclass` PASS with the original's throw/catch/resume sequence; probe 6/6 identical, 2/2 negatives fatal; 24/24 + 6/6 traced |
| F. Engine.dll / VMProbe | in progress | Engine.dll and GlmLib.dll lifted; first failure below |

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

Runner tests (`tools/xrt/tests/test_run_xrt.py`, 61 tests; `test_xlift.py` adds 14): synthetic schema-2 timelines
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
| hellonew (`x=1 -flag "two words" back\slash ünï`) | 3 + 1 traced | PASS 4/4 |
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

### Latest acceptance

On commit `0120005` (only this file modified): **24/24 PASS**, invocation `20261022-193849-832a4aa5` (3 x the 8
cases; hello and badclass with the traced original's EH sequence), and **traced 6/6 PASS**, invocation
`20261022-194149-1d1f0230`. Identity: xrt_ucc.exe `b3a98102...3c7b`, runtime sources `b808865e...b883` (14 files),
generated code `42805624...6e75` (147 files; includes the Engine/GlmLib lifts, which this binary does not link),
marks.json `2f0c2551...6ed0`, uctrace `06aa8b80...08e1`; the same UCC.exe/Core.dll/Core.u inputs as in C.

## Milestones

| | Status | Evidence (strict runner) |
|---|---|---|
| M0 host enters translated code | done | evidence group 1 |
| M1 module + engine initialisation | done | group 1 |
| M2 package loaded, commandlet constructed | done | group 2 |
| M3 commandlet executes, correct output | done | group 3 + output comparison |
| M4 worker shutdown, cleanup, exit status | done | groups 4-7 |
| M5 repeated, multiple argument strings | done for Core-only cases, incl. the exception paths | 24/24 strict + 6/6 traced |

Highest gate passed: E. Engine.dll has not executed yet.

## First reproducible failure

`VMProbe.VMProbe` in a fresh `make_sandbox.py --probe` sandbox:

```bat
.venv\Scripts\python -I tools\xrt\make_sandbox.py sandbox_cmp\vmprobe_try --probe
cd sandbox_cmp\vmprobe_try\System
..\..\..\experiments\xrt\build\xrt_ucc.exe --guest E:\Unreal2-Port-Investigation\sandbox_cmp\vmprobe_try\System\UCC.exe --log ..\xrt.log --report ..\report.json -- VMProbe.VMProbe
```

exits 75: `LoadLibraryW(...\System\Engine.dll): the DLL exists but is not part of this translated runtime`, from
`appGetDllHandle` while `UPackage`'s constructor binds package Engine (`BindPackage`). Expected, since gate F has not
added Engine.dll to the runtime yet.

## Gate F: what the original does (traced, `experiments/xrt/traces/vmprobe.json`)

Engine.dll (preferred base 0x10300000) executes 1429 functions. GlmLib.dll is a static import of Engine.dll (82
imports). Its preferred base 0x10000000 is taken (by vorbisfile in the original, by Core.dll's range in this layout),
so the original loader put it at 0x02df0000. It runs CRT initialisation and calls `malloc` (6853), `qsort` (232,
guest comparator), `toupper` (33), `GetModuleHandleA` (50), `GetTickCount`. msvcr70 imports the runtime does not yet
implement: `qsort`, `toupper` (GlmLib), `_CIpow` (3073 calls), `_isnan` (Core 3072), `_CIfmod` and `atof` (Core).
That trace (an older uctrace) attributes 3072 `_CIpow` calls to Engine.dll, but only GlmLib.dll and Core.dll import
`_CIpow`; the attribution is to be rechecked with the current tracer. Lifted: Engine.dll 16,449 functions (3521 static traps, 2326 EH frames), GlmLib.dll 11,592 functions
(1556 static traps, 1137 EH frames); all EH funclets/continuations are translated entries.

## Next concrete task

Gate F: map lifted modules on demand from `LoadLibraryW` (static imports first, DllMain in dependency order: GlmLib,
then Engine), apply base relocations for a rebased lift, keep guest stacks out of module ranges, add the six CRT
adapters with differential tests against msvcr70, register a `vmprobe` case, then follow the concrete failures.

## Deliberate limitations

See [experiments/xrt/README.md](experiments/xrt/README.md#deliberate-limitations).
