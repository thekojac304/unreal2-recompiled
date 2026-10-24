# Measured AdjustWindowRect boundary

The same project-owned x86 DLL calls the actual Windows API natively and through
the normal lifter and runtime import table. No border dimensions are encoded.
`build.cmd` refuses an existing output directory; `native` and `translated` allow
the native oracle to be measured before implementing the adapter.

3,888 calls cover both genuine WinDrv OpenWindow styles (`0x10cf0000` and
`0x54000000`, both menu 0 at the call site), ten additional relevant styles,
nine rectangles, four BOOL menu bit patterns, three last-error sentinels and
three placements (aligned, unaligned, spanning two committed writable pages).
Rectangles include negative/nonzero origins, inverted/empty rectangles and signed
integer limits. All four output fields, return value, last-error, surrounding
bytes, stdcall stack cleanup and EBP/EBX/ESI/EDI are compared exactly.

Eight separate native calls intentionally exercise NULL, low, uncommitted,
read-only, no-access, partially committed, guard and wrapping pointers. The
native host catches the resulting access/guard exceptions and records them.
There is no native return value or GetLastError result for an interrupted call;
the untouched exported result/error slots are not treated as API results.
Translated calls stop with explicit unsupported-pointer diagnostics before
reading or writing guest memory or calling USER32. Native guest SEH delivery for
these faults is intentionally unsupported; no synthetic success/error is used.

The adapter marshals four signed 32-bit fields into a local host RECT and copies
all four fields back after the real call. It checks every guest page for readable
and writable protection, rejects guard/no-access/uncommitted/wrapping ranges and
never passes a guest pointer to USER32. It uses actual calling-thread last-error.
The Windows API's existing DPI/style/menu behavior is delegated unchanged; this
fixture does not claim separate DPI modes, AdjustWindowRectEx, multi-row menus,
scrollbar compensation, or hardware/renderer validation.

Microsoft reference: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-adjustwindowrect
