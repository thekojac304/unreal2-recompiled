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

extern const XrtLiftedModule xrt_mod_UCC, xrt_mod_Core, xrt_mod_Engine, xrt_mod_GlmLib, xrt_mod_Editor, xrt_mod_Window,
    xrt_mod_UnrImp, xrt_mod_Fire;
#ifdef XRT_WITH_UNREAL2
extern const XrtLiftedModule xrt_mod_Unreal2, xrt_mod_WinDrv, xrt_mod_D3DDrv;
#endif
void hle_msvcr70_init(void);

/* Every translated module linked into this host. UCC.exe and Core.dll are mapped at start (Core is UCC's static
 * import); the others only when the guest loads them (LoadLibrary), together with their translated static
 * imports, as the Windows loader does. A DLL that exists but is not in this list cannot be loaded (fatal).
 * Bases are those of the original's `ucc make` process: Editor.dll rebased to 0x02de0000 (its preferred range
 * overlaps Engine.dll's), GlmLib.dll to 0x02f40000, Engine.dll and Window.dll at their preferred bases. GlmLib's
 * editor-mode initialisation loads its plugin plugins\UnrImp.gpi (a DLL with its own static CRT) and frees it again;
 * Editor.u imports the Fire package, whose native classes are in Fire.dll. The original placed these two differently
 * from run to run; this host uses the bases of one observed run, UnrImp.gpi 0x036d0000 and Fire.dll 0x03710000. */
static const XrtLiftedModule* const lifted_all[] = {&xrt_mod_UCC, &xrt_mod_Core, &xrt_mod_Engine, &xrt_mod_GlmLib,
                                                    &xrt_mod_Editor, &xrt_mod_Window, &xrt_mod_UnrImp, &xrt_mod_Fire
#ifdef XRT_WITH_UNREAL2
                                                    , &xrt_mod_Unreal2, &xrt_mod_WinDrv, &xrt_mod_D3DDrv
#endif
};
#define NLIFTED ((int)(sizeof lifted_all / sizeof lifted_all[0]))
static XrtModule* init_order[16];   /* DLLs whose DLL_PROCESS_ATTACH completed, in that order */
static int ninit;
static char app_dir[520];           /* directory of the guest EXE: where the loader looks for DLLs first */

char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a;
uint32_t xrt_cmdline_w;
const char* xrt_report_path;
static const char* run_id = "";
static volatile long report_written;
static char guest_cmdline[4096];
static WCHAR guest_cmdline_w[4096];
static volatile long process_exiting;
static uint32_t timeout_ms;
static int quote_exe;               /* --quote-exe: quote the guest exe path as uctrace does */

static void json_str(FILE* f, const char* s) {   /* ANSI string -> ASCII-only JSON string (xrt_jstr) */
    size_t n = 6 * strlen(s) + 3;
    char* buf = (char*)malloc(n);
    if (!buf) {
        fputs("\"<out of memory>\"", f);
        return;
    }
    fputs(xrt_jstr(buf, n, s), f);
    free(buf);
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
        fprintf(f, "%s\n  {\"name\": \"%s\", \"base\": \"0x%08x\", \"unloaded\": %s, \"sha256\": \"%s\", \"marks_sha256\": "
                   "\"%s\", \"lifted_functions\": %u, \"static_traps\": %u, \"functions_executed\": %u, \"hit_rvas\": [",
                i ? "," : "", m->name, m->base, m->unloaded ? "true" : "false", l->sha256,
                l->marks_sha256 ? l->marks_sha256 : "", l->nfuncs, l->ntraps, n);
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
        json_str(f, t->index ? d : "main executable entry point");
        fprintf(f, ", \"state\": \"%s\", \"exit_code\": %u, \"exit_via\": \"%s\", \"sleeps\": %llu, \"contended_cs\": %llu, "
                   "\"preemptions\": %llu, \"functions_entered\": %u, \"x87_cw\": \"0x%04x\"}",
                t->state == 2 ? "exited" : t->state == 1 ? "running" : "created", t->exit_code,
                t->exit_via == 1 ? "ExitThread" : t->exit_via == 2 ? "return" : "", t->sleeps, t->cs_waits, t->preemptions,
                t->cpu.hpos, t->cpu.fcw);
    }
    fputs("\n ]", f);
    xrt_events_report(f);
    xrt_eh_report(f);
    xrt_heap_stats(&a, &fr, &live, &hw);
    fprintf(f, ",\n \"guest_heap\": {\"allocs\": %llu, \"frees\": %llu, \"live_bytes\": %llu, \"high_water\": %u}\n}\n",
            a, fr, live, hw);
    if (fclose(f) == 0)
        MoveFileExA(tmp, xrt_report_path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
}

