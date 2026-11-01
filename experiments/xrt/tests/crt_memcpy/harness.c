/* crt_memcpy - focused test of a lifted static-CRT memcpy (ogg.dll's, lifted by tools/xrt/xlift.py at 0x10010000;
 * the developer sound lift in out/dev-init/audio-lift/ogg). That memcpy jumps through LeadUpVec/TrailUpVec/... tables
 * inside .text; discovery used to split it at relocated case labels, and one jump indexes a table negatively
 * (jmp [ecx*4 + TrailUpVec + 16] after sub ecx, 4 / jb). The lifted function runs on the runtime CPU model:
 *   every dst/src alignment (0..3) x length 0..96, lengths 97..4100 in steps, and overlapping moves in both
 *   directions (the 2002 CRT memcpy is memmove: it copies downwards when dst > src and the ranges overlap);
 *   oracle: host memmove on a copy of the same window. Checked: the whole 16 KiB window (no stray writes), the
 *   return value (dst), esp, and the callee-saved ebx/esi/edi/ebp.
 *   harness.exe image.bin BASE MEMCPY_VA
 * Exit 0 when every case matches. Build/run: run.py. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "xrt.h"

extern const XrtLiftedModule xrt_mod_ogg;
uint8_t* xrt_g;
volatile long xrt_preempt_req = 0;
static jmp_buf jb;
static const char* why = "";
static uint32_t why_site;

static XrtFn lookup(uint32_t va) {
    const XrtLiftedModule* m = &xrt_mod_ogg;
    uint32_t lo = 0, hi = m->nfuncs;
    while (lo < hi) { uint32_t mid = (lo + hi) / 2; if (m->funcs[mid].va < va) lo = mid + 1; else hi = mid; }
    return lo < m->nfuncs && m->funcs[lo].va == va ? m->funcs[lo].fn : NULL;
}
void xrt_preempt(CPU* c) { (void)c; }
XrtCallCache xrt_call_cache[65536];
uint32_t xrt_call_cache_gen = 1;
void xrt_icall_after(CPU* c) { (void)c; }
void xrt_icall(CPU* c, uint32_t target, uint32_t site) {
    XrtFn fn = lookup(target);
    if (!fn) { why = "indirect transfer to a non-entry"; why_site = site; longjmp(jb, 4); }
    fn(c);
}
void xrt_ijmp(CPU* c, uint32_t target, uint32_t site) { xrt_icall(c, target, site); }
XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* w) { (void)c; why = w; why_site = site; longjmp(jb, 1); }
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected) { (void)c; (void)expected; why = "bad return"; why_site = site; longjmp(jb, 3); }
XRT_NORETURN void xrt_div0(CPU* c, uint32_t site) { (void)c; why = "div0"; why_site = site; longjmp(jb, 2); }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) { (void)c; (void)code; why = fmt; longjmp(jb, 2); }
void xrt_mark(CPU* c, XrtMark* m) { (void)c; (void)m; }
void xrt_watch_store(CPU* c, XrtWatchDef* w, uint32_t site) { (void)c; (void)w; (void)site; }
void xrt_log(const char* fmt, ...) { (void)fmt; }
void xrt_fldcw(CPU* c, uint16_t cw) { c->fcw = cw; }
void xrt_fsqrt(CPU* c) { (void)c; longjmp(jb, 2); }
void xrt_fsin(CPU* c) { (void)c; longjmp(jb, 2); }
int32_t xrt_fist32(CPU* c, double v) { (void)c; (void)v; longjmp(jb, 2); }
/* other ogg.dll functions register SEH frames; memcpy does not, so these are never reached */
void xrt_eh_register(CPU* c, XrtEhPad* p) { (void)c; (void)p; longjmp(jb, 2); }
void xrt_eh_landed(CPU* c, XrtEhPad* p) { (void)c; (void)p; longjmp(jb, 2); }
void xrt_eh_pop(CPU* c, XrtEhPad* p) { (void)c; (void)p; longjmp(jb, 2); }

#define WIN 0x00800000u      /* 16 KiB window */
#define WINSZ 0x4000u
#define STACK 0x00700000u
#define RETADDR 0x00401234u
static uint8_t expect[WINSZ];
static int failures, cases;

