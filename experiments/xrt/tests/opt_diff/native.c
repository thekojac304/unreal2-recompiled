/* native.c - x86 side of opt_diff: calls the owned test DLL's exports on the CPU.
 *   native.exe OptCases.dll out.bin NVEC name...                                                        */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include "opt_diff.h"

typedef uint64_t (__cdecl *TestFn)(const uint8_t*, uint8_t*, uint32_t, uint32_t);

int main(int argc, char** argv) {
    HMODULE m;
    FILE* fo;
    uint8_t *in, *out;
    uint32_t nvec, f, k;
    if (argc < 5)
        return 2;
    m = LoadLibraryA(argv[1]);
    fo = fopen(argv[2], "wb");
    nvec = (uint32_t)strtoul(argv[3], NULL, 0);
    in = (uint8_t*)VirtualAlloc((void*)(uintptr_t)OD_IN, OD_BUF, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    out = (uint8_t*)VirtualAlloc((void*)(uintptr_t)OD_OUT, OD_BUF, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!m || !fo || in != (uint8_t*)(uintptr_t)OD_IN || out != (uint8_t*)(uintptr_t)OD_OUT) {
        fprintf(stderr, "native: setup failed\n");
        return 2;
    }
    for (f = 0; f < (uint32_t)argc - 4; f++) {
        TestFn fn = (TestFn)GetProcAddress(m, argv[4 + f]);
        if (!fn) {
            fprintf(stderr, "native: no export %s\n", argv[4 + f]);
            return 2;
        }
        for (k = 0; k < nvec; k++) {
            OdVec v;
            OdRec r;
            uint64_t ret;
            od_vector(f, k, in, out, &v);
            ret = fn(in, out, v.n, v.seed);
            memset(&r, 0, sizeof r);
            r.fn = f;
            r.vec = k;
            r.eax = (uint32_t)ret;
            r.edx = (uint32_t)(ret >> 32);
            r.h_in = od_hash(in, OD_BUF);
            r.h_out = od_hash(out, OD_BUF);
            fwrite(&r, sizeof r, 1, fo);
        }
    }
    fclose(fo);
    printf("native: %u functions x %u vectors\n", (unsigned)(argc - 4), nvec);
    return 0;
}
