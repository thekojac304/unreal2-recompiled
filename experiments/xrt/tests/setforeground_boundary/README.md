# SetForegroundWindow

Encountered in the genuine client at WinDrv.dll+0x4a58 with owned viewport HWND token 0x126c, style 0x10cf0000. The same x86 DLL executes natively and through xlift against real USER32. Three last-error seeds cover the exact owned visible top-level window, repeated calls, transitions and NULL, with ESP and EBP/EBX/ESI/EDI checks. Cross-thread and unknown nonzero tokens remain guarded. No success is synthesized and no input is injected.

Primary contract: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow
