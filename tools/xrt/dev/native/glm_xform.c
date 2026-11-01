/* glm_xform.c - native C replacement (developer build, opt-in: dev.py build --native) for one translated GlmLib.dll
 * function, guest f_2fd7d20: the virtual thiscall  Xform* Node::GetTransform(Xform* out, bool world)  (vtable slot
 * 0x2c, ret 8). This is a reconstruction of game code (like the translated units): keep it out of redistribution.
 *
 * Node: +0x20 parent node (0 = root), +0x40 local transform Xform, 15 floats:
 *   R[0..8] rotation, row-major 3x3, row vectors (v' = v R);  T[0..2] translation (+0x64);  S[0..2] scale (+0x70).
 * world == 0: *out = local (copied as 32-bit words).
 * world != 0: acc = local; for each ancestor p (innermost first), P = p->GetTransform(tmp, false) through the guest
 *   calling interface (the ancestor may be any node class), and
 *     acc.S = acc.S * P.S,   acc.T = (acc.T * P.S) R_P + P.T,   acc.R = acc.R R_P;
 *   then *out = acc.
 *
 * Exactness against the translated function (the reference; experiments/xrt/tests/native_glm_xform):
 *   - arithmetic: the guest runs x87 with CW 0x027F (53-bit precision, round to nearest); the translator models x87
 *     registers as host doubles, so this file computes in double with the guest's operation order (the sums are not
 *     reassociated) and rounds to float exactly where the guest stores to memory. Products of two floats are exact in
 *     double, so only the sums and float stores round. NaN payloads follow the same operand order as the translation.
 *   - registers: eax = out, edx/ecx = the last two words copied (out+0x34, out+0x38), esi/ebx/ebp/edi preserved,
 *     esp as after ret 8; flags as left by the final `add esp, 0xc0` (live at the return of an address-taken function).
 *   - x87: TOP and FSW as after the last ancestor call (balanced); the register slots the guest code leaves popped
 *     hold the same stale values (visible through fsave), written as the translation writes them back.
 *   - guest stack: the ancestor call sees the guest's frame exactly (esi saved at esp0-0xc4, arguments and return
 *     address 0x2fd7e21 below it, tmp at esp0-0x3c); the function's own scratch (acc and temporaries at
 *     esp0-0xc0..esp0-0x40) is kept in host locals instead: it lies below esp after the return.
 *   - eh/faults: no EH registration (as the guest code); a guest fault or exception in an ancestor call unwinds through
 *     this host frame exactly as through the translated one (no host resources are held). c->pc names the guest
 *     instruction for diagnostics. */
#include <stdlib.h>
#include "xrt.h"

extern uint8_t xrt_hits_GlmLib[];
void f_2fd7d20_translated(CPU* c);   /* the translated function, kept for the differential test */

enum { XF_R = 0, XF_T = 9, XF_S = 12, XF_N = 15 };
#define NODE_PARENT 0x20u
#define NODE_LOCAL 0x40u

static inline double f64(float f) { return (double)f; }

/* XRT_NATIVE_VERIFY=N (dev.py run --native-verify N): every Nth call first runs the translated function on a copy of
 * the CPU state (it writes *out and calls the ancestors, whose local GetTransform is a pure copy), keeps its results,
 * restores the 15 output words (out may alias the node's own transform), then runs the native one on the real state
 * and compares registers, flags, x87 state and the 15 output words (NaN payloads may differ, as in the differential
 * test). Mismatches and a running count go to xrt.log. */