static void fill(uint32_t seed) {
    uint32_t i, x = seed * 2654435761u + 1;
    for (i = 0; i < WINSZ; i++) { x = x * 1103515245u + 12345u; xrt_g[WIN + i] = (uint8_t)(x >> 16); }
}
static void one(XrtFn fn, uint32_t dst, uint32_t src, uint32_t n) {
    static CPU c;
    uint32_t i, esp = STACK - 64;
    int st;
    fill(dst * 31u + src * 7u + n);
    memcpy(expect, xrt_g + WIN, WINSZ);
    memmove(expect + (dst - WIN), expect + (src - WIN), n);
    memset(&c, 0, sizeof c);
    c.fcw = 0x027F;
    c.r[EBX] = 0x11111111u; c.r[EBP] = 0x22222222u; c.r[ESI] = 0x33333333u; c.r[EDI] = 0x44444444u;
    c.r[ECX] = 0x55555555u; c.r[EDX] = 0x66666666u; c.r[EAX] = 0x77777777u;
    wr32(esp, RETADDR); wr32(esp + 4, dst); wr32(esp + 8, src); wr32(esp + 12, n);
    c.r[ESP] = esp;
    cases++;
    if ((st = setjmp(jb)) == 0) {
        fn(&c);
        if (c.rv != RETADDR || c.r[ESP] != esp + 4) { why = "return address/stack"; st = 5; }
    }
    if (!st && (c.r[EAX] != dst || c.r[EBX] != 0x11111111u || c.r[EBP] != 0x22222222u || c.r[ESI] != 0x33333333u || c.r[EDI] != 0x44444444u)) {
        why = "eax/callee-saved registers"; st = 6;
    }
    if (!st)
        for (i = 0; i < WINSZ; i++)
            if (xrt_g[WIN + i] != expect[i]) { why = "memory"; why_site = WIN + i; st = 7; break; }
    if (st && failures++ < 20)
        printf("FAIL dst %08x src %08x n %u: %s (%08x)\n", dst, src, n, why, why_site);
}

int main(int argc, char** argv) {
    FILE* fi;
    uint32_t base, va, da, sa, n, d;
    size_t got;
    XrtFn fn;
    static uint8_t image[1 << 20];
    if (argc < 4) return 2;
    base = (uint32_t)strtoul(argv[2], NULL, 0);
    va = (uint32_t)strtoul(argv[3], NULL, 0);
    xrt_g = (uint8_t*)VirtualAlloc(NULL, 0x100000000ull + 0x10000u, MEM_RESERVE, PAGE_NOACCESS);
    if (!xrt_g || !(fi = fopen(argv[1], "rb"))) return 2;
    got = fread(image, 1, sizeof image, fi);
    fclose(fi);
    VirtualAlloc(xrt_g + base, (got + 0xFFFF) & ~0xFFFFu, MEM_COMMIT, PAGE_READWRITE);
    memcpy(xrt_g + base, image, got);
    VirtualAlloc(xrt_g + WIN, WINSZ, MEM_COMMIT, PAGE_READWRITE);
    VirtualAlloc(xrt_g + STACK - 0x10000, 0x10000, MEM_COMMIT, PAGE_READWRITE);
    if (!(fn = lookup(va))) { printf("FAIL: %08x is not a lifted function entry\n", va); return 1; }
    for (da = 0; da < 4; da++)
        for (sa = 0; sa < 4; sa++) {
            for (n = 0; n <= 96; n++) one(fn, WIN + 0x2000 + da, WIN + 0x100 + sa, n);
            for (n = 97; n <= 4100; n += 37) one(fn, WIN + 0x2000 + da, WIN + 0x100 + sa, n);
        }
    for (d = 1; d <= 40; d++)                      /* overlapping: dst above src (downward copy) and below */
        for (n = 0; n <= 300; n += (n < 40 ? 1 : 13)) {
            one(fn, WIN + 0x1000 + d, WIN + 0x1000, n);
            one(fn, WIN + 0x1000, WIN + 0x1000 + d, n);
            one(fn, WIN + 0x1003 + d, WIN + 0x1001, n);
        }
    printf("%s: %d cases, %d failure(s)\n", failures ? "FAIL" : "PASS", cases, failures);
    return failures ? 1 : 0;
}