/* ---------------------------------------------------------------- loader */
static const char* file_part(const char* p) {
    const char* b = p;
    for (; *p; p++)
        if (*p == '\\' || *p == '/' || *p == ':')
            b = p + 1;
    return b;
}

const XrtLiftedModule* xrt_lifted_find(const char* name) {
    char want[128];
    int i;
    snprintf(want, sizeof want, "%s", file_part(name));
    if (!strchr(want, '.') && strlen(want) + 4 < sizeof want)
        strcat(want, ".dll");
    for (i = 0; i < NLIFTED; i++)
        if (!_stricmp(lifted_all[i]->name, want))
            return lifted_all[i];
    return NULL;
}

int xrt_lifted_overlap(uint32_t a, uint32_t size, uint32_t* end) {
    int i;
    for (i = 0; i < NLIFTED; i++) {
        uint64_t lo = lifted_all[i]->base, hi = lo + lifted_all[i]->size;
        if (a < hi && lo < (uint64_t)a + size) {
            *end = (uint32_t)hi;
            return 1;
        }
    }
    return 0;
}

/* DllMain(DLL_PROCESS_ATTACH) under the loader lock; reserved is non-NULL for a load at process start, NULL for
 * LoadLibrary. A failed initialisation (FALSE) is not modelled: fatal. */
static void dll_attach(CPU* c, XrtModule* m, uint32_t reserved) {
    uint32_t args[3], rc = 1;
    if (m->entry) {
        args[0] = m->base;
        args[1] = 1;                              /* DLL_PROCESS_ATTACH */
        args[2] = reserved;
        xrt_log("DllMain(%s, DLL_PROCESS_ATTACH)", m->name);
        xrt_event("dll_attach", "\"module\": \"%s\"", m->name);
        c->thread->loader_lock++;
        rc = xrt_call_guest(c, m->entry, 3, args, 1);
        c->thread->loader_lock--;
        xrt_event("dll_attach_returned", "\"module\": \"%s\", \"result\": %u", m->name, rc);
    }
    if (!rc)
        xrt_fatal(c, XRT_EXIT_SETUP, "%s DllMain(DLL_PROCESS_ATTACH) returned FALSE", m->name);
    m->attached = 1;
    if (ninit == (int)(sizeof init_order / sizeof init_order[0]))
        xrt_fatal(c, XRT_EXIT_SETUP, "too many initialised DLLs");
    init_order[ninit++] = m;
}

/* Map a translated module and, depth first, the translated DLLs it imports that are not mapped yet (found in the
 * application directory, as the loader's search order finds them there first). Newly mapped modules are appended
 * to list in completion order: dependencies before the modules that import them. */
static void map_tree(CPU* c, const char* host_path, const XrtLiftedModule* l, XrtModule** list, int* n) {
    XrtModule* m = xrt_module_load(host_path, l);
    uint8_t* hdr = (uint8_t*)G2H(m->base);
    uint32_t pe = *(uint32_t*)(hdr + 0x3C), dir = *(uint32_t*)(hdr + pe + 24 + 104), d;
    xrt_event(m->is_dll ? "dll_mapped" : "exe_mapped", "\"module\": \"%s\", \"base\": \"0x%08x\", \"preferred_base\": \"0x%08x\"", m->name, m->base,
              m->preferred_base);
    for (d = dir ? m->base + dir : 0; d && rd32(d + 12); d += 20) {
        const char* dll = (const char*)G2H(m->base + rd32(d + 12));
        XrtModule* have = xrt_module_by_name(dll);
        const XrtLiftedModule* dl;
        char path[600];
        if (have) {
            if (have->load_count >= 0)
                have->load_count++;
            continue;
        }
        if (!(dl = xrt_lifted_find(dll)))
            continue;                             /* a system DLL: its imports bind to host adapters */
        snprintf(path, sizeof path, "%s\\%s", app_dir, dl->name);
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES)
            xrt_fatal(c, XRT_EXIT_IMPORT, "%s imports %s, which is not in %s", m->name, dll, app_dir);
        map_tree(c, path, dl, list, n);
    }
    if (*n == 8)
        xrt_fatal(c, XRT_EXIT_SETUP, "too many modules in one load");
    list[(*n)++] = m;
    m->load_count = 1;
}

