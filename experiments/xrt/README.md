**Graphics checkpoint (2026-10-22 Eastern):** original opens CS_Intro through LoadMap with dgVoodoo2;
translated real splash path passes and stops at Window.dll's GetModuleHandleW. G4/G5 and game rendering remain
open. See [configuration, adapter scope and tests](GRAPHICS_STARTUP.md). Older pre-graphics observations below
are retained as history.

# X1 translated runtime (`xrt`): UCC.exe and its DLLs as translated code on Windows x64

The original 32-bit `UCC.exe`, `Core.dll`, `Engine.dll`, `GlmLib.dll`, `Editor.dll`, `Window.dll`, `Fire.dll` and
GlmLib's plugin `plugins\UnrImp.gpi` are statically translated to C by `tools/xrt/xlift.py` (whole modules, every
discovered function), compiled for x64, and run by a small host runtime (`runtime/`). UCC.exe and Core.dll are mapped
at start; the others when the guest loads them (LoadLibraryW/LoadLibraryA), together with their translated static
imports, as the Windows loader does. The original PE files are read from the sandbox only as data (sections, constant
tables); none of their code is executed. Execution goes through translated functions and explicit host adapters only;
one msvcr70 routine (the SSE2 path of `_CIpow`) is translated as well.

Paths demonstrated: Core commandlets, VMProbe through Engine.dll/GlmLib.dll (gate F), and the UnrealScript compiler
(`ucc make`, Editor.dll): fresh project-owned sources compiled into a package that loads and runs in both the original
and the translated engine (see CURRENT_STATUS.md, "Compiler milestone").

The real Unreal2.exe client is now also translated, with WinDrv/D3DDrv lifts linked for its observed native path.
**Level loading has not passed.** The original fails GetDeviceCaps(HAL) before LoadMap; the candidate stops at the
splash bitmap's USER32!GetDC. See CURRENT_STATUS.md, "Bounded level experiment", for exact evidence and scope.

## Layout

