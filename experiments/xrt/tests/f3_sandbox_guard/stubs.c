/* stubs.c - minimal definitions of the runtime symbols hle_kernel32.obj references, so the real adapter object
 * (compiled with the runtime's own flags) can be linked into the F3 test without the lifted modules.
 * xrt_fatal does not exit: it records the message and longjmps back to the test (f3_fatal_jmp). */
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "xrt_internal.h"

uint8_t* xrt_g;
volatile long xrt_exiting;
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a;

jmp_buf f3_fatal_jmp;
int f3_fatal_armed;
char f3_fatal_msg[1200];
static uint32_t last_error;
int f3_quiet_log = 1;

static XRT_NORETURN void unexpected(const char* name) {
    fprintf(stderr, "unexpected test harness dependency: %s\n", name);
    exit(99);   /* never longjmp into a test that expects a sandbox rejection */
}

void xrt_heap_stats(uint64_t* allocs, uint64_t* frees, uint64_t* bytes_live, uint32_t* high_water) {
    unexpected("xrt_heap_stats");
}
void xrt_log(const char* fmt, ...) {
    if (!f3_quiet_log) {
        va_list ap;
        va_start(ap, fmt);
        fputs("    [xrt_log] ", stdout);
        vprintf(fmt, ap);
        fputc('\n', stdout);
        va_end(ap);
    }
}
void xrt_fatal(CPU* c, int code, const char* fmt, ...) {
    va_list ap;
    (void)c;
    va_start(ap, fmt);
    vsnprintf(f3_fatal_msg, sizeof f3_fatal_msg, fmt, ap);
    va_end(ap);
    if (f3_fatal_armed)
        longjmp(f3_fatal_jmp, code);
    printf("unexpected xrt_fatal(%d): %s\n", code, f3_fatal_msg);
    exit(99);
}
void xrt_describe(char* out, size_t n, uint32_t va) { unexpected("xrt_describe"); }
void xrt_baton_acquire(void) { unexpected("xrt_baton_acquire"); }
void xrt_baton_release(void) { unexpected("xrt_baton_release"); }
uint32_t xrt_thread_create(CPU* c, uint32_t stack_size, uint32_t start, uint32_t param, uint32_t* tid) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "stub: xrt_thread_create");
}
void xrt_thread_exit(CPU* c, uint32_t code) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "stub: xrt_thread_exit"); }
int xrt_module_count(void) { unexpected("xrt_module_count"); return 0; }
XrtModule* xrt_module_get(int i) { unexpected("xrt_module_get"); return NULL; }
XrtModule* xrt_module_by_name(const char* name) { unexpected("xrt_module_by_name"); return NULL; }
uint32_t xrt_module_export(XrtModule* m, const char* name, uint32_t ordinal) { unexpected("xrt_module_export"); return 0; }
void xrt_set_last_error(CPU* c, uint32_t e) { last_error = e; }
uint32_t xrt_get_last_error(CPU* c) { return last_error; }
void xrt_process_exit(CPU* c, uint32_t code) { xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "stub: xrt_process_exit"); }
void xrt_stdout_flush(void) { unexpected("xrt_stdout_flush"); }
