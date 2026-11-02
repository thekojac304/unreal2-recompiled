/* native.c - x86 side of perf_kernels: calls the kernel DLL's exports on the CPU, records the checksums the lifted
 * runs must reproduce and the native timings they are compared against.
 *   native.exe PerfKernels.dll out.bin REPS name:N ... */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include "kernels.h"

typedef uint64_t (__cdecl *KernelFn)(const uint8_t*, uint8_t*, uint32_t, uint32_t);

static double now_ms(void) {
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f); QueryPerformanceCounter(&t);
    return (double)t.QuadPart * 1000.0 / (double)f.QuadPart;
}
static int cmp_double(const void* a, const void* b) { double x = *(const double*)a, y = *(const double*)b; return x < y ? -1 : x > y; }

int main(int argc, char** argv) {
    HMODULE m;
    FILE* fo;
    uint8_t *in, *out;
    uint32_t reps, k;
    int a;
    double* times;
    if (argc < 5) { fprintf(stderr, "usage: native PerfKernels.dll out.bin REPS name:N ...\n"); return 2; }
    m = LoadLibraryA(argv[1]);
    fo = fopen(argv[2], "wb");
    reps = (uint32_t)strtoul(argv[3], NULL, 0);
    in = (uint8_t*)VirtualAlloc((void*)(uintptr_t)PK_IN, PK_BUF, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    out = (uint8_t*)VirtualAlloc((void*)(uintptr_t)PK_OUT, PK_BUF, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!m || !fo || in != (uint8_t*)(uintptr_t)PK_IN || out != (uint8_t*)(uintptr_t)PK_OUT) { fprintf(stderr, "native: setup failed\n"); return 2; }
    times = (double*)calloc(reps ? reps : 1, sizeof *times);
    printf("%-10s %9s %9s %9s  %s\n", "kernel", "n", "min ms", "med ms", "checksum");
    for (a = 4; a < argc; a++) {
        PkRec r;
        char* colon = strchr(argv[a], ':');
        KernelFn fn;
        uint64_t ret;
        uint32_t n;
        if (!colon) return 2;
        memset(&r, 0, sizeof r);
        snprintf(r.name, sizeof r.name, "%.*s", (int)(colon - argv[a]), argv[a]);
        n = (uint32_t)strtoul(colon + 1, NULL, 0);
        fn = (KernelFn)GetProcAddress(m, r.name);
        if (!fn) { fprintf(stderr, "native: no export %s\n", r.name); return 2; }
        r.n = n;
        pk_fill(in, out);
        ret = fn(in, out, n, 0x1234u);
        r.eax = (uint32_t)ret; r.edx = (uint32_t)(ret >> 32);
        r.h_out = pk_hash(out, PK_BUF);
        for (k = 0; k < reps; k++) {
            double t0;
            pk_fill(in, out);
            t0 = now_ms();
            ret = fn(in, out, n, 0x1234u);
            times[k] = now_ms() - t0;
            if ((uint32_t)ret != r.eax || (uint32_t)(ret >> 32) != r.edx) r.status = 6;
        }
        if (reps) {
            qsort(times, reps, sizeof *times, cmp_double);
            r.min_ms = times[0]; r.med_ms = times[reps / 2];
        }
        fwrite(&r, sizeof r, 1, fo);
        printf("%-10s %9u %9.3f %9.3f  %08x%08x %s\n", r.name, n, r.min_ms, r.med_ms, r.edx, r.eax, r.status ? "NONDETERMINISTIC" : "");
    }
    fclose(fo);
    return 0;
}
