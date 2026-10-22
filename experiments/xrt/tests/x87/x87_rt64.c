/* x87_rt64.c - x64 harness: the runtime's x87 model against real x87 hardware.
 *
 * Runtime side: experiments/xrt/runtime/xrt_cpu.c (compiled with the runtime's own flags) and the
 * lifted Core.dll functions appExp/appLoge/appSin/appCos/appTan/appAtan/appAtan2/appSqrt/_ftol2
 * (tools/xrt/xlift.py --only, git-ignored), executed on a CPU struct from runtime/xrt.h over a small
 * guest memory. Caller sequences (script natives, FGlobalMath tables, appInit timing loop) are mirrored
 * with the same statements the lifter emits for them.
 * Hardware side: x87_hw32.exe output (records, hashes) and, for exhaustive runs, the ml64 kernels in
 * x87_hw64.asm (validated against x87_hw32.exe by per-chunk hashes).
 * Alternative helper models (x87_alt.c) run the same lifted code with other x87 helpers:
 *   hx   host x87 instructions (ml64) with results rounded to double
 *   p66  libm with the hardware's 66-bit-pi argument reduction for fsin/fcos/fptan
 *   pfix p66 plus the SDM special-operand behaviour of fsin/fcos/fptan (NaN, inf) and fscale
 *
 *   x87_rt64 info
 *   x87_rt64 gen <inputs.bin>
 *   x87_rt64 cmp <inputs.bin> <hw.bin> <out.json> [models]
 *   x87_rt64 exhaustive <op|all> <hash-prefix> <out.jsonl> <mismatch-prefix> [models] [P|E|all] [nofma]
 *   x87_rt64 dummy <steps> <hw-dummy.bin>
 *   x87_rt64 run <inputs.bin> <model> <out.bin>             (raw model outputs)
 *   x87_rt64 atan2 <pairs> <out.jsonl> [models]
 *   x87_rt64 fmadiff <op|all> <out.jsonl>                  (runtime with UCRT FMA3 paths on vs off)
 *   x87_rt64 eval <model> <op> <a-bits-hex> [b-bits-hex]      (one record, for investigation) */
#include "x87_common.h"
#include "xrt_internal.h"
#include <intrin.h>
#include <math.h>
#include <stdarg.h>

/* ------------------------------------------------------------------ runtime symbols (stubs) */
uint8_t* xrt_g;
volatile long xrt_preempt_req;
uint8_t xrt_hits_Core[64];
void xrt_preempt(CPU* c) { (void)c; }
static void die(const char* what, CPU* c) {
    fprintf(stderr, "fatal: %s at pc=%08x\n", what, c ? c->pc : 0);
    exit(3);
}
void xrt_icall(CPU* c, uint32_t t, uint32_t s) { (void)t; (void)s; die("icall", c); }
void xrt_ijmp(CPU* c, uint32_t t, uint32_t s) { (void)t; (void)s; die("ijmp", c); }
XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* why) { (void)site; die(why, c); exit(3); }
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t e) { (void)site; (void)e; die("badret", c); exit(3); }
XRT_NORETURN void xrt_div0(CPU* c, uint32_t site) { (void)site; die("div0", c); exit(3); }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fprintf(stderr, " (code %d, pc=%08x)\n", code, c ? c->pc : 0);
    exit(3);
}
void xrt_log(const char* fmt, ...) { (void)fmt; }

/* ------------------------------------------------------------------ models */
#pragma warning(disable : 4003)   /* LIFTED() with an empty prefix */
#define LIFTED(P) \
    void P##f_10116f60(CPU*); void P##f_10116f80(CPU*); void P##f_10116fa0(CPU*); void P##f_10116fc0(CPU*); \
    void P##f_10116fe0(CPU*); void P##f_10116ff0(CPU*); void P##f_10117000(CPU*); void P##f_10117010(CPU*); \
    void P##f_1015d510(CPU*);
LIFTED()
LIFTED(hx_)
LIFTED(p66_)
LIFTED(pfix_)
#define HELPERS(P) \
    void P##fsin(CPU*); void P##fcos(CPU*); void P##fptan(CPU*); void P##fpatan(CPU*); void P##fyl2x(CPU*); \
    void P##f2xm1(CPU*); void P##fscale(CPU*); void P##fsqrt(CPU*);
HELPERS(hx_)
HELPERS(p66_)
HELPERS(pfix_)
void x87_setcw(uint16_t cw);
uint16_t x87_getcw(void);

typedef struct Model {
    const char* name;
    XrtFn exp, loge, sin, cos, tan, atan, atan2, sqrt, ftol;               /* lifted Core.dll functions */
    XrtFn fsin, fcos, fptan, fpatan, fyl2x, f2xm1, fscale, fsqrt;          /* helpers (instruction level) */
} Model;
#define MODEL(N, P, H) {N, P##f_10116f60, P##f_10116f80, P##f_10116fa0, P##f_10116fc0, P##f_10116fe0, \
    P##f_10116ff0, P##f_10117000, P##f_10117010, P##f_1015d510, H##fsin, H##fcos, H##fptan, H##fpatan, \
    H##fyl2x, H##f2xm1, H##fscale, H##fsqrt}
static const Model models[] = {MODEL("rt", , xrt_), MODEL("hx", hx_, hx_), MODEL("p66", p66_, p66_),
                               MODEL("pfix", pfix_, pfix_)};
#define NMODELS 4
static int model_enabled(const char* list, int m) { return !list || !strcmp(list, "all") || strstr(list, models[m].name); }

/* ------------------------------------------------------------------ guest memory */
#define GUEST_SIZE (64u << 20)
#define GC_BASE 0x00010000u          /* constants the mirrored caller code loads from memory */
#define GC_PI16384 (GC_BASE + 0)     /* double pi/16384 (FGlobalMath sine-table step) */
#define GC_2M14 (GC_BASE + 8)        /* float 2^-14 (FGlobalMath sqrt table) */
#define GC_314 (GC_BASE + 16)        /* double 3.14 (appInit timing loop) */
#define GSTACK(t) (0x00100000u + (uint32_t)(t) * 0x10000u)
#define RA 0x00C0FFEEu               /* return address pushed by mirrored calls (checked, never executed) */

static void guest_init(void) {
    xrt_g = (uint8_t*)VirtualAlloc(NULL, GUEST_SIZE, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!xrt_g) die("VirtualAlloc", NULL);
    wrf64(GC_PI16384, 3.14159265358979323846 / 16384.0);
    wrf32(GC_2M14, 6.103515625e-05f);
    wrf64(GC_314, 3.14);
}

static void cpu_init(CPU* c, int t) {
    memset(c, 0, sizeof *c);
    c->fcw = 0x027F;
    c->r[ESP] = GSTACK(t) + 0xF000u;
    c->r[EBP] = c->r[ESP];
}

/* reset the x87 model to an empty stack whose ST(0) slot was never written (a fresh guest thread) */
static void fpu_reset(CPU* c) {
    c->top = 0;
    c->fsw = 0;
    c->fcw = 0x027F;
    for (int i = 0; i < 8; i++) c->st[i] = 0.0;
}

static uint64_t dbits(double d) { uint64_t u; memcpy(&u, &d, 8); return u; }
static double bitsd(uint64_t u) { double d; memcpy(&d, &u, 8); return d; }
static uint32_t fbits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static float bitsf(uint32_t u) { float f; memcpy(&f, &u, 4); return f; }

/* script native: P_GET_FLOAT(A); *(FLOAT*)Result = appXxx(A);   (execSin, execCos, ...) */
static uint32_t exec_native(CPU* c, XrtFn fn, uint32_t abits, double* st0) {
    uint32_t sp = c->r[ESP];
    wr32(sp + 0xcu, abits);
    fpush(c, (double)rdf32(sp + 0xcu));                    /* fld dword ptr [esp + 0xc] */
    c->r[ESP] -= 8;                                         /* sub esp, 8 */
    wrf64(c->r[ESP], *ST(c, 0));                            /* fstp qword ptr [esp] */
    fpop(c);
    CALL(fn, RA, RA);
    c->r[ESP] += 8;
    *st0 = *ST(c, 0);
    wrf32(sp + 0x20u, (float)*ST(c, 0));                    /* fstp dword ptr [ecx] */
    fpop(c);
    return rd32(sp + 0x20u);
}

/* execAtan2-like: appAtan2(Y, X) with float arguments */
static uint32_t exec_native2(CPU* c, XrtFn fn, uint32_t ybits, uint32_t xbits, double* st0) {
    uint32_t sp = c->r[ESP];
    wr32(sp + 0xcu, ybits);
    wr32(sp + 0x14u, xbits);
    fpush(c, (double)rdf32(sp + 0x14u));
    c->r[ESP] -= 0x10;
    wrf64(c->r[ESP] + 8, *ST(c, 0));
    fpop(c);
    fpush(c, (double)rdf32(sp + 0xcu));
    wrf64(c->r[ESP], *ST(c, 0));
    fpop(c);
    CALL(fn, RA, RA);
    c->r[ESP] += 0x10;
    *st0 = *ST(c, 0);
    wrf32(sp + 0x20u, (float)*ST(c, 0));
    fpop(c);
    return rd32(sp + 0x20u);
}

/* appXxx(double) called with a double argument; result left in ST(0) */
static double call_d(CPU* c, XrtFn fn, double a) {
    c->r[ESP] -= 8;
    wrf64(c->r[ESP], a);
    CALL(fn, RA, RA);
    c->r[ESP] += 8;
    return *ST(c, 0);
}

