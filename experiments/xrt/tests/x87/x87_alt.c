/* x87_alt.c - alternative x87 helper models, evaluated with the same lifted code as the runtime
 * (build_x87.cmd compiles the lifted functions again with the helper names remapped). They are
 * measurement prototypes for the report, not runtime code.
 *
 *   hx_*   execute the x87 instruction on the host x87 unit (x64 mode, ml64 helpers in x87_hw64.asm);
 *          the model register stays a double, so the 64-bit hardware result is rounded to 53 bits.
 *   p66_*  host libm, but fsin/fcos/fptan first reduce the argument with the 66-bit pi the x87 uses
 *          (pi66 = 0x3243F6A8885A308D3 * 2^-64), exactly, in 128-bit integer arithmetic.
 *          All other helpers are the runtime's. */
#include <intrin.h>
#include <math.h>
#include "xrt.h"

uint16_t x87d_fsin(double* st0);
uint16_t x87d_fcos(double* st0);
uint16_t x87d_fptan(double* st0);
uint16_t x87d_fpatan(double* st1, double* st0);
uint16_t x87d_fyl2x(double* st1, double* st0);
uint16_t x87d_f2xm1(double* st0);
uint16_t x87d_fscale(double* st0, double* st1);
uint16_t x87d_fsqrt(double* st0);

static void set_c2(CPU* c, uint16_t sw) { c->fsw = (uint16_t)((c->fsw & ~0x0400) | (sw & 0x0400)); }

void hx_fsin(CPU* c) { double v = *ST(c, 0); set_c2(c, x87d_fsin(&v)); *ST(c, 0) = v; }
void hx_fcos(CPU* c) { double v = *ST(c, 0); set_c2(c, x87d_fcos(&v)); *ST(c, 0) = v; }
void hx_fptan(CPU* c) {
    double v = *ST(c, 0);
    uint16_t sw = x87d_fptan(&v);
    set_c2(c, sw);
    *ST(c, 0) = v;
    if (!(sw & 0x0400)) fpush(c, 1.0);
}
void hx_fpatan(CPU* c) { double y = *ST(c, 1), x = *ST(c, 0); x87d_fpatan(&y, &x); *ST(c, 1) = y; fpop(c); }
void hx_fyl2x(CPU* c) { double y = *ST(c, 1), x = *ST(c, 0); x87d_fyl2x(&y, &x); *ST(c, 1) = y; fpop(c); }
void hx_f2xm1(CPU* c) { double v = *ST(c, 0); x87d_f2xm1(&v); *ST(c, 0) = v; }
void hx_fscale(CPU* c) { double v = *ST(c, 0), s = *ST(c, 1); x87d_fscale(&v, &s); *ST(c, 0) = v; }
void hx_fsqrt(CPU* c) { double v = *ST(c, 0); x87d_fsqrt(&v); *ST(c, 0) = v; }

/* ---------------------------------------------------------------- 66-bit-pi reduction */
static const uint64_t P_LO = 0x243F6A8885A308D3ull, P_HI = 0x3;   /* P = pi * 2^64 (66 bits) */

