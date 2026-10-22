/* x87_hw32.c - 32-bit native x87 reference (real hardware) for the runtime's x87 model.
 *
 * Every operation is written here as inline x87 assembly that mirrors the instruction sequence the
 * engine uses (see README.md); no code of the original modules is executed. FCW is 0x027F (53-bit
 * precision, round to nearest, all exceptions masked), the engine's control word.
 *
 *   x87_hw32 info
 *   x87_hw32 records <inputs.bin> <hw.bin>                 evaluate Rec records (x87_common.h)
 *   x87_hw32 exhaustive <op|all> <hash-prefix> [P|E|all]   all 2^32 float arguments, per-chunk hashes
 *   x87_hw32 dummy <steps> <out.bin>                         appInit timing-loop recurrence, block hashes
 *
 * Build (x86): cl /nologo /O1 /W3 x87_hw32.c   (see build_x87.cmd) */
#include "x87_common.h"

static const double kPiOver16384 = 3.14159265358979323846 / 16384.0;   /* FGlobalMath sine-table step */
static const float k2m14 = 6.103515625e-05f;                             /* 2^-14 (FGlobalMath sqrt table) */
static const double k314 = 3.14;                                         /* appInit timing loop */
static const uint16_t kCW = 0x027F, kCWChop = 0x0E7F;

static void set_cw(void) {
    __asm { fldcw kCW }
}
static uint16_t get_cw(void) {
    uint16_t w;
    __asm { fnstcw w }
    return w;
}

/* NB: in inline assembly ';' starts a comment, so these macros are used on lines of their own */
#define SW __asm { fnstsw sw }
#define ST3 __asm { fld st(0) } __asm { fstp tbyte ptr t80 } __asm { fld st(0) } __asm { fstp qword ptr t64 } __asm { fstp dword ptr t32 }

static void hw_eval(const Rec* r, Out* o) {
    double A, B, X = 0, t64 = 0, one = 0;
    int64_t A64, ti = 0;
    int32_t I = (int32_t)r->idx, t32i = 0;
    int16_t t16 = 0;
    float t32 = 0;
    uint16_t sw = 0, cw = (uint16_t)(0x027F | ((r->aux & 3) << 10)), cw0 = 0x027F;
    uint8_t t80[10];
    uint32_t flags = 0;
    memcpy(&A, &r->a, 8);
    memcpy(&B, &r->b, 8);
    memcpy(&A64, &r->a, 8);
    memset(t80, 0, sizeof t80);
    switch (r->op) {
    case OP_FSIN: case E_SIN:
        __asm { fld qword ptr A
                fsin }
        SW
        ST3
        break;
    case OP_FCOS: case E_COS:
        __asm { fld qword ptr A
                fcos }
        SW
        ST3
        break;
    case OP_FPTAN:
        __asm {
            fld qword ptr A
            fptan
            fnstsw sw
            test sw, 0x400
            jnz tan_oor
            fstp qword ptr one
            mov flags, 1
        tan_oor:
        }
        if (flags) X = one;           /* the value fptan pushed (1.0 for a finite in-range operand) */
        ST3
        break;
    case E_TAN:
        __asm { fld qword ptr A
                fptan
                fnstsw sw
                fstp st(0) }
        ST3
        break;
    case OP_FPATAN: case E_ATAN2:
        __asm { fld qword ptr A
                fld qword ptr B
                fpatan }
        SW
        ST3
        break;
    case E_ATAN:
        __asm { fld qword ptr A
                fld1
                fpatan }
        SW
        ST3
        break;
    case OP_FYL2X:
        __asm { fld qword ptr A
                fld qword ptr B
                fyl2x }
        SW
        ST3
        break;
    case OP_F2XM1:
        __asm { fld qword ptr A
                f2xm1 }
        SW
        ST3
        break;
    case OP_FSCALE:
        __asm { fld qword ptr B
                fld qword ptr A
                fscale
                fnstsw sw
                fstp st(1) }
        ST3
        break;
    case OP_FSQRT: case E_SQRT:
        __asm { fld qword ptr A
                fsqrt }
        SW
        ST3
        break;
    case E_EXP:
        __asm {
            fldl2e
            fmul qword ptr A
            fld st(0)
            frndint
            fxch st(1)
            fsub st(0), st(1)
            f2xm1
            fld1
            faddp st(1), st(0)
            fscale
            fstp st(1)
        }
        SW
        ST3
        break;
    case E_LOGE:
        __asm { fldln2
                fld qword ptr A
                fyl2x }
        SW
        ST3
        break;
    case OP_FRNDINT:
        __asm { fldcw cw
                fld qword ptr A
                frndint
                fnstsw sw
                fldcw cw0 }
        ST3
        break;
    case OP_FIST16:
        __asm { fldcw cw
                fld qword ptr A
                fistp word ptr t16
                fldcw cw0 }
        ti = t16; break;
    case OP_FIST16NP:
        __asm { fldcw cw
                fld qword ptr A
                fist word ptr t16
                fstp st(0)
                fldcw cw0 }
        ti = t16; break;
    case OP_FIST32:
        __asm { fldcw cw
                fld qword ptr A
                fistp dword ptr t32i
                fldcw cw0 }
        ti = t32i; break;
    case OP_FIST32NP:
        __asm { fldcw cw
                fld qword ptr A
                fist dword ptr t32i
                fstp st(0)
                fldcw cw0 }
        ti = t32i; break;
    case OP_FIST64:
        __asm { fldcw cw
                fld qword ptr A
                fistp qword ptr ti
                fldcw cw0 }
        break;
    case OP_FILD64:
        __asm { fild qword ptr A64 }
        ST3
        break;
    case OP_FILD64_RT:
        __asm { fild qword ptr A64
                fistp qword ptr ti }
        break;
    case OP_FILD64_MUL:
        __asm { fild qword ptr A64
                fmul qword ptr B }
        ST3
        break;
    case OP_FILD64_ADD:
        __asm { fild qword ptr A64
                fadd qword ptr B }
        ST3
        break;
    case OP_FLDCONST:
        switch (r->aux) {
        case 0: __asm { fld1 }
            break;
        case 1: __asm { fldl2t }
            break;
        case 2: __asm { fldl2e }
            break;
        case 3: __asm { fldpi }
            break;
        case 4: __asm { fldlg2 }
            break;
        case 5: __asm { fldln2 }
            break;
        default: __asm { fldz }
            break;
        }
        ST3
        break;
    case E_SINTAB:
        __asm {
            fild dword ptr I
            fadd st(0), st(0)
            fmul qword ptr kPiOver16384
            fstp qword ptr X
            fld qword ptr X
            fsin
        }
        SW
        ST3
        break;
    case E_SQRTTAB:
        __asm {
            fild dword ptr I
            fmul dword ptr k2m14
            fstp qword ptr X
            fld qword ptr X
            fsqrt
        }
        SW
        ST3
        break;
    case E_FTOL:      /* reference semantics of _ftol2: truncation toward zero (RC = chop) */
        __asm { fldcw kCWChop
                fld qword ptr A
                fistp qword ptr ti
                fldcw kCW }
        break;
    default:
        fprintf(stderr, "unknown op %u\n", r->op);
        exit(2);
    }
    memcpy(o->r80, t80, 10);
    o->fsw = sw;
    memcpy(&o->r32, &t32, 4);
    memcpy(&o->r64, &t64, 8);
    o->i64 = (uint64_t)ti;
    memcpy(&o->x, &X, 8);
    o->flags = flags;
    o->pad = 0;
}

