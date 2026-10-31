/* Entirely owned test program; no game/runtime objects or data linked. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "dev_support.h"
int main(int argc, char **argv) {
    dev_start();
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "ok")) return 0;
    if (!strcmp(argv[1], "endpoint")) dev_finish();
    if (!strcmp(argv[1], "crash")) RaiseException(0xE0123456, EXCEPTION_NONCONTINUABLE, 0, NULL);
    if (!strcmp(argv[1], "tree")) {
        char exe[1024], command[1100]; STARTUPINFOA si = {sizeof si}; PROCESS_INFORMATION pi;
        GetModuleFileNameA(NULL, exe, sizeof exe);
        snprintf(command, sizeof command, "\"%s\" hang", exe);
        if (!CreateProcessA(NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) return 3;
        printf("child=%lu\n", pi.dwProcessId); fflush(stdout);
        CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    }
    Sleep(INFINITE);
    return 4;
}
