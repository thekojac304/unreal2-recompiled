/* xrt_cpu.c - x87 helpers and the guest CPU-feature policy.
 *
 * x87 model: host doubles. The engine runs with control word 0x027F (53-bit precision, round to
 * nearest, all exceptions masked). With that setting add/sub/mul/div/fsqrt and the conversions give the
 * IEEE double result as long as no operand or intermediate leaves the double range: the hardware keeps
 * the 80-bit exponent range in registers, so overflow, underflow and subnormal intermediates (and fild of
 * integers wider than 53 bits) can differ - the instruction differential (experiments/xrt/tests/insn_diff)
 * counts these as "x87-not-a-double" cases. fsin/fcos/fptan reduce their argument like the hardware (see
 * below); fpatan/fyl2x/f2xm1 use host libm. C1 and the exception flags are not modelled. Any attempt to
 * leave the modelled control-word state is fatal (xrt_fldcw, _controlfp).
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

/* ---------------------------------------------------------------- fsin / fcos / fptan / fscale
 * The x87 reduces the argument of fsin/fcos/fptan with a 66-bit approximation of pi (pi66 = 0x3243F6A8885A308D3
 * * 2^-64), not with the exact pi a libm uses. For |x| > pi/4 the hardware results therefore differ from sin/cos/tan
 * of the exact argument - by up to ~1.2e8 float ulp for |x| >= 2^20, and by up to ~3e2 float ulp near multiples of
 * pi (FGlobalMath's sine-table entry for x = pi, measured). This model reduces exactly as the hardware does (128-bit
 * integer arithmetic) and evaluates the reduced argument with host libm. Special operands follow the SDM: NaN ->
 * quiet NaN, +-inf -> QNaN indefinite (both with C2 = 0; fptan then pushes that NaN too); only a finite |x| >= 2^63 sets C2
 * and leaves the operand unchanged.
 * Measured agreement, not exactness: see experiments/xrt/tests/x87 (all 2^32 float32 arguments and the engine's
 * own input sets compared with the hardware x87 at PC=53). Results are not bit-identical at double precision (the
 * hardware evaluates with a 64-bit significand; libm on the reduced double does not).
 * Adopted from the "pfix" prototype in experiments/xrt/tests/x87/x87_alt.c (parallel validation session). */
static const uint64_t PI66_LO = 0x243F6A8885A308D3ull, PI66_HI = 0x3;   /* pi66 * 2^64 (a 66-bit integer) */

