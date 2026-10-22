/* x87_common.h - definitions shared by the x87 differential harnesses:
 *   x87_hw32.c  32-bit native reference (inline __asm, FCW 0x027F) - real x87 hardware
 *   x87_rt64.c  x64 harness running the runtime's helpers (runtime/xrt_cpu.c) and the lifted Core.dll
 *               functions (build/x87/gen, git-ignored) on a CPU struct from runtime/xrt.h
 * Records are exchanged through binary files; exhaustive runs exchange per-chunk hashes. */
#ifndef X87_COMMON_H
#define X87_COMMON_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

/* operations: OP_* are single x87 instructions, E_* are Core.dll functions / call-site sequences */
enum {
    OP_FSIN = 1, OP_FCOS, OP_FPTAN, OP_FPATAN, OP_FYL2X, OP_F2XM1, OP_FSCALE, OP_FSQRT,
    OP_FRNDINT, OP_FIST16, OP_FIST32, OP_FIST64, OP_FIST16NP, OP_FIST32NP,
    OP_FILD64, OP_FILD64_RT, OP_FILD64_MUL, OP_FILD64_ADD, OP_FLDCONST,
    E_SIN = 32,   /* appSin(double)                    fld; fsin                                     */
    E_COS,        /* appCos(double)                    fld; fcos                                     */
    E_TAN,        /* appTan(double)                    fld; fptan; fstp st(0)                        */
    E_ATAN,       /* appAtan(double)                   fld; fld1; fpatan                             */
    E_ATAN2,      /* appAtan2(double Y, double X)      fld Y; fld X; fpatan                          */
    E_SQRT,       /* appSqrt(double)                   fld; fsqrt                                    */
    E_EXP,        /* appExp(double)                    fldl2e; fmul; ...; f2xm1; fld1; faddp; fscale */
    E_LOGE,       /* appLoge(double)                   fldln2; fld; fyl2x                            */
    E_SINTAB,     /* FGlobalMath ctor: fild i; fadd st,st; fmul qword C; fstp/fld; appSin; fstp dword */
    E_SQRTTAB,    /* FGlobalMath ctor: fild i; fmul dword 2^-14; fstp/fld; appSqrt; fstp dword       */
    E_FTOL,       /* statically linked CRT _ftol2 (float -> int64 truncation)                        */
    OP_LIMIT
};

#pragma pack(push, 1)
typedef struct Rec {          /* 32 bytes */
    uint32_t op, aux, set, idx;
    uint64_t a, b;            /* raw bits: doubles, or int64 for fild */
} Rec;
typedef struct Out {          /* 48 bytes */
    uint8_t r80[10];          /* hardware only: full 80-bit ST(0) after the operation */
    uint16_t fsw;             /* status word after the operation (condition codes compared: C0-C3) */
    uint32_t r32;             /* result stored as float (fstp dword) */
    uint64_t r64;             /* result stored as double (fstp qword) */
    uint64_t i64;             /* integer result (fist/fistp/_ftol2) */
    uint64_t x;               /* engine sequences: the double argument actually passed (computed) */
    uint32_t flags;           /* bit0: fptan pushed 1.0 */
    uint32_t pad;
} Out;
#pragma pack(pop)

#define FSW_CC 0x4700u        /* C3 C2 C1 C0 */
#define FSW_C2 0x0400u

/* exhaustive float32 runs: every bit pattern of the float argument of a script native */
enum { X_SIN, X_COS, X_TAN, X_ATAN, X_SQRT, X_EXP, X_LOGE, X_COUNT };
static const char* const x_names[X_COUNT] = {"sin", "cos", "tan", "atan", "sqrt", "exp", "loge"};
#define CHUNK_BITS 20
#define NCHUNKS (1u << (32 - CHUNK_BITS))
#define CHUNK (1u << CHUNK_BITS)

typedef struct ChunkHash { uint64_t h32, h80, hcc; } ChunkHash;

