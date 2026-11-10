/* xrt_internal.h - declarations shared by the runtime's host-side components (not by generated code). */
#ifndef XRT_INTERNAL_H
#define XRT_INTERNAL_H
#include <setjmp.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include "xrt.h"
#include "monitor.h"

struct XrtModule;

/* ---------------------------------------------------------------- guest address-space layout
 * 0x00000000-0x0000FFFF  never mapped (guest null-pointer accesses fault and are diagnosed)
 * 0x00010000-0x002FFFFF  runtime data: TEBs, PEB, command line, argv, CRT data objects
 * 0x00300000-0x0033FFFF  import stubs: guest addresses that dispatch to host adapters; reserved but never
 *                        committed, so reading data through a function import faults visibly
 * 0x00400000-...         UCC.exe image (preferred base)
 * 0x01000000-0x0FFFFFFF  guest thread stacks (each with an uncommitted guard region below it); stacks skip the
 *                        range of every linked translated module, mapped yet or not (Editor.dll is lifted for
 *                        0x02de0000 and GlmLib.dll for 0x02f40000, where the original's `ucc make` rebases them;
 *                        GlmLib's plugin plugins\UnrImp.gpi for 0x036d0000 and Fire.dll for 0x03710000, where one
 *                        of its runs loaded them)
 * 0x10100000-...         Core.dll image (preferred base); Engine.dll at its preferred base 0x10300000;
 *                        Window.dll at its preferred base 0x11000000
 * 0x12000000-0x1FFFFFFF  guest VirtualAlloc pool, first segment (client; lifted images inside it are skipped)
 * 0x20000000-0x5FFFFFFF  guest heap (malloc/realloc/free, HeapAlloc); the game peaks near 50 MB
 * 0x60000000-0x7FEFFFFF  guest VirtualAlloc pool, second segment (beta batch: the 224 MB first segment fragmented
 *                        in long sessions; the original non large-address-aware process had all of its 2 GB)
 * System module handles are typed opaque tokens backed by owned host loader references. They are not images. */
#define XRT_RT_BASE 0x00010000u
#define XRT_RT_END 0x00300000u
#define XRT_STUB_BASE 0x00300000u
#define XRT_STUB_END 0x00340000u
#define XRT_STUB_SIZE 16u
#define XRT_HOST_RETURN (XRT_STUB_END - XRT_STUB_SIZE)   /* sentinel return address for host->guest calls */
#define XRT_STACK_BASE 0x01000000u
#define XRT_STACK_END 0x10000000u
#define XRT_POOL_BASE 0x12000000u
#define XRT_POOL_END 0x20000000u
#define XRT_HEAP_BASE 0x20000000u
#define XRT_HEAP_END 0x60000000u
#define XRT_POOL2_BASE 0x60000000u
#define XRT_POOL2_END 0x7FF00000u
#define XRT_MAX_MODULES 32 /* Includes unloaded slots; client packages exceed the old eight-module limit. */

/* exit codes used by the runtime itself (guest exit codes are passed through unchanged) */
enum { XRT_EXIT_TRAP = 71, XRT_EXIT_BADRET = 72, XRT_EXIT_DIV0 = 73, XRT_EXIT_FAULT = 74, XRT_EXIT_IMPORT = 75,
       XRT_EXIT_UNSUPPORTED = 76, XRT_EXIT_SETUP = 77 };

/* ---------------------------------------------------------------- memory (xrt_mem.c) */
void xrt_mem_init(void);
void xrt_commit(uint32_t a, uint32_t size);
int xrt_is_committed(uint32_t a, uint32_t size);
int xrt_range_is_free(uint32_t a, uint32_t size);           /* no page of the range committed */
void xrt_decommit(uint32_t a, uint32_t size);
uint32_t xrt_staging_take(CPU* c, uint32_t size);   /* developer D3D8 staging reuse: a warm block of this size class */
int xrt_staging_put(CPU* c, uint32_t base);         /* keeps the block committed for the next staging take */
uint32_t xrt_rt_alloc(uint32_t size, uint32_t align);       /* runtime region, zeroed, never freed */
uint32_t xrt_heap_alloc(uint32_t size);                      /* 0 on exhaustion */
void xrt_heap_free(CPU* c, uint32_t p);
uint32_t xrt_heap_realloc(CPU* c, uint32_t p, uint32_t size);
uint32_t xrt_heap_msize(CPU* c, uint32_t p);
void xrt_heap_stats(uint64_t* allocs, uint64_t* frees, uint64_t* bytes_live, uint32_t* high_water);
uint32_t xrt_virtual_alloc(CPU* c, uint32_t size);
int xrt_virtual_free(CPU* c, uint32_t base);
typedef struct { uint32_t blocks, live_blocks, bump_next, bump_high, reclaims, splits, largest_free;
                 uint64_t live_reserved, free_reserved, staging_reserved; } XrtPoolStats;
