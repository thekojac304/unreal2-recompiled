/* Developer diagnostics only. Never linked into the strict candidate. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
#include <stdio.h>
#include <stdlib.h>
#include "dev_support.h"
static volatile LONG dumped;

void dev_dump(EXCEPTION_POINTERS *exception, const char *reason) {
    char path[1024];
    const char *root = getenv("XRT_DEV_OUTPUT");
    MINIDUMP_EXCEPTION_INFORMATION info;
    HANDLE file;
    BOOL ok;
    if (!root || InterlockedExchange(&dumped, 1)) return;
    snprintf(path, sizeof path, "%s\\crash.dmp", root);
    file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "dev: dump open failed: %lu\n", GetLastError()); return;
    }
    info.ThreadId = GetCurrentThreadId();
    info.ExceptionPointers = exception;
    info.ClientPointers = FALSE;
    ok = MiniDumpWriteDump(GetCurrentProcess(), GetCurrentProcessId(), file,
        MiniDumpWithIndirectlyReferencedMemory | MiniDumpWithThreadInfo,
        exception ? &info : NULL, NULL, NULL);
    fprintf(stderr, "dev: %s dump %s (error %lu)\n", reason, ok ? "saved" : "FAILED", ok ? 0 : GetLastError());
    CloseHandle(file);
    fflush(stderr);
}
static LONG WINAPI unhandled(EXCEPTION_POINTERS *exception) {
    dev_dump(exception, "unhandled exception");
    return EXCEPTION_EXECUTE_HANDLER;
}
void dev_start(void) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    SetUnhandledExceptionFilter(unhandled);
    if (getenv("XRT_DEV_ATTACH")) {
        fprintf(stderr, "dev: attach Visual Studio/WinDbg to PID %lu; timeout is still active\n", GetCurrentProcessId());
        fflush(stderr);
        while (!IsDebuggerPresent()) Sleep(50);
        DebugBreak();
    }
}
__declspec(noreturn) void dev_finish(void) {
    fprintf(stderr, "dev: INIT_RETURN endpoint reached; stopping before guest 0x1090ED5C\n");
    fflush(NULL);
    /* A distinct controlled-stop status, never a claim of normal engine exit. */
    ExitProcess(10);
}

#ifndef XRT_DEV_FIXTURE
#include "xrt_internal.h"
#include "monitor.h"
__declspec(noinline) void xrt_dev_init_return(CPU *c) {
    xrt_log("DEV Init returned: caller=1090ed59 return=%08x esp=%08x", c->rv, c->r[ESP]);
    xrt_event("dev_init_return", "\"guest_next\": \"0x1090ed5c\"");
    xm_checkpoint(c, "dev.Init.return");
    xrt_report_write(10, "developer Init-return stop; main loop not entered");
    /* We are still inside outer guest invocation scopes. CHECKPOINT flushes;
       CLOSE would falsely require an orderly return from the whole process. */
    dev_finish();
}
#endif
