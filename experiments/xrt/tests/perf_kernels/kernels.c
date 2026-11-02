/* kernels.c - owned performance kernels shaped like Unreal II hot paths (see README.md).
 *
 * Built as a 32-bit DLL with the x87 code generator (cl /O2 /arch:IA32, no CRT: no memcpy/_ftol/sqrt calls, so every
 * helper is written out or is an x87 instruction in __asm), lifted by tools/xrt/xlift.py and run natively and
 * translated from the same input bytes. Every export has the signature
 *   uint64_t __cdecl k_name(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed)
 * and returns a checksum that must be identical natively and translated: only +,-,*,/, fsqrt, compares and
 * conversions are used (no transcendental x87 instructions, whose hardware results are not bit-exact in the model).
 *   k_bones    64-bone skeleton: parent-chain quaternion/translation composition through a per-kind function table
 *              (the GlmLib Node::GetTransform shape: x87 arithmetic, memory operands, one indirect call per bone)
 *   k_verts    1024 vertices transformed by a per-iteration matrix, normals renormalised (fsqrt), clamped lighting
 *              term, bounding box (fcom/fnstsw compare chains, float stores)
 *   k_actors   256 polymorphic actors (vtable with tick/touch): integration, box bounce, state machine (jump table),
 *              grid hashing and pairwise touch calls (indirect calls, flags, integer work)
 *   k_strings  FName-style case-insensitive hashing, hash-table probing with string compares, byte copies (integer
 *              and flag heavy, byte loads/stores, compare loops)
 *   k_bsp      2047-node BSP tree traversal of 512 points (pointer chasing, signed-distance compares) */
#include <stdint.h>

#define EXPORT __declspec(dllexport)
#define NOINLINE __declspec(noinline)

int _fltused;                          /* no CRT: the compiler's floating-point marker symbol */

