/* Minimal runtime for statically lifted 32-bit x86 code (feasibility experiment).
 * Guest state is explicit; guest memory is a sparse 4 GB space of 4 KB pages.
 * x87 is modelled with host doubles, which matches an x87 running with the
 * Windows default precision control (53-bit mantissa) except for exponent
 * range and FILD of >53-bit integers. Portable C99: builds for x86-64 and ARM64. */
#ifndef X86RT_H
#define X86RT_H
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI };

typedef struct CPU {
    uint32_t r[8];
    uint32_t cf, zf, sf, of, pf;
    double st[8];
    int top;
    uint16_t fcw, fsw;
} CPU;

/* ---------------- memory ---------------- */
extern uint8_t* g_pages[1u << 20];
static inline uint8_t* page_of(uint32_t a) {
    uint8_t** p = &g_pages[a >> 12];
    if (!*p) { *p = (uint8_t*)calloc(4096, 1); if (!*p) { fprintf(stderr, "oom\n"); exit(3); } }
    return *p;
}
static inline uint8_t rd8(uint32_t a) { return page_of(a)[a & 4095]; }
static inline void wr8(uint32_t a, uint8_t v) { page_of(a)[a & 4095] = v; }
static inline uint16_t rd16(uint32_t a) { return (uint16_t)(rd8(a) | (rd8(a + 1) << 8)); }
static inline uint32_t rd32(uint32_t a) {
    if ((a & 4095) <= 4092) { uint32_t v; memcpy(&v, page_of(a) + (a & 4095), 4); return v; }
    return (uint32_t)rd16(a) | ((uint32_t)rd16(a + 2) << 16);
}
static inline uint64_t rd64(uint32_t a) { return (uint64_t)rd32(a) | ((uint64_t)rd32(a + 4) << 32); }
static inline void wr16(uint32_t a, uint16_t v) { wr8(a, (uint8_t)v); wr8(a + 1, (uint8_t)(v >> 8)); }
static inline void wr32(uint32_t a, uint32_t v) {
    if ((a & 4095) <= 4092) { memcpy(page_of(a) + (a & 4095), &v, 4); return; }
    wr16(a, (uint16_t)v); wr16(a + 2, (uint16_t)(v >> 16));
}
static inline void wr64(uint32_t a, uint64_t v) { wr32(a, (uint32_t)v); wr32(a + 4, (uint32_t)(v >> 32)); }
static inline float rdf32(uint32_t a) { uint32_t u = rd32(a); float f; memcpy(&f, &u, 4); return f; }
static inline double rdf64(uint32_t a) { uint64_t u = rd64(a); double d; memcpy(&d, &u, 8); return d; }
static inline void wrf32(uint32_t a, float f) { uint32_t u; memcpy(&u, &f, 4); wr32(a, u); }
static inline void wrf64(uint32_t a, double d) { uint64_t u; memcpy(&u, &d, 8); wr64(a, u); }

/* ---------------- stack ---------------- */
static inline void push32(CPU* c, uint32_t v) { c->r[ESP] -= 4; wr32(c->r[ESP], v); }
static inline uint32_t pop32(CPU* c) { uint32_t v = rd32(c->r[ESP]); c->r[ESP] += 4; return v; }

/* ---------------- flags ---------------- */
static inline uint32_t parity8(uint32_t v) { v &= 0xFF; v ^= v >> 4; v ^= v >> 2; v ^= v >> 1; return (~v) & 1; }
static inline uint32_t msb(uint32_t v, int bits) { return (v >> (bits - 1)) & 1; }
static inline uint32_t mask(int bits) { return bits == 32 ? 0xFFFFFFFFu : ((1u << bits) - 1); }
static inline void fl_logic(CPU* c, uint32_t res, int bits) {
    res &= mask(bits);
    c->cf = 0; c->of = 0; c->zf = res == 0; c->sf = msb(res, bits); c->pf = parity8(res);
}
static inline void fl_add(CPU* c, uint32_t a, uint32_t b, uint32_t res, int bits) {
    uint32_t m = mask(bits);
    a &= m; b &= m; res &= m;
    c->cf = res < a; c->zf = res == 0; c->sf = msb(res, bits); c->pf = parity8(res);
    c->of = msb((a ^ res) & (b ^ res), bits);
}
static inline void fl_sub(CPU* c, uint32_t a, uint32_t b, uint32_t res, int bits) {
    uint32_t m = mask(bits);
    a &= m; b &= m; res &= m;
    c->cf = a < b; c->zf = res == 0; c->sf = msb(res, bits); c->pf = parity8(res);
    c->of = msb((a ^ b) & (a ^ res), bits);
}
static inline void fl_incdec(CPU* c, uint32_t a, uint32_t res, int bits, int is_inc) {
    uint32_t keep = c->cf;
    if (is_inc) fl_add(c, a, 1, res, bits); else fl_sub(c, a, 1, res, bits);
    c->cf = keep;
}

/* ---------------- x87 ---------------- */
static inline double* ST(CPU* c, int i) { return &c->st[(c->top + i) & 7]; }
static inline void fpush(CPU* c, double v) { c->top = (c->top - 1) & 7; c->st[c->top] = v; }
static inline double fpop(CPU* c) { double v = c->st[c->top]; c->top = (c->top + 1) & 7; return v; }
static inline double fround(CPU* c, double v) {          /* rounding per FCW.RC */
    switch ((c->fcw >> 10) & 3) {
        case 0: return nearbyint(v);    /* host default mode is round-to-nearest-even */
        case 1: return floor(v);
        case 2: return ceil(v);
        default: return trunc(v);
    }
}
static inline int64_t fist64(CPU* c, double v) {
    double r = fround(c, v);
    if (!(r >= -9223372036854775808.0 && r < 9223372036854775808.0)) return INT64_MIN;  /* integer indefinite */
    return (int64_t)r;
}
static inline int32_t fist32(CPU* c, double v) {
    double r = fround(c, v);
    if (!(r >= -2147483648.0 && r < 2147483648.0)) return INT32_MIN;
    return (int32_t)r;
}
static inline void fcompare(CPU* c, double a, double b) {   /* sets C0 (bit 8), C2 (bit 10), C3 (bit 14) */
    c->fsw &= (uint16_t)~(0x4500);
    if (isnan(a) || isnan(b)) c->fsw |= 0x4500;
    else if (a < b) c->fsw |= 0x0100;
    else if (a == b) c->fsw |= 0x4000;
}
static inline uint16_t fstatus(CPU* c) { return (uint16_t)((c->fsw & ~0x3800) | ((c->top & 7) << 11)); }

/* ---------------- host thunks for imports ---------------- */
typedef void (*HostFn)(CPU*);
#endif
