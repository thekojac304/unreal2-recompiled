/* cand.c - candidate side of the msvcr70 differential test (x64).
 *
 *   cand.exe <corpus.txt> <results.txt> [<sandbox root>]   (stdout receives the wprintf adapter's output)
 *
 * Links the runtime's xrt_fmt.c, hle_msvcr70.c and xrt_mem.c, hle_kernel32.c for its handle table and sandbox guard,
 * and xrt_msvcr70img.c, which loads <sandbox root>\System\msvcr70.dll for _dosmaperr's table (stubs below and in
 * common\xrt_test_stubs.c for the rest of the runtime).
 * Narrow sprintf cases go through the sprintf adapter (xrt_output); their length probe calls xrt_output directly.
 * Test data, format strings and argument blocks live in guest memory; adapters from xrt_hle_msvcr70[] are
 * called with a CPU whose ESP points at [return address][args...] (cdecl) and the result is read from
 * EAX. Every unbounded _vsnwprintf call is also checked against a direct xrt_wformat call. The qsort adapter's
 * comparator calls (xrt_call_guest) reach the shared cmp_eval through sentinel guest addresses. */
#include <fcntl.h>
#include <io.h>
#include "xrt_internal.h"
typedef uint32_t Ptr;
#define ARENA_LO 0x00400000u
#define ARENA_HI 0x04400000u
#define STACK_LO 0x08000000u
#define STACK_HI 0x08100000u
#define RET_SENTINEL 0x0BADC0DEu
#define TEB_VA 0x07F00000u
static Ptr arena_lo = ARENA_LO, arena_hi = ARENA_HI;
static void* H(Ptr p) { return G2H(p); }
static void flush_stdout(void) { xrt_stdout_flush(); }
#include "crt_diff_core.h"

/* ---------------------------------------------------------------- stubs for the rest of the runtime */
__declspec(thread) XrtThread* xrt_cur;
uint32_t xrt_cmdline_a, xrt_cmdline_w;
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
/* Exact data exports requested by startup; unrecognized dependencies stay fatal. */
static Ptr iob_va;
uint32_t xrt_hle_data(const char* dll, const char* name) {
    static Ptr acmdln_va;
    if (!_stricmp(dll, "msvcr70.dll") && !strcmp(name, "_acmdln"))
        return acmdln_va ? acmdln_va : (acmdln_va = xrt_rt_alloc(4, 4));
    if (strcmp(name, "_iob"))
        xrt_fatal(NULL, 70, "xrt_hle_data(%s, %s) in the test harness", dll, name);
    return iob_va = xrt_rt_alloc(20 * 32, 16);
}
static Ptr iob_base(void) { return iob_va; }
/* guest calls: only the harness's qsort comparators (cmp_ptr) are guest code here; anything else is fatal */
#define CMP_VA 0x0C000000u
static Ptr cmp_ptr(int kind) { return CMP_VA + 16u * (uint32_t)kind; }
uint32_t xrt_call_guest(CPU* c, uint32_t va, int nargs, const uint32_t* args, int stdcall) {
    if (va >= CMP_VA && va < CMP_VA + 16u * CMP_COUNT && !(va & 15u) && nargs == 2 && !stdcall)
        return (uint32_t)cmp_eval((int)((va - CMP_VA) / 16u), args[0], args[1]);
    xrt_fatal(c, 70, "xrt_call_guest(%08x, %d args%s) in the test harness", va, nargs, stdcall ? ", stdcall" : "");
}
XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code) { xrt_fatal(c, 70, "xrt_process_exit(%u) in the test harness", code); }
/* the runtime's xrt_fldcw enforces the modelled control word; no adapter under test should reach it */
void xrt_fldcw(CPU* c, uint16_t cw) { xrt_fatal(c, 70, "xrt_fldcw(%04x) reached in the test harness", cw); }
void hle_msvcr70_init(void);

/* ---------------------------------------------------------------- adapter calls */
static XrtThread thr;
static XrtFn fns[F_COUNT], f_wprintf, f_sprintf, bfns[BF_COUNT], deps[D_COUNT];
static unsigned long direct_mismatches;

/* NULL when the runtime registers no adapter under that export name (the import stays unbound and fatal) */
static XrtFn lookup_opt(const char* name) {
    const XrtHle* h;
    for (h = xrt_hle_msvcr70; h->name; h++)
        if (!strcmp(h->name, name) && h->fn)
            return h->fn;
    return NULL;
}

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

/* sprintf through the adapter (buffer, format, then the varargs at esp+12) */
static uint32_t call_sprintf(Ptr buf, Ptr fmt, const uint32_t* block, uint32_t* exc) {
    uint32_t a[BLOCKW + 2];
    (void)exc;
    a[0] = buf;
    a[1] = fmt;
    memcpy(a + 2, block, BLOCKW * 4);
    return call_adapter(f_sprintf, a, BLOCKW + 2);
}

