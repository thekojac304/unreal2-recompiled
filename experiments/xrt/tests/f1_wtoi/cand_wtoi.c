/* cand_wtoi.c (x64) - calls the runtime's _wtoi adapter (runtime/hle_msvcr70.c) on the same cases.
 * Stubs for the rest of the runtime follow tests/crt_diff/cand.c. */
#include <stdlib.h>
#include <wchar.h>
#include "xrt_internal.h"
#include "cases.h"
#define ARENA_LO 0x00400000u
#define ARENA_HI 0x00500000u
#define STACK_LO 0x08000000u
#define STACK_HI 0x08100000u
#define RET_SENTINEL 0x0BADC0DEu

__declspec(thread) XrtThread* xrt_cur;
uint32_t xrt_cmdline_a;
void xrt_log(const char* fmt, ...) { (void)fmt; }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    (void)c;
    fprintf(stderr, "xrt_fatal (%d): %s\n", code, fmt);
    exit(code);
}
uint32_t xrt_hle_data(const char* dll, const char* name) { (void)dll; (void)name; return xrt_rt_alloc(20 * 32, 16); }
uint32_t xrt_call_guest(CPU* c, uint32_t va, int nargs, const uint32_t* args, int stdcall) {
    (void)nargs; (void)args; (void)stdcall;
    xrt_fatal(c, 70, "xrt_call_guest(%08x) in the test harness", va);
}
XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code) { xrt_fatal(c, 70, "xrt_process_exit(%u)", code); }
/* the runtime's xrt_fldcw enforces the modelled control word; no adapter under test should reach it */
void xrt_fldcw(CPU* c, uint16_t cw) { xrt_fatal(c, 70, "xrt_fldcw(%04x) reached in the test harness", cw); }
void hle_msvcr70_init(void);

static XrtThread thr;

int main(void) {
    const XrtHle* h;
    XrtFn fn = NULL;
    int i;
    xrt_mem_init();
    xrt_commit(ARENA_LO, ARENA_HI - ARENA_LO);
    xrt_commit(STACK_LO, STACK_HI - STACK_LO);
    thr.cpu.thread = &thr;
    thr.cpu.fcw = 0x027F;
    xrt_cur = &thr;
    hle_msvcr70_init();
    for (h = xrt_hle_msvcr70; h->name; h++)
        if (!strcmp(h->name, "_wtoi") && h->fn)
            fn = h->fn;
    if (!fn)
        return 2;
    for (i = 0; i < NCASES; i++) {
        CPU* c = &thr.cpu;
        uint32_t s = ARENA_LO + 0x1000u * (uint32_t)i, sp = STACK_HI - 256u;
        size_t n = wcslen(cases[i]), k;
        for (k = 0; k <= n; k++)
            wr16(s + 2u * (uint32_t)k, (uint16_t)cases[i][k]);
        /* fill the guest page after the string with digits so a reader that ignores the terminator would be visible */
        for (k = n + 1; k < n + 40; k++)
            wr16(s + 2u * (uint32_t)k, (uint16_t)'9');
        c->r[ESP] = sp;
        wr32(sp, RET_SENTINEL);
        wr32(sp + 4u, s);
        c->r[EAX] = 0xDEADBEEFu;
        fn(c);
        if (c->rv != RET_SENTINEL || c->r[ESP] != sp + 4u)
            return 4;
        printf("%2d len=%2u r=%d\n", i, (unsigned)n, (int32_t)c->r[EAX]);
    }
    return 0;
}
