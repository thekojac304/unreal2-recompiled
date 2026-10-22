/* native_x86.c - native side of the differential instruction test (32-bit Windows program).
 *
 *   native_x86.exe cases.bin out_native.bin        (ID_TRACE=1: snippet progress, =2: exceptions too)
 *
 * For every case: copy the snippet to an executable page followed by "jmp dword ptr [g_back]", fill the
 * scratch windows, load GPRs/EFLAGS/x87 state (native_run.asm), execute, and record GPRs, EFLAGS, the
 * x87 state (FNSAVE: control/status/tag words and ST(0)..ST(7) converted to doubles with an exactness
 * flag) and the windows. Hardware exceptions inside a snippet (#DE) are caught by a vectored handler. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include "insn_diff.h"

extern uint32_t g_in_r[8], g_in_flags, g_out_r[8], g_out_flags, g_nst, g_code, g_back;
extern uint16_t g_fcw;
extern double g_st[8];
extern uint8_t g_fsave[108], g_teb_after[ID_TEB_SNAP];
void run_native(void);
void run_native_back(void);
void run_native_fault(void);

/* 80-bit extended -> double; *exact = 0 when the value is not a double (precision or range) */
static double ext_to_double(const uint8_t* b, int* exact) {
    uint64_t mant, bits;
    uint32_t se = (uint32_t)b[8] | ((uint32_t)b[9] << 8);
    uint32_t sign = se >> 15, exp = se & 0x7FFF;
    int lz = 0, e;
    double d;
    memcpy(&mant, b, 8);
    *exact = 1;
    if (exp == 0x7FFF) {
        if ((mant << 1) == 0) {
            bits = ((uint64_t)sign << 63) | 0x7FF0000000000000ull;
        } else {
            bits = ((uint64_t)sign << 63) | 0x7FF0000000000000ull | ((mant >> 11) & 0x000FFFFFFFFFFFFFull);
            if ((mant & 0x7FF) != 0 || !(mant >> 63))
                *exact = 0;
            if (!(bits & 0x000FFFFFFFFFFFFFull))
                bits |= 1;               /* keep it a NaN */
        }
        memcpy(&d, &bits, 8);
        return d;
    }
    if (mant == 0) {
        bits = (uint64_t)sign << 63;
        if (exp != 0)
            *exact = 0;                  /* pseudo-zero */
        memcpy(&d, &bits, 8);
        return d;
    }
    while (!(mant >> 63)) {
        mant <<= 1;
        lz++;
    }
    e = (exp ? (int)exp : 1) - 16383 - lz;   /* unbiased exponent of the leading bit */
    if (e > 1023) {
        *exact = 0;
        bits = ((uint64_t)sign << 63) | 0x7FF0000000000000ull;
    } else if (e >= -1022) {
        uint64_t frac = mant >> 11, rem = mant & 0x7FF;
        if (rem)
            *exact = 0;
        if (rem > 0x400 || (rem == 0x400 && (frac & 1)))
            frac++;                      /* round to nearest even (diagnostics only) */
        bits = ((uint64_t)sign << 63) + ((uint64_t)(e + 1023) << 52) + (frac - (1ull << 52));
    } else {
        int sh = 11 + (-1022 - e);
        if (sh >= 64) {
            *exact = 0;
            bits = (uint64_t)sign << 63;
        } else {
            if (mant & ((1ull << sh) - 1))
                *exact = 0;
            bits = ((uint64_t)sign << 63) | (mant >> sh);
        }
    }
    memcpy(&d, &bits, 8);
    return d;
}

/* Hardware exceptions inside a snippet (#DE): the vectored handler resumes at run_native_fault, which
 * restores the host stack and returns from run_native(). Frame-based SEH is not used: ESP points into
 * the scratch region while a snippet runs, and frame-based dispatch does not survive that. */
static uint8_t* code_page;
static volatile uint32_t fault_code;
static int trace;