static double call_dd(CPU* c, XrtFn fn, double y, double x) {
    c->r[ESP] -= 16;
    wrf64(c->r[ESP], y);
    wrf64(c->r[ESP] + 8, x);
    CALL(fn, RA, RA);
    c->r[ESP] += 16;
    return *ST(c, 0);
}

/* evaluate one record on the model; fills r32/r64/i64/x/fsw/flags */
static void rt_eval(CPU* c, const Model* m, const Rec* r, Out* o) {
    double A = bitsd(r->a), B = bitsd(r->b), v = 0;
    int64_t A64 = (int64_t)r->a;
    int has_v = 1;
    memset(o, 0, sizeof *o);
    fpu_reset(c);
    c->fcw = (uint16_t)(0x027F | ((r->aux & 3) << 10));
    switch (r->op) {
    case OP_FSIN: fpush(c, A); m->fsin(c); v = *ST(c, 0); break;
    case OP_FCOS: fpush(c, A); m->fcos(c); v = *ST(c, 0); break;
    case OP_FPTAN:
        fpush(c, A);
        m->fptan(c);
        if (!(c->fsw & FSW_C2)) {         /* something was pushed: record its bits */
            o->flags = 1;
            o->x = dbits(*ST(c, 0));
            fpop(c);
        }
        v = *ST(c, 0);
        break;
    case OP_FPATAN: fpush(c, A); fpush(c, B); m->fpatan(c); v = *ST(c, 0); break;
    case OP_FYL2X: fpush(c, A); fpush(c, B); m->fyl2x(c); v = *ST(c, 0); break;
    case OP_F2XM1: fpush(c, A); m->f2xm1(c); v = *ST(c, 0); break;
    case OP_FSCALE:
        fpush(c, B); fpush(c, A); m->fscale(c);
        *ST(c, 1) = *ST(c, 0); fpop(c);                     /* fstp st(1) */
        v = *ST(c, 0);
        break;
    case OP_FSQRT: fpush(c, A); m->fsqrt(c); v = *ST(c, 0); break;
    case OP_FRNDINT: v = xrt_fround(c, A); break;
    case OP_FIST16: case OP_FIST16NP: o->i64 = (uint64_t)(int64_t)xrt_fist16(c, A); has_v = 0; break;
    case OP_FIST32: case OP_FIST32NP: o->i64 = (uint64_t)(int64_t)xrt_fist32(c, A); has_v = 0; break;
    case OP_FIST64: o->i64 = (uint64_t)xrt_fist64(c, A); has_v = 0; break;
    case OP_FILD64: v = (double)A64; break;                 /* lifter: fpush(c, (double)(int64_t)rd64(a)) */
    case OP_FILD64_RT: c->fcw = 0x027F; o->i64 = (uint64_t)xrt_fist64(c, (double)A64); has_v = 0; break;
    case OP_FILD64_MUL: { double m_ = B; v = (double)A64; v = v * m_; } break;
    case OP_FILD64_ADD: { double m_ = B; v = (double)A64; v = v + m_; } break;
    case OP_FLDCONST: {
        static const double k[] = {1.0, XRT_L2T, XRT_L2E, XRT_PI, XRT_LG2, XRT_LN2, 0.0};
        v = k[r->aux < 7 ? r->aux : 6];
    } break;
    case E_SIN: v = call_d(c, m->sin, A); break;
    case E_COS: v = call_d(c, m->cos, A); break;
    case E_TAN: v = call_d(c, m->tan, A); break;
    case E_ATAN: v = call_d(c, m->atan, A); break;
    case E_ATAN2: v = call_dd(c, m->atan2, A, B); break;
    case E_SQRT: v = call_d(c, m->sqrt, A); break;
    case E_EXP: v = call_d(c, m->exp, A); break;
    case E_LOGE: v = call_d(c, m->loge, A); break;
    case E_SINTAB: case E_SQRTTAB: {                        /* FGlobalMath::FGlobalMath loops */
        uint32_t sp = c->r[ESP];
        wr32(sp + 0xcu, r->idx);
        fpush(c, (double)(int32_t)rd32(sp + 0xcu));         /* fild dword ptr [esp + 0xc] */
        c->r[ESP] -= 8;
        if (r->op == E_SINTAB) {
            *ST(c, 0) = *ST(c, 0) + *ST(c, 0);              /* fadd st(0), st(0) */
            { double m_ = rdf64(GC_PI16384); *ST(c, 0) = *ST(c, 0) * m_; }
        } else {
            double m_ = (double)rdf32(GC_2M14);
            *ST(c, 0) = *ST(c, 0) * m_;                     /* fmul dword ptr [2^-14] */
        }
        wrf64(c->r[ESP], *ST(c, 0));
        fpop(c);
        o->x = rd64(c->r[ESP]);
        XrtFn fn = r->op == E_SINTAB ? m->sin : m->sqrt;
        CALL(fn, RA, RA);
        c->r[ESP] += 8;
        v = *ST(c, 0);
    } break;
    case E_FTOL:
        fpush(c, A);
        CALL(m->ftol, RA, RA);
        o->i64 = ((uint64_t)c->r[EDX] << 32) | c->r[EAX];
        has_v = 0;
        break;
    default:
        fprintf(stderr, "unknown op %u\n", r->op);
        exit(2);
    }
    if (has_v) {
        float f = (float)v;                                  /* the lifted fstp dword: wrf32(a, (float)ST0) */
        o->r64 = dbits(v);
        o->r32 = fbits(f);
    }
    o->fsw = c->fsw;
}

/* ------------------------------------------------------------------ comparison helpers */
static int isnan64(uint64_t b) { return (b & 0x7FF0000000000000ull) == 0x7FF0000000000000ull && (b & 0xFFFFFFFFFFFFFull); }
static int isnan32(uint32_t b) { return (b & 0x7F800000u) == 0x7F800000u && (b & 0x7FFFFFu); }
static int64_t key32(uint32_t b) { return (b & 0x80000000u) ? -(int64_t)(b & 0x7FFFFFFFu) : (int64_t)b; }
static int64_t key64(uint64_t b) { return (b >> 63) ? -(int64_t)(b & 0x7FFFFFFFFFFFFFFFull) : (int64_t)b; }

/* error of double v relative to the 80-bit hardware value, in units of the double ulp of that value;
 * <0 when not meaningful (non-finite, outside double range) */
static double ulp_err80(double v, const uint8_t* r80) {
    uint64_t mant;
    memcpy(&mant, r80, 8);
    int e15 = (r80[8] | (r80[9] << 8)) & 0x7FFF, neg = r80[9] >> 7;
    if (e15 == 0x7FFF || !isfinite(v)) return -1;
    if (mant == 0) return v == 0 ? 0 : -2;
    int e = e15 - 16383 - 63, top = 63;
    while (!((mant >> top) & 1)) top--;
    int ex = e + top;
    if (ex > 1023 || ex < -1074) return -3;
    double hi = ldexp((double)(mant & ~0x7FFull), e), lo = ldexp((double)(mant & 0x7FFull), e);
    if (neg) { hi = -hi; lo = -lo; }
    double d = (v - hi) - lo;
    int ue = ex - 52 < -1074 ? -1074 : ex - 52;
    double res = fabs(d) / ldexp(1.0, ue);
    return isfinite(res) ? res : -4;
}

static void hex80(char* s, const uint8_t* r) {
    sprintf(s, "%02x%02x:%02x%02x%02x%02x%02x%02x%02x%02x", r[9], r[8], r[7], r[6], r[5], r[4], r[3], r[2], r[1], r[0]);
}

/* ------------------------------------------------------------------ input generation */
static Rec* g_recs;
static size_t g_n, g_cap;
static void add(uint32_t op, uint32_t aux, uint32_t set, uint32_t idx, uint64_t a, uint64_t b) {
    if (g_n == g_cap) {
        g_cap = g_cap ? g_cap * 2 : 1 << 20;
        g_recs = (Rec*)realloc(g_recs, g_cap * sizeof(Rec));
    }
    Rec* r = &g_recs[g_n++];
    r->op = op; r->aux = aux; r->set = set; r->idx = idx; r->a = a; r->b = b;
}
static void addd(uint32_t op, uint32_t aux, uint32_t set, uint32_t idx, double a, double b) { add(op, aux, set, idx, dbits(a), dbits(b)); }

/* log-uniform double: random sign (if neg), unbiased exponent in [emin, emax], random mantissa */
static double rnd_ld(uint64_t* s, int emin, int emax, int neg) {
    uint64_t r = splitmix64(s), q = splitmix64(s);
    int e = emin + (int)(q % (uint64_t)(emax - emin + 1));
    uint64_t sign = neg ? (r >> 63) : 0, bits;
    if (e < -1022) bits = (sign << 63) | ((r & 0xFFFFFFFFFFFFFull) >> (-1022 - e > 51 ? 51 : -1022 - e)) | 1u; /* subnormal */
    else bits = (sign << 63) | ((uint64_t)(e + 1023) << 52) | (r & 0xFFFFFFFFFFFFFull);
    return bitsd(bits);
}

