# Exact SetRenderState(7,1) fixtures

These disposable project-owned PE32/PE32+ clients use pinned x86/x64 DXVK and
the production typed device adapter. They do not launch Unreal II. Production
supports only state 7, value 1. Native alternate-value/invalid-state probes,
GetRenderState readback, 0-to-1 priming and callback injection are test-only.

Every negative identity call saves slot 50 while its device is valid, then calls
the saved pointer with invalid/stale/wrong-type/NULL `this`. The assembly ABI
wrapper is used only for valid devices. The observed fixture logs adapter entry
before identity validation and separates the actual native call interval from
forced callbacks and readback. Production source is copied without observation
for the independent production-translated fixture.

Use a new output directory; all commands run serially. `run.py native-build`,
`run.py native-run`, `audit.py native`, `run.py build`, `run.py run`, and
`audit.py translated` take `--out PATH`, with `--state 7 --value 1` defaults.
Keep every failed output directory. A fixture construction error must be
distinguished from an adapter failure; never reinterpret a guest fault before
adapter entry as a passing identity guard.

The final recovery evidence is in
`out/recovery/d3d8-render-state-recovery-20261025-01/fixture-02`.
Native characterization has 18 processes and 72 instrumented calls. The final
client matrix has 31 native/translated processes, including negative guards,
parent-first lifetime and reentrant callback cases. All comparisons and cleanup
assertions are in `audit.py`. The earlier exit-74 and report-schema failures
remain preserved separately.

Normal paths release device and parent references, destroy windows, and unload
both modules. Fatal reentrant mutation retains modules until process teardown.
Do not add production readback, change HRESULTs or skip rendering to advance.
