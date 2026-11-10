# Scalable runtime monitoring — experimental subsystem, NOT READY for genuine execution

This is an implemented, qualified foundation for common runtime observation. It
does **not** complete every requested coverage gate. No genuine game was launched,
queued, or retried. Production runtime sources and the supervisor policy were
preserved. All integration lives in a fresh experimental runtime and candidate.

Evidence root: `out/recovery/runtime-monitoring-20261030-01`.
The source templates and reproducible integration are in this directory.

## Architecture and execution boundaries

| Boundary | Common instrumentation | Typed/special handling | Qualification / remaining gap |
|---|---|---|---|
| Windows imports and guest COM stubs | `xrt_loader.c:dispatch`, before existing assertions and after adapter return | DLL + symbol; raw guest CPU and bounded readable stack | Real translated GUI/thread tests pass. Native import signatures and converted arguments remain incomplete. Data imports are memory accesses, outside this scope. |
| D3D8 parent/device/resource native calls | Generated `monitor_com.inc` wrappers, selected by C11 `_Generic` on actual receiver type | Compiler-checked native prototype and `offsetof` slot; actual result; scalar/opaque arguments; explicit bounded struct spans | All 138 D3D8/DirectInput vtable call expressions found in this runtime are wrapped, including prerequisite queries and ternary/cast expressions. Variable payloads remain partial. |
| COM identity | Typed wrapper plus borrowed registry snapshots | Interface ID, native address, guest token, receiver generation, physical interface slot | A slot is never a global method identity. `D8Buffer` is resolved to vertex/index type by registry; inherited `D8Unknown` slots resolve to the registered concrete interface. Native-address reuse is tested. |
| Direct3DCreate8 / DirectInput8Create | Explicit factory entry/return scopes | SDK/version, IID, converted instance identity, actual output pointer value | Native output pointers are opaque identities, not dereferenced objects. No fabricated success. |
| GUI native calls | Existing `begin/end` boundaries, independently of renderer state | Common native scope plus enclosing import identity | Actual GUI return values/converted native parameters are incomplete; several calls do not use begin/end. These are readiness blockers. |
| GUI callbacks | `invoke_gui_proc` before validation; `xrt_call_guest` before guest frame construction and after validated return | Separate nested invocation for native callback and guest transition; complete raw CPU snapshots | Native x86/x64/translated message-delivery comparison passes. Native message-specific payload coverage is not exhaustive. |
| Resource registry | Create/adopt, AddRef, release, bind/unbind, mapping/unlock, retirement/destruction | Existing registry only; refs/bindings/generation and bounded map metadata | Actual adapters tested with owned COM doubles. No added COM references. Binding locations and full mapping contents remain incomplete. |
| DirectInput lifecycle | Typed Acquire, Unacquire, SetCooperativeLevel and Release wrappers | Receiver generation, real HRESULT/error, HWND association and flags | 14 actual adapter/native inner-transfer comparisons pass. One independent Acquire last-error difference remains a strict failure. |
| Fatal / unsupported | `xrt_fatal` records before formatting/cleanup; independent `xm_failure` fail-closed boundary | CPU, frame, diagnostic format, code; pending binary record preserved on sink failure | All retained traps remain. Seven DirectMusic native COM calls and IPC boundaries still need wrappers. |
| Guest threads / CPU transitions | Import scopes and `xrt_call_guest` on thread-local invocation stacks | Shared serialized sequence allocation; independent thread IDs, CPU/TEB snapshots | Four actual guest threads match the native x86 oracle. The runtime's cooperative guest baton remains unchanged. Nonlocal exception/ExitThread scope unwind is unqualified. |
| Init entry / checked return | `xrt_world_enter` / `xrt_world_return` paired `UGameEngine.Init` scope | Raw entry/return CPUs and caller frame | Implemented and linked; genuine execution deliberately untested. |

`coverage.json` inventories import bindings, native COM sites, Windows-call
candidates, nonlocal transitions, typed method descriptors, and blocking gaps.
The lexical Windows-call inventory includes macros and is not a completeness proof.

## Record and preservation contract