typedef struct U128 { uint64_t lo, hi; } U128;
static U128 u128_sub(U128 a, U128 b) { U128 r; r.lo = a.lo - b.lo; r.hi = a.hi - b.hi - (a.lo < b.lo); return r; }
static U128 u128_add(U128 a, U128 b) { U128 r; r.lo = a.lo + b.lo; r.hi = a.hi + b.hi + (r.lo < a.lo); return r; }
static uint64_t mul64x64(uint64_t a, uint64_t b, uint64_t* hi) {
#if defined(_MSC_VER) && defined(_M_X64)
    return _umul128(a, b, hi);
#else
    unsigned __int128 p = (unsigned __int128)a * b;
    *hi = (uint64_t)(p >> 64);
    return (uint64_t)p;
#endif
}
static int top_bit64(uint64_t v) {               /* index of the highest set bit, v != 0 */
#if defined(_MSC_VER) && defined(_M_X64)
    unsigned long t;
    _BitScanReverse64(&t, v);
    return (int)t;
#else
    return 63 - __builtin_clzll(v);
#endif
}
static U128 mul_k_pi66(uint64_t k) {              /* k * pi66 * 2^64 for k < 2^63: below 2^128 for |x| < 2^63 */
    U128 r;
    uint64_t h;
    r.lo = mul64x64(k, PI66_LO, &h);
    r.hi = h + k * PI66_HI;
    return r;
}
static int s128_neg(U128 a) { return (int64_t)a.hi < 0; }
static U128 s128_negate(U128 a) { U128 z = {0, 0}; return u128_sub(z, a); }
static double s128_to_double_approx(U128 a) {
    int neg = s128_neg(a);
    double v;
    if (neg)
        a = s128_negate(a);
    v = (double)a.hi * 18446744073709551616.0 + (double)a.lo;
    return neg ? -v : v;
}
static double s128_scaled_to_double(U128 a) {     /* correctly rounded a * 2^-65 */
    int neg = s128_neg(a), top;
    double v;
    if (neg)
        a = s128_negate(a);
    if (!a.hi && !a.lo)
        return 0.0;
    top = a.hi ? 64 + top_bit64(a.hi) : top_bit64(a.lo);
    if (top > 63) {
        int sh = top - 63;
        uint64_t lost = a.lo & ((1ull << sh) - 1), m = (a.lo >> sh) | (a.hi << (64 - sh));
        if (lost)
            m |= 1;                               /* sticky bit keeps the 64 -> 53 bit conversion correctly rounded */
        v = ldexp((double)m, sh - 65);
    } else {
        v = ldexp((double)a.lo, -65);
    }
    return neg ? -v : v;
}
/* ax = q * pi66/2 + r (q mod 4), |r| <= pi66/4; returns 0 when no reduction is needed (ax <= pi/4) */
static int reduce_pi66(double ax, double* r, int* q) {
    uint64_t b, M, k;
    int E, sh, it;
    U128 X, R, half = {(PI66_LO >> 1) | (PI66_HI << 63), PI66_HI >> 1}, P = {PI66_LO, PI66_HI};
    double dk;
    if (ax <= 0.78539816339744828) {
        *r = ax;
        *q = 0;
        return 0;
    }
    memcpy(&b, &ax, 8);
    E = (int)((b >> 52) & 0x7FF) - 1075;
    M = (b & 0xFFFFFFFFFFFFFull) | (1ull << 52);
    sh = E + 65;                                   /* ax = M * 2^E; X = ax * 2^65, in which pi66/2 is the integer P */
    if (sh >= 64) {
        X.hi = M << (sh - 64);
        X.lo = 0;
    } else {
        X.lo = M << sh;
        X.hi = sh ? M >> (64 - sh) : 0;
    }
    k = (uint64_t)nearbyint(ax * 0.63661977236758134);
    R = u128_sub(X, mul_k_pi66(k));
    dk = nearbyint(s128_to_double_approx(R) / ((double)PI66_HI * 18446744073709551616.0 + (double)PI66_LO));
    k = (uint64_t)((int64_t)k + (int64_t)dk);
    R = u128_sub(X, mul_k_pi66(k));
    for (it = 0; it < 4; it++) {
        if (!s128_neg(R) && (R.hi > half.hi || (R.hi == half.hi && R.lo > half.lo))) {
            k++;
            R = u128_sub(R, P);
        } else if (s128_neg(R)) {
            U128 m = s128_negate(R);
            if (m.hi > half.hi || (m.hi == half.hi && m.lo > half.lo)) {
                k--;
                R = u128_add(R, P);
            } else {
                break;
            }
        } else {
            break;
        }
    }
    *r = s128_scaled_to_double(R);
    *q = (int)(k & 3);
    return 1;
}
static double qnan_indefinite(void) { uint64_t u = 0xFFF8000000000000ull; double d; memcpy(&d, &u, 8); return d; }
/* 0: finite in range (C2 = 0); 1: finite |x| >= 2^63 (C2 = 1, operand unchanged); 2: NaN/inf -> NaN, C2 = 0 */
static int trig_operand(CPU* c) {
    double x = *ST(c, 0);
    c->fsw &= (uint16_t)~0x0400;
    if (isnan(x)) {
        *ST(c, 0) = x + 0.0;                       /* quiets a signalling NaN, keeps sign and payload */
        return 2;
    }
    if (isinf(x)) {
        *ST(c, 0) = qnan_indefinite();
        return 2;
    }
    if (!(fabs(x) < 9223372036854775808.0)) {
        c->fsw |= 0x0400;
        return 1;
    }
    return 0;
}
void xrt_fsin(CPU* c) {
    double x, r, v;
    int q;
    if (trig_operand(c))
        return;
    x = *ST(c, 0);
    if (!reduce_pi66(fabs(x), &r, &q)) {
        *ST(c, 0) = sin(x);
        return;
    }
    v = q == 0 ? sin(r) : q == 1 ? cos(r) : q == 2 ? -sin(r) : -cos(r);
    *ST(c, 0) = x < 0 ? -v : v;
}
void xrt_fcos(CPU* c) {
    double x, r;
    int q;
    if (trig_operand(c))
        return;
    x = *ST(c, 0);
    if (!reduce_pi66(fabs(x), &r, &q)) {
        *ST(c, 0) = cos(x);
        return;
    }
    *ST(c, 0) = q == 0 ? cos(r) : q == 1 ? -sin(r) : q == 2 ? -cos(r) : sin(r);
}
void xrt_fptan(CPU* c) {
    double x, r, v;
    int q, k = trig_operand(c);
    if (k == 1)
        return;                                    /* out of range: no push */
    if (k == 2) {
        fpush(c, *ST(c, 0));                       /* NaN/inf operand: the hardware pushes the NaN result, not 1.0
                                                      (measured, experiments/xrt/tests/insn_diff) */
        return;
    }
    x = *ST(c, 0);
    if (!reduce_pi66(fabs(x), &r, &q)) {
        *ST(c, 0) = tan(x);
    } else {
        v = (q & 1) ? -cos(r) / sin(r) : tan(r);
        *ST(c, 0) = x < 0 ? -v : v;
    }
    fpush(c, 1.0);
}
void xrt_fpatan(CPU* c) { *ST(c, 1) = atan2(*ST(c, 1), *ST(c, 0)); fpop(c); }
void xrt_fyl2x(CPU* c) { *ST(c, 1) = *ST(c, 1) * log2(*ST(c, 0)); fpop(c); }
void xrt_f2xm1(CPU* c) { *ST(c, 0) = expm1(*ST(c, 0) * XRT_LN2); }
/* fscale: NaN operands propagate (quieted); 0 * 2^+inf and inf * 2^-inf are invalid (QNaN indefinite); an
 * infinite scale is never converted to an integer */
