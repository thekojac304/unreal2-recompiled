# ClipCursor(NULL)

The genuine client encountered NULL at WinDrv.dll+0x418c, return 0x11104192,
after the paired SetCapture(NULL) return. Only this NULL RECT path is adapted.

The same x86 DLL runs natively and translated. Six calls cover three last-error
seeds with an already released clip and with the original clip reapplied.
Real GetClipCursor observations, return values, last-error and x86 stdcall
ESP/EBP/EBX/ESI/EDI agree. Both drivers restore and verify the original clip.
A valid non-NULL RECT is measured natively and explicitly unsupported translated.
GetClipCursor and setup/restore calls belong only to the native test drivers.

GetCursorPos is denied (error 5) in this environment; no cursor movement or
restricted-region test is attempted. The original clip was the full desktop.
The earlier native-only fixture attempts are retained: one stopped on that
GetCursorPos restriction, and another exposed DPI-scaled screen metrics differing
from GetClipCursor coordinates. The corrected fixture compares actual RECTs.

Primary contract: [ClipCursor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clipcursor).
