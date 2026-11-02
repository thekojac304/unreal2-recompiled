/* native_glm_xform - differential test of the native C GlmLib transform query (tools/xrt/dev/native/glm_xform.c,
 * guest f_2fd7d20) against the translated function (extracted from out/dev-init/generated/GlmLib_008.c by extract.py).
 *
 * Each case builds one guest scenario (node chain, vtables, out buffer, caller stack, random CPU state) in two identical
 * guest arenas, runs the translated function on one and the native one on the other, and compares the whole
 * guest-visible contract:
 *   - CPU: eax..edi, esp, cf/pf/zf/sf/of/df, eflags_rest, fs_base, rv, all 8 x87 registers bit for bit (including the
 *     stale popped slots), TOP, FCW, FSW, the XRT_ENTER history; c->pc (diagnostics) is not compared
 *   - guest memory: every byte of the arena except the function's own scratch [esp0-0xc0, esp0-0x3c) (acc and
 *     temporaries, below esp after the return; the native version keeps them in host locals)
 *   - the number and order of ancestor calls (a counter in guest memory)
 * Ancestors are either the function under test itself (same variant, world=false) or a synthetic node class whose
 * GetTransform returns a different buffer and disturbs registers, flags, FSW and an x87 slot like real callee code.
 * Inputs: realistic node chains (rotations from unit quaternions, scales 0.05-20, translations +-5000, depth 0-6),
 * the same with IEEE specials mixed in (+-0, denormals, FLT_MIN/MAX, +-inf, quiet/signalling NaNs with payloads,
 * products that overflow or underflow float), and uniformly random bit patterns; under MXCSR default and FTZ|DAZ.
 * Exit 0 when no case differs. Build/run: experiments/xrt/tests/native_glm_xform/run.cmd */
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <xmmintrin.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "xrt.h"

void f_2fd7d20(CPU* c);
void f_2fd7d20_translated(CPU* c);

/* ---- owned stubs for what the two functions reach in the runtime */
uint8_t* xrt_g;
volatile long xrt_preempt_req;
void xrt_preempt(CPU* c) { (void)c; }
XrtCallCache xrt_call_cache[65536];
uint32_t xrt_call_cache_gen = 1;   /* never matches a zeroed entry: every ICALLI takes xrt_icall */
void xrt_icall_after(CPU* c) { (void)c; }
void xrt_world_return(CPU* c) { (void)c; }
uint8_t xrt_hits_GlmLib[8192];
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected) {
    printf("FAIL bad return at site %08x: %08x, expected %08x\n", site, c->rv, expected); exit(2);
}
uint32_t xrt_h2g(const void* p) { return (uint32_t)((const uint8_t*)p - xrt_g); }
static unsigned verify_mismatches; static char verify_last[256];
void xrt_log(const char* fmt, ...) {
    va_list a; va_start(a, fmt); vsnprintf(verify_last, sizeof verify_last, fmt, a); va_end(a);
    if (strstr(verify_last, "MISMATCH")) { verify_mismatches++; printf("  %s\n", verify_last); }
}

#define ARENA (16u << 20)
#define VT_SELF 0x00010000u        /* vtable whose slot 0x2c is f_2fd7d20 */
#define VT_OTHER 0x00010100u       /* vtable whose slot 0x2c is the synthetic class */
#define T_SELF 0x02fd7d20u
#define T_OTHER 0x02f00010u
#define NODES 0x00100000u
#define NODE_SIZE 0x100u
#define OUTBUF 0x00200000u
#define CALLS 0x00300000u          /* ancestor call log: count, then the node of each call */
#define ESP0 0x00effe00u

static int variant;                /* 0 translated, 1 native: ancestors of class SELF run the same variant */

/* Synthetic ancestor class: GetTransform(out, world) ignores world, returns node+0x90 (its own cache), and leaves
 * registers, flags, FSW and an x87 slot changed the way compiled callee code may. */
