# Measured D3D8 ZENABLE state

2026-10-25, US Eastern. The typed device adapter forwards exactly
`SetRenderState(7,1)` to pinned native DXVK. All other state/value tuples and
production `GetRenderState` stop explicitly. The existing device identity,
window lifetime, callback context and reentrancy guards apply. No textures,
buffers, shaders, drawing or additional device methods were added.

Fresh native x86/x64 characterization and translated fixtures pass for actual
HRESULT/last-error, a real 0-to-1 readback transition, repeated calls, stdcall,
nonvolatile registers, x87 values/control/status/TOP, MXCSR and XMM6-XMM15.
Wrong-type, stale, invalid and NULL device arguments are rejected before native
forwarding. Parent-first lifetime, nested callbacks, reentrant Release/state
calls, pinned-window destruction, unsupported GetRenderState and cleanup pass.

The original invalid-device fixture incorrectly loaded a vtable from `this=1`.
Its exit-74 evidence remains under `out/recovery/d3d8-render-state-20261025-01`.
The corrected fixture retains slot 50 from a valid typed device and calls that
function with invalid `this`; an isolated observer proves adapter entry and
exit 76 before any native state call. Production implementation source did not
change during fixture recovery.

Fresh serial production build: all 279 objects, no reused objects.
`build/d3d8-render-state-recovery-20261025-01/xrt_ucc.exe`

EXE SHA-256: `c8fdb9cd70658408c6ed86cbe3e10c4a208f4ab68cc4c3ff146e8c9210a4e7c2`

PDB SHA-256: `fa50547f0113435d9b2e02bbb8a1f7784f04a9d54855d09a0cf13da743aacc51`

Fresh D3D8, COM ownership, Clear/Present, GUI/window/callback, compact VM and
commandlet, compiler and full Python acceptance pass. One genuine translated
graphical session completes paired CreateDevice, Clear, Present and
SetRenderState(7,1) returns through the real backend. No game frame was visually
captured. Viewport/engine/world completion is established only by paired trace
evidence in the report.

The next unsupported call is `SetRenderState` with arguments
`{'state': 9, 'value': 2}`, slot 50, caller
`0x696f1ac`. It remains unsupported; no second game session ran.

Existing CRT, ACP 932 and general x87 limitations remain unchanged.

[Full report](../../out/recovery/d3d8-render-state-recovery-20261025-01/REPORT.txt)
and [fixture instructions](tests/d3d8_state/README.md).
