/* xrt.h - translated runtime (X1): guest CPU state, guest memory, flags, x87 model and the
 * interface between lifter-generated code (tools/xrt/xlift.py) and the host runtime.
 *
 * Address spaces are kept apart deliberately:
 *   guest address  uint32_t, what translated code computes and stores in guest memory
 *   host pointer   void*, only ever obtained with G2H() and converted back with xrt_h2g()
 *   guest handle   uint32_t values handed to guest code for host objects (see xrt_handle_*)
 * Guest memory is one 4 GB host reservation: guest address a lives at host xrt_g + a, so no host
 * pointer is ever narrowed. The low 64 KB stay unmapped so guest null dereferences fault and are
 * reported (xrt_diag.c), like on Windows.
 *
 * Portable C99 except where marked; host Win32 services are confined to the xrt_*.c adapters. */
#ifndef XRT_H
#define XRT_H
#include <math.h>
#include <stdint.h>
#include <string.h>

enum { EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI };

#define XRT_HIST 64

typedef struct XrtThread XrtThread;

typedef struct CPU {
    uint32_t r[8];
    uint32_t cf, pf, zf, sf, of, df;    /* AF is not modelled: no instruction in the lifted modules reads it */
    uint32_t eflags_rest;               /* other EFLAGS bits as last written (not read by lifted code) */
    uint32_t fs_base;                   /* guest address of this thread's TEB */
    uint32_t rv;                        /* return address popped by the most recent ret (checked by callers) */
    uint32_t pc;                        /* guest address of the instruction being executed (diagnostics) */
    double st[8];                       /* x87 registers as host doubles: exact for PC=53-bit (CW 0x027F) */
    uint32_t top;
    uint16_t fcw, fsw;
    uint32_t hist[XRT_HIST];            /* ring of recent function entries (diagnostics) */
    uint32_t hpos;
    XrtThread* thread;
} CPU;

typedef void (*XrtFn)(CPU*);

/* ---------------------------------------------------------------- guest memory */
extern uint8_t* xrt_g;                 /* host address of guest address 0 */
#define G2H(a) ((void*)(xrt_g + (uint32_t)(a)))
uint32_t xrt_h2g(const void* p);       /* fatal if p is not inside guest memory */

static inline uint8_t rd8(uint32_t a) { return xrt_g[a]; }
static inline uint16_t rd16(uint32_t a) { uint16_t v; memcpy(&v, xrt_g + a, 2); return v; }
static inline uint32_t rd32(uint32_t a) { uint32_t v; memcpy(&v, xrt_g + a, 4); return v; }
static inline uint64_t rd64(uint32_t a) { uint64_t v; memcpy(&v, xrt_g + a, 8); return v; }
static inline void wr8(uint32_t a, uint8_t v) { xrt_g[a] = v; }
static inline void wr16(uint32_t a, uint16_t v) { memcpy(xrt_g + a, &v, 2); }
static inline void wr32(uint32_t a, uint32_t v) { memcpy(xrt_g + a, &v, 4); }
static inline void wr64(uint32_t a, uint64_t v) { memcpy(xrt_g + a, &v, 8); }
static inline float rdf32(uint32_t a) { float f; memcpy(&f, xrt_g + a, 4); return f; }
static inline double rdf64(uint32_t a) { double d; memcpy(&d, xrt_g + a, 8); return d; }
static inline void wrf32(uint32_t a, float f) { memcpy(xrt_g + a, &f, 4); }
static inline void wrf64(uint32_t a, double d) { memcpy(xrt_g + a, &d, 8); }

static inline void push32(CPU* c, uint32_t v) { c->r[ESP] -= 4; wr32(c->r[ESP], v); }
static inline uint32_t pop32(CPU* c) { uint32_t v = rd32(c->r[ESP]); c->r[ESP] += 4; return v; }

/* ---------------------------------------------------------------- flags */
static inline uint32_t parity8(uint32_t v) { v &= 0xFF; v ^= v >> 4; v ^= v >> 2; v ^= v >> 1; return (~v) & 1; }
static inline uint32_t msb(uint32_t v, int bits) { return (v >> (bits - 1)) & 1; }
static inline uint32_t bmask(int bits) { return bits == 32 ? 0xFFFFFFFFu : ((1u << bits) - 1); }
static inline void fl_szp(CPU* c, uint32_t res, int bits) {
    res &= bmask(bits);
    c->zf = res == 0; c->sf = msb(res, bits); c->pf = parity8(res);
}
static inline void fl_logic(CPU* c, uint32_t res, int bits) { fl_szp(c, res, bits); c->cf = 0; c->of = 0; }
static inline void fl_add(CPU* c, uint32_t a, uint32_t b, uint32_t res, int bits) {
    uint32_t m = bmask(bits);
    a &= m; b &= m; res &= m;
    c->cf = res < a; fl_szp(c, res, bits);
    c->of = msb((a ^ res) & (b ^ res), bits);
}
static inline void fl_sub(CPU* c, uint32_t a, uint32_t b, uint32_t res, int bits) {
    uint32_t m = bmask(bits);
    a &= m; b &= m; res &= m;
    c->cf = a < b; fl_szp(c, res, bits);
    c->of = msb((a ^ b) & (a ^ res), bits);
}

