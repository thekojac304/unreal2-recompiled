/* xrt_thread.c - guest threads.
 *
 * Each guest thread is a real host thread with its own CPU state, guest stack (guard region below it)
 * and guest TEB (fs:). Translated code runs only while holding the runtime's execution baton, a FIFO
 * ticket lock: exactly one guest thread executes guest code at any time. The baton is handed over
 *   - at blocking imports (Sleep, contended EnterCriticalSection), and
 *   - by time slicing: while another guest thread waits, a 1 ms ticker requests preemption and the
 *     running thread yields at its next translated function entry (XRT_ENTER).
 * So guest threads interleave at function-entry granularity, like a preemptive scheduler with a coarse
 * grain; a loop that makes no calls cannot be preempted (the harness timeout would catch a hang).
 * Lock-prefixed read-modify-write instructions are atomic with respect to other guest threads.
 * Once ExitProcess starts, other guest threads never get the baton again (Windows terminates them before
 * DLL_PROCESS_DETACH). This is not a claim of general multithreading compatibility. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <stdlib.h>
#include "xrt_internal.h"

__declspec(thread) XrtThread* xrt_cur;
uint32_t xrt_default_stack_reserve = 0x100000;

static SRWLOCK baton_lock = SRWLOCK_INIT;
static CONDITION_VARIABLE baton_cv = CONDITION_VARIABLE_INIT;
static uint64_t ticket_next, ticket_serving;
static volatile DWORD baton_owner;

volatile long xrt_preempt_req;
volatile long xrt_exiting;
static volatile long ticker_started;

static int baton_waiters(void) {
    return (int)(ticket_next - ticket_serving) - 1;   /* racy read: only used as a scheduling hint */
}

void xrt_preempt(CPU* c) {
    xrt_preempt_req = 0;
    if (xrt_exiting || baton_waiters() <= 0)
        return;
    c->thread->preemptions++;
    xrt_baton_release();
    xrt_baton_acquire();
}

static DWORD WINAPI ticker(void* unused) {
    (void)unused;
    timeBeginPeriod(1);
    while (!xrt_exiting) {
        Sleep(1);
        if (baton_waiters() > 0)
            xrt_preempt_req = 1;
    }
    return 0;
}

static XrtThread* threads[64];
static int nthreads;
static uint32_t stack_next = XRT_STACK_BASE;
static uint32_t peb;

void xrt_baton_acquire(void) {
    uint64_t mine;
    AcquireSRWLockExclusive(&baton_lock);
    mine = ticket_next++;
    while (mine != ticket_serving)
        SleepConditionVariableSRW(&baton_cv, &baton_lock, INFINITE, 0);
    baton_owner = GetCurrentThreadId();
    ReleaseSRWLockExclusive(&baton_lock);
}

void xrt_baton_release(void) {
    AcquireSRWLockExclusive(&baton_lock);
    if (baton_owner != GetCurrentThreadId())
        xrt_fatal(NULL, XRT_EXIT_SETUP, "baton released by a thread that does not hold it");
    baton_owner = 0;
    ticket_serving++;
    WakeAllConditionVariable(&baton_cv);
    ReleaseSRWLockExclusive(&baton_lock);
}

int xrt_thread_count(void) { return nthreads; }
XrtThread* xrt_thread_get(int i) { return i >= 0 && i < nthreads ? threads[i] : NULL; }

void xrt_set_last_error(CPU* c, uint32_t e) { wr32(c->fs_base + 0x34, e); }
uint32_t xrt_get_last_error(CPU* c) { return rd32(c->fs_base + 0x34); }