void xrt_virtual_stats(XrtPoolStats* s);                     /* guest VirtualAlloc pool, for the runtime report */
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
int xrt_event_room(void);                                    /* 0 once further events would only be counted */
extern volatile long xrt_mem_generation;                     /* bumped before guest pages are decommitted */
int xrt_mem_hint_valid(uint64_t lo, uint64_t hi, long* gen); /* range checked under *gen not decommitted since */
uint32_t xrt_staging_guard_take(CPU* c, uint32_t size);   /* guard staging: re-open a guarded block (xrt_mem.c) */
int xrt_staging_guard_put(CPU* c, uint32_t base);          /* guard staging: close a block (PAGE_NOACCESS) */
void xrt_hint_committed(uint32_t a, uint32_t size);          /* this thread just committed [a, a+size) read-write */
void xrt_event_skip(void);   /* the event timeline is full: count an event as xrt_event would, without formatting it */
const char* xrt_jstr(char* out, size_t n, const char* s);   /* quoted, escaped JSON string in out */
void xrt_watches_arm(void);                                  /* after the modules are mapped */
void xrt_watches_arm_module(struct XrtModule* m);            /* a module mapped later (LoadLibrary) */
void xrt_watches_check(CPU* c, const char* import, uint32_t site);
void xrt_events_report(FILE* f);

/* ---------------------------------------------------------------- threads (xrt_thread.c) */
struct XrtThread {
    CPU cpu;
    int host_calls;                /* nesting of host->guest calls (xrt_call_guest) on this thread */
    XrtEhPad* eh_pads;             /* landing stack of the C++ exception dispatcher (innermost first) */
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
    struct XrtEhCatch* eh_catches; /* catch blocks currently executing (innermost first) */
    int eh_unwinding;              /* > 0 while the dispatcher runs unwind actions (a throw then is terminate()) */
    int loader_lock;               /* > 0 while this thread runs DllMain notifications (no baton hand-over) */
    unsigned com_initializations;  /* successful guest COM initializations owned by this host thread */
};
extern __declspec(thread) XrtThread* xrt_cur;
#ifdef XRT_EH_FRAMES   /* xrt.h XrtThreadEh mirrors this prefix for the inline pad link/unlink */
_Static_assert(offsetof(XrtThread, host_calls) == offsetof(XrtThreadEh, host_calls) &&
               offsetof(XrtThread, eh_pads) == offsetof(XrtThreadEh, eh_pads), "XrtThreadEh prefix");
#endif
void xrt_com_thread_cleanup(CPU* c); /* owning thread only; Loader8 references before apartment balance */
extern volatile long xrt_exiting;          /* set when ExitProcess starts: no more baton hand-overs */
void xrt_baton_acquire(void);
void xrt_baton_release(void);
void xrt_baton_stats_log(FILE* also);     /* hand-over statistics to the log, and to also when not NULL (diagnostic) */
void xrt_thread_service(CPU* c, const char* name, void (*body)(CPU*, void*), void* arg); /* runtime-owned guest thread */
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
    uint32_t preferred_base;       /* ImageBase in the file; differs from base for a rebased lift */
    int is_dll, attached;
    int load_count;                /* LoadLibrary references; -1: loaded with the process (never unloaded) */
    int unloaded;                  /* unmapped by FreeLibrary (slot kept for the report; reused if loaded again) */
    uint32_t generation;           /* distinguish successive mappings in the same slot/base */
    const XrtLiftedModule* lifted;
    uint32_t export_dir, export_dir_size;
    int no_thread_calls;           /* DisableThreadLibraryCalls: no DLL_THREAD_ATTACH/DETACH for this mapping */
} XrtModule;