static const char* const set_names[] = {
    "edge", "pi_multiples", "rand_small", "rand_medium", "rand_large", "rand_out_of_range", "rand_tiny",
    "f2xm1_domain", "f2xm1_outside_domain_UB", "fyl2x_y1", "fyl2x_near1", "fyl2x_rand", "fyl2x_special",
    "fpatan_rand", "fpatan_special", "fscale_rand", "fscale_special", "fsqrt_rand", "round_halfway",
    "round_rand", "fild64_above_2p53", "fild64_below_2p53", "constants", "engine_sintab", "engine_sqrttab",
    "engine_rand_small", "engine_rand_large", "engine_exp_range", "engine_loge_range", "engine_edge",
    "ftol_timing_loop", "ftol_edge", "ftol_out_of_range_UB", "engine_atan2_rand",
};
enum { S_EDGE, S_PIMUL, S_RSMALL, S_RMED, S_RLARGE, S_ROOR, S_RTINY, S_F2XM1, S_F2XM1_UB, S_YL2X_Y1, S_YL2X_N1,
       S_YL2X_RAND, S_YL2X_SPEC, S_PATAN_RAND, S_PATAN_SPEC, S_SCALE_RAND, S_SCALE_SPEC, S_SQRT_RAND,
       S_ROUND_HALF, S_ROUND_RAND, S_FILD_BIG, S_FILD_SMALL, S_CONST, S_SINTAB, S_SQRTTAB, S_ERSMALL, S_ERLARGE,
       S_EEXP, S_ELOGE, S_EEDGE, S_FTOL_LOOP, S_FTOL_EDGE, S_FTOL_UB, S_EATAN2, NSETS };

static double edge_vals[512];
static int n_edge;
static void edge_add(double d) { edge_vals[n_edge++] = d; edge_vals[n_edge++] = -d; }
static void build_edges(void) {
    const double pi = 3.14159265358979323846;
    double base[] = {0.0, bitsd(1), bitsd(0x000FFFFFFFFFFFFFull), bitsd(0x0010000000000000ull), 1e-300, 1e-200,
                     ldexp(1, -60), ldexp(1, -30), 1e-8, 1e-4, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 10.0,
                     pi / 4, pi / 2, 3 * pi / 4, pi, 3 * pi / 2, 2 * pi, 100.0, 1e5, 1e6, 65536.0,
                     2147483648.0, ldexp(1, 52), ldexp(1, 53), ldexp(1, 62), ldexp(1, 63) - 1024.0, ldexp(1, 63),
                     ldexp(1, 63) + 2048.0, ldexp(1, 64), 1e20, 1e300, bitsd(0x7FEFFFFFFFFFFFFFull),
                     bitsd(0x7FF0000000000000ull), bitsd(0x7FF8000000000000ull), bitsd(0x7FF8000000000123ull),
                     bitsd(0x7FF0000000000001ull),
                     88.0, 88.7, 89.0, 700.0, 709.0, 710.0, 1000.0, 11356.0, 11357.0, 2.718281828459045};
    n_edge = 0;
    for (size_t i = 0; i < sizeof base / sizeof base[0]; i++) edge_add(base[i]);
}

