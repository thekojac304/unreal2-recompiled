/* ref_argv.c (x86) - F2 reference: the real msvcr70.dll __getmainargs on this process's own command line.
 *
 * msvcr70.dll is loaded from the sandbox copy (path in F2_MSVCR70). Its DLL init captures GetCommandLineA()
 * into _acmdln and builds its MBCS lead-byte table from the process ANSI code page, so the output reflects
 * exactly what an original guest would get in a process with this ACP. Built twice: plain (system ACP) and
 * with acp932.manifest (activeCodePage ja-JP, a per-process ACP of 932; no system setting is changed).
 * Prints only ASCII: the ACP, msvcr70's _getmbcp(), the raw command line bytes and each argv[i], in hex. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { int newmode; } StartupInfo;
typedef int(__cdecl* GetMainArgs)(int*, char***, char***, int, StartupInfo*);
typedef int(__cdecl* IntVoid)(void);

static void hex(const char* s) {
    if (!*s)
        printf("-");
    while (*s)
        printf("%02X", (unsigned char)*s++);
}

int main(void) {
    const char* path = getenv("F2_MSVCR70");
    HMODULE m;
    GetMainArgs gma;
    IntVoid getmbcp;
    char*** pacmdln;
    int argc = -1, i, rc;
    char **argv = NULL, **envp = NULL;
    StartupInfo si = {0};
    if (!path)
        return 2;
    m = LoadLibraryExA(path, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!m)
        return 3;
    gma = (GetMainArgs)GetProcAddress(m, "__getmainargs");
    getmbcp = (IntVoid)GetProcAddress(m, "_getmbcp");
    pacmdln = (char***)GetProcAddress(m, "_acmdln");
    if (!gma || !getmbcp || !pacmdln)
        return 4;
    printf("ACP %u\nmbcp %d\ncmd ", GetACP(), getmbcp());
    hex(*(char**)pacmdln);
    printf("\n");
    rc = gma(&argc, &argv, &envp, 0, &si);
    printf("rc %d\nargc %d\n", rc, argc);
    for (i = 0; i < argc; i++) {
        printf("argv ");
        hex(argv[i]);
        printf("\n");
    }
    return 0;
}