static uint32_t rd32(const uint8_t* p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static float frand(uint32_t* s) {       /* -1 .. 1 */
    *s = *s * 1664525u + 1013904223u;
    return (float)(int32_t)(*s >> 9 & 0xFFFFFFu) * (1.0f / 8388608.0f) - 1.0f;
}
static int32_t ftoi(float f) { int32_t r; __asm { fld f } __asm { fistp r } return r; }
static float fsqrt_(float x) { float r; __asm { fld x } __asm { fsqrt } __asm { fstp r } return r; }
static uint32_t fbits(float f) { union { float f; uint32_t u; } u; u.f = f; return u.u; }
static uint32_t bsum(const uint8_t* p, uint32_t n) { uint32_t s = 0, i; for (i = 0; i < n; i++) s = s * 3 + p[i]; return s; }

/* ---------------------------------------------------------------- k_bones */
typedef struct Xf { float t[3], q[4], s; } Xf;                        /* 32 bytes */
typedef struct Bone { float t[3], q[4], s; int parent, kind; } Bone;  /* 40 bytes */
typedef void (*ComposeFn)(Xf* w, const Xf* p, const Bone* b);

static void qmul(float* r, const float* a, const float* b) {
    r[0] = a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1];
    r[1] = a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0];
    r[2] = a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3];
    r[3] = a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2];
}
static void qrot(float* r, const float* q, const float* v) {          /* v' = v + 2 q.w (q.xyz x v) + 2 q.xyz x (q.xyz x v) */
    float c1[3], c2[3];
    c1[0] = q[1] * v[2] - q[2] * v[1]; c1[1] = q[2] * v[0] - q[0] * v[2]; c1[2] = q[0] * v[1] - q[1] * v[0];
    c2[0] = q[1] * c1[2] - q[2] * c1[1]; c2[1] = q[2] * c1[0] - q[0] * c1[2]; c2[2] = q[0] * c1[1] - q[1] * c1[0];
    r[0] = v[0] + 2.0f * (q[3] * c1[0] + c2[0]);
    r[1] = v[1] + 2.0f * (q[3] * c1[1] + c2[1]);
    r[2] = v[2] + 2.0f * (q[3] * c1[2] + c2[2]);
}
static NOINLINE void compose_plain(Xf* w, const Xf* p, const Bone* b) {
    float tv[3];
    qrot(tv, p->q, b->t);
    w->t[0] = p->t[0] + p->s * tv[0]; w->t[1] = p->t[1] + p->s * tv[1]; w->t[2] = p->t[2] + p->s * tv[2];
    qmul(w->q, p->q, b->q);
    w->s = p->s * b->s;
}
static NOINLINE void compose_mirror(Xf* w, const Xf* p, const Bone* b) {
    float tv[3], bt[3];
    bt[0] = -b->t[0]; bt[1] = b->t[1]; bt[2] = b->t[2];
    qrot(tv, p->q, bt);
    w->t[0] = p->t[0] + p->s * tv[0]; w->t[1] = p->t[1] + p->s * tv[1]; w->t[2] = p->t[2] + p->s * tv[2];
    qmul(w->q, p->q, b->q);
    w->q[0] = -w->q[0];
    w->s = p->s * b->s;
}
static NOINLINE void compose_scaled(Xf* w, const Xf* p, const Bone* b) {
    float tv[3], inv, q[4];
    qrot(tv, p->q, b->t);
    w->t[0] = p->t[0] + p->s * b->s * tv[0]; w->t[1] = p->t[1] + p->s * b->s * tv[1]; w->t[2] = p->t[2] + p->s * b->s * tv[2];
    qmul(q, p->q, b->q);
    inv = 1.0f / fsqrt_(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    w->q[0] = q[0] * inv; w->q[1] = q[1] * inv; w->q[2] = q[2] * inv; w->q[3] = q[3] * inv;
    w->s = p->s * b->s * b->s;
}
static const ComposeFn compose_by_kind[3] = { compose_plain, compose_mirror, compose_scaled };

EXPORT uint64_t __cdecl k_bones(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    Bone* bones = (Bone*)out;                     /* 64 * 40 = 2560 bytes */
    Xf* world = (Xf*)(out + 4096);                /* 64 * 32 */
    uint32_t s = seed ^ 0x1234567u, i, it, acc = 0;
    for (i = 0; i < 64; i++) {
        Bone* b = &bones[i];
        float inv;
        b->t[0] = frand(&s) * 10.0f; b->t[1] = frand(&s) * 10.0f; b->t[2] = frand(&s) * 10.0f;
        b->q[0] = frand(&s); b->q[1] = frand(&s); b->q[2] = frand(&s); b->q[3] = frand(&s) + 2.0f;
        inv = 1.0f / fsqrt_(b->q[0] * b->q[0] + b->q[1] * b->q[1] + b->q[2] * b->q[2] + b->q[3] * b->q[3]);
        b->q[0] *= inv; b->q[1] *= inv; b->q[2] *= inv; b->q[3] *= inv;
        b->s = 1.0f + frand(&s) * 0.05f;
        b->parent = i == 0 ? -1 : (int)(i - 1 - rd32(in + 4 * i) % (i < 4 ? i : 4));
        b->kind = (int)(rd32(in + 256 + 4 * i) % 3u);
    }
    for (it = 0; it < n; it++) {
        bones[0].t[0] = frand(&s);                /* the root moves a little each frame */
        for (i = 0; i < 64; i++) {
            const Bone* b = &bones[i];
            Xf* w = &world[i];
            if (b->parent < 0) {
                w->t[0] = b->t[0]; w->t[1] = b->t[1]; w->t[2] = b->t[2];
                w->q[0] = b->q[0]; w->q[1] = b->q[1]; w->q[2] = b->q[2]; w->q[3] = b->q[3];
                w->s = b->s;
            } else {
                compose_by_kind[b->kind](w, &world[b->parent], b);
            }
        }
        acc += fbits(world[63].t[0]) ^ fbits(world[31].q[2]) ^ it;
    }
    return ((uint64_t)acc << 32) | fbits(world[63].t[1] + world[62].s);
}

/* ---------------------------------------------------------------- k_verts */
typedef struct Vtx { float p[3], nrm[3]; } Vtx;                        /* 24 bytes */

EXPORT uint64_t __cdecl k_verts(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    Vtx* v = (Vtx*)out;                           /* 1024 * 24 = 24 KB */
    float* tp = (float*)(out + 32768);            /* transformed positions, 1024 * 12 */
    float light[3] = { 0.3f, 0.5f, 0.8f }, m[12];
    uint32_t s = seed ^ 0xC0FFEEu, i, it, acc = 0;
    float inv = 1.0f / fsqrt_(light[0] * light[0] + light[1] * light[1] + light[2] * light[2]);
    light[0] *= inv; light[1] *= inv; light[2] *= inv;
    for (i = 0; i < 1024; i++) {
        float ni;
        v[i].p[0] = frand(&s) * 100.0f; v[i].p[1] = frand(&s) * 100.0f; v[i].p[2] = frand(&s) * 50.0f;
        v[i].nrm[0] = frand(&s); v[i].nrm[1] = frand(&s); v[i].nrm[2] = frand(&s) + 1.5f;
        ni = 1.0f / fsqrt_(v[i].nrm[0] * v[i].nrm[0] + v[i].nrm[1] * v[i].nrm[1] + v[i].nrm[2] * v[i].nrm[2]);
        v[i].nrm[0] *= ni; v[i].nrm[1] *= ni; v[i].nrm[2] *= ni;
    }
    (void)in;
    for (it = 0; it < n; it++) {
        /* rotation about a unit axis by the angle whose half-tangent is a (rational: no trig), plus a translation */
        float a = 0.05f + (float)(int32_t)(it & 63) * 0.01f, d = 1.0f / (1.0f + a * a), c = (1.0f - a * a) * d, sn = 2.0f * a * d;
        float ax = 0.6f, ay = 0.0f, az = 0.8f, t = 1.0f - c;
        float mins[3] = { 1e30f, 1e30f, 1e30f }, maxs[3] = { -1e30f, -1e30f, -1e30f }, bright = 0.0f;
        m[0] = c + ax * ax * t; m[1] = ax * ay * t - az * sn; m[2] = ax * az * t + ay * sn;
        m[3] = ay * ax * t + az * sn; m[4] = c + ay * ay * t; m[5] = ay * az * t - ax * sn;
        m[6] = az * ax * t - ay * sn; m[7] = az * ay * t + ax * sn; m[8] = c + az * az * t;
        m[9] = (float)(int32_t)it * 0.5f; m[10] = 3.0f; m[11] = -(float)(int32_t)(it & 15);
        for (i = 0; i < 1024; i++) {
            const float* p = v[i].p;
            const float* nr = v[i].nrm;
            float* o = tp + 3 * i;
            float nx, ny, nz, nl, dl;
            int ki;
            o[0] = m[0] * p[0] + m[1] * p[1] + m[2] * p[2] + m[9];
            o[1] = m[3] * p[0] + m[4] * p[1] + m[5] * p[2] + m[10];
            o[2] = m[6] * p[0] + m[7] * p[1] + m[8] * p[2] + m[11];
            nx = m[0] * nr[0] + m[1] * nr[1] + m[2] * nr[2];
            ny = m[3] * nr[0] + m[4] * nr[1] + m[5] * nr[2];
            nz = m[6] * nr[0] + m[7] * nr[1] + m[8] * nr[2];
            nl = 1.0f / fsqrt_(nx * nx + ny * ny + nz * nz + 1e-12f);
            dl = (nx * light[0] + ny * light[1] + nz * light[2]) * nl;
            if (dl < 0.0f) dl = 0.0f;
            if (dl > 1.0f) dl = 1.0f;
            bright += dl;
            for (ki = 0; ki < 3; ki++) {
                if (o[ki] < mins[ki]) mins[ki] = o[ki];
                if (o[ki] > maxs[ki]) maxs[ki] = o[ki];
            }
        }
        acc += (uint32_t)ftoi(bright) ^ fbits(maxs[0] - mins[0]) ^ fbits(maxs[2] + mins[1]);
    }
    return ((uint64_t)acc << 32) | fbits(tp[3 * 777 + 1]);
}

/* ---------------------------------------------------------------- k_actors */
typedef struct Actor Actor;
typedef struct ActorVt { void (*tick)(Actor*, float); int (*touch)(Actor*, Actor*); } ActorVt;
struct Actor { const ActorVt* vt; float pos[3], vel[3]; int state, hits, kind, cell, life, pad; };   /* 48 bytes */

static NOINLINE void bounce(Actor* a, float lim) {
    int k;
    for (k = 0; k < 3; k++) {
        if (a->pos[k] > lim) { a->pos[k] = lim; a->vel[k] = -a->vel[k] * 0.8f; a->hits++; }
        else if (a->pos[k] < -lim) { a->pos[k] = -lim; a->vel[k] = -a->vel[k] * 0.8f; a->hits++; }
    }
}
static NOINLINE void tick_pawn(Actor* a, float dt) {
    a->vel[2] -= 9.8f * dt;
    a->pos[0] += a->vel[0] * dt; a->pos[1] += a->vel[1] * dt; a->pos[2] += a->vel[2] * dt;
    bounce(a, 100.0f);
    switch (a->state) {                           /* dense switch: a jump table */
    case 0: if (a->vel[2] < -5.0f) a->state = 1; break;
    case 1: if (a->pos[2] <= -99.0f) a->state = 2; break;
    case 2: a->vel[0] *= 0.99f; a->vel[1] *= 0.99f; a->state = a->hits & 1 ? 3 : 4; break;
    case 3: a->vel[0] += 1.0f * dt; a->state = 5; break;
    case 4: a->vel[1] += 1.0f * dt; a->state = 5; break;
    case 5: if (a->hits > 100) { a->hits = 0; a->state = 0; } else a->state = (a->life++ & 7) ? 5 : 0; break;
    default: a->state = 0; break;
    }
}
static NOINLINE void tick_proj(Actor* a, float dt) {
    a->pos[0] += a->vel[0] * dt * 4.0f; a->pos[1] += a->vel[1] * dt * 4.0f; a->pos[2] += a->vel[2] * dt * 4.0f;
    if (--a->life <= 0 || a->pos[0] > 100.0f || a->pos[0] < -100.0f || a->pos[1] > 100.0f || a->pos[1] < -100.0f ||
        a->pos[2] > 100.0f || a->pos[2] < -100.0f) {
        a->pos[0] = a->pos[1] = a->pos[2] = 0.0f;
        a->life = 50 + (a->hits & 63);
        a->hits++;
    }
}
static NOINLINE void tick_deco(Actor* a, float dt) {
    a->pos[1] += a->vel[1] * dt;
    if (a->pos[1] > 2.0f || a->pos[1] < -2.0f) a->vel[1] = -a->vel[1];
    a->state = (a->state + 1) & 15;
}
static NOINLINE int touch_pawn(Actor* a, Actor* b) {
    float dx = a->pos[0] - b->pos[0], dy = a->pos[1] - b->pos[1], dz = a->pos[2] - b->pos[2];
    if (dx * dx + dy * dy + dz * dz < 25.0f) { a->vel[0] -= dx * 0.1f; b->vel[0] += dx * 0.1f; return 1; }
    return 0;
}
static NOINLINE int touch_proj(Actor* a, Actor* b) {
    float dx = a->pos[0] - b->pos[0], dy = a->pos[1] - b->pos[1];
    if (dx * dx + dy * dy < 4.0f && b->kind == 0) { b->hits += 10; a->life = 0; return 1; }
    return 0;
}
static NOINLINE int touch_none(Actor* a, Actor* b) { (void)a; (void)b; return 0; }
static const ActorVt vt_pawn = { tick_pawn, touch_pawn }, vt_proj = { tick_proj, touch_proj }, vt_deco = { tick_deco, touch_none };

EXPORT uint64_t __cdecl k_actors(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    Actor* act = (Actor*)out;                     /* 256 * 48 = 12 KB */
    int* grid = (int*)(out + 16384);              /* 256 cells: last actor index seen */
    uint32_t s = seed ^ 0xACC0u, i, it, acc = 0, touches = 0;
    const float dt = 1.0f / 60.0f;
    for (i = 0; i < 256; i++) {
        Actor* a = &act[i];
        a->kind = (int)(rd32(in + 4 * i) % 3u);
        a->vt = a->kind == 0 ? &vt_pawn : a->kind == 1 ? &vt_proj : &vt_deco;
        a->pos[0] = frand(&s) * 90.0f; a->pos[1] = frand(&s) * 90.0f; a->pos[2] = frand(&s) * 90.0f;
        a->vel[0] = frand(&s) * 20.0f; a->vel[1] = frand(&s) * 20.0f; a->vel[2] = frand(&s) * 20.0f;
        a->state = 0; a->hits = 0; a->cell = 0; a->life = 20 + (int)(i & 31); a->pad = 0;
    }
    for (it = 0; it < n; it++) {
        for (i = 0; i < 256; i++) grid[i] = -1;
        for (i = 0; i < 256; i++) {
            Actor* a = &act[i];
            int cell, prev;
            a->vt->tick(a, dt);
            cell = ((ftoi(a->pos[0]) >> 3) * 73 + (ftoi(a->pos[1]) >> 3) * 31 + (ftoi(a->pos[2]) >> 3)) & 255;
            a->cell = cell;
            prev = grid[cell];
            if (prev >= 0)
                touches += (uint32_t)a->vt->touch(a, &act[prev]);
            grid[cell] = (int)i;
        }
        acc += touches ^ (uint32_t)act[it & 255].state ^ (uint32_t)act[(it * 7) & 255].hits;
    }
    return ((uint64_t)acc << 32) | (fbits(act[17].pos[0]) ^ fbits(act[200].vel[2]));
}

/* ---------------------------------------------------------------- k_strings */
EXPORT uint64_t __cdecl k_strings(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint8_t* strs = out;                          /* 256 strings in 32-byte slots */
    uint32_t* table = (uint32_t*)(out + 8192);    /* 512 slots: string index + 1, 0 empty */
    uint8_t* copies = out + 16384;                /* byte copies */
    uint8_t upper[256];
    uint32_t i, it, acc = 0, found = 0, tall = 0;
    for (i = 0; i < 256; i++)
        upper[i] = (uint8_t)(i >= 'a' && i <= 'z' ? i - 32 : i);
    for (i = 0; i < 256; i++) {
        uint32_t len = 8 + rd32(in + 4 * i) % 24, k;
        for (k = 0; k < len; k++) {
            uint32_t c = in[1024 + 32 * i + k] % 62u;
            strs[32 * i + k] = (uint8_t)(c < 26 ? 'A' + c : c < 52 ? 'a' + c - 26 : '0' + c - 52);
        }
        strs[32 * i + len] = 0;
        if ((i & 7) == 7) {                       /* some duplicates differing only in case */
            for (k = 0; k <= len; k++) strs[32 * i + k] = (uint8_t)(strs[32 * (i - 1) + k] ^ ((k & 1) && strs[32 * (i - 1) + k] ? 0x20 : 0));
        }
    }
    for (i = 0; i < 512; i++) table[i] = 0;
    (void)seed;
    for (it = 0; it < n; it++) {
        for (i = 0; i < 256; i++) {
            const uint8_t* p = strs + 32 * i;
            uint32_t h = 2166136261u, slot, k;
            for (k = 0; p[k]; k++)
                h = (h ^ upper[p[k]]) * 16777619u;
            slot = h & 511;
            for (;;) {
                uint32_t idx = table[slot];
                if (!idx) { table[slot] = i + 1; break; }
                {
                    const uint8_t* q = strs + 32 * (idx - 1);
                    uint32_t j = 0;
                    while (upper[p[j]] == upper[q[j]] && p[j]) j++;
                    if (upper[p[j]] == upper[q[j]]) { found++; break; }
                }
                slot = (slot + 1) & 511;
            }
            for (k = 0; (copies[32 * i + k] = p[k]) != 0; k++)
                tall += p[k] > 'Z';
        }
        acc = acc * 33 + found + tall;
    }
    return ((uint64_t)acc << 32) | (found ^ (tall << 8) ^ bsum(copies, 8192));
}

/* ---------------------------------------------------------------- k_bsp */
typedef struct Node { float nrm[3], dist; int front, back, leaf, pad; } Node;    /* 32 bytes */

EXPORT uint64_t __cdecl k_bsp(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    Node* nodes = (Node*)out;                     /* 2047 * 32 = 64 KB */
    float* pts = (float*)(out + 65536);           /* 512 * 12 */
    uint32_t s = seed ^ 0xB5Bu, i, it, acc = 0;
    float dsum = 0.0f;
    for (i = 0; i < 2047; i++) {
        Node* nd = &nodes[i];
        float inv;
        nd->nrm[0] = frand(&s); nd->nrm[1] = frand(&s); nd->nrm[2] = frand(&s) + 0.1f;
        inv = 1.0f / fsqrt_(nd->nrm[0] * nd->nrm[0] + nd->nrm[1] * nd->nrm[1] + nd->nrm[2] * nd->nrm[2]);
        nd->nrm[0] *= inv; nd->nrm[1] *= inv; nd->nrm[2] *= inv;
        nd->dist = frand(&s) * 50.0f;
        nd->front = 2 * (int)i + 1 < 2047 ? 2 * (int)i + 1 : -(int)(i + 1);
        nd->back = 2 * (int)i + 2 < 2047 ? 2 * (int)i + 2 : -(int)(i + 1000);
        nd->leaf = (int)(rd32(in + 4 * (i & 1023)) & 0xFFFF);
        nd->pad = 0;
    }
    for (i = 0; i < 512 * 3; i++)
        pts[i] = frand(&s) * 100.0f;
    for (it = 0; it < n; it++) {
        float drift = (float)(int32_t)(it & 31) * 0.25f;
        for (i = 0; i < 512; i++) {
            const float* p = pts + 3 * i;
            int k = 0, depth = 0;
            float px = p[0] + drift, py = p[1] - drift, pz = p[2];
            while (k >= 0) {
                const Node* nd = &nodes[k];
                float d = nd->nrm[0] * px + nd->nrm[1] * py + nd->nrm[2] * pz - nd->dist;
                depth++;
                if (d >= 0.0f) { dsum += d; k = nd->front; }
                else k = nd->back;
            }
            acc += (uint32_t)(-k) * 31u + (uint32_t)depth;
        }
    }
    return ((uint64_t)acc << 32) | fbits(dsum);
}
