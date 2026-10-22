/* xrt_fmt.c - msvcr70 _woutput (the wide printf engine behind wprintf and _vsnwprintf), reading the format
 * and the arguments from guest memory; and its narrow build _output (sprintf), see xrt_output below.
 *
 * Mirrors the old CRT rather than C99/UCRT behaviour, including its quirks:
 *   - parsing is the CRT's character-class state machine: a character that is not valid in the current
 *     state ends the specification and is printed ("%5*d" -> "*d", "%y" -> "y"); 'B' is in the type class
 *     but has no conversion, so it re-emits the previous conversion's text (before any conversion that
 *     text is uninitialised in the CRT - undefined; here it is empty)
 *   - integer precision is capped at 512; %p always uses precision 8; %Z prints counted strings
 *   - floating point: __dtold + $I10_OUTPUT produce 17 significant digits with the CRT's 80/96-bit
 *     arithmetic (power-of-ten tables, truncated multiplication), rounded half-up on an 18th computed
 *     digit; then _fptostr rounds half-up on that decimal string and _cftoe/_cftof/_cftog lay it out.
 *     Exponents have at least 3 digits (e+006); INF/NaN print as 1.#INF, 1.#QNAN, 1.#SNAN, -1.#IND and
 *     go through the same string rounding; -0.0 prints without a sign
 *   - %s is a wide string and %S / %hs a narrow one (wide printf family); NULL prints "(null)"
 *   - output goes through a character sink with the CRT's charsout rule: a failed write sets the count to
 *     -1, a later successful write counts up from there, padding and wide text stop at a failure, the
 *     narrow-text loop does not, and the format loop ends once the count is negative
 * Narrow text is widened byte-for-byte and stops at a NUL byte (mbtowc in the "C" locale; the guest
 * never calls setlocale). Verified against the real msvcr70.dll by experiments/xrt/tests/crt_diff. */
#include <stdlib.h>
#include "xrt_internal.h"

/* ---------------------------------------------------------------- 12-byte long doubles (_LDBL12)
 * w[0..4]: 80-bit mantissa, least significant word first, explicit leading bit in w[4] bit 15;
 * w[5]: sign (bit 15) and exponent (bias 0x3FFF). */
typedef struct Ld12 { uint16_t w[6]; } Ld12;

/* 10^(d*8^g), d = 1..7, g = 0..2: 64-bit mantissa rounded to nearest in w[1..4] with the next 16 bits of
 * the value (rounded) in w[0], as the CRT stores them. Generated from exact arithmetic by
 * tests/crt_diff/i10_model.py (which also checks them against the DLL). |exponent| < 512 covers doubles. */
