/* lifted_x64.c - lifted side of the differential instruction test (Windows x64 program).
 *
 *   lifted_x64.exe cases.bin out_lifted.bin
 *
 * Runs every case through the C that tools/xrt/xlift.py produced for the snippet (generated
 * id_lifted.c, compiled with the same flags as the translated modules), on the runtime's CPU model
 * (runtime/xrt.h, xrt_cpu.c) and guest memory (xrt_mem.c: 4 GB reservation, the scratch region is
 * committed at the same address the native harness uses). Runtime entry points the generated code may
 * reach (xrt_div0, xrt_trap, xrt_fatal, ...) are trivial definitions here that record the outcome and
 * longjmp back to the harness. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include "xrt_internal.h"
#include "insn_diff.h"

extern const XrtFn id_fns[];
extern const uint32_t id_nfns;

static jmp_buf jb;
static uint32_t last_site;

/* ---- runtime symbols referenced by generated code, xrt_cpu.c and xrt_mem.c */
volatile long xrt_preempt_req = 0;
__declspec(thread) XrtThread* xrt_cur;
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) {
    (void)a; (void)size; (void)end;
    fputs("test harness: unexpected module-overlap query\n", stderr);
    exit(XRT_EXIT_UNSUPPORTED);
}
void xrt_preempt(CPU* c) { (void)c; }
void xrt_log(const char* fmt, ...) { (void)fmt; }
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    (void)c; (void)code; (void)fmt;
    longjmp(jb, ID_FATAL);
}
XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* why) {
    (void)c; (void)why;
    last_site = site;
    longjmp(jb, ID_TRAP);
}
XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected) {
    (void)c; (void)expected;
    last_site = site;
    longjmp(jb, ID_OTHER);
}
XRT_NORETURN void xrt_div0(CPU* c, uint32_t site) {
    (void)c;
    last_site = site;
    longjmp(jb, ID_DE);
}
void xrt_icall(CPU* c, uint32_t target, uint32_t site) {
    (void)c; (void)target;
    last_site = site;
    longjmp(jb, ID_OTHER);
}
void xrt_ijmp(CPU* c, uint32_t target, uint32_t site) {
    (void)c; (void)target;
    last_site = site;
    longjmp(jb, ID_OTHER);
}

static CPU cpu;

int main(int argc, char** argv) {
    FILE *fi, *fo;
    IdHeader h;
    uint32_t i, skip;
    uint8_t *data, *stack;
    static uint8_t data0[ID_DATA_SIZE], stack0[ID_STACK_SIZE];
    uint32_t teb = 0;
    uint8_t teb_snap[ID_TEB_SNAP];
    if (argc < 4) {
        fprintf(stderr, "usage: lifted_x64 cases.bin out.bin teb.bin\n");
        return 2;
    }
    fi = fopen(argv[1], "rb");
    fo = fopen(argv[2], "wb");
    if (!fi || !fo || fread(&h, sizeof h, 1, fi) != 1 || memcmp(h.magic, "XDIN", 4)) {
        fprintf(stderr, "lifted_x64: bad input/output\n");
        return 2;
    }
    if (h.nsnip != id_nfns) {
        fprintf(stderr, "lifted_x64: %u snippets in the cases, %u lifted functions\n", h.nsnip, id_nfns);
        return 2;
    }
    skip = 8 * h.nsnip;
    fseek(fi, (long)skip, SEEK_CUR);
    if (fread(&skip, 4, 1, fi) != 1)
        return 2;
    fseek(fi, (long)skip, SEEK_CUR);
    xrt_mem_init();
    xrt_commit(ID_REGION, ID_REGION_SIZE);
    {
        /* guest TEB at the native TEB's address with the native snapshot: fs: operands see the same data */
        FILE* ft = fopen(argv[3], "rb");
        if (!ft || fread(&teb, 4, 1, ft) != 1 || fread(teb_snap, 1, ID_TEB_SNAP, ft) != ID_TEB_SNAP) {
            fprintf(stderr, "lifted_x64: cannot read %s\n", argv[3]);
            return 2;
        }
        fclose(ft);
        xrt_commit(teb, ID_TEB_SNAP);
    }
    data = (uint8_t*)G2H(ID_DATA);
    stack = (uint8_t*)G2H(ID_STACK);
    for (i = 0; i < h.ncase; i++) {
        IdCase k;
        IdOut o;
        volatile int st;
        uint32_t j;
        CPU* c = &cpu;
        if (fread(&k, sizeof k, 1, fi) != 1) {
            fprintf(stderr, "lifted_x64: short input at case %u\n", i);
            return 2;
        }
        memset(&o, 0, sizeof o);
        memset(c, 0, sizeof *c);
        memcpy(c->r, k.r, sizeof k.r);
        c->cf = k.eflags & 1;
        c->pf = (k.eflags >> 2) & 1;
        c->zf = (k.eflags >> 6) & 1;
        c->sf = (k.eflags >> 7) & 1;
        c->df = (k.eflags >> 10) & 1;
        c->of = (k.eflags >> 11) & 1;
        c->fcw = k.fcw;
        c->fsw = 0;
        c->fs_base = teb;
        memcpy(G2H(teb), teb_snap, ID_TEB_SNAP);
        c->top = (8u - k.nst) & 7u;
        for (j = 0; j < 8; j++)
            c->st[j] = -12345.0;                  /* empty registers (the model has no tag word) */
        for (j = 0; j < k.nst; j++)
            *ST(c, (int)j) = k.st[j];
        id_fill(data, stack, &k);
        memcpy(data0, data, ID_DATA_SIZE);
        memcpy(stack0, stack, ID_STACK_SIZE);
        st = setjmp(jb);
        if (st == 0) {
            id_fns[k.snip](c);
            o.status = ID_OK;
        } else {
            o.status = (uint32_t)st;
            o.excode = last_site;
        }
        if (o.status == ID_OK) {
            memcpy(o.r, c->r, sizeof o.r);
            o.eflags = 2u | c->cf | (c->pf << 2) | (c->zf << 6) | (c->sf << 7) | (c->df << 10) | (c->of << 11);
            o.fcw = c->fcw;
            o.hfs = id_teb_hash((const uint8_t*)G2H(teb));
            o.fsw = fstatus(c);
            o.valid = 0xFF;
            o.exact = 0xFF;
            for (j = 0; j < 8; j++)
                o.st[j] = *ST(c, (int)j);
        }
        id_windows_out(&o, data, stack, data0, stack0);
        fwrite(&o, sizeof o, 1, fo);
    }
    fclose(fo);
    fprintf(stderr, "lifted_x64: %u cases, %u snippets\n", h.ncase, h.nsnip);
    return 0;
}