`monitor.h` defines a versioned fixed-size little-endian record. Every record has
a globally ordered sequence number and invocation ID. Native calls and callbacks
have per-thread nesting with parent IDs. Records contain typed values, bounded
bytes, full guest CPU bytes (the CPU's thread pointer is explicitly opaque), a
128-byte checked guest stack snapshot, guest TEB last-error, native last-error,
and the host probe context. No pointer is interpreted as a validated object based
only on its numeric value. Missing readable ranges are flagged.

`monitor.asm` saves every GPR, flags, x87/SSE register and control/status state
before C logging, then restores it. Reserved FXSAVE bytes are zeroed before
capture. `monitor.c` restores host last-error after recording. Record construction
uses integer operations and bounded copies; it does not write guest state.
The host snapshot describes the **probe** boundary. It is not represented as an
independent capture of volatile machine registers at every actual API entry/RET.
AVX upper state is outside the qualified non-AVX candidate's scope.

The sink uses exclusive creation, synchronous writes and flushes, a shared SRW
lock, CRC32 chaining, and a 131,072-record limit. CRC detects accidental damage;
source/file SHA-256 identities and debugger comparison provide separate evidence.
There is no sampling, overwrite, or silent-drop mode. A write/flush, capacity,
nesting, span or schema failure retains `xm_pending` and terminates at
`xm_failure`. The debugger captures pending evidence before terminating the Job.
An interrupted write cannot be reported as committed. A filesystem failure cannot
guarantee disk persistence of the failed record; debugger memory capture is the
independent preservation path, and loss of both remains a failure.

The strict reader rejects gaps, duplicates, truncation, bad CRC chains, wrong
parents, invalid sizes, mismatched returns, fatal/gap records and missing close
records. A bounded stopped prefix additionally requires the independently read
committed counter and matching pending bytes. `complete_coverage` remains false
even for a structurally valid stream until the separate coverage gates are met.

No API result, unsupported trap, COM ownership or callback order is replaced by
the monitor. Observer locks and durable writes add latency; scheduling/performance
equivalence and the 60-second genuine workload throughput are not established.

## Live non-game evidence

| Test | Result |
|---|---|
| Core nested calls/callbacks, callback-in-callback and callback-native call, three concurrent workers | PASS, real message-only USER32 window and real DirectInput; nine positive/negative cases |
| Independent debugger comparison | PASS, 149 records; all guest CPU bytes, all GPRs, x87 state, MXCSR, XMM and native TEB last-error matched at the probe |
| Nondefault FPU oracle | PASS, exact 512-byte FXSAVE comparison across the assembly probe with nonempty x87 stack, altered CW/MXCSR and XMM registers |
| Evidence write failure | PASS rejection; complete uncommitted record captured independently; terminated before continuing |
| Stream corruption/gap/truncation/duplicate/missing tail | PASS rejection for all five mutation classes |
| Actual translated resource adapters with trace enabled | PASS, creation/refcount/binding/lock/unlock/destruction and native-address reuse with distinct generations; native doubles, no GPU |
| Actual DirectInput adapters with trace enabled | PASS for 14 native inner-transfer HRESULT/error/CPU comparisons; retained independent-invocation difference remains FAILED |
| Actual GUI runtime with trace enabled | PASS, 806 records, 114 callback scopes; native x86/x64/translated 24-operation, 56-callback-log-row outputs agree; seven negative cases still trap |
| Actual concurrent guest threads | PASS, main + three translated guest threads, native x86 oracle `3 / 48 49 50`; thread-local last-error preserved |
| Retained integrated adapter oracles | PASS, 15,331 checks per architecture; x86 uses immutable prior source, instrumented x64 tested with sink disabled because negative doubles deliberately longjmp/reset |
| Watchdog, descendant Job, cancellation, fatal observation failure | PASS using unchanged production containment machinery |
| Candidate endpoint mapping | PASS, SEC_IMAGE_NO_EXECUTE mapping only; all-thread DR readbacks and termination before identical owned instruction; failure cases retained |

Some early implementation/fixture attempts failed. Their build logs and evidence
directories are retained. Later receipts identify corrected fixture assumptions
and the exact source under test; no historical failure was overwritten or waived.
Strict historical x87/WNDPROC/DirectInput compatibility failures remain failures.

## Candidate and exact stop

The current `build.json`, `candidate-identity.json`, `monitor-linked.json`,
`linked-adapters.json` and `stop-mapping.json` are authoritative. The candidate
contains 265 verified reused generated objects, 15 freshly compiled runtime
objects and one assembled probe object: **281 objects**. All 60 retained HLE
adapter bindings and the common monitoring symbols are resolved through the PDB.

Candidate SHA-256:
`75530d04d139539a6ae8f51eee49c5b6b7770fad9c99b2536867ccdb0fc2a8cb`.

PDB SHA-256:
`d8fd1dbfc9a33ef8c9e2f0864ec549f41424cfff04790ed3f89c15d2d6fb048f`.

Stop at loaded image base + **`0x069F3BFF`**, bytes **`89 5F 44`**,
`mov dword ptr [rdi+0x44], ebx`. At this boundary RDI is the guest CPU,
EBX is `0x1090ED5C`, and CPU.rv has passed the caller's return-address check.
The instruction has not executed. Guest `0x1090ED5C` is the next CALL to
`0x10901370`; it must not run. Original PE bytes and generated source are checked
independently. Host RVAs from earlier candidates must not be reused.

## Breakpoint plan and readiness

Routine native methods/callbacks need no debugger hardware slot in this design.
The proposed four critical slots are runtime fatal, monitor failure, Init endpoint,
and the independently justified CreateDevice environment gate. Init entry state
comes from the runtime pair. This plan is **not activated**. The existing production
supervisor and all its current protections/readback/terminate-before-continue
policy remain unchanged. Owned qualification used existing hardware mechanisms;
no genuine breakpoint boundary was expanded.

Readiness is **NOT READY**. Remaining typed import/GUI coverage, dynamic payloads,
nonlocal exits, cleanup/binding identity, actual error/FPU consumers, and production
observer integration must be qualified first. This package contains no genuine
launcher or queue submission. The fresh candidate requires a new trace sink path
and fails closed if it is absent. No owner launch command is issued.

A future genuine continuation retains **one launch, 60 seconds, no retry**, the
exact Init endpoint, file pins, Job/watchdog containment, all-thread hardware
readbacks and termination before continuing the endpoint. Existing authorization
and consumed-candidate state are unchanged. No original installation/save,
remote repository or release was modified.

## Reproduction (owned preparation only)

From the workspace, use `.venv/Scripts/python.exe -B -I` with:

1. `integrate.py stage` once; it refuses an existing evidence root.
2. `integrate.py integrate`, then `build.py` for a fresh candidate after source changes.
3. `live.py`, `adapter_checks.py contracts`, `adapter_checks.py gui`,
   `resource_trace.py`, `dinput_trace.py`, and `guest_threads.py`.
4. `verify.py`, then `qualify.py` for the current candidate.
5. `audit.py`, then `finalize.py` to check preservation and seal NOT_READY.

Run suites in separate interpreters. Rechecks use fresh UUID directories. The
small top-level JSON files are current consolidation receipts; historical run
directories remain intact. `observer.py` only collects stopped evidence and
rejects incomplete readiness; it never resumes or launches a process.
