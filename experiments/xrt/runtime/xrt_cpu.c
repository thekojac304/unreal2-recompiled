/* xrt_cpu.c - x87 helpers and the guest CPU-feature policy.
 *
 * x87 model: host doubles. The engine runs with control word 0x027F (53-bit precision, round to
 * nearest, all exceptions masked); with that setting the basic operations and fsqrt round exactly
 * like IEEE doubles. Known deviations (documented in experiments/xrt/README.md): 80-bit exponent range
 * of intermediates, fild of integers wider than 53 bits, and the transcendental instructions
 * (fsin/fcos/fptan/fpatan/fyl2x/f2xm1), which use host libm here and can differ from the hardware in
 * the last bits. Any attempt to leave the modelled control-word state is fatal (xrt_fldcw, _controlfp).
 *
 * CPU-feature policy: CPUID is the host's, except that MMX, FXSR, SSE, SSE2 (leaf 1 EDX), the SIMD
 * bits of leaf 1 ECX, leaf 7 and the AMD MMX/3DNow extensions are cleared. Core's appInit then leaves
 * GIsMMX/GIsSSE at 0 and the engine selects its original scalar code paths (e.g. appMemcpy's
 * rep movsd fallback). Reaching an MMX/SSE instruction anyway is a lifted trap. */
#include <intrin.h>
#include "xrt_internal.h"

double xrt_fround(CPU* c, double v) {
    switch ((c->fcw >> 10) & 3) {
    case 0: return nearbyint(v);   /* host rounding mode is never changed from round-to-nearest-even */
    case 1: return floor(v);
    case 2: return ceil(v);
    default: return trunc(v);
    }
}

int64_t xrt_fist64(CPU* c, double v) {
    double r = xrt_fround(c, v);
    if (!(r >= -9223372036854775808.0 && r < 9223372036854775808.0))
        return INT64_MIN;              /* integer indefinite */
    return (int64_t)r;
}

int32_t xrt_fist32(CPU* c, double v) {
    double r = xrt_fround(c, v);
    if (!(r >= -2147483648.0 && r <= 2147483647.0))
        return INT32_MIN;
    return (int32_t)r;
}

int16_t xrt_fist16(CPU* c, double v) {
    double r = xrt_fround(c, v);
    if (!(r >= -32768.0 && r <= 32767.0))
        return INT16_MIN;
    return (int16_t)r;
}

/* fsin/fcos/fptan leave the operand alone and set C2 when |x| >= 2^63 */
static int trig_out_of_range(CPU* c) {
    double x = *ST(c, 0);
    if (!(fabs(x) < 9223372036854775808.0)) {
        c->fsw |= 0x0400;
        return 1;
    }
    c->fsw &= (uint16_t)~0x0400;
    return 0;
}
void xrt_fsin(CPU* c) { if (!trig_out_of_range(c)) *ST(c, 0) = sin(*ST(c, 0)); }
void xrt_fcos(CPU* c) { if (!trig_out_of_range(c)) *ST(c, 0) = cos(*ST(c, 0)); }
void xrt_fptan(CPU* c) {
    if (!trig_out_of_range(c)) {
        *ST(c, 0) = tan(*ST(c, 0));
        fpush(c, 1.0);
    }
}
void xrt_fpatan(CPU* c) { *ST(c, 1) = atan2(*ST(c, 1), *ST(c, 0)); fpop(c); }
void xrt_fyl2x(CPU* c) { *ST(c, 1) = *ST(c, 1) * log2(*ST(c, 0)); fpop(c); }
void xrt_f2xm1(CPU* c) { *ST(c, 0) = expm1(*ST(c, 0) * XRT_LN2); }
void xrt_fscale(CPU* c) {
    double s = trunc(*ST(c, 1));
    int e = s > 100000.0 ? 100000 : s < -100000.0 ? -100000 : (int)s;
    *ST(c, 0) = ldexp(*ST(c, 0), e);
}
void xrt_fsqrt(CPU* c) { *ST(c, 0) = sqrt(*ST(c, 0)); }

void xrt_fldcw(CPU* c, uint16_t cw) {
    if (((cw >> 8) & 3) != 2 || ((cw >> 10) & 3) != 0 || (cw & 0x3F) != 0x3F)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED,
                  "fldcw %04x leaves the modelled x87 state (53-bit precision, round-to-nearest, exceptions masked)", cw);
    c->fcw = cw;
}

static long cpuid_log_budget = 16;

void xrt_cpuid(CPU* c) {
    int r[4];
    uint32_t leaf = c->r[EAX], sub = c->r[ECX];
    __cpuidex(r, (int)leaf, (int)sub);
    if (leaf == 1) {
        r[3] &= ~((1 << 23) | (1 << 24) | (1 << 25) | (1 << 26));            /* MMX FXSR SSE SSE2 */
        r[2] &= ~((1 << 0) | (1 << 1) | (1 << 9) | (1 << 12) | (1 << 19) | (1 << 20) | (1 << 25) |
                  (1 << 27) | (1 << 28) | (1 << 29));                              /* SSE3..AVX, AES, OSXSAVE */
    } else if (leaf == 7) {
        r[1] = r[2] = r[3] = 0;
    } else if (leaf == 0x80000001u) {
        r[3] &= ~((1 << 22) | (1 << 23) | (1 << 24) | (1 << 30) | (1u << 31)); /* MMXExt MMX FXSR 3DNowExt 3DNow */
        r[2] &= ~((1 << 6) | (1 << 11) | (1 << 16));                              /* SSE4A XOP FMA4 */
    }
    c->r[EAX] = (uint32_t)r[0];
    c->r[EBX] = (uint32_t)r[1];
    c->r[ECX] = (uint32_t)r[2];
    c->r[EDX] = (uint32_t)r[3];
    if (cpuid_log_budget > 0) {
        cpuid_log_budget--;
        xrt_log("cpuid leaf=%08x -> eax=%08x ebx=%08x ecx=%08x edx=%08x (policy applied)", leaf, c->r[EAX], c->r[EBX],
                c->r[ECX], c->r[EDX]);
    }
}

void xrt_rdtsc(CPU* c) {
    uint64_t t = __rdtsc();
    c->r[EAX] = (uint32_t)t;
    c->r[EDX] = (uint32_t)(t >> 32);
}
