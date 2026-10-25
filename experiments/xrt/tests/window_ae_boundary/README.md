# Observed window callback 0x00ae

The genuine viewport creation stopped on message 0xae, wParam=8, lParam=0,
after SetFocus returned. Only this exact scalar tuple is accepted. It reaches
the guest window procedure and real USER32 default procedure through the existing
validated callback frame. No undocumented pointer layout or drawing routine is
implemented, and no other numeric message/argument combination is inferred.

`build.cmd native` runs the x86 DLL through USER32; `translated` lifts exactly
that DLL and compares. 24 outer calls produce 24 callback returns across A/W
classes, hidden popup/overlapped windows, three last-error seeds and repeated sends. The host driver delivers the real
message under the active callback CPU; no guest SendMessage extension is added.
Callback order, actual arguments, real default-procedure results, errors,
Default-procedure stdcall ESP and EBP/EBX/ESI/EDI match. Nonobserved wParam and non-NULL lParam
cases stop explicitly before crossing into guest code. Native negative pointer
messages are deliberately not executed. This is a measured scalar bridge;
neither a general theme protocol nor rendering implementation is claimed.

The first fixture stopped at the existing guest SendMessage message guard. Its
corrected successor uses native delivery, matching the actual USER32 callback
origin, and leaves that unencountered guest-send path guarded.
