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
    if (c->thread->loader_lock)
        return;                       /* DllMain notifications run under the loader lock: yield after them */
    xrt_preempt_req = 0;
    if (xrt_exiting || baton_waiters() <= 0)
        return;
    c->thread->preemptions++;
    xrt_baton_release();
    xrt_baton_acquire();
}

/* The 1 ms time slice is measured from the holder's acquisition (QPC); release resets it to "no holder",
 * so a waiter or the ticker never measures the previous holder's slice. */
static volatile LONGLONG baton_slice_start = MAXLONGLONG;
static LARGE_INTEGER baton_qpf;
static unsigned baton_ticker_requests;   /* diagnostic: preemption requests raised by the ticker */
static int baton_slice_expired(LONGLONG now) {
    return baton_qpf.QuadPart && now - baton_slice_start >= baton_qpf.QuadPart / 1000;
}

static DWORD WINAPI ticker(void* unused) {
    (void)unused;
    timeBeginPeriod(1);
    while (!xrt_exiting) {
        LARGE_INTEGER t;
        Sleep(1);
        QueryPerformanceCounter(&t);
        if (baton_waiters() > 0 && baton_slice_expired(t.QuadPart)) {
            if (!xrt_preempt_req) baton_ticker_requests++;
            xrt_preempt_req = 1;
        }
    }
    return 0;
}

static XrtThread* threads[64];
static int nthreads;
static uint32_t stack_next = XRT_STACK_BASE;
static uint32_t peb;

/* Hand-offs are frequent (time slices; Core's FFileStream worker polls with Sleep(1) ~1000 times a
 * second). A waiter first spins for up to XRT_BATON_SPIN_US, so the next ticket holder usually resumes
 * without a kernel wake-up; then it sleeps on the condition variable. The FIFO ticket order is unchanged,
 * and release wakes the condition variable only when a waiter actually sleeps on it. */
#define XRT_BATON_SPIN_US 2000
static unsigned baton_sleepers;
/* A spinning waiter requests preemption itself once the holder's slice has expired, instead of waiting
 * for the next ticker period (1-2 ms later). A new holder starts with no request pending: a request
 * raised during the hand-over was meant for the previous holder. */
/* Hand-over statistics per guest thread index (63: host threads without one), logged by
 * xrt_baton_stats_log: diagnostic only, updated under the baton lock or by the holder. */
