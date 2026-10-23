/* ref.c - reference side of the msvcr70 differential test (x86, 32-bit).
 *
 *   ref.exe <path to msvcr70.dll> <corpus.txt> <results.txt>   (stdout receives wprintf output)
 *
 * Loads the real msvcr70.dll (a read-only sandbox copy) with LoadLibrary and calls the functions under
 * test through GetProcAddress. _vsnwprintf gets a hand-built va_list (on x86 a pointer to the packed
 * argument block); wprintf gets the block copied onto the stack as a by-value structure argument.
 * Every call is wrapped in SEH so a fault is recorded instead of ending the run. */
#include <stdint.h>
typedef uint32_t Ptr;
static Ptr arena_lo, arena_hi;
static void* H(Ptr p) { return (void*)(uintptr_t)p; }
static void flush_stdout(void);
#include "crt_diff_core.h"

typedef uint32_t(__cdecl* Fn4)(uint32_t, uint32_t, uint32_t, uint32_t);
typedef struct Block { uint32_t w[BLOCKW]; } Block;
typedef int(__cdecl* WprintfFn)(const wchar_t*, Block);
typedef int(__cdecl* SprintfFn)(char*, const char*, Block);
typedef int(__cdecl* SnprintfFn)(char*, uint32_t, const char*, Block);
typedef int(__cdecl* FflushFn)(void*);

static FARPROC fns[F_COUNT];
static WprintfFn p_wprintf;
static SprintfFn p_sprintf;
static SnprintfFn p_snprintf;
static Fn4 p_vsnprintf;
static FflushFn p_fflush;
static uint8_t* p_iob;