| Path | What |
|---|---|
| `tools/xrt/discover.py` | recursive-descent function discovery (from the tracer phase) |
| `tools/xrt/xlift.py` | x86-32 to C translator, writes `gen/<module>/` (git-ignored: machine translation of proprietary code) |
| `tools/xrt/marks.json` | evidence instrumentation compiled into the translated code (marks, watched globals) |
| `tools/xrt/eh_points.py` | static C++ EH metadata (FuncInfo, try blocks, unwind maps) and uctrace event points |
| `tools/xrt/lift_sse2.py` | translates one SSE2 function of msvcr70.dll to C with SSE2 intrinsics (`_CIpow`'s core -> `gen/msvcr70/`, git-ignored) |
| `runtime/xrt_msvcr70img.c` | msvcr70.dll image loaded as data (SHA-256 checked) for the translated `_CIpow` core and its error-handler rules |
| `runtime/xrt.h` | guest CPU state, guest memory accessors, flags, x87 model, control-transfer and landing-pad macros |
| `runtime/xrt_mem.c` | 4 GB guest address-space reservation, runtime data region, guest heap |
| `runtime/xrt_loader.c` | module mapping (SHA-256 checked), import binding, exports, dispatcher, call-site histograms, watches |
| `runtime/xrt_thread.c` | guest threads, execution baton, time slicing, ExitThread |
| `runtime/xrt_cpu.c` | x87 helpers, CPU-feature policy (CPUID), RDTSC |
| `runtime/xrt_eh.c` | C++ exception dispatch (msvcr70 `__CxxFrameHandler` semantics) |
| `runtime/xrt_events.c` | ordered evidence timeline (marks, watches, process and thread events) for the report |
| `runtime/xrt_diag.c` | fatal diagnostics (module+RVA, registers, history, guest backtrace), event log, fault handler |
| `runtime/xrt_fmt.c` | msvcr70 `_woutput` (wide printf engine) over guest varargs |
| `runtime/hle_*.c` | host adapters for KERNEL32, MSVCR70, WINMM, ADVAPI32 and ole32 (`CoCreateGuid`) imports |
| `runtime/xrt_main.c` | host entry point: process model, DllMain/entry sequencing, FreeLibrary unloading, exit protocol, report |
| `tools/xrt/run_xrt.py` | acceptance runner: original and translated in the same fresh sandbox path, four-way verdict |
| `tools/xrt/compile_xrt.py` | compiler-milestone driver: `ucc make` with both compilers, package comparison, the four compiler/engine combinations |
| `compile_probe/<variant>/` | project-owned UnrealScript probe sources (v1, v2 = changed constants, v3 = extended, invalid) and expected output |
| `tracer/uctrace.c` | debugger-based tracer of the original (functions hit, imports, sites, ordered event points, exceptions) |

## Model

- **Addresses.** Guest address `a` is host `xrt_g + a` inside one 4 GB reservation; host pointers are never narrowed.
  Guest handles are table indices, never host `HANDLE` values. Layout: null guard below 64 KB, runtime data,
  uncommitted import-stub region, `UCC.exe` at 0x400000, guest stacks (skipping every linked module's range),
  `Editor.dll` at 0x02de0000, `GlmLib.dll` at 0x02f40000, `UnrImp.gpi` at 0x036d0000, `Fire.dll` at 0x03710000 (all
  rebased, see below), `Core.dll` at 0x10100000, `Engine.dll` at 0x10300000, `Window.dll` at 0x11000000, heap
  0x20000000-0x7FF00000, and at 0x7FF00000 the module handle the guest gets for kernel32.dll (never committed).
  The optional client host also links Unreal2.exe at 0x10900000, WinDrv.dll at 0x11100000, and D3DDrv.dll rebased
  to 0x06960000; the executable selected by --guest is mapped, never UCC in its place. Client VirtualAlloc blocks
  occupy a separate bounded 0x12000000-0x20000000 pool with reserve/commit/release bookkeeping.
- **Modules and the loader.** Each translated module is lifted for one base. Where the preferred base is taken the
  original loader rebases the DLL, to an address that varies between runs (`ucc make` traces: Editor.dll
  0x02de0000/0x028e0000, GlmLib.dll 0x02f40000/0x02e60000, UnrImp.gpi 0x01100000/0x036d0000, Fire.dll
  0x03670000/0x03710000); the lift uses one observed base (`xlift.py --base`, function entries discovered at the
  preferred base so the function set does not depend on the base) and the runtime applies the same base relocations
  to the mapped image. `LoadLibraryW`/`LoadLibraryA` of a linked translated module maps it and, depth first, its
  translated static imports from the application directory, binds imports, then runs `DllMain(DLL_PROCESS_ATTACH)` in
  dependency order (GlmLib before Engine) under a loader lock. Guest threads get `DLL_THREAD_ATTACH`/`DETACH` for
  every initialised DLL (none of the modules calls `DisableThreadLibraryCalls`); process exit detaches in reverse
  initialisation order. `FreeLibrary` to a zero count unloads: `DllMain(DLL_PROCESS_DETACH)` with lpReserved NULL
  under the loader lock, the references it holds on its translated imports are released (a dependency reaching zero
  is unloaded the same way), then the image is decommitted (a later access faults) and the module leaves the lookup
  tables (GlmLib loads and frees its plugin UnrImp.gpi during editor-mode initialisation). `GetModuleHandleA` of
  kernel32 returns the runtime's kernel32 handle; `GetProcAddress` on it resolves only to host adapters (anything
  else is fatal).
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
  block when the continuation lies inside it). Every catch funclet, unwind action and continuation of every lifted
  module is verified to be a translated function entry at lift time.
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
  which only matters under a DBCS ANSI code page); stdout/stderr plus limited `fopen`/`fclose` (`r`/`w`, no stream I/O); wide stdout stops at characters the
  "C" locale cannot convert (as msvcr70 does); `SetConsoleCtrlHandler` is recorded but console events are not forwarded.
  New file/directory adapters maintain per-thread errno through `_errno`; older adapters do not generally set it. `qsort`, `atof` (`__strgtold12`/`_ld12tod`) and narrow `sprintf`
  (`_output`) are ports of the DLL's own code; `_CIpow` runs the DLL's SSE2 code translated and is fatal if the guest
  control word would select msvcr70's x87 path; `_CIfmod` follows the DLL's measured special-operand rules (not C99).
  Expanded filesystem/heap validation still reports 110 differences (last-error state, FILE fields, realloc(NULL,0) size); `_snprintf`/`_vsnprintf` remain unbound (1,796 pending cases). Measured against the real msvcr70: `tools/xrt/tests/crt_gatef` (0 mismatches, incl. VMProbe's recorded inputs) and
  the parallel session's `experiments/xrt/tests/crt_diff` (narrow and wide printf).
- Loader: LoadLibrary of a DLL that is not a linked translated module is fatal (a missing file fails as on Windows);
  a blocking call inside DllMain is fatal; loader notifications of threads the original process gets from the system
  are not modelled (only guest threads; e.g. UnrImp.gpi's CRT thread attach for a system thread in one original
  trace); every rebased DLL sits at one fixed base while the original's choice varies between runs; `GetProcAddress`
  on kernel32 resolves only functions that have a host adapter (anything else, and lookups by ordinal, are fatal);
  reading kernel32's image through its module handle faults. `FreeConsole` is recorded only: correct while the
  guest's stdout is a file (as in every measured run), not for a console.
- Win32: `GlobalMemoryStatus`/`GetSystemInfo` return WOW64-style 32-bit values; file writes, moves, directory changes
  and attribute changes outside the run's sandbox are refused (fatal); dynamic loading of DLLs other than the
  translated modules is fatal unless the file does not exist (then NULL, as on Windows). For a DLL's own static CRT
  (UnrImp.gpi, VC7 LIBCMT): TLS uses the 64 TEB slots (index values differ from the original's, expansion slots are
  fatal); `HeapCreate` heaps are growable heaps on the guest heap (flags other than `HEAP_NO_SERIALIZE`, a maximum
  size, `HeapReAlloc` and the process heap are fatal); standard handles are the host's (reading or writing them
  through kernel32 is not modelled); the environment block is empty (the same limitation as `__getmainargs`);
  `SetUnhandledExceptionFilter` is recorded but never called (an unhandled guest exception is fatal);
  `IsProcessorFeaturePresent` follows the CPUID policy (SIMD features absent), answers the FDIV-erratum query from
  the host and is fatal for other features; code-page and locale services are the host's on the same arguments.
  `CoCreateGuid` returns a host GUID, recorded as an evidence event (package GUIDs are random in the original too).
