/* ref_wtoi.c (x86) - calls the real msvcr70.dll _wtoi (LoadLibrary of a read-only sandbox copy).
 *   ref_wtoi.exe <path to msvcr70.dll>   -> one line per case: index, length, result (signed decimal) */
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include "cases.h"
typedef int(__cdecl* WtoiFn)(const wchar_t*);
int main(int argc, char** argv) {
    HMODULE m;
    WtoiFn f;
    int i;
    if (argc != 2)
        return 2;
    m = LoadLibraryA(argv[1]);
    if (!m || !(f = (WtoiFn)GetProcAddress(m, "_wtoi"))) {
        fprintf(stderr, "cannot load _wtoi from %s (%lu)\n", argv[1], GetLastError());
        return 2;
    }
    for (i = 0; i < NCASES; i++)
        printf("%2d len=%2u r=%d\n", i, (unsigned)wcslen(cases[i]), f(cases[i]));
    return 0;
}