void xrt_log(const char* fmt, ...);
static void native_body(CPU* c);
static int nan32(uint32_t u) { return (u & 0x7f800000u) == 0x7f800000u && (u & 0x007fffffu); }
static int nan_or_same(uint32_t a, uint32_t b) { return a == b || (nan32(a) && nan32(b)); }
static void verify_call(CPU* c) {
    CPU t = *c;
    const uint32_t node = c->r[ECX], out = rd32(c->r[ESP] + 4u), world = rd8(c->r[ESP] + 8u);
    uint32_t words[XF_N], before[XF_N], i, bad = 0;
    static unsigned long long compared, differ;
    for (i = 0; i < XF_N; i++) before[i] = rd32(out + 4u * i);
    f_2fd7d20_translated(&t);
    for (i = 0; i < XF_N; i++) { words[i] = rd32(out + 4u * i); wr32(out + 4u * i, before[i]); }   /* out may alias an input */
    native_body(c);
    for (i = 0; i < 8; i++) if (!nan_or_same(t.r[i], c->r[i])) bad |= 1;
    if (t.cf != c->cf || t.pf != c->pf || t.zf != c->zf || t.sf != c->sf || t.of != c->of || t.df != c->df || t.rv != c->rv ||
        t.top != c->top || t.fsw != c->fsw || t.fcw != c->fcw) bad |= 2;
    for (i = 0; i < 8; i++)
        if (memcmp(&t.st[i], &c->st[i], 8) && !(t.st[i] != t.st[i] && c->st[i] != c->st[i])) bad |= 4;
    for (i = 0; i < XF_N; i++) if (!nan_or_same(words[i], rd32(out + 4u * i))) bad |= 8;
    compared++;
    if (bad && differ++ < 10)
        xrt_log("DEV native verify f_2fd7d20: MISMATCH (mask %x) node %08x out %08x world %u", bad, node, out, world);
    if (!(compared & (compared - 1)) || compared % 65536 == 0)
        xrt_log("DEV native verify f_2fd7d20: %llu calls compared, %llu differ", compared, differ);
}

void f_2fd7d20(CPU* c) {
    static int verify = -1; static unsigned calls;
    if (verify < 0) { const char* v = getenv("XRT_NATIVE_VERIFY"); verify = v && *v ? atoi(v) : 0; }
    if (verify > 0 && ++calls % (unsigned)verify == 0) { verify_call(c); return; }
    native_body(c);
}