static struct { uint64_t acquires, waits, wait_ticks, wait_max, cv_sleeps, hold_ticks, hold_max, requests; LONGLONG held_at; } baton_stats[64];
static unsigned baton_slot(void) { return xrt_cur && xrt_cur->index >= 0 && xrt_cur->index < 63 ? (unsigned)xrt_cur->index : 63; }
void xrt_baton_stats_log(FILE* also) {
    unsigned i;
    double ms = baton_qpf.QuadPart ? 1000.0 / (double)baton_qpf.QuadPart : 0;
    xrt_log("baton stats: ticker requests %u", baton_ticker_requests);
    if (also) fprintf(also, "# baton ticker_requests=%u\n", baton_ticker_requests);
    for (i = 0; i < 64; i++)
        if (baton_stats[i].acquires) {
            xrt_log("baton stats thread %u: acquires %llu, waited %llu (%.1f ms total, max %.3f ms, %llu condition-variable sleeps), "
                    "held %.1f ms total (max %.3f ms), preemption requests raised while waiting %llu", i,
                    baton_stats[i].acquires, baton_stats[i].waits, baton_stats[i].wait_ticks * ms, baton_stats[i].wait_max * ms,
                    baton_stats[i].cv_sleeps, baton_stats[i].hold_ticks * ms, baton_stats[i].hold_max * ms, baton_stats[i].requests);
            if (also)
                fprintf(also, "# baton thread=%u acquires=%llu waits=%llu wait_ms=%.1f wait_max_ms=%.3f cv_sleeps=%llu held_ms=%.1f "
                        "held_max_ms=%.3f requests=%llu\n", i, baton_stats[i].acquires, baton_stats[i].waits,
                        baton_stats[i].wait_ticks * ms, baton_stats[i].wait_max * ms, baton_stats[i].cv_sleeps,
                        baton_stats[i].hold_ticks * ms, baton_stats[i].hold_max * ms, baton_stats[i].requests);
        }
}
void xrt_baton_acquire(void) {
    uint64_t mine;
    unsigned slot = baton_slot();
    int requested = 0;
    LARGE_INTEGER f, t0, t;
    AcquireSRWLockExclusive(&baton_lock);
    mine = ticket_next++;
    if (!baton_qpf.QuadPart)
        QueryPerformanceFrequency(&baton_qpf);
    f = baton_qpf;
    if (mine != ticket_serving) {
        unsigned n = 0;
        ReleaseSRWLockExclusive(&baton_lock);
        QueryPerformanceCounter(&t0);
        t = t0;
        while (*(volatile uint64_t*)&ticket_serving != mine) {
            if (baton_slice_expired(t.QuadPart)) {
                if (!xrt_preempt_req && !requested) { requested = 1; baton_stats[slot].requests++; }
                xrt_preempt_req = 1;
            }
            YieldProcessor();
            if (!(++n & 63)) {
                QueryPerformanceCounter(&t);
                if ((uint64_t)(t.QuadPart - t0.QuadPart) * 1000000u >= (uint64_t)f.QuadPart * XRT_BATON_SPIN_US)
                    break;
            }
        }
        AcquireSRWLockExclusive(&baton_lock);
        while (mine != ticket_serving) {
            baton_sleepers++;
            baton_stats[slot].cv_sleeps++;
            SleepConditionVariableSRW(&baton_cv, &baton_lock, INFINITE, 0);
            baton_sleepers--;
        }
        QueryPerformanceCounter(&t);
        baton_stats[slot].waits++;
        baton_stats[slot].wait_ticks += (uint64_t)(t.QuadPart - t0.QuadPart);
        if ((uint64_t)(t.QuadPart - t0.QuadPart) > baton_stats[slot].wait_max)
            baton_stats[slot].wait_max = (uint64_t)(t.QuadPart - t0.QuadPart);
    }
    QueryPerformanceCounter(&t);
    baton_stats[slot].acquires++;
    baton_stats[slot].held_at = t.QuadPart;
    baton_slice_start = t.QuadPart;
    xrt_preempt_req = 0;
    baton_owner = GetCurrentThreadId();
    ReleaseSRWLockExclusive(&baton_lock);
}

