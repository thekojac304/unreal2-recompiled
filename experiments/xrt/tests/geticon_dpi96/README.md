# Focused WM_GETICON DPI-96 evidence

The only production change is in `runtime/hle_gui.c`: accept selector 1 / DPI 96
on callback ingress and SendMessage, and forward the actual DPI. Existing DPI-zero
coverage is retained. Other selectors/nonzero DPI combinations still trap.

`run.py` creates isolated native x86 and translated fixtures from the existing
owned icon probe. It compares normalized typed icon identities, NULL, seeded and
callback-written last-error, stdcall stack/return behavior, nonvolatile registers,
one nested callback, and direct host callbacks with suspended CPU/frame checks.
The final ANSI and Unicode fixtures each cover 48 sends and 72 callback returns.
Nine translated negative processes cover selectors, DPI and wrong handle type.

`wndproc.c` is a native-only D3D8 first-Present diagnostic using pinned DXVK.
It records module/base/RVA attribution, timed callbacks, direct previous-procedure
reachability, installed-procedure forwarding and both cleanup orders. It requires
no input. Installed-procedure snapshots inside destruction callbacks distinguish
restoration before WM_NCDESTROY from an invalid HWND after destruction.

`report.py` independently checks the saved evidence and original-file integrity.
The output is `out/recovery/geticon-dpi96-20261027-01/REPORT.txt` and structured
`acceptance.json`. This is a focused compatibility result, not full renderer or
x87 acceptance. Old failed audits and one-shot captures are unchanged.

The scripts bind this historical output location and refuse to reuse existing
build paths. For a future authorized experiment, select a new output location.
They do not invoke owner phases, the 93-process matrix or a genuine game.
