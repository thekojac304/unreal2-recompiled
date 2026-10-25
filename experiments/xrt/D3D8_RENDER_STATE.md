# Measured D3D8 scalar render states

2026-10-25, US Eastern. The typed device adapter forwards exactly
`(7,1)`, `(9,2)`, `(29,0)`, `(26,1)`, and `(143,1)` to pinned native DXVK.
Every other state/value combination and
production `GetRenderState` remain explicitly unsupported.

Each newly encountered tuple passed independent native x86/x64 characterization
and translated fixture checks for actual HRESULT/last-error, real state changes
and repeats, 256-state readback, stdcall/nonvolatile registers, guest x87,
MXCSR/XMM preservation, COM identity/lifetime, callbacks, reentrancy guards and
window cleanup. Invalid-this fixtures call a slot saved from a valid device.
Prior accepted tuples were freshly rechecked after each bridge extension.

Exactly 4 bounded genuine sessions ran. CreateDevice, Clear, Present and each
supported SetRenderState have paired actual native and guest returns. Present
success has no independent visual game-frame verification. The highest verified
world milestone remains T2. TryRenderDevice, OpenWindow, and Engine Init have
entries without paired returns. No engine or selected-world Tick completed.

Stopped at `SetRenderState` slot 50, caller
`D3DDrv.dll+0xf213`, arguments
`{'state': 48, 'value': 0}`.
The three-additional-combination allowance is exhausted; `(48,0)` remains
unsupported and was not characterized or implemented.

Final executable: `build/d3d8-gouraud-20261025-04/xrt_ucc.exe`

EXE SHA-256: `4f2b5dadb326d0c417a088ee46acc4824384d3788739380612e52dc6526fb9f1`

PDB SHA-256: `d39723bb16d57936116c60553fcefd074c0f8ac6687299bfc701b4f7961807ea`

All 4 builds freshly compiled 279 objects serially. Required D3D8/COM/GUI,
commandlet/VM, compiler, traced and full Python acceptance passed: 33 stages and
158 Python tests with zero skips per build. Protected
inputs, old evidence/builds, pending unrelated work, settings/cursor, locks and
cleanup passed verification after every session.

[Full report](../../out/recovery/d3d8-gouraud-20261025-01/REPORT.txt) and
[fixture instructions](tests/d3d8_state/README.md). Earlier ZENABLE recovery
evidence remains in `out/recovery/d3d8-render-state-recovery-20261025-01`.
