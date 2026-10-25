# Measured SetCapture boundary

`build.cmd` creates a fresh native x86 oracle DLL and driver, lifts the same DLL,
builds the actual GUI runtime and compares identities, callbacks, last-error and
the x86 stdcall ESP/EBP/EBX/ESI/EDI contract. `native` and `translated` arguments
split those stages. A second invocation needs a new output name; old evidence
must remain intact.

55 supported paired calls cover NULL with/without capture, same HWND, A/B/A,
three last-error seeds, invalid/-1/destroyed handles, creation-time capture,
previously unrepresented native stock HWNDs, and reentrant WM_CAPTURECHANGED.
GetCapture observations and ReleaseCapture interactions are native test-driver
operations; no guest GetCapture or ReleaseCapture adapter is added. The callback
record includes the actual scalar wParam (zero in the native corpus). Hidden windows only, no
input injection or attached queues.

On this installation SetCapture(NULL) returns the previous HWND, clears capture
and preserves last-error. SetCapture(same HWND) sends WM_CAPTURECHANGED with
that HWND in lParam. Invalid/destroyed HWNDs return NULL/error 1400 without
changing capture. Reentrancy can change final capture independently of the outer
return. All these results come from real USER32, with typed guest HWND identities
in API returns and callback lParams. Unknown nonzero handles use a verified
invalid host sentinel rather than casting guest bits to native HWNDs.

A native worker owns capture on its own queue; three unattached foreign-window
attempts preserve both queues and the seeded last-error. Translation stops at
cross-thread capture because attached queues/callback transfer are outside this
measurement. Wrong-type guest tokens also stop explicitly. Borrowed HWND tokens
do not grant lifetime or ownership. The first development comparison retained
an expired fixture identity slot; the corrected fresh `_02` fixture passes.

Primary contracts: [SetCapture](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setcapture),
[ReleaseCapture](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-releasecapture),
[WM_CAPTURECHANGED](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-capturechanged).
