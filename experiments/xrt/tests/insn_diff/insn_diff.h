/* insn_diff.h - record layouts shared by the native (x86) and lifted (x64) harnesses of the
 * differential instruction test (experiments/xrt/tests/insn_diff, see README.md).
 *
 * Both harnesses execute the same snippet with the same input state at the same addresses:
 * a 64 KB scratch region at ID_REGION (native: VirtualAlloc at that address in the 32-bit process;
 * lifted: committed inside the runtime's 4 GB guest reservation), so register values that are
 * pointers need no relocation when the outputs are compared. */
#ifndef INSN_DIFF_H
#define INSN_DIFF_H
#include <stdint.h>
#include <string.h>

#define ID_REGION 0x20000000u
#define ID_REGION_SIZE 0x10000u
#define ID_DATA 0x20008000u          /* data window: memory operands, string-op buffers */
#define ID_DATA_SIZE 0x200u
#define ID_STACK 0x2000BF00u         /* stack window: initial ESP is near 0x2000C000 */
#define ID_STACK_SIZE 0x200u
#define ID_MAXCHG 24
/* fs: test: TEB fields a snippet may write (ExceptionList at 0, ArbitraryUserPointer at 0x14); the
 * native side saves and restores them around every snippet, both sides hash them afterwards */
#define ID_TEB_SNAP 0x34u              /* bytes of TEB snapshot handed from native to lifted */
#define ID_FLAG_FS 1u

enum { ID_OK = 0, ID_DE = 1, ID_EXC = 2, ID_TRAP = 3, ID_FATAL = 4, ID_OTHER = 5 };

#pragma pack(push, 1)
typedef struct IdPatch {
    uint32_t addr;                   /* absolute address inside one of the windows */
    uint8_t len, pad[3];
    uint8_t bytes[8];
} IdPatch;

typedef struct IdCase {
    uint32_t snip, seed;             /* snippet index; PRNG seed for the window contents */
    uint32_t r[8];                   /* eax ecx edx ebx esp ebp esi edi */
    uint32_t eflags;                 /* CF PF AF ZF SF DF OF (bit 1 set) */
    uint32_t nst;                    /* x87 stack depth: st[0] = ST(0) */
    uint16_t fcw, flags;             /* flags: ID_FLAG_FS (snippet addresses the TEB through fs:) */
    uint32_t pad;
    double st[8];
    IdPatch patch[4];                /* explicit operand values written over the PRNG fill */
} IdCase;

typedef struct IdChg {
    uint16_t off;                    /* 0..ID_DATA_SIZE-1 data window, ID_DATA_SIZE+ stack window */
    uint8_t val, pad;
} IdChg;

typedef struct IdOut {
    uint32_t status, excode;
    uint32_t r[8];
    uint32_t eflags;
    uint16_t fcw, fsw;               /* fsw includes TOP (bits 11-13) */
    uint16_t valid, exact;           /* bit i: ST(i) is not empty / is exactly a double (native) */
    uint32_t hfs;                    /* FNV-1a 32 of the writable TEB fields (id_teb_hash) */
    double st[8];
    uint64_t hdata, hstack;          /* FNV-1a of the windows after execution */
    uint16_t nchg, pad2;             /* bytes that differ from the initial window contents */
    IdChg chg[ID_MAXCHG];
} IdOut;
#pragma pack(pop)

typedef struct IdHeader {
    char magic[4];                   /* "XDIN" */
    uint32_t version, nsnip, ncase;
} IdHeader;

static uint32_t id_xorshift(uint32_t* s) {
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return *s = x;
}

/* initial window contents: PRNG fill, then the case's patches */
static void id_fill(uint8_t* data, uint8_t* stack, const IdCase* k) {
    uint32_t s = k->seed ? k->seed : 0x9E3779B9u, i, j;
    for (i = 0; i < ID_DATA_SIZE; i += 4) {
        uint32_t v = id_xorshift(&s);
        memcpy(data + i, &v, 4);
    }
    for (i = 0; i < ID_STACK_SIZE; i += 4) {
        uint32_t v = id_xorshift(&s);
        memcpy(stack + i, &v, 4);
    }
    for (j = 0; j < 4; j++) {
        const IdPatch* p = &k->patch[j];
        if (!p->len)
            continue;
        if (p->addr >= ID_DATA && p->addr + p->len <= ID_DATA + ID_DATA_SIZE)
            memcpy(data + (p->addr - ID_DATA), p->bytes, p->len);
        else if (p->addr >= ID_STACK && p->addr + p->len <= ID_STACK + ID_STACK_SIZE)
            memcpy(stack + (p->addr - ID_STACK), p->bytes, p->len);
    }
}

static uint32_t id_teb_hash(const uint8_t* teb) {
    uint32_t h = 0x811c9dc5u, i;
    for (i = 0; i < 4; i++)
        h = (h ^ teb[i]) * 0x01000193u;
    for (i = 0x14; i < 0x18; i++)
        h = (h ^ teb[i]) * 0x01000193u;
    return h;
}

static uint64_t id_fnv(const uint8_t* p, uint32_t n) {
    uint64_t h = 0xcbf29ce484222325ull;
    uint32_t i;
    for (i = 0; i < n; i++)
        h = (h ^ p[i]) * 0x100000001b3ull;
    return h;
}

/* record the windows after execution (hashes and the bytes that changed) */
static void id_windows_out(IdOut* o, const uint8_t* data, const uint8_t* stack, const uint8_t* data0,
                           const uint8_t* stack0) {
    uint32_t i;
    o->hdata = id_fnv(data, ID_DATA_SIZE);
    o->hstack = id_fnv(stack, ID_STACK_SIZE);
    o->nchg = 0;
    for (i = 0; i < ID_DATA_SIZE + ID_STACK_SIZE; i++) {
        uint8_t now = i < ID_DATA_SIZE ? data[i] : stack[i - ID_DATA_SIZE];
        uint8_t was = i < ID_DATA_SIZE ? data0[i] : stack0[i - ID_DATA_SIZE];
        if (now != was) {
            if (o->nchg < ID_MAXCHG) {
                o->chg[o->nchg].off = (uint16_t)i;
                o->chg[o->nchg].val = now;
            }
            o->nchg++;
        }
    }
}
#endif
