/* xrt_fmt.c - wide printf formatting with msvcr70 (_woutput) semantics, reading arguments from the guest
 * stack/va_list in guest memory.
 *
 * Deliberately mirrors the old CRT rather than C99/UCRT behaviour:
 *   - floating point: 17 significant digits are produced first and then rounded half-up on the decimal
 *     string (_fltout2 + _fptostr); digits beyond 17 are '0'; exponents have at least 3 digits (e+006);
 *     INF/NaN print as 1.#INF, 1.#QNAN, 1.#SNAN, -1.#IND and go through the same string rounding
 *   - %s is a wide string and %S / %hs a narrow one (wide printf family); NULL prints "(null)"
 *   - %p is 8 upper-case hex digits; %n stores the count; unknown conversion characters are output
 *     literally and end the specification
 * Narrow text is widened byte-for-byte (the guest never calls setlocale, so the CRT is in the "C"
 * locale where mbtowc maps bytes 1:1). Verified against the real msvcr70.dll by
 * experiments/xrt/tests/fmt_diff (see README). */
#include <stdlib.h>
#include "xrt_internal.h"

typedef struct WOut { uint16_t* buf; size_t len, cap; } WOut;

static void wput(WOut* o, uint16_t ch) {
    if (o->len == o->cap) {
        o->cap = o->cap ? o->cap * 2 : 256;
        o->buf = (uint16_t*)realloc(o->buf, o->cap * sizeof *o->buf);
        if (!o->buf)
            xrt_fatal(NULL, XRT_EXIT_SETUP, "host out of memory (formatter)");
    }
    o->buf[o->len++] = ch;
}
static void wputn(WOut* o, uint16_t ch, int n) { while (n-- > 0) wput(o, ch); }

enum { FL_SIGN = 1, FL_SIGNSP = 2, FL_LEFT = 4, FL_LEADZERO = 8, FL_LONG = 16, FL_SHORT = 32, FL_SIGNED = 64,
       FL_ALTERNATE = 128, FL_NEGATIVE = 256, FL_FORCEOCTAL = 512, FL_WIDECHAR = 1024, FL_I64 = 2048 };

/* ---------------------------------------------------------------- floating point (cvt.c equivalents) */
typedef struct StrFlt { char sign; int decpt; char man[40]; } StrFlt;

static void fltout(double x, StrFlt* f) {
    uint64_t bits;
    unsigned ex;
    uint64_t frac;
    memcpy(&bits, &x, 8);
    ex = (unsigned)((bits >> 52) & 0x7FF);
    frac = bits & 0xFFFFFFFFFFFFFull;
    f->sign = (bits >> 63) ? '-' : ' ';
    if (ex == 0x7FF) {
        f->decpt = 1;
        if (!frac)
            strcpy(f->man, "1#INF");
        else if ((bits >> 63) && frac == 0x8000000000000ull)
            strcpy(f->man, "1#IND");
        else if (frac & 0x8000000000000ull)
            strcpy(f->man, "1#QNAN");
        else
            strcpy(f->man, "1#SNAN");
        return;
    }
    if (x == 0.0) {
        f->decpt = 0;
        strcpy(f->man, "0");
        return;
    } else {
        char tmp[64];
        int e, k, n = 0;
        snprintf(tmp, sizeof tmp, "%.16e", fabs(x));     /* 17 significant digits, correctly rounded */
        for (k = 0; tmp[k] && tmp[k] != 'e'; k++)
            if (tmp[k] >= '0' && tmp[k] <= '9')
                f->man[n++] = tmp[k];
        while (n > 1 && f->man[n - 1] == '0')
            n--;
        f->man[n] = 0;
        e = atoi(tmp + k + 1);
        f->decpt = e + 1;
    }
}

/* _fptostr: copy `digits` digits (0-padded) into buf and round half-up on the decimal string */
static void fptostr(char* buf, int digits, StrFlt* f) {
    char* p = buf;
    const char* m = f->man;
    *p++ = '0';
    while (digits > 0) {
        *p++ = *m ? *m++ : '0';
        digits--;
    }
    *p = 0;
    if (digits >= 0 && *m >= '5') {
        p--;
        while (*p == '9')
            *p-- = '0';
        *p += 1;
    }
    if (*buf == '1')
        f->decpt++;
    else
        memmove(buf, buf + 1, strlen(buf + 1) + 1);
}