void xrt_baton_release(void) {
    if (xrt_cur && xrt_cur->loader_lock && xrt_cur->state == 1)
        xrt_fatal(&xrt_cur->cpu, XRT_EXIT_UNSUPPORTED, "blocking call while thread %d holds the loader lock (inside "
                  "DllMain or LoadLibrary): not modelled", xrt_cur->index);
    AcquireSRWLockExclusive(&baton_lock);
    if (baton_owner != GetCurrentThreadId())
        xrt_fatal(NULL, XRT_EXIT_SETUP, "baton released by a thread that does not hold it");
    {
        LARGE_INTEGER t; unsigned slot = baton_slot(); uint64_t held;
        QueryPerformanceCounter(&t);
        held = (uint64_t)(t.QuadPart - baton_stats[slot].held_at);
        baton_stats[slot].hold_ticks += held;
        if (held > baton_stats[slot].hold_max) baton_stats[slot].hold_max = held;
    }
    baton_owner = 0;
    baton_slice_start = MAXLONGLONG;
    ticket_serving++;
    if (baton_sleepers)
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
    for (;;) {                          /* keep stacks out of every translated module's image range */
        uint32_t end;
        if ((uint64_t)stack_next + guard + reserve > XRT_STACK_END)
            xrt_fatal(NULL, XRT_EXIT_SETUP, "guest stack region exhausted");
        if (!xrt_lifted_overlap(stack_next, guard + reserve, &end))
            break;
        stack_next = (end + 0xFFFFu) & ~0xFFFFu;
    }
    t->stack_lo = stack_next + guard;   /* the guard region below stays uncommitted: overflow faults */
    t->stack_hi = t->stack_lo + reserve;
    stack_next = t->stack_hi;
    xrt_commit(t->stack_lo, reserve);
    if (!peb) {
        peb = xrt_rt_alloc(0x1000, 0x1000);
        wr32(peb + 0x08, xrt_module_get(0)->base);  /* ImageBaseAddress of the actual mapped executable */
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
    xrt_event("thread_start", "\"index\": %d, \"entry\": \"0x%08x\"", t->index, t->start_va);
    xrt_dll_thread_notify(c, 2);                                      /* DLL_THREAD_ATTACH */
    if (setjmp(t->exit_jmp) == 0) {
        uint32_t arg = t->param;
        t->exit_code = xrt_call_guest(c, t->start_va, 1, &arg, 1);   /* LPTHREAD_START_ROUTINE is __stdcall */
        t->exit_via = 2;
    }
    if (!xrt_exiting)
        xrt_dll_thread_notify(c, 3);                                  /* DLL_THREAD_DETACH, on this thread */
    xrt_com_thread_cleanup(c);
    t->state = 2;
    xrt_log("thread %d exited with code %u via %s after %llu Sleep calls (%llu contended critical sections, %llu preemptions)",
            t->index, t->exit_code, t->exit_via == 1 ? "ExitThread" : "return from its entry point", t->sleeps, t->cs_waits,
            t->preemptions);
    xrt_event("thread_end", "\"index\": %d, \"code\": %u, \"via\": \"%s\"", t->index, t->exit_code,
              t->exit_via == 1 ? "ExitThread" : "return");
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
    xrt_event("thread_create", "\"index\": %d, \"entry\": \"0x%08x\", \"param\": \"0x%08x\"", t->index, start, param);
    ResumeThread(h);
    return xrt_handle_new(XH_THREAD, h);
}

XRT_NORETURN void xrt_thread_exit(CPU* c, uint32_t code) {
    XrtThread* t = c->thread;
    if (t->index == 0)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "ExitThread on the main guest thread is not supported");
    if(t->host_calls>1)xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"ExitThread through nested native callback is unqualified");
    t->exit_code = code;
    t->exit_via = 1;
    xm_unwind(c,0,3);
    longjmp(t->exit_jmp, 1);
}

/* Runtime-owned guest thread for native components that call guest code from their own
 * threads (DirectMusic tool callbacks). Like a guest CreateThread thread it has a real host
 * thread, its own guest stack/TEB and DLL_THREAD_ATTACH, but no guest handle. The body runs
 * without the baton and acquires it only around guest execution. Called with the baton held. */
typedef struct { XrtThread* t; void (*body)(CPU*, void*); void* arg; } ServiceStart;
static DWORD WINAPI service_proc(void* p) {
    ServiceStart s = *(ServiceStart*)p;
    free(p);
    xrt_cur = s.t;
    xrt_baton_acquire();
    s.t->state = 1;
    xrt_dll_thread_notify(&s.t->cpu, 2);                              /* DLL_THREAD_ATTACH */
    xrt_baton_release();
    s.body(&s.t->cpu, s.arg);
    return 0;
}
void xrt_thread_service(CPU* c, const char* name, void (*body)(CPU*, void*), void* arg) {
    ServiceStart* s = (ServiceStart*)calloc(1, sizeof *s);
    HANDLE h;
    DWORD htid;
    if (!s)
        xrt_fatal(c, XRT_EXIT_SETUP, "service thread allocation");
    s->t = new_thread(xrt_default_stack_reserve);
    s->body = body;
    s->arg = arg;
    if (!InterlockedExchange(&ticker_started, 1))
        CloseHandle(CreateThread(NULL, 0, ticker, NULL, 0, NULL));
    h = CreateThread(NULL, 64u << 20, service_proc, s, CREATE_SUSPENDED | STACK_SIZE_PARAM_IS_A_RESERVATION, &htid);
    if (!h)
        xrt_fatal(c, XRT_EXIT_SETUP, "host CreateThread failed (%lu)", GetLastError());
    s->t->host_handle = h;
    s->t->host_tid = s->t->guest_tid = htid;
    wr32(s->t->teb + 0x24, htid);
    xrt_log("runtime service thread %d (%s): guest stack %08x-%08x teb %08x", s->t->index, name, s->t->stack_lo,
            s->t->stack_hi, s->t->teb);
    xrt_event("thread_service", "\"index\": %d, \"name\": \"%s\"", s->t->index, name);
    ResumeThread(h);
}
