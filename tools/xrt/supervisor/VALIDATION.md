# Autonomous development qualification — October 29, 2026

**PASS; 44 tests, two autonomous recovery cycles, three independent validator
processes, zero genuine launches and zero production genuine requests.**

Final qualification: `c96d57aa-dfc5-412c-898c-bf2b743d4331`.
Evidence: [qualification directory](../../../out/desktop-supervisor/qualification-c96d57aa-dfc5-412c-898c-bf2b743d4331/).
Seal: [qualification.json](../../../out/desktop-supervisor/qualification.json),
SHA-256 `e67b7f9ef587a5ffe9b22b3cabf1f20722a08de67b03d58dc7716a98027c0ae5`;
457 project source/helper files and 220 Python/host files are bound.

The complete [report](../../../out/supervisor-autonomy-20261029-01/REPORT.txt)
answers all seven requested deliverables. [AUTONOMY.md](AUTONOMY.md) specifies the
exact state machine, approved recovery policy, review boundary and adoption steps.

| Qualification | Result |
|---|---|
| RUNNING → DIAGNOSTIC HOLD on contained defects | PASS; actual non-game debuggee with explicitly injected non-security reporting defect |
| Diagnostics remain available; genuine requests rejected before reservation | PASS; fixed hardware-stop fixture, synthetic genuine-scope requests rejected in isolated home |
| Independent qualified recovery | PASS twice in the same Service/batch, without owner interaction; original failed profile is rechecked |
| Unresolved original fixture | Third validator refuses the deliberately still-failing native fixture; hold persists |
| Unresolved isolation guard | Recovery refused even after successful diagnostics; previous guard blocker survives later routine failures |
| Actual integrity violation | Manifest SHA mismatch enters SAFETY HALT; later requests/recovery cannot override it |
| Validator safety fault/crash propagation | PASS; safety failures and loss without cleanup evidence cannot become routine validation failures |
| Helper root cause and enforcement | Exact unchanged helper reproduces pre-IPC failure without ProgramData; trusted Windows folder restores read-only/outside/traversal enforcement |
| Watchdog, tree cleanup, local stop, fatal observer, file pins | PASS; zero remaining Job processes in completed safety cases |
| Production observer and runtime stream | Five live non-game cases pass; actual translated fixture stream equals stopped memory |
| Permanent guest breakpoint | Real consumed candidate's PE/PDB mapping before `0x0696f292` verified offline; live fixture sentinel readback/terminate-before-instruction pass |
| Physical desktop acceptance | Construction desktop correctly rejected; actual owner gate remains mandatory |
| Owner migration | Synthetic console-review test archives exact halt bytes and preserves STOP, ledger prefix and consumed identity; production migration not run |
| Historical preservation | PASS; original halt, all 69 production ledger rows, consumed builds, historical requests/results/evidence, runtime/generated/helper sources, strict failures and protected assets |

The current DirectMusic failure is **eligible for DIAGNOSTIC HOLD**, with verified
failed-closed startup. The legacy `HALTED.json` remains effective **SAFETY HALT**
until explicit owner review. No historical batch is retroactively given a recovery
policy. The code and helper environment change require the separate enforcement
review requested by the owner before any genuine resumption.

The prior halted process still held source pins. Its normal STOP path released
them, changing only the status activity word `halted` → `stopped`, with
`halted: true` and the original batch intact. Original status and qualification
were preserved before shutdown. STOP remains present.

[Preservation evidence](../../../out/supervisor-autonomy-20261029-01/preservation-after.json),
[helper assessment](../../../out/supervisor-autonomy-20261029-01/directmusic-assessment.json),
[machine summary](../../../out/supervisor-autonomy-20261029-01/qualification-summary.json).
Strict x87 and full WNDPROC equality remain separately **FAILED**. These results
make no genuine renderer, first-tick or gameplay claim. Earlier qualification
attempts and historical validation entries below remain retained.

---

# Observer integration repair qualification — October 29, 2026 (historical)

**PASS; zero genuine launches or requests during repair. The production batch
remains stopped and HALTED, with its original 66-row ledger unchanged.**

