/* bench.c - runs the lifted kernels (tools/xrt/xlift.py output of kernels.c) on the runtime's CPU model and times
 * them. Portable C (Windows: VirtualAlloc/__try; POSIX: mmap/SIGSEGV+sigsetjmp), so the same file builds with
 * cl, gcc and clang for x86-64 and AArch64 (see run.py --export).
 *   bench image.bin BASE out.bin REPS name=0xVA:N ...
 * Runtime entry points the generated code can reach are local definitions, as in ../opt_diff/lifted.c: indirect
 * calls dispatch through the module's own function table (and fill the call-target cache, so later calls take the
 * inline ICALLI path), traps/fatals end the call with a status. x87 helpers: only fsqrt, fist, fround, fldcw are
 * expected (kernels.c uses no transcendental instruction); the others are reported as status 2. */
#include <math.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xrt.h"
#include "kernels.h"
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <signal.h>
#include <sys/mman.h>
#include <time.h>
#endif

extern const XrtLiftedModule xrt_mod_PerfKernels;

uint8_t* xrt_g;
volatile long xrt_preempt_req = 0;
#if defined(_WIN32)
static jmp_buf jb;
#define SETJMP(b) setjmp(b)
#define LONGJMP(b, v) longjmp(b, v)
#else
static sigjmp_buf jb;
#define SETJMP(b) sigsetjmp(b, 1)
#define LONGJMP(b, v) siglongjmp(b, v)
static void on_segv(int sig) { (void)sig; LONGJMP(jb, 5); }
#endif

static XrtLiftedFn lookup(uint32_t va) {
    const XrtLiftedModule* m = &xrt_mod_PerfKernels;
    uint32_t lo = 0, hi = m->nfuncs;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (m->funcs[mid].va < va) lo = mid + 1; else hi = mid;
    }
    return lo < m->nfuncs && m->funcs[lo].va == va ? m->funcs[lo].fn : NULL;
}

