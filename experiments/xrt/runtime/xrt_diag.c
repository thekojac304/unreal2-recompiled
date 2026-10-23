/* xrt_diag.c - fatal diagnostics and the bounded runtime event log.
 * Every failure names: module + RVA (+ export), the instruction or call target, the guest thread,
 * registers, a stack-scanned guest backtrace and the recent function-entry history. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

volatile long xrt_dying;
static FILE* log_file;
static long log_budget = 50000;
static SRWLOCK log_lock = SRWLOCK_INIT;

void xrt_log(const char* fmt, ...) {
    va_list ap;
    if (!log_file)
        return;
    AcquireSRWLockExclusive(&log_lock);
    if (log_budget > 0) {
        if (--log_budget == 0) {
            fputs("[log budget exhausted; further events dropped]\n", log_file);
        } else {
            fprintf(log_file, "[t%d] ", xrt_cur ? xrt_cur->index : -1);
            va_start(ap, fmt);
            vfprintf(log_file, fmt, ap);
            va_end(ap);
            fputc('\n', log_file);
        }
    }
    ReleaseSRWLockExclusive(&log_lock);
}

void xrt_describe(char* out, size_t n, uint32_t va) {
    XrtModule* m = xrt_module_by_addr(va);
    const char* stub = xrt_stub_name(va);
    if (stub) {
        snprintf(out, n, "%08x [import stub %s]", va, stub);
    } else if (m) {
        uint32_t f = xrt_lookup_containing(va);
        const char* ex = f ? xrt_export_name_at(f) : NULL;
        if (f && f != va)
            snprintf(out, n, "%08x (%s+%x, in f_%x+%x%s%s)", va, m->name, va - m->base, f, va - f, ex ? " " : "", ex ? ex : "");
        else
            snprintf(out, n, "%08x (%s+%x%s%s)", va, m->name, va - m->base, ex ? " " : "", ex ? ex : "");
    } else if (va == XRT_HOST_RETURN) {
        snprintf(out, n, "%08x (host return sentinel)", va);
    } else {
        snprintf(out, n, "%08x (outside lifted modules)", va);
    }
}

static int looks_like_return_address(uint32_t a) {
    XrtModule* m = xrt_module_by_addr(a);
    if (!m || a < m->base + 0x1000 || a - 6 < m->base)
        return 0;
    return rd8(a - 5) == 0xE8 || (rd8(a - 6) == 0xFF && ((rd8(a - 5) >> 3) & 7) == 2) ||
           (rd8(a - 2) == 0xFF && ((rd8(a - 1) >> 3) & 7) == 2) || (rd8(a - 3) == 0xFF && ((rd8(a - 2) >> 3) & 7) == 2) ||
           (rd8(a - 7) == 0xFF && ((rd8(a - 6) >> 3) & 7) == 2);
}

static void dump_cpu(CPU* c) {
    char d[512];
    int i, shown = 0;
    XrtThread* t = c->thread;
    xrt_describe(d, sizeof d, c->pc);
    fprintf(stderr, "  guest thread %d (tid %u), last instruction %s\n", t ? t->index : -1, t ? t->guest_tid : 0, d);
    fprintf(stderr, "  eax=%08x ecx=%08x edx=%08x ebx=%08x esp=%08x ebp=%08x esi=%08x edi=%08x\n", c->r[0], c->r[1],
            c->r[2], c->r[3], c->r[4], c->r[5], c->r[6], c->r[7]);
    fprintf(stderr, "  cf=%u pf=%u zf=%u sf=%u of=%u df=%u  fcw=%04x fsw=%04x top=%u fs_base=%08x\n", c->cf, c->pf, c->zf,
            c->sf, c->of, c->df, c->fcw, fstatus(c), c->top, c->fs_base);
    fprintf(stderr, "  recent function entries (newest first):\n");
    for (i = 0; i < 16 && i < (int)c->hpos; i++) {
        uint32_t va = c->hist[(c->hpos - 1 - i) & (XRT_HIST - 1)];
        xrt_describe(d, sizeof d, va);
        fprintf(stderr, "    %s\n", d);
    }
    fprintf(stderr, "  guest stack (return addresses found scanning up from esp):\n");
    if (t && c->r[ESP] >= t->stack_lo && c->r[ESP] < t->stack_hi) {
        uint32_t p;
        for (p = c->r[ESP]; p + 4 <= t->stack_hi && shown < 24; p += 4) {
            uint32_t v = rd32(p);
            if (looks_like_return_address(v)) {
                xrt_describe(d, sizeof d, v);
                fprintf(stderr, "    [esp+%04x] %s\n", p - c->r[ESP], d);
                shown++;
            }
        }
    } else {
        fprintf(stderr, "    (esp outside the thread's guest stack)\n");
    }
}

XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list ap;
    char msg[1024];
    if (InterlockedExchange(&xrt_dying, 1)) {
        TerminateProcess(GetCurrentProcess(), (UINT)code);
        for (;;) {}
    }
    if (!c && xrt_cur)
        c = &xrt_cur->cpu;
    xrt_stdout_flush();
    va_start(ap, fmt);
    vsnprintf(msg, sizeof msg, fmt, ap);
    va_end(ap);
    fprintf(stderr, "\nXRT FATAL (exit %d): %s\n", code, msg);
    if (c)
        dump_cpu(c);
    fflush(stderr);
    xrt_log("FATAL %d: %s", code, msg);
    {
        char j[1200];
        xrt_event("fatal", "\"code\": %d, \"message\": %s", code, xrt_jstr(j, sizeof j, msg));
    }
    if (log_file)
        fflush(log_file);
    xrt_cleanup_atoms();
    xrt_report_write((uint32_t)code, msg);
    TerminateProcess(GetCurrentProcess(), (UINT)code);
    for (;;) {}
}

XRT_NORETURN void xrt_trap(CPU* c, uint32_t site, const char* why) {
    char d[512];
    xrt_describe(d, sizeof d, site);
    c->pc = site;
    xrt_fatal(c, XRT_EXIT_TRAP, "reached untranslated code at %s: %s", d, why);
}

XRT_NORETURN void xrt_badret(CPU* c, uint32_t site, uint32_t expected) {
    char d[512], r[512];
    xrt_describe(d, sizeof d, site);
    xrt_describe(r, sizeof r, c->rv);
    xrt_fatal(c, XRT_EXIT_BADRET, "return-address mismatch after the call at %s: expected %08x, callee returned to %s", d,
              expected, r);
}

XRT_NORETURN void xrt_div0(CPU* c, uint32_t site) {
    char d[512];
    xrt_describe(d, sizeof d, site);
    c->pc = site;
    xrt_fatal(c, XRT_EXIT_DIV0, "integer divide error (#DE) at %s (the original would raise a structured exception)", d);
}

static LONG CALLBACK veh(EXCEPTION_POINTERS* ep) {
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    void* pc = ep->ExceptionRecord->ExceptionAddress;
    HMODULE self = GetModuleHandleW(NULL), owner = NULL;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCWSTR)pc, &owner);
    if (code == EXCEPTION_STACK_OVERFLOW) {
        static const char m[] = "\nXRT FATAL: host stack overflow while executing translated code\n";
        DWORD w;
        WriteFile(GetStdHandle(STD_ERROR_HANDLE), m, sizeof m - 1, &w, NULL);
        TerminateProcess(GetCurrentProcess(), XRT_EXIT_FAULT);
    }
    if (code == EXCEPTION_ACCESS_VIOLATION && ep->ExceptionRecord->NumberParameters >= 2) {
        uint8_t* a = (uint8_t*)ep->ExceptionRecord->ExceptionInformation[1];
        const char* kind = ep->ExceptionRecord->ExceptionInformation[0] == 1 ? "write" : "read";
        if (a >= xrt_g && a < xrt_g + 0x100010000ull) {
            uint32_t ga = (uint32_t)(a - xrt_g);
            const char* stub = xrt_stub_name(ga & ~(XRT_STUB_SIZE - 1));
            if (stub)
                xrt_fatal(NULL, XRT_EXIT_FAULT, "guest %s of %08x: data access through function import stub %s", kind, ga, stub);
            xrt_fatal(NULL, XRT_EXIT_FAULT, "guest memory %s fault at guest address %08x%s (host pc %p%s)", kind, ga,
                      ga < 0x10000 ? " (null-pointer region)" : "", pc, owner == self ? "" : " in a host library");
        }
        if (owner == self)
            xrt_fatal(NULL, XRT_EXIT_FAULT, "host %s fault at %p in the runtime (host pc %p)", kind, (void*)a, pc);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    if (owner == self && (code == EXCEPTION_INT_DIVIDE_BY_ZERO || code == EXCEPTION_ILLEGAL_INSTRUCTION ||
                          code == EXCEPTION_PRIV_INSTRUCTION || code == EXCEPTION_INT_OVERFLOW))
        xrt_fatal(NULL, XRT_EXIT_FAULT, "host exception %08lx at host pc %p", code, pc);
    return EXCEPTION_CONTINUE_SEARCH;
}

void xrt_diag_init(const char* log_path) {
    if (log_path) {
        log_file = fopen(log_path, "w");
        if (log_file)
            setvbuf(log_file, NULL, _IOFBF, 1 << 16);
    }
    AddVectoredExceptionHandler(1, veh);
}
