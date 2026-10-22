# X1 translated runtime (`xrt`): UCC.exe + Core.dll as translated code on Windows x64

The original 32-bit `UCC.exe` and `Core.dll` are statically translated to C by `tools/xrt/xlift.py` (whole modules,
every discovered function), compiled for x64, and run by a small host runtime (`runtime/`). The original PE files
are read from the sandbox only as data (sections, constant tables); none of their code is executed. Execution goes
through translated functions and explicit host adapters only.

## Layout

| Path | What |
|---|---|
| `tools/xrt/discover.py` | recursive-descent function discovery (from the tracer phase) |
| `tools/xrt/xlift.py` | x86-32 to C translator, writes `gen/<module>/` (git-ignored: machine translation of proprietary code) |
| `runtime/xrt.h` | guest CPU state, guest memory accessors, flags, x87 model, control-transfer macros used by generated code |
| `runtime/xrt_mem.c` | 4 GB guest address-space reservation, runtime data region, guest heap |
| `runtime/xrt_loader.c` | module mapping (SHA-256 checked), import binding, exports, dispatcher, call-site histograms, watches |
| `runtime/xrt_thread.c` | guest threads, execution baton, time slicing, ExitThread |
| `runtime/xrt_cpu.c` | x87 helpers, CPU-feature policy (CPUID), RDTSC |
| `runtime/xrt_diag.c` | fatal diagnostics (module+RVA, registers, history, guest backtrace), event log, fault handler |
| `runtime/xrt_fmt.c` | msvcr70-compatible wide printf formatter over guest varargs |
| `runtime/hle_*.c` | host adapters for KERNEL32, MSVCR70, WINMM, ADVAPI32 imports |
| `runtime/xrt_main.c` | host entry point: process model, DllMain/entry sequencing, exit protocol, report |
| `tools/xrt/run_xrt.py` | runs original and translated in the same fresh sandbox path and compares |
| `tracer/uctrace.c` | debugger-based tracer of the original (functions hit, imports, per-site histograms) |

## Model

- **Addresses.** Guest address `a` is host `xrt_g + a` inside one 4 GB reservation; host pointers are never narrowed.
  Guest handles are table indices, never host `HANDLE` values. Layout: null guard below 64 KB, runtime data,
  uncommitted import-stub region, `UCC.exe` at 0x400000, guest stacks, `Core.dll` at 0x10100000, heap 0x20000000-0x7FF00000.
- **Functions.** Each discovered function is `void f_<va>(CPU*)`. Calls push the guest return address; every call
  site checks the address the callee's `ret` popped (`xrt_badret` on mismatch). Indirect calls/jumps and all import
  calls go through the dispatcher; an unknown target is fatal with a diagnostic.
- **Imports.** Loader fills IATs with guest addresses: exports of the other translated module, stubs dispatching to
  host adapters, adapter-owned data objects (`_iob`, `_adjust_fdiv`), or named stubs that are fatal when called.
- **SEH / C++ EH.** `fs:` is a per-thread guest TEB; registration records are ordinary guest memory writes and the
  chain is preserved. Dispatch is not implemented: `_CxxThrowException` and the frame handlers are fatal with a
  description of the thrown object.
- **Threads.** Real host threads, one guest stack + TEB + CPU each. Translated code runs under a FIFO execution baton
  handed over at blocking imports and by 1 ms time slicing at translated function entries and import calls.
- **x87.** Host doubles. Exact for the engine's control word 0x027F (53-bit precision, nearest, masked) for add/sub/
  mul/div/sqrt and conversions; leaving that state is fatal.

## Deliberate limitations (first milestone)

- CPU-feature policy: CPUID is the host's with MMX/FXSR/SSE/SSE2 (+ AMD MMX/3DNow, SSE3+ bits, leaf 7) cleared, so
  the engine selects its own scalar paths (validated: the original run with `-NOMMX -NOSSE` produces an identical
  UCC.log including the "CPU Features" line). MMX/SSE instructions are lifted as traps.
- x87: 80-bit memory operands, BCD, environment save/restore and FCW states other than PC=53/RC=nearest/all masked
  are traps/fatal; transcendental instructions (fsin, fcos, fptan, fpatan, fyl2x, f2xm1) use host libm and may differ
  from the hardware in the last bits; 80-bit exponent range of intermediates and >53-bit `fild` are not modelled.
- Exceptions: no SEH/C++ exception dispatch; integer #DE is fatal.
- Threads: preemption only at translated function entries and import calls; a guest loop with neither cannot be
  preempted. Guest `CRITICAL_SECTION` contents are initialised but not updated (host critical sections are used).
- CRT: empty guest environment (`envp`); no wildcard expansion in `__getmainargs`; only stdout/stderr `FILE`s; wide
  stdout stops at characters the "C" locale cannot convert (as msvcr70 does); `SetConsoleCtrlHandler` is recorded
  but console events are not forwarded.
- Win32: `GlobalMemoryStatus`/`GetSystemInfo` return WOW64-style 32-bit values; file writes, directory changes and
  attribute changes outside the run's sandbox are refused (fatal); dynamic loading of DLLs other than the translated
  modules is fatal unless the file does not exist (then NULL, as on Windows).
- Imports not on the measured paths are unbound and fatal when called (USER32, SHELL32, ole32, vorbisfile, ...).

## Build and run

```bat
python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\UCC.exe --out experiments\xrt\gen\ucc
python -I tools\xrt\xlift.py sandbox_ref\hellofull\System\Core.dll --out experiments\xrt\gen\core
experiments\xrt\build_xrt.cmd
python -I tools\xrt\run_xrt.py hellofull --repeat 3 -- Core.HelloWorldCommandlet a b c
```