static void synthetic_get_transform(CPU* c) {
    uint32_t node = c->r[ECX], n;
    n = rd32(CALLS); wr32(CALLS + 4 + 4 * (n & 255), node); wr32(CALLS, n + 1);
    c->r[EAX] = node + 0x90u; c->r[ECX] = 0xdeadbeefu; c->r[EDX] = n * 0x9e3779b9u;
    fl_sub(c, n, 7, n - 7, 32);
    c->fsw = (uint16_t)(c->fsw ^ 0x0200);              /* C1 */
    c->st[(c->top + 7u) & 7u] = 1234.5 + n;            /* a push/pop pair */
    RET(8u);
}
void xrt_icall(CPU* c, uint32_t target, uint32_t site) {
    (void)site;
    if (target == T_SELF) {
        uint32_t n = rd32(CALLS);
        wr32(CALLS + 4 + 4 * (n & 255), c->r[ECX]); wr32(CALLS, n + 1);
        (variant ? f_2fd7d20 : f_2fd7d20_translated)(c);
    } else if (target == T_OTHER) synthetic_get_transform(c);
    else { printf("FAIL unexpected call target %08x\n", target); exit(2); }
}

/* ---- inputs */
static uint64_t rng = 0x243f6a8885a308d3ull;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (uint32_t)(rng >> 16); }
static float frnd(float lo, float hi) { return lo + (hi - lo) * (float)(rnd() & 0xffffff) / 16777216.0f; }
static const uint32_t specials[] = {
    0x00000000, 0x80000000, 0x3f800000, 0xbf800000, 0x00800000, 0x00000001, 0x007fffff, 0x807fffff, 0x7f7fffff,
    0xff7fffff, 0x7f800000, 0xff800000, 0x7fc00000, 0x7fc12345, 0xffc00001, 0x7f800001, 0x7fa00000, 0xffb00003,
    0x1e3ce508 /* 1e-20 */, 0x60ad78ec /* 1e20 */, 0x7effffff, 0x0c000000, 0x72000000};
static uint32_t fbits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static void put_xform(uint32_t a, int kind) {
    uint32_t w[15]; int i;
    if (kind == 2) { for (i = 0; i < 15; i++) w[i] = rnd(); }
    else {
        /* rotation from a random unit quaternion, scale, translation */
        float x = frnd(-1, 1), y = frnd(-1, 1), z = frnd(-1, 1), s = frnd(-1, 1), n = sqrtf(x * x + y * y + z * z + s * s);
        float q[4], r[9], sc = frnd(0.05f, 20.0f);
        if (n < 1e-3f) { x = 0; y = 0; z = 0; s = 1; n = 1; }
        q[0] = x / n; q[1] = y / n; q[2] = z / n; q[3] = s / n;
        r[0] = 1 - 2 * (q[1] * q[1] + q[2] * q[2]); r[1] = 2 * (q[0] * q[1] + q[2] * q[3]); r[2] = 2 * (q[0] * q[2] - q[1] * q[3]);
        r[3] = 2 * (q[0] * q[1] - q[2] * q[3]); r[4] = 1 - 2 * (q[0] * q[0] + q[2] * q[2]); r[5] = 2 * (q[1] * q[2] + q[0] * q[3]);
        r[6] = 2 * (q[0] * q[2] + q[1] * q[3]); r[7] = 2 * (q[1] * q[2] - q[0] * q[3]); r[8] = 1 - 2 * (q[0] * q[0] + q[1] * q[1]);
        for (i = 0; i < 9; i++) w[i] = fbits(r[i]);
        for (i = 9; i < 12; i++) w[i] = fbits(frnd(-5000, 5000));
        for (i = 12; i < 15; i++) w[i] = fbits(rnd() & 1 ? sc : frnd(0.05f, 20.0f));
        if (kind == 1) for (i = 0; i < 15; i++) if (rnd() % 4 == 0) w[i] = specials[rnd() % (sizeof specials / 4)];
    }
    for (i = 0; i < 15; i++) wr32(a + 4 * i, w[i]);
}

static uint8_t *arena_a, *arena_b;
static unsigned cases, differ, nan_payload, calls_total;
static unsigned by_kind[3], world_cases, synthetic_cases, depth_max, exact_by_kind[3];

/* NaN payloads: when two NaNs (or an invalid-operation default NaN and an input NaN) meet in one add/multiply, SSE
 * returns the first operand's, and which operand is first is MSVC's register-allocation choice in each build of the
 * translated unit (real x87 picks the larger significand, so the translation already differs from the guest CPU
 * there). A difference where both sides are NaN is counted as a NaN-payload difference; any other difference -
 * including NaN against a number - is a failure. */
