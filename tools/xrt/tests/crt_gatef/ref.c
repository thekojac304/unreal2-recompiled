/* ref.c - reference side of the gate-F CRT differential test (x86): the real msvcr70.dll, loaded from a sandbox
 * copy of the game's System directory. Only that DLL's code runs; nothing of the game.
 *   ref.exe <directory of msvcr70.dll> <corpus.txt> <results.txt>
 * _CIpow/_CIfmod run with the engine's x87 control word 0x027F and the default MXCSR (all exceptions masked), the
 * state in which msvcr70 picks its SSE2 pow; their st(0) is captured as an 80-bit value. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t Ptr;
static uint8_t arena[1 << 20];
static size_t arena_used;
static void* H(Ptr p) { return (void*)(uintptr_t)p; }
#include "gatef_core.h"

static void* p_qsort;
static double (__cdecl* p_atof)(const char*);
static void* p_CIpow;
static void* p_CIfmod;
static int (__cdecl* p_isnan)(double);
static int (__cdecl* p_toupper)(int);
static char* (__cdecl* p_strchr)(const char*, int);
static int (__cdecl* p_stricmp)(const char*, const char*);
static int (__cdecl* p_atoi)(const char*);

static void arena_reset(void) { arena_used = 0; }
static Ptr side_str(const uint8_t* s, size_t n) {
    uint8_t* p;
    arena_used = (arena_used + 15) & ~(size_t)15;
    if (arena_used + n + 1 > sizeof arena) {
        fprintf(stderr, "arena full\n");
        exit(2);
    }
    p = arena + arena_used;
    memcpy(p, s, n);
    p[n] = 0;
    arena_used += n + 1;
    return (Ptr)(uintptr_t)p;
}

/* an 80-bit x87 value as a double if it is exactly one; otherwise "x80:<hex>" */
static void describe80(const uint8_t r[10], char* out) {
    uint64_t m, bits;
    uint16_t se;
    int e;
    memcpy(&m, r, 8);
    memcpy(&se, r + 8, 2);
    e = se & 0x7FFF;
    bits = (uint64_t)(se >> 15) << 63;
    if (e == 0x7FFF) {                             /* inf or NaN */
        if ((m & 0x7FF) == 0) {
            bits |= 0x7FFull << 52 | (m >> 11 & 0xFFFFFFFFFFFFFull);
            sprintf(out, "%016llx", (unsigned long long)bits);
            return;
        }
    } else if (e == 0 && m == 0) {
        sprintf(out, "%016llx", (unsigned long long)bits);
        return;
    } else if (m >> 63) {
        int de = e - 16383;
        if (de >= -1022 && de <= 1023 && (m & 0x7FF) == 0) {
            bits |= (uint64_t)(de + 1023) << 52 | (m >> 11 & 0xFFFFFFFFFFFFFull);
            sprintf(out, "%016llx", (unsigned long long)bits);
            return;
        }
        if (de < -1022 && de >= -1074) {           /* a double denormal, if the low bits are zero */
            int sh = 11 + (-1022 - de);
            if (sh < 64 && (m & ((1ull << sh) - 1)) == 0) {
                bits |= m >> sh;
                sprintf(out, "%016llx", (unsigned long long)bits);
                return;
            }
        }
    }
    sprintf(out, "x80:%04x%016llx", se, (unsigned long long)m);
}

static void side_pow(int fmod_, uint64_t xb, uint64_t yb, char* out) {
    double x, y;
    uint8_t r[10];
    void* f = fmod_ ? p_CIfmod : p_CIpow;
    unsigned short cw = 0x027F, sw;
    memcpy(&x, &xb, 8);
    memcpy(&y, &yb, 8);
    __asm {
        fninit
        fldcw cw
        fld x
        fld y
        call f
        fstp tbyte ptr r
        fnstsw sw
    }
    describe80(r, out);
    /* the stack must be empty again: TOP (bits 11-13 of the status word) back at 0 */
    if ((sw >> 11) & 7)
        strcat(out, " stack-imbalance");
}

static uint64_t side_atof(Ptr s) {
    double d = p_atof((const char*)H(s));
    uint64_t b;
    memcpy(&b, &d, 8);
    return b;
}
static int32_t side_isnan(uint64_t bits) {
    double d;
    memcpy(&d, &bits, 8);
    return p_isnan(d);
}
static int32_t side_toupper(int32_t ch) { return p_toupper(ch); }
static Ptr side_strchr(Ptr s, int32_t ch) { return (Ptr)(uintptr_t)p_strchr((const char*)H(s), ch); }
static int32_t side_stricmp(Ptr a, Ptr b) { return p_stricmp((const char*)H(a), (const char*)H(b)); }
static int32_t side_atoi(Ptr s) { return p_atoi((const char*)H(s)); }

static int __cdecl ref_compare(const void* a, const void* b) { return qs_compare((Ptr)(uintptr_t)a, (Ptr)(uintptr_t)b); }
static void side_qsort(Ptr base, uint32_t n, uint32_t width) {
    ((void (__cdecl*)(void*, size_t, size_t, int (__cdecl*)(const void*, const void*)))p_qsort)(H(base), n, width,
                                                                                                 ref_compare);
}

static void* need(HMODULE m, const char* name) {
    void* f = (void*)GetProcAddress(m, name);
    if (!f) {
        fprintf(stderr, "msvcr70.dll has no %s\n", name);
        exit(2);
    }
    return f;
}

int main(int argc, char** argv) {
    HMODULE m;
    char path[MAX_PATH];
    if (argc != 4) {
        fprintf(stderr, "usage: ref.exe <msvcr70 directory> <corpus> <results>\n");
        return 2;
    }
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    snprintf(path, sizeof path, "%s\\msvcr70.dll", argv[1]);
    m = LoadLibraryA(path);
    if (!m) {
        fprintf(stderr, "cannot load %s (%lu)\n", path, GetLastError());
        return 2;
    }
    p_qsort = need(m, "qsort");
    p_atof = (double (__cdecl*)(const char*))need(m, "atof");
    p_CIpow = need(m, "_CIpow");
    p_CIfmod = need(m, "_CIfmod");
    p_isnan = (int (__cdecl*)(double))need(m, "_isnan");
    p_toupper = (int (__cdecl*)(int))need(m, "toupper");
    p_strchr = (char* (__cdecl*)(const char*, int))need(m, "strchr");
    p_stricmp = (int (__cdecl*)(const char*, const char*))need(m, "_stricmp");
    p_atoi = (int (__cdecl*)(const char*))need(m, "atoi");
    run_corpus(argv[2], argv[3]);
    return 0;
}