static int bounded_available(int bf) { return bfns[bf] != NULL; }

/* _snprintf through its adapter: buffer, count, format, then the varargs (at esp+16); the va_list functions get
 * buffer, count, format and a pointer to the argument block */
static uint32_t call_bounded(int bf, Ptr buf, uint32_t count, Ptr fmt, Ptr va, const uint32_t* block, uint32_t* exc) {
    uint32_t a[BLOCKW + 3];
    (void)exc;
    a[0] = buf;
    a[1] = count;
    a[2] = fmt;
    if (bf == BF_SNPRINTF) {
        memcpy(a + 3, block, BLOCKW * 4);
        return call_adapter(bfns[bf], a, BLOCKW + 3);
    }
    a[3] = va;
    return call_adapter(bfns[bf], a, 4);
}

static int dep_available(int d) { return deps[d] != NULL; }

static uint32_t call_dep(int d, const uint32_t* args, int nargs, uint32_t* exc) {
    uint32_t r;
    (void)exc;
    wr32(TEB_VA + 0x34, LE_SENTINEL);   /* the guest's Win32 last error */
    r = call_adapter(deps[d], args, nargs);
    dep_last_error = rd32(TEB_VA + 0x34);
    return r;
}

/* length probe: the runtime's narrow formatter over a sink that refuses the character after `limit`, which
 * the CRT's charsout rule turns into -1, as the real _vsnprintf's full string stream does */
typedef struct Count { uint32_t n, limit; } Count;
static int count_put(void* ctx, uint16_t ch) {
    Count* k = (Count*)ctx;
    (void)ch;
    if (k->n >= k->limit)
        return 0;
    k->n++;
    return 1;
}
static int probe_too_long(Ptr fmt, Ptr va, uint32_t limit, uint32_t* exc) {
    Count k;
    int32_t r;
    (void)exc;
    k.n = 0;
    k.limit = limit;
    r = xrt_output(fmt, va, count_put, &k);
    return r < 0 || (uint32_t)r >= limit;
}

int main(int argc, char** argv) {
    int i;
    if (argc != 3 && argc != 4) {
        fprintf(stderr, "usage: cand.exe corpus results [sandbox root holding System\\msvcr70.dll]\n");
        return 2;
    }
    xrt_mem_init();
    xrt_commit(ARENA_LO, ARENA_HI - ARENA_LO);
    xrt_commit(STACK_LO, STACK_HI - STACK_LO);
    xrt_commit(TEB_VA, 0x1000);
    thr.cpu.fs_base = TEB_VA;   /* the guest last error is the TEB word at +0x34 */
    thr.cpu.thread = &thr;
    thr.cpu.fcw = 0x027F;
    thr.rand_seed = 1;          /* as xrt_thread.c initialises every guest thread */
    xrt_cur = &thr;
    hle_msvcr70_init();         /* also puts host stdout in binary mode: the adapter does the text translation */
    for (i = 0; i < F_COUNT; i++)
        fns[i] = lookup(fn_names[i]);
    f_wprintf = lookup("wprintf");
    f_sprintf = lookup("sprintf");
    for (i = 0; i < BF_COUNT; i++) {
        bfns[i] = lookup_opt(bf_names[i]);
        fprintf(stderr, "bounded %s: %s\n", bf_names[i], bfns[i] ? "adapter" : "no adapter (PENDING)");
    }
    fputs("dependencies with an adapter:", stderr);
    for (i = 0; i < D_COUNT; i++)
        if ((deps[i] = lookup_opt(d_names[i])) != NULL)
            fprintf(stderr, " %s", d_names[i][0] == '?' ? "_set_se_translator" : d_names[i]);
    fputs("\ndependencies without an adapter (PENDING):", stderr);
    for (i = 0; i < D_COUNT; i++)
        if (!deps[i])
            fprintf(stderr, " %s", d_names[i][0] == '?' ? "_set_se_translator" : d_names[i]);
    fputc('\n', stderr);
    if (argc == 4) {
        /* _dosmaperr reads its table from the DLL image (SHA-checked), loaded once from the reference's sandbox */
        snprintf(xrt_sandbox_root, sizeof xrt_sandbox_root, "%s", argv[3]);
        xrt_msvcr70_image();
    }
    if (GetFileAttributesA(FS_MARKER) != INVALID_FILE_ATTRIBUTES) {
        /* F lines: the scratch tree's parent is the sandbox root, as the game's System directory (the current
         * directory of a run) sits one level below its sandbox */
        char* slash;
        GetCurrentDirectoryA(sizeof xrt_sandbox_root, xrt_sandbox_root);
        if ((slash = strrchr(xrt_sandbox_root, '\\')) != NULL)
            *slash = 0;
    }
    run_corpus(argv[1], argv[2]);
    xrt_stdout_flush();
    fprintf(stderr, "direct xrt_wformat vs adapter mismatches: %lu\n", direct_mismatches);
    return direct_mismatches ? 5 : 0;
}
