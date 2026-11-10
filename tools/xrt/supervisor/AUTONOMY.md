# Autonomous development and execution safety

Implemented October 29, 2026 (America/New_York). This replaces the single
`halted` execution/development gate. The historical production halt is not
converted, cleared, or adopted by qualification.

## Root cause

Previously `Service.process` treated every exception outside four expected
results as an integrity-or-unclassified failure, overwrote `HALTED.json`, and
rejected every subsequent queue item. Startup also refused a halted home.
Thus successful terminate-before-continue and clean Job teardown still left no
diagnostic path. Execution containment and development eligibility were coupled.

The latest helper failure had a second, concrete integration cause:
`fixture.environment` dropped `ProgramData`. `guard_install` requires it before
installing either NT hook and before COM initialization or its IPC receive loop.
The exact pinned helper reproduces the fatal with that variable absent. With
Windows' known common-app-data folder supplied, the unchanged helper passes
synthetic in-tree reads and denies writes, outside reads and traversal. The
environment now obtains this folder from `SHGetFolderPathW(CSIDL_COMMON_APPDATA)`;
queue values and inherited ProgramData overrides cannot choose it. Neither the
helper executable nor `file_guard.h` was changed.

## Operational states

`status.state` remains the activity indicator (`waiting`, `processing`, `stopped`
or `halted`). `status.operational_state` is the execution policy. For old clients,
`halted` is true for either execution-blocking state.

| State | Queue behavior | Development and exit condition |
|---|---|---|
| RUNNING | Verified fresh genuine requests within the live owner batch, plus fixed qualified fixtures | Existing attempt limits, module verification, watchdogs and permanent breakpoint remain |
| DIAGNOSTIC HOLD | Genuine scope rejected before candidate validation or reservation; only the pinned non-game fixture profile executes | Inspect evidence, repair runtime/non-security harnesses, build disposable differential tests and new candidates; recovery requires the policy and independent checks below |
| SAFETY HALT | All queue execution rejected, including fixture and purported recovery requests | Read-only investigation and independently bounded known-safe qualification remain possible; explicit local owner review required before a fresh batch |

Every non-success needs verified Job cleanup and post-run integrity checks to
qualify for a diagnostic hold. Missing assurance, incomplete cleanup, unhandled
host exceptions, manifest/source/module/asset mismatches or other integrity
exceptions produce SAFETY HALT. A successful result cannot erase a prior hold.
Unknowns remain explicitly unknown; later routine failures cannot make an earlier
unknown or unresolved guard failure recoverable.

| Evidence-based category | Result | Automatic recovery under approved policy |
|---|---|---|
| Expected unsupported GUI/D3D boundary, independently captured and terminated | RUNNING | No recovery needed; proceed with measured compatibility work and a fresh build |
| Routine fixed-fixture defect or explicitly evidenced non-security observer defect, containment/integrity verified | DIAGNOSTIC HOLD | Eligible only after exact failed fixture rechecks and independent validation pass |
| Contained helper startup failure before IPC | DIAGNOSTIC HOLD | Only known non-guard startup defects are eligible; exact helper guard must pass independently |
| Isolation guard startup failure, proved closed before IPC | DIAGNOSTIC HOLD eligibility | Never automatically recovered; guard blocker and owner review requirement persist even after a positive diagnostic |
| Documented experimental x87 difference | DIAGNOSTIC HOLD | No; strict x87 remains FAILED |
| Unclassified correctness failure with verified containment/integrity | DIAGNOSTIC HOLD, explicitly unclassified | No; diagnosis is autonomous, but the policy does not authorize guessing a routine classification |
| Security, integrity, containment, unexplained corruption or unexpected host crash | SAFETY HALT | Never |

## Previously approved recovery policy

The local owner can select `--recovery-policy contained-development-v1` at batch
startup. The exact console phrase includes that policy; the immutable ledger
authorization binds the batch and qualification digest. Old authorizations do
not acquire a policy retroactively. The default authorizes no automatic recovery.

