/* adapter.c - F4 check: drives the runtime's own hle_SetFilePointer / hle_GetFileSize adapters (runtime/hle_kernel32.c,
 * compiled unchanged and linked into this test) through the xrt_hle_kernel32 table with a guest stack, guest TEB and
 * guest out-parameters, and checks the guest-visible result: EAX, out-params, stdcall cleanup and the guest TEB
 * last-error slot. Host last-error and the guest slot are both preloaded with stale values before every call.
 * Usage: adapter.exe <scratch file path>  (x64; file is sparse, deleted on close) */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>
#include <stdlib.h>
#include "xrt_internal.h"

/* ---- minimal stand-ins for the runtime pieces hle_kernel32.c links against */
uint8_t* xrt_g;
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a;
const char* xrt_report_path;
volatile long xrt_dying, xrt_exiting;
__declspec(thread) XrtThread* xrt_cur;
/* same definition as runtime/xrt_thread.c: the guest last-error value lives at TEB+0x34 */
void xrt_set_last_error(CPU* c, uint32_t e) { wr32(c->fs_base + 0x34, e); }
uint32_t xrt_get_last_error(CPU* c) { return rd32(c->fs_base + 0x34); }
void xrt_log(const char* fmt, ...) { (void)fmt; }
void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list ap;
    (void)c;
    va_start(ap, fmt);
    printf("xrt_fatal: ");
    vprintf(fmt, ap);
    printf("\n");
    va_end(ap);
    exit(code);
}
static void unexpected(const char* what) {
    printf("unexpected runtime call: %s\n", what);
    exit(3);
}
void xrt_baton_acquire(void) { unexpected("xrt_baton_acquire"); }
void xrt_baton_release(void) { unexpected("xrt_baton_release"); }
void xrt_describe(char* out, size_t n, uint32_t va) { (void)out; (void)n; (void)va; unexpected("xrt_describe"); }
void xrt_heap_stats(uint64_t* a, uint64_t* f, uint64_t* b, uint32_t* hw) {
    (void)a; (void)f; (void)b; (void)hw;
    unexpected("xrt_heap_stats");
}
XrtModule* xrt_module_by_name(const char* name) { (void)name; unexpected("xrt_module_by_name"); return NULL; }
int xrt_module_count(void) { unexpected("xrt_module_count"); return 0; }
XrtModule* xrt_module_get(int i) { (void)i; unexpected("xrt_module_get"); return NULL; }
uint32_t xrt_module_export(XrtModule* m, const char* name, uint32_t ordinal) {
    (void)m; (void)name; (void)ordinal;
    unexpected("xrt_module_export");
    return 0;
}
uint32_t xrt_thread_create(CPU* c, uint32_t s, uint32_t st, uint32_t p, uint32_t* tid) {
    (void)c; (void)s; (void)st; (void)p; (void)tid;
    unexpected("xrt_thread_create");
    return 0;
}
void xrt_thread_exit(CPU* c, uint32_t code) { (void)c; (void)code; unexpected("xrt_thread_exit"); }
void xrt_process_exit(CPU* c, uint32_t code) { (void)c; (void)code; unexpected("xrt_process_exit"); }
void xrt_stdout_flush(void) { unexpected("xrt_stdout_flush"); }

/* ---- guest layout used by the test */
#define G_TEB 0x1000u
#define G_OUT 0x2000u        /* guest DWORD/LONG out-parameter */
#define G_STACK_TOP 0x10000u
#define G_RET 0x00ABCDE0u    /* fake guest return address */
#define STALE_HOST 0x1234u
#define STALE_GUEST 0x5555u

static CPU cpu;
static int fails;

static void check(const char* what, uint32_t got, uint32_t want) {
    printf("  %-58s got 0x%08X want 0x%08X  %s\n", what, got, want, got == want ? "ok" : "MISMATCH");
    if (got != want)
        fails++;
}
static void info(const char* what, uint32_t got) { printf("  %-58s got 0x%08X  (info)\n", what, got); }

static XrtFn adapter(const char* name) {
    const XrtHle* e;
    for (e = xrt_hle_kernel32; e->name; e++)
        if (!strcmp(e->name, name))
            return e->fn;
    printf("no adapter %s\n", name);
    exit(2);
}