void xrt_fscale(CPU* c) {
    double v = *ST(c, 0), s = *ST(c, 1), t;
    int e;
    if (isnan(v) || isnan(s)) {
        *ST(c, 0) = isnan(v) ? v + 0.0 : s + 0.0;
        return;
    }
    if (isinf(s)) {
        if (s > 0)
            *ST(c, 0) = v == 0 ? qnan_indefinite() : v * s;
        else
            *ST(c, 0) = isinf(v) ? qnan_indefinite() : v * 0.0;
        return;
    }
    t = trunc(s);
    e = t > 100000.0 ? 100000 : t < -100000.0 ? -100000 : (int)t;
    *ST(c, 0) = ldexp(v, e);
}
void xrt_fsqrt(CPU* c) { *ST(c, 0) = sqrt(*ST(c, 0)); }

void xrt_fldcw(CPU* c, uint16_t cw) {
    if (((cw >> 8) & 3) != 2 || ((cw >> 10) & 3) != 0 || (cw & 0x3F) != 0x3F)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED,
                  "fldcw %04x leaves the modelled x87 state (53-bit precision, round-to-nearest, exceptions masked)", cw);
    /* Hardware reads reserved bit 6 as one, even after FLDCW 023f. GlmLib's
     * control-word helper clears it; native floor still sees 027f. Measured by
     * floor_boundary (including the full status word, not masked comparisons). */
    c->fcw = cw | 0x0040;
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

/* xlift --opt rdtsc on hosts without the instruction (xrt.h XRT_RDTSC): the generic timer counter */
#if defined(_M_ARM64)
uint64_t xrt_rdtsc64(void) { return (uint64_t)_ReadStatusReg(ARM64_CNTVCT); }
#elif defined(__aarch64__)
uint64_t xrt_rdtsc64(void) { uint64_t v; __asm__ volatile("mrs %0, cntvct_el0" : "=r"(v)); return v; }
#endif
