# Current status: X1 translated runtime (UCC.exe + Core.dll on Windows x64)

Updated 2026-10-22. Details and limitations: [experiments/xrt/README.md](experiments/xrt/README.md).

## Working commands (from the workspace root)

```bat
rem 1. lift (generated C is git-ignored: machine translation of proprietary code)
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\UCC.exe --out experiments\xrt\gen\ucc
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\Core.dll --out experiments\xrt\gen\core
rem 2. build (about 30 s; "runtime" rebuilds only the host runtime)
experiments\xrt\build_xrt.cmd
rem 3. compare against the original, same fresh sandbox path for both, N repeats
.venv\Scripts\python -I tools\xrt\run_xrt.py hellofull --repeat 3 -- Core.HelloWorldCommandlet a b c
rem 4. lifter regression tests
.venv\Scripts\python -I -m unittest discover -s tools\xrt\tests -v
```

## Milestones

| | Status | Evidence |
|---|---|---|
| M0 host enters translated code | done | Core `DllMain`, UCC CRT startup, `main`, `appInit` run as lifted C; first failure was an actionable diagnostic |
| M1 module + engine initialisation | done | `appInit`, `UObject::StaticInit`, config load, CPU detection, file-stream worker creation |
| M2 package loaded, commandlet constructed | done | `StaticLoadClass` → `GetPackageLinker` (Core.u) → `StaticConstructObject` executed (report `hit_rvas`) |
| M3 commandlet executes, correct output | done | `UCommandlet::Main` → `eventMain` → `ProcessEvent` → VM `execLog`; stdout byte-identical |
| M4 worker shutdown, cleanup, exit status | done | worker thread runs its polling loop (60–80 `Sleep(1)`), sees `FFileStream::Destroyed`=1, sets 2, `ExitThread`; `appExit`, onexit handlers, `DLL_PROCESS_DETACH`; exit 0 |
| M5 repeated, multiple argument strings | done for Core-only cases | 18/18 runs match fresh original references (6 cases × 3, see `experiments/xrt/results/compare/`) |

Cases: `Core.HelloWorldCommandlet` with `a b c`, no arguments, a new string (`x=1 -flag "two words" back\slash ünï`),
and `a b c -NOMMX -NOSSE`; `Core.SimpleCommandlet`; `Core.ArrayTest`.

## Comparison results

- stdout: byte-identical except ArrayTest's script warning, which embeds wall-clock seconds since start (varies between
  original runs too: 0.620/0.655/0.666); that one field is normalised.
- UCC.log: identical after normalising timestamps, measured CPU speed, elapsed ms, that same seconds field, and the
  "CPU Features" line (CPU policy) - which is identical when both run with `-NOMMX -NOSSE`.
- Function coverage (hellofull): Core 961/968 and UCC 99/100 of the original's executed entries, nothing extra; the
  difference is 2 MMX entries (policy) and 6 relocated labels inside other functions (executed inline).
- Import call counts: identical (including per-call-site `_wcsicmp` histograms when both run in the same sandbox
  path) except timing-dependent ones (`Sleep`, critical sections, `timeGetTime` calibration spin).

## First reproducible failure

None on the target paths. Known fatal-by-design: C++ exception dispatch (e.g. the short alias `HelloWorld` throws
during lookup: `run_xrt.py hello -- HelloWorld a b c` fails with "C++ exception thrown ... not supported").

## Next tasks

1. Differential instruction tests (native x86 vs lifted) over the operand forms in the census; formatter and CRT
   adapter differential tests against the real msvcr70.dll.
2. x87 transcendental accuracy check for the FGlobalMath tables (fsin) against the hardware.
3. C++ exception dispatch (needed for the `HelloWorld` alias and error paths), then Engine.dll / VMProbe.

## Deliberate limitations

See [experiments/xrt/README.md](experiments/xrt/README.md#deliberate-limitations-first-milestone).
