/* Stubs for runtime symbols that adapter-level test harnesses do not exercise. Each harness compiles this file
 * with the STUB_* switches for the symbols it does not already define or link:
 *   STUB_EVENT  xrt_event (evidence timeline, xrt_events.c): ignored
 *   STUB_JSTR   xrt_jstr: a real JSON quoting, since callers use its result as text
 *   STUB_EH     xrt_eh_throw (C++ exception dispatch, xrt_eh.c): fatal, because no harness throws
 *   STUB_LOADLIB xrt_load_library / xrt_free_library (module loading, xrt_main.c): fatal, no harness loads DLLs */
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

#ifdef STUB_LOADLIB
XrtModule* xrt_load_library(CPU* c, const char* host_path) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_load_library(\"%s\") reached", host_path);
}
int xrt_free_library(CPU* c, XrtModule* m) {
    (void)m;
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: xrt_free_library reached");
}
#endif
