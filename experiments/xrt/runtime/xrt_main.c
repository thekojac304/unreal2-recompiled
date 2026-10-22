/* xrt_main.c - host program for the translated UCC.exe + Core.dll (Windows x64 first milestone).
 *
 *   xrt_ucc.exe --guest <sandbox>\System\UCC.exe [--log FILE] [--report FILE] [--run-id ID] [--timeout-ms N] -- <guest args>
 *
 * The report (JSON, schema 2) is written once, atomically (temporary file + rename), when the process exits, a
 * fatal diagnostic stops it, or the watchdog fires; "outcome" says which. --run-id is echoed into the report and
 * the first line of the log so a harness can prove both belong to the invocation it started.
 *
 * Process model reproduced: map UCC.exe and Core.dll (original files from the sandbox, as data), bind
 * imports, run Core.dll's entry point (DLL_PROCESS_ATTACH) and then UCC.exe's entry point (the original,
 * translated mainCRTStartup), on a guest main thread. exit() runs the EXE's onexit table; ExitProcess
 * then runs DLL_PROCESS_DETACH (Core's CRT runs its own onexit table) before the host process exits with
 * the guest's exit code. The guest command line is "<guest exe> <args>" quoted like Python's
 * subprocess.list2cmdline, which is how the reference runs of the original are launched. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

extern const XrtLiftedModule xrt_mod_UCC, xrt_mod_Core;
void hle_msvcr70_init(void);

char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a;
const char* xrt_report_path;
static const char* run_id = "";
static volatile long report_written;
static char guest_cmdline[4096];
static volatile long process_exiting;
static uint32_t timeout_ms;
static int quote_exe;               /* --quote-exe: quote the guest exe path as uctrace does */

static void json_str(FILE* f, const char* s) {
    fputc('"', f);
    for (; *s; s++) {
        if (*s == '"' || *s == '\\')
            fputc('\\', f);
        if ((unsigned char)*s < 0x20)
            fprintf(f, "\\u%04x", (unsigned char)*s);
        else
            fputc(*s, f);
    }
    fputc('"', f);
}

void xrt_report_write(uint32_t exit_code, const char* outcome) {
    FILE* f;
    int i;
    uint64_t a, fr, live;
    uint32_t hw;
    char tmp[1100];
    if (!xrt_report_path || InterlockedExchange(&report_written, 1))
        return;
    snprintf(tmp, sizeof tmp, "%s.partial", xrt_report_path);
    if (!(f = fopen(tmp, "w")))
        return;
    fprintf(f, "{\n \"schema\": 2,\n \"run_id\": ");
    json_str(f, run_id);
    fprintf(f, ",\n \"exit_code\": %u,\n \"outcome\": ", exit_code);
    json_str(f, outcome);
    fprintf(f, ",\n \"guest_command_line\": ");
    json_str(f, guest_cmdline);
    fprintf(f, ",\n \"modules\": [");
    for (i = 0; i < xrt_module_count(); i++) {
        XrtModule* m = xrt_module_get(i);
        const XrtLiftedModule* l = m->lifted;
        uint32_t k, n = 0;
        for (k = 0; k < l->nfuncs; k++)
            n += l->hits[k] != 0;
        fprintf(f, "%s\n  {\"name\": \"%s\", \"base\": \"0x%08x\", \"sha256\": \"%s\", \"lifted_functions\": %u, "
                   "\"static_traps\": %u, \"functions_executed\": %u, \"hit_rvas\": [",
                i ? "," : "", m->name, m->base, l->sha256, l->nfuncs, l->ntraps, n);
        for (k = 0, n = 0; k < l->nfuncs; k++)
            if (l->hits[k])
                fprintf(f, "%s\"%x\"", n++ ? ", " : "", l->funcs[k].va - m->base);
        fputs("]}", f);
    }
    fprintf(f, "\n ],\n \"imports\": ");
    xrt_imports_report(f);
    fprintf(f, ",\n \"import_sites\": ");
    xrt_sites_report(f);
    fprintf(f, ",\n \"threads\": [");
    for (i = 0; i < xrt_thread_count(); i++) {
        XrtThread* t = xrt_thread_get(i);
        char d[512];
        xrt_describe(d, sizeof d, t->start_va);
        fprintf(f, "%s\n  {\"index\": %d, \"guest_tid\": %u, \"entry\": ", i ? "," : "", t->index, t->guest_tid);
        json_str(f, t->index ? d : "main (UCC.exe entry point)");
        fprintf(f, ", \"state\": \"%s\", \"exit_code\": %u, \"exit_via\": \"%s\", \"sleeps\": %llu, \"contended_cs\": %llu, "
                   "\"preemptions\": %llu, \"functions_entered\": %u, \"x87_cw\": \"0x%04x\"}",
                t->state == 2 ? "exited" : t->state == 1 ? "running" : "created", t->exit_code,
                t->exit_via == 1 ? "ExitThread" : t->exit_via == 2 ? "return" : "", t->sleeps, t->cs_waits, t->preemptions,
                t->cpu.hpos, t->cpu.fcw);
    }
    fputs("\n ]", f);
    xrt_events_report(f);
    xrt_heap_stats(&a, &fr, &live, &hw);
    fprintf(f, ",\n \"guest_heap\": {\"allocs\": %llu, \"frees\": %llu, \"live_bytes\": %llu, \"high_water\": %u}\n}\n",
            a, fr, live, hw);
    if (fclose(f) == 0)
        MoveFileExA(tmp, xrt_report_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
}

XRT_NORETURN void xrt_process_exit(CPU* c, uint32_t code) {
    int i;
    if (InterlockedExchange(&process_exiting, 1))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "process exit re-entered during termination");
    xrt_exiting = 1;
    xrt_log("ExitProcess(%u) on thread %d", code, c->thread->index);
    xrt_event("process_exit", "\"code\": %u", code);
    for (i = 0; i < xrt_thread_count(); i++) {
        XrtThread* t = xrt_thread_get(i);
        if (t != c->thread) {
            xrt_log("  thread %d at process exit: %s", t->index,
                    t->state == 2 ? "already exited" : "still alive (terminated by ExitProcess, as on Windows)");
            xrt_event("thread_at_exit", "\"index\": %d, \"state\": \"%s\"", t->index, t->state == 2 ? "exited" : "alive");
        }
    }
    for (i = xrt_module_count() - 1; i >= 0; i--) {
        XrtModule* m = xrt_module_get(i);
        if (m->is_dll && m->attached && m->entry) {
            uint32_t args[3] = {m->base, 0 /* DLL_PROCESS_DETACH */, 1 /* process is terminating */};
            uint32_t rc;
            xrt_log("DllMain(%s, DLL_PROCESS_DETACH)", m->name);
            xrt_event("dll_detach", "\"module\": \"%s\"", m->name);
            rc = xrt_call_guest(c, m->entry, 3, args, 1);
            xrt_event("dll_detach_returned", "\"module\": \"%s\", \"result\": %u", m->name, rc);
            m->attached = 0;
        }
    }
    xrt_stdout_flush();
    xrt_log("process exit complete, exit code %u", code);
    xrt_event("process_exit_complete", "\"code\": %u", code);
    xrt_report_write(code, "exited");
    fflush(NULL);
    ExitProcess(code);
}