static int nan32(uint32_t u) { return (u & 0x7f800000u) == 0x7f800000u && (u & 0x007fffffu); }
static int compare(const CPU* a, const CPU* b, uint32_t esp0, const char* what, int* payload) {
    int bad = 0, i;
#define F(field) if (a->field != b->field) { if (differ < 12) printf("  %s: " #field " %08llx vs %08llx\n", what, \
        (unsigned long long)a->field, (unsigned long long)b->field); bad = 1; }
    for (i = 0; i < 8; i++)
        if (a->r[i] != b->r[i] && (i == EAX || i == ESP || !nan32(a->r[i]) || !nan32(b->r[i]))) F(r[i])
        else if (a->r[i] != b->r[i]) *payload = 1;
    F(cf); F(pf); F(zf); F(sf); F(of); F(df); F(eflags_rest); F(fs_base); F(rv); F(top); F(fcw); F(fsw); F(hpos);
    for (i = 0; i < XRT_HIST; i++) F(hist[i]);
#undef F
    for (i = 0; i < 8; i++)
        if (memcmp(&a->st[i], &b->st[i], 8)) {
            if (isnan(a->st[i]) && isnan(b->st[i])) { *payload = 1; continue; }
            if (differ < 12) printf("  %s: st[%d] %.17g vs %.17g\n", what, i, a->st[i], b->st[i]);
            bad = 1;
        }
    {
        uint32_t lo = esp0 - 0xc0u, hi = esp0 - 0x3cu, at, x, y;
        for (at = 0; at < ARENA; at += 4)
            if ((at < lo || at >= hi) && memcmp(arena_a + at, arena_b + at, 4)) {
                memcpy(&x, arena_a + at, 4); memcpy(&y, arena_b + at, 4);
                if (nan32(x) && nan32(y)) { *payload = 1; continue; }
                if (differ < 12) printf("  %s: guest word %08x %08x vs %08x\n", what, at, x, y);
                bad = 1;
                break;
            }
    }
    return bad;
}

static void one_case(int kind, unsigned mxcsr) {
    CPU init, ca, cb;
    uint32_t esp0 = ESP0 - 16 * (rnd() & 63), node0, out, depth, k, world;
    int synthetic = 0;
    memset(arena_a, 0, 0x00400000u);
    memset(arena_a + 0x00e00000u, 0, ARENA - 0x00e00000u);
    xrt_g = arena_a;
    wr32(VT_SELF + 0x2c, T_SELF); wr32(VT_OTHER + 0x2c, T_OTHER);
    depth = rnd() % 7;
    world = rnd() % 5 != 0;
    if (depth > depth_max) depth_max = depth;
    for (k = 0; k <= depth; k++) {
        uint32_t node = NODES + k * NODE_SIZE;
        int other = k > 0 && rnd() % 6 == 0;
        synthetic |= other;
        wr32(node, other ? VT_OTHER : VT_SELF);
        wr32(node + 0x20, k < depth ? node + NODE_SIZE : 0);
        put_xform(node + 0x40, kind);
        put_xform(node + 0x90, kind);                    /* the synthetic class's cached transform */
    }
    node0 = NODES;
    out = rnd() % 8 == 0 ? node0 + 0x40 : OUTBUF + 4 * (rnd() & 15);   /* sometimes out aliases the local */
    memset(&init, 0, sizeof init);
    for (k = 0; k < 8; k++) init.r[k] = rnd();
    init.r[ECX] = node0; init.r[ESP] = esp0;
    init.cf = rnd() & 1; init.pf = rnd() & 1; init.zf = rnd() & 1; init.sf = rnd() & 1; init.of = rnd() & 1;
    init.df = 0; init.eflags_rest = rnd() & 0x00000202u; init.fs_base = 0x7ffde000u; init.rv = rnd();
    init.top = rnd() & 7; init.fcw = 0x027f; init.fsw = (uint16_t)((rnd() & 0x47ff & ~0x3800) | (init.top << 11));
    for (k = 0; k < 8; k++) { uint64_t u = ((uint64_t)rnd() << 32) | rnd(); memcpy(&init.st[k], &u, 8); }
    wr32(esp0, 0x0abc1234u);                                         /* caller's return address */
    wr32(esp0 + 4, out);
    wr32(esp0 + 8, (rnd() & 0xffffff00u) | (world ? 1u + (rnd() % 255) : 0u));
    for (k = 0; k < 64; k++) wr32(esp0 - 0x400 + 16 * k, rnd());    /* stale stack below */
    memcpy(arena_b, arena_a, ARENA);
    _mm_setcsr(mxcsr);
    variant = 0; xrt_g = arena_a; ca = init; f_2fd7d20_translated(&ca);
    variant = 1; xrt_g = arena_b; cb = init; f_2fd7d20(&cb);
    _mm_setcsr(0x1f80);
    cases++; by_kind[kind]++; world_cases += world; synthetic_cases += synthetic && world;
    calls_total += *(uint32_t*)(arena_a + CALLS);
    {
        int payload = 0;
        if (compare(&ca, &cb, esp0, kind == 0 ? "realistic" : kind == 1 ? "specials" : "random-bits", &payload)) {
            if (differ < 12) printf("  (case %u: depth %u, world %u, synthetic %d, mxcsr %04x)\n", cases, depth, world, synthetic, mxcsr);
            differ++;
        } else if (payload) nan_payload++;
        else exact_by_kind[kind]++;
    }
}