/* ------------------------------------------------------------------ exhaustive float arguments */
typedef struct XRes { uint8_t r80[10]; uint16_t sw; float r32; } XRes;

static void hw_x(int op, const float* in, XRes* o) {
    uint16_t sw = 0;
    uint8_t t80[10];
    double t64;
    float t32, A = *in;
    switch (op) {     /* the float argument is loaded directly: exact, like the caller's fld dword; fstp qword */
    case X_SIN: __asm { fld dword ptr A
                        fsin } break;
    case X_COS: __asm { fld dword ptr A
                        fcos } break;
    case X_TAN: __asm { fld dword ptr A
                        fptan
                        fstp st(0) } break;
    case X_ATAN: __asm { fld dword ptr A
                         fld1
                         fpatan } break;
    case X_SQRT: __asm { fld dword ptr A
                         fsqrt } break;
    case X_EXP: __asm {
            fldl2e
            fmul dword ptr A
            fld st(0)
            frndint
            fxch st(1)
            fsub st(0), st(1)
            f2xm1
            fld1
            faddp st(1), st(0)
            fscale
            fstp st(1)
        } break;
    case X_LOGE: __asm { fldln2
                         fld dword ptr A
                         fyl2x } break;
    }
    SW
    ST3
    (void)t64;
    memcpy(o->r80, t80, 10);
    o->sw = sw;
    o->r32 = t32;
}

typedef struct XJob { int op; volatile LONG* next; ChunkHash* out; } XJob;

static DWORD WINAPI x_worker(LPVOID p) {
    XJob* j = (XJob*)p;
    set_cw();
    for (;;) {
        LONG k = InterlockedIncrement(j->next) - 1;
        if (k >= (LONG)NCHUNKS) break;
        uint64_t h32 = FNV_INIT, h80 = FNV_INIT, hcc = FNV_INIT;
        for (uint32_t i = 0; i < CHUNK; i++) {
            uint32_t bits = ((uint32_t)k << CHUNK_BITS) | i;
            float f;
            XRes r;
            memcpy(&f, &bits, 4);
            hw_x(j->op, &f, &r);
            uint16_t cc = (uint16_t)(r.sw & FSW_CC);
            h32 = fnv1a(h32, &r.r32, 4);
            h80 = fnv1a(h80, r.r80, 10);
            hcc = fnv1a(hcc, &cc, 2);
        }
        j->out[k].h32 = h32;
        j->out[k].h80 = h80;
        j->out[k].hcc = hcc;
    }
    return 0;
}

