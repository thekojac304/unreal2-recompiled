# Autonomous desktop build and test workflow

The fixture service extends the existing Python desktop supervisor and shares its
durable ledger, state, file pinning and queue primitives. It uses
`out/desktop-fixtures` independently of the historical genuine service at
`out/desktop-supervisor`. The old halt, STOP, consumption ledger and game
authorization are not migrated or cleared. No service installer, elevation,
network listener, scheduled task, session switch or display change is involved.

## Owner startup, status and stop

After reviewing the qualification and enforcement changes, open an ordinary
PowerShell on the signed-in physical Windows desktop and run:

```powershell
Set-Location 'E:\Unreal2-Port-Investigation'
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' serve-fixtures
```

The service checks the qualified source/host hashes and physical desktop, then
requires the exact local console phrase:

```text
AUTHORIZE DISPOSABLE FIXTURES FAST AND FORMAL
```

This authorizes four hours of the fixed disposable fixture families. It grants
zero genuine game launches. Keep the console open. Codex then builds and submits
through workspace files without commands being copied to the owner's console.

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' fixture-status
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' stop-fixtures
```

Ctrl+C also stops the service. `out/desktop-fixtures/STOP` cancels the active tree
and leaves queued requests/evidence intact. A later owner startup requires local
removal of this STOP after inspection and a new console authorization. It cannot
resume an interrupted claimed request. A safety halt requires investigation,
requalification and explicit owner review; queue data has no reset operation.

After investigation and a passing requalification, the stopped fixture service's
owner can run `desktop_supervisor.py review-fixtures`. It displays the retained
hold and exact qualification digest and requires its local console review phrase.
It archives the original latch, appends review history and preserves STOP and all
failed evidence. It also records explicitly reviewed correctness blockers. The
next startup requires fresh authorization and the complete original assertions;
review never changes a failed functional or strict verdict. This command operates
only on the fixture home and cannot clear the genuine service's halt or ledger.

## Execution profiles

| Property | Fast development | Formal acceptance |
|---|---|---|
| Approved families | `collector-smoke`, `renderer-abi`, `renderer-group` | `renderer-batch-23` |
| Native/translated scope | Selected group 1–7, native x86/native x64/translated x64 | Two state-148 preflights plus all seven groups × three variants, exactly 23 processes |
| Source | Fresh fixed-recipe candidate with frozen build/source/dependency hashes | Frozen repaired `renderer-evidence-20261029-03` delivery and original historical snapshots |
| Evidence | Exact process, Job, ABI, event and cleanup checks; physical backend/driver identity for graphics | All original environment, driver, module, raw ABI/FPU, COM lifetime, cleanup and numerical differential assertions plus separate interpreter audit |
| Result | Focused development result, no milestone inference | Separate functional and strict compatibility verdicts; `production_accepted` remains false while historical gates fail |
| Failure handling | Contained fixture/parser failures permit later requests | First missing/asserted evidence fails the request; later development remains available |
| Executable reuse | Same disposable candidate may serve distinct request UUIDs | Distinct request UUIDs required; each batch gets fresh evidence |

Gamma, resize, arbitrary groups and translated x86 graphics are not approved.
Renderer ABI fixtures use doubles and create no GPU device. Smoke uses only a
message-only HWND and disposable DLL. Neither constitutes graphics acceptance.

## Codex submission loop

All commands run directly through Codex's existing workspace access after owner
startup. For example:

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' build-test renderer-group --group 7 --arch x64 --variant translated
# Final output line is a fresh candidate UUID.
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' submit-test --candidate '<candidate UUID>' --objective 'Measure FVF calls and readbacks after the fixture repair' --timeout 60
# Output is the request UUID.
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' test-result '<request UUID>'
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' cancel-test '<request UUID>'
```

`submit-test` validates the fixed recipe and hashes before atomically publishing
the request. The service checks them again before and after execution. Multiple
requests can be queued within one batch; failed request IDs are never replayed.
Build output, stderr and all failed build directories are retained.

To edit a failed disposable fixture without changing its retained source files:

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' checkout-test --candidate '<candidate UUID>'
# Edit files in out/fixture-sources/<returned workspace UUID>/sources/.
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' build-test renderer-group --group 7 --arch x64 --variant translated --source-workspace '<workspace UUID>'
```

The fixed compiler recipe creates a new candidate UUID, complete strict-FP build
record, compiler/linker hashes and a new source snapshot. ABI-only regressions
use `build-test renderer-abi` with the same group/arch/variant options. Other
runtime edits and builds use existing project tools; a genuine candidate still
requires the old, separately authorized workflow. Editing supervisor enforcement,
collector transport, validators or guards requires stopping and requalifying.

## Ready formal request

Qualification creates `out/desktop-fixtures/prepared-acceptance.json` and a
copy in its qualification directory. It binds the exact candidate manifest hash,
23-process family, objective and 60-second process deadline. It has not been
queued. Once the owner service is authorized, Codex can submit it with:

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' submit-acceptance
```