static void gen(const char* path) {
    uint64_t s = 0x5EED000087ull;
    const double pi = 3.14159265358979323846;
    static const uint32_t unary_ops[] = {OP_FSIN, OP_FCOS, OP_FPTAN, OP_F2XM1, OP_FSQRT};
    static const uint32_t trig_ops[] = {OP_FSIN, OP_FCOS, OP_FPTAN, E_SIN, E_COS, E_TAN};
    static const uint32_t eng_ops[] = {E_SIN, E_COS, E_TAN, E_ATAN, E_SQRT, E_EXP, E_LOGE};
    static const uint32_t round_ops[] = {OP_FRNDINT, OP_FIST16, OP_FIST32, OP_FIST64, OP_FIST16NP, OP_FIST32NP};
    build_edges();
    /* edge values through every single-argument instruction and engine function */
    for (int i = 0; i < n_edge; i++) {
        for (size_t k = 0; k < sizeof unary_ops / 4; k++) addd(unary_ops[k], 0, S_EDGE, i, edge_vals[i], 0);
        for (size_t k = 0; k < sizeof eng_ops / 4; k++) addd(eng_ops[k], 0, S_EEDGE, i, edge_vals[i], 0);
    }
    /* multiples of pi (as doubles) and their neighbours */
    for (int k = -1000, j = 0; k <= 1000; k++) {
        for (int q = 1; q <= 4; q *= 2) {
            double x = k * (pi / q);
            for (int d = -2; d <= 2; d++) {
                double y = bitsd(dbits(x) + (int64_t)d);
                if (x == 0 && d < 0) continue;
                for (size_t t = 0; t < sizeof trig_ops / 4; t++) addd(trig_ops[t], 0, S_PIMUL, j, y, 0);
                j++;
            }
        }
    }
    /* random arguments by magnitude */
    struct { int set, emin, emax, n; } rr[] = {{S_RSMALL, -30, 3, 100000}, {S_RMED, 3, 19, 50000},
                                               {S_RLARGE, 20, 62, 50000}, {S_ROOR, 63, 1023, 5000},
                                               {S_RTINY, -1074, -31, 20000}};
    for (size_t g = 0; g < sizeof rr / sizeof rr[0]; g++)
        for (int i = 0; i < rr[g].n; i++) {
            double x = rnd_ld(&s, rr[g].emin, rr[g].emax, 1);
            for (size_t t = 0; t < sizeof trig_ops / 4; t++) addd(trig_ops[t], 0, rr[g].set, i, x, 0);
            if (rr[g].set == S_RTINY || rr[g].set == S_RSMALL) {
                addd(OP_FSQRT, 0, rr[g].set, i, fabs(x), 0);
                addd(E_ATAN, 0, rr[g].set, i, x, 0);
            }
            if (rr[g].set == S_RTINY) addd(OP_F2XM1, 0, rr[g].set, i, x, 0);
        }
    /* f2xm1: defined for -1 <= x <= +1 (SDM); outside is undefined */
    for (int i = 0; i < 100000; i++) {
        double x = rnd_ld(&s, -60, -1, 1);
        if (i % 4 == 0) x = (double)(splitmix64(&s) >> 11) * ldexp(1, -52) - 1.0;   /* uniform in [-1, 1) */
        addd(OP_F2XM1, 0, S_F2XM1, i, x, 0);
    }
    addd(OP_F2XM1, 0, S_F2XM1, 100000, 1.0, 0);
    addd(OP_F2XM1, 0, S_F2XM1, 100001, -1.0, 0);
    for (int i = 0; i < 5000; i++) addd(OP_F2XM1, 0, S_F2XM1_UB, i, rnd_ld(&s, 0, 6, 1) * 1.0000001, 0);
    /* fyl2x */
    for (int i = 0; i < 100000; i++) addd(OP_FYL2X, 0, S_YL2X_Y1, i, 1.0, rnd_ld(&s, -1074, 1023, 0));
    for (int i = 0; i < 50000; i++) {
        double d = rnd_ld(&s, -60, -2, 1);
        addd(OP_FYL2X, 0, S_YL2X_N1, i, 1.0, 1.0 + d);
        addd(OP_FYL2X, 0, S_YL2X_N1, 50000 + i, XRT_LN2, 1.0 + d);
    }
    for (int i = 0; i < 100000; i++) addd(OP_FYL2X, 0, S_YL2X_RAND, i, rnd_ld(&s, -40, 40, 1), rnd_ld(&s, -1022, 1023, 0));
    {
        double xs[] = {0.0, -0.0, -1.0, -1e-300, 1.0, bitsd(0x7FF0000000000000ull), -bitsd(0x7FF0000000000000ull),
                       bitsd(0x7FF8000000000000ull), 0.5, 2.0, bitsd(1)};
        double ys[] = {0.0, -0.0, 1.0, -1.0, 3.5, bitsd(0x7FF0000000000000ull), -bitsd(0x7FF0000000000000ull),
                       bitsd(0x7FF8000000000000ull), XRT_LN2};
        int j = 0;
        for (size_t a = 0; a < sizeof ys / 8; a++)
            for (size_t b = 0; b < sizeof xs / 8; b++) addd(OP_FYL2X, 0, S_YL2X_SPEC, j++, ys[a], xs[b]);
    }
    /* fpatan (y = ST1 = a, x = ST0 = b) */
    for (int i = 0; i < 100000; i++) addd(OP_FPATAN, 0, S_PATAN_RAND, i, rnd_ld(&s, -60, 60, 1), rnd_ld(&s, -60, 60, 1));
    for (int i = 0; i < 20000; i++) addd(OP_FPATAN, 0, S_PATAN_RAND, 100000 + i, rnd_ld(&s, -1074, 1023, 1), rnd_ld(&s, -1074, 1023, 1));
    {
        double v[] = {0.0, -0.0, 1.0, -1.0, 1e-300, -1e-300, 1e300, -1e300, bitsd(0x7FF0000000000000ull),
                      -bitsd(0x7FF0000000000000ull), bitsd(0x7FF8000000000000ull)};
        int j = 0;
        for (size_t a = 0; a < sizeof v / 8; a++)
            for (size_t b = 0; b < sizeof v / 8; b++) {
                addd(OP_FPATAN, 0, S_PATAN_SPEC, j, v[a], v[b]);
                addd(E_ATAN2, 0, S_PATAN_SPEC, j++, v[a], v[b]);
            }
    }
    /* fscale: ST(0) = a, ST(1) = b */
    for (int i = 0; i < 50000; i++) {
        double a = rnd_ld(&s, -100, 100, 1);
        double b = (double)((int64_t)(splitmix64(&s) % 2201) - 1100);
        if (i % 3 == 0) b += (double)(splitmix64(&s) >> 11) * ldexp(1, -53) * ((i & 1) ? 1 : -1);
        addd(OP_FSCALE, 0, S_SCALE_RAND, i, a, b);
    }
    {
        double a[] = {0.0, -0.0, 1.0, -3.0, bitsd(0x7FF0000000000000ull), bitsd(0x7FF8000000000000ull), bitsd(1)};
        double b[] = {0.0, 1.0, -1.0, 0.5, -0.5, 1074.0, -1075.0, 2000.0, -2000.0, 1e10, -1e10, 100000.5,
                      bitsd(0x7FF0000000000000ull), -bitsd(0x7FF0000000000000ull), bitsd(0x7FF8000000000000ull)};
        int j = 0;
        for (size_t p = 0; p < sizeof a / 8; p++)
            for (size_t q = 0; q < sizeof b / 8; q++) addd(OP_FSCALE, 0, S_SCALE_SPEC, j++, a[p], b[q]);
    }
    /* fsqrt over the whole positive range, plus negatives */
    for (int i = 0; i < 200000; i++) addd(OP_FSQRT, 0, S_SQRT_RAND, i, rnd_ld(&s, -1074, 1023, i % 50 == 0), 0);
    for (int i = 0; i < 50000; i++) addd(E_SQRT, 0, S_SQRT_RAND, 200000 + i, rnd_ld(&s, -1074, 1023, 0), 0);
    /* rounding: halfway and near-halfway values, integer boundaries */
    {
        int j = 0;
        double fr[] = {0.0, 0.25, 0.5, 0.75, 0.49999999999999994, 0.5000000000000001};
        for (int k = -2050; k <= 2050; k++)
            for (size_t f = 0; f < sizeof fr / 8; f++) {
                double x = (double)k + (k < 0 ? -fr[f] : fr[f]);
                for (size_t o = 0; o < sizeof round_ops / 4; o++)
                    for (uint32_t rc = 0; rc < 4; rc++) addd(round_ops[o], rc, S_ROUND_HALF, j, x, 0);
                j++;
            }
        double big[] = {32766.5, 32767.0, 32767.5, 32768.0, -32768.0, -32768.5, -32769.0, 2147483646.5,
                        2147483647.0, 2147483647.5, 2147483648.0, -2147483648.0, -2147483648.5, -2147483649.0,
                        ldexp(1, 52) + 0.5, ldexp(1, 52) + 1.5, ldexp(1, 53), ldexp(1, 53) + 2, ldexp(1, 63) - 1024.0,
                        ldexp(1, 63), -ldexp(1, 63), -ldexp(1, 63) - 2048.0, 1e300, -0.0, 1e-300, -1e-300,
                        bitsd(0x7FF0000000000000ull), -bitsd(0x7FF0000000000000ull), bitsd(0x7FF8000000000000ull)};
        for (size_t b = 0; b < sizeof big / 8; b++) {
            for (size_t o = 0; o < sizeof round_ops / 4; o++)
                for (uint32_t rc = 0; rc < 4; rc++) addd(round_ops[o], rc, S_ROUND_HALF, j, big[b], 0);
            j++;
        }
        for (int i = 0; i < 20000; i++) {
            double x = rnd_ld(&s, -10, 70, 1);
            for (size_t o = 0; o < sizeof round_ops / 4; o++)
                for (uint32_t rc = 0; rc < 4; rc++) addd(round_ops[o], rc, S_ROUND_RAND, i, x, 0);
        }
    }
    /* fild of 64-bit integers */
    for (int i = 0; i < 100000; i++) {
        int e = 53 + (int)(splitmix64(&s) % 10);
        uint64_t m = (1ull << e) | (splitmix64(&s) & ((1ull << e) - 1));
        int64_t v = (splitmix64(&s) & 1) ? -(int64_t)m : (int64_t)m;
        if (i < 16) {
            static const int64_t ev[] = {(1ll << 53) + 1, (1ll << 53) + 3, (1ll << 54) + 2, (1ll << 54) + 6,
                                         0x7FFFFFFFFFFFFFFFll, (-0x7FFFFFFFFFFFFFFFll - 1), -((1ll << 53) + 1),
                                         (1ll << 62) + 1, (1ll << 53) + 2, (1ll << 54) + 1, -((1ll << 54) + 2),
                                         0x7FFFFFFFFFFFFC00ll, 0x7FFFFFFFFFFFFBFFll, (1ll << 60) + 0x7FF,
                                         (1ll << 60) + 0x800, (1ll << 60) + 0x801};
            v = ev[i];
        }
        add(OP_FILD64, 0, S_FILD_BIG, i, (uint64_t)v, 0);
        add(OP_FILD64_RT, 0, S_FILD_BIG, i, (uint64_t)v, 0);
        add(OP_FILD64_MUL, 0, S_FILD_BIG, i, (uint64_t)v, dbits(rnd_ld(&s, -40, 10, 0)));
        add(OP_FILD64_ADD, 0, S_FILD_BIG, i, (uint64_t)v, dbits(rnd_ld(&s, -20, 20, 1)));
        int64_t w = (int64_t)(splitmix64(&s) & ((1ull << 53) - 1)) * ((i & 1) ? -1 : 1);
        add(OP_FILD64, 0, S_FILD_SMALL, i, (uint64_t)w, 0);
        add(OP_FILD64_RT, 0, S_FILD_SMALL, i, (uint64_t)w, 0);
        add(OP_FILD64_MUL, 0, S_FILD_SMALL, i, (uint64_t)w, dbits(rnd_ld(&s, -40, 10, 0)));
    }
    for (uint32_t k = 0; k < 7; k++) add(OP_FLDCONST, k, S_CONST, k, 0, 0);
    /* FGlobalMath tables: the exact engine inputs */
    for (uint32_t i = 0; i < 16384; i++) {
        add(E_SINTAB, 0, S_SINTAB, i, 0, 0);
        add(E_SQRTTAB, 0, S_SQRTTAB, i, 0, 0);
    }
    /* appXxx(double) with general double arguments (callers other than the float script natives) */
    for (int i = 0; i < 100000; i++) {
        double x = rnd_ld(&s, -30, 4, 1), y = rnd_ld(&s, 4, 62, 1);
        for (size_t k = 0; k < sizeof eng_ops / 4; k++) {
            uint32_t op = eng_ops[k];
            double a = (op == E_SQRT || op == E_LOGE) ? fabs(x) : x, b = (op == E_SQRT || op == E_LOGE) ? fabs(y) : y;
            if (op == E_EXP) continue;
            addd(op, 0, S_ERSMALL, i, a, 0);
            if (i < 50000) addd(op, 0, S_ERLARGE, i, b, 0);
        }
        addd(E_EXP, 0, S_EEXP, i, (double)((int64_t)(splitmix64(&s) >> 12) - (1ll << 51)) * ldexp(1, -51) * 750.0, 0);
        addd(E_LOGE, 0, S_ELOGE, i, (i & 1) ? 1.0 + rnd_ld(&s, -50, -1, 1) : rnd_ld(&s, -1074, 1023, 0), 0);
        if (i < 50000) addd(E_ATAN2, 0, S_EATAN2, i, rnd_ld(&s, -30, 30, 1), rnd_ld(&s, -30, 30, 1));
    }
    /* _ftol2: values of the appInit timing loop (D += sqrt(D) + 3.14), and edges */
    {
        double D = 0;
        for (uint32_t n = 0, j = 0; n < (1u << 25); n++) {
            double S = sqrt(D);
            D = (S + 3.14) + D;
            if ((n & 127) == 0 || n < 4096) addd(E_FTOL, 0, S_FTOL_LOOP, j++, D, 0);
        }
        double fe[] = {0.0, -0.0, 0.5, -0.5, 1.5, -1.5, 2.5, -2.5, 0.49999999999999994, -0.49999999999999994,
                       1e-300, -1e-300, 2147483647.5, -2147483648.5, 4294967295.5, 4294967296.0, -4294967296.5,
                       ldexp(1, 52) + 0.5, -(ldexp(1, 52) + 0.5), ldexp(1, 62) + 1024.0, ldexp(1, 63) - 1024.0,
                       -(ldexp(1, 63) - 1024.0), -ldexp(1, 63), 123456789.987654321, -987654321.123456789};
        for (size_t i = 0; i < sizeof fe / 8; i++) addd(E_FTOL, 0, S_FTOL_EDGE, (uint32_t)i, fe[i], 0);
        for (int i = 0; i < 20000; i++) addd(E_FTOL, 0, S_FTOL_EDGE, 100 + i, rnd_ld(&s, -10, 62, 1), 0);
        double ub[] = {ldexp(1, 63), ldexp(1, 64), -ldexp(1, 63) - 2048.0, 1e300, -1e300,
                       bitsd(0x7FF0000000000000ull), -bitsd(0x7FF0000000000000ull), bitsd(0x7FF8000000000000ull)};
        for (size_t i = 0; i < sizeof ub / 8; i++) addd(E_FTOL, 0, S_FTOL_UB, (uint32_t)i, ub[i], 0);
    }
    write_file(path, g_recs, g_n * sizeof(Rec));
    printf("{\"records\":%zu}\n", g_n);
}

/* ------------------------------------------------------------------ record comparison */
typedef struct Example { Rec r; Out hw, rt; double ulp; } Example;
typedef struct Stat {
    uint64_t n, m64, m32, nanpay, cc, i64m, xm, flagm, zsign, pushv;
    uint64_t m32_after_m64;      /* float mismatches (stored precision) */
    double max_ulp64;            /* runtime double vs 80-bit hardware value, double ulps (finite, in range) */
    uint64_t max_ulp32;          /* float ulps between the stored floats (finite, same sign) */
    uint64_t max_ulp64r;         /* double ulps between rt double and hw double store (finite) */
    int nex;
    Example ex[4];
} Stat;

static int op_has_float(uint32_t op) {
    return !(op == OP_FIST16 || op == OP_FIST32 || op == OP_FIST64 || op == OP_FIST16NP || op == OP_FIST32NP ||
             op == OP_FILD64_RT || op == E_FTOL);
}
static int op_checks_c2(uint32_t op) { return op == OP_FSIN || op == OP_FCOS || op == OP_FPTAN || op == E_TAN; }