static const Ld12 pow10_pos[21] = {
    {{0x0000, 0x0000, 0x0000, 0x0000, 0xA000, 0x4002}},   /* 1e1 */
    {{0x0000, 0x0000, 0x0000, 0x0000, 0xC800, 0x4005}},   /* 1e2 */
    {{0x0000, 0x0000, 0x0000, 0x0000, 0xFA00, 0x4008}},   /* 1e3 */
    {{0x0000, 0x0000, 0x0000, 0x0000, 0x9C40, 0x400C}},   /* 1e4 */
    {{0x0000, 0x0000, 0x0000, 0x0000, 0xC350, 0x400F}},   /* 1e5 */
    {{0x0000, 0x0000, 0x0000, 0x0000, 0xF424, 0x4012}},   /* 1e6 */
    {{0x0000, 0x0000, 0x0000, 0x8000, 0x9896, 0x4016}},   /* 1e7 */
    {{0x0000, 0x0000, 0x0000, 0x2000, 0xBEBC, 0x4019}},   /* 1e8 */
    {{0x0000, 0x0000, 0x0400, 0xC9BF, 0x8E1B, 0x4034}},   /* 1e16 */
    {{0x0000, 0xA100, 0xCCED, 0x1BCE, 0xD3C2, 0x404E}},   /* 1e24 */
    {{0xF020, 0xB59E, 0x2B70, 0xADA8, 0x9DC5, 0x4069}},   /* 1e32 */
    {{0x5DD0, 0x25FD, 0x1AE5, 0x4F8E, 0xEB19, 0x4083}},   /* 1e40 */
    {{0x9671, 0x95D7, 0x0E43, 0x8D05, 0xAF29, 0x409E}},   /* 1e48 */
    {{0xBFF9, 0x44A0, 0x81ED, 0x8F12, 0x8281, 0x40B9}},   /* 1e56 */
    {{0x3CBF, 0xA6D5, 0xFFCF, 0x1F49, 0xC278, 0x40D3}},   /* 1e64 */
    {{0xC66F, 0x8CE0, 0x80E9, 0x47C9, 0x93BA, 0x41A8}},   /* 1e128 */
    {{0x85BC, 0x556B, 0x3927, 0xF78D, 0xE070, 0x427C}},   /* 1e192 */
    {{0xDDBC, 0xDE8E, 0x9DF9, 0xEBFB, 0xAA7E, 0x4351}},   /* 1e256 */
    {{0xE6A1, 0xE376, 0xF2CC, 0x2F29, 0x8184, 0x4426}},   /* 1e320 */
    {{0x1028, 0xAA17, 0xAEF8, 0xE310, 0xC4C5, 0x44FA}},   /* 1e384 */
    {{0xA7EB, 0xF3D4, 0xEBF7, 0x4AE1, 0x957A, 0x45CF}},   /* 1e448 */
};
static const Ld12 pow10_neg[21] = {
    {{0xCCCD, 0xCCCD, 0xCCCC, 0xCCCC, 0xCCCC, 0x3FFB}},   /* 1e-1 */
    {{0x3D71, 0xD70A, 0x70A3, 0x0A3D, 0xA3D7, 0x3FF8}},   /* 1e-2 */
    {{0x645A, 0xDF3B, 0x8D4F, 0x6E97, 0x8312, 0x3FF5}},   /* 1e-3 */
    {{0xD3C3, 0x652C, 0xE219, 0x1758, 0xD1B7, 0x3FF1}},   /* 1e-4 */
    {{0x0FD0, 0x8423, 0x1B47, 0xAC47, 0xA7C5, 0x3FEE}},   /* 1e-5 */
    {{0xA640, 0x69B6, 0xAF6C, 0xBD05, 0x8637, 0x3FEB}},   /* 1e-6 */
    {{0x3D33, 0x42BC, 0xE57A, 0x94D5, 0xD6BF, 0x3FE7}},   /* 1e-7 */
    {{0xFDC2, 0xCEFD, 0x8461, 0x7711, 0xABCC, 0x3FE4}},   /* 1e-8 */
    {{0x4C2F, 0xE15B, 0xC44D, 0x94BE, 0xE695, 0x3FC9}},   /* 1e-16 */
    {{0xC492, 0x3B53, 0x4475, 0x14CD, 0x9ABE, 0x3FAF}},   /* 1e-24 */
    {{0x67DE, 0x94BA, 0x4539, 0x1EAD, 0xCFB1, 0x3F94}},   /* 1e-32 */
    {{0x2324, 0xE2C6, 0xBABC, 0x313B, 0x8B61, 0x3F7A}},   /* 1e-40 */
    {{0x5561, 0xC159, 0xB17E, 0x7C53, 0xBB12, 0x3F5F}},   /* 1e-48 */
    {{0xEED7, 0x8D2F, 0xBE06, 0x8592, 0xFB15, 0x3F44}},   /* 1e-56 */
    {{0x3F24, 0xE9A5, 0xA539, 0xEA27, 0xA87F, 0x3F2A}},   /* 1e-64 */
    {{0xAC7D, 0xE4A1, 0x64BC, 0x467C, 0xDDD0, 0x3E55}},   /* 1e-128 */
    {{0x7B63, 0xCC06, 0x5423, 0x8377, 0x91FF, 0x3D81}},   /* 1e-192 */
    {{0xFA91, 0x193A, 0x637A, 0x4325, 0xC031, 0x3CAC}},   /* 1e-256 */
    {{0x8921, 0x38D1, 0x4782, 0xB897, 0xFD00, 0x3BD7}},   /* 1e-320 */
    {{0x88DC, 0x0858, 0xB11B, 0xE3E8, 0xA686, 0x3B03}},   /* 1e-384 */
    {{0x84C6, 0x4245, 0xB607, 0x7599, 0xDB37, 0x3A2E}},   /* 1e-448 */
};
/* 1/10 truncated to 80 bits ($I10_OUTPUT's correction factor) */
static const Ld12 ld12_one_tenth = {{0xCCCC, 0xCCCC, 0xCCCC, 0xCCCC, 0xCCCC, 0x3FFB}};

static int s16(uint32_t v) { v &= 0xFFFFu; return v >= 0x8000u ? (int)v - 0x10000 : (int)v; }
static uint32_t ld_dw(const Ld12* x, int k) { return (uint32_t)x->w[k] | (uint32_t)x->w[k + 1] << 16; }
static void ld_setdw(Ld12* x, int k, uint32_t v) { x->w[k] = (uint16_t)v; x->w[k + 1] = (uint16_t)(v >> 16); }

static void shl12(Ld12* x) {
    uint16_t c = 0, n;
    int k;
    for (k = 0; k < 6; k++) {
        n = (uint16_t)(x->w[k] >> 15);
        x->w[k] = (uint16_t)(x->w[k] << 1 | c);
        c = n;
    }
}
static void shr12(Ld12* x) {
    uint16_t c = 0, n;
    int k;
    for (k = 5; k >= 0; k--) {
        n = (uint16_t)(x->w[k] & 1);
        x->w[k] = (uint16_t)(x->w[k] >> 1 | c << 15);
        c = n;
    }
}
static void add12(Ld12* x, const Ld12* y) {   /* 96-bit addition, carry out of the top is lost */
    uint32_t c = 0, s;
    int k;
    for (k = 0; k < 6; k++) {
        s = (uint32_t)x->w[k] + y->w[k] + c;
        x->w[k] = (uint16_t)s;
        c = s >> 16;
    }
}
static void ld12_inf(Ld12* x, uint16_t sign) {
    memset(x, 0, sizeof *x);
    x->w[4] = 0x8000;
    x->w[5] = (uint16_t)(0x7FFF | sign);
}

/* __ld12mul: x *= y. Only the partial products of words i+j >= 4 are summed (a truncated 80x80-bit
 * product, carries into the word above without further propagation, as the CRT does), then the 96-bit
 * result is normalised and rounded to 80 bits (nearest, ties to even; sticky bits only from denormalising). */
