# Registered-window OBJID_QUERYCLASSNAMEIDX

October 29, 2026. The new production gate admits only a live registered Unicode
WNDPROC, actual matching class procedure/module generation, `WM_GETOBJECT`,
`wParam=0`, and zero- or sign-extended `OBJID_QUERYCLASSNAMEIDX` (`-12`). The real
guest WNDPROC and Windows `DefWindowProcW` execute through the existing validated
callback frame. The measured default result is zero. Nonzero results retain the
existing trap; no accessible object, cookie, class identifier or provider is invented.

Windows documents this ID as a standard-control identification request and says
that unhandled `WM_GETOBJECT` requests go to default processing. Custom controls
may return zero. See [WM_GETOBJECT](https://learn.microsoft.com/en-us/windows/win32/winauto/wm-getobject)
and [query-class identifier values](https://learn.microsoft.com/en-us/windows/win32/winauto/appendix-f--object-identifier-values-for-objid-queryclassnameidx).

The native x86/x64 fixtures were run before the production change; the original
translated fixture stopped at the expected `-12` guard. After the change:

- All three architectures match across 18 samples each, using `SendMessageW`,
  real default processing and direct registered-procedure invocation; both x64
  integer representations are observed behind the actual adapter.
- All 18 host ABI/x87/MXCSR checks per architecture pass. Translated guest
  callback ABI/FPU checks and 18 complete suspended-CPU comparisons pass.
- Three real `AccessibleObjectFromWindow` acquisitions per architecture agree
  on role/state/child count/HWND identity. Objects are released; no substitute
  accessibility provider is used. Nested callbacks and measured focus requests pass.
- Ten registered-window negatives pass: other ID, wParam, upper ID bits, upper
  wParam bits, nonzero result, ANSI class, UIA ID, mutated forwarding arguments,
  unrelated pointer message and arbitrary unregistered procedure.
- The original 18-sample registered `OBJID_CLIENT` fixture and the original
  18-sample dialog/three-accessibility-query/four-negative matrix pass. The new
  `-12` tuple is also explicitly rejected in the separate translated dialog
  protocol (exit 76).
- The optional supervisor event stream equals every runtime report record in
  positive message, accessibility and fatal-negative fixtures. The supervisor's
  live debugger additionally verifies stream equality to stopped process memory
  before a non-game runtime fatal body executes, then terminates before continuing.

The original client comparison emitted native CRLF and translated LF. Its first
new byte-equality assertion exposed only that line-ending difference. The final
audit checks that CRLF-to-LF is the sole difference, preserving the inherited
text-mode comparison and all actual ABI/state assertions. The failed assertion
and earlier build-preparation records remain in the evidence tree. No genuine
attempt was made in any of these construction steps.

Evidence: `out/recovery/queryclass-20261029-01/`, including `fixture-audit.json`,
`regressions.json`, `dialog-queryclass-guard.json`, `stream-audit.json`, before
sources, implementation patches, and `final-integrity.json`.

The unexecuted experimental client has SHA-256
`a3ae73aea705a328c097e61dfbe3d7644f59390afa7f79ef864157fd38f72d1b`.
Fourteen runtime objects were compiled fresh, serially; 265 generated objects
were copied from the exact hash-verified consumed build. All 279 objects, source
and generated inventories, link response, PE and PDB are identified in `build.json`.
This is explicitly an incremental runtime build. `candidate-preview.json` passes
the supervisor's complete candidate validation without being queued or launched.
The exact PE/PDB stop mapping before guest `0x0696f292` resolves successfully;
live target breakpoint installation awaits the owner-authorized execution.

Reproduce the complete positive/negative non-game phase into fresh output paths:

```powershell
& '.\.venv\Scripts\python.exe' -B -I '.\experiments\xrt\tests\queryclass_boundary\run.py' all --phase queryclass-local-repeat-01
```

Choose a new phase name for each run. Existing output paths are exclusive. The
historical pre-change baseline is preserved rather than silently recreated against
the fixed runtime. This driver has no genuine-game launch entry point.

Supervisor startup and bounded requests are documented in
[`tools/xrt/supervisor/README.md`](../../../../tools/xrt/supervisor/README.md).
Strict historical x87 and complete WNDPROC equality remain separately FAILED.
There is no new engine-init return, world tick, D3D device, rendered frame or
gameplay claim from these fixtures.