Current qualification: `058b2a04-6a1c-45fa-a537-30b8c6b48372`.
Evidence: [`qualification-058b2a04-6a1c-45fa-a537-30b8c6b48372`](../../../out/desktop-supervisor/qualification-058b2a04-6a1c-45fa-a537-30b8c6b48372/).
The machine-readable seal is [`qualification.json`](../../../out/desktop-supervisor/qualification.json).

The first genuine attempt stopped before its first debug event continued because
the retained `Observe` instance received `BoundedLoop.run` and `on_debugbreak`,
but not `module_record`, which `run` calls at process creation and DLL load.
This was incomplete mixin binding, not a missing retained implementation or a
runtime/renderer fault. Native fixtures inherited the complete mixin; the old
offline check constructed the retained observer without the production bindings.

`observer.construct` now binds the complete mixin, validates the retained
interface and initial state, and retains instance-bound fatal capture. Production
and qualification use this same constructor. The audit found no further missing
observer methods or state. It also found that null image handles could skip
verification; both process/DLL paths now reject them. Qualification now uses its
own queue/status/ledger so an existing production HALTED state is preserved.

- All **20** unit/regression tests pass. A real disposable non-game debuggee
  reproduces the exact original AttributeError under the original partial
  binding and confirms termination before first continuation.
- Five live production-observer cases pass: thread/DLL/debug-string dispatch,
  fatal without a guest CPU, import fatal with independently captured symbol,
  fatal with an actual translated fixture CPU/stack, and an unapproved DLL.
- The real retained `on_create`, symbol/type queries, `update`, hardware
  breakpoint installation/readback, memory/event snapshots and fatal evidence
  execute. The stop case uses a fixture sentinel whose value remains unchanged;
  it terminates before the sentinel instruction. Production renderer-state
  assertions are not claimed exercised by this non-game sentinel.
- The real candidate's exact PE/PDB mapping before guest `0x0696f292` passes
  offline; that consumed candidate is read only and never launched again.
- Three requests pass through one persistent fixture event loop; replay is
  rejected. Watchdog, descendant cleanup, local cancellation, injected observer
  failure, file pinning and stream/stopped-memory equality pass. All process
  cleanup records report zero active Job processes.
- The isolated construction desktop is correctly rejected by the physical gate.
  Owner physical-desktop checks remain required for a new genuine batch.
- Historical requests, responses, evidence, HALTED, status, ledger, consumed
  candidate, generated/runtime sources, strict-failure evidence and protected
  assets pass preservation checks. Strict x87 and WNDPROC remain separately FAILED.

The old seal was copied before replacement. The repair report and owner restart
steps are in [`REPORT.txt`](../../../out/supervisor-observer-repair-20261029-01/REPORT.txt).
The owner must review and archive the resolved HALTED latch locally before
starting a fresh authorized batch; this repair does not do so. The ledger must
remain in place, so the consumed executable stays permanently ineligible.

---

# Original owner desktop qualification (historical) — October 29, 2026

**Verdict: qualified for owner startup and a bounded renderer-initialization
batch. Zero genuine game launches and zero genuine requests submitted.**

The remaining action is for the owner to start the supervisor from their normal
physical Windows desktop and authorize the batch at its local console. The
construction process runs on `CodexSandboxDesktop`; the actual physical/input
gate correctly rejects that context. This rejection has not been bypassed.

