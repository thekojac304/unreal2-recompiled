/* host_api.c - F4 check: what the host SetFilePointer / GetFileSize do to the calling thread's last-error value
 * when the result's low dword is legitimately 0xFFFFFFFF (INVALID_SET_FILE_POINTER / INVALID_FILE_SIZE).
 * Pure Win32 test, no game code. Built for x86 (WOW64 kernel32, what the original UCC.exe calls) and x64 (what the
 * translated runtime's adapters call). Usage: host_api.exe <scratch file path>  (file is sparse, deleted on close) */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>
#include <stdio.h>
#include <stdlib.h>

#define STALE 0x1234u
static int fails;

static void check(const char* what, DWORD got, DWORD want) {
    printf("  %-58s got 0x%08lX want 0x%08lX  %s\n", what, (unsigned long)got, (unsigned long)want,
           got == want ? "ok" : "MISMATCH");
    if (got != want)
        fails++;
}
static void info(const char* what, DWORD got) { printf("  %-58s got 0x%08lX  (info)\n", what, (unsigned long)got); }

static void set_size(HANDLE h, LONGLONG n) {
    LARGE_INTEGER d;
    d.QuadPart = n;
    if (!SetFilePointerEx(h, d, NULL, FILE_BEGIN) || !SetEndOfFile(h)) {
        printf("cannot set size: %lu\n", GetLastError());
        exit(2);
    }
}

int main(int argc, char** argv) {
    HANDLE h;
    DWORD r, e, br, uhi;
    LONG hi;
    if (argc < 2)
        return 2;
    printf("host_api (%d-bit)\n", (int)(sizeof(void*) * 8));
    h = CreateFileA(argv[1], GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        printf("CreateFile failed %lu\n", GetLastError());
        return 2;
    }
    if (!DeviceIoControl(h, FSCTL_SET_SPARSE, NULL, 0, NULL, 0, &br, NULL)) {
        printf("FSCTL_SET_SPARSE failed %lu\n", GetLastError());
        return 2;
    }
    set_size(h, 0xFFFFFFFFLL);

    printf("[1] SetFilePointer(dist=0xFFFFFFFF, &hi=1, FILE_BEGIN) -> 0x1_FFFFFFFF (claim's scenario)\n");
    hi = 1;
    SetLastError(STALE);
    r = SetFilePointer(h, (LONG)0xFFFFFFFFu, &hi, FILE_BEGIN);
    e = GetLastError();
    check("return", r, 0xFFFFFFFFu);
    check("*lpDistanceToMoveHigh", (DWORD)hi, 1);
    check("GetLastError (stale 0x1234 set before)", e, NO_ERROR);

    printf("[2] SetFilePointer(0, NULL, FILE_END) on size 0xFFFFFFFF (shape of UCC call site 0x402805)\n");
    SetLastError(STALE);
    r = SetFilePointer(h, 0, NULL, FILE_END);
    e = GetLastError();
    check("return", r, 0xFFFFFFFFu);
    check("GetLastError (stale 0x1234 set before)", e, NO_ERROR);

    printf("[3] SetFilePointer(0, &hi=0, FILE_END) on size 0xFFFFFFFF\n");
    hi = 0;
    SetLastError(STALE);
    r = SetFilePointer(h, 0, &hi, FILE_END);
    e = GetLastError();
    check("return", r, 0xFFFFFFFFu);
    check("*lpDistanceToMoveHigh", (DWORD)hi, 0);
    check("GetLastError (stale 0x1234 set before)", e, NO_ERROR);

    printf("[4] GetFileSize(NULL) and GetFileSize(&hi) on size 0xFFFFFFFF\n");
    SetLastError(STALE);
    r = GetFileSize(h, NULL);
    e = GetLastError();
    check("GetFileSize(h, NULL) return", r, 0xFFFFFFFFu);
    check("GetLastError (stale 0x1234 set before)", e, NO_ERROR);
    uhi = 0xAAAAAAAAu;
    SetLastError(STALE);
    r = GetFileSize(h, &uhi);
    e = GetLastError();
    check("GetFileSize(h, &hi) return", r, 0xFFFFFFFFu);
    check("*lpFileSizeHigh", uhi, 0);
    check("GetLastError (stale 0x1234 set before)", e, NO_ERROR);

    printf("[5] size 0x1_FFFFFFFF: GetFileSize(&hi) (claim's GetFileSize scenario)\n");
    set_size(h, 0x1FFFFFFFFLL);
    uhi = 0;
    SetLastError(STALE);
    r = GetFileSize(h, &uhi);
    e = GetLastError();
    check("return", r, 0xFFFFFFFFu);
    check("*lpFileSizeHigh", uhi, 1);
    check("GetLastError (stale 0x1234 set before)", e, NO_ERROR);

    printf("[6] real failures still report an error\n");
    SetLastError(STALE);
    r = SetFilePointer(h, -1, NULL, FILE_BEGIN);
    e = GetLastError();
    check("SetFilePointer(-1, NULL, FILE_BEGIN) return", r, 0xFFFFFFFFu);
    check("GetLastError", e, ERROR_NEGATIVE_SEEK);
    SetLastError(STALE);
    r = SetFilePointer(h, 0, NULL, FILE_END);      /* size 0x1_FFFFFFFF does not fit with lpDistanceToMoveHigh NULL */
    e = GetLastError();
    info("SetFilePointer(0, NULL, FILE_END), size 0x1_FFFFFFFF: return", r);
    info("  GetLastError", e);

    printf("[7] ordinary successes (return != 0xFFFFFFFF), informational\n");
    set_size(h, 64);
    SetLastError(STALE);
    r = SetFilePointer(h, 16, NULL, FILE_BEGIN);
    e = GetLastError();
    check("SetFilePointer(16, NULL, FILE_BEGIN) return", r, 16);
    info("  GetLastError after (stale 0x1234 set before)", e);
    SetLastError(STALE);
    r = GetFileSize(h, NULL);
    e = GetLastError();
    check("GetFileSize(h, NULL) return", r, 64);
    info("  GetLastError after (stale 0x1234 set before)", e);

    CloseHandle(h);
    printf("%s (%d mismatches)\n", fails ? "FAIL" : "PASS", fails);
    return fails ? 1 : 0;
}