void xrt_preempt(CPU* c) { (void)c; }
XrtCallCache xrt_call_cache[65536];
uint32_t xrt_call_cache_gen = 1;
void xrt_icall_after(CPU* c) { (void)c; }
void xrt_world_return(CPU* c) { c->world_floor = 0xFFFFFFFFu; }
XrtLiftedRet xrt_icall(CPU* c, uint32_t target, uint32_t site) {
    XrtLiftedFn fn = lookup(target);
    XrtCallCache* e = &xrt_call_cache[XRT_CALL_CACHE_SLOT(target)];
    (void)site;
    if (!fn)
        LONGJMP(jb, 4);
    e->va = target; e->gen = xrt_call_cache_gen; e->fn = fn; e->flags = 0;
    XRT_CALL_LIFTED(fn, c);
    XRT_LIFTED_RETURN(c);
}
XrtLiftedRet xrt_ijmp(CPU* c, uint32_t target, uint32_t site) { XRT_TAIL(xrt_icall(c, target, site)); }
XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* why) { (void)c; (void)site; (void)why; LONGJMP(jb, 1); }
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected) { (void)c; (void)site; (void)expected; LONGJMP(jb, 3); }
XRT_NORETURN void xrt_div0(CPU* c, uint32_t site) { (void)c; (void)site; LONGJMP(jb, 2); }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) { (void)c; (void)code; (void)fmt; LONGJMP(jb, 2); }
void xrt_mark(CPU* c, XrtMark* m) { (void)c; (void)m; }
void xrt_watch_store(CPU* c, XrtWatchDef* w, uint32_t site) { (void)c; (void)w; (void)site; }
void xrt_log(const char* fmt, ...) { (void)fmt; }
void xrt_cpuid(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_rdtsc(CPU* c) { (void)c; LONGJMP(jb, 2); }
#if !(defined(_M_X64) || defined(_M_IX86) || defined(__x86_64__) || defined(__i386__))
uint64_t xrt_rdtsc64(void) { return 0; }
#endif
/* x87 helpers, as runtime/xrt_cpu.c implements them for control word 0x027F (round to nearest) */
double xrt_fround(CPU* c, double v) { (void)c; return nearbyint(v); }
int64_t xrt_fist64(CPU* c, double v) { double r = xrt_fround(c, v); return r >= -9223372036854775808.0 && r < 9223372036854775808.0 ? (int64_t)r : INT64_MIN; }
int32_t xrt_fist32(CPU* c, double v) { double r = xrt_fround(c, v); return r >= -2147483648.0 && r <= 2147483647.0 ? (int32_t)r : INT32_MIN; }
int16_t xrt_fist16(CPU* c, double v) { double r = xrt_fround(c, v); return r >= -32768.0 && r <= 32767.0 ? (int16_t)r : INT16_MIN; }
void xrt_fsqrt(CPU* c) { *ST(c, 0) = sqrt(*ST(c, 0)); }
void xrt_fsin(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_fcos(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_fptan(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_fpatan(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_fyl2x(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_f2xm1(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_fscale(CPU* c) { (void)c; LONGJMP(jb, 2); }
void xrt_fldcw(CPU* c, uint16_t cw) { if (cw != 0x027F) LONGJMP(jb, 2); c->fcw = cw; }

static void commit(uint32_t a, uint32_t n) {
#if defined(_WIN32)
    if (!VirtualAlloc(xrt_g + a, n, MEM_COMMIT, PAGE_READWRITE)) { fprintf(stderr, "bench: commit %08x+%x failed\n", a, n); exit(2); }
#else
    if (mprotect(xrt_g + a, n, PROT_READ | PROT_WRITE)) { fprintf(stderr, "bench: commit %08x+%x failed\n", a, n); exit(2); }
#endif
}

static double now_ms(void) {
#if defined(_WIN32)
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f); QueryPerformanceCounter(&t);
    return (double)t.QuadPart * 1000.0 / (double)f.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
#endif
}

static int cmp_double(const void* a, const void* b) { double x = *(const double*)a, y = *(const double*)b; return x < y ? -1 : x > y; }

/* one kernel call on a fresh CPU; returns the status */
static int call_kernel(XrtLiftedFn fn, CPU* c, uint32_t n, uint32_t seed) {
    volatile int st;
    memset(c, 0, sizeof *c);
    c->fcw = 0x027F;
    c->world_floor = 0xFFFFFFFFu;
    c->r[ESP] = PK_STACK_TOP - 256;
    push32(c, seed); push32(c, n); push32(c, PK_OUT); push32(c, PK_IN); push32(c, PK_SENTINEL);
    st = SETJMP(jb);
    if (st == 0) {
#if defined(_WIN32)
        __try {
            XRT_CALL_LIFTED(fn, c);
            if (c->rv != PK_SENTINEL) st = 3;
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            st = 5;
        }
#else
        XRT_CALL_LIFTED(fn, c);
        if (c->rv != PK_SENTINEL) st = 3;
#endif
    }
    return st;
}

int main(int argc, char** argv) {
    FILE *fi, *fo;
    uint32_t base, size, reps, k;
    int a;
    static uint8_t image[16 << 20];
    static CPU cpu;
    double* times;
    if (argc < 5) { fprintf(stderr, "usage: bench image.bin BASE out.bin REPS name=0xVA:N ...\n"); return 2; }
    base = (uint32_t)strtoul(argv[2], NULL, 0);
    reps = (uint32_t)strtoul(argv[4], NULL, 0);
    fi = fopen(argv[1], "rb"); fo = fopen(argv[3], "wb");
    if (!fi || !fo) return 2;
    size = (uint32_t)fread(image, 1, sizeof image, fi);
    fclose(fi);
#if defined(_WIN32)
    xrt_g = (uint8_t*)VirtualAlloc(NULL, XRT_GUEST_GUARD_BELOW + XRT_GUEST_WINDOW, MEM_RESERVE, PAGE_NOACCESS);
#else
    xrt_g = (uint8_t*)mmap(NULL, XRT_GUEST_GUARD_BELOW + XRT_GUEST_WINDOW, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (xrt_g == MAP_FAILED) xrt_g = NULL;
    signal(SIGSEGV, on_segv);
    signal(SIGBUS, on_segv);
#endif
    if (!xrt_g) { fprintf(stderr, "bench: cannot reserve guest memory\n"); return 2; }
    xrt_g += XRT_GUEST_GUARD_BELOW;        /* 2 GB guard below the window (xrt.h, --opt addr64) */
    commit(base, (size + 0xFFFF) & ~0xFFFFu);
    memcpy(xrt_g + base, image, size);
    commit(PK_IN, PK_BUF); commit(PK_OUT, PK_BUF); commit(PK_STACK_LO, PK_STACK_TOP - PK_STACK_LO);
    times = (double*)calloc(reps ? reps : 1, sizeof *times);
    printf("%-10s %9s %9s %9s  %s\n", "kernel", "n", "min ms", "med ms", "checksum");
    for (a = 5; a < argc; a++) {
        PkRec r;
        char* eq = strchr(argv[a], '=');
        char* colon = eq ? strchr(eq, ':') : NULL;
        uint32_t va, n;
        XrtLiftedFn fn;
        int st = 0;
        if (!eq || !colon) { fprintf(stderr, "bench: bad argument %s\n", argv[a]); return 2; }
        memset(&r, 0, sizeof r);
        snprintf(r.name, sizeof r.name, "%.*s", (int)(eq - argv[a]), argv[a]);
        va = (uint32_t)strtoul(eq + 1, NULL, 0);
        n = (uint32_t)strtoul(colon + 1, NULL, 0);
        fn = lookup(va);
        if (!fn) { fprintf(stderr, "bench: %08x is not a lifted function\n", va); return 2; }
        r.n = n;
        pk_fill(xrt_g + PK_IN, xrt_g + PK_OUT);
        st = call_kernel(fn, &cpu, n, 0x1234u);        /* warm-up and checksum */
        r.eax = cpu.r[EAX]; r.edx = cpu.r[EDX];
        r.h_out = pk_hash(xrt_g + PK_OUT, PK_BUF);
        for (k = 0; k < reps && !st; k++) {
            double t0;
            pk_fill(xrt_g + PK_IN, xrt_g + PK_OUT);
            t0 = now_ms();
            st = call_kernel(fn, &cpu, n, 0x1234u);
            times[k] = now_ms() - t0;
            if (cpu.r[EAX] != r.eax || cpu.r[EDX] != r.edx) st = 6;   /* not deterministic */
        }
        r.status = (uint32_t)st;
        if (!st && reps) {
            qsort(times, reps, sizeof *times, cmp_double);
            r.min_ms = times[0];
            r.med_ms = times[reps / 2];
        }
        fwrite(&r, sizeof r, 1, fo);
        printf("%-10s %9u %9.3f %9.3f  %08x%08x %s\n", r.name, n, r.min_ms, r.med_ms, r.edx, r.eax,
               st ? (st == 1 ? "TRAP" : st == 2 ? "UNSUPPORTED" : st == 3 ? "BADRET" : st == 4 ? "UNKNOWN-CALL" : st == 5 ? "FAULT" : "NONDETERMINISTIC") : "");
    }
    fclose(fo);
    return 0;
}
