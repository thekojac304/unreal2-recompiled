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
| `tools/xrt/marks.json` | evidence instrumentation compiled into the translated code (marks, watched globals) |
| `tools/xrt/eh_points.py` | static C++ EH metadata (FuncInfo, try blocks, unwind maps) and uctrace event points |
| `runtime/xrt.h` | guest CPU state, guest memory accessors, flags, x87 model, control-transfer and landing-pad macros |
| `runtime/xrt_mem.c` | 4 GB guest address-space reservation, runtime data region, guest heap |
| `runtime/xrt_loader.c` | module mapping (SHA-256 checked), import binding, exports, dispatcher, call-site histograms, watches |
| `runtime/xrt_thread.c` | guest threads, execution baton, time slicing, ExitThread |
| `runtime/xrt_cpu.c` | x87 helpers, CPU-feature policy (CPUID), RDTSC |
| `runtime/xrt_eh.c` | C++ exception dispatch (msvcr70 `__CxxFrameHandler` semantics) |
| `runtime/xrt_events.c` | ordered evidence timeline (marks, watches, process and thread events) for the report |
| `runtime/xrt_diag.c` | fatal diagnostics (module+RVA, registers, history, guest backtrace), event log, fault handler |
| `runtime/xrt_fmt.c` | msvcr70 `_woutput` (wide printf engine) over guest varargs |
| `runtime/hle_*.c` | host adapters for KERNEL32, MSVCR70, WINMM, ADVAPI32 imports |
| `runtime/xrt_main.c` | host entry point: process model, DllMain/entry sequencing, exit protocol, report |
| `tools/xrt/run_xrt.py` | acceptance runner: original and translated in the same fresh sandbox path, four-way verdict |
| `tracer/uctrace.c` | debugger-based tracer of the original (functions hit, imports, sites, ordered event points, exceptions) |

## Model

- **Addresses.** Guest address `a` is host `xrt_g + a` inside one 4 GB reservation; host pointers are never narrowed.
  Guest handles are table indices, never host `HANDLE` values. Layout: null guard below 64 KB, runtime data,
  uncommitted import-stub region, `UCC.exe` at 0x400000, guest stacks, `Core.dll` at 0x10100000, heap 0x20000000-0x7FF00000.
- **Functions.** Each discovered function is `void f_<va>(CPU*)`. Calls push the guest return address; every call
  site checks the address the callee's `ret` popped (`xrt_badret` on mismatch). Indirect calls/jumps and all import
  calls go through the dispatcher; an unknown target is fatal with a diagnostic.
- **Imports.** Loader fills IATs with guest addresses: exports of the other translated module, stubs dispatching to
  host adapters, adapter-owned data objects (`_iob`, `_adjust_fdiv`), or named stubs that are fatal when called.
- **SEH / C++ EH.** `fs:` is a per-thread guest TEB; EH registration nodes are ordinary guest memory writes and the
  chain is preserved. `_CxxThrowException` is dispatched by `runtime/xrt_eh.c` following msvcr70's VC7 frame handler:
  search (try blocks by state and catch depth, VC7 TypeMatch), catch (catch object, unwind of the nodes above via
  their unwind funclets, local unwind to tryLow, catch funclet below the throw site under a CatchGuard node), rethrow
  (leaves the innermost catch block and continues the suspended search), resumption (fs:[0], EBP, ESP = [node-4],
  then a host landing record: the translated function's pad registered at `mov fs:[0], esp`, or the active catch
  block when the continuation lies inside it). Every catch funclet, unwind action and continuation of UCC.exe and
  Core.dll is verified to be a translated function entry at lift time.
- **Threads.** Real host threads, one guest stack + TEB + CPU each. Translated code runs under a FIFO execution baton
  handed over at blocking imports and by 1 ms time slicing at translated function entries and import calls (never at
  ExitThread/ExitProcess/exit).
