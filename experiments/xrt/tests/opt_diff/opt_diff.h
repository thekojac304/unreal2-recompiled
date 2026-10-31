/* opt_diff.h - vectors and result records shared by the native (x86) and lifted (x64) harnesses. */
#ifndef OPT_DIFF_H
#define OPT_DIFF_H
#include <stdint.h>
#include <string.h>

/* same guest addresses on both sides, so pointer values written by the tests compare equal */
#define OD_IN 0x20010000u
#define OD_OUT 0x20020000u
#define OD_BUF 0x1000u
#define OD_STACK_LO 0x20030000u
#define OD_STACK_TOP 0x20040000u
#define OD_SENTINEL 0x0DEAD000u

typedef struct OdRec {
    uint32_t fn, vec, status;          /* 0 ok, 1 trap, 2 fatal, 3 bad return, 4 unknown indirect call, 5 fault */
    uint32_t eax, edx;                 /* return value: compared with the native run */
    uint32_t pc;                       /* lifted only: c->pc after the return (the ret instruction) */
    uint64_t h_in, h_out;              /* FNV-1a of the in/out buffers after the call: compared with native */
    /* lifted only (zero in native records): complete architectural state after the return */
    uint32_t r[8], flags, top;         /* flags: CF PF ZF SF OF DF in their EFLAGS bit positions */
    uint16_t fcw, fsw;
    uint32_t pad1;
    uint64_t st[8];
    uint64_t h_stack;
} OdRec;

typedef struct OdVec {
    uint32_t n, seed, r[8], eflags;    /* r/eflags: initial lifted CPU state (the native call cannot set them) */
} OdVec;

static uint32_t od_rng(uint64_t* s) {
    *s = *s * 6364136223846793005ull + 1442695040888963407ull;
    return (uint32_t)(*s >> 33);
}

static uint64_t od_hash(const uint8_t* p, uint32_t n) {
    uint64_t h = 1469598103934665603ull;
    uint32_t i;
    for (i = 0; i < n; i++)
        h = (h ^ p[i]) * 1099511628211ull;
    return h;
}

/* deterministic vector k of function f: buffer contents plus arguments and initial lifted state */
static void od_vector(uint32_t f, uint32_t k, uint8_t* in, uint8_t* out, OdVec* v) {
    uint64_t s = ((uint64_t)f << 32) ^ k ^ 0x9E3779B97F4A7C15ull;
    uint32_t i, mode;
    od_rng(&s);
    mode = od_rng(&s) % 5;
    for (i = 0; i < OD_BUF; i++) {
        uint32_t x = od_rng(&s);
        in[i] = mode == 0 ? (uint8_t)x : mode == 1 ? (uint8_t)(x % 17) : mode == 2 ? (uint8_t)(x & 0x81)
              : mode == 3 ? (uint8_t)(i * 7 + k) : (uint8_t)((x & 1) ? 0xFF : 0);
        out[i] = (uint8_t)(od_rng(&s) >> 7);
    }
    v->n = k < 64 ? k : od_rng(&s) % 1100;
    v->seed = (k & 3) == 0 ? 0 : (k & 3) == 1 ? 0x80000000u : od_rng(&s);
    for (i = 0; i < 8; i++)
        v->r[i] = od_rng(&s);
    v->eflags = od_rng(&s) & 0x8C5u;   /* CF PF ZF SF OF at entry: random, a buggy translation might read them */
}
#endif