static void ld12mul(Ld12* x, const Ld12* y) {
    uint16_t ex = x->w[5], ey = y->w[5], sign = (uint16_t)((ex ^ ey) & 0x8000);
    uint16_t t[7] = {0};
    Ld12 tm;
    uint32_t es;
    unsigned sticky = 0;
    int i, j;
    ex &= 0x7FFF;
    ey &= 0x7FFF;
    es = (uint32_t)ex + ey;
    if (ex >= 0x7FFF || ey >= 0x7FFF || (uint16_t)es > 0xBFFD) {
        ld12_inf(x, sign);
        return;
    }
    if ((uint16_t)es <= 0x3FBF) {
        memset(x, 0, sizeof *x);
        return;
    }
    if (ex == 0) {
        es++;
        if (!(ld_dw(x, 4) & 0x7FFFFFFFu) && !ld_dw(x, 2) && !ld_dw(x, 0)) {
            x->w[5] = sign;
            return;
        }
    }
    if (ey == 0) {
        es++;
        if (!(ld_dw(y, 4) & 0x7FFFFFFFu) && !ld_dw(y, 2) && !ld_dw(y, 0)) {
            memset(x, 0, sizeof *x);
            return;
        }
    }
    for (i = 0; i < 5; i++)
        for (j = 0; j < 5 - i; j++) {
            uint32_t prod = (uint32_t)x->w[i + j] * y->w[4 - j];
            uint32_t r0 = (uint32_t)t[i] | (uint32_t)t[i + 1] << 16, r = r0 + prod;
            t[i] = (uint16_t)r;
            t[i + 1] = (uint16_t)(r >> 16);
            if (r < r0)
                t[i + 2]++;           /* t[6] would only be reached by a carry out of 96 bits: impossible */
        }
    memcpy(tm.w, t, sizeof tm.w);
    es += 0xC002u;                    /* - 0x3FFE in the low 16 bits */
    if (s16(es) > 0) {
        while (!(tm.w[5] & 0x8000)) {
            shl12(&tm);
            es += 0xFFFFu;
            if (s16(es) <= 0)
                break;
        }
    }
    if (s16(es) <= 0) {
        es += 0xFFFFu;
        if (s16(es) < 0) {
            uint16_t n = (uint16_t)(0u - es);
            es += n;
            for (; n; n--) {
                if (tm.w[0] & 1)
                    sticky++;
                shr12(&tm);
            }
            if (sticky)
                tm.w[0] |= 1;
        }
    }
    if (tm.w[0] > 0x8000 || (ld_dw(&tm, 0) & 0x1FFFFu) == 0x18000u) {
        if (ld_dw(&tm, 1) == 0xFFFFFFFFu) {
            ld_setdw(&tm, 1, 0);
            if (ld_dw(&tm, 3) == 0xFFFFFFFFu) {
                ld_setdw(&tm, 3, 0);
                if (tm.w[5] == 0xFFFF) {
                    es++;
                    tm.w[5] = 0x8000;
                } else {
                    tm.w[5]++;
                }
            } else {
                ld_setdw(&tm, 3, ld_dw(&tm, 3) + 1);
            }
        } else {
            ld_setdw(&tm, 1, ld_dw(&tm, 1) + 1);
        }
    }
    if ((uint16_t)es >= 0x7FFF) {
        ld12_inf(x, sign);
        return;
    }
    memcpy(x->w, tm.w + 1, 5 * sizeof x->w[0]);
    x->w[5] = (uint16_t)(es | sign);
}

/* __multtenpow12(x, pw, 1) */
static void multtenpow12(Ld12* x, int pw) {
    const Ld12* tab = pow10_pos;
    int g = 0;
    if (pw < 0) {
        pw = -pw;
        tab = pow10_neg;
    }
    for (; pw; pw >>= 3, g++) {
        int last3 = pw & 7;
        Ld12 y;
        if (!last3)
            continue;
        if (g > 2)
            xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "formatter: power of ten beyond the double range");
        y = tab[g * 7 + last3 - 1];
        if (y.w[0] >= 0x8000)         /* "unround": the stored 64-bit mantissa was rounded up */
            ld_setdw(&y, 1, ld_dw(&y, 1) - 1);
        ld12mul(x, &y);
    }
}

/* __multtenpow12(x, pw, 1) on a 12-byte long double given as six 16-bit words, for the atof port in
 * hle_msvcr70.c (the same tables and multiplication as the DLL's __strgtold12 uses); |pw| < 512 */
void xrt_ld12_multtenpow12(uint16_t w[6], int pw) {
    Ld12 x;
    memcpy(x.w, w, sizeof x.w);
    multtenpow12(&x, pw);
    memcpy(w, x.w, sizeof x.w);
}

/* ---------------------------------------------------------------- double -> digits (_fltout2) */
typedef struct StrFlt { char sign; int decpt; char man[24]; } StrFlt;

