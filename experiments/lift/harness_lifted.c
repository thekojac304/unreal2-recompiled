/* Runs the LIFTED (x86 -> C) Core.dll routines natively (x64, ARM64, ...) and
 * prints results in the same format as harness_original.c.
 * Usage: harness_lifted <path to original Core.dll>   (used read-only to map data sections) */
#include <stdio.h>

#include "testvec.h"
#include "x86rt.h"

uint8_t* g_pages[1u << 20];

/* Lifted entry points (generated). */
void lifted_appMemCrc(CPU* c);
void lifted_appStrCrcCaps(CPU* c);
void lifted_appMD5Transform(CPU* c);
void lifted_appBlend(CPU* c);
void lifted_appAblend(CPU* c);
void lifted_appRound(CPU* c);
void lifted_appFloor(CPU* c);
void lifted_appCeil(CPU* c);
void lifted_appSRandInit(CPU* c);
void lifted_appSRand(CPU* c);

/* Host implementations of imported CRT functions (cdecl, double arg, x87 return). */
void host_floor(CPU* c) { double x = rdf64(c->r[ESP] + 4); fpush(c, floor(x)); c->r[ESP] += 4; }
void host_ceil(CPU* c) { double x = rdf64(c->r[ESP] + 4); fpush(c, ceil(x)); c->r[ESP] += 4; }
void host_wcslen(CPU* c) {
    uint32_t p = rd32(c->r[ESP] + 4), n = 0;
    while (rd16(p + 2u * n)) n++;
    c->r[EAX] = n;
    c->r[ESP] += 4;
}

#define STACK_TOP 0x00800000u
#define SCRATCH 0x00400000u
#define RET_SENTINEL 0xDEAD0000u
#define GCRCTABLE_VA 0x101ed7b8u

static void map_pe(const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t* d = (uint8_t*)malloc((size_t)n);
    if (fread(d, 1, (size_t)n, f) != (size_t)n) { fprintf(stderr, "read error\n"); exit(1); }
    fclose(f);
    uint32_t pe; memcpy(&pe, d + 0x3c, 4);
    uint16_t nsec; memcpy(&nsec, d + pe + 6, 2);
    uint16_t optsz; memcpy(&optsz, d + pe + 20, 2);
    uint32_t base; memcpy(&base, d + pe + 24 + 28, 4);
    uint8_t* sh = d + pe + 24 + optsz;
    for (int i = 0; i < nsec; i++, sh += 40) {
        uint32_t vsize, va, rawsize, rawptr;
        memcpy(&vsize, sh + 8, 4); memcpy(&va, sh + 12, 4); memcpy(&rawsize, sh + 16, 4); memcpy(&rawptr, sh + 20, 4);
        for (uint32_t k = 0; k < rawsize && k < vsize; k++) wr8(base + va + k, d[rawptr + k]);
    }
    free(d);
}

static CPU g_cpu;
static void call_cdecl(void (*fn)(CPU*), int nargs, const uint32_t* args) {
    CPU* c = &g_cpu;
    for (int i = nargs - 1; i >= 0; i--) push32(c, args[i]);
    push32(c, RET_SENTINEL);
    fn(c);
    c->r[ESP] += 4u * (uint32_t)nargs;   /* caller cleans (cdecl) */
    if (c->r[ESP] != STACK_TOP) { fprintf(stderr, "stack imbalance\n"); exit(4); }
}
static float pop_float_result(void) { return (float)fpop(&g_cpu); }

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: harness_lifted <Core.dll>\n"); return 2; }
    map_pe(argv[1]);
    CPU* c = &g_cpu;
    memset(c, 0, sizeof *c);
    c->r[ESP] = STACK_TOP;
    c->fcw = 0x027F;      /* Windows default x87 control word: PC=53-bit, RC=nearest, exceptions masked */
    c->top = 0;
    uint32_t table[256];
    fill_crc_table(table);
    for (int i = 0; i < 256; i++) wr32(GCRCTABLE_VA + 4u * (uint32_t)i, table[i]);

    for (int i = 0; i < N_CASES; i++) {
        int len = (int)(rng() % 300);
        for (int k = 0; k < len; k++) wr8(SCRATCH + (uint32_t)k, (uint8_t)rng());
        uint32_t seed = rng();
        uint32_t a1[3] = {SCRATCH, (uint32_t)len, seed};
        call_cdecl(lifted_appMemCrc, 3, a1);
        printf("memcrc %d %08lx\n", i, (unsigned long)c->r[EAX]);
        int wl = (int)(rng() % 40);
        for (int k = 0; k < wl; k++) wr16(SCRATCH + 0x1000u + 2u * (uint32_t)k, (uint16_t)(0x20 + rng() % 0x60));
        wr16(SCRATCH + 0x1000u + 2u * (uint32_t)wl, 0);
        uint32_t a2[1] = {SCRATCH + 0x1000u};
        call_cdecl(lifted_appStrCrcCaps, 1, a2);
        printf("strcrccaps %d %08lx\n", i, (unsigned long)c->r[EAX]);
        for (int k = 0; k < 4; k++) wr32(SCRATCH + 0x2000u + 4u * (uint32_t)k, rng());
        for (int k = 0; k < 64; k++) wr8(SCRATCH + 0x3000u + (uint32_t)k, (uint8_t)rng());
        uint32_t a3[2] = {SCRATCH + 0x2000u, SCRATCH + 0x3000u};
        call_cdecl(lifted_appMD5Transform, 2, a3);
        printf("md5 %d %08lx%08lx%08lx%08lx\n", i, (unsigned long)rd32(SCRATCH + 0x2000u), (unsigned long)rd32(SCRATCH + 0x2004u),
               (unsigned long)rd32(SCRATCH + 0x2008u), (unsigned long)rd32(SCRATCH + 0x200Cu));
        float a = rngf(), b = rngf(), p = rngf();
        uint32_t a4[3] = {f2bits(a), f2bits(b), f2bits(p)};
        call_cdecl(lifted_appBlend, 3, a4);
        float r1 = pop_float_result();
        call_cdecl(lifted_appAblend, 3, a4);
        float r2 = pop_float_result();
        printf("blend %d %08x %08x\n", i, f2bits(r1), f2bits(r2));
        float x = rngf();
        uint32_t a5[1] = {f2bits(x)};
        call_cdecl(lifted_appRound, 1, a5);
        uint32_t rr = c->r[EAX];
        call_cdecl(lifted_appFloor, 1, a5);
        uint32_t rf = c->r[EAX];
        call_cdecl(lifted_appCeil, 1, a5);
        uint32_t rc = c->r[EAX];
        printf("round %d %08x %08x %08x\n", i, rr, rf, rc);
    }
    uint32_t s[1] = {12345};
    call_cdecl(lifted_appSRandInit, 1, s);
    for (int i = 0; i < 2000; i++) {
        call_cdecl(lifted_appSRand, 0, NULL);
        printf("srand %d %08x\n", i, f2bits(pop_float_result()));
    }
    return 0;
}
