# Remote physical-console observation proof

This package does not start or authorize a supervisor, renderer fixture or game.
The native GUI launcher accepts no arguments and can launch only the hash-pinned
native `observation.exe` at a compiled absolute path. It requires the existing
owner SID, authentication LUID, active console session, non-elevated and
unrestricted token before creating a child. It does not obtain alternate tokens.

The child receives a new hidden console on `WinSta0\Default`, without inherited
handles. It is created suspended and assigned to a kill-on-close Job with an
active-process limit of one before resumption. The launcher waits at most 15
seconds and kills the Job on failure. There is no breakaway, restart or replay.

The child records SID/LUID/session, window station/desktop/input desktop, real
console handles and CRT `isatty`, then calls only `ev_snapshot` from the pinned
existing collector DLL. That call enumerates displays/adapters; it creates no
rendering device. After a bounded observation interval, the child exits normally.
No input is read or supplied, and no settings are changed.

Preparation uses the normal sandbox command runner:

```powershell
& '.\.venv\Scripts\python.exe' -B -I experiments/xrt/tests/remote_console_proof/prepare.py preserve
& '.\.venv\Scripts\python.exe' -B -I experiments/xrt/tests/remote_console_proof/prepare.py build
& '.\.venv\Scripts\python.exe' -B -I experiments/xrt/tests/remote_console_proof/audit.py refusal
```

Preparation refuses existing directories. Sandbox invocation verifies argument
rejection and owner-identity refusal, creating no child. Owner-context execution
requires separate explicit approval of the exact mechanism and executable; the
workspace runner is not an owner-context mechanism. Do not obtain owner tokens,
use a shell-through-UI workaround, or change the environment/authorization gates.

After an approved one-shot owner launch, `audit.py evidence` independently checks
saved evidence, reruns the unchanged production environment validator, verifies
actual process termination and scans for descendants. `audit.py preservation`
compares supervisor homes/ledgers/seals, original assets, runtime and physical
display/input configuration against the fresh pre-execution preservation record.

Evidence directory:
`out/recovery/remote-console-proof-20261030-01`.
No successful owner execution may be claimed without `independent-audit.json`.

The single owner-approved `sky.launch_app` call was denied after the permission
dialog identified **Proton VPN** instead of the exact requested executable. No
child evidence was produced. The launch claim is consumed; do not retry, rename
the target, or use another mechanism without fresh approval. The denial and
downstream app-identity investigation are retained in the evidence `REPORT.txt`
and `launch-denial-investigation.json`.