static DWORD WINAPI watchdog(void* unused) {
    int i;
    (void)unused;
    Sleep(timeout_ms);
    if (process_exiting || xrt_dying)
        return 0;
    InterlockedExchange(&xrt_dying, 1);
    xrt_stdout_flush();
    fprintf(stderr, "\nXRT TIMEOUT after %u ms: guest state (read without the baton, may be mid-update):\n", timeout_ms);
    for (i = 0; i < xrt_thread_count(); i++) {
        XrtThread* t = xrt_thread_get(i);
        char d[512];
        int k;
        xrt_describe(d, sizeof d, t->cpu.pc);
        fprintf(stderr, " thread %d state %ld sleeps %llu: last instruction %s\n", t->index, t->state, t->sleeps, d);
        for (k = 0; k < 8 && k < (int)t->cpu.hpos; k++) {
            xrt_describe(d, sizeof d, t->cpu.hist[(t->cpu.hpos - 1 - k) & (XRT_HIST - 1)]);
            fprintf(stderr, "    entered %s\n", d);
        }
    }
    fflush(stderr);
    xrt_event("timeout", "\"after_ms\": %u", timeout_ms);
    xrt_report_write(78, "timeout");
    TerminateProcess(GetCurrentProcess(), 78);
    return 0;
}

/* offset of the first character after the "--" argument in the raw command line */
static const wchar_t* args_after_dashdash(const wchar_t* cmd) {
    const wchar_t* p = cmd;
    int inq = 0;
    while (*p) {
        const wchar_t* start;
        while (*p == L' ' || *p == L'\t')
            p++;
        start = p;
        while (*p && (inq || (*p != L' ' && *p != L'\t'))) {
            if (*p == L'"')
                inq = !inq;
            p++;
        }
        if (p - start == 2 && start[0] == L'-' && start[1] == L'-') {
            while (*p == L' ' || *p == L'\t')
                p++;
            return p;
        }
    }
    return NULL;
}

static int usage(void) {
    fprintf(stderr, "usage: xrt_ucc.exe --guest <sandbox>\\System\\UCC.exe [--log FILE] [--report FILE] [--run-id ID] [--timeout-ms N] [--count-sites NAMES] [--quote-exe] -- <args>\n");
    return XRT_EXIT_SETUP;
}

