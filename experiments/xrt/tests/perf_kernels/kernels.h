/* kernels.h - shared by native.c (x86, runs the kernels on the CPU) and bench.c (x64/any host, runs the lifted C):
 * fixed guest addresses, the deterministic buffer fill and the result record. No game data anywhere. */
#ifndef PK_KERNELS_H
#define PK_KERNELS_H
#include <stdint.h>
#include <string.h>

#define PK_IN 0x20100000u                 /* read-only input bytes the kernels derive their working sets from */
#define PK_OUT 0x20200000u                /* scratch: working sets and results (hashed into the checksum) */
#define PK_BUF 0x40000u                   /* 256 KB each */
#define PK_STACK_LO 0x20300000u
#define PK_STACK_TOP 0x20340000u
#define PK_SENTINEL 0x0DEAD000u

typedef struct PkRec {
    char name[24];
    uint32_t n, status;                   /* status: 0 ok, 1 trap, 2 fatal/unsupported helper, 3 bad return, 4 unknown call, 5 fault */
    uint32_t eax, edx;                    /* the kernel's checksum (uint64 return) */
    uint64_t h_out;                       /* FNV-1a of the OUT buffer after the last call */
    double min_ms, med_ms;                /* per call, over the timed repetitions */
} PkRec;

static uint32_t pk_rng(uint64_t* s) {
    *s = *s * 6364136223846793005ull + 1442695040888963407ull;
    return (uint32_t)(*s >> 33);
}

static void pk_fill(uint8_t* in, uint8_t* out) {
    uint64_t s = 0x5EED5EED00C0FFEEull;
    uint32_t i;
    for (i = 0; i < PK_BUF; i++)
        in[i] = (uint8_t)pk_rng(&s);
    memset(out, 0, PK_BUF);
}

static uint64_t pk_hash(const uint8_t* p, uint32_t n) {
    uint64_t h = 1469598103934665603ull;
    uint32_t i;
    for (i = 0; i < n; i++)
        h = (h ^ p[i]) * 1099511628211ull;
    return h;
}
#endif
