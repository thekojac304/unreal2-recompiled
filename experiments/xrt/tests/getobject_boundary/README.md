# Measured WM_GETOBJECT startup-dialog boundary

The project-owned x86 DLL runs natively and through the real lifter/runtime.
The x64 native DLL measures both `0x00000000fffffffc` and
`0xfffffffffffffffc` representations of OBJID_CLIENT. Its callback always
executes and returns FALSE in positive cases, matching the genuine startup
dialog procedure's return semantics.

The native hosts exercise SendMessageW, DefDlgProcW and DefWindowProcW, preserving
the real Windows dialog manager. Three callback modes cover unchanged last-error,
a nested WM_GETTEXTLENGTH request, and a callback-written error. Three real
AccessibleObjectFromWindow calls inspect the returned IAccessible role, state,
child count and HWND, then release it. No accessible object or result is supplied
by the fixture or compatibility adapter. Accessibility names would require the
separate, still-guarded WM_GETTEXT path and are outside this fixture's acceptance.

Native x86 and translated callbacks check the stdcall stack and callee-saved
registers. The translated test-only wrapper also checks x87 registers, control,
status and stack position around every actual guest callback. It does not add
test entry points to production. Guard tests retain unsupported IDs, wParam,
unmeasured upper object-ID bits and nonzero guest dialog results.

`observer_evidence.py` is the preserved diagnosis correction integrated into a
fresh harness. It binds the exact output directory to each instance and captures
fatal arguments and guest CPU before CreateDevice. Guest-stack reads use the
runtime TEB's actual stack bounds. `debugger_test.py` qualifies this with two
non-game live early fatals and a terminate-before-instruction hardware-stop test.
The original six observer unit tests and their assertions are retained; one
additional test covers a stack-top boundary.

Artifacts for this completed phase are under
`out/recovery/getobject-recovery-20261028-01`. Historical unsuccessful fixture
attempts stay there with their diagnostics. Scripts use exclusive output paths;
select new phase/build directories before reproducing the characterization.
`phase.py` provides preservation, native/translated builds, GUI regressions and
serial client compilation. `prepare.py` only prepares and verifies the owner
package. It does not execute a genuine client.

The prepared owner command uses a fresh sandbox, one session, a 60-second
watchdog and a permanent execute stop before guest `0x0696f292`. The genuine
session consumed on October 28 is never reused. Strict historical renderer x87
and complete WNDPROC state-equality failures remain separate and unwaived.

Windows semantics: [WM_GETOBJECT](https://learn.microsoft.com/en-us/windows/win32/winauto/wm-getobject),
[accessibility fallback](https://learn.microsoft.com/en-us/windows/win32/winauto/how-wm-getobject-works),
[dialog default processing](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-defdlgprocw).
