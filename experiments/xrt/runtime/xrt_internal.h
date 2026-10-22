/* xrt_internal.h - declarations shared by the runtime's host-side components (not by generated code). */
#ifndef XRT_INTERNAL_H
#define XRT_INTERNAL_H
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include "xrt.h"

/* ---------------------------------------------------------------- guest address-space layout
 * 0x00000000-0x0000FFFF  never mapped (guest null-pointer accesses fault and are diagnosed)
 * 0x00010000-0x002FFFFF  runtime data: TEBs, PEB, command line, argv, CRT data objects
 * 0x00300000-0x0033FFFF  import stubs: guest addresses that dispatch to host adapters; reserved but never
 *                        committed, so reading data through a function import faults visibly
 * 0x00400000-...         UCC.exe image (preferred base)
 * 0x01000000-0x0FFFFFFF  guest thread stacks (each with an uncommitted guard region below it)
 * 0x10100000-...         Core.dll image (preferred base)
 * 0x20000000-0x7FEFFFFF  guest heap (malloc/realloc/free); stays below 2 GB like the original
 *                        (non large-address-aware) process */
#define XRT_RT_BASE 0x00010000u
#define XRT_RT_END 0x00300000u
#define XRT_STUB_BASE 0x00300000u
#define XRT_STUB_END 0x00340000u
#define XRT_STUB_SIZE 16u
#define XRT_HOST_RETURN (XRT_STUB_END - XRT_STUB_SIZE)   /* sentinel return address for host->guest calls */
#define XRT_STACK_BASE 0x01000000u
#define XRT_STACK_END 0x10000000u
#define XRT_HEAP_BASE 0x20000000u
#define XRT_HEAP_END 0x7FF00000u

/* exit codes used by the runtime itself (guest exit codes are passed through unchanged) */
enum { XRT_EXIT_TRAP = 71, XRT_EXIT_BADRET = 72, XRT_EXIT_DIV0 = 73, XRT_EXIT_FAULT = 74, XRT_EXIT_IMPORT = 75,
       XRT_EXIT_UNSUPPORTED = 76, XRT_EXIT_SETUP = 77 };

/* ---------------------------------------------------------------- memory (xrt_mem.c) */
void xrt_mem_init(void);
void xrt_commit(uint32_t a, uint32_t size);
int xrt_is_committed(uint32_t a, uint32_t size);
uint32_t xrt_rt_alloc(uint32_t size, uint32_t align);       /* runtime region, zeroed, never freed */
uint32_t xrt_heap_alloc(uint32_t size);                      /* 0 on exhaustion */
void xrt_heap_free(CPU* c, uint32_t p);
uint32_t xrt_heap_realloc(CPU* c, uint32_t p, uint32_t size);
uint32_t xrt_heap_msize(CPU* c, uint32_t p);
void xrt_heap_stats(uint64_t* allocs, uint64_t* frees, uint64_t* bytes_live, uint32_t* high_water);
uint32_t xrt_guest_strdup_a(const char* s);                  /* into the runtime region */
uint32_t xrt_guest_strlen16(uint32_t p);

/* ---------------------------------------------------------------- diagnostics (xrt_diag.c) */
void xrt_diag_init(const char* log_path);
void xrt_log(const char* fmt, ...);                          /* bounded runtime event log */
XRT_NORETURN void xrt_fatal(CPU* c, int code, const char* fmt, ...);
void xrt_describe(char* out, size_t n, uint32_t va);         /* module+rva [export] */
extern volatile long xrt_dying;

/* ---------------------------------------------------------------- evidence timeline (xrt_events.c) */
void xrt_events_init(void);
void xrt_event(const char* kind, const char* fmt, ...);     /* fmt: further JSON members, may be NULL */
const char* xrt_jstr(char* out, size_t n, const char* s);   /* quoted, escaped JSON string in out */
void xrt_watches_arm(void);                                  /* after the modules are mapped */
void xrt_watches_check(CPU* c, const char* import, uint32_t site);
void xrt_events_report(FILE* f);

/* ---------------------------------------------------------------- threads (xrt_thread.c) */
struct XrtThread {
    CPU cpu;
    int index;                     /* 0 = main thread */
    uint32_t guest_tid, host_tid;
    void* host_handle;
    uint32_t teb, stack_lo, stack_hi;
    uint32_t start_va, param;
    uint32_t exit_code;
    volatile long state;           /* 0 created, 1 running, 2 exited */
    jmp_buf exit_jmp;
    uint32_t rand_seed;            /* msvcr70 per-thread rand() state */
    uint64_t sleeps, preemptions, cs_waits;
    uint32_t exit_via;             /* 1 ExitThread, 2 returned from entry */
    int host_calls;                /* nesting of host->guest calls (xrt_call_guest) on this thread */
    XrtEhPad* eh_pads;             /* landing stack of the C++ exception dispatcher (innermost first) */
    struct XrtEhCatch* eh_catches; /* catch blocks currently executing (innermost first) */
    int eh_unwinding;              /* > 0 while the dispatcher runs unwind actions (a throw then is terminate()) */
};
extern __declspec(thread) XrtThread* xrt_cur;
extern volatile long xrt_exiting;          /* set when ExitProcess starts: no more baton hand-overs */
void xrt_baton_acquire(void);
void xrt_baton_release(void);
XrtThread* xrt_thread_main(uint32_t stack_reserve);
uint32_t xrt_thread_create(CPU* c, uint32_t stack_size, uint32_t start, uint32_t param, uint32_t* tid);
XRT_NORETURN void xrt_thread_exit(CPU* c, uint32_t code);
int xrt_thread_count(void);
XrtThread* xrt_thread_get(int i);
extern uint32_t xrt_default_stack_reserve;

