/* Focused regression for the first real client CRT startup failures.
 * Module registry is a fixture; every unrelated dependency fails explicitly. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>
#include <stdlib.h>
#include "xrt_internal.h"

static XrtModule main_module;

/* ---- minimal stand-ins for the runtime pieces hle_kernel32.c links against */
uint8_t* xrt_g;
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a, xrt_cmdline_w;
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
static XRT_NORETURN void unexpected(const char* what) {
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
int xrt_module_count(void) { return 1; }
XrtModule* xrt_module_get(int i) { return i == 0 ? &main_module : NULL; }
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
    for (e = xrt_hle_misc; e->name; e++)
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


int main(void) {
    uint32_t r;
    DWORD native_error;
    xrt_g = (uint8_t*)VirtualAlloc(NULL, 0x20000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!xrt_g) return 2;
    cpu.fs_base = G_TEB;
    main_module.base = 0x10900000u;
    strcpy(main_module.name, "Unreal2.exe");
    strcpy(main_module.path, "E:\\sandbox\\System\\Unreal2.exe");
    check("GetModuleHandleA(NULL), client base", call_std("GetModuleHandleA",1,(uint32_t[]){0}),0x10900000u);
    r=call_std("GetModuleFileNameA",3,(uint32_t[]){0,G_OUT,256});
    check("NULL module filename length",r,(uint32_t)strlen(main_module.path));
    check("NULL module resolves actual executable",strcmp((char*)G2H(G_OUT),main_module.path),0);
    main_module.base=0x00400000u;
    check("GetModuleHandleA(NULL), UCC base", call_std("GetModuleHandleA",1,(uint32_t[]){0}),0x00400000u);
    xrt_cmdline_w=0x3000u;
    memcpy(G2H(xrt_cmdline_w), L"guest.exe \"two words\" \x65e5\x672c", sizeof L"guest.exe \"two words\" \x65e5\x672c");
    r=call_std("GetCommandLineW",0,NULL);
    check("wide command line pointer",r,xrt_cmdline_w);
    check("wide command line contents",wcscmp((WCHAR*)G2H(r),L"guest.exe \"two words\" \x65e5\x672c"),0);
    strcpy((char*)G2H(0x4000u),"XRT_never_registered_596423b5_test_class");
    SetLastError(STALE_GUEST);
    if (FindWindowExA(NULL,NULL,(char*)G2H(0x4000u),NULL)) return 2;
    native_error=GetLastError();
    check("actual absent-window query",call_std("FindWindowExA",4,(uint32_t[]){0,0,0x4000u,0}),0);
    check("absent-window last-error matches native",xrt_get_last_error(&cpu),native_error);
    printf("%s client startup adapters\n",fails?"FAIL":"PASS");
    return fails?1:0;
}
