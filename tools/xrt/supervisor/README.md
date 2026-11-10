# Persistent owner desktop test supervisor

For the autonomous disposable GPU build/test system, use the separate
[fixture service workflow](FIXTURE_SERVICE.md). Start it with `serve-fixtures`;
`submit-test` and `submit-acceptance` use its independent queue. The genuine
execution policy documented below remains separately authorized.

This is a local Python supervisor for this workspace, started once by the owner
from their signed-in **physical Windows desktop**, using an ordinary PowerShell
window. No administrator account, service, scheduled task, remote listener or
display change is used. Queue data never becomes a shell command or Python code.

The operational states are **RUNNING**, **DIAGNOSTIC HOLD**, and **SAFETY HALT**.
Contained failures preserve diagnostic development while genuine execution is
blocked. The current legacy halt is preserved and needs a one-time owner review
of the new enforcement before adoption. See [state policy and migration](AUTONOMY.md)
and [qualification results](VALIDATION.md).

## Owner startup

Run exactly:

```powershell
Set-Location 'E:\Unreal2-Port-Investigation'
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' serve --authorize-genuine-attempts 5 --recovery-policy contained-development-v1
```

After the read-only physical desktop, session, input, NVIDIA driver and display
checks pass, type `AUTHORIZE 5 RENDERER INIT WITH CONTAINED-DEVELOPMENT-V1` at its local prompt. This authorizes
one four-hour development batch, with **at most five genuine process launches**,
each limited to **60 seconds**, and the fixed renderer initialization scope.
The supervisor remains waiting between attempts. Requests may name the first
classified unsupported GUI/D3D method or the permanent stop as their expected
boundary. Neither authorization nor a fixture result permits unrestricted gameplay.

The permanent hardware execute breakpoint before guest **0x0696f292** remains
reserved on every debuggee thread. Its exact host instruction is resolved from
each candidate's PE/PDB and read back before continuing. Advancing it requires
separate authorization and a reviewed implementation change; queue data cannot
change it. The existing renderer, x87, WNDPROC, presentation and ABI assertions
remain active. Historical strict x87 and complete WNDPROC equality are separately
**FAILED**, not waived by this supervisor.

Stop with **Ctrl+C**, close the console, or use:

```powershell
& 'E:\Unreal2-Port-Investigation\.venv\Scripts\python.exe' -B -I 'E:\Unreal2-Port-Investigation\tools\xrt\desktop_supervisor.py' stop
```

The `out/desktop-supervisor/STOP` file is also an obvious local stop switch.
The independent watchdog checks it every 50 ms. Debuggee processes enter a
non-inheritable kill-on-close Windows Job before the first debug event is
continued. Children inherit membership; no breakaway flag is allowed. Shutdown
terminates the whole tree. A new owner batch requires the owner to remove STOP.

## Codex operating loop

1. Inspect `out/desktop-supervisor/status.json`, the response and its evidence.
2. Characterize the next boundary using native/translated non-game fixtures.
3. Make the measured compatibility change and run affected checks.
4. Build a fresh candidate with an exact source/generated/object build record.
5. Submit an identified, bounded renderer request while the owner batch waits:

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' submit-renderer `
  --build-record 'out/recovery/<fresh-verified-build>/build.json' `
  --objective 'Validate registered WM_GETOBJECT(0,-12) during viewport initialization; stop at the first unsupported GUI/D3D method or before guest 0x0696f292.'
```

This command is for use **after owner startup**. No genuine request is submitted
during construction. Replace the build-record placeholder with a newly built,
verified, unconsumed candidate; both historical genuine executables are consumed.
An optional `--expected-fatal-format` restricts the expected
stop to an exact runtime format string. The default is the first classified
GUI/D3D unsupported method or permanent stop. Classification is deliberately
narrow: specified WM callbacks, guarded D3D device slots, and missing
USER32/IMM32/D3D8 host imports with an independently decoded DLL/symbol.
Contained unknown stops enter DIAGNOSTIC HOLD and stay explicitly unclassified;
they are not automatically recoverable. Security/integrity/containment failures
enter SAFETY HALT and require owner review. Malformed queue data is rejected.

No failed or timed-out request is retried. Every genuine SHA-256 is allowed only
one launch across **all batches**, including a launch whose supervisor later
crashes. A changed objective, request UUID, PDB or manifest cannot bypass this.
Five capacity slots are reserved durably before launch, not after success.
Timeout may consume a slot without producing a normal runtime report; it never
implies completed initialization or gameplay.

Inspect status with `desktop_supervisor.py status`. For non-game operation only,
start `serve --fixtures-only`, then use `submit-fixture ok-a`, `submit-fixture ok-b`
or `submit-fixture hard-stop`. `routine-failure` is a fixed negative qualification
case that deliberately remains unresolved. Production fixture requests can
execute only the qualified native fixture hash with those fixed arguments.

## Protocol and evidence

The versioned JSON schemas are in `request.schema.json`, `candidate.schema.json`
and `result.schema.json`. `core.py` implements stricter cross-field, clock, file,
hash and authorization checks than JSON Schema alone can express.