static void append_exp(char* p, int caps, StrFlt* f) {
    int e = f->man[0] != '0' ? f->decpt - 1 : 0;
    char es = '+';
    if (e < 0) {
        es = '-';
        e = -e;
    }
    sprintf(p, "%c%c%03d", caps ? 'E' : 'e', es, e);
}

/* digits string `d` (already rounded) laid out as d.ddd e+xxx with `ndec` fraction digits */
static void layout_e(char* out, const char* d, int ndec, int caps, StrFlt* f, int alt) {
    char* p = out;
    int k;
    *p++ = d[0] ? d[0] : '0';
    if (ndec > 0 || alt)
        *p++ = '.';
    for (k = 1; k <= ndec; k++)
        *p++ = d[0] && (int)strlen(d) > k ? d[k] : '0';
    append_exp(p, caps, f);
}

static void layout_f(char* out, const char* d, int ndec, StrFlt* f, int alt) {
    char* p = out;
    int len = (int)strlen(d), k, idx = 0;
    if (f->decpt <= 0) {
        *p++ = '0';
    } else {
        for (k = 0; k < f->decpt; k++)
            *p++ = idx < len ? d[idx++] : '0';
    }
    if (ndec > 0 || alt)
        *p++ = '.';
    if (ndec > 0) {
        int z = f->decpt < 0 ? (-f->decpt < ndec ? -f->decpt : ndec) : 0;
        for (k = 0; k < z; k++)
            *p++ = '0';
        for (k = z; k < ndec; k++)
            *p++ = idx < len ? d[idx++] : '0';
    }
    *p = 0;
}

static void cropzeros(char* s) {
    char* dot = strchr(s, '.');
    char *e, *q;
    if (!dot)
        return;
    e = dot;
    while (*e && *e != 'e' && *e != 'E')
        e++;
    q = e;
    while (q > dot + 1 && q[-1] == '0')
        q--;
    if (q == dot + 1)
        q = dot;
    memmove(q, e, strlen(e) + 1);
}

/* returns the text without sign; *neg set when the value carries a '-' */
static void cfltcvt(double x, char ch, int prec, int caps, int alt, char* out, int* neg) {
    StrFlt f;
    char d[600];
    fltout(x, &f);
    *neg = f.sign == '-';
    if (ch == 'e') {
        fptostr(d, prec + 1, &f);
        layout_e(out, d, prec, caps, &f, alt);
    } else if (ch == 'f') {
        fptostr(d, f.decpt + prec, &f);
        layout_f(out, d, prec, &f, alt);
    } else {
        int mag;
        fptostr(d, prec, &f);
        mag = f.decpt - 1;
        if (mag < -4 || mag >= prec)
            layout_e(out, d, prec - 1, caps, &f, alt);
        else
            layout_f(out, d, prec - f.decpt, &f, alt);
        if (!alt)
            cropzeros(out);
    }
}

/* ---------------------------------------------------------------- the formatter */
static int is_flag(uint16_t ch) { return ch == '-' || ch == '+' || ch == ' ' || ch == '#' || ch == '0'; }
static int is_size(uint16_t ch) { return ch == 'h' || ch == 'l' || ch == 'I' || ch == 'L' || ch == 'w' || ch == 'N' || ch == 'F'; }
static int is_type(uint16_t ch) { return ch && strchr("cCdeEfgGinopsSuxXZ", (char)ch) && ch < 128; }

/* Formats guest wide string `fmt` with arguments starting at guest address *va. Returns a malloc'ed
 * buffer (not terminated) and its length in *len. */