static const char* op_name(uint32_t op) {
    static const char* const n1[] = {"?", "fsin", "fcos", "fptan", "fpatan", "fyl2x", "f2xm1", "fscale", "fsqrt",
                                     "frndint", "fistp_m16", "fistp_m32", "fistp_m64", "fist_m16", "fist_m32",
                                     "fild_m64", "fild_m64+fistp_m64", "fild_m64+fmul_m64", "fild_m64+fadd_m64",
                                     "fld_constant"};
    static const char* const n2[] = {"appSin", "appCos", "appTan", "appAtan", "appAtan2", "appSqrt", "appExp",
                                     "appLoge", "FGlobalMath_sine_table", "FGlobalMath_sqrt_table", "_ftol2"};
    if (op < sizeof n1 / sizeof n1[0]) return n1[op];
    if (op >= E_SIN && op <= E_FTOL) return n2[op - E_SIN];
    return "?";
}

static void compare(const Rec* r, const Out* hw, const Out* rt, Stat* st) {
    int bad = 0;
    double ue = 0;
    st->n++;
    if (op_has_float(r->op)) {
        int n64 = isnan64(hw->r64) && isnan64(rt->r64);
        if (hw->r64 != rt->r64) {
            if (n64) st->nanpay++;
            else { st->m64++; bad = 1; }
        }
        int n32 = isnan32(hw->r32) && isnan32(rt->r32);
        if (hw->r32 != rt->r32 && !n32) {
            st->m32++;
            bad = 1;
            if ((hw->r32 & 0x7FFFFFFFu) == 0 && (rt->r32 & 0x7FFFFFFFu) == 0) st->zsign++;
            else if (!isnan32(hw->r32) && !isnan32(rt->r32) && ((hw->r32 ^ rt->r32) >> 31) == 0) {
                uint64_t u = (uint64_t)llabs(key32(hw->r32) - key32(rt->r32));
                if (u > st->max_ulp32) st->max_ulp32 = u;
            }
        }
        if (!n64 && !isnan64(hw->r64) && !isnan64(rt->r64) && ((hw->r64 ^ rt->r64) >> 63) == 0) {
            uint64_t u = (uint64_t)llabs(key64(hw->r64) - key64(rt->r64));
            if (u > st->max_ulp64r) st->max_ulp64r = u;
        }
        ue = ulp_err80(bitsd(rt->r64), hw->r80);
        if (ue > st->max_ulp64) st->max_ulp64 = ue;
    } else if (hw->i64 != rt->i64) {
        st->i64m++;
        bad = 1;
    }
    if (op_checks_c2(r->op) && ((hw->fsw ^ rt->fsw) & FSW_C2)) { st->cc++; bad = 1; }
    if (r->op == OP_FPTAN && (hw->flags & 1) != (rt->flags & 1)) { st->flagm++; bad = 1; }
    if (r->op == OP_FPTAN && (hw->flags & 1) && (rt->flags & 1) && hw->x != rt->x) { st->pushv++; bad = 1; }
    if ((r->op == E_SINTAB || r->op == E_SQRTTAB) && hw->x != rt->x) { st->xm++; bad = 1; }
    if (bad && st->nex < 4) {
        Example* e = &st->ex[st->nex++];
        e->r = *r; e->hw = *hw; e->rt = *rt; e->ulp = ue;
    }
}

/* JSON number, or a string for non-finite values */
static const char* jnum(char* buf, double v) {
    if (isnan(v)) strcpy(buf, signbit(v) ? "\"-nan\"" : "\"nan\"");
    else if (isinf(v)) strcpy(buf, v < 0 ? "\"-inf\"" : "\"inf\"");
    else sprintf(buf, "%.17g", v);
    return buf;
}

static void print_example(FILE* f, const Example* e) {
    char h80[32], b1[40], b2[40], b3[40];
    hex80(h80, e->hw.r80);
    fprintf(f, "{\"a\":\"%016llx\",\"a_val\":%s,\"b\":\"%016llx\",\"aux\":%u,\"idx\":%u,\"hw80\":\"%s\","
               "\"hw64\":\"%016llx\",\"rt64\":\"%016llx\",\"hw64_val\":%s,\"rt64_val\":%s,"
               "\"hw32\":\"%08x\",\"rt32\":\"%08x\",\"hw_i64\":\"%016llx\",\"rt_i64\":\"%016llx\","
               "\"hw_fsw\":\"%04x\",\"rt_fsw\":\"%04x\",\"hw_x\":\"%016llx\",\"rt_x\":\"%016llx\",\"ulp64_vs_hw80\":%.4g}",
            (unsigned long long)e->r.a, jnum(b1, bitsd(e->r.a)), (unsigned long long)e->r.b, e->r.aux, e->r.idx, h80,
            (unsigned long long)e->hw.r64, (unsigned long long)e->rt.r64, jnum(b2, bitsd(e->hw.r64)), jnum(b3, bitsd(e->rt.r64)),
            e->hw.r32, e->rt.r32, (unsigned long long)e->hw.i64, (unsigned long long)e->rt.i64, e->hw.fsw, e->rt.fsw,
            (unsigned long long)e->hw.x, (unsigned long long)e->rt.x, e->ulp);
}

static void cmp(const char* in_path, const char* hw_path, const char* out_path, const char* mlist) {
    size_t ni, nh;
    Rec* recs = (Rec*)read_file(in_path, &ni);
    Out* hw = (Out*)read_file(hw_path, &nh);
    ni /= sizeof(Rec);
    nh /= sizeof(Out);
    if (ni != nh) { fprintf(stderr, "record count mismatch %zu %zu\n", ni, nh); exit(2); }
    CPU c;
    cpu_init(&c, 0);
    FILE* f = fopen(out_path, "w");
    fprintf(f, "{\"records\":%zu,\"models\":[\n", ni);
    int firstm = 1;
    for (int mi = 0; mi < NMODELS; mi++) {
        if (!model_enabled(mlist, mi)) continue;
        Stat* st = (Stat*)calloc((size_t)NSETS * OP_LIMIT, sizeof(Stat));
        x87_setcw(0x027F);
        for (size_t i = 0; i < ni; i++) {
            Out o;
            rt_eval(&c, &models[mi], &recs[i], &o);
            compare(&recs[i], &hw[i], &o, &st[recs[i].set * OP_LIMIT + recs[i].op]);
        }
        fprintf(f, "%s{\"model\":\"%s\",\"groups\":[\n", firstm ? "" : ",\n", models[mi].name);
        firstm = 0;
        int first = 1;
        for (int s = 0; s < NSETS; s++)
            for (int op = 0; op < OP_LIMIT; op++) {
                Stat* t = &st[s * OP_LIMIT + op];
                if (!t->n) continue;
                fprintf(f, "%s {\"set\":\"%s\",\"op\":\"%s\",\"n\":%llu,\"mismatch_double\":%llu,\"mismatch_float\":%llu,"
                           "\"float_zero_sign_only\":%llu,\"nan_payload_only\":%llu,\"c2_mismatch\":%llu,"
                           "\"int_mismatch\":%llu,\"arg_mismatch\":%llu,\"fptan_push_mismatch\":%llu,\"fptan_pushed_value_mismatch\":%llu,"
                           "\"max_ulp_double_vs_hw80\":%.4g,\"max_ulp_double_vs_hw_double\":%llu,\"max_ulp_float\":%llu,"
                           "\"examples\":[",
                        first ? "" : ",\n", set_names[s], op_name((uint32_t)op), (unsigned long long)t->n,
                        (unsigned long long)t->m64, (unsigned long long)t->m32, (unsigned long long)t->zsign,
                        (unsigned long long)t->nanpay, (unsigned long long)t->cc, (unsigned long long)t->i64m,
                        (unsigned long long)t->xm, (unsigned long long)t->flagm, (unsigned long long)t->pushv, t->max_ulp64,
                        (unsigned long long)t->max_ulp64r, (unsigned long long)t->max_ulp32);
                for (int k = 0; k < t->nex; k++) {
                    if (k) fputc(',', f);
                    print_example(f, &t->ex[k]);
                }
                fprintf(f, "]}");
                first = 0;
            }
        fprintf(f, "\n]}");
        free(st);
    }
    fprintf(f, "\n]}\n");
    fclose(f);
    printf("{\"compared\":%zu,\"out\":\"%s\"}\n", ni, out_path);
}

/* ------------------------------------------------------------------ exhaustive float arguments */
typedef struct KArgs { const void* in; uint64_t n; float* r32; double* r64; uint8_t* r80; uint16_t* sw; uint16_t cw[4]; } KArgs;
typedef void (*Kernel)(KArgs*);
void x87k_sin(KArgs*); void x87k_cos(KArgs*); void x87k_tan(KArgs*); void x87k_atan(KArgs*);
void x87k_sqrt(KArgs*); void x87k_exp(KArgs*); void x87k_loge(KArgs*); void x87k_atan2(KArgs*);
static const Kernel kernels[X_COUNT] = {x87k_sin, x87k_cos, x87k_tan, x87k_atan, x87k_sqrt, x87k_exp, x87k_loge};

static XrtFn model_fn(const Model* m, int op) {
    switch (op) {
    case X_SIN: return m->sin; case X_COS: return m->cos; case X_TAN: return m->tan; case X_ATAN: return m->atan;
    case X_SQRT: return m->sqrt; case X_EXP: return m->exp; default: return m->loge;
    }
}