typedef struct XrtHle {
    const char* dll;               /* lower-case, e.g. "kernel32.dll" */
    const char* name;
    XrtFn fn;                      /* function adapter (NULL for data objects) */
    uint32_t data_size;            /* data object size in guest memory (fn == NULL) */
} XrtHle;
extern const XrtHle xrt_hle_kernel32[], xrt_hle_msvcr70[], xrt_hle_misc[], xrt_hle_gui[], xrt_hle_openal[];   /* each ends with {0} */

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
/* port_settings.c: walking speed / UI scale; dispatch hands it the calls flagged CALL_PORT_* (1 = completed there) */
int xrt_port_call(CPU* c, unsigned kind, XrtLiftedFn fn);
int xrt_d3d8_borderless_window(void* hwnd);   /* d3d8_borderless.inc: this window shows borderless fullscreen now */
float xrt_port_walking_speed(void);
/* port_settings.c: field of view, Hor+, frame limit, VSync, script tick ceiling (see that file) */
int xrt_port_field_of_view(void);
int xrt_port_hor_plus(void);
int xrt_port_frame_limit(void);
int xrt_port_vsync(void);
int xrt_port_vsync_reset_due(void);
int xrt_port_script_tick_rate(void);
void xrt_port_set(int key, int value, const char* source);
/* dev_support.c: the frame rate limiter (0 = unlimited, i.e. only the engine's 1 ms time-step floor) */
void xrt_dev_frame_limit(unsigned fps, const char* source);
void xrt_dev_dmusic_kill(void);   /* dmusic_backend_pipe.inc: developer test hook (input step dmkill) */
void xrt_world_enter(CPU* c, uint32_t target);
extern int xrt_scene_level_depth,xrt_scene_camera_depth;extern unsigned xrt_scene_level_renders,xrt_scene_camera_renders,xrt_scene_engine_ticks,xrt_scene_level_ticks;
/* Developer first-scene mode (dev_support.c). */
int xrt_dev_scene_capture(unsigned level_renders,unsigned scene_draws);
void xrt_dev_scene_frame(unsigned frame,unsigned width,unsigned height,unsigned format,const void*bits,int pitch);
void xrt_dev_map_open(CPU*c,const char*path);
int xrt_dev_draw_dump(void);
void xrt_dev_music_cue(const unsigned short*text);
int xrt_dev_input_blocked(const char*what);
int xrt_dev_background(void);
void xrt_dev_input_tick(void);
void xrt_dev_input_window_actions(void);
void xrt_dev_view(const unsigned int bits[16]);
void xrt_dev_input_window(void*hwnd);
int xrt_dev_input_allowed(void*hwnd,unsigned msg,unsigned long long wp,long long lp);
int xrt_dev_input_mouse(unsigned*ofs,unsigned*data);
int xrt_dev_key_held(unsigned vk);
void xrt_dev_cursor(int op,long*x,long*y,const void*r);
void xrt_dev_scene_present(CPU*c,long hr,unsigned draws,unsigned prims,unsigned scene_draws,unsigned scene_prims,unsigned level_draws);
void xrt_world_return(CPU* c);
uint32_t xrt_call_funclet(CPU* c, uint32_t va);   /* EH funclet call: no args, not a host boundary */
uint32_t xrt_call_continuation(CPU* c, uint32_t va, uint32_t expected_return);  /* run code at va until it returns */
uint32_t xrt_hle_data(const char* dll, const char* name);  /* guest address of an HLE data object */
uint32_t xrt_hle_proc(const char* dll, const char* name);  /* stub address of a host adapter, 0 if there is none */
uint32_t xrt_hle_export_proc(const char* dll, const char* name); /* proven export: adapter or explicit call trap */
void xrt_system_import(const char* name, int delta);      /* guest PE import reference, including unload */
int xrt_system_export_live(const char* name);
void xrt_module_unmap(XrtModule* m);                       /* FreeLibrary's unmapping, after DLL_PROCESS_DETACH */
void xrt_imports_report(FILE* f);
void xrt_sites_enable(const char* names);   /* comma-separated substrings of "dll!function" */
void xrt_sites_report(FILE* f);
void xrt_watch_add(uint32_t guest_addr);
const char* xrt_stub_name(uint32_t va);

/* process model: translated modules linked into this host and the Windows loader's behaviour (xrt_main.c) */
const XrtLiftedModule* xrt_lifted_find(const char* name);  /* by file name, case-insensitive, ".dll" optional */
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end);   /* range meets a linked module's image range */
XrtModule* xrt_load_library(CPU* c, const char* host_path); /* LoadLibrary of a translated DLL; NULL if not translated */
int xrt_free_library(CPU* c, XrtModule* m);                 /* FreeLibrary of a mapped module */
void xrt_dll_thread_notify(CPU* c, uint32_t reason);        /* DLL_THREAD_ATTACH / DLL_THREAD_DETACH on this thread */