uint16_t* xrt_wformat(uint32_t fmt, uint32_t va, size_t* len) {
    WOut o = {0};
    uint32_t p = fmt;
    for (;;) {
        uint16_t ch = rd16(p);
        int flags = 0, width = 0, prec = -1, state;
        if (!ch)
            break;
        p += 2;
        if (ch != '%') {
            wput(&o, ch);
            continue;
        }
        /* state: 0 percent/flags, 1 width, 2 dot/precision, 3 size */
        state = 0;
        for (;;) {
            ch = rd16(p);
            if (!ch)
                goto done;
            p += 2;
            if (state == 0 && is_flag(ch)) {
                flags |= ch == '-' ? FL_LEFT : ch == '+' ? FL_SIGN : ch == ' ' ? FL_SIGNSP : ch == '#' ? FL_ALTERNATE : FL_LEADZERO;
                continue;
            }
            if (state <= 1 && ch == '*') {
                width = (int32_t)rd32(va);
                va += 4;
                if (width < 0) {
                    flags |= FL_LEFT;
                    width = -width;
                }
                state = 1;
                continue;
            }
            if (state <= 1 && ch >= '0' && ch <= '9') {
                width = width * 10 + (ch - '0');
                state = 1;
                continue;
            }
            if (state <= 1 && ch == '.') {
                prec = 0;
                state = 2;
                continue;
            }
            if (state == 2 && ch == '*') {
                prec = (int32_t)rd32(va);
                va += 4;
                if (prec < 0)
                    prec = -1;
                continue;
            }
            if (state == 2 && ch >= '0' && ch <= '9') {
                prec = prec * 10 + (ch - '0');
                continue;
            }
            if (is_size(ch)) {
                state = 3;
                if (ch == 'l')
                    flags |= FL_LONG;
                else if (ch == 'h')
                    flags |= FL_SHORT;
                else if (ch == 'w')
                    flags |= FL_WIDECHAR;
                else if (ch == 'I') {
                    uint16_t a = rd16(p), b = rd16(p + 2);
                    if (a == '6' && b == '4') {
                        p += 4;
                        flags |= FL_I64;
                    } else if (a == '3' && b == '2') {
                        p += 4;
                        flags &= ~FL_I64;
                    } else if (!(a && strchr("dioxXu", (char)a) && a < 128)) {
                        wput(&o, 'I');        /* not a size: msvcr70 prints the 'I' and resumes normal text */
                        break;
                    }
                }
                continue;
            }
            if (ch == '%' && state == 0) {
                wput(&o, '%');
                break;
            }
            if (!is_type(ch)) {
                wput(&o, ch);                 /* invalid character ends the specification and is printed */
                break;
            }
            /* ---- conversion */
            {
                char nbuf[700];
                const char* ntext = NULL;     /* narrow text */
                const uint16_t* wtext = NULL; /* wide text */
                uint16_t wtmp[2];
                int textlen = 0, no_output = 0, prefixlen = 0;
                char prefix[2];
                switch (ch) {
                case 'C':
                    if (!(flags & (FL_SHORT | FL_LONG | FL_WIDECHAR)))
                        flags |= FL_SHORT;
                    /* fall through */
                case 'c': {
                    uint16_t w = (uint16_t)rd32(va);
                    va += 4;
                    wtmp[0] = (flags & FL_SHORT) ? (uint16_t)(w & 0xFF) : w;
                    wtext = wtmp;             /* a NUL narrow char converts to NUL and is still printed */
                    textlen = 1;
                    break;
                }
                case 'S':
                    if (!(flags & (FL_SHORT | FL_LONG | FL_WIDECHAR)))
                        flags |= FL_SHORT;
                    /* fall through */
                case 's': {
                    uint32_t sp = rd32(va), lim = prec == -1 ? 0x7FFFFFFFu : (uint32_t)prec;
                    va += 4;
                    if (flags & FL_SHORT) {
                        if (!sp)
                            ntext = "(null)";
                        else
                            ntext = (const char*)G2H(sp);
                        while ((uint32_t)textlen < lim && ntext[textlen])
                            textlen++;
                    } else {
                        static const uint16_t wnull[] = {'(', 'n', 'u', 'l', 'l', ')', 0};
                        wtext = sp ? (const uint16_t*)G2H(sp) : wnull;
                        while ((uint32_t)textlen < lim && wtext[textlen])
                            textlen++;
                    }
                    break;
                }
                case 'Z':
                    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "printf %%Z (counted string) is not implemented");
                case 'n': {
                    uint32_t np = rd32(va);
                    va += 4;
                    if (flags & FL_SHORT)
                        wr16(np, (uint16_t)o.len);
                    else
                        wr32(np, (uint32_t)o.len);
                    no_output = 1;
                    break;
                }
                case 'E': case 'G': case 'e': case 'f': case 'g': {
                    double x;
                    int caps = ch == 'E' || ch == 'G', neg;
                    char lc = (char)(ch | 0x20);
                    memcpy(&x, G2H(va), 8);
                    va += 8;
                    flags |= FL_SIGNED;
                    if (prec < 0)
                        prec = 6;
                    else if (prec == 0 && lc == 'g')
                        prec = 1;
                    else if (prec > 512)
                        prec = 512;
                    cfltcvt(x, lc, prec, caps, (flags & FL_ALTERNATE) != 0, nbuf, &neg);
                    if (neg)
                        flags |= FL_NEGATIVE;
                    ntext = nbuf;
                    textlen = (int)strlen(nbuf);
                    break;
                }
                default: {   /* d i u o x X p */
                    uint64_t number;
                    int64_t l;
                    int radix = 10, hexadd = 0, pr = prec;
                    char* t;
                    if (ch == 'd' || ch == 'i')
                        flags |= FL_SIGNED;
                    if (ch == 'p') {
                        pr = 8;
                        hexadd = 'A' - '9' - 1;
                        radix = 16;
                    } else if (ch == 'X' || ch == 'x') {
                        hexadd = (ch == 'X' ? 'A' : 'a') - '9' - 1;
                        radix = 16;
                    } else if (ch == 'o') {
                        radix = 8;
                    }
                    if (radix == 16 && (flags & FL_ALTERNATE)) {
                        prefix[0] = '0';
                        prefix[1] = (char)('x' - 'a' + '9' + 1 + hexadd);
                        prefixlen = 2;
                    }
                    if (ch == 'o' && (flags & FL_ALTERNATE))
                        flags |= FL_FORCEOCTAL;
                    if (flags & FL_I64) {
                        l = (int64_t)rd64(va);
                        va += 8;
                    } else {
                        uint32_t v = rd32(va);
                        va += 4;
                        if (flags & FL_SHORT)
                            l = (flags & FL_SIGNED) ? (int64_t)(int16_t)v : (int64_t)(uint16_t)v;
                        else
                            l = (flags & FL_SIGNED) ? (int64_t)(int32_t)v : (int64_t)v;
                    }
                    if ((flags & FL_SIGNED) && l < 0) {
                        number = (uint64_t)(-l);
                        flags |= FL_NEGATIVE;
                    } else {
                        number = (uint64_t)l;
                    }
                    if (!(flags & FL_I64))
                        number &= 0xFFFFFFFFu;
                    if (pr < 0)
                        pr = 1;
                    else
                        flags &= ~FL_LEADZERO;
                    if (number == 0)
                        prefixlen = 0;
                    t = nbuf + sizeof nbuf - 1;
                    *t = 0;
                    while (pr-- > 0 || number != 0) {
                        int digit = (int)(number % (uint64_t)radix) + '0';
                        number /= (uint64_t)radix;
                        if (digit > '9')
                            digit += hexadd;
                        *--t = (char)digit;
                    }
                    textlen = (int)(nbuf + sizeof nbuf - 1 - t);
                    if ((flags & FL_FORCEOCTAL) && (textlen == 0 || t[0] != '0')) {
                        *--t = '0';
                        textlen++;
                    }
                    ntext = t;
                    break;
                }
                }
                if (!no_output) {
                    int padding, k;
                    if (flags & FL_SIGNED) {
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
                    padding = width - textlen - prefixlen;
                    if (!(flags & (FL_LEFT | FL_LEADZERO)))
                        wputn(&o, ' ', padding);
                    for (k = 0; k < prefixlen; k++)
                        wput(&o, (uint8_t)prefix[k]);
                    if ((flags & FL_LEADZERO) && !(flags & FL_LEFT))
                        wputn(&o, '0', padding);
                    for (k = 0; k < textlen; k++)
                        wput(&o, wtext ? wtext[k] : (uint8_t)ntext[k]);
                    if (flags & FL_LEFT)
                        wputn(&o, ' ', padding);
                }
            }
            break;
        }
    }
done:
    *len = o.len;
    if (!o.buf)
        o.buf = (uint16_t*)malloc(2);
    return o.buf;
}