XrtModule* xrt_load_library(CPU* c, const char* host_path) {
    XrtModule* m = xrt_module_by_name(host_path);
    XrtModule* list[8];
    const XrtLiftedModule* l;
    int n = 0, i;
    if (m) {
        if (m->load_count >= 0)
            m->load_count++;
        return m;
    }
    if (!(l = xrt_lifted_find(host_path)))
        return NULL;
    xrt_log("LoadLibrary: loading translated %s", host_path);
    c->thread->loader_lock++;
    map_tree(c, host_path, l, list, &n);
    for (i = 0; i < n; i++)
        xrt_module_bind_imports(list[i]);
    for (i = 0; i < n; i++)
        xrt_watches_arm_module(list[i]);
    for (i = 0; i < n; i++)
        dll_attach(c, list[i], 0);
    c->thread->loader_lock--;
    return list[n - 1];
}

/* The last reference of a dynamically loaded DLL: DllMain(DLL_PROCESS_DETACH) with lpReserved NULL (FreeLibrary,
 * not process termination) under the loader lock, then the references it holds on the translated DLLs it imports
 * are released (a dependency whose count reaches zero is unloaded the same way), then it is unmapped. */
static void unload(CPU* c, XrtModule* m) {
    uint8_t* hdr = (uint8_t*)G2H(m->base);
    uint32_t pe = *(uint32_t*)(hdr + 0x3C), dir = *(uint32_t*)(hdr + pe + 24 + 104), d;
    int i, k;
    c->thread->loader_lock++;
    if (m->attached && m->entry) {
        uint32_t args[3] = {m->base, 0 /* DLL_PROCESS_DETACH */, 0 /* FreeLibrary */}, rc;
        xrt_log("DllMain(%s, DLL_PROCESS_DETACH) on FreeLibrary", m->name);
        xrt_event("dll_detach", "\"module\": \"%s\", \"reserved\": 0", m->name);
        rc = xrt_call_guest(c, m->entry, 3, args, 1);
        xrt_event("dll_detach_returned", "\"module\": \"%s\", \"result\": %u, \"reserved\": 0", m->name, rc);
    }
    m->attached = 0;
    for (i = k = 0; i < ninit; i++)
        if (init_order[i] != m)
            init_order[k++] = init_order[i];
    ninit = k;
    for (d = dir ? m->base + dir : 0; d && rd32(d + 12); d += 20) {
        XrtModule* dep = xrt_module_by_name((const char*)G2H(m->base + rd32(d + 12)));
        if (!dep) {
            xrt_system_import((const char*)G2H(m->base + rd32(d + 12)), -1);
            continue;
        }
        if (dep->load_count < 0)
            continue;                             /* system DLL (host adapters) or loaded with the process */
        if (dep->load_count > 1)
            dep->load_count--;
        else
            unload(c, dep);
    }
    m->load_count = 0;
    xrt_module_unmap(m);
    xrt_event("dll_unloaded", "\"module\": \"%s\", \"base\": \"0x%08x\"", m->name, m->base);
    c->thread->loader_lock--;
}

int xrt_free_library(CPU* c, XrtModule* m) {
    if (m->load_count < 0)
        return 1;                                 /* loaded with the process: stays mapped */
    if (m->load_count > 1) {
        m->load_count--;
        return 1;
    }
    unload(c, m);
    return 1;
}

/* DLL_THREAD_ATTACH (initialisation order) when a guest thread starts, DLL_THREAD_DETACH (reverse order) when it
 * ends, for every initialised DLL - none of these modules calls DisableThreadLibraryCalls. Threads the original
 * process got from the system (not created by guest code) are not modelled. */