Only at submission are the live batch UUID, fresh request UUID and five-minute
queue TTL added. Acceptance never runs as part of preparation or qualification.
Every process uses its unchanged original evidence assertion functions, then a
separate isolated interpreter reruns the full saved-evidence audit. Missing data
never becomes an inferred pass. The prior `-01` results, rejected `-02` run and
repaired `-03` delivery stay preserved.

The original `prepare_evidence.preserve()` also seals the entire old supervisor
tree and old supervisor home. This infrastructure task intentionally changes the
supervisor. The new formal preflight explicitly replaces only those two
infrastructure seals with the current qualified enforcement and preserved
historical genuine home. Frozen renderer deliveries, original numerical/ABI
assertions, runtime/generated trees, protected assets and strict failure sources
remain exact. This delta is recorded in `qualification.json`; original manifests
and old preservation records are not rewritten.

## Recovery and evidence

| Outcome | Execution policy |
|---|---|
| Fixture assertion/exit or parser implementation error, independently cleaned and identity-checked | Failed result retained; next disposable development request allowed |
| Expected unsupported boundary with complete evidence | Existing narrow genuine boundary policy remains; a renderer assertion is never relabeled unsupported to obtain a pass |
| Physical desktop temporarily unavailable | Graphical dispatch pauses before launch; request and gate observations remain; no attempt to change sessions or input/display configuration |
| Unclassified correctness discrepancy | Retain as unresolved, allow focused diagnosis, block formal acceptance across restart; never automatically waive |
| Identity, protected asset, Job/descendant cleanup or enforcement failure | Durable SAFETY HALT; later queue requests rejected; owner investigation required |
| Cancellation or deadline | Kill Job, verify final zero active processes, retain partial evidence; never claim completed fixture cleanup/COM release |

A queued request's five-minute TTL is not renewed by a desktop pause. If it
expires, it receives a retained rejection; Codex may submit a fresh request after
the environment returns. A desktop loss between acceptance processes rejects
that partial batch and preserves all captured evidence; a new complete batch is
needed. Session availability never authorizes partial evidence acceptance.

Each dispatch creates an exclusive evidence directory. `progress.json` tracks
completed processes; `captures/` contains raw owner/child snapshots, mapped module
identities, checkpoint receipts, commands/environment, stdout, events, Job
membership and exit evidence. `assurance.json` records independent cleanup and
identity checks. `result.json`, response JSON, hash inventory and the fsynced,
hash-chained ledger bind the outcome. Replayed request responses get separate
filenames. No prior result is overwritten.

The repaired x86 WOW64 identity path stays in the original production collector:
actual mapped-file identities and PE machine checks are reused without changes.
An independent 50-ms watchdog aborts the non-inheritable kill-on-close Job on
cancellation or the total per-process deadline, including checkpoint/module
collection. Children inherit the Job; there is no breakaway option.

## Qualification and limits

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\tools\xrt\desktop_supervisor.py' qualify-fixtures
```

This runs all supervisor tests, the original 105 collector tests, full legacy
non-game enforcement qualification in an isolated home, and repeated real
production-collector cycles through one persistent fixture service. It injects
a parser exception after collection, repairs a deliberately failing source in a
fresh candidate, tests timeout/cancellation/descendant cleanup, and injects a real
candidate digest mismatch. Qualification permits only harmless non-graphical
processes in its isolated service; even that flag cannot bypass a graphical
physical-desktop gate. Qualification writes a seal, never starts the owner
service, submits graphics or launches genuine Unreal II.

This is a cooperative local development interface, not a sandbox for hostile
native source code from a user with workspace write access. Native code is
trusted project development code built through fixed recipes. Queue data alone
cannot select arbitrary executables or commands. The compiler is never invoked
from queue data. Windows/Python/driver dependencies remain host trust boundaries.

The original installation and saves remain protected. The DirectMusic filesystem
guard, genuine executable one-shot consumption and permanent breakpoint before
guest `0x0696f292` are unchanged. Strict x87, WNDPROC equality and native-x86
compatibility remain FAILED. No push or release is authorized.
