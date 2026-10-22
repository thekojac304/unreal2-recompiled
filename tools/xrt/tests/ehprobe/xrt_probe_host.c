/* xrt_probe_host.c (x64) - runs probe functions of the LIFTED ehprobe.dll on the translated runtime (all runtime
 * sources except xrt_main.c, unchanged): the module is mapped and bound like UCC.exe/Core.dll (msvcr70 imports go to
 * the host adapters, _CxxThrowException to the dispatcher in xrt_eh.c), and each probe is called on a guest thread.
 *   xrt_probe_host.exe <ehprobe.dll> <report.json> <probe> [<probe> ...]
 * Output format as native_host.c. A fatal diagnostic ends the process with the runtime's exit code. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

extern const XrtLiftedModule xrt_mod_ehprobe;
void hle_msvcr70_init(void);

/* the process-level pieces xrt_main.c provides for UCC.exe */
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a;
const char* xrt_report_path;
static volatile long report_written;

void xrt_report_write(uint32_t exit_code, const char* outcome) {
    FILE* f;
    if (!xrt_report_path || InterlockedExchange(&report_written, 1) || !(f = fopen(xrt_report_path, "w")))
        return;
    fprintf(f, "{\n \"schema\": \"ehprobe\",\n \"exit_code\": %u,\n \"outcome\": \"%s\"", exit_code,
            exit_code ? "fatal" : "exited");
    xrt_events_report(f);
    xrt_eh_report(f);
    fprintf(f, "\n}\n");
    fclose(f);
    (void)outcome;
}

XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code) {
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "the probe called exit/ExitProcess(%u)", code);
}

int main(int argc, char** argv) {
    char full[520], *slash;
    XrtModule* m;
    XrtThread* t;
    CPU* c;
    uint32_t log, n;
    int i;
    if (argc < 4)
        return 2;
    if (!GetFullPathNameA(argv[1], sizeof full, full, NULL))
        return 2;
    snprintf(xrt_sandbox_root, sizeof xrt_sandbox_root, "%s", full);
    slash = strrchr(xrt_sandbox_root, '\\');
    if (slash)
        *slash = 0;
    xrt_report_path = argv[2];
    xrt_events_init();
    xrt_mem_init();
    xrt_diag_init(NULL);
    m = xrt_module_load(full, &xrt_mod_ehprobe);
    xrt_module_bind_imports(m);
    xrt_cmdline_a = xrt_guest_strdup_a("ehprobe");
    hle_msvcr70_init();
    t = xrt_thread_main(0x100000);
    xrt_baton_acquire();
    c = &t->cpu;
    log = xrt_module_export(m, "probe_log", 0);
    n = xrt_module_export(m, "probe_log_n", 0);
    for (i = 3; i < argc; i++) {
        uint32_t f = xrt_module_export(m, argv[i], 0), r, k;
        if (!f || !log || !n) {
            printf("%s missing\n", argv[i]);
            return 2;
        }
        r = xrt_call_guest(c, f, 0, NULL, 0);
        printf("%s returned %d log", argv[i], (int)r);
        for (k = 0; k < rd32(n); k++)
            printf(" %d", (int)rd32(log + 4 * k));
        printf("\n");
        fflush(stdout);
    }
    xrt_report_write(0, "exited");
    return 0;
}