/* ---------------------------------------------------------------- modules, imports, dispatch (xrt_loader.c) */
typedef struct XrtModule {
    char name[64];
    char path[520];                /* host path of the original file (also what GetModuleFileName reports) */
    uint32_t base, size, entry;
    int is_dll, attached;
    const XrtLiftedModule* lifted;
    uint32_t export_dir, export_dir_size;
} XrtModule;

typedef struct XrtHle {
    const char* dll;               /* lower-case, e.g. "kernel32.dll" */
    const char* name;
    XrtFn fn;                      /* function adapter (NULL for data objects) */
    uint32_t data_size;            /* data object size in guest memory (fn == NULL) */
} XrtHle;
extern const XrtHle xrt_hle_kernel32[], xrt_hle_msvcr70[], xrt_hle_misc[];   /* each ends with {0} */

int xrt_module_count(void);
XrtModule* xrt_module_get(int i);
XrtModule* xrt_module_load(const char* host_path, const XrtLiftedModule* lifted);
void xrt_module_bind_imports(XrtModule* m);
XrtModule* xrt_module_by_name(const char* name);           /* case-insensitive, ".dll" optional */
XrtModule* xrt_module_by_addr(uint32_t va);
uint32_t xrt_module_export(XrtModule* m, const char* name, uint32_t ordinal);
XrtFn xrt_lookup(uint32_t va, const char** stub_name);
uint32_t xrt_lookup_containing(uint32_t va);                /* lifted function entry at or below va */
uint32_t xrt_call_guest(CPU* c, uint32_t va, int nargs, const uint32_t* args, int stdcall);
uint32_t xrt_call_funclet(CPU* c, uint32_t va);   /* EH funclet call: no args, not a host boundary */
uint32_t xrt_call_continuation(CPU* c, uint32_t va, uint32_t expected_return);  /* run code at va until it returns */
uint32_t xrt_hle_data(const char* dll, const char* name);  /* guest address of an HLE data object */
void xrt_imports_report(FILE* f);
void xrt_sites_enable(const char* names);   /* comma-separated substrings of "dll!function" */
void xrt_sites_report(FILE* f);
void xrt_watch_add(uint32_t guest_addr);
const char* xrt_stub_name(uint32_t va);

/* ---------------------------------------------------------------- host adapters (hle_*.c) */
#define ARG(i) rd32(c->r[ESP] + 4u + 4u * (i))
#define RET_STD(nargs, v) do { uint32_t v__ = (uint32_t)(v); c->r[EAX] = v__; c->rv = pop32(c); c->r[ESP] += 4u * (nargs); } while (0)
#define RET_C(v) do { uint32_t v__ = (uint32_t)(v); c->r[EAX] = v__; c->rv = pop32(c); } while (0)
#define RET_C_VOID() do { c->rv = pop32(c); } while (0)
void xrt_set_last_error(CPU* c, uint32_t e);
uint32_t xrt_get_last_error(CPU* c);

/* handles: guest handle values for host objects */
enum { XH_FREE, XH_FILE, XH_FIND, XH_THREAD };
uint32_t xrt_handle_new(int type, void* host);
void* xrt_handle_get(uint32_t h, int type);
int xrt_handle_type(uint32_t h);
void xrt_handle_free(uint32_t h);

/* process */
extern char xrt_sandbox_root[520];         /* writes are only permitted below this directory */
extern uint32_t xrt_cmdline_a;             /* guest ANSI command line */
extern const char* xrt_report_path;
void xrt_report_write(uint32_t exit_code, const char* outcome);
const char* xrt_export_name_at(uint32_t va);   /* exact export at va, or NULL */
XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code);
void xrt_stdout_write(const uint16_t* s, size_t n);
void xrt_stdout_flush(void);
int xrt_path_is_inside_sandbox(const uint16_t* path);

/* C++ exceptions (xrt_eh.c) */
void xrt_eh_throw(CPU* c);                 /* the _CxxThrowException adapter */
void xrt_eh_report(FILE* f);               /* statistics for the runtime report */

/* formatter (xrt_fmt.c): msvcr70-compatible wide printf over guest varargs */
uint16_t* xrt_wformat(uint32_t fmt, uint32_t va, size_t* len);   /* malloc'ed, not terminated */
int32_t xrt_woutput(uint32_t fmt, uint32_t va, int (*put)(void* ctx, uint16_t ch), void* ctx);   /* msvcr70 _woutput over a sink */
#endif