static void native_body(CPU* c) {
    XRT_ENTER(0x2fd7d20u);
    uint8_t* const g = xrt_g;
    const uint32_t esp0 = c->r[ESP], node = c->r[ECX];
    uint32_t out, parent, i;
    float a[XF_N];
    xrt_hits_GlmLib[2037] = 1;
    c->pc = 0x2fd7d20u;
    c->r[EAX] = (c->r[EAX] & 0xFFFFFF00u) | rd8b(g, esp0 + 8u);   /* mov al, [esp+8] (overwritten below) */
    if (!(c->r[EAX] & 0xFFu)) {
        /* local: copy the 15 words */
        c->pc = 0x2fd7d31u;
        out = rd32b(g, esp0 + 4u);
        for (i = 0; i < XF_N; i++) wr32b(g, out + 4u * i, rd32b(g, node + NODE_LOCAL + 4u * i));
        c->r[EAX] = out;
        c->r[EDX] = rd32b(g, node + NODE_LOCAL + 0x34u);
        c->r[ECX] = rd32b(g, node + NODE_LOCAL + 0x38u);
    } else {
        const uint32_t esp2 = esp0 - 0xc4u, tmp = esp2 + 0x88u;
        uint32_t edx_at_call;
        c->pc = 0x2fd7d97u;
        for (i = 0; i < XF_N; i++) a[i] = rdf32b(g, node + NODE_LOCAL + 4u * i);
        edx_at_call = rd32b(g, node + NODE_LOCAL + 0x38u);
        wr32b(g, esp2, c->r[ESI]);                         /* push esi */
        parent = rd32b(g, node + NODE_PARENT);
        while (parent) {
            /* P = parent->GetTransform(tmp, false): the guest's own call sequence and register state */
            uint32_t vtbl, p;
            float pf[XF_N];
            double s0, s1, u0, u1, u2, v0, v1, v2, w0, w1, r[9], last;
            c->pc = 0x2fd7e10u;
            vtbl = rd32b(g, parent);
            c->r[ESI] = parent; c->r[ECX] = parent; c->r[EAX] = vtbl; c->r[EDX] = edx_at_call;
            c->r[ESP] = esp2;
            push32b(g, c, 0);                                   /* world = false */
            push32b(g, c, tmp);
            fl_logic(c, parent, 32);                            /* flags of `test esi, esi` reach the callee */
            c->pc = 0x2fd7e1eu;
            ICALLI(rd32b(g, vtbl + 0x2cu), 0x2fd7e21u, 0x2fd7e1eu);
            p = c->r[EAX];
            c->pc = 0x2fd7e21u;
            for (i = 0; i < XF_N; i++) pf[i] = rdf32b(g, p + 4u * i);
            /* scale; translation scaled by the ancestor's scale, then rotated (row vector) and offset */
            s0 = f64(a[12]) * f64(pf[12]);
            s1 = f64(a[13]) * f64(pf[13]);
            const float s2 = (float)(f64(a[14]) * f64(pf[14]));
            u0 = f64(a[9]) * f64(pf[12]);
            u1 = f64(a[10]) * f64(pf[13]);
            u2 = f64(a[11]) * f64(pf[14]);
            v0 = u0 * f64(pf[0]) + u2 * f64(pf[6]); v0 = v0 + u1 * f64(pf[3]);
            v1 = u2 * f64(pf[7]) + u1 * f64(pf[4]); v1 = v1 + u0 * f64(pf[1]);
            v2 = u2 * f64(pf[8]) + u1 * f64(pf[5]); v2 = v2 + u0 * f64(pf[2]);
            w0 = f64((float)v0) + f64(pf[9]);
            w1 = f64((float)v1) + f64(pf[10]);
            const float t2 = (float)(f64((float)v2) + f64(pf[11]));
            /* rotation: acc.R = acc.R R_P, each element as the guest sums it */
            r[6] = f64(a[8]) * f64(pf[6]) + f64(a[7]) * f64(pf[3]); r[6] = r[6] + f64(a[6]) * f64(pf[0]);
            r[7] = f64(a[8]) * f64(pf[7]) + f64(a[7]) * f64(pf[4]); r[7] = r[7] + f64(a[6]) * f64(pf[1]);
            r[8] = f64(a[8]) * f64(pf[8]) + f64(a[7]) * f64(pf[5]); r[8] = r[8] + f64(a[6]) * f64(pf[2]);
            r[3] = f64(a[5]) * f64(pf[6]) + f64(a[4]) * f64(pf[3]); r[3] = r[3] + f64(a[3]) * f64(pf[0]);
            r[4] = f64(a[5]) * f64(pf[7]) + f64(a[4]) * f64(pf[4]); r[4] = r[4] + f64(a[3]) * f64(pf[1]);
            r[5] = f64(a[5]) * f64(pf[8]) + f64(a[4]) * f64(pf[5]); r[5] = r[5] + f64(a[3]) * f64(pf[2]);
            r[0] = f64(a[1]) * f64(pf[3]) + f64(a[0]) * f64(pf[0]); r[0] = r[0] + f64(a[2]) * f64(pf[6]);
            r[1] = f64(a[2]) * f64(pf[7]) + f64(a[0]) * f64(pf[1]); r[1] = r[1] + f64(a[1]) * f64(pf[4]);
            r[2] = f64(a[2]) * f64(pf[8]) + f64(a[0]) * f64(pf[2]);
            last = f64(a[1]) * f64(pf[5]);                      /* stays in an x87 slot */
            r[2] = r[2] + last;
            /* x87 slots the guest leaves popped at the loop edge (depth d below TOP: st[(top - d) & 7]) */
            {
                const uint32_t t = c->top;
                c->st[(t + 7u) & 7u] = s1;   c->st[(t + 6u) & 7u] = s0;
                c->st[(t + 5u) & 7u] = w1;   c->st[(t + 4u) & 7u] = w0;
                c->st[(t + 3u) & 7u] = r[7]; c->st[(t + 2u) & 7u] = r[6];
                c->st[(t + 1u) & 7u] = r[2]; c->st[t & 7u] = last;
            }
            for (i = 0; i < 9; i++) a[i] = (float)r[i];
            a[9] = (float)w0; a[10] = (float)w1; a[11] = t2;
            a[12] = (float)s0; a[13] = (float)s1; a[14] = s2;
            edx_at_call = 0;
            memcpy(&edx_at_call, &a[8], 4);                     /* edx holds acc.R[8]'s bits at the next call */
            parent = rd32b(g, parent + NODE_PARENT);
        }
        c->r[ESI] = rd32b(g, esp2);                             /* pop esi */
        c->pc = 0x2fd801bu;
        out = rd32b(g, esp0 + 4u);
        {   /* fld [esp+4]; fstp [eax]: acc.R[0] passes through an x87 slot (depth 1) */
            const double r0 = f64(a[0]);
            wrf32s(g, out, (float)r0);
            c->st[(c->top + 7u) & 7u] = r0;
        }
        for (i = 1; i < XF_N; i++) wrf32s(g, out + 4u * i, a[i]);
        c->r[EAX] = out;
        memcpy(&c->r[EDX], &a[13], 4);
        memcpy(&c->r[ECX], &a[14], 4);
    }
    c->r[ESP] = esp0 - 0xc0u;
    {   /* add esp, 0xc0 */
        const uint32_t sp = c->r[ESP], res = sp + 0xc0u;
        fl_add(c, sp, 0xc0u, res, 32);
        c->r[ESP] = res;
    }
    RET(8u);
}
