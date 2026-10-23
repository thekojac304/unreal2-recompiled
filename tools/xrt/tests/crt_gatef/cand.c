/* cand.c - candidate side of the gate-F CRT differential test (x64): the runtime's adapters from
 * experiments/xrt/runtime/hle_msvcr70.c, called with a guest CPU (cdecl stack, x87 stack) on guest memory.
 *   cand.exe <sandbox root> <corpus.txt> <results.txt>   (the sandbox's System\msvcr70.dll gives _CIpow its tables)
 * qsort's comparator is "guest code" here only by address: xrt_call_guest below recognises the comparator's
 * address and runs the shared comparison (gatef_core.h), checking the arguments the adapter passes. */
#include "xrt_internal.h"
typedef uint32_t Ptr;
#define ARENA_LO 0x00400000u
#define ARENA_HI 0x00500000u
#define STACK_LO 0x08000000u
#define STACK_HI 0x08100000u
#define RET_SENTINEL 0x0BADC0DEu
#define COMPARATOR_VA 0x0C0FFEE0u
static uint32_t arena_used;
static void* H(Ptr p) { return G2H(p); }
#include "gatef_core.h"

/* ---------------------------------------------------------------- stubs for the rest of the runtime */
__declspec(thread) XrtThread* xrt_cur;
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a;
void xrt_log(const char* fmt, ...) { (void)fmt; }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list ap;
    (void)c;
    fflush(stdout);
    fprintf(stderr, "xrt_fatal (%d): ", code);
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    exit(code);
}
uint32_t xrt_hle_data(const char* dll, const char* name) { (void)dll; (void)name; return xrt_rt_alloc(20 * 32, 16); }
XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code) { xrt_fatal(c, 70, "xrt_process_exit(%u) in the test harness", code); }
void xrt_fldcw(CPU* c, uint16_t cw) { xrt_fatal(c, 70, "test harness: unexpected xrt_fldcw(%04x)", cw); }
void hle_msvcr70_init(void);

uint32_t xrt_call_guest(CPU* c, uint32_t va, int nargs, const uint32_t* args, int stdcall) {
    if (va != COMPARATOR_VA || nargs != 2 || stdcall)
        xrt_fatal(c, 70, "unexpected guest call %08x (%d args, stdcall %d)", va, nargs, stdcall);
    return (uint32_t)qs_compare(args[0], args[1]);
}

/* ---------------------------------------------------------------- adapter calls */
static XrtThread thr;
static XrtFn f_qsort, f_atof, f_CIpow, f_CIfmod, f_isnan, f_toupper, f_strchr, f_stricmp, f_atoi;

static XrtFn lookup(const char* name) {
    const XrtHle* h;
    for (h = xrt_hle_msvcr70; h->name; h++)
        if (!strcmp(h->name, name) && h->fn)
            return h->fn;
    fprintf(stderr, "no adapter for %s\n", name);
    exit(2);
}

static uint32_t call_adapter(XrtFn fn, const uint32_t* args, int nargs) {
    CPU* c = &thr.cpu;
    uint32_t sp = STACK_HI - 256u - 4u * (uint32_t)(nargs + 1);
    int i;
    c->r[ESP] = sp;
    wr32(sp, RET_SENTINEL);
    for (i = 0; i < nargs; i++)
        wr32(sp + 4u + 4u * (uint32_t)i, args[i]);
    c->r[EAX] = 0xDEADBEEFu;
    c->rv = 0;
    fn(c);
    if (c->rv != RET_SENTINEL || c->r[ESP] != sp + 4u) {
        fprintf(stderr, "adapter broke the cdecl stack discipline (rv %08x, esp %08x, expected %08x)\n", c->rv,
                c->r[ESP], sp + 4u);
        exit(4);
    }
    return c->r[EAX];
}

static void arena_reset(void) { arena_used = 0; }
static Ptr side_str(const uint8_t* s, size_t n) {
    Ptr p;
    arena_used = (arena_used + 15u) & ~15u;
    if (ARENA_LO + arena_used + n + 1 > ARENA_HI) {
        fprintf(stderr, "arena full\n");
        exit(2);
    }
    p = ARENA_LO + arena_used;
    memcpy(G2H(p), s, n);
    wr8(p + (uint32_t)n, 0);
    arena_used += (uint32_t)n + 1;
    return p;
}

static void side_pow(int fmod_, uint64_t xb, uint64_t yb, char* out) {
    CPU* c = &thr.cpu;
    double x, y, r;
    uint64_t b;
    memcpy(&x, &xb, 8);
    memcpy(&y, &yb, 8);
    c->top = 0;
    fpush(c, x);
    fpush(c, y);
    call_adapter(fmod_ ? f_CIfmod : f_CIpow, NULL, 0);
    r = *ST(c, 0);
    fpop(c);
    memcpy(&b, &r, 8);
    sprintf(out, "%016llx", (unsigned long long)b);
    if (c->top != 0)
        strcat(out, " stack-imbalance");
}

static uint64_t side_atof(Ptr s) {
    CPU* c = &thr.cpu;
    double r;
    uint64_t b;
    c->top = 0;
    call_adapter(f_atof, &s, 1);
    if (c->top != 7) {
        fprintf(stderr, "atof did not push exactly one x87 value\n");
        exit(4);
    }
    r = *ST(c, 0);
    fpop(c);
    memcpy(&b, &r, 8);
    return b;
}
static int32_t side_isnan(uint64_t bits) {
    uint32_t a[2];
    a[0] = (uint32_t)bits;
    a[1] = (uint32_t)(bits >> 32);
    return (int32_t)call_adapter(f_isnan, a, 2);
}
static int32_t side_toupper(int32_t ch) {
    uint32_t a = (uint32_t)ch;
    return (int32_t)call_adapter(f_toupper, &a, 1);
}
static Ptr side_strchr(Ptr s, int32_t ch) {
    uint32_t a[2];
    a[0] = s;
    a[1] = (uint32_t)ch;
    return call_adapter(f_strchr, a, 2);
}
static int32_t side_stricmp(Ptr x, Ptr y) {
    uint32_t a[2];
    a[0] = x;
    a[1] = y;
    return (int32_t)call_adapter(f_stricmp, a, 2);
}
static int32_t side_atoi(Ptr s) { return (int32_t)call_adapter(f_atoi, &s, 1); }
static void side_qsort(Ptr base, uint32_t n, uint32_t width) {
    uint32_t a[4];
    a[0] = base;
    a[1] = n;
    a[2] = width;
    a[3] = COMPARATOR_VA;
    call_adapter(f_qsort, a, 4);
}

int main(int argc, char** argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: cand.exe <sandbox root> <corpus> <results>\n");
        return 2;
    }
    snprintf(xrt_sandbox_root, sizeof xrt_sandbox_root, "%s", argv[1]);
    xrt_mem_init();
    xrt_commit(ARENA_LO, ARENA_HI - ARENA_LO);
    xrt_commit(STACK_LO, STACK_HI - STACK_LO);
    thr.cpu.thread = &thr;
    thr.cpu.fcw = 0x027F;
    thr.rand_seed = 1;
    xrt_cur = &thr;
    hle_msvcr70_init();
    f_qsort = lookup("qsort");
    f_atof = lookup("atof");
    f_CIpow = lookup("_CIpow");
    f_CIfmod = lookup("_CIfmod");
    f_isnan = lookup("_isnan");
    f_toupper = lookup("toupper");
    f_strchr = lookup("strchr");
    f_stricmp = lookup("_stricmp");
    f_atoi = lookup("atoi");
    run_corpus(argv[2], argv[3]);
    return 0;
}