typedef struct U128 { uint64_t lo, hi; } U128;
static U128 u128_sub(U128 a, U128 b) { U128 r; r.lo = a.lo - b.lo; r.hi = a.hi - b.hi - (a.lo < b.lo); return r; }
static U128 u128_add(U128 a, U128 b) { U128 r; r.lo = a.lo + b.lo; r.hi = a.hi + b.hi + (r.lo < a.lo); return r; }
static U128 mul_kP(uint64_t k) {          /* k * P (k < 2^63; the product stays below 2^128 for |x| < 2^63) */
    U128 r;
    uint64_t h;
    r.lo = _umul128(k, P_LO, &h);
    r.hi = h + k * P_HI;
    return r;
}
static int s128_neg(U128 a) { return (int64_t)a.hi < 0; }
static U128 s128_negate(U128 a) { U128 z = {0, 0}; return u128_sub(z, a); }
static double s128_to_double_approx(U128 a) {
    int neg = s128_neg(a);
    if (neg) a = s128_negate(a);
    double v = (double)a.hi * 18446744073709551616.0 + (double)a.lo;
    return neg ? -v : v;
}
/* correctly rounded conversion of a signed 128-bit value scaled by 2^-65 */
static double s128_scaled_to_double(U128 a) {
    int neg = s128_neg(a);
    if (neg) a = s128_negate(a);
    if (!a.hi && !a.lo) return 0.0;
    unsigned long t;
    int top;
    if (a.hi) { _BitScanReverse64(&t, a.hi); top = 64 + (int)t; } else { _BitScanReverse64(&t, a.lo); top = (int)t; }
    uint64_t m;
    if (top > 63) {
        int sh = top - 63;
        uint64_t lost = a.lo & ((1ull << sh) - 1);
        m = (a.lo >> sh) | (a.hi << (64 - sh));
        if (lost) m |= 1;                      /* sticky: keeps the 64->53 conversion correctly rounded */
        double v = ldexp((double)m, sh - 65);
        return neg ? -v : v;
    }
    double v = ldexp((double)a.lo, -65);
    return neg ? -v : v;
}

/* |x| = (q-quadrant) * pi66/2 + r, |r| <= pi66/4; returns 0 if no reduction is needed (|x| <= pi/4) */
static int reduce66(double ax, double* r, int* q) {
    if (ax <= 0.78539816339744828) { *r = ax; *q = 0; return 0; }
    uint64_t b;
    memcpy(&b, &ax, 8);
    int E = (int)((b >> 52) & 0x7FF) - 1075;
    uint64_t M = (b & 0xFFFFFFFFFFFFFull) | (1ull << 52);
    int sh = E + 65;                           /* X = M * 2^sh, H = P * 2^-65  ->  X/P in units of H */
    U128 X;
    if (sh >= 64) { X.hi = M << (sh - 64); X.lo = 0; }
    else { X.lo = M << sh; X.hi = sh ? M >> (64 - sh) : 0; }
    uint64_t k = (uint64_t)nearbyint(ax * 0.63661977236758134);
    U128 R = u128_sub(X, mul_kP(k));
    double dk = nearbyint(s128_to_double_approx(R) / ((double)P_HI * 18446744073709551616.0 + (double)P_LO));
    k = (uint64_t)((int64_t)k + (int64_t)dk);
    R = u128_sub(X, mul_kP(k));
    U128 half = {(P_LO >> 1) | (P_HI << 63), P_HI >> 1};
    for (int it = 0; it < 4; it++) {
        if (!s128_neg(R) && (R.hi > half.hi || (R.hi == half.hi && R.lo > half.lo))) { k++; R = u128_sub(R, (U128){P_LO, P_HI}); }
        else if (s128_neg(R)) {
            U128 m = s128_negate(R);
            if (m.hi > half.hi || (m.hi == half.hi && m.lo > half.lo)) { k--; R = u128_add(R, (U128){P_LO, P_HI}); }
            else break;
        } else break;
    }
    *r = s128_scaled_to_double(R);
    *q = (int)(k & 3);
    return 1;
}

