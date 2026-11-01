/* forms_equiv.c - the xrt.h helper twins used by xlift --opt sse against the helpers they replace, compiled with the
 * game build's flags (/O2 /fp:strict) against out/dev-init/runtime/xrt.h (forms_equiv.py builds and runs it):
 *   wrf32s / wrf64s    == wrf32b / wrf64b      stored bytes and the neighbouring bytes, unaligned, any bit pattern
 *   fcompareo/XFCOMPAREO == fcompare/XFCOMPARE C0/C2/C3 for special values (NaN payloads, +-0, +-inf, denormals)
 * Exit 0 when every case agrees. */
#include <stdio.h>
#include <stdlib.h>
#include "sse_mutants.h"   /* xrt.h and the broken variants: forms_equiv.py --mutate points a TWIN_* at one */
#ifndef TWIN_WR32
#define TWIN_WR32 wrf32s
#endif
#ifndef TWIN_WR64
#define TWIN_WR64 wrf64s
#endif
#ifndef TWIN_CMP
#define TWIN_CMP fcompareo
#endif
#ifndef TWIN_XCMP
#define TWIN_XCMP XFCOMPAREO
#endif

uint8_t* xrt_g;

static uint64_t s = 0x9E3779B97F4A7C15ull;
static uint32_t rnd(void) { s = s * 6364136223846793005ull + 1442695040888963407ull; return (uint32_t)(s >> 32); }
static uint64_t rnd64(void) { return ((uint64_t)rnd() << 32) | rnd(); }

int main(void) {
    static uint8_t mem_a[64], mem_b[64];
    uint64_t cases = 0, bad = 0;
    int i, j, k;
    for (i = 0; i < 2000000; i++) {
        uint32_t off = rnd() % 48, f32 = (i & 3) == 0 ? (0x7F800000u | (rnd() & 0x807FFFFFu)) : rnd();
        uint64_t f64 = (i & 3) == 1 ? (0x7FF0000000000000ull | (rnd64() & 0x800FFFFFFFFFFFFFull)) : rnd64();
        float f; double d;
        memcpy(&f, &f32, 4); memcpy(&d, &f64, 8);
        for (j = 0; j < 64; j++) mem_a[j] = mem_b[j] = (uint8_t)rnd();
        wrf32b(mem_a, off, f); TWIN_WR32(mem_b, off, f);
        wrf64b(mem_a, off + 8, d); TWIN_WR64(mem_b, off + 8, d);
        bad += memcmp(mem_a, mem_b, 64) != 0;
        cases++;
    }
    {
        static const uint64_t sp[] = {0, 0x8000000000000000ull, 0x7FF0000000000000ull, 0xFFF0000000000000ull,
                                      0x7FF8000000000000ull, 0xFFF8000000000001ull, 0x7FF0000000000001ull,
                                      0x0000000000000001ull, 0x800FFFFFFFFFFFFFull, 0x3FF0000000000000ull,
                                      0xBFF0000000000000ull, 0x3FF0000000000001ull, 0x7FEFFFFFFFFFFFFFull};
        enum { NSP = sizeof sp / sizeof sp[0] };
        for (i = 0; i < 1000000 + NSP * NSP; i++) {
            uint64_t ua = i < NSP * NSP ? sp[i / NSP] : (i & 1) ? sp[rnd() % NSP] : rnd64();
            uint64_t ub = i < NSP * NSP ? sp[i % NSP] : (i & 2) ? ua : rnd64();
            double a, b;
            CPU x, y;
            uint16_t fsw_, w1, w2;
            memcpy(&a, &ua, 8); memcpy(&b, &ub, 8);
            for (k = 0; k < 2; k++) {
                uint16_t init = (uint16_t)rnd();
                x.fsw = y.fsw = init;
                fcompare(&x, a, b); TWIN_CMP(&y, a, b); bad += x.fsw != y.fsw;
                fsw_ = init; XFCOMPARE(a, b); w1 = fsw_;
                fsw_ = init; TWIN_XCMP(a, b); w2 = fsw_;
                bad += w1 != w2;
                cases += 2;
            }
        }
    }
    printf("forms_equiv: %llu cases, %llu differences\n", (unsigned long long)cases, (unsigned long long)bad);
    return bad != 0;
}