static void exhaustive(const char* which, const char* prefix, const char* cores) {
    DWORD_PTR mask = select_mask(cores);
    int n = thread_count(mask);
    for (int op = 0; op < X_COUNT; op++) {
        if (strcmp(which, "all") && strcmp(which, x_names[op])) continue;
        ChunkHash* out = (ChunkHash*)calloc(NCHUNKS, sizeof(ChunkHash));
        volatile LONG next = 0;
        XJob jobs[64];
        for (int t = 0; t < n && t < 64; t++) { jobs[t].op = op; jobs[t].next = &next; jobs[t].out = out; }
        DWORD t0 = GetTickCount();
        run_threads(n, x_worker, jobs, sizeof(XJob), mask);
        char path[512];
        snprintf(path, sizeof path, "%s_%s.bin", prefix, x_names[op]);
        write_file(path, out, NCHUNKS * sizeof(ChunkHash));
        uint64_t all = fnv1a(FNV_INIT, out, NCHUNKS * sizeof(ChunkHash));
        printf("{\"op\":\"%s\",\"cores\":\"%s\",\"threads\":%d,\"ms\":%lu,\"hash\":\"%016llx\"}\n", x_names[op],
               cores ? cores : "all", n, GetTickCount() - t0, (unsigned long long)all);
        fflush(stdout);
        free(out);
    }
}

/* ------------------------------------------------------------------ appInit timing loop */
static void dummy(uint32_t steps, const char* path) {
    double D = 0, S;
    int64_t ti;
    uint32_t nblocks = (steps + 65535) / 65536;
    ChunkHash* out = (ChunkHash*)calloc(nblocks, sizeof(ChunkHash));
    set_cw();
    for (uint32_t b = 0; b < nblocks; b++) {
        uint64_t hd = FNV_INIT, hi = FNV_INIT;
        for (uint32_t s = 0; s < 65536 && b * 65536 + s < steps; s++) {
            __asm {
                fld qword ptr D
                fsqrt
                fstp qword ptr S
                fld qword ptr S
                fadd qword ptr k314
                fadd qword ptr D
                fst qword ptr D
                fldcw kCWChop
                fistp qword ptr ti
                fldcw kCW
            }
            hd = fnv1a(hd, &D, 8);
            hi = fnv1a(hi, &ti, 8);
        }
        out[b].h32 = hd;
        out[b].h80 = hi;
        out[b].hcc = 0;
    }
    write_file(path, out, nblocks * sizeof(ChunkHash));
    printf("{\"steps\":%u,\"final_D\":%.17g,\"final_D_bits\":\"%016llx\"}\n", steps, D, *(unsigned long long*)&D);
}

int main(int argc, char** argv) {
    uint16_t cw_at_start = get_cw();
    set_cw();
    if (argc >= 2 && !strcmp(argv[1], "info")) {
        DWORD_PTR p, e;
        core_masks(&p, &e);
        printf("{\"fcw_at_start\":\"%04x\",\"pmask\":\"%08lx\",\"emask\":\"%08lx\",\"sizeof_Rec\":%u,\"sizeof_Out\":%u}\n",
               cw_at_start, (unsigned long)p, (unsigned long)e, (unsigned)sizeof(Rec), (unsigned)sizeof(Out));
        return 0;
    }
    if (argc >= 4 && !strcmp(argv[1], "records")) {
        size_t n;
        Rec* recs = (Rec*)read_file(argv[2], &n);
        n /= sizeof(Rec);
        Out* outs = (Out*)calloc(n ? n : 1, sizeof(Out));
        for (size_t i = 0; i < n; i++) hw_eval(&recs[i], &outs[i]);
        write_file(argv[3], outs, n * sizeof(Out));
        printf("{\"records\":%zu,\"fcw_at_start\":\"%04x\",\"fcw_at_end\":\"%04x\"}\n", n, cw_at_start, get_cw());
        return 0;
    }
    if (argc >= 4 && !strcmp(argv[1], "exhaustive")) {
        exhaustive(argv[2], argv[3], argc >= 5 ? argv[4] : "all");
        return 0;
    }
    if (argc >= 4 && !strcmp(argv[1], "dummy")) {
        dummy((uint32_t)strtoul(argv[2], NULL, 0), argv[3]);
        return 0;
    }
    fprintf(stderr, "usage: x87_hw32 info | records <in> <out> | exhaustive <op|all> <prefix> [P|E|all] | dummy <n> <out>\n");
    return 2;
}
