# Surface transfer and conditional window transitions

Isolated successor to `resource_frame`. The exact implementation is staged in
`out/recovery/surface-transfer-20261030-01/runtime`; production runtime, prior
candidates, consumed identities, original assets and supervisor policy are preserved.
The remote console proof is closed unsuccessful. This workflow has no remote startup,
authorization or genuine-game launch entry point.

Implemented subsystems include surface creation/ownership/copy/readback and conditional
window style/menu/posted-command operations with STYLESTRUCT callback marshalling.
The original renderer's depth-surface resource-cache path motivates this extension.
Backbuffer access is identified in ReadPixels; it is not asserted to run in the first frame.

Run from the repository root with `.venv/Scripts/python.exe -B -I`:

| Script | Purpose |
| --- | --- |
| `phase.py stage` | One-time preservation and copy; refuses an existing phase. |
| `integrate.py` | Rebuild staged sources from the sealed predecessor and templates. |
| `contracts.py` | Native x86/x64 actual-adapter COM-double contracts; real DirectInput. |
| `gui_contracts.py` | Real USER32/native x86/native x64/translated callback differential. |
| `static_audit.py`, `path_audit.py`, `initialization_audit.py` | Original PE, generated markers, resource/conditional-import paths and Init sequence. |
| `phase.py audit` | Independently verify accepted historical SetRes evidence. |
| `phase.py build`, `phase.py verify`, `mapping.py` | Fresh serial candidate, full lineage/PE/PDB/nonconsumption, HLE binding and endpoint audit. |
| `qualify.py` | Owned non-game debugger fixtures; candidate mapped NO_EXECUTE. |
| `regressions.py` | Supervisor, collector and registered-window regressions. |
| `prepare_gpu.py` | Compile one consolidated three-candidate physical batch; never submit/run. |
| `test_evidence.py`, `test_observer.py` | Synthetic evidence/observer corruption tests. |
| `phase.py preservation`, `finalize.py` | Verify preservation and seal receipts/report/batch. |

Runtime changes invalidate build, tests and the physical package. Rebuild dependent
receipts before sealing. Failed/intermediate outputs remain in fresh UUID directories.
The six surface operations retain native HRESULT and last-error behavior within explicit
memory/type/capacity limits. They have protocol coverage but pending physical acceptance.
GetFrontBuffer's physical test is NULL-destination failure only; successful front capture
is unqualified. CopyRects allows at most 256 rectangles; created surfaces allow at most
16384 per dimension and 16M pixels. Existing resource/map budgets remain in force.

Windows scope: SetWindowLongA/W style and exstyle, SetMenu(NULL), and PostMessageA/W
for owned same-thread window command/scalar messages. Pointer fields, non-NULL menus,
foreign/thread/broadcast targets and asynchronous pointer payloads remain guarded.
STYLECHANGING is writable; STYLECHANGED is read-only. No host pointer enters guest memory.

`physical-batch.json` identifies all three immutable candidates and comparison command.
The existing physical collector must retain desktop/module/process/Job/cleanup checks;
the supplementary parser cannot replace a failed collector verdict or grant acceptance.
No genuine Init completion or rendered scene is claimed. Strict x87, full WNDPROC and
independent DirectInput last-error discrepancies remain separately recorded.

Implementation references: preserved, hash-pinned
[DXVK v3.1.1 surface methods](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_device.cpp)
and Microsoft's [SetWindowLong contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowlongw).