static LONG CALLBACK veh(EXCEPTION_POINTERS* ep) {
    uint32_t eip = ep->ContextRecord->Eip, lo = (uint32_t)(uintptr_t)code_page;
    if (trace > 1) {
        fprintf(stderr, "  exception %08lx at %08x esp=%08lx\n", ep->ExceptionRecord->ExceptionCode, eip,
                ep->ContextRecord->Esp);
        fflush(stderr);
    }
    if (eip >= lo && eip < lo + 0x100) {
        fault_code = ep->ExceptionRecord->ExceptionCode;
        ep->ContextRecord->Eip = (DWORD)(uintptr_t)&run_native_fault;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

int main(int argc, char** argv) {
    FILE *fi, *fo;
    IdHeader h;
    uint32_t *offs, *lens, bloblen, i, cur = UINT32_MAX;
    uint8_t *blob, *region, *data, *stack;
    static uint8_t data0[ID_DATA_SIZE], stack0[ID_STACK_SIZE];
    const char* tr = getenv("ID_TRACE");
    trace = tr ? atoi(tr) : 0;
    if (argc < 4) {
        fprintf(stderr, "usage: native_x86 cases.bin out.bin teb.bin\n");
        return 2;
    }
    fi = fopen(argv[1], "rb");
    fo = fopen(argv[2], "wb");
    if (!fi || !fo || fread(&h, sizeof h, 1, fi) != 1 || memcmp(h.magic, "XDIN", 4)) {
        fprintf(stderr, "native_x86: bad input/output\n");
        return 2;
    }
    offs = (uint32_t*)malloc(4 * h.nsnip);
    lens = (uint32_t*)malloc(4 * h.nsnip);
    for (i = 0; i < h.nsnip; i++)
        if (fread(&offs[i], 4, 1, fi) != 1 || fread(&lens[i], 4, 1, fi) != 1)
            return 2;
    if (fread(&bloblen, 4, 1, fi) != 1)
        return 2;
    blob = (uint8_t*)malloc(bloblen);
    if (fread(blob, 1, bloblen, fi) != bloblen)
        return 2;
    region = (uint8_t*)VirtualAlloc((void*)(uintptr_t)ID_REGION, ID_REGION_SIZE, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (region != (uint8_t*)(uintptr_t)ID_REGION) {
        fprintf(stderr, "native_x86: cannot allocate the scratch region at %08x (error %lu)\n", ID_REGION, GetLastError());
        return 3;
    }
    data = region + (ID_DATA - ID_REGION);
    stack = region + (ID_STACK - ID_REGION);
    code_page = (uint8_t*)VirtualAlloc(NULL, 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (!code_page)
        return 3;
    {
        /* TEB address and snapshot for the lifted side's fs: (guest TEB at the same address) */
        /* copied here, in main's frame: ExceptionList must be the value run_native() will see (fwrite
         * registers its own SEH frame, so the TEB must not be passed to it directly) */
        uint8_t* teb = (uint8_t*)NtCurrentTeb();
        uint8_t snap[ID_TEB_SNAP];
        uint32_t ta = (uint32_t)(uintptr_t)teb;
        FILE* ft = fopen(argv[3], "wb");
        memcpy(snap, teb, ID_TEB_SNAP);
        if (!ft || fwrite(&ta, 4, 1, ft) != 1 || fwrite(snap, 1, ID_TEB_SNAP, ft) != ID_TEB_SNAP)
            return 2;
        fclose(ft);
    }
    AddVectoredExceptionHandler(1, veh);
    g_back = (uint32_t)(uintptr_t)&run_native_back;
    g_code = (uint32_t)(uintptr_t)code_page;
    for (i = 0; i < h.ncase; i++) {
        IdCase k;
        IdOut o;
        uint32_t j, valid = 0, exact = 0, top, tags;
        if (fread(&k, sizeof k, 1, fi) != 1) {
            fprintf(stderr, "native_x86: short input at case %u\n", i);
            return 2;
        }
        if (k.snip != cur) {
            uint32_t a = (uint32_t)(uintptr_t)&g_back;
            cur = k.snip;
            if (trace) {
                fprintf(stderr, "snippet %u (case %u)\n", cur, i);
                fflush(stderr);
            }
            memset(code_page, 0xCC, 0x100);
            memcpy(code_page, blob + offs[cur], lens[cur]);
            code_page[lens[cur]] = 0xFF;
            code_page[lens[cur] + 1] = 0x25;
            memcpy(code_page + lens[cur] + 2, &a, 4);
            FlushInstructionCache(GetCurrentProcess(), code_page, 0x100);
        }
        memset(&o, 0, sizeof o);
        id_fill(data, stack, &k);
        memcpy(data0, data, ID_DATA_SIZE);
        memcpy(stack0, stack, ID_STACK_SIZE);
        memcpy(g_in_r, k.r, sizeof k.r);
        g_in_flags = (k.eflags & 0x0CD5u) | 2u;
        g_fcw = k.fcw;
        g_nst = k.nst;
        memcpy(g_st, k.st, sizeof k.st);
        memset(g_fsave, 0, sizeof g_fsave);
        fault_code = 0;
        run_native();
        if (fault_code) {
            o.status = (fault_code == EXCEPTION_INT_DIVIDE_BY_ZERO || fault_code == EXCEPTION_INT_OVERFLOW) ? ID_DE : ID_EXC;
            o.excode = fault_code;
        } else {
            o.status = ID_OK;
            memcpy(o.r, g_out_r, sizeof o.r);
            o.eflags = g_out_flags;
            memcpy(&o.fcw, g_fsave + 0, 2);
            memcpy(&o.fsw, g_fsave + 4, 2);
            tags = (uint32_t)g_fsave[8] | ((uint32_t)g_fsave[9] << 8);
            top = (o.fsw >> 11) & 7;
            for (j = 0; j < 8; j++) {
                int ex;
                uint32_t phys = (top + j) & 7;
                if (((tags >> (2 * phys)) & 3) != 3)
                    valid |= 1u << j;
                o.st[j] = ext_to_double(g_fsave + 28 + 10 * j, &ex);
                if (ex)
                    exact |= 1u << j;
            }
            o.valid = (uint16_t)valid;
            o.exact = (uint16_t)exact;
        }
        if (o.status == ID_OK)
            o.hfs = id_teb_hash(g_teb_after);
        id_windows_out(&o, data, stack, data0, stack0);
        fwrite(&o, sizeof o, 1, fo);
    }
    fclose(fo);
    fprintf(stderr, "native_x86: %u cases, %u snippets\n", h.ncase, h.nsnip);
    return 0;
}