static uint32_t call_fn(int f, const uint32_t* args, int nargs, uint32_t* exc) {
    uint32_t a[4] = {0, 0, 0, 0}, r = 0;
    memcpy(a, args, (size_t)nargs * 4);
    __try {
        r = ((Fn4)fns[f])(a[0], a[1], a[2], a[3]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *exc = GetExceptionCode();
    }
    return r;
}

static uint32_t call_wprintf(Ptr fmt, const uint32_t* block, uint32_t* exc) {
    Block b;
    uint32_t r = 0;
    memcpy(b.w, block, sizeof b.w);
    __try {
        r = (uint32_t)p_wprintf((const wchar_t*)H(fmt), b);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *exc = GetExceptionCode();
    }
    return r;
}

static uint32_t call_sprintf(Ptr buf, Ptr fmt, const uint32_t* block, uint32_t* exc) {
    Block b;
    uint32_t r = 0;
    memcpy(b.w, block, sizeof b.w);
    __try {
        r = (uint32_t)p_sprintf((char*)H(buf), (const char*)H(fmt), b);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *exc = GetExceptionCode();
    }
    return r;
}

/* _vsnprintf returns -1 only when the string stream fills up (the narrow _output has no other failing write),
 * and returns the count itself, without a terminator, when the output is exactly that long */
static int probe_too_long(Ptr fmt, Ptr va, uint32_t limit, uint32_t* exc) {
    Ptr p = talloc(limit + GUARD);
    int32_t r = 0;
    __try {
        r = (int32_t)p_vsnprintf(p, limit, fmt, va);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *exc = GetExceptionCode();
        return 1;
    }
    return r < 0 || (uint32_t)r >= limit;
}

static int bounded_available(int bf) {
    (void)bf;
    return 1;
}

/* _snprintf gets the argument block by value (so its varargs follow the format on the stack); the va_list
 * functions get a pointer to the block */
static uint32_t call_bounded(int bf, Ptr buf, uint32_t count, Ptr fmt, Ptr va, const uint32_t* block, uint32_t* exc) {
    Block b;
    uint32_t r = 0;
    memcpy(b.w, block, sizeof b.w);
    __try {
        if (bf == BF_SNPRINTF)
            r = (uint32_t)p_snprintf((char*)H(buf), count, (const char*)H(fmt), b);
        else
            r = (bf == BF_VSNPRINTF ? p_vsnprintf : (Fn4)fns[F_VSNWPRINTF])(buf, count, fmt, va);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *exc = GetExceptionCode();
    }
    return r;
}

static FARPROC deps[D_COUNT];

static int dep_available(int d) { return deps[d] != NULL; }

static uint32_t call_dep(int d, const uint32_t* args, int nargs, uint32_t* exc) {
    uint32_t a[4] = {0, 0, 0, 0}, r = 0;
    memcpy(a, args, (size_t)nargs * 4);
    SetLastError(LE_SENTINEL);
    __try {
        r = ((Fn4)deps[d])(a[0], a[1], a[2], a[3]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *exc = GetExceptionCode();
    }
    dep_last_error = GetLastError();
    return r;
}

static Ptr iob_base(void) { return (Ptr)(uintptr_t)p_iob; }

/* native comparators for msvcr70's qsort */
static int __cdecl ref_cmp0(const void* a, const void* b) { return cmp_eval(0, (Ptr)(uintptr_t)a, (Ptr)(uintptr_t)b); }
static int __cdecl ref_cmp1(const void* a, const void* b) { return cmp_eval(1, (Ptr)(uintptr_t)a, (Ptr)(uintptr_t)b); }
static int __cdecl ref_cmp2(const void* a, const void* b) { return cmp_eval(2, (Ptr)(uintptr_t)a, (Ptr)(uintptr_t)b); }
static int __cdecl ref_cmp3(const void* a, const void* b) { return cmp_eval(3, (Ptr)(uintptr_t)a, (Ptr)(uintptr_t)b); }
static int __cdecl ref_cmp4(const void* a, const void* b) { return cmp_eval(4, (Ptr)(uintptr_t)a, (Ptr)(uintptr_t)b); }
static Ptr cmp_ptr(int kind) {
    static int(__cdecl* const t[CMP_COUNT])(const void*, const void*) = {ref_cmp0, ref_cmp1, ref_cmp2, ref_cmp3,
                                                                          ref_cmp4};
    return (Ptr)(uintptr_t)t[kind];
}

static void flush_stdout(void) { p_fflush(p_iob + 32); }   /* &_iob[1]: msvcr70 FILE is 32 bytes */

int main(int argc, char** argv) {
    HMODULE m;
    int i;
    void* mem;
    if (argc != 4) {
        fprintf(stderr, "usage: ref.exe msvcr70.dll corpus results\n");
        return 2;
    }
    m = LoadLibraryA(argv[1]);
    if (!m) {
        fprintf(stderr, "LoadLibrary(%s) failed: %lu\n", argv[1], GetLastError());
        return 2;
    }
    for (i = 0; i < F_COUNT; i++)
        if (!(fns[i] = GetProcAddress(m, fn_names[i]))) {
            fprintf(stderr, "missing export %s\n", fn_names[i]);
            return 2;
        }
    p_wprintf = (WprintfFn)GetProcAddress(m, "wprintf");
    p_fflush = (FflushFn)GetProcAddress(m, "fflush");
    p_iob = (uint8_t*)GetProcAddress(m, "_iob");
    p_sprintf = (SprintfFn)GetProcAddress(m, "sprintf");
    p_vsnprintf = (Fn4)GetProcAddress(m, "_vsnprintf");
    p_snprintf = (SnprintfFn)GetProcAddress(m, "_snprintf");
    if (!p_wprintf || !p_fflush || !p_iob || !p_sprintf || !p_vsnprintf || !p_snprintf)
        return 2;
    for (i = 0; i < D_COUNT; i++)
        if (!(deps[i] = GetProcAddress(m, d_names[i]))) {
            fprintf(stderr, "missing export %s\n", d_names[i]);
            return 2;
        }
    mem = VirtualAlloc(NULL, 64u << 20, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!mem)
        return 2;
    arena_lo = (Ptr)(uintptr_t)mem;
    arena_hi = arena_lo + (64u << 20);
    {
        char path[MAX_PATH];
        GetModuleFileNameA(m, path, sizeof path);
        fprintf(stderr, "reference: %s at %p\n", path, (void*)m);
    }
    run_corpus(argv[2], argv[3]);
    flush_stdout();
    return 0;
}
