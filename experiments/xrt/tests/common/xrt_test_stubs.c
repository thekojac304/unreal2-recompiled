/* Stubs for runtime symbols that adapter-level test harnesses do not exercise. Each harness compiles this file
 * with the STUB_* switches for the symbols it does not already define or link:
 *   STUB_EVENT  xrt_event (evidence timeline, xrt_events.c): ignored
 *   STUB_JSTR   xrt_jstr: a real JSON quoting, since callers use its result as text
 *   STUB_EH     xrt_eh_throw (C++ exception dispatch, xrt_eh.c): fatal, because no harness throws
 *   STUB_LOADLIB xrt_load_library / xrt_free_library (module loading, xrt_main.c): fatal, no harness loads DLLs
 *   STUB_POW    xrt_msvcr70_pow / xrt_msvcr70_image (xrt_msvcr70img.c): fatal, no harness calls _CIpow or uses its image
 *               (tools/xrt/tests/crt_gatef tests it)
 *   STUB_K32DEPS what hle_kernel32.c needs from the rest of the runtime, for a harness that links it for its handle
 *               table and sandbox guard: threads, modules, the baton and diagnostics are fatal; the guest last error
 *               is the TEB word (as xrt_thread.c); xrt_sandbox_root and xrt_exiting are plain variables
 *   STUB_CRTDEPS unexercised file/handle/error dependencies of a CRT-only harness: fatal
 *   STUB_K32EXTRA new heap/thread/procedure dependencies of the F3/F4 kernel32 harnesses: fatal */
#include "xrt_internal.h"

#ifdef STUB_EVENT
void xrt_event(const char* kind, const char* fmt, ...) {
    (void)kind;
    (void)fmt;
}
#endif

#ifdef STUB_JSTR
const char* xrt_jstr(char* out, size_t n, const char* s) {
    size_t o = 0;
    if (n < 3)
        return "\"\"";
    out[o++] = '"';
    for (; s && *s && o + 8 < n; s++) {
        unsigned char ch = (unsigned char)*s;
        if (ch == '"' || ch == '\\') {
            out[o++] = '\\';
            out[o++] = (char)ch;
        } else if (ch < 0x20) {
            o += (size_t)snprintf(out + o, n - o, "\\u%04x", ch);
        } else {
            out[o++] = (char)ch;
        }
    }
    out[o++] = '"';
    out[o] = 0;
    return out;
}
#endif

#ifdef STUB_EH
void xrt_eh_throw(CPU* c) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: _CxxThrowException reached"); }
#endif

#ifdef STUB_POW
const uint8_t* xrt_msvcr70_image(void) {
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_msvcr70_image reached");
}
double xrt_msvcr70_pow(CPU* c, double x, double y, uint32_t* error_type) {
    (void)x;
    (void)y;
    (void)error_type;
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_msvcr70_pow reached");
}
#endif

#ifdef STUB_CRTDEPS
uint32_t xrt_get_last_error(CPU* c) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_get_last_error reached");
}
void xrt_set_last_error(CPU* c, uint32_t e) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_set_last_error(%u) reached", e);
}
uint32_t xrt_handle_new(int type, void* host) {
    (void)host;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_handle_new(%d) reached", type);
}
void* xrt_handle_get(uint32_t h, int type) {
    (void)type;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_handle_get(%08x) reached", h);
}
void xrt_handle_free(uint32_t h) {
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_handle_free(%08x) reached", h);
}
int xrt_path_is_inside_sandbox(const uint16_t* p) {
    (void)p;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_path_is_inside_sandbox reached");
}
#endif

#if defined(STUB_CRTDEPS) || defined(STUB_K32DEPS)
int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) {
    (void)end;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_lifted_overlap(%08x, %u) reached", a, size);
}
#endif

#ifdef STUB_K32EXTRA
XrtModule* xrt_module_by_addr(uint32_t p) { xrt_fatal(NULL,XRT_EXIT_UNSUPPORTED,"test harness: module_by_addr(%08x)",p); }
int xrt_is_committed(uint32_t p,uint32_t n) { xrt_fatal(NULL,XRT_EXIT_UNSUPPORTED,"test harness: is_committed(%08x,%u)",p,n); }
uint32_t xrt_virtual_alloc(CPU* c, uint32_t size) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_virtual_alloc(%u) reached", size);
}
int xrt_virtual_free(CPU* c, uint32_t base) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_virtual_free(%08x) reached", base);
}
uint32_t xrt_guest_strdup_a(const char* s) {
    (void)s;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_guest_strdup_a reached");
}
int xrt_thread_count(void) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_thread_count reached"); }
XrtThread* xrt_thread_get(int i) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_thread_get(%d) reached", i); }
uint32_t xrt_hle_proc(const char* dll, const char* name) {
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_hle_proc(%s, %s) reached", dll, name);
}
uint32_t xrt_heap_alloc(uint32_t n) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_heap_alloc(%u) reached", n); }
void xrt_heap_free(CPU* c, uint32_t p) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_heap_free(%08x) reached", p); }
uint32_t xrt_heap_msize(CPU* c, uint32_t p) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_heap_msize(%08x) reached", p);
}
uint32_t xrt_rt_alloc(uint32_t n, uint32_t align) {
    (void)align;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_rt_alloc(%u) reached", n);
}
#endif

#ifdef STUB_LOADLIB
XrtModule* xrt_load_library(CPU* c, const char* host_path) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_load_library(\"%s\") reached", host_path);
}
int xrt_free_library(CPU* c, XrtModule* m) {
    (void)m;
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_free_library reached");
}
#endif

#if defined(STUB_K32EXTRA) || defined(STUB_K32DEPS)
uint32_t xrt_hle_export_proc(const char* dll, const char* name) {
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_hle_export_proc(%s, %s) reached", dll, name);
}
#endif

#ifdef STUB_K32DEPS
char xrt_sandbox_root[520];
volatile long xrt_exiting;
void xrt_set_last_error(CPU* c, uint32_t e) { wr32(c->fs_base + 0x34, e); }
uint32_t xrt_get_last_error(CPU* c) { return rd32(c->fs_base + 0x34); }
void xrt_describe(char* out, size_t n, uint32_t va) {
    (void)out;
    (void)n;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_describe(%08x) reached", va);
}
void xrt_baton_acquire(void) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_baton_acquire reached"); }
void xrt_baton_release(void) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_baton_release reached"); }
uint32_t xrt_thread_create(CPU* c, uint32_t stack_size, uint32_t start, uint32_t param, uint32_t* tid) {
    (void)stack_size;
    (void)param;
    (void)tid;
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_thread_create(%08x) reached", start);
}
void xrt_thread_exit(CPU* c, uint32_t code) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_thread_exit(%u) reached", code); }
int xrt_thread_count(void) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_thread_count reached"); }
XrtThread* xrt_thread_get(int i) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_thread_get(%d) reached", i); }
int xrt_module_count(void) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_module_count reached"); }
XrtModule* xrt_module_get(int i) { xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_module_get(%d) reached", i); }
XrtModule* xrt_module_by_name(const char* name) {
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_module_by_name(\"%s\") reached", name);
}
uint32_t xrt_module_export(XrtModule* m, const char* name, uint32_t ordinal) {
    (void)m;
    (void)ordinal;
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_module_export(\"%s\") reached", name ? name : "");
}
uint32_t xrt_hle_proc(const char* dll, const char* name) {
    xrt_fatal(NULL, XRT_EXIT_UNSUPPORTED, "test harness: xrt_hle_proc(%s, %s) reached", dll, name);
}
#endif