/* $I10_OUTPUT(ld, 17, 0) of __dtold(x) */
static void fltout(double x, StrFlt* f) {
    uint64_t bits;
    uint32_t manhi, manlo, msb = 0x80000000u, mh, ml;
    unsigned dexp;
    uint16_t sign, expn;
    Ld12 v;
    uint32_t r;
    int ir, ndigits = 17, k, p, ub;
    char dig[24];
    memcpy(&bits, &x, 8);
    /* __dtold: the sign of a zero is dropped */
    dexp = (unsigned)(bits >> 52) & 0x7FF;
    sign = (uint16_t)((bits >> 48) & 0x8000);
    manhi = (uint32_t)(bits >> 32) & 0xFFFFF;
    manlo = (uint32_t)bits;
    if (dexp == 0x7FF) {
        expn = 0x7FFF;
    } else if (dexp == 0) {
        if (!manhi && !manlo) {
            f->sign = ' ';
            f->decpt = 0;
            strcpy(f->man, "0");
            return;
        }
        expn = 0x3FFF - 0x3FF + 1;
        msb = 0;
    } else {
        expn = (uint16_t)(dexp + 0x3FFF - 0x3FF);
    }
    mh = manhi << 11 | msb | manlo >> 21;
    ml = manlo << 11;
    while (!(mh & 0x80000000u)) {
        mh = mh << 1 | ml >> 31;
        ml <<= 1;
        expn--;
    }
    /* $I10_OUTPUT */
    f->sign = sign ? '-' : ' ';
    if (expn == 0x7FFF) {
        f->decpt = 1;
        if (mh == 0x80000000u && !ml)
            strcpy(f->man, "1#INF");
        else if (!(mh & 0x40000000u))
            strcpy(f->man, "1#SNAN");
        else if (sign && mh == 0xC0000000u && !ml)
            strcpy(f->man, "1#IND");
        else
            strcpy(f->man, "1#QNAN");
        return;
    }
    /* low estimate of 1 + log10(x) from the exponent and the top mantissa byte (16.16 fixed point) */
    r = (uint32_t)expn * 0x4D10u + ((uint32_t)(expn >> 8) + 2u * (mh >> 24)) * 0x4Du - 0x134312F4u;
    ir = s16(r >> 16);
    v.w[0] = 0;
    ld_setdw(&v, 1, ml);
    ld_setdw(&v, 3, mh);
    v.w[5] = expn;
    multtenpow12(&v, -ir);
    if (v.w[5] >= 0x3FFF) {           /* the estimate was one too low: scale into [0.1, 1) */
        ir++;
        ld12mul(&v, &ld12_one_tenth);
    }
    f->decpt = ir;
    ub = (int)v.w[5] - 0x3FFE;
    v.w[5] = 0;
    for (k = 0; k < 8; k++)
        shl12(&v);
    if (ub < 0)
        for (k = (-ub) & 0xFF; k > 0; k--)
            shr12(&v);
    for (k = 0; k <= ndigits; k++) {  /* digits from the 96-bit fixed point (88 fraction bits) */
        Ld12 t = v;
        shl12(&v);
        shl12(&v);
        add12(&v, &t);
        shl12(&v);
        dig[k] = (char)('0' + (v.w[5] >> 8));
        v.w[5] &= 0x00FF;
    }
    p = ndigits - 1;
    if (dig[ndigits] >= '5') {        /* round half-up on the 18th digit */
        while (p >= 0 && dig[p] == '9')
            dig[p--] = '0';
        if (p < 0) {
            p = 0;
            f->decpt++;
        }
        dig[p]++;
    } else {
        while (p >= 0 && dig[p] == '0')
            p--;
        if (p < 0) {
            f->sign = ' ';
            f->decpt = 0;
            strcpy(f->man, "0");
            return;
        }
    }
    memcpy(f->man, dig, (size_t)p + 1);
    f->man[p + 1] = 0;
}

/* ---------------------------------------------------------------- digits -> text (_cfltcvt) */
static void shift_right(char* s, int dist) {
    if (dist)
        memmove(s + dist, s, strlen(s) + 1);
}

/* _fptostr: `digits` digits of the mantissa (0-padded) after a leading '0', rounded half-up on the next
 * mantissa character; the leading position absorbs a carry (then decpt is incremented) or is removed */
static void fptostr(char* buf, int digits, StrFlt* f) {
    char* p = buf + 1;
    const char* m = f->man;
    buf[0] = '0';
    for (; digits > 0; digits--)
        *p++ = *m ? *m++ : '0';
    *p = 0;
    if (digits >= 0 && *m >= '5') {
        p--;
        while (*p == '9')
            *p-- = '0';
        *p += 1;
    }
    if (buf[0] == '1')
        f->decpt++;
    else
        memmove(buf, buf + 1, strlen(buf + 1) + 1);
}

static void cftoe2(char* buf, int ndec, int caps, const StrFlt* f, int g_fmt) {
    char* p = buf;
    if (g_fmt)
        shift_right(buf + (f->sign == '-'), ndec > 0);
    if (f->sign == '-')
        *p++ = '-';
    if (ndec > 0) {
        p[0] = p[1];
        *++p = '.';
    }
    p = strcpy(p + (g_fmt == 0) + ndec, "e+000");
    if (caps)
        *p = 'E';
    p++;
    if (f->man[0] != '0') {
        int e = f->decpt - 1;
        if (e < 0) {
            e = -e;
            *p = '-';
        }
        p++;
        if (e >= 100) {
            *p = (char)(*p + e / 100);
            e %= 100;
        }
        p++;
        if (e >= 10) {
            *p = (char)(*p + e / 10);
            e %= 10;
        }
        p[1] = (char)(p[1] + e);
    }
}