/* ---------------------------------------------------------------- x87 (host-double model) */
static inline double* ST(CPU* c, int i) { return &c->st[(c->top + i) & 7]; }
static inline void fpush(CPU* c, double v) { c->top = (c->top - 1) & 7; c->st[c->top] = v; }
static inline void fpop(CPU* c) { c->top = (c->top + 1) & 7; }
double xrt_fround(CPU* c, double v);                    /* round to integer per FCW.RC */
int64_t xrt_fist64(CPU* c, double v);                   /* integer indefinite on overflow/NaN */
int32_t xrt_fist32(CPU* c, double v);
int16_t xrt_fist16(CPU* c, double v);
static inline void fcompare(CPU* c, double a, double b) { /* C0 (bit 8), C2 (bit 10), C3 (bit 14) */
    c->fsw &= (uint16_t)~0x4500;
    if (isnan(a) || isnan(b)) c->fsw |= 0x4500;
    else if (a < b) c->fsw |= 0x0100;
    else if (a == b) c->fsw |= 0x4000;
}
static inline uint16_t fstatus(CPU* c) { return (uint16_t)((c->fsw & ~0x3800) | ((c->top & 7) << 11)); }
void xrt_fsin(CPU* c);
void xrt_fcos(CPU* c);
void xrt_fptan(CPU* c);
void xrt_fpatan(CPU* c);
void xrt_fyl2x(CPU* c);
void xrt_f2xm1(CPU* c);
void xrt_fscale(CPU* c);
void xrt_fsqrt(CPU* c);
void xrt_fldcw(CPU* c, uint16_t cw);              /* only PC=53-bit, RC=nearest is modelled; else fatal */
#define XRT_PI 3.14159265358979323846
#define XRT_L2E 1.44269504088896340736
#define XRT_L2T 3.32192809488736234787
#define XRT_LG2 0.30102999566398119521
#define XRT_LN2 0.69314718055994530942

/* ---------------------------------------------------------------- privileged-ish instructions */
void xrt_cpuid(CPU* c);                                 /* documented guest CPU-feature policy */
void xrt_rdtsc(CPU* c);

/* ---------------------------------------------------------------- control transfer */
#if defined(_MSC_VER)
#define XRT_NORETURN __declspec(noreturn)
#else
#define XRT_NORETURN __attribute__((noreturn))
#endif
void xrt_icall(CPU* c, uint32_t target, uint32_t site);           /* indirect call (return addr already pushed) */
void xrt_ijmp(CPU* c, uint32_t target, uint32_t site);            /* indirect tail jump */
XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* why);
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected);
XRT_NORETURN void xrt_div0(CPU* c, uint32_t site);

/* Every translated function entry records history and is a preemption point: when another guest thread
 * waits for the execution baton and the time slice has expired, the runtime hands the baton over here. */
extern volatile long xrt_preempt_req;
void xrt_preempt(CPU* c);
#define XRT_ENTER(va) do { c->hist[c->hpos++ & (XRT_HIST - 1)] = (va); if (xrt_preempt_req) xrt_preempt(c); } while (0)
#ifdef XRT_NO_PC
#define P(va) ((void)0)
#else
#define P(va) (c->pc = (va))
#endif
#define CALL(fn, nxt, site) do { push32(c, (nxt)); fn(c); if (c->rv != (nxt)) xrt_badret(c, (site), (nxt)); } while (0)
#define ICALL(t, nxt, site) do { uint32_t t__ = (t); push32(c, (nxt)); xrt_icall(c, t__, (site)); \
                                 if (c->rv != (nxt)) xrt_badret(c, (site), (nxt)); } while (0)
#define RET(n) do { c->rv = pop32(c); c->r[ESP] += (n); return; } while (0)

/* ---------------------------------------------------------------- generated module descriptors */
typedef struct XrtFuncEntry { uint32_t va; XrtFn fn; } XrtFuncEntry;
typedef struct XrtLiftedModule {
    const char* name;              /* file name, e.g. "Core.dll" */
    uint32_t base;                 /* image base the code was lifted for */
    uint32_t size;
    const char* sha256;            /* of the original file the code was lifted from */
    const XrtFuncEntry* funcs;     /* sorted by va */
    uint32_t nfuncs;
    uint32_t ntraps;               /* static traps emitted (unsupported code, reached => fatal) */
    uint8_t* hits;                 /* hits[k] != 0 once funcs[k] has been entered (evidence) */
} XrtLiftedModule;

#endif