void xrt_dll_thread_notify(CPU* c, uint32_t reason) {
    XrtModule* order[16];
    int n = ninit, k;
    memcpy(order, init_order, sizeof order);
    c->thread->loader_lock++;
    for (k = 0; k < n; k++) {
        XrtModule* m = reason == 2 ? order[k] : order[n - 1 - k];
        uint32_t args[3];
        if (!m->attached || !m->entry)
            continue;
        args[0] = m->base;
        args[1] = reason;
        args[2] = 0;
        xrt_event(reason == 2 ? "dll_thread_attach" : "dll_thread_detach", "\"module\": \"%s\"", m->name);
        xrt_call_guest(c, m->entry, 3, args, 1);
    }
    c->thread->loader_lock--;
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
    for (i = ninit - 1; i >= 0; i--) {            /* reverse initialisation order */
        XrtModule* m = init_order[i];
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
    xrt_cleanup_atoms();
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
    xrt_cleanup_input_settings();
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
    XrtModule *ucc, *core, *startup[8];
    int nstartup = 0;
    const XrtLiftedModule* executable;
    XrtThread* t;
    CPU* c;
    uint32_t rc;
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
    snprintf(app_dir, sizeof app_dir, "%s", dir);
    snprintf(xrt_sandbox_root, sizeof xrt_sandbox_root, "%s", dir);
    slash = strrchr(xrt_sandbox_root, '\\');
    if (slash)
        *slash = 0;                               /* sandbox root = parent of System */
    rest = args_after_dashdash(GetCommandLineW());
    if (rest && *rest)
        WideCharToMultiByte(CP_ACP, 0, rest, -1, rest_a, sizeof rest_a, NULL, NULL);
    {
        char exe[600];
        WCHAR exe_w[600];
        snprintf(exe, sizeof exe, "%s", guest_cmdline);
        MultiByteToWideChar(CP_ACP, 0, exe, -1, exe_w, 600);
        _snwprintf(guest_cmdline_w, 4095, quote_exe || strchr(exe, ' ') || strchr(exe, '\t') ? L"\"%ls\"%ls%ls" : L"%ls%ls%ls",
                   exe_w, rest && *rest ? L" " : L"", rest ? rest : L"");
        guest_cmdline_w[4095] = 0;
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
    executable = xrt_lifted_find(file_part(guest));
    if (!executable || (strcmp(executable->name, "UCC.exe") && strcmp(executable->name, "Unreal2.exe")))
        xrt_fatal(NULL, XRT_EXIT_SETUP, "guest executable has no linked translation: %s", guest);
    {
        char exe_full[600];
        snprintf(exe_full, sizeof exe_full, "%s\\%s", dir, executable->name);
        if (executable == &xrt_mod_UCC) {
            ucc = xrt_module_load(exe_full, executable);
            core = xrt_module_load(core_path, &xrt_mod_Core);
            xrt_module_bind_imports(core);
            xrt_module_bind_imports(ucc);
            startup[nstartup++] = core;
        } else {
            map_tree(NULL, exe_full, executable, startup, &nstartup);
            ucc = startup[nstartup - 1];
            for (i = 0; i < nstartup; i++) {
                startup[i]->load_count = -1;
                xrt_module_bind_imports(startup[i]);
            }
        }
    }
    xrt_watches_arm();
    xrt_cmdline_a = xrt_guest_strdup_a(guest_cmdline);
    xrt_cmdline_w = xrt_rt_alloc((uint32_t)(2 * (wcslen(guest_cmdline_w) + 1)), 2);
    memcpy(G2H(xrt_cmdline_w), guest_cmdline_w, 2 * (wcslen(guest_cmdline_w) + 1));
    hle_msvcr70_init();
    t = xrt_thread_main(xrt_default_stack_reserve);
    xrt_baton_acquire();
    c = &t->cpu;
    for (i = 0; i < nstartup; i++)
        if (startup[i]->is_dll)
            dll_attach(c, startup[i], 1);        /* reserved non-NULL: static load */
    xrt_log("entering %s entry point %08x", ucc->name, ucc->entry);
    xrt_event("exe_entry", "\"module\": \"%s\"", ucc->name);
    rc = xrt_call_guest(c, ucc->entry, 0, NULL, 1);
    xrt_log("%s entry point returned %u", ucc->name, rc);
    xrt_event("exe_entry_returned", "\"result\": %u", rc);
    xrt_process_exit(c, rc);
}