static void cftof2(char* buf, int ndec, const StrFlt* f, int g_fmt) {
    char* p = buf;
    if (g_fmt && f->decpt - 1 == ndec) {
        char* q = buf + (f->sign == '-') + f->decpt - 1;
        q[0] = '0';
        q[1] = 0;
    }
    if (f->sign == '-')
        *p++ = '-';
    if (f->decpt <= 0) {
        shift_right(p, 1);
        *p++ = '0';
    } else {
        p += f->decpt;
    }
    if (ndec > 0) {
        shift_right(p, 1);
        *p++ = '.';
        if (f->decpt < 0) {
            int n = -f->decpt;
            if (g_fmt || ndec >= n)
                ndec = n;
            shift_right(p, ndec);
            memset(p, '0', (size_t)ndec);
        }
    }
}

/* _cfltcvt(x, buf, ch, precision, caps) for ch = 'e', 'f' or 'g'; buf receives the text with its sign */
static void cfltcvt(double x, char* buf, char ch, int prec, int caps) {
    StrFlt f;
    fltout(x, &f);
    if (ch == 'e') {
        fptostr(buf + (f.sign == '-') + (prec > 0), prec + 1, &f);
        cftoe2(buf, prec, caps, &f, 0);
    } else if (ch == 'f') {
        fptostr(buf + (f.sign == '-'), f.decpt + prec, &f);
        cftof2(buf, prec, &f, 0);
    } else {
        int mag0 = f.decpt - 1, mag;
        char* p = buf + (f.sign == '-');
        fptostr(p, prec, &f);
        mag = f.decpt - 1;
        if (mag < -4 || mag >= prec) {
            cftoe2(buf, prec, caps, &f, 1);
        } else {
            if (mag0 < mag)           /* rounding added a digit (9.99 -> 10.0): drop the last one */
                p[strlen(p) - 1] = 0;
            cftof2(buf, prec, &f, 1);
        }
    }
}

/* _forcdecpt: insert a decimal point after the leading digits (or at the 'e') */
static void forcdecpt(char* s) {
    char hold, next;
    if (*s != 'e' && *s != 'E')
        do
            s++;
        while (*s >= '0' && *s <= '9');
    hold = *s;
    *s++ = '.';
    do {
        next = *s;
        *s = hold;
        hold = next;
    } while (*s++);
}

/* _cropzeros: remove trailing fraction zeros (and a bare decimal point) before the exponent or the end */
static void cropzeros(char* s) {
    char* stop;
    while (*s && *s != '.')
        s++;
    if (*s++) {
        while (*s && *s != 'e' && *s != 'E')
            s++;
        stop = s--;
        while (*s == '0')
            s--;
        if (*s == '.')
            s--;
        while ((*++s = *stop++) != 0)
            ;
    }
}

/* ---------------------------------------------------------------- output sink with the CRT's count rule */
typedef struct Out { int (*put)(void* ctx, uint16_t ch); void* ctx; int32_t n; } Out;

static void out_char(Out* o, uint16_t ch) {
    if (o->put(o->ctx, ch))
        o->n = (int32_t)((uint32_t)o->n + 1u);
    else
        o->n = -1;
}
static void out_multi(Out* o, uint16_t ch, int32_t k) {
    for (; k > 0; k--) {
        out_char(o, ch);
        if (o->n == -1)
            break;
    }
}
static void out_wide(Out* o, const uint8_t* s, int32_t k) {   /* wide text, possibly unaligned */
    for (; k > 0; k--, s += 2) {
        uint16_t ch;
        memcpy(&ch, s, 2);
        out_char(o, ch);
        if (o->n == -1)
            break;
    }
}
static void out_narrow(Out* o, const uint8_t* s, int32_t k) { /* mbtowc loop: stops at NUL, not at failures */
    uint32_t count = (uint32_t)k;
    while (count--) {
        if (!*s)
            break;
        out_char(o, *s++);
    }
}

/* ---------------------------------------------------------------- the format state machine */
enum { FL_SIGN = 1, FL_SIGNSP = 2, FL_LEFT = 4, FL_LEADZERO = 8, FL_LONG = 16, FL_SHORT = 32, FL_SIGNED = 64,
       FL_ALTERNATE = 128, FL_NEGATIVE = 256, FL_FORCEOCTAL = 512, FL_WIDECHAR = 1024, FL_I64 = 2048 };
enum { CH_OTHER, CH_PERCENT, CH_DOT, CH_STAR, CH_ZERO, CH_DIGIT, CH_FLAG, CH_SIZE, CH_TYPE };
enum { ST_NORMAL, ST_PERCENT, ST_FLAG, ST_WIDTH, ST_DOT, ST_PRECIS, ST_SIZE, ST_TYPE };