/* ---------------------------------------------------------------- host adapters (hle_*.c) */
#define ARG(i) rd32(c->r[ESP] + 4u + 4u * (i))
#define RET_STD(nargs, v) do { uint32_t v__ = (uint32_t)(v); c->r[EAX] = v__; c->rv = pop32(c); c->r[ESP] += 4u * (nargs); } while (0)
#define RET_C(v) do { uint32_t v__ = (uint32_t)(v); c->r[EAX] = v__; c->rv = pop32(c); } while (0)
#define RET_C_VOID() do { c->rv = pop32(c); } while (0)
void xrt_set_last_error(CPU* c, uint32_t e);
uint32_t xrt_get_last_error(CPU* c);

/* handles: guest handle values for host objects */
enum { XH_FREE, XH_FILE, XH_FIND, XH_THREAD, XH_STD, XH_DC, XH_BITMAP, XH_WINDOW, XH_FONT, XH_MODULE, XH_MUTEX, XH_IMC,
       XH_FINDLIST }; /* host objects behind guest tokens (XH_FINDLIST: a merged content-overlay directory listing) */
uint32_t xrt_handle_new(int type, void* host);
void* xrt_handle_get(uint32_t h, int type);
int xrt_handle_type(uint32_t h);
void xrt_handle_free(uint32_t h);
/* GUI module identity conversion: system tokens only, never guest PE execution. */
void* xrt_system_module_host(CPU* c, uint32_t token);
uint32_t xrt_system_module_guest(CPU* c, void* host);
uint32_t xrt_system_gui_owner(CPU* c, const char* name);
uint32_t xrt_system_module_generation(CPU* c,uint32_t token);
void xrt_cleanup_atoms(void);
void xrt_cleanup_register(void (*fn)(void)); /* owned host resources, also on handled fatal stops */
void xrt_cleanup_input_settings(void); /* timeout watchdog: no concurrent COM Release */
/* Scoped synchronous callbacks and owned window identities for native D3D8. */
CPU* xrt_gui_callback_enter(CPU* c);
void xrt_gui_callback_leave(CPU* previous);
void* xrt_gui_device_window(CPU* c,uint32_t token);
uint32_t xrt_gui_window_identity(CPU* c,void* host);
void xrt_gui_window_pin(CPU* c,uint32_t token);
void xrt_gui_window_unpin(uint32_t token);
int xrt_gui_window_destroyed(uint32_t token);   /* destroyed by the guest while a D3D8 device still held it */

/* process */
extern char xrt_sandbox_root[520];         /* writes are only permitted below this directory */
/* Standalone player (tools/xrt/dev/player.c; empty/0 in the developer build): the game root above is the player's private
 * data folder and xrt_content_root the user's Unreal II installation (its singleplayer folder), read-only. A read of a
 * file the game root does not have resolves to the same relative path in the content root (never ...\Save), and
 * directory listings merge both (the game root wins). Every write stays confined to the game root. */
extern char xrt_content_root[520];
extern int xrt_player_mode;
int xrt_overlay_read_path(const uint16_t* path, uint16_t* out, size_t n);   /* 1: out = the content-root path to read */
int xrt_overlay_content_dir(const uint16_t* path, uint16_t* out, size_t n); /* 1: out = the content root's same folder */
void* xrt_overlay_find_first(const uint16_t* pattern);                     /* NULL: not overlaid (use the host's find) */
int xrt_overlay_find_next(void* list, void* find_data_w);                  /* WIN32_FIND_DATAW; 0 at the end */
void xrt_overlay_find_close(void* list);
extern uint32_t xrt_cmdline_a;             /* guest ANSI command line */
extern uint32_t xrt_cmdline_w;             /* guest Unicode command line, preserving raw host argument text */
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
int32_t xrt_output(uint32_t fmt, uint32_t va, int (*put)(void* ctx, uint16_t ch), void* ctx);    /* msvcr70 _output (narrow) */
void xrt_ld12_multtenpow12(uint16_t w[6], int pw);   /* msvcr70 __multtenpow12(x, pw, 1), |pw| < 512 */

/* msvcr70 code run translated (xrt_msvcr70img.c, gen/msvcr70/) */
double xrt_msvcr70_pow(CPU* c, double x, double y, uint32_t* error_type);   /* _CIpow's SSE2 path */
const uint8_t* xrt_msvcr70_image(void);   /* the SHA-checked msvcr70.dll image (preferred-base layout), as data */
#endif
