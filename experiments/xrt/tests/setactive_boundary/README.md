# SetActiveWindow

Encountered at WinDrv.dll+0x4a89 with owned viewport token 0x126c. Same x86 DLL runs natively and through xlift. Three error seeds cover visible owned windows, repeated activation, transitions and NULL, with ESP and EBP/EBX/ESI/EDI checks. A native stock window exercises borrowed previous-HWND identity and token reuse. Unknown, wrong-type and cross-thread tokens stay guarded.

Primary contract: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setactivewindow