static int char_class(uint16_t ch) {
    if (ch < ' ' || ch > 'x')
        return CH_OTHER;
    if (ch >= '1' && ch <= '9')
        return CH_DIGIT;
    switch (ch) {
    case '%': return CH_PERCENT;
    case '.': return CH_DOT;
    case '*': return CH_STAR;
    case '0': return CH_ZERO;
    case ' ': case '#': case '+': case '-': return CH_FLAG;
    case 'F': case 'I': case 'L': case 'N': case 'h': case 'l': case 'w': return CH_SIZE;
    case 'B': case 'C': case 'E': case 'G': case 'S': case 'X': case 'Z': case 'c': case 'd': case 'e':
    case 'f': case 'g': case 'i': case 'n': case 'o': case 'p': case 's': case 'u': case 'x': return CH_TYPE;
    default: return CH_OTHER;
    }
}
/* next state, indexed [class][state] */
static const uint8_t next_state[9][8] = {
    /*            NORMAL      PERCENT     FLAG        WIDTH       DOT         PRECIS      SIZE        TYPE */
    /* OTHER */  {ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL},
    /* % */      {ST_PERCENT, ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_PERCENT},
    /* . */      {ST_NORMAL,  ST_DOT,     ST_DOT,     ST_DOT,     ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL},
    /* * */      {ST_NORMAL,  ST_WIDTH,   ST_WIDTH,   ST_NORMAL,  ST_PRECIS,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL},
    /* 0 */      {ST_NORMAL,  ST_FLAG,    ST_FLAG,    ST_WIDTH,   ST_PRECIS,  ST_PRECIS,  ST_NORMAL,  ST_NORMAL},
    /* 1-9 */    {ST_NORMAL,  ST_WIDTH,   ST_WIDTH,   ST_WIDTH,   ST_PRECIS,  ST_PRECIS,  ST_NORMAL,  ST_NORMAL},
    /* flag */   {ST_NORMAL,  ST_FLAG,    ST_FLAG,    ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL,  ST_NORMAL},
    /* size */   {ST_NORMAL,  ST_SIZE,    ST_SIZE,    ST_SIZE,    ST_SIZE,    ST_SIZE,    ST_SIZE,    ST_NORMAL},
    /* type */   {ST_NORMAL,  ST_TYPE,    ST_TYPE,    ST_TYPE,    ST_TYPE,    ST_TYPE,    ST_TYPE,    ST_NORMAL},
};

static const uint8_t null_narrow[] = "(null)";
static const uint8_t null_wide[] = {'(', 0, 'n', 0, 'u', 0, 'l', 0, 'l', 0, ')', 0, 0, 0};

/* Narrow output (msvcr70's _output, the engine behind sprintf): the same state machine over a narrow format,
 * with the narrow build's defaults - %s/%c are narrow and %S/%C (or l/w) wide - and wide text converted by
 * wctomb in the "C" locale (a character above 0xFF ends that text; a wide %c above 0xFF prints nothing).
 * Narrow text is written as is (a %c of NUL writes a NUL). Characters reach put() as byte values. */
static void out_narrow_bytes(Out* o, const uint8_t* s, int32_t k) {
    for (; k > 0; k--) {
        out_char(o, *s++);
        if (o->n == -1)
            break;
    }
}
static void out_wide_wctomb(Out* o, const uint8_t* s, int32_t k) {
    for (; k > 0; k--, s += 2) {
        uint16_t ch;
        memcpy(&ch, s, 2);
        if (ch > 0xFF)
            break;
        out_char(o, ch);
    }
}

static int32_t output(uint32_t fmt, uint32_t va, int narrow, int (*put)(void* ctx, uint16_t ch), void* ctx);

/* Formats guest wide string `fmt` with the guest argument list at `va`, handing each character to
 * put(ctx, ch) (which returns 0 when it cannot be written). Returns the CRT's charsout. */
int32_t xrt_woutput(uint32_t fmt, uint32_t va, int (*put)(void* ctx, uint16_t ch), void* ctx) {
    return output(fmt, va, 0, put, ctx);
}

/* The same for a guest narrow format string (_output) */
int32_t xrt_output(uint32_t fmt, uint32_t va, int (*put)(void* ctx, uint16_t ch), void* ctx) {
    return output(fmt, va, 1, put, ctx);
}