After a successful pinned fixture request in a diagnostic hold, the supervisor
may run its fixed validator in a separate isolated Python interpreter. Queue
JSON has no recovery verb, command, environment, script, or validator path.
The validator reruns every failed fixed-fixture profile, normal fixture and
hardware-stop tests, watchdog/tree/fatal-observer cleanup, the exact helper's
guard tests, and five production-observer non-game cases. It does not launch a
genuine executable. An unresolved original fixture is rejected even if other
diagnostics pass. Validation failure leaves the hold intact.
An actual integrity or containment violation inside the validator, or loss of
the validator without final safety evidence, propagates as SAFETY HALT.

Recovery additionally requires unchanged enforcement/host seals, original
attempt evidence hashes, the same still-authorized unexpired batch, remaining
capacity, no STOP or safety latch, and the physical desktop gate. These gates
are checked after validation too. Recovery appends a ledger event and a new
RUNNING transition. It never changes the old result, consumes a retry, resets a
budget, renews authorization, or removes a consumed executable identity.
Every later genuine request revalidates its build and freshly qualifies the
unchanged helper guard before reservation. Authorization is checked again after
preflight and immediately before genuine launch.

Ledger transitions are authoritative across restart; `operational-state.json` is
a projection. An interrupted claimed request is a safety halt. Restart cannot
renew a diagnostic hold's old batch: fixture-only diagnostics remain available,
but genuine resumption needs explicit review and fresh authorization. The first
`HALTED.json` is never rewritten by subsequent failures. Failure records bind the
original result, request, candidate and evidence. Nested ledger records are copied
so later mutation of an in-memory batch cannot rewrite authorization history.

## Autonomous work and review boundaries

Codex can inspect and characterize every contained failure, fix runtime
compatibility and non-security test/observer integration, run disposable non-game
tests and regressions, and produce fresh build records without per-fixture owner
approval. In an authorized RUNNING batch, or after qualified recovery under its
approved policy, Codex can submit a new candidate. The queue remains a small fixed
execution interface; general development tests run through their existing local
bounded harnesses rather than arbitrary queue commands.

Sealed enforcement files stay pinned while the supervisor runs. Changing
supervisor enforcement, guard/transport rules, Job/watchdog/module/asset checks,
or permanent-stop machinery requires stopping, requalification and separate
owner review. Non-security development outside those files does not expand that
review boundary. Neither an unknown failure nor a known strict x87/WNDPROC failure
becomes an execution pass. Original installations and saves remain protected;
no remote push or release is part of this workflow.

## Current DirectMusic disposition and migration

The latest attempt qualifies for DIAGNOSTIC HOLD **eligibility**, because the
original environment lacks ProgramData, the helper's exact sources/binary match
the retained build, the unchanged helper reproduces the pre-IPC fatal, the game
was terminated before fatal continuation, and process/input/asset/stream checks
passed. No actual containment breach was found. A matching message alone would
not be enough evidence.

Its historical legacy `HALTED.json` remains an effective SAFETY HALT until
explicitly reviewed. This redesign changes enforcement and the helper environment;
the old batch has no approved recovery policy. It cannot be upgraded in place.

The old owner process was still alive holding source pins. Its documented STOP
path was used to release them; status changed only from `halted` to `stopped`,
with `halted: true`. The original status and seal were saved in
`out/supervisor-autonomy-20261029-01/`. The 69-row production ledger, both consumed
genuine identities, historical requests/results/evidence and original halt remain.
STOP remains present. Qualification uses its own queue, candidate directory,
status and ledger, and makes zero genuine requests or launches.

Smallest adoption sequence, performed by the owner after reviewing the report:

```powershell
Set-Location 'E:\Unreal2-Port-Investigation'
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' review-halt
# Read the displayed qualification digest and type its exact review phrase.
# The command archives the original halt with an append-only owner-review record.
# It preserves STOP, the ledger and all consumed identities; no game is launched.
Remove-Item -LiteralPath '.\out\desktop-supervisor\STOP'
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' serve --authorize-genuine-attempts 5 --recovery-policy contained-development-v1
```

The startup prompt is `AUTHORIZE 5 RENDERER INIT WITH CONTAINED-DEVELOPMENT-V1`.
This creates a new four-hour batch, never resumes or edits the old authorization.
Use a newly built executable; both prior genuine hashes remain permanently
ineligible. None of these adoption commands is executed by qualification.
