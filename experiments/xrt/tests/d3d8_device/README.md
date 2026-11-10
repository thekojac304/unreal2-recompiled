# Fixture-only D3D8 device oracle

Production `D8.CreateDevice` remains unsupported. No file in `runtime/` is edited by
these drivers. `FixtureCreateDevice` is injected into a generated copy of hle_misc.c
only for the separate translated fixture executable.

Use fresh, unique output directories; all existing outputs must remain preserved.

```powershell
.venv\Scripts\python.exe -B experiments/xrt/tests/d3d8_device/run.py build --out <fresh-native-dir>
.venv\Scripts\python.exe -B experiments/xrt/tests/d3d8_device/run.py characterize --out <fresh-native-dir>
.venv\Scripts\python.exe -B experiments/xrt/tests/d3d8_device/translated.py build --out <fresh-translated-dir>
.venv\Scripts\python.exe -B experiments/xrt/tests/d3d8_device/translated.py run --out <fresh-translated-dir>
```

The native driver records a command, environment, JSONL, stdout/stderr, DXVK logs and
result JSON per disposable process. Pointer hazards are isolated and caught for
recording, followed immediately by process exit. A 45-second watchdog bounds each
native process. It never invokes Clear, Present or draw methods. Resource queries
are native oracle queries only, with temporary surface references balanced.

The extended cases `cross_thread`, `separate_zero`, `abi_invalid_adapter`,
`abi_invalid_depth`, and repeated failures are dispatched with `run.run_case`;
their exact invocations are in each retained result JSON. Backend failure leaks
are measured, not hidden by guessed cleanup. Do not retry initialization in a
long-lived process until that behavior is resolved or contained.

`audit.py` checks the retained phase's actual HRESULTs, outputs, mutations,
live FPU state, nonvolatile registers, repeated success stability, HWND association
and translated values. Its phase paths intentionally point at preserved evidence.
`source_snapshots.py` recovers earlier fixture revisions and verifies their exact
recorded build hashes; byte-identical snapshots are under each completed build's
`source-snapshot/verified/`. `preserve.py` verifies accepted checkpoint identities
and earlier pending work. `report.py` generates the final report from audited data.

See [the full report](../../D3D8_DEVICE_CHARACTERIZATION.md) for results, limitations,
the public 97-slot device ABI and the proposed bridge design. No genuine client
continuation is part of this fixture suite.
