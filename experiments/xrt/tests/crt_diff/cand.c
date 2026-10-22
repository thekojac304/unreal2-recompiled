/* cand.c - candidate side of the msvcr70 differential test (x64).
 *
 *   cand.exe <corpus.txt> <results.txt>   (stdout receives the wprintf adapter's output)
 *
 * Links the runtime's xrt_fmt.c, hle_msvcr70.c and xrt_mem.c (stubs below for the rest of the runtime).
 * Test data, format strings and argument blocks live in guest memory; adapters from xrt_hle_msvcr70[] are
 * called with a CPU whose ESP points at [return address][args...] (cdecl) and the result is read from
 * EAX. Every unbounded _vsnwprintf call is also checked against a direct xrt_wformat call. */
#include <fcntl.h>
#include <io.h>
#include "xrt_internal.h"
typedef uint32_t Ptr;
#define ARENA_LO 0x00400000u
#define ARENA_HI 0x04400000u
#define STACK_LO 0x08000000u
#define STACK_HI 0x08100000u
#define RET_SENTINEL 0x0BADC0DEu
static Ptr arena_lo = ARENA_LO, arena_hi = ARENA_HI;
static void* H(Ptr p) { return G2H(p); }
static void flush_stdout(void) { xrt_stdout_flush(); }
#include "crt_diff_core.h"

/* ---------------------------------------------------------------- stubs for the rest of the runtime */
__declspec(thread) XrtThread* xrt_cur;
uint32_t xrt_cmdline_a;
void xrt_log(const char* fmt, ...) { (void)fmt; }
void xrt_event(const char* kind, const char* fmt, ...) { (void)kind; (void)fmt; }
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
uint32_t xrt_call_guest(CPU* c, uint32_t va, int nargs, const uint32_t* args, int stdcall) {
    (void)nargs; (void)args; (void)stdcall;
    xrt_fatal(c, 70, "xrt_call_guest(%08x) in the test harness", va);
}
XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code) { xrt_fatal(c, 70, "xrt_process_exit(%u) in the test harness", code); }
void xrt_fldcw(CPU* c, uint16_t cw) { c->fcw = cw; }
void hle_msvcr70_init(void);

/* ---------------------------------------------------------------- adapter calls */
static XrtThread thr;
static XrtFn fns[F_COUNT], f_wprintf;
static unsigned long direct_mismatches;

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

static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc) {
    uint32_t r;
    (void)exc;
    r = call_adapter(fns[f], args, nargs);
    if (f == F_VSNWPRINTF && args[1] == BIG && (int32_t)r >= 0) {
        /* xrt_wformat's sink never fails, so outputs containing U+FFFF (a "failed" write in the CRT's
         * string stream) are not comparable */
        size_t len, k, ffff = 0;
        uint16_t* s = xrt_wformat(args[2], args[3], &len);
        for (k = 0; k < len; k++)
            ffff |= s[k] == 0xFFFF;
        if (!ffff && (len != r || memcmp(s, G2H(args[0]), len * 2))) {
            direct_mismatches++;
            fprintf(stderr, "xrt_wformat differs from the _vsnwprintf adapter (len %zu vs %u)\n", len, r);
        }
        free(s);
    }
    return r;
}

static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc) {
    uint32_t a[BLOCKW + 1];
    (void)exc;
    a[0] = fmt;
    memcpy(a + 1, block, BLOCKW * 4);
    return call_adapter(f_wprintf, a, BLOCKW + 1);
}

int main(int argc, char** argv) {
    int i;
    if (argc != 3) {
        fprintf(stderr, "usage: cand.exe corpus results\n");
        return 2;
    }
    xrt_mem_init();
    xrt_commit(ARENA_LO, ARENA_HI - ARENA_LO);
    xrt_commit(STACK_LO, STACK_HI - STACK_LO);
    thr.cpu.thread = &thr;
    thr.cpu.fcw = 0x027F;
    thr.rand_seed = 1;          /* as xrt_thread.c initialises every guest thread */
    xrt_cur = &thr;
    hle_msvcr70_init();         /* also puts host stdout in binary mode: the adapter does the text translation */
    for (i = 0; i < F_COUNT; i++)
        fns[i] = lookup(fn_names[i]);
    f_wprintf = lookup("wprintf");
    run_corpus(argv[1], argv[2]);
    xrt_stdout_flush();
    fprintf(stderr, "direct xrt_wformat vs adapter mismatches: %lu\n", direct_mismatches);
    return direct_mismatches ? 5 : 0;
}