static int oor(CPU* c) {
    if (!(fabs(*ST(c, 0)) < 9223372036854775808.0)) { c->fsw |= 0x0400; return 1; }
    c->fsw &= (uint16_t)~0x0400;
    return 0;
}
void p66_fsin(CPU* c) {
    if (oor(c)) return;
    double x = *ST(c, 0), r;
    int q;
    if (!reduce66(fabs(x), &r, &q)) { *ST(c, 0) = sin(x); return; }
    double v = q == 0 ? sin(r) : q == 1 ? cos(r) : q == 2 ? -sin(r) : -cos(r);
    *ST(c, 0) = x < 0 ? -v : v;
}
void p66_fcos(CPU* c) {
    if (oor(c)) return;
    double x = *ST(c, 0), r;
    int q;
    if (!reduce66(fabs(x), &r, &q)) { *ST(c, 0) = cos(x); return; }
    *ST(c, 0) = q == 0 ? cos(r) : q == 1 ? -sin(r) : q == 2 ? -cos(r) : sin(r);
}
void p66_fptan(CPU* c) {
    if (oor(c)) return;
    double x = *ST(c, 0), r;
    int q;
    if (!reduce66(fabs(x), &r, &q)) *ST(c, 0) = tan(x);
    else {
        double v = (q & 1) ? -cos(r) / sin(r) : tan(r);
        *ST(c, 0) = x < 0 ? -v : v;
    }
    fpush(c, 1.0);
}
void p66_fpatan(CPU* c) { xrt_fpatan(c); }
void p66_fyl2x(CPU* c) { xrt_fyl2x(c); }
void p66_f2xm1(CPU* c) { xrt_f2xm1(c); }
void p66_fscale(CPU* c) { xrt_fscale(c); }
void p66_fsqrt(CPU* c) { xrt_fsqrt(c); }

/* ---------------------------------------------------------------- pfix: proposed portable helper set
 * p66 reduction, plus the SDM special-operand behaviour the runtime lacks:
 *   fsin/fcos/fptan  NaN -> quiet NaN, inf -> QNaN indefinite, C2 = 0 (SDM: #IA for +-inf; only a finite
 *                    |x| >= 2^63 sets C2 and leaves the operand). For such an operand fptan pushes that same NaN,
 *                    not 1.0 (measured: OP_FPTAN records compare the pushed value).
 *   fscale           NaN operands propagate; 0 * 2^+inf and inf * 2^-inf are #IA (QNaN indefinite);
 *                    no (int) conversion of a NaN or infinite scale */
static const uint64_t QNAN_INDEFINITE = 0xFFF8000000000000ull;
static double indefinite(void) { double d; memcpy(&d, &QNAN_INDEFINITE, 8); return d; }

/* 0: finite in range; 1: finite out of range (C2 = 1, operand unchanged); 2: NaN result written, C2 = 0 */
static int trig_special(CPU* c) {
    double x = *ST(c, 0);
    c->fsw &= (uint16_t)~0x0400;
    if (isnan(x)) { *ST(c, 0) = x + 0.0; return 2; }        /* quiets a signalling NaN, keeps the payload */
    if (isinf(x)) { *ST(c, 0) = indefinite(); return 2; }
    if (!(fabs(x) < 9223372036854775808.0)) { c->fsw |= 0x0400; return 1; }
    return 0;
}
void pfix_fsin(CPU* c) { int k = trig_special(c); if (!k) { p66_fsin(c); } }
void pfix_fcos(CPU* c) { int k = trig_special(c); if (!k) { p66_fcos(c); } }
void pfix_fptan(CPU* c) {
    int k = trig_special(c);
    if (k == 0) p66_fptan(c);                                /* pushes 1.0 */
    else if (k == 2) fpush(c, *ST(c, 0));
}
void pfix_fscale(CPU* c) {
    double v = *ST(c, 0), s = *ST(c, 1);
    if (isnan(v) || isnan(s)) { *ST(c, 0) = isnan(v) ? v + 0.0 : s + 0.0; return; }
    if (isinf(s)) {
        if (s > 0) *ST(c, 0) = v == 0 ? indefinite() : v * s;          /* +-inf (v finite nonzero or inf) */
        else *ST(c, 0) = isinf(v) ? indefinite() : v * 0.0;          /* +-0 */
        return;
    }
    xrt_fscale(c);
}
void pfix_fpatan(CPU* c) { xrt_fpatan(c); }
void pfix_fyl2x(CPU* c) { xrt_fyl2x(c); }
void pfix_f2xm1(CPU* c) { xrt_f2xm1(c); }
void pfix_fsqrt(CPU* c) { xrt_fsqrt(c); }