static XrtThread* new_thread(uint32_t reserve) {
    XrtThread* t = (XrtThread*)calloc(1, sizeof *t);
    uint32_t guard = 0x10000, teb;
    if (!t || nthreads == (int)(sizeof threads / sizeof threads[0]))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "cannot create guest thread record");
    reserve = (reserve + 0xFFFFu) & ~0xFFFFu;
    if ((uint64_t)stack_next + guard + reserve > XRT_STACK_END)
        xrt_fatal(NULL, XRT_EXIT_SETUP, "guest stack region exhausted");
    t->stack_lo = stack_next + guard;   /* the guard region below stays uncommitted: overflow faults */
    t->stack_hi = t->stack_lo + reserve;
    stack_next = t->stack_hi;
    xrt_commit(t->stack_lo, reserve);
    if (!peb) {
        peb = xrt_rt_alloc(0x1000, 0x1000);
        wr32(peb + 0x08, 0x00400000u);  /* ImageBaseAddress */
    }
    teb = xrt_rt_alloc(0x1000, 0x1000);
    wr32(teb + 0x00, 0xFFFFFFFFu);     /* ExceptionList: end of the SEH chain */
    wr32(teb + 0x04, t->stack_hi);     /* StackBase */
    wr32(teb + 0x08, t->stack_lo);     /* StackLimit */
    wr32(teb + 0x18, teb);             /* Self */
    wr32(teb + 0x20, GetCurrentProcessId());
    wr32(teb + 0x30, peb);
    t->teb = teb;
    t->cpu.r[ESP] = t->stack_hi - 16;
    t->cpu.fs_base = teb;
    t->cpu.fcw = 0x027F;               /* Windows' initial x87 control word (also observed in the reference) */
    t->cpu.thread = t;
    t->rand_seed = 1;
    t->index = nthreads;
    threads[nthreads++] = t;
    return t;
}

XrtThread* xrt_thread_main(uint32_t stack_reserve) {
    XrtThread* t = new_thread(stack_reserve);
    t->host_tid = t->guest_tid = GetCurrentThreadId();
    wr32(t->teb + 0x24, t->guest_tid);
    t->state = 1;
    xrt_cur = t;
    xrt_log("main guest thread: stack %08x-%08x teb %08x", t->stack_lo, t->stack_hi, t->teb);
    return t;
}

static DWORD WINAPI host_thread_proc(void* p) {
    XrtThread* t = (XrtThread*)p;
    CPU* c = &t->cpu;
    char d[512];
    xrt_cur = t;
    xrt_baton_acquire();
    t->state = 1;
    xrt_describe(d, sizeof d, t->start_va);
    xrt_log("thread %d running: guest entry %s, param %08x", t->index, d, t->param);
    if (setjmp(t->exit_jmp) == 0) {
        uint32_t arg = t->param;
        t->exit_code = xrt_call_guest(c, t->start_va, 1, &arg, 1);   /* LPTHREAD_START_ROUTINE is __stdcall */
        t->exit_via = 2;
    }
    t->state = 2;
    xrt_log("thread %d exited with code %u via %s after %llu Sleep calls (%llu contended critical sections, %llu preemptions)",
            t->index, t->exit_code, t->exit_via == 1 ? "ExitThread" : "return from its entry point", t->sleeps, t->cs_waits,
            t->preemptions);
    xrt_baton_release();
    return 0;
}

uint32_t xrt_thread_create(CPU* c, uint32_t stack_size, uint32_t start, uint32_t param, uint32_t* tid) {
    uint32_t reserve = xrt_default_stack_reserve;
    XrtThread* t;
    HANDLE h;
    DWORD htid;
    char d[512];
    if (stack_size > reserve)
        reserve = (stack_size + 0xFFFFFu) & ~0xFFFFFu;
    t = new_thread(reserve);
    t->start_va = start;
    t->param = param;
    /* translated code recurses on the host stack, so give host threads a generous reservation */
    if (!InterlockedExchange(&ticker_started, 1))
        CloseHandle(CreateThread(NULL, 0, ticker, NULL, 0, NULL));
    h = CreateThread(NULL, 64u << 20, host_thread_proc, t, CREATE_SUSPENDED | STACK_SIZE_PARAM_IS_A_RESERVATION, &htid);
    if (!h)
        xrt_fatal(c, XRT_EXIT_SETUP, "host CreateThread failed (%lu)", GetLastError());
    t->host_handle = h;
    t->host_tid = t->guest_tid = htid;
    wr32(t->teb + 0x24, htid);
    *tid = htid;
    xrt_describe(d, sizeof d, start);
    xrt_log("thread %d created by thread %d: entry %s param %08x guest stack %08x-%08x teb %08x", t->index,
            c->thread->index, d, param, t->stack_lo, t->stack_hi, t->teb);
    ResumeThread(h);
    return xrt_handle_new(XH_THREAD, h);
}

XRT_NORETURN void xrt_thread_exit(CPU* c, uint32_t code) {
    XrtThread* t = c->thread;
    if (t->index == 0)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "ExitThread on the main guest thread is not supported");
    t->exit_code = code;
    t->exit_via = 1;
    longjmp(t->exit_jmp, 1);
}