/* argument classes for reporting */
enum { C_ZERO_TINY, C_SMALL, C_UNIT, C_MED, C_LARGE, C_OOR, C_NAN, NCLASS };
static const char* const class_names[NCLASS] = {"|x|<2^-30", "2^-30<=|x|<1", "1<=|x|<2^10", "2^10<=|x|<2^20",
                                                 "2^20<=|x|<2^63", "|x|>=2^63_or_inf", "nan"};
static int arg_class(uint32_t b) {
    uint32_t e = (b >> 23) & 0xFF;
    if (e == 0xFF) return (b & 0x7FFFFF) ? C_NAN : C_OOR;
    int ue = (int)e - 127;
    if (ue < -30) return C_ZERO_TINY;
    if (ue < 0) return C_SMALL;
    if (ue < 10) return C_UNIT;
    if (ue < 20) return C_MED;
    if (ue < 63) return C_LARGE;
    return C_OOR;
}

typedef struct XStat {
    uint64_t m32[NCLASS], m64[NCLASS], nanpay, zsign, max_ulp32;
    uint64_t hw_nan_rt_num, rt_nan_hw_num;
    double max_ulp64;              /* rt double vs hw 80-bit, classes below C_OOR, finite */
    uint32_t max_ulp64_arg;
    uint64_t max_ulp32c[NCLASS];   /* per argument class: float ulps (finite, same sign) */
    double max_ulp64c[NCLASS];     /* per argument class: rt double vs hw 80-bit, double ulps */
    uint64_t m32_1ulp[NCLASS];     /* float mismatches of exactly one ulp */
    uint32_t ex_n[NCLASS];
    uint32_t ex[NCLASS][6][4];     /* arg, hw32, rt32, (unused) */
} XStat;

typedef struct XMis { uint32_t arg, hw32, rt32, pad; uint8_t hw80[16]; } XMis;

typedef struct XShared {
    int op;
    const char* mlist;
    volatile LONG next;
    ChunkHash* hw_hash;
    ChunkHash* rt_hash[NMODELS];
    XStat stat[NMODELS];
    CRITICAL_SECTION lock;
    XMis* mis[NMODELS];
    size_t nmis[NMODELS], capmis;
    int mis_overflow;
} XShared;
typedef struct XThread { XShared* sh; int t; } XThread;

static void xstat_merge(XStat* d, const XStat* s) {
    for (int k = 0; k < NCLASS; k++) {
        d->m32[k] += s->m32[k];
        d->m64[k] += s->m64[k];
        d->m32_1ulp[k] += s->m32_1ulp[k];
        if (s->max_ulp32c[k] > d->max_ulp32c[k]) d->max_ulp32c[k] = s->max_ulp32c[k];
        if (s->max_ulp64c[k] > d->max_ulp64c[k]) d->max_ulp64c[k] = s->max_ulp64c[k];
        for (uint32_t j = 0; j < s->ex_n[k] && d->ex_n[k] < 6; j++) memcpy(d->ex[k][d->ex_n[k]++], s->ex[k][j], 16);
    }
    d->nanpay += s->nanpay;
    d->zsign += s->zsign;
    d->hw_nan_rt_num += s->hw_nan_rt_num;
    d->rt_nan_hw_num += s->rt_nan_hw_num;
    if (s->max_ulp32 > d->max_ulp32) d->max_ulp32 = s->max_ulp32;
    if (s->max_ulp64 > d->max_ulp64) { d->max_ulp64 = s->max_ulp64; d->max_ulp64_arg = s->max_ulp64_arg; }
}

static DWORD WINAPI x_worker(LPVOID p) {
    XThread* th = (XThread*)p;
    XShared* sh = th->sh;
    CPU c;
    cpu_init(&c, th->t);
    x87_setcw(0x027F);
    float* in = (float*)malloc(CHUNK * 4);
    float* r32 = (float*)malloc(CHUNK * 4);
    double* r64 = (double*)malloc(CHUNK * 8);
    uint8_t* r80 = (uint8_t*)malloc(CHUNK * 16);
    uint16_t* sw = (uint16_t*)malloc(CHUNK * 2);
    XStat* ls = (XStat*)calloc(NMODELS, sizeof(XStat));
    XMis* lm = (XMis*)malloc(sizeof(XMis) * 65536);
    for (;;) {
        LONG k = InterlockedIncrement(&sh->next) - 1;
        if (k >= (LONG)NCHUNKS) break;
        for (uint32_t i = 0; i < CHUNK; i++) { uint32_t b = ((uint32_t)k << CHUNK_BITS) | i; memcpy(&in[i], &b, 4); }
        KArgs ka = {in, CHUNK, r32, r64, r80, sw, {0, 0, 0, 0}};
        kernels[sh->op](&ka);
        uint64_t h32 = FNV_INIT, h80 = FNV_INIT, hcc = FNV_INIT;
        for (uint32_t i = 0; i < CHUNK; i++) {
            uint16_t cc = (uint16_t)(sw[i] & FSW_CC);
            h32 = fnv1a(h32, &r32[i], 4);
            h80 = fnv1a(h80, &r80[i * 16], 10);
            hcc = fnv1a(hcc, &cc, 2);
        }
        sh->hw_hash[k].h32 = h32; sh->hw_hash[k].h80 = h80; sh->hw_hash[k].hcc = hcc;
        for (int mi = 0; mi < NMODELS; mi++) {
            if (!model_enabled(sh->mlist, mi)) continue;
            XrtFn fn = model_fn(&models[mi], sh->op);
            XStat* st = &ls[mi];
            size_t nl = 0;
            uint64_t hr = FNV_INIT;
            for (uint32_t i = 0; i < CHUNK; i++) {
                uint32_t arg = ((uint32_t)k << CHUNK_BITS) | i, hb = fbits(r32[i]);
                double v;
                fpu_reset(&c);
                uint32_t rb = exec_native(&c, fn, arg, &v);
                hr = fnv1a(hr, &rb, 4);
                int cls = arg_class(arg);
                uint64_t hd = dbits(r64[i]), rd = dbits(v);
                if (hd != rd && !(isnan64(hd) && isnan64(rd))) st->m64[cls]++;
                if (cls < C_OOR) {
                    double ue = ulp_err80(v, &r80[i * 16]);
                    if (ue > st->max_ulp64) { st->max_ulp64 = ue; st->max_ulp64_arg = arg; }
                    if (ue > st->max_ulp64c[cls]) st->max_ulp64c[cls] = ue;
                }
                if (hb == rb) continue;
                if (isnan32(hb) && isnan32(rb)) { st->nanpay++; continue; }
                st->m32[cls]++;
                if (isnan32(hb)) st->hw_nan_rt_num++;
                else if (isnan32(rb)) st->rt_nan_hw_num++;
                else if (((hb ^ rb) >> 31) == 0) {
                    uint64_t u = (uint64_t)llabs(key32(hb) - key32(rb));
                    if (u > st->max_ulp32) st->max_ulp32 = u;
                    if (u > st->max_ulp32c[cls]) st->max_ulp32c[cls] = u;
                    if (u == 1) st->m32_1ulp[cls]++;
                } else if (((hb | rb) & 0x7FFFFFFFu) == 0) st->zsign++;
                if (st->ex_n[cls] < 6) {
                    uint32_t* e = st->ex[cls][st->ex_n[cls]++];
                    e[0] = arg; e[1] = hb; e[2] = rb; e[3] = 0;
                }
                if (cls < C_LARGE && nl < 65536) {
                    XMis* x = &lm[nl++];
                    x->arg = arg; x->hw32 = hb; x->rt32 = rb; x->pad = 0;
                    memcpy(x->hw80, &r80[i * 16], 16);
                }
            }
            sh->rt_hash[mi][k].h32 = hr;
            if (nl) {
                EnterCriticalSection(&sh->lock);
                if (sh->nmis[mi] + nl > sh->capmis) sh->mis_overflow = 1;
                if (sh->nmis[mi] + nl <= sh->capmis) {
                    memcpy(&sh->mis[mi][sh->nmis[mi]], lm, nl * sizeof(XMis));
                    sh->nmis[mi] += nl;
                }
                LeaveCriticalSection(&sh->lock);
            }
        }
    }
    EnterCriticalSection(&sh->lock);
    for (int mi = 0; mi < NMODELS; mi++) xstat_merge(&sh->stat[mi], &ls[mi]);
    LeaveCriticalSection(&sh->lock);
    free(in); free(r32); free(r64); free(r80); free(sw); free(ls); free(lm);
    return 0;
}

static int cmp_mis(const void* a, const void* b) {
    uint32_t x = ((const XMis*)a)->arg, y = ((const XMis*)b)->arg;
    return x < y ? -1 : x > y;
}