int main(int argc, char** argv) {
    const char* guest = NULL;
    const char* log_path = NULL;
    char dir[520], core_path[600], *slash;
    const wchar_t* rest;
    char rest_a[3000] = "";
    int i;
    XrtModule *ucc, *core;
    XrtThread* t;
    CPU* c;
    uint32_t args[3], rc;
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--"))
            break;
        if (!strcmp(argv[i], "--guest") && i + 1 < argc)
            guest = argv[++i];
        else if (!strcmp(argv[i], "--log") && i + 1 < argc)
            log_path = argv[++i];
        else if (!strcmp(argv[i], "--report") && i + 1 < argc)
            xrt_report_path = argv[++i];
        else if (!strcmp(argv[i], "--run-id") && i + 1 < argc)
            run_id = argv[++i];
        else if (!strcmp(argv[i], "--count-sites") && i + 1 < argc)
            xrt_sites_enable(argv[++i]);
        else if (!strcmp(argv[i], "--watch") && i + 1 < argc)
            xrt_watch_add((uint32_t)strtoul(argv[++i], NULL, 16));
        else if (!strcmp(argv[i], "--quote-exe"))
            quote_exe = 1;
        else if (!strcmp(argv[i], "--timeout-ms") && i + 1 < argc)
            timeout_ms = (uint32_t)strtoul(argv[++i], NULL, 10);
        else
            return usage();
    }
    if (!guest || i >= argc)
        return usage();
    if (!GetFullPathNameA(guest, sizeof dir, dir, NULL))
        return usage();
    /* sandbox discipline: never run against the original installation */
    if (!strstr(dir, "sandbox") || _strnicmp(dir, "E:\\Launchbox\\", 13) == 0) {
        fprintf(stderr, "xrt: refusing to run outside a sandbox copy: %s\n", dir);
        return XRT_EXIT_SETUP;
    }
    snprintf(guest_cmdline, sizeof guest_cmdline, "%s", dir);
    slash = strrchr(dir, '\\');
    *slash = 0;                                   /* dir = ...\System */
    snprintf(core_path, sizeof core_path, "%s\\Core.dll", dir);
    snprintf(xrt_sandbox_root, sizeof xrt_sandbox_root, "%s", dir);
    slash = strrchr(xrt_sandbox_root, '\\');
    if (slash)
        *slash = 0;                               /* sandbox root = parent of System */
    rest = args_after_dashdash(GetCommandLineW());
    if (rest && *rest)
        WideCharToMultiByte(CP_ACP, 0, rest, -1, rest_a, sizeof rest_a, NULL, NULL);
    {
        char exe[600];
        snprintf(exe, sizeof exe, "%s", guest_cmdline);
        if (quote_exe || strchr(exe, ' ') || strchr(exe, '\t'))
            snprintf(guest_cmdline, sizeof guest_cmdline, "\"%s\"%s%s", exe, rest_a[0] ? " " : "", rest_a);
        else
            snprintf(guest_cmdline, sizeof guest_cmdline, "%s%s%s", exe, rest_a[0] ? " " : "", rest_a);
    }
    SetCurrentDirectoryA(dir);
    xrt_events_init();
    xrt_mem_init();
    xrt_diag_init(log_path);
    if (timeout_ms)
        CloseHandle(CreateThread(NULL, 0, watchdog, NULL, 0, NULL));
    xrt_log("run id: %s", run_id);
    xrt_log("guest command line: %s", guest_cmdline);
    xrt_log("sandbox root: %s", xrt_sandbox_root);
    {
        char exe_full[600];
        snprintf(exe_full, sizeof exe_full, "%s\\UCC.exe", dir);
        ucc = xrt_module_load(exe_full, &xrt_mod_UCC);
    }
    core = xrt_module_load(core_path, &xrt_mod_Core);
    xrt_module_bind_imports(core);
    xrt_module_bind_imports(ucc);
    xrt_watches_arm();
    xrt_cmdline_a = xrt_guest_strdup_a(guest_cmdline);
    hle_msvcr70_init();
    t = xrt_thread_main(xrt_default_stack_reserve);
    xrt_baton_acquire();
    c = &t->cpu;
    args[0] = core->base;
    args[1] = 1;                                  /* DLL_PROCESS_ATTACH */
    args[2] = 1;                                  /* non-NULL: static load, as for an import-time DLL */
    xrt_log("DllMain(%s, DLL_PROCESS_ATTACH)", core->name);
    xrt_event("dll_attach", "\"module\": \"%s\"", core->name);
    rc = xrt_call_guest(c, core->entry, 3, args, 1);
    xrt_event("dll_attach_returned", "\"module\": \"%s\", \"result\": %u", core->name, rc);
    if (!rc)
        xrt_fatal(c, XRT_EXIT_SETUP, "Core.dll DllMain(DLL_PROCESS_ATTACH) returned FALSE");
    core->attached = 1;
    xrt_log("entering %s entry point %08x", ucc->name, ucc->entry);
    xrt_event("exe_entry", "\"module\": \"%s\"", ucc->name);
    rc = xrt_call_guest(c, ucc->entry, 0, NULL, 1);
    xrt_log("UCC.exe entry point returned %u", rc);
    xrt_event("exe_entry_returned", "\"result\": %u", rc);
    xrt_process_exit(c, rc);
}
