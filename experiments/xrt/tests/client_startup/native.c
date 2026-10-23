/* Project-owned native x86 probe, deliberately linked at the shipped client's nondefault base. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
int main(int argc, char** argv) {
    char a[1024], b[1024];
    HMODULE self = GetModuleHandleA(NULL);
    DWORD n = GetModuleFileNameA(NULL, a, sizeof a);
    DWORD m = GetModuleFileNameA(self, b, sizeof b);
    unsigned long peb_base;
    __asm {
        mov eax, fs:[30h]
        mov eax, [eax+8]
        mov peb_base, eax
    }
    if ((unsigned long)self != 0x10900000u || peb_base != (unsigned long)self || !n || n != m || strcmp(a,b)) return 1;
    if (argc == 2) {
        HMODULE crt = LoadLibraryA(argv[1]);
        char** command_line = crt ? (char**)GetProcAddress(crt, "_acmdln") : NULL;
        if (!command_line || !*command_line || strcmp(*command_line, GetCommandLineA())) return 1;
    } else return 2;
    puts("PASS native main module, PEB and msvcr70 _acmdln");
    return 0;
}