static void exhaustive(const char* which, const char* hash_prefix, const char* out_path, const char* mis_prefix,
                       const char* mlist, const char* cores, int nofma) {
    DWORD_PTR mask = select_mask(cores);
    int n = thread_count(mask);
    FILE* f = fopen(out_path, "a");
    for (int op = 0; op < X_COUNT; op++) {
        if (strcmp(which, "all") && strcmp(which, x_names[op])) continue;
        XShared* sh = (XShared*)calloc(1, sizeof(XShared));
        sh->op = op;
        sh->mlist = mlist;
        sh->hw_hash = (ChunkHash*)calloc(NCHUNKS, sizeof(ChunkHash));
        sh->capmis = 4u << 20;
        for (int mi = 0; mi < NMODELS; mi++) {
            sh->rt_hash[mi] = (ChunkHash*)calloc(NCHUNKS, sizeof(ChunkHash));
            if (model_enabled(mlist, mi)) sh->mis[mi] = (XMis*)malloc(sh->capmis * sizeof(XMis));
        }
        InitializeCriticalSection(&sh->lock);
        XThread th[64];
        for (int t = 0; t < n && t < 64; t++) { th[t].sh = sh; th[t].t = t; }
        DWORD t0 = GetTickCount();
        run_threads(n, x_worker, th, sizeof(XThread), mask);
        DWORD ms = GetTickCount() - t0;
        char path[512];
        snprintf(path, sizeof path, "%s_%s.bin", hash_prefix, x_names[op]);
        write_file(path, sh->hw_hash, NCHUNKS * sizeof(ChunkHash));
        uint64_t hall = fnv1a(FNV_INIT, sh->hw_hash, NCHUNKS * sizeof(ChunkHash));
        for (int mi = 0; mi < NMODELS; mi++) {
            if (!model_enabled(mlist, mi)) continue;
            XStat* st = &sh->stat[mi];
            uint64_t tot = 0, fin = 0;
            for (int k = 0; k < NCLASS; k++) { tot += st->m32[k]; if (k < C_OOR) fin += st->m32[k]; }
            qsort(sh->mis[mi], sh->nmis[mi], sizeof(XMis), cmp_mis);
            snprintf(path, sizeof path, "%s_%s_%s%s.bin", mis_prefix, x_names[op], models[mi].name, nofma ? "_nofma" : "");
            write_file(path, sh->mis[mi], sh->nmis[mi] * sizeof(XMis));
            uint64_t rall = fnv1a(FNV_INIT, sh->rt_hash[mi], NCHUNKS * sizeof(ChunkHash));
            fprintf(f, "{\"op\":\"%s\",\"model\":\"%s\",\"fma3\":%s,\"cores\":\"%s\",\"threads\":%d,\"ms\":%lu,"
                       "\"inputs\":4294967296,\"hw_hash\":\"%016llx\",\"rt_hash\":\"%016llx\",\"mismatch_float\":%llu,"
                       "\"mismatch_float_finite_in_range\":%llu,\"nan_payload_only\":%llu,\"zero_sign_only\":%llu,"
                       "\"hw_nan_rt_number\":%llu,\"rt_nan_hw_number\":%llu,\"max_ulp_float_same_sign\":%llu,"
                       "\"max_ulp_double_vs_hw80_in_range\":%.4g,\"max_ulp_double_arg\":\"%08x\",\"mismatch_list_below_2^20\":%zu,"
                       "\"mismatch_list_complete\":%s,\"by_class\":{",
                    x_names[op], models[mi].name, nofma ? "false" : "true", cores ? cores : "all", n, ms,
                    (unsigned long long)hall, (unsigned long long)rall, (unsigned long long)tot,
                    (unsigned long long)fin, (unsigned long long)st->nanpay, (unsigned long long)st->zsign,
                    (unsigned long long)st->hw_nan_rt_num, (unsigned long long)st->rt_nan_hw_num,
                    (unsigned long long)st->max_ulp32, st->max_ulp64, st->max_ulp64_arg, sh->nmis[mi],
                    sh->mis_overflow ? "false" : "true");
            char nb[40];
            for (int k = 0; k < NCLASS; k++) {
                fprintf(f, "%s\"%s\":{\"float\":%llu,\"float_1ulp\":%llu,\"max_ulp_float\":%llu,\"double\":%llu,"
                           "\"max_ulp_double_vs_hw80\":%.4g,\"examples\":[", k ? "," : "", class_names[k],
                        (unsigned long long)st->m32[k], (unsigned long long)st->m32_1ulp[k], (unsigned long long)st->max_ulp32c[k],
                        (unsigned long long)st->m64[k], st->max_ulp64c[k]);
                for (uint32_t j = 0; j < st->ex_n[k]; j++)
                    fprintf(f, "%s[\"%08x\",%s,\"%08x\",\"%08x\"]", j ? "," : "", st->ex[k][j][0], jnum(nb, (double)bitsf(st->ex[k][j][0])),
                            st->ex[k][j][1], st->ex[k][j][2]);
                fprintf(f, "]}");
            }
            fprintf(f, "}}\n");
            fflush(f);
            printf("%s %s%s: float mismatches %llu (finite in-range %llu), max ulp %llu, %lu ms\n", x_names[op],
                   models[mi].name, nofma ? " nofma" : "", (unsigned long long)tot, (unsigned long long)fin,
                   (unsigned long long)st->max_ulp32, ms);
            fflush(stdout);
            free(sh->mis[mi]);
            free(sh->rt_hash[mi]);
        }
        DeleteCriticalSection(&sh->lock);
        free(sh->hw_hash);
        free(sh);
    }
    fclose(f);
}

/* Host dependence of the runtime itself: the x64 UCRT dispatches sin/cos/tan/atan2/log2/expm1/... to
 * FMA3 code paths when the CPU has FMA3. Evaluate the runtime model with the FMA3 paths enabled and
 * disabled (_set_FMA3_enable, a process-wide switch: the work runs in 2^28-argument groups, all threads
 * with FMA3 on storing results, then all threads with FMA3 off comparing). */
typedef struct FJob { int op, phase, t; uint32_t base, count; float* buf; volatile LONG* next;
                      uint64_t diff[NCLASS]; uint32_t ex[4][3]; int nex; } FJob;
static DWORD WINAPI fma_worker(LPVOID p) {
    FJob* j = (FJob*)p;
    CPU c;
    cpu_init(&c, j->t);
    XrtFn fn = model_fn(&models[0], j->op);
    for (;;) {
        LONG k = InterlockedIncrement(j->next) - 1;
        if ((uint64_t)k * 65536 >= j->count) break;
        for (uint32_t i = (uint32_t)k * 65536; i < (uint32_t)k * 65536 + 65536 && i < j->count; i++) {
            uint32_t arg = j->base + i;
            double v;
            fpu_reset(&c);
            uint32_t rb = exec_native(&c, fn, arg, &v);
            if (j->phase == 0) { memcpy(&j->buf[i], &rb, 4); continue; }
            uint32_t ab;
            memcpy(&ab, &j->buf[i], 4);
            if (ab == rb || (isnan32(ab) && isnan32(rb))) continue;
            j->diff[arg_class(arg)]++;
            if (j->nex < 4) { j->ex[j->nex][0] = arg; j->ex[j->nex][1] = ab; j->ex[j->nex][2] = rb; j->nex++; }
        }
    }
    return 0;
}

static void fmadiff(const char* which, const char* out_path) {
    const uint32_t G = 1u << 28;
    float* buf = (float*)malloc((size_t)G * 4);
    int n = thread_count(0);
    FILE* f = fopen(out_path, "a");
    for (int op = 0; op < X_COUNT; op++) {
        if (strcmp(which, "all") && strcmp(which, x_names[op])) continue;
        uint64_t diff[NCLASS] = {0};
        uint32_t ex[8][3];
        int nex = 0;
        DWORD t0 = GetTickCount();
        for (uint32_t g = 0; g < 16; g++) {
            for (int phase = 0; phase < 2; phase++) {
                _set_FMA3_enable(phase == 0);
                FJob jobs[64];
                volatile LONG next = 0;
                for (int t = 0; t < n && t < 64; t++) {
                    memset(&jobs[t], 0, sizeof jobs[t]);
                    jobs[t].op = op; jobs[t].phase = phase; jobs[t].t = t; jobs[t].base = g * G; jobs[t].count = G;
                    jobs[t].buf = buf; jobs[t].next = &next;
                }
                run_threads(n, fma_worker, jobs, sizeof(FJob), 0);
                if (phase == 1)
                    for (int t = 0; t < n && t < 64; t++) {
                        for (int k = 0; k < NCLASS; k++) diff[k] += jobs[t].diff[k];
                        for (int e = 0; e < jobs[t].nex && nex < 8; e++) memcpy(ex[nex++], jobs[t].ex[e], 12);
                    }
            }
        }
        _set_FMA3_enable(1);
        uint64_t tot = 0;
        fprintf(f, "{\"op\":\"%s\",\"model\":\"rt\",\"compare\":\"fma3_on_vs_off\",\"inputs\":4294967296,\"ms\":%lu,\"by_class\":{",
                x_names[op], GetTickCount() - t0);
        for (int k = 0; k < NCLASS; k++) {
            fprintf(f, "%s\"%s\":%llu", k ? "," : "", class_names[k], (unsigned long long)diff[k]);
            tot += diff[k];
        }
        fprintf(f, "},\"float_differences\":%llu,\"examples\":[", (unsigned long long)tot);
        for (int e = 0; e < nex; e++) fprintf(f, "%s[\"%08x\",\"%08x\",\"%08x\"]", e ? "," : "", ex[e][0], ex[e][1], ex[e][2]);
        fprintf(f, "]}\n");
        fflush(f);
        printf("%s: runtime float results differing between FMA3 on/off: %llu\n", x_names[op], (unsigned long long)tot);
        fflush(stdout);
    }
    fclose(f);
    free(buf);
}

