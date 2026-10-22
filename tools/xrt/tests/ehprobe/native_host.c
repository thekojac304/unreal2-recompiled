/* native_host.c (x86) - runs probe functions of ehprobe.dll natively; msvcr70.dll is loaded from the sandbox copy of
 * the game's System directory (SetDllDirectory), so the original __CxxFrameHandler handles the exceptions.
 *   native_host.exe <msvcr70 directory> <ehprobe.dll> <probe> [<probe> ...]
 * Output per probe: "<probe> returned <n> log <v> <v> ..." (the whole log, destructors after the return included). */
#include <windows.h>
#include <stdio.h>

int main(int argc, char** argv) {
    HMODULE m;
    int *log, *n, i;
    if (argc < 4)
        return 2;
    /* an unhandled exception (negative probe) must end the process, not wait in an error-reporting dialog */
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    SetDllDirectoryA(argv[1]);
    m = LoadLibraryA(argv[2]);
    if (!m) {
        printf("cannot load %s (%lu)\n", argv[2], GetLastError());
        return 2;
    }
    log = (int*)GetProcAddress(m, "probe_log");
    n = (int*)GetProcAddress(m, "probe_log_n");
    for (i = 3; i < argc; i++) {
        int (*f)(void) = (int (*)(void))GetProcAddress(m, argv[i]);
        int r, k;
        if (!f || !log || !n) {
            printf("%s missing\n", argv[i]);
            return 2;
        }
        __try {
            r = f();
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            /* the probe's own frames had no handler: the exception escaped into this host */
            printf("%s unhandled exception %08lx escaped the probe\n", argv[i], GetExceptionCode());
            fflush(stdout);
            return 3;
        }
        printf("%s returned %d log", argv[i], r);
        for (k = 0; k < *n; k++)
            printf(" %d", log[k]);
        printf("\n");
        fflush(stdout);
    }
    return 0;
}
