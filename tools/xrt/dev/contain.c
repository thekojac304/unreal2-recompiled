/* Independent launcher: suspended creation, kill-on-close Job, wall deadline.
   Does not attach a debugger or import the strict supervisor. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
static volatile LONG cancelled;
static BOOL WINAPI control(DWORD event) {
    (void)event; InterlockedExchange(&cancelled, 1); return TRUE;
}
static BOOL interactive_desktop(void) {
    wchar_t current[128], input[128]; DWORD needed;
    HDESK desktop = OpenInputDesktop(0, FALSE, DESKTOP_READOBJECTS);
    BOOL ok = desktop &&
        GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()), UOI_NAME, current, sizeof current, &needed) &&
        GetUserObjectInformationW(desktop, UOI_NAME, input, sizeof input, &needed) &&
        !_wcsicmp(current, L"Default") && !_wcsicmp(current, input);
    if (desktop) CloseDesktop(desktop);
    return ok;
}
int wmain(int argc, wchar_t **argv) {
    HANDLE job = NULL, log = INVALID_HANDLE_VALUE, exclusive = NULL;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting = {0};
    STARTUPINFOW si = {sizeof si}; PROCESS_INFORMATION pi = {0};
    SECURITY_ATTRIBUTES sa = {sizeof sa, NULL, TRUE};
    STICKYKEYS keys = {sizeof keys}; RECT clip;
    BOOL have_keys = FALSE, have_clip = FALSE, launched = FALSE;
    DWORD code = 125, wait, ms, remaining = 0;
    ULONGLONG deadline;
    wchar_t logfile[1024], result[1024]; FILE *f;
    if (argc != 5) { fwprintf(stderr, L"contain TIMEOUT_SECONDS OUTPUT_DIR CWD COMMAND_LINE\n"); return 125; }
    ms = (DWORD)_wtoi(argv[1]);
    if (ms < 1 || ms > 360) return 125;
    ms *= 1000;
    SetConsoleCtrlHandler(control, TRUE);
    if (_wgetenv(L"XRT_DEV_GAME") && !interactive_desktop()) {
        fprintf(stderr, "dev: run game initialization from the owner's active Default desktop\n");
        goto done;
    }
    if (_wgetenv(L"XRT_DEV_GAME")) {
        exclusive = CreateMutexW(NULL, FALSE, L"Local\\Unreal2DeveloperInit");
        if (!exclusive || GetLastError() == ERROR_ALREADY_EXISTS) {
            fprintf(stderr, "dev: another developer initialization run is active\n"); goto done;
        }
    }
    job = CreateJobObjectW(NULL, NULL);
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits)) goto done;
    swprintf(logfile, 1024, L"%ls\\console.txt", argv[2]);
    log = CreateFileW(logfile, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (log == INVALID_HANDLE_VALUE) goto done;
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = si.hStdError = log;
    si.hStdInput = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
    if (si.hStdInput == INVALID_HANDLE_VALUE) goto done;
    have_keys = SystemParametersInfoW(SPI_GETSTICKYKEYS, sizeof keys, &keys, 0);
    have_clip = GetClipCursor(&clip);
    if (!have_keys || !have_clip) goto done;
    if (!CreateProcessW(NULL, argv[4], NULL, NULL, TRUE, CREATE_SUSPENDED | CREATE_NO_WINDOW,
                        NULL, argv[3], &si, &pi)) goto done;
    launched = TRUE;
    if (!AssignProcessToJobObject(job, pi.hProcess)) goto done;
    deadline = GetTickCount64() + ms;
    if (ResumeThread(pi.hThread) == (DWORD)-1) goto done;
    printf("dev: contained PID %lu; deadline %lu seconds\n", pi.dwProcessId, ms / 1000); fflush(stdout);
    for (;;) {
        wait = WaitForSingleObject(pi.hProcess, 50);
        if (wait == WAIT_OBJECT_0) { if (!GetExitCodeProcess(pi.hProcess, &code)) code = 125; break; }
        if (wait == WAIT_FAILED) { code = 125; break; }
        if (cancelled) { code = 130; break; }
        if (GetTickCount64() >= deadline) { code = 124; break; }
    }
done:
    if (code == 125) fprintf(stderr, "dev: containment/setup failure: Win32 %lu\n", GetLastError());
    /* Also kill descendants after the main process exits successfully. */
    if (job) TerminateJobObject(job, code);
    if (launched) {
        /* Covers assignment/resume failure before the process joined the Job. */
        TerminateProcess(pi.hProcess, code);
        WaitForSingleObject(pi.hProcess, 5000);
        CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    }
    if (job) {
        ULONGLONG until = GetTickCount64() + 5000;
        do {
            if (!QueryInformationJobObject(job, JobObjectBasicAccountingInformation, &accounting, sizeof accounting, NULL)) { remaining = MAXDWORD; break; }
            remaining = accounting.ActiveProcesses;
            if (!remaining) break;
            Sleep(20);
        } while (GetTickCount64() < until);
        CloseHandle(job);
    }
    if (remaining) code = 125;
    if (have_keys && !SystemParametersInfoW(SPI_SETSTICKYKEYS, sizeof keys, &keys, 0)) code = 125;
    if (have_clip && !ClipCursor(&clip)) code = 125;
    if (log != INVALID_HANDLE_VALUE) CloseHandle(log);
    if (si.hStdInput && si.hStdInput != INVALID_HANDLE_VALUE) CloseHandle(si.hStdInput);
    if (exclusive) CloseHandle(exclusive);
    swprintf(result, 1024, L"%ls\\process.json", argv[2]);
    f = _wfopen(result, L"w");
    if (!f) return 125;
    fprintf(f, "{\"exit_code\":%lu,\"pid\":%lu,\"remaining_processes\":%lu,\"launched\":%s}\n", code, pi.dwProcessId, remaining, launched ? "true" : "false");
    fclose(f);
    return (int)code;
}
