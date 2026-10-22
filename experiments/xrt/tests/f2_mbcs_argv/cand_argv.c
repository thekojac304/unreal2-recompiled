/* cand_argv.c (x64) - F2 candidate: the runtime's __getmainargs adapter (runtime/hle_msvcr70.c) on given bytes.
 *
 *   cand_argv.exe <hex of the guest ANSI command line>
 *
 * Puts the bytes in guest memory as xrt_cmdline_a (as xrt_main.c does), calls the adapter from
 * xrt_hle_msvcr70[] with a cdecl frame and prints argc/argv in the same format as ref_argv.c.
 * Stubs for the rest of the runtime follow tests/crt_diff/cand.c. */
#include <stdlib.h>
#include "xrt_internal.h"
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
void xrt_fldcw(CPU* c, uint16_t cw) { c->fcw = cw; }
void hle_msvcr70_init(void);

static XrtThread thr;

static void hexg(uint32_t s) {
    if (!rd8(s))
        printf("-");
    for (; rd8(s); s++)
        printf("%02X", rd8(s));
}

int main(int argc, char** argv) {
    const XrtHle* h;
    XrtFn fn = NULL;
    CPU* c = &thr.cpu;
    uint32_t cmd = ARENA_LO, out = ARENA_LO + 0x8000u, sp = STACK_HI - 256u, gargv;
    const char* x;
    int n = 0, i, gargc;
    if (argc != 2)
        return 2;
    xrt_mem_init();
    xrt_commit(ARENA_LO, ARENA_HI - ARENA_LO);
    xrt_commit(STACK_LO, STACK_HI - STACK_LO);
    thr.cpu.thread = &thr;
    thr.cpu.fcw = 0x027F;
    xrt_cur = &thr;
    for (x = argv[1]; x[0] && x[1] && strcmp(x, "-"); x += 2) {
        unsigned b;
        if (sscanf(x, "%2x", &b) != 1)
            return 2;
        wr8(cmd + (uint32_t)n++, (uint8_t)b);
    }
    wr8(cmd + (uint32_t)n, 0);
    xrt_cmdline_a = cmd;
    hle_msvcr70_init();
    for (h = xrt_hle_msvcr70; h->name; h++)
        if (!strcmp(h->name, "__getmainargs") && h->fn)
            fn = h->fn;
    if (!fn)
        return 3;
    c->r[ESP] = sp;
    wr32(sp, RET_SENTINEL);
    wr32(sp + 4u, out);          /* int* argc */
    wr32(sp + 8u, out + 4u);     /* char*** argv */
    wr32(sp + 12u, out + 8u);    /* char*** envp */
    wr32(sp + 16u, 0);           /* dowildcard */
    wr32(sp + 20u, out + 12u);   /* _startupinfo* */
    c->r[EAX] = 0xDEADBEEFu;
    fn(c);
    if (c->rv != RET_SENTINEL || c->r[ESP] != sp + 4u)
        return 4;
    gargc = (int)rd32(out);
    gargv = rd32(out + 4u);
    printf("rc %d\nargc %d\n", (int)c->r[EAX], gargc);
    for (i = 0; i < gargc; i++) {
        printf("argv ");
        hexg(rd32(gargv + 4u * (uint32_t)i));
        printf("\n");
    }
    if (rd32(gargv + 4u * (uint32_t)gargc) != 0)
        printf("argv[argc] not NULL\n");
    return 0;
}