/* `bench`: host time per call of each variant on one realistic world-path chain of the given depth (the ancestor calls
 * go through this file's xrt_icall stub in both variants, so the comparison is of the two function bodies). */
static double bench(int v, unsigned depth) {
    LARGE_INTEGER f, t0, t1; CPU c0, c; unsigned k, reps = 2000000;
    xrt_g = v ? arena_b : arena_a; variant = v;
    memset(&c0, 0, sizeof c0);
    c0.r[ECX] = NODES; c0.r[ESP] = ESP0; c0.fcw = 0x027f;
    QueryPerformanceFrequency(&f); QueryPerformanceCounter(&t0);
    for (k = 0; k < reps; k++) { c = c0; (v ? f_2fd7d20 : f_2fd7d20_translated)(&c); }
    QueryPerformanceCounter(&t1);
    (void)depth;
    return (double)(t1.QuadPart - t0.QuadPart) * 1e9 / (double)f.QuadPart / reps;
}

int main(int argc, char** argv) {
    unsigned n = argc > 1 ? (unsigned)atoi(argv[1]) : 20000, i, m;
    static const unsigned mxcsrs[] = {0x1f80, 0x9fc0};
    arena_a = calloc(1, ARENA); arena_b = calloc(1, ARENA);
    if (argc > 1 && !strcmp(argv[1], "verify")) {
        /* the in-game XRT_NATIVE_VERIFY path (every call compared) on the same scenarios: no mismatch expected */
        _putenv_s("XRT_NATIVE_VERIFY", "1");
        for (i = 0; i < 3000; i++) one_case(i % 2, 0x1f80);   /* realistic and specials */
        printf("verify mode: %u cases, last log '%s', %u mismatches reported\n", cases, verify_last, verify_mismatches);
        printf(verify_mismatches || !strstr(verify_last, "calls compared") ? "FAIL\n" : "PASS\n");
        return verify_mismatches != 0;
    }
    if (argc > 1 && !strcmp(argv[1], "bench")) {
        unsigned depth;
        for (depth = 0; depth <= 4; depth++) {
            uint32_t k;
            xrt_g = arena_a; memset(arena_a, 0, ARENA);
            wr32(VT_SELF + 0x2c, T_SELF);
            for (k = 0; k <= depth; k++) {
                uint32_t node = NODES + k * NODE_SIZE;
                wr32(node, VT_SELF); wr32(node + 0x20, k < depth ? node + NODE_SIZE : 0); put_xform(node + 0x40, 0);
            }
            wr32(ESP0, 0x0abc1234u); wr32(ESP0 + 4, OUTBUF); wr32(ESP0 + 8, 1);
            memcpy(arena_b, arena_a, ARENA);
            printf("depth %u: translated %.1f ns/call, native %.1f ns/call\n", depth, bench(0, depth), bench(1, depth));
        }
        return 0;
    }
    for (m = 0; m < 2; m++)
        for (i = 0; i < n; i++) one_case(i % 3, mxcsrs[m]);
    printf("%u cases (realistic %u, specials %u, random bits %u; world path %u, with a synthetic ancestor %u; depth 0-%u; "
           "%u ancestor calls), MXCSR 1f80 and 9fc0\n", cases, by_kind[0], by_kind[1], by_kind[2], world_cases,
           synthetic_cases, depth_max, calls_total);
    printf("bit-identical: realistic %u/%u, specials %u/%u, random bits %u/%u; NaN-payload-only differences %u; "
           "other differences %u\n", exact_by_kind[0], by_kind[0], exact_by_kind[1], by_kind[1], exact_by_kind[2], by_kind[2],
           nan_payload, differ);
    /* NaN-free inputs must be bit-identical; elsewhere only NaN payloads may differ */
    printf(differ || exact_by_kind[0] != by_kind[0] ? "FAIL\n" : "PASS\n");
    return differ || exact_by_kind[0] != by_kind[0];
}