/* guest stdcall: push args right to left, push return address, enter the adapter; returns guest EAX */
static uint32_t call_std(const char* name, int n, const uint32_t* args) {
    CPU* c = &cpu;
    XrtFn fn = adapter(name);
    int i;
    c->r[ESP] = G_STACK_TOP;
    for (i = n - 1; i >= 0; i--)
        push32(c, args[i]);
    push32(c, G_RET);
    xrt_set_last_error(c, STALE_GUEST);
    SetLastError(STALE_HOST);
    fn(c);
    if (c->rv != G_RET || c->r[ESP] != G_STACK_TOP) {
        printf("  stdcall frame wrong: rv %08X esp %08X\n", c->rv, c->r[ESP]);
        fails++;
    }
    return c->r[EAX];
}

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
    DWORD br;
    uint32_t gh, r;
    if (argc < 2)
        return 2;
    xrt_g = (uint8_t*)VirtualAlloc(NULL, 0x20000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    cpu.fs_base = G_TEB;
    h = CreateFileA(argv[1], GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (h == INVALID_HANDLE_VALUE || !DeviceIoControl(h, FSCTL_SET_SPARSE, NULL, 0, NULL, 0, &br, NULL)) {
        printf("setup failed %lu\n", GetLastError());
        return 2;
    }
    set_size(h, 0xFFFFFFFFLL);
    gh = xrt_handle_new(XH_FILE, h);
    printf("adapter test (guest handle 0x%X)\n", gh);

    printf("[1] SetFilePointer(dist=0xFFFFFFFF, &hi=1, FILE_BEGIN) -> 0x1_FFFFFFFF (claim's scenario)\n");
    wr32(G_OUT, 1);
    r = call_std("SetFilePointer", 4, (uint32_t[]){gh, 0xFFFFFFFFu, G_OUT, FILE_BEGIN});
    check("EAX", r, 0xFFFFFFFFu);
    check("guest *lpDistanceToMoveHigh", rd32(G_OUT), 1);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), NO_ERROR);

    printf("[2] SetFilePointer(0, NULL, FILE_END), size 0xFFFFFFFF (shape of UCC call site 0x402805)\n");
    r = call_std("SetFilePointer", 4, (uint32_t[]){gh, 0, 0, FILE_END});
    check("EAX", r, 0xFFFFFFFFu);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), NO_ERROR);

    printf("[3] GetFileSize(NULL) and GetFileSize(&hi), size 0xFFFFFFFF\n");
    r = call_std("GetFileSize", 2, (uint32_t[]){gh, 0});
    check("EAX", r, 0xFFFFFFFFu);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), NO_ERROR);
    wr32(G_OUT, 0xAAAAAAAAu);
    r = call_std("GetFileSize", 2, (uint32_t[]){gh, G_OUT});
    check("EAX", r, 0xFFFFFFFFu);
    check("guest *lpFileSizeHigh", rd32(G_OUT), 0);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), NO_ERROR);

    printf("[4] size 0x1_FFFFFFFF: GetFileSize(&hi) (claim's GetFileSize scenario)\n");
    set_size(h, 0x1FFFFFFFFLL);
    wr32(G_OUT, 0);
    r = call_std("GetFileSize", 2, (uint32_t[]){gh, G_OUT});
    check("EAX", r, 0xFFFFFFFFu);
    check("guest *lpFileSizeHigh", rd32(G_OUT), 1);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), NO_ERROR);

    printf("[5] real failures still reach the guest\n");
    r = call_std("SetFilePointer", 4, (uint32_t[]){gh, 0xFFFFFFFFu, 0, FILE_BEGIN});
    check("SetFilePointer(-1, NULL, FILE_BEGIN) EAX", r, 0xFFFFFFFFu);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), ERROR_NEGATIVE_SEEK);
    r = call_std("SetFilePointer", 4, (uint32_t[]){0x7777u, 0, 0, FILE_BEGIN});
    check("SetFilePointer(bad guest handle) EAX", r, 0xFFFFFFFFu);
    check("guest last error (TEB+0x34)", xrt_get_last_error(&cpu), ERROR_INVALID_HANDLE);

    printf("[6] ordinary successes (return != 0xFFFFFFFF), informational\n");
    set_size(h, 64);
    r = call_std("SetFilePointer", 4, (uint32_t[]){gh, 16, 0, FILE_BEGIN});
    check("SetFilePointer(16, NULL, FILE_BEGIN) EAX", r, 16);
    info("  guest last error after (stale 0x5555 preloaded)", xrt_get_last_error(&cpu));
    r = call_std("GetFileSize", 2, (uint32_t[]){gh, 0});
    check("GetFileSize(NULL) EAX", r, 64);
    info("  guest last error after (stale 0x5555 preloaded)", xrt_get_last_error(&cpu));

    xrt_handle_free(gh);
    CloseHandle(h);
    printf("%s (%d mismatches)\n", fails ? "FAIL" : "PASS", fails);
    return fails ? 1 : 0;
}
