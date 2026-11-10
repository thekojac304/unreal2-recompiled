# Measured window callback 0xae(9,0)

October 29, 2026. The first request in owner batch
`204bd647-7eb3-4355-9e5e-e3132ad00f9f` stopped before the runtime fatal body on
`window callback 0xae: unmeasured arguments`, with independently captured
`wParam=9`, `lParam=0`. Cleanup and integrity checks passed.

This fixture derives from `window_ae_boundary`. Native x86 USER32 delivery and
the translated callback agree on 24 samples each for `(8,0)` and `(9,0)`:
ANSI/Unicode classes, popup/overlapped windows, three last-error seeds and two
repeats. Actual default processing, callback order, return values, last errors,
stdcall stack balance and EBP/EBX/ESI/EDI match. The original translated runtime
rejects `(9,0)`; its baseline evidence is preserved. After the two-line runtime
change, all 48 samples pass. `wParam=0`, `wParam=10` and nonzero `lParam` remain
guarded before guest callback execution. No native pointer-negative test runs.

`run.py native`, `run.py translated baseline`, `run.py translated fixed`, and
`run.py audit` are separate phases. The baseline must run before the runtime
change. Output directories are exclusive; `O` and `B` must name fresh paths for
a reproduction. This driver has no genuine game launcher.

Evidence is in `out/recovery/windowae9-20261029-01/`. The complete query-class,
accessibility, dialog, callback ABI/FPU, suspended-CPU and event-stream regression
phase is `out/recovery/queryclass-ae9-20261029-01/`.

The next fresh candidate reached the permanent breakpoint before `0x0696f292`.
That genuine run happened to receive `(8,0)`, so genuine `(9,0)` completion is
not claimed. Its measured fixture remains the evidence for accepting `(9,0)`.
Strict historical x87 and complete WNDPROC equality remain separately FAILED.
