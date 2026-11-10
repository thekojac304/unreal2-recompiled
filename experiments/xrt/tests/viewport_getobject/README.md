# Registered-window WM_GETOBJECT boundary

This phase uses a disposable, project-owned registered Unicode window. The same
x86 DLL runs natively and through the production lifter/runtime; a native x64
build measures both zero- and sign-extended OBJID_CLIENT. The real registered
WNDPROC executes and delegates to Windows DefWindowProcW. A test-only wrapper
records actual default-processing results and full-width forwarded arguments.

There are 18 message samples per architecture: SendMessageW, direct Windows
DefWindowProcW, and direct invocation of the actual registered WNDPROC; three
callback modes; and both object-ID representations. Nested WM_GETTEXTLENGTH
reenters the procedure. Test-only assembly measures stack/nonvolatile registers,
x87 control/status/tags/registers and MXCSR; x64 also checks nonvolatile XMMs.
Translation checks every guest callback's ABI/FPU state and byte equality of
the suspended CPU around all 18 calls, with nonempty, nondefault guest x87 state.
Two deterministic requests are injected by a host-only CBT hook inside real
SetFocus. This does not claim reproduction of Windows' spontaneous accessibility
request during the genuine viewport creation.

The ordinary WNDPROC protocol differs from a DLGPROC: it returns the actual
DefWindowProcW LRESULT, while the dialog callback returns FALSE for the dialog
manager to perform default processing. The prior dialog matrix is rerun intact.
The production change admits only a live registered Unicode class whose actual
class procedure matches the explicit translated procedure and module generation.
The original scalar tuple and zero-result restrictions remain in force.

Native real AccessibleObjectFromWindow succeeds with Windows' generic window
provider (role 10, zero children). Acquisition sends an additional
WM_GETOBJECT(0, OBJID_QUERYCLASSNAMEIDX), unlike the earlier dialog oracle.
Translation executes the OBJID_CLIENT callback/default call, then deliberately
rejects that separate request. Successful translated object acquisition is not
claimed, and no provider/cookie/result is fabricated. Other object IDs, upper
bits, ANSI registration, nonzero results, argument mutation, unrelated messages
and arbitrary explicit procedures have focused rejection tests.

`phase.py` preserves consumed evidence, builds fixtures, runs regressions and
serially compiles the client. `audit.py` compares raw measurements. `prepare.py`
only prepares and verifies the owner package. None launches a genuine game.
Outputs are exclusive; choose a fresh phase name before repeating a phase.
Historical unsuccessful fixture versions and their source snapshots are retained.
They document compiler-emitted SSE, unsupported fixture-only imports/sends, and
an overly restrictive hook-count assertion; these did not expand production APIs.

Artifacts: `out/recovery/viewport-getobject-20261028-01`. The fresh owner launcher
retains one session, a 60-second watchdog, no retry, and the permanent execute
stop before guest 0x0696f292. Strict historical x87 and full WNDPROC equality
failures remain separately FAILED. No original installation/save is changed.

Windows references:
[WM_GETOBJECT](https://learn.microsoft.com/en-us/windows/win32/winauto/wm-getobject),
[real default processing and fallback](https://learn.microsoft.com/en-us/windows/win32/winauto/how-wm-getobject-works).