static inline uint64_t fnv1a(uint64_t h, const void* p, size_t n) {
    const uint8_t* b = (const uint8_t*)p;
    for (size_t i = 0; i < n; i++) { h ^= b[i]; h *= 0x100000001B3ull; }
    return h;
}
#define FNV_INIT 0xCBF29CE484222325ull

/* deterministic generator (integer only, so both harnesses agree without floating point) */
static inline uint64_t splitmix64(uint64_t* s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

/* Affinity masks for performance (P) and efficiency (E) cores from EfficiencyClass (hybrid CPUs). */
static int core_masks(DWORD_PTR* pmask, DWORD_PTR* emask) {
    DWORD len = 0;
    *pmask = *emask = 0;
    GetLogicalProcessorInformationEx(RelationProcessorCore, NULL, &len);
    uint8_t* buf = (uint8_t*)malloc(len);
    if (!buf || !GetLogicalProcessorInformationEx(RelationProcessorCore, (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)buf, &len))
        return 0;
    int maxc = 0;
    for (DWORD off = 0; off < len;) {
        PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX e = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)(buf + off);
        if (e->Processor.EfficiencyClass > maxc) maxc = e->Processor.EfficiencyClass;
        off += e->Size;
    }
    for (DWORD off = 0; off < len;) {
        PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX e = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)(buf + off);
        if (e->Processor.EfficiencyClass == maxc) *pmask |= (DWORD_PTR)e->Processor.GroupMask[0].Mask;
        else *emask |= (DWORD_PTR)e->Processor.GroupMask[0].Mask;
        off += e->Size;
    }
    free(buf);
    return 1;
}

static int popcount_mask(DWORD_PTR m) { int n = 0; while (m) { n += (int)(m & 1); m >>= 1; } return n; }

/* "P", "E" or "all" -> mask (0 = no restriction) */
static DWORD_PTR select_mask(const char* which) {
    DWORD_PTR p, e;
    if (!which || !strcmp(which, "all") || !core_masks(&p, &e)) return 0;
    if (!strcmp(which, "P")) return p;
    if (!strcmp(which, "E")) return e ? e : p;
    return 0;
}

/* run fn(arg, thread index) on n threads (optionally pinned to mask), wait for all */
typedef DWORD(WINAPI* WorkerFn)(LPVOID);
static void run_threads(int n, WorkerFn fn, void* args, size_t arg_size, DWORD_PTR mask) {
    HANDLE th[64];
    if (n > 64) n = 64;
    for (int i = 0; i < n; i++) {
        th[i] = CreateThread(NULL, 0, fn, (uint8_t*)args + arg_size * (size_t)i, CREATE_SUSPENDED, NULL);
        if (mask) SetThreadAffinityMask(th[i], mask);
        ResumeThread(th[i]);
    }
    WaitForMultipleObjects((DWORD)n, th, TRUE, INFINITE);
    for (int i = 0; i < n; i++) CloseHandle(th[i]);
}

static int thread_count(DWORD_PTR mask) {
    if (mask) return popcount_mask(mask);
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return (int)si.dwNumberOfProcessors;
}

static void* read_file(const char* path, size_t* size) {
    FILE* f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    _fseeki64(f, 0, SEEK_END);
    long long n = _ftelli64(f);
    _fseeki64(f, 0, SEEK_SET);
    void* p = malloc((size_t)n + 1);
    if (!p || fread(p, 1, (size_t)n, f) != (size_t)n) { fprintf(stderr, "cannot read %s\n", path); exit(2); }
    fclose(f);
    *size = (size_t)n;
    return p;
}

static void write_file(const char* path, const void* p, size_t n) {
    FILE* f = fopen(path, "wb");
    if (!f || fwrite(p, 1, n, f) != n) { fprintf(stderr, "cannot write %s\n", path); exit(2); }
    fclose(f);
}

#endif
