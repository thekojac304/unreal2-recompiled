# X1 validation suite (component differential tests)

These tests check the translated runtime's parts against the originals they replace:
- lifted instructions against the real x86 CPU;
- CRT adapters against the real `msvcr70.dll`;
- x87 helpers against the hardware x87;
- Win32 adapters against the host API.

The end-to-end commandlet comparisons are in `tools/xrt/run_xrt.py` and `CURRENT_STATUS.md`. Run everything from the
workspace root. Build products go to `experiments/xrt/build/<test>/` (git-ignored). Original binaries are only read
from the sandbox copy `sandbox_ref/hellofull/System/`. `common/xrt_test_stubs.c` stubs runtime symbols an
adapter-level harness does not exercise (evidence events, JSON quoting, C++ throw); each build script selects stubs
with `STUB_*` defines.

| Test | Checks | Run | Result (2026-10-22, runtime `xrt_cpu.c` a39bf8c8) |
|---|---|---|---|
| `insn_diff` | Every non-control-flow operand form of the Core.dll + UCC.exe census (203 forms, 294 encoding classes), plus 179 forms the lifter implements but these modules don't use: native 32-bit execution vs lifted C on x64, defined outputs only. `mutation_check.py` proves sensitivity with 13 injected lifter bugs. | `.venv\Scripts\python -I experiments\xrt\tests\insn_diff\run.py` (about 1 min); `--seed 7 --scale 3` | 432,304 cases, 0 failures; seed 7 ×3: 1,293,592 cases, 0 failures; 13/13 mutations killed. `results.before.json` is the run against the pre-pi66 trig model (20 failures, all fsin/fcos/fptan on NaN/inf). |
| `crt_diff` | `xrt_fmt.c` (wide printf, and since gate F the narrow `xrt_output` behind the `sprintf` adapter) and the string/number adapters in `hle_msvcr70.c` vs the real msvcr70.dll | `crt_diff\build.cmd`, then `compare.py --json ...\results.json`; extended: `compare.py --i10 60000 --seed 7` | Wide: 178,398 cases, 0 mismatches. Narrow sprintf: 31,175 cases; **open**: 17 mismatches, all narrow `%s`/`%hs` with a negative precision other than -1 (`%.*5s`, `*` = -1). The real CRT prints the whole string; the runtime prints nothing. |
| `x87` | Runtime x87 helpers vs the hardware x87 (i7-14700K), at the engine's storage precision: engine inputs (FGlobalMath tables, timing loop, `_ftol2`), random/edge records, exhaustive float32 sin/cos/tan/atan/sqrt/exp/loge | `.venv\Scripts\python -I experiments\xrt\tests\x87\run_x87.py --build` (about 1 h; `--skip-exhaustive`, `--quick`) | See below |
| `f1_wtoi` | `_wtoi` adapter vs msvcr70 `_wtol` (review finding F1: long inputs, NBSP, Unicode digits, wrap) | `f1_wtoi\build.cmd`, then compare `build\f1_wtoi\ref.txt` with `cand.txt` (ignoring CR) | 21/21 identical (F1 fixed) |
| `f2_mbcs_argv` | `__getmainargs` command-line splitting vs msvcr70 under the system ANSI code page and a per-process ACP 932 (review finding F2: MBCS lead bytes) | `f2_mbcs_argv\build.cmd`, then `run_f2.py` | **Open**: 6 differences, all under DBCS code pages; identical under the system code page 1252 |
| `f3_sandbox_guard` | The file-system sandbox guard with paths longer than its buffer (review finding F3) | `f3_sandbox_guard\build.cmd`, then `build\f3_sandbox_guard\f3_test.exe <scratch dir>` | No write escapes the sandbox (F3 refuted). The guard is conservative: `\\?\`-prefixed paths are refused even inside the sandbox (control case C4). |
| `f4_setfilepointer` | `SetFilePointer`/`GetFileSize` last-error behaviour: host x86, host x64, and the adapter (review finding F4) | `f4_setfilepointer\build.cmd` (builds and runs) | PASS ×3 (F4 refuted) |

## x87 results (runtime HEAD `805e2fe` → working tree a39bf8c8)

The exhaustive float32 data is in `x87/results.json`: `exhaustive_float32` is HEAD and `working_tree_runtime` is
a39bf8c8.

- **sin:** 314,698,636 → 4 mismatches. All 4 are 1-ulp double-rounding cases.
- **cos:** 314,705,340 → 0.
- **tan, finite in range:** 345,660,498 → 0.
- **tan, |x| >= 2^63:** still 1,090,519,040. The x87 stack underflow after appTan's `fstp st(0)` is not modelled: there
  is no tag word in the CPU struct.
- **FGlobalMath sine table:** 1 → 0 float mismatches. The sqrt table, the timing loop and `_ftol2` were already
  identical.
- **On the measured commandlet paths:** only appSin (table build, finite angles) and appSqrt execute. fptan never runs,
  and no NaN or infinity reaches fsin.

The nine lifted helpers are byte-identical under the current lifter, and `xrt_cpu.c` is unchanged since the
measurement, so these results are current.