| Check | Result and evidence |
|---|---|
| Parser, authorization, bounded scope, malformed/duplicate/nonfinite JSON, deadlines, stale/future requests | PASS; 17 unit test methods, including the checks below |
| Traversal, ADS, Windows aliases/devices, hardlinks, actual junction escape | PASS |
| Wrong executable/source/dependency/manifest hashes | Rejected; integrity failures latch the batch |
| Durable replay, unchanged genuine SHA across batches, sixth attempt | Rejected; durable pre-launch reservation and hash-chained/fsynced ledger |
| Unclassified failure, interrupted processing record | Batch latches; no retry |
| Classified unsupported stop followed by another distinct request | State-machine test passes; synthetic handler is explicitly non-game |
| Persistent live request/result cycles | Three distinct native non-game requests pass in one event loop |
| Real CLI startup and persistent operation | Three more requests pass through the documented `serve --fixtures-only` process, same PID **54768**, then local stop and clean exit |
| Hardware execute breakpoints | Live readback passes; sentinel buffer unchanged at the stopped instruction |
| Terminate-before-continue | Hard stop and injected fatal-observer failure both terminate before releasing the pending event |
| Watchdog and descendant cleanup | PASS; root and spawned child gone, zero active Job processes |
| Local stop during active tree | PASS; independent watchdog cancels and cleans up the whole Job |
| Shutdown ownership | Non-inheritable kill-on-close Job; explicit cleanup records; no remaining fixture/client processes |
| Executable file pin | Live write attempt denied while pinned |
| Loaded module profile | Debug events identify/hash modules and reject project modules outside the fixed profile before continuation |
| Input cleanup | Existing owner cursor/StickyKeys cleanup runs and verifies the captured baseline; no display change |
| Physical/session/display/input gate | Actual isolated desktop rejected; negative gate cases pass; final physical owner acceptance remains mandatory |
| Runtime evidence surviving termination | Actual translated non-game runtime stream equals complete stopped-memory records before `xrt_fatal` body; no normal-exit report fabricated |
| Candidate permanent stop | New exact PE/PDB disassembly resolves the stop before guest `0x0696f292`; live new-client installation is deliberately untested until owner execution |
| Production observer | Offline construction succeeds with the new candidate and instance-bound fatal evidence; no process created |
| Preserved strict failures | Historical strict x87 and full WNDPROC equality remain separately **FAILED**, with original source hashes verified |
| Original assets, prior consumed build | Final protected-input and complete prior-build inventories pass unchanged |

Final qualification:
[`out/desktop-supervisor/qualification-f932b8c0-7d36-457d-a109-889045b29a5b/`](../../../out/desktop-supervisor/qualification-f932b8c0-7d36-457d-a109-889045b29a5b/).
The machine-readable startup seal is
[`qualification.json`](../../../out/desktop-supervisor/qualification.json), covering
439 project source/helper files and 160 Python/host dependency files. The final
CLI integration evidence is
[`cli-smoke-06b46139-6087-4862-9d16-3a58e9ba6b3c/result.json`](../../../out/desktop-supervisor/cli-smoke-06b46139-6087-4862-9d16-3a58e9ba6b3c/result.json).

The query-class phase passes native x86/x64/translated message, default processing,
real accessibility, nested callback, ABI/x87, suspended-CPU and rejection tests.
The existing OBJID_CLIENT and dialog matrices pass; `-12` remains explicitly
rejected for dialogs. The full documented reproduction command also passes in
the fresh `out/recovery/queryclass-reproduction-20261029-01/` tree, including a
separate unexecuted incremental candidate build. See
[query-class measurements](../../../experiments/xrt/tests/queryclass_boundary/README.md).

The prepared initial candidate is
`experiments/xrt/build/queryclass-20261029-01/client/xrt_ucc.exe`, SHA-256
`a3ae73aea705a328c097e61dfbe3d7644f59390afa7f79ef864157fd38f72d1b`.
Its PDB is `96fa0c881bf21b639cff2a361ba6a67db0e9502b3ca6189ecff5d2baf965549f`.
Fourteen runtime objects were compiled fresh and serially; 265 unchanged generated
objects were copied and individually hash checked from the consumed build. The
candidate preview passes full source/generated/build-output/dependency validation.
No genuine renderer or gameplay milestone is advanced by these results.

Construction issues remain preserved in earlier qualification/evidence trees:
the watchdog's second-termination race was fixed and rerun successfully; a new
over-strict fixture stdout assertion was diagnosed as solely native CRLF versus
translated LF and replaced with the inherited text comparison plus a check that
no other bytes differ. Failed preparations and old evidence were retained.

Startup, stop, queue operation and failure recovery:
[README.md](README.md). Formal schemas:
[request](request.schema.json), [candidate](candidate.schema.json),
[result](result.schema.json). Requalify after changing supervisor code; routine
runtime and non-game fixture development can continue within the authorized batch
using fresh identified builds and request IDs.