- Atomically publish `<UUID>.json` into `out/desktop-supervisor/requests/`.
- Each request identifies the current random batch ID, timestamps (Unix seconds),
  exact objective, immutable candidate manifest SHA-256, expected stop, scope and
  integer deadline. Maximum request lifetime is five minutes; pre-start requests,
  expired requests, replayed IDs and unknown fields are rejected.
- A candidate manifest contains exact executable/PDB/build-record/source and
  dependency identities. Paths use workspace-relative forward slashes.
  Commands, arbitrary arguments, working directories, environment and plugins
  are not request fields. The supervisor constructs all of them from fixed code.
- Genuine candidates must be `experiments/xrt/build/**/xrt_ucc.exe`; complete
  serial-build output, runtime-source and generated-source inventories are
  rechecked before and after execution. Unexpected files fail the build check.
  Executables, PDBs and approved project dependencies are opened with read-only
  sharing for the entire launch. Junctions, symlinks, hardlinks, ADS, UNC/device
  paths, traversal and Windows path aliases are rejected.
- DLL load events are checked before continuation. Only the selected executable,
  exact pinned project DLL dependencies and Windows system dependencies are
  admitted. Their loaded-file identities are recorded. The NVIDIA driver files
  and current owner topology are additionally verified by the existing collector.
- Dependencies are the pinned project DirectMusic helper and x64 DXVK D3D8/D3D9
  pair. Python, its standard library, Windows DLLs and the NVIDIA driver are
  unavoidable host dependencies; their observed identities are recorded/pinned.
  The supervisor imports only its qualified fixed Python modules, never a path
  selected in a request.
- Every attempt gets an exclusive `sandbox_cmp/desktop-<UUID>/` and a fresh
  evidence folder. Only verified snapshot assets are copied. Original installation
  and saves are neither working directories nor output targets. Existing trees
  and previous evidence are never reused or deleted.
- `responses/<UUID>.json` points to request, candidate, command/environment,
  stdout/stderr, raw debugger events, exception/fatal diagnostics, stopped-memory
  runtime records, streamed runtime records, sandbox inventory and cleanup.
  The inherited owner cleanup restores only the attempt's measured cursor and
  StickyKeys baseline if the child changed them; display settings are untouched.
  Replay responses get a separate filename so the original response survives.
  `ledger.jsonl` is fsynced, sequence checked and hash chained. A claim remaining
  in `processing/` after interruption latches the next startup; it is not relaunched.

`XRT_EVENT_STREAM` is an optional fixed-record sink used only by the supervisor.
Normal runs without that environment variable retain their prior behavior.
Every committed event is written synchronously. At controlled stops the stream
must equal the complete stopped-memory timeline, with contiguous sequences and
no truncation. At a forced deadline the stream preserves committed records;
an event interrupted before its write cannot be claimed as recorded. No normal
guest cleanup, COM release, completed tick or gameplay is inferred from termination.

`HALTED.json` means a safety failure or an unresolved historical legacy halt.
It is never rewritten by later failures and cannot be overridden by queue data.
Use `review-halt` only after explicit local owner review; it archives the original
latch and appends review history, leaving STOP and consumed identities intact.
For an integrity failure, interrupted claim or unexplained host crash, stop,
investigate and retain all evidence before owner review and a fresh batch.
Contained unclassified correctness discrepancies retain diagnostic access but
are excluded from automatic recovery.
There is no queue command for clearing it, increasing the batch, changing the
stop, resetting attempts, changing the display or running an arbitrary program.

This provides a bounded cooperative developer workflow under the same Windows
account. It is not an OS security boundary against malicious code or another
process already running as that account. Candidate review, source identity and
the runtime's unsupported-method traps remain essential.

## Qualification and readiness

The October 29 autonomy redesign adds the state-machine and migration checks to
the original observer repair and live non-game production-observer matrix.
Production and qualification use the same complete observer constructor. See
[current qualification](VALIDATION.md). Qualification owns a separate queue,
candidate directory, status and ledger inside its fresh evidence
directory. It can run while the production queue is halted, without clearing the
production latch, publishing a production status, or appending to its ledger.

Reproduce all non-game safety qualification with:

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' qualify
```

This uses native, project-owned fixtures only. It runs parser/path/authorization
tests, real queue cycles in one persistent event loop, replay rejection,
watchdog and descendant cleanup, local stop cancellation, breakpoint readback,
terminate-before-instruction, injected observer failure, file-pin enforcement,
and a read-only actual desktop observation. It resolves the new candidate's
permanent stop and constructs its production observer **without launching it**.
The resulting `out/desktop-supervisor/qualification.json` binds the qualified
source/dependency hashes and evidence. Startup refuses changed supervisor code.
Runtime compatibility sources may evolve during a batch; each new build must
bind their exact identities. Changing supervisor code requires stopping and
requalifying it.

Construction runs on `CodexSandboxDesktop`, whose physical input gate correctly
refuses genuine execution. The owner's actual Default desktop is checked twice
at startup and again before launch/CreateDevice/after cleanup. Final owner
desktop acceptance cannot be substituted with the construction observation.

The initial query-class fixture, regressions, build and readiness results are
documented in `experiments/xrt/tests/queryclass_boundary/README.md`. No genuine
game has been launched or queued by this implementation task.