- **x87.** Host doubles. With the engine's control word 0x027F (53-bit precision, nearest, all masked) add/sub/mul/
  div/fsqrt and the conversions give the IEEE double result *as long as no operand or intermediate leaves the double
  range*: the hardware keeps an 80-bit exponent in registers, so overflow/underflow/subnormal intermediates (and
  `fild` of integers wider than 53 bits) can differ. fsin/fcos/fptan reduce the argument with the hardware's 66-bit pi
  and evaluate the reduced argument with host libm (measured agreement, see below); fpatan/fyl2x/f2xm1 use host libm.
  Leaving the modelled control-word state is fatal (fldcw, _controlfp, fninit).

### What is measured, and what is not claimed

Measured on an i7-14700K, original hardware x87 at PC=53 against this model (experiments/xrt/tests, by the parallel
validation session, and tools/xrt/tests/x87_sintab):
- instruction differential over every operand form of the lifted modules' census (203 forms, 294 encodings):
  432,304 cases (seed 20261022) and 1,293,592 (seed 7, scale 3): 0 failures; documented model deviations counted
  separately (values outside double range, C1, exception flags, NaN payloads);
- fsin/fcos/fptan over all 2^32 float32 arguments: float32 results identical except 4 sin arguments (1 ulp, double
  rounding) and tan of |x| >= 2^63 (see limitations); FGlobalMath's 16384-entry sine table float32-identical (the
  previous libm model differed in entry 8192, x = pi, by 306 ulp); results are NOT bit-identical at double precision
  (up to ~1.3 double ulp on reduced arguments);
- fsqrt and the exp/atan/loge paths: float32-identical except a few 1-ulp cases (atan 2, loge 6).
None of this is a proof for other inputs; "exact" is only claimed for the IEEE basic operations within double range.

## Deliberate limitations

- CPU-feature policy: CPUID is the host's with MMX/FXSR/SSE/SSE2 (+ AMD MMX/3DNow, SSE3+ bits, leaf 7) cleared, so
  the engine selects its own scalar paths (validated: the original run with `-NOMMX -NOSSE` produces an identical
  UCC.log including the "CPU Features" line). MMX/SSE instructions are lifted as traps.
- x87: 80-bit memory operands, BCD, environment save/restore and FCW states other than PC=53/RC=nearest/all masked
  are traps/fatal; no tag word, so stack underflow is not modelled (e.g. `fptan` of |x| >= 2^63 followed by `fstp
  st(0)` returns a stale register where the hardware returns QNaN indefinite); `fldl2e`/`fldln2`/`fldpi`... load the
  64-bit-significand constants rounded to double (affects e.g. appExp at double precision); 80-bit exponent range of
  intermediates and >53-bit `fild` are not modelled.
- Exceptions: C++ exceptions of the VC7 kind only. Fatal by design: SEH `__try/__except/__finally` frames on the
  exception path, FuncInfo other than 0x19930520, catch objects that need a copy constructor or a virtual-base
  adjustment, a throw while unwind actions run, unhandled exceptions, resumption across a host adapter that called
  guest code. Integer #DE is fatal. Demonstrated so far: the UCC/Core lookup paths (`HelloWorld` alias, unknown class)
  and the controlled probe tools/xrt/tests/ehprobe - not general SEH/C++ EH compatibility.
- Threads: preemption only at translated function entries and import calls; a guest loop with neither cannot be
  preempted. Guest `CRITICAL_SECTION` contents are initialised but not updated (host critical sections are used).
- CRT: empty guest environment (`envp`); no wildcard expansion in `__getmainargs` (and no MBCS lead-byte handling,
  which only matters under a DBCS ANSI code page); only stdout/stderr `FILE`s; wide stdout stops at characters the
  "C" locale cannot convert (as msvcr70 does); `SetConsoleCtrlHandler` is recorded but console events are not forwarded.
- Win32: `GlobalMemoryStatus`/`GetSystemInfo` return WOW64-style 32-bit values; file writes, directory changes and
  attribute changes outside the run's sandbox are refused (fatal); dynamic loading of DLLs other than the translated
  modules is fatal unless the file does not exist (then NULL, as on Windows).
- Imports not on the measured paths are unbound and fatal when called (USER32, SHELL32, ole32, vorbisfile, ...).

## Build and run

See [CURRENT_STATUS.md](../../CURRENT_STATUS.md#working-commands-from-the-workspace-root).