static int32_t output(uint32_t fmt, uint32_t va, int narrow, int (*put)(void* ctx, uint16_t ch), void* ctx) {
    Out o;
    const uint32_t step = narrow ? 1u : 2u;   /* format character size */
    /* models the CRT's local conversion buffer (a 1024-byte char[512] / wchar_t[512] union): integers end at
     * byte 511, floating-point text starts at byte 0, %c stores at bytes 0..1; %B re-reads whatever `text`
     * was. Larger here because the CRT converts floats with precision > 163 into a heap buffer instead
     * (up to 825 bytes of text). */
    uint8_t buf[1100];
    const uint8_t* text = buf;
    int32_t textlen = 0, width = 0, prec = -1;
    int state = ST_NORMAL, flags = 0, bufferiswide = 0, no_output = 0, prefixlen = 0;
    uint8_t prefix[4];
    uint32_t p = fmt;
    o.put = put;
    o.ctx = ctx;
    o.n = 0;
    buf[0] = 0;
    for (;;) {
        uint16_t ch = narrow ? rd8(p) : rd16(p);
        if (!ch)
            break;
        p += step;
        if (o.n < 0)
            break;
        state = next_state[char_class(ch)][state];
        switch (state) {
        case ST_NORMAL:
        normal:
            out_char(&o, ch);
            break;
        case ST_PERCENT:
            no_output = 0;
            width = 0;
            prefixlen = 0;
            bufferiswide = 0;
            flags = 0;
            prec = -1;
            break;
        case ST_FLAG:
            flags |= ch == '-' ? FL_LEFT : ch == '+' ? FL_SIGN : ch == ' ' ? FL_SIGNSP : ch == '#' ? FL_ALTERNATE : FL_LEADZERO;
            break;
        case ST_WIDTH:
            if (ch == '*') {
                width = (int32_t)rd32(va);
                va += 4;
                if (width < 0) {
                    flags |= FL_LEFT;
                    width = (int32_t)(0u - (uint32_t)width);
                }
            } else {
                width = (int32_t)((uint32_t)width * 10u + (uint32_t)(ch - '0'));
            }
            break;
        case ST_DOT:
            prec = 0;
            break;
        case ST_PRECIS:
            if (ch == '*') {
                prec = (int32_t)rd32(va);
                va += 4;
                if (prec < 0)
                    prec = -1;
            } else {
                prec = (int32_t)((uint32_t)prec * 10u + (uint32_t)(ch - '0'));
            }
            break;
        case ST_SIZE:
            if (ch == 'l') {
                flags |= FL_LONG;
            } else if (ch == 'h') {
                flags |= FL_SHORT;
            } else if (ch == 'w') {
                flags |= FL_WIDECHAR;
            } else if (ch == 'I') {
                uint16_t a = narrow ? rd8(p) : rd16(p), b = narrow ? rd8(p + 1) : rd16(p + 2);
                if (a == '6' && b == '4') {
                    p += 2 * step;
                    flags |= FL_I64;
                } else if (a == '3' && b == '2') {
                    p += 2 * step;
                    flags &= ~FL_I64;
                } else if (!(a == 'd' || a == 'i' || a == 'o' || a == 'u' || a == 'x' || a == 'X')) {
                    state = ST_NORMAL;        /* not a size after all: print the 'I' */
                    goto normal;
                }
            }
            break;                            /* 'F', 'L', 'N': accepted and ignored */
        case ST_TYPE: {
            int caps = 0;
            switch (ch) {
            case 'C':
                if (!(flags & (FL_SHORT | FL_LONG | FL_WIDECHAR)))
                    flags |= narrow ? FL_WIDECHAR : FL_SHORT;
                /* fall through */
            case 'c': {
                uint16_t wc = (uint16_t)rd32(va);
                va += 4;
                if (narrow) {
                    bufferiswide = 0;
                    text = buf;
                    textlen = 1;
                    buf[0] = (uint8_t)wc;
                    if ((flags & (FL_LONG | FL_WIDECHAR)) && wc > 0xFF) {
                        textlen = -1;         /* wctomb fails in the "C" locale */
                        no_output = 1;
                    }
                    break;
                }
                bufferiswide = 1;
                if (flags & FL_SHORT)
                    wc &= 0xFF;               /* mbtowc of one byte in the "C" locale (NUL gives NUL) */
                buf[0] = (uint8_t)wc;
                buf[1] = (uint8_t)(wc >> 8);
                text = buf;
                textlen = 1;
                break;
            }
            case 'S':
                if (!(flags & (FL_SHORT | FL_LONG | FL_WIDECHAR)))
                    flags |= narrow ? FL_WIDECHAR : FL_SHORT;
                /* fall through */
            case 's': {
                uint32_t sp = rd32(va), i = prec == -1 ? 0x7FFFFFFFu : (uint32_t)prec;
                va += 4;
                if (narrow ? !(flags & (FL_LONG | FL_WIDECHAR)) : (flags & FL_SHORT)) {
                    text = sp ? (const uint8_t*)G2H(sp) : null_narrow;
                    if (narrow)                   /* "while (i-- && *p)": a negative precision is unlimited */
                        for (textlen = 0; i-- && text[textlen]; textlen++)
                            ;
                    else
                        for (textlen = 0; textlen < (int32_t)i && text[textlen]; textlen++)
                            ;
                } else {
                    const uint8_t* q;
                    text = sp ? (const uint8_t*)G2H(sp) : null_wide;
                    bufferiswide = 1;
                    for (q = text; i-- && (q[0] | q[1]); q += 2)   /* a negative precision is "unlimited" */
                        ;
                    textlen = (int32_t)((q - text) / 2);
                }
                break;
            }
            case 'Z': {                       /* counted string {short Length, short MaximumLength, char* Buffer} */
                uint32_t ps = rd32(va);
                va += 4;
                if (!ps || !rd32(ps + 4)) {
                    text = null_narrow;
                    textlen = 6;
                } else if (flags & FL_WIDECHAR) {
                    text = (const uint8_t*)G2H(rd32(ps + 4));
                    textlen = (int16_t)rd16(ps) / 2;
                    bufferiswide = 1;
                } else {
                    bufferiswide = 0;
                    text = (const uint8_t*)G2H(rd32(ps + 4));
                    textlen = (int16_t)rd16(ps);
                }
                break;
            }
            case 'n': {
                uint32_t np = rd32(va);
                va += 4;
                if (flags & FL_SHORT)
                    wr16(np, (uint16_t)o.n);
                else
                    wr32(np, (uint32_t)o.n);
                no_output = 1;
                break;
            }
            case 'E': case 'G':
                caps = 1;
                ch = (uint16_t)(ch + ('a' - 'A'));
                /* fall through */
            case 'e': case 'f': case 'g': {
                double x;
                flags |= FL_SIGNED;
                if (prec < 0)
                    prec = 6;
                else if (prec == 0 && ch == 'g')
                    prec = 1;
                else if (prec > 512)
                    prec = 512;
                /* above precision 163 the CRT converts into a heap buffer instead (same text) */
                memcpy(&x, G2H(va), 8);
                va += 8;
                cfltcvt(x, (char*)buf, (char)ch, prec, caps);
                if ((flags & FL_ALTERNATE) && prec == 0)
                    forcdecpt((char*)buf);
                if (ch == 'g' && !(flags & FL_ALTERNATE))
                    cropzeros((char*)buf);
                text = buf;
                if (*text == '-') {
                    flags |= FL_NEGATIVE;
                    text++;
                }
                textlen = (int32_t)strlen((const char*)text);
                break;
            }
            case 'd': case 'i': case 'u': case 'o': case 'x': case 'X': case 'p': {
                uint64_t number;
                int64_t l;
                int k, radix = 10, hexadd = 0;
                if (ch == 'd' || ch == 'i')
                    flags |= FL_SIGNED;
                if (ch == 'p') {
                    prec = 8;
                    ch = 'X';
                }
                if (ch == 'X' || ch == 'x') {
                    hexadd = (ch == 'X' ? 'A' : 'a') - '9' - 1;
                    radix = 16;
                    if (flags & FL_ALTERNATE) {
                        prefix[0] = '0';
                        prefix[1] = 0;
                        prefix[2] = (uint8_t)('x' - 'a' + '9' + 1 + hexadd);
                        prefix[3] = 0;
                        prefixlen = 2;
                    }
                } else if (ch == 'o') {
                    radix = 8;
                    if (flags & FL_ALTERNATE)
                        flags |= FL_FORCEOCTAL;
                }
                if (flags & FL_I64) {
                    l = (int64_t)rd64(va);
                    va += 8;
                } else {
                    uint32_t v32 = rd32(va);
                    va += 4;
                    if (flags & FL_SHORT)
                        l = (flags & FL_SIGNED) ? (int64_t)(int16_t)v32 : (int64_t)(uint16_t)v32;
                    else
                        l = (flags & FL_SIGNED) ? (int64_t)(int32_t)v32 : (int64_t)v32;
                }
                if ((flags & FL_SIGNED) && l < 0) {
                    number = 0u - (uint64_t)l;
                    flags |= FL_NEGATIVE;
                } else {
                    number = (uint64_t)l;
                }
                if (!(flags & FL_I64))
                    number &= 0xFFFFFFFFu;
                if (prec < 0) {
                    prec = 1;
                } else {
                    flags &= ~FL_LEADZERO;
                    if (prec > 512)
                        prec = 512;
                }
                if (number == 0)
                    prefixlen = 0;
                k = 511;                      /* at most 512 digits: k ends >= -1 */
                while (prec-- > 0 || number != 0) {
                    int digit = (int)(number % (uint64_t)radix) + '0';
                    number /= (uint64_t)radix;
                    if (digit > '9')
                        digit += hexadd;
                    buf[k--] = (uint8_t)digit;
                }
                textlen = 511 - k;
                if ((flags & FL_FORCEOCTAL) && (textlen == 0 || buf[k + 1] != '0') && k >= 0) {
                    buf[k--] = '0';
                    textlen++;
                }
                text = buf + k + 1;
                break;
            }
            default:                          /* 'B': a type character without a conversion */
                break;
            }
            if (!no_output) {
                int32_t padding;
                if (flags & FL_SIGNED) {
                    prefix[1] = 0;
                    if (flags & FL_NEGATIVE) {
                        prefix[0] = '-';
                        prefixlen = 1;
                    } else if (flags & FL_SIGN) {
                        prefix[0] = '+';
                        prefixlen = 1;
                    } else if (flags & FL_SIGNSP) {
                        prefix[0] = ' ';
                        prefixlen = 1;
                    }
                }
                padding = (int32_t)((uint32_t)width - (uint32_t)textlen - (uint32_t)prefixlen);
                if (!(flags & (FL_LEFT | FL_LEADZERO)))
                    out_multi(&o, ' ', padding);
                out_wide(&o, prefix, prefixlen);
                if ((flags & FL_LEADZERO) && !(flags & FL_LEFT))
                    out_multi(&o, '0', padding);
                if (narrow && bufferiswide)
                    out_wide_wctomb(&o, text, textlen);
                else if (narrow)
                    out_narrow_bytes(&o, text, textlen);
                else if (bufferiswide)
                    out_wide(&o, text, textlen);
                else
                    out_narrow(&o, text, textlen);
                if (flags & FL_LEFT)
                    out_multi(&o, ' ', padding);
            }
            break;
        }
        }
    }
    return o.n;
}

/* ---------------------------------------------------------------- unbounded variant */
typedef struct WOut { uint16_t* buf; size_t len, cap; } WOut;

static int wout_put(void* ctx, uint16_t ch) {
    WOut* o = (WOut*)ctx;
    if (o->len == o->cap) {
        o->cap = o->cap ? o->cap * 2 : 256;
        o->buf = (uint16_t*)realloc(o->buf, o->cap * sizeof *o->buf);
        if (!o->buf)
            xrt_fatal(NULL, XRT_EXIT_SETUP, "host out of memory (formatter)");
    }
    o->buf[o->len++] = ch;
    return 1;
}

/* Formats guest wide string `fmt` with arguments starting at guest address `va` into a sink that never
 * fails. Returns a malloc'ed buffer (not terminated) and its length in *len. */
uint16_t* xrt_wformat(uint32_t fmt, uint32_t va, size_t* len) {
    WOut o = {0};
    xrt_woutput(fmt, va, wout_put, &o);
    *len = o.len;
    if (!o.buf)
        o.buf = (uint16_t*)malloc(2);
    return o.buf;
}