- Imports not on the measured paths are unbound and fatal when called (USER32 except the launcher's FindWindowExA
  absent-window query and RegisterWindowMessageW; GDI32, SHELL32, the rest of ole32,
  d3d8, DINPUT, WS2_32, dbghelp, vorbisfile, ...); the translated DLLs keep them as genuine imports, nothing is
  substituted.

## Build and run

See [CURRENT_STATUS.md](../../CURRENT_STATUS.md#working-commands-from-the-workspace-root).

### Real client experiment (currently blocked)

`tools/xrt/fresh_checkpoint.py --system sandbox/System` verifies the declared eight-module generation and builds
all its generated/runtime TUs in a new directory. Keep that accepted directory unchanged. After
`tools/xrt/level_probe.py prepare` stages the one shared isolated content tree, generate the new client modules:

```bat
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\level\System\Unreal2.exe --out experiments\xrt\gen\unreal2
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\level\System\WinDrv.dll --out experiments\xrt\gen\windrv
.venv\Scripts\python -I tools\xrt\xlift.py sandbox_cmp\level\System\D3DDrv.dll --out experiments\xrt\gen\d3ddrv --base 0x06960000
set XRT_BASE_BUILD=E:\Unreal2-Port-Investigation\experiments\xrt\build\fresh-20261023-015722-b7ee8987
set XRT_CLIENT_BUILD=E:\Unreal2-Port-Investigation\experiments\xrt\build\client-bounded-level
experiments\xrt\build_client.cmd
```

Use a new client build directory for a new experiment. `client_identity.py` verifies the unchanged base objects,
generated-code header, new input hashes/bases and object membership, and records current sources and binary.
`XRT_BINARY` selects this binary for run_xrt/compile_xrt/level_probe without replacing the accepted UCC build.

`level_probe.py reference --minimal --timeout-ms 45000` runs the real client with milestone-only breakpoints;
omit `--minimal` for the slower function/import census. Candidate uses `level_probe.py candidate --timeout-ms 45000`.
These commands report process status, never gameplay PASS. Raw commands, source/input identities, writes and
reports stay in results/raw/level. `level_summary.py` writes a structured conservative blocker comparison; a map
open or Tick entry cannot pass world/tick completion. The original error observer stops before a modal crash UI;
the debugger records the stop and EXIT_PROCESS. Time-limit fallback is separately labelled.

Tracer controls: `UCTRACE_TIMEOUT_MS`, `UCTRACE_STOP_LABEL` and `UCTRACE_STOP_AFTER` bound execution; termination
reason/exit/completeness are explicit. `UCTRACE_SITES` also captures bounded diagnostic argument snapshots
(`calls_dropped` is reported). Strings at arbitrary arguments are best-effort diagnostics, not typed world state.

`tests/client_startup/build.cmd` runs the focused startup/memory regressions and builds the read-only x86 graphics
diagnostic. Run `experiments\xrt\build\client_startup\x86\graphics_boundary.exe` separately: it currently returns 1
because GetDeviceCaps(HAL) fails on both adapters. It creates no window/device/frame. CURRENT_STATUS.md records the
bounded result and smallest next frame experiment. No artificial headless engine or successful graphics stub exists.
