# GetForegroundWindow

The client encountered this zero-argument USER32 query at WinDrv.dll+0x4a12
inside TryRenderDevice, after the viewport CreateWindowExW return. The adapter
calls real USER32 and maps its actual HWND (including NULL) to a borrowed typed
window token. It does not transfer focus, capture, callbacks or ownership.

Nine native x86/translated calls compare the actual foreground HWND, three
last-error seeds, stdcall ESP and EBP/EBX/ESI/EDI. USER32 returned NULL in this
restricted desktop context. The fixture includes identity reuse and owner checks
for non-NULL observations, but that branch did not execute and is not claimed as
new non-NULL query coverage. Non-NULL mapping uses the existing window_token
helper, separately exercised with borrowed HWNDs by the focus/capture suites. This
fixture does not change the foreground window or inject input. A spontaneous
foreground change during a sample is rejected rather than normalized away.

Primary contract: [GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow).