/* atan2 over random float pairs (2^64 pairs cannot be enumerated) */
static void atan2_pairs(uint64_t npairs, const char* out_path, const char* mlist) {
    uint64_t s = 0xA7A2ull;
    CPU c;
    cpu_init(&c, 0);
    x87_setcw(0x027F);
    const uint32_t B = 4096;
    uint32_t* in = (uint32_t*)malloc(B * 8);
    float* r32 = (float*)malloc(B * 4);
    double* r64 = (double*)malloc(B * 8);
    uint8_t* r80 = (uint8_t*)malloc(B * 16);
    uint16_t* sw = (uint16_t*)malloc(B * 2);
    uint64_t mism[NMODELS] = {0}, nanp[NMODELS] = {0}, maxu[NMODELS] = {0}, fin[NMODELS] = {0};
    uint32_t ex[NMODELS][4][4];
    int nex[NMODELS] = {0};
    for (uint64_t done = 0; done < npairs; done += B) {
        for (uint32_t i = 0; i < B; i++) {
            uint64_t r = splitmix64(&s);
            in[2 * i] = (uint32_t)r;
            in[2 * i + 1] = (uint32_t)(r >> 32);
            if (i & 1) {          /* half of the pairs: moderate magnitudes (exponents -20..20) */
                in[2 * i] = (in[2 * i] & 0x807FFFFFu) | ((uint32_t)(107 + (r >> 8) % 41) << 23);
                in[2 * i + 1] = (in[2 * i + 1] & 0x807FFFFFu) | ((uint32_t)(107 + (r >> 20) % 41) << 23);
            }
        }
        KArgs ka = {in, B, r32, r64, r80, sw, {0, 0, 0, 0}};
        x87k_atan2(&ka);
        for (int mi = 0; mi < NMODELS; mi++) {
            if (!model_enabled(mlist, mi)) continue;
            for (uint32_t i = 0; i < B; i++) {
                double v;
                fpu_reset(&c);
                uint32_t rb = exec_native2(&c, models[mi].atan2, in[2 * i], in[2 * i + 1], &v), hb = fbits(r32[i]);
                if (hb == rb) continue;
                if (isnan32(hb) && isnan32(rb)) { nanp[mi]++; continue; }
                mism[mi]++;
                if (!isnan32(hb) && !isnan32(rb) && ((hb ^ rb) >> 31) == 0) {
                    fin[mi]++;
                    uint64_t u = (uint64_t)llabs(key32(hb) - key32(rb));
                    if (u > maxu[mi]) maxu[mi] = u;
                }
                if (nex[mi] < 4) { uint32_t* e = ex[mi][nex[mi]++]; e[0] = in[2 * i]; e[1] = in[2 * i + 1]; e[2] = hb; e[3] = rb; }
            }
        }
    }
    FILE* f = fopen(out_path, "a");
    for (int mi = 0; mi < NMODELS; mi++) {
        if (!model_enabled(mlist, mi)) continue;
        fprintf(f, "{\"op\":\"atan2\",\"model\":\"%s\",\"inputs\":%llu,\"mismatch_float\":%llu,\"mismatch_float_finite\":%llu,"
                   "\"nan_payload_only\":%llu,\"max_ulp_float_same_sign\":%llu,\"examples\":[",
                models[mi].name, (unsigned long long)npairs, (unsigned long long)mism[mi], (unsigned long long)fin[mi],
                (unsigned long long)nanp[mi], (unsigned long long)maxu[mi]);
        for (int j = 0; j < nex[mi]; j++)
            fprintf(f, "%s[\"%08x\",\"%08x\",\"%08x\",\"%08x\"]", j ? "," : "", ex[mi][j][0], ex[mi][j][1], ex[mi][j][2], ex[mi][j][3]);
        fprintf(f, "]}\n");
        printf("atan2 %s: %llu mismatches of %llu (finite %llu, max ulp %llu)\n", models[mi].name,
               (unsigned long long)mism[mi], (unsigned long long)npairs, (unsigned long long)fin[mi], (unsigned long long)maxu[mi]);
    }
    fclose(f);
}

/* ------------------------------------------------------------------ appInit timing loop */
static void dummy(uint32_t steps, const char* hw_path) {
    size_t nh;
    ChunkHash* hw = (ChunkHash*)read_file(hw_path, &nh);
    nh /= sizeof(ChunkHash);
    CPU cpu;
    CPU* c = &cpu;
    cpu_init(c, 0);
    const uint32_t D = 0x00080000u, S = 0x00080008u;
    wrf64(D, 0.0);
    uint32_t nblocks = (steps + 65535) / 65536, bad = 0, first_bad = 0xFFFFFFFFu;
    for (uint32_t b = 0; b < nblocks; b++) {
        uint64_t hd = FNV_INIT, hi = FNV_INIT;
        for (uint32_t s = 0; s < 65536 && b * 65536 + s < steps; s++) {
            push32(c, rd32(D + 4));                               /* mov edx, [ebp - 0x54]; push edx */
            push32(c, rd32(D));                                   /* mov eax, [ebp - 0x58]; push eax */
            CALL(models[0].sqrt, RA, RA);                         /* call appSqrt */
            wrf64(S, *ST(c, 0));                                  /* fstp qword ptr [ebp - 0x344] */
            fpop(c);
            c->r[ESP] += 8;
            fpush(c, rdf64(S));                                   /* fld qword ptr [ebp - 0x344] */
            { double m_ = rdf64(GC_314); *ST(c, 0) = *ST(c, 0) + m_; }
            { double m_ = rdf64(D); *ST(c, 0) = *ST(c, 0) + m_; }
            wrf64(D, *ST(c, 0));                                  /* fst qword ptr [ebp - 0x58] */
            CALL(models[0].ftol, RA, RA);                         /* call _ftol2 */
            uint64_t dv = rd64(D), ti = ((uint64_t)c->r[EDX] << 32) | c->r[EAX];
            hd = fnv1a(hd, &dv, 8);
            hi = fnv1a(hi, &ti, 8);
        }
        if (b < nh && (hw[b].h32 != hd || hw[b].h80 != hi)) { bad++; if (first_bad == 0xFFFFFFFFu) first_bad = b; }
    }
    double dfin = rdf64(D);
    printf("{\"steps\":%u,\"blocks\":%u,\"hw_blocks\":%zu,\"mismatching_blocks\":%u,\"first_bad_block\":%d,"
           "\"final_D\":%.17g,\"final_D_bits\":\"%016llx\",\"x87_top_after\":%u}\n",
           steps, nblocks, nh, bad, (int)first_bad, dfin, (unsigned long long)dbits(dfin), c->top);
}

/* ------------------------------------------------------------------ main */
int main(int argc, char** argv) {
    guest_init();
    int nofma = 0;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "nofma")) nofma = 1;
    if (nofma) _set_FMA3_enable(0);
    if (argc >= 2 && !strcmp(argv[1], "info")) {
        int r[4];
        __cpuid(r, 1);
        DWORD_PTR p, e;
        core_masks(&p, &e);
        printf("{\"cpuid1_ecx_fma\":%d,\"crt_fma3_enabled\":%d,\"x87_cw\":\"%04x\",\"pmask\":\"%llx\",\"emask\":\"%llx\"}\n",
               (r[2] >> 12) & 1, _get_FMA3_enable(), x87_getcw(), (unsigned long long)p, (unsigned long long)e);
        return 0;
    }
    if (argc >= 3 && !strcmp(argv[1], "gen")) { gen(argv[2]); return 0; }
    if (argc >= 5 && !strcmp(argv[1], "cmp")) { cmp(argv[2], argv[3], argv[4], argc >= 6 ? argv[5] : "all"); return 0; }
    if (argc >= 6 && !strcmp(argv[1], "exhaustive")) {
        exhaustive(argv[2], argv[3], argv[4], argv[5], argc >= 7 ? argv[6] : "rt", argc >= 8 ? argv[7] : "all", nofma);
        return 0;
    }
    if (argc >= 5 && !strcmp(argv[1], "run")) {       /* raw model outputs for offline analysis */
        size_t ni;
        Rec* recs = (Rec*)read_file(argv[2], &ni);
        ni /= sizeof(Rec);
        int mi = 0;
        for (int i = 0; i < NMODELS; i++)
            if (!strcmp(argv[3], models[i].name)) mi = i;
        Out* outs = (Out*)calloc(ni ? ni : 1, sizeof(Out));
        CPU c;
        cpu_init(&c, 0);
        x87_setcw(0x027F);
        for (size_t i = 0; i < ni; i++) rt_eval(&c, &models[mi], &recs[i], &outs[i]);
        write_file(argv[4], outs, ni * sizeof(Out));
        printf("{\"records\":%zu,\"model\":\"%s\"}\n", ni, models[mi].name);
        return 0;
    }
    if (argc >= 4 && !strcmp(argv[1], "atan2")) { atan2_pairs(strtoull(argv[2], NULL, 0), argv[3], argc >= 5 ? argv[4] : "all"); return 0; }
    if (argc >= 4 && !strcmp(argv[1], "fmadiff")) { fmadiff(argv[2], argv[3]); return 0; }
    if (argc >= 4 && !strcmp(argv[1], "dummy")) { dummy((uint32_t)strtoul(argv[2], NULL, 0), argv[3]); return 0; }
    if (argc >= 5 && !strcmp(argv[1], "eval")) {
        int mi = 0;
        for (int i = 0; i < NMODELS; i++)
            if (!strcmp(argv[2], models[i].name)) mi = i;
        Rec r = {0};
        r.op = (uint32_t)strtoul(argv[3], NULL, 0);
        r.a = strtoull(argv[4], NULL, 16);
        r.b = argc >= 6 ? strtoull(argv[5], NULL, 16) : 0;
        CPU c;
        cpu_init(&c, 0);
        Out o;
        rt_eval(&c, &models[mi], &r, &o);
        printf("{\"r64\":\"%016llx\",\"r64_val\":%.17g,\"r32\":\"%08x\",\"i64\":\"%016llx\",\"fsw\":\"%04x\"}\n",
               (unsigned long long)o.r64, bitsd(o.r64), o.r32, (unsigned long long)o.i64, o.fsw);
        return 0;
    }
    fprintf(stderr, "usage: see header comment\n");
    return 2;
}
