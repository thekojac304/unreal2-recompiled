/* uctrace - records what the ORIGINAL 32-bit UCC.exe actually executes (dependency map for X1).
 *
 * A minimal Win32 debugger (build as x86). It launches the target from the sandbox and records:
 *   - every module mapped (static and dynamic loads, in order, with base and size);
 *   - the first execution of every statically discovered function entry in instrumented modules
 *     (one-shot int3 breakpoints at entries listed in <entries-dir>/<module>.txt, RVAs in hex);
 *   - every imported function called FROM an instrumented module (persistent breakpoints on the
 *     bound IAT targets, attributed by return address; counts capped at IMPORT_CAP hits per target);
 *   - _controlfp arguments and every distinct x87 control word seen at import calls;
 *   - all first-chance exceptions (C++ throws are 0xE06D7363) and the exit code.
 * The debuggee's stdout/stderr go to files. Output: one JSON document.
 *
 * Usage: uctrace <entries-dir> <out.json> <stdout-file> <exe> [args...]   (cwd = the exe's directory)
 * UCTRACE_RUN_ID=<id> is echoed into the JSON ("run_id") so a harness can prove the trace is from its own run.
 * Exit status: 0 trace complete (the debuggee's exit code is in the JSON, whatever it is); 1/2/5 setup errors;
 * 3 the JSON could not be written; 4 the debug loop ended without the debuggee's EXIT_PROCESS event.
 * Optional: UCTRACE_SITES=name1,name2 (substrings of "DLL!function") additionally records, for those
 * imports, a histogram of return addresses ("import_sites") for site-by-site comparison with the
 * translated runtime (xrt_ucc --count-sites).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#define MAX_MODS 64
#define MAX_BP (1 << 18)
#define IMPORT_CAP 20000

typedef struct {
    char name[64];
    char path[MAX_PATH];
    DWORD base, size, entry;
    int instrumented, dynamic, iat_done;
    DWORD* entries; int nentries;
    DWORD* hit_order; int nhit;        /* RVAs in first-hit order */
} Mod;

typedef struct { DWORD addr; BYTE orig; int kind; int mod; int imp; } BP;   /* kind: 1 func, 2 import, 3 module entry */
typedef struct { char name[160]; DWORD addr; int count[MAX_MODS]; int capped; int total; } Imp;

static Mod mods[MAX_MODS]; static int nmods;
static BP* bps; static int nbps;
static Imp* imps; static int nimps;
static HANDLE hProc;
static struct { DWORD tid; HANDLE h; DWORD rearm; } threads[256]; static int nthreads;
static FILE* jout;
static char entries_dir[MAX_PATH];
static unsigned cws[64]; static char cw_where[64][160]; static int ncws;
static int order_counter;
#define MAX_SITES 65536
static char site_names[8][64]; static int nsite_names;
static struct { int imp; DWORD ret, ret2; int count; } sites[MAX_SITES]; static int nsites;
static int site_extra_off = -1;   /* UCTRACE_SITE_EXTRA=<byte offset>: also key by the dword at [esp+offset] */
static int site_wanted(const char* name) {
    for (int i = 0; i < nsite_names; i++) if (strstr(name, site_names[i])) return 1;
    return 0;
}
static void site_count(int imp, DWORD ret, DWORD ret2) {
    for (int i = 0; i < nsites; i++) if (sites[i].imp == imp && sites[i].ret == ret && sites[i].ret2 == ret2) { sites[i].count++; return; }
    if (nsites < MAX_SITES) { sites[nsites].imp = imp; sites[nsites].ret = ret; sites[nsites].ret2 = ret2; sites[nsites].count = 1; nsites++; }
}
static int loader_done;   /* set at the loader's initial breakpoint: later DLL loads are dynamic */

static HANDLE thread_handle(DWORD tid) {
    for (int i = 0; i < nthreads; i++) if (threads[i].tid == tid) return threads[i].h;
    return NULL;
}
static int thread_index(DWORD tid) {
    for (int i = 0; i < nthreads; i++) if (threads[i].tid == tid) return i;
    return -1;
}
static BOOL rd(DWORD a, void* b, SIZE_T n) { SIZE_T got; return ReadProcessMemory(hProc, (LPCVOID)(ULONG_PTR)a, b, n, &got) && got == n; }
static BOOL wr(DWORD a, const void* b, SIZE_T n) {
    SIZE_T got; DWORD old;
    VirtualProtectEx(hProc, (LPVOID)(ULONG_PTR)a, n, PAGE_EXECUTE_READWRITE, &old);
    BOOL ok = WriteProcessMemory(hProc, (LPVOID)(ULONG_PTR)a, b, n, &got) && got == n;
    VirtualProtectEx(hProc, (LPVOID)(ULONG_PTR)a, n, old, &old);
    FlushInstructionCache(hProc, (LPCVOID)(ULONG_PTR)a, n);
    return ok;
}

/* open-addressing map addr -> bp index */
static int* bpmap; static int bpmap_size = 1 << 20;
static int bp_find(DWORD a) {
    unsigned h = (a * 2654435761u) & (bpmap_size - 1);
    while (bpmap[h] >= 0) { if (bps[bpmap[h]].addr == a) return bpmap[h]; h = (h + 1) & (bpmap_size - 1); }
    return -1;
}
static int bp_add(DWORD a, int kind, int mod, int imp) {
    if (bp_find(a) >= 0) return -1;
    if (nbps >= MAX_BP) { fprintf(stderr, "uctrace: too many breakpoints\n"); exit(5); }
    BYTE orig, cc = 0xCC;
    if (!rd(a, &orig, 1) || !wr(a, &cc, 1)) return -1;
    BP* b = &bps[nbps]; b->addr = a; b->orig = orig; b->kind = kind; b->mod = mod; b->imp = imp;
    unsigned h = (a * 2654435761u) & (bpmap_size - 1);
    while (bpmap[h] >= 0) h = (h + 1) & (bpmap_size - 1);
    bpmap[h] = nbps;
    return nbps++;
}

static void lower(char* s) { for (; *s; s++) if (*s >= 'A' && *s <= 'Z') *s += 32; }

static void load_entries(Mod* m) {
    char p[MAX_PATH], lname[64];
    strcpy(lname, m->name); lower(lname);
    snprintf(p, sizeof p, "%s\\%s.txt", entries_dir, lname);
    FILE* f = fopen(p, "r");
    if (!f) return;
    int cap = 1024; m->entries = malloc(cap * sizeof(DWORD));
    unsigned v;
    while (fscanf(f, "%x", &v) == 1) {
        if (m->nentries == cap) { cap *= 2; m->entries = realloc(m->entries, cap * sizeof(DWORD)); }
        m->entries[m->nentries++] = v;
    }
    fclose(f);
    m->hit_order = malloc((m->nentries + 1) * sizeof(DWORD));
    m->instrumented = 1;
}

static int mod_of(DWORD a) {
    for (int i = 0; i < nmods; i++) if (a >= mods[i].base && a < mods[i].base + mods[i].size) return i;
    return -1;
}

static void add_module(DWORD base, const char* path, int dynamic) {
    if (nmods >= MAX_MODS) return;
    Mod* m = &mods[nmods];
    memset(m, 0, sizeof *m);
    strncpy(m->path, path, MAX_PATH - 1);
    const char* s = strrchr(path, '\\');
    strncpy(m->name, s ? s + 1 : path, 63);
    m->base = base; m->dynamic = dynamic;
    IMAGE_DOS_HEADER dos; IMAGE_NT_HEADERS32 nt;
    if (rd(base, &dos, sizeof dos) && rd(base + dos.e_lfanew, &nt, sizeof nt)) {
        m->size = nt.OptionalHeader.SizeOfImage;
        m->entry = nt.OptionalHeader.AddressOfEntryPoint ? base + nt.OptionalHeader.AddressOfEntryPoint : 0;
    }
    int idx = nmods++;
    load_entries(m);
    if (m->instrumented) {
        for (int i = 0; i < m->nentries; i++) bp_add(base + m->entries[i], 1, idx, -1);
        if (m->entry && bp_find(m->entry) < 0) bp_add(m->entry, 3, idx, -1);
    }
}

/* Resolve the bound IAT of an instrumented module and set persistent breakpoints on its targets. */
static void hook_imports(int mi) {
    Mod* m = &mods[mi];
    if (m->iat_done) return;
    m->iat_done = 1;
    IMAGE_DOS_HEADER dos; IMAGE_NT_HEADERS32 nt;
    if (!rd(m->base, &dos, sizeof dos) || !rd(m->base + dos.e_lfanew, &nt, sizeof nt)) return;
    IMAGE_DATA_DIRECTORY dd = nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    for (DWORD d = m->base + dd.VirtualAddress;; d += sizeof(IMAGE_IMPORT_DESCRIPTOR)) {
        IMAGE_IMPORT_DESCRIPTOR id;
        if (!rd(d, &id, sizeof id) || !id.FirstThunk) break;
        char dll[64] = {0};
        rd(m->base + id.Name, dll, 63);
        DWORD names = m->base + (id.OriginalFirstThunk ? id.OriginalFirstThunk : id.FirstThunk);
        for (int k = 0;; k++) {
            DWORD nref, target;
            if (!rd(names + 4 * k, &nref, 4) || !nref) break;
            rd(m->base + id.FirstThunk + 4 * k, &target, 4);
            char fname[128] = {0};
            if (nref & 0x80000000u) snprintf(fname, sizeof fname, "#%u", nref & 0xFFFF);
            else rd(m->base + nref + 2, fname, 127);
            int ti = mod_of(target);
            if (ti >= 0 && mods[ti].instrumented) continue;   /* import from another instrumented module: covered by its entries */
            int bi = bp_find(target);
            int ii;
            if (bi >= 0 && bps[bi].kind == 2) { ii = bps[bi].imp; }
            else {
                imps = realloc(imps, (nimps + 1) * sizeof(Imp));
                ii = nimps++;
                memset(&imps[ii], 0, sizeof(Imp));
                imps[ii].addr = target;
                bp_add(target, 2, -1, ii);
            }
            if (!strstr(imps[ii].name, fname)) {
                char tmp[160];
                snprintf(tmp, sizeof tmp, "%s%s%s!%s", imps[ii].name, imps[ii].name[0] ? "|" : "", dll, fname);
                strncpy(imps[ii].name, tmp, 159);
            }
        }
    }
}

static void note_cw(HANDLE th, const char* where) {
    WOW64_CONTEXT dummy; (void)dummy;
    CONTEXT ctx; ctx.ContextFlags = CONTEXT_FLOATING_POINT;
    if (!GetThreadContext(th, &ctx)) return;
    unsigned cw = ctx.FloatSave.ControlWord & 0xFFFF;
    for (int i = 0; i < ncws; i++) if (cws[i] == cw) return;
    if (ncws < 64) { cws[ncws] = cw; strncpy(cw_where[ncws], where, 159); ncws++; }
}

static void json_str(FILE* f, const char* s) {
    fputc('"', f);
    for (; *s; s++) {
        if ((unsigned char)*s < 0x20) { fprintf(f, "\\u%04x", (unsigned char)*s); continue; }
        if (*s == '"' || *s == '\\') fputc('\\', f);
        fputc(*s, f);
    }
    fputc('"', f);
}

typedef struct { DWORD code, addr, ret; int mod; char type[64]; char text[201]; } ExRec;
static ExRec exs[4096]; static int nexs;
typedef struct { DWORD newv, mask, caller; } CfRec;
static CfRec cfs[256]; static int ncfs;

int main(int argc, char** argv) {
    if (argc < 5) { fprintf(stderr, "usage: uctrace <entries-dir> <out.json> <stdout-file> <exe> [args...]\n"); return 2; }
    strncpy(entries_dir, argv[1], MAX_PATH - 1);
    {
        const char* env = getenv("UCTRACE_SITES");
        if (getenv("UCTRACE_SITE_EXTRA")) site_extra_off = atoi(getenv("UCTRACE_SITE_EXTRA"));
        while (env && *env && nsite_names < 8) {
            const char* comma = strchr(env, ',');
            size_t n = comma ? (size_t)(comma - env) : strlen(env);
            if (n > 63) n = 63;
            memcpy(site_names[nsite_names], env, n); site_names[nsite_names][n] = 0; nsite_names++;
            env = comma ? comma + 1 : NULL;
        }
    }
    bps = malloc(MAX_BP * sizeof(BP));
    bpmap = malloc(bpmap_size * sizeof(int));
    memset(bpmap, 0xFF, bpmap_size * sizeof(int));
    char cmd[4096];
    snprintf(cmd, sizeof cmd, "\"%s\"", argv[4]);
    for (int i = 5; i < argc; i++) { strcat(cmd, " "); strcat(cmd, argv[i]); }
    char dir[MAX_PATH]; strncpy(dir, argv[4], MAX_PATH - 1);
    char* sl = strrchr(dir, '\\'); if (sl) *sl = 0;
    SECURITY_ATTRIBUTES sa = {sizeof sa, NULL, TRUE};
    HANDLE hout = CreateFileA(argv[3], GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, 0, NULL);
    STARTUPINFOA si = {sizeof si}; PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESTDHANDLES; si.hStdOutput = hout; si.hStdError = hout; si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    if (!CreateProcessA(NULL, cmd, NULL, NULL, TRUE, DEBUG_ONLY_THIS_PROCESS, NULL, dir, &si, &pi)) {
        fprintf(stderr, "CreateProcess failed %lu\n", GetLastError()); return 1;
    }
    DWORD exit_code = 0; int done = 0;
    DEBUG_EVENT ev;
    while (!done && WaitForDebugEvent(&ev, INFINITE)) {
        DWORD cont = DBG_CONTINUE;
        switch (ev.dwDebugEventCode) {
        case CREATE_PROCESS_DEBUG_EVENT: {
            hProc = ev.u.CreateProcessInfo.hProcess;
            threads[nthreads].tid = ev.dwThreadId; threads[nthreads].h = ev.u.CreateProcessInfo.hThread; nthreads++;
            add_module((DWORD)(ULONG_PTR)ev.u.CreateProcessInfo.lpBaseOfImage, argv[4], 0);
            if (ev.u.CreateProcessInfo.hFile) CloseHandle(ev.u.CreateProcessInfo.hFile);
            break;
        }
        case CREATE_THREAD_DEBUG_EVENT:
            if (nthreads < 256) { threads[nthreads].tid = ev.dwThreadId; threads[nthreads].h = ev.u.CreateThread.hThread; nthreads++; }
            break;
        case LOAD_DLL_DEBUG_EVENT: {
            char path[MAX_PATH] = "?";
            if (ev.u.LoadDll.hFile) {
                GetFinalPathNameByHandleA(ev.u.LoadDll.hFile, path, MAX_PATH, 0);
                CloseHandle(ev.u.LoadDll.hFile);
            }
            add_module((DWORD)(ULONG_PTR)ev.u.LoadDll.lpBaseOfDll, path, loader_done);
            break;
        }
        case EXCEPTION_DEBUG_EVENT: {
            EXCEPTION_RECORD* er = &ev.u.Exception.ExceptionRecord;
            DWORD addr = (DWORD)(ULONG_PTR)er->ExceptionAddress;
            HANDLE th = thread_handle(ev.dwThreadId);
            if (er->ExceptionCode == EXCEPTION_BREAKPOINT) {
                int bi = bp_find(addr);
                if (bi < 0) { loader_done = 1; cont = DBG_CONTINUE; break; }   /* loader breakpoint or foreign int3 */
                BP* b = &bps[bi];
                CONTEXT ctx; ctx.ContextFlags = CONTEXT_FULL;
                GetThreadContext(th, &ctx);
                ctx.Eip = addr;
                wr(addr, &b->orig, 1);
                if (b->kind == 1 || b->kind == 3) {
                    if (b->mod >= 0 && b->kind == 1) { Mod* m = &mods[b->mod]; m->hit_order[m->nhit++] = addr - m->base; }
                    order_counter++;
                    if (b->kind == 3 || (b->mod >= 0 && addr == mods[b->mod].entry)) hook_imports(b->mod);
                    b->kind = 0;   /* one-shot */
                } else if (b->kind == 2) {
                    DWORD ret = 0; rd(ctx.Esp, &ret, 4);
                    int cm = mod_of(ret);
                    Imp* im = &imps[b->imp];
                    if (cm >= 0 && mods[cm].instrumented) {
                        im->count[cm]++; im->total++;
                        if (site_wanted(im->name)) {
                            DWORD ret2 = 0;
                            if (site_extra_off >= 0) rd(ctx.Esp + (DWORD)site_extra_off, &ret2, 4);
                            site_count(b->imp, ret, ret2);
                        }
                        char where[160]; snprintf(where, sizeof where, "%s from %s", im->name, mods[cm].name);
                        note_cw(th, where);
                        if (strstr(im->name, "_controlfp") && ncfs < 256) {
                            DWORD a1 = 0, a2 = 0; rd(ctx.Esp + 4, &a1, 4); rd(ctx.Esp + 8, &a2, 4);
                            cfs[ncfs].newv = a1; cfs[ncfs].mask = a2; cfs[ncfs].caller = ret; ncfs++;
                        }
                    }
                    int ti = thread_index(ev.dwThreadId);
                    if (++im->capped < IMPORT_CAP && ti >= 0) {   /* re-arm after single step */
                        ctx.EFlags |= 0x100;
                        threads[ti].rearm = addr;
                    } else {
                        b->kind = 0;
                    }
                }
                SetThreadContext(th, &ctx);
                cont = DBG_CONTINUE;
            } else if (er->ExceptionCode == EXCEPTION_SINGLE_STEP) {
                int ti = thread_index(ev.dwThreadId);
                if (ti >= 0 && threads[ti].rearm) {
                    BYTE cc = 0xCC; wr(threads[ti].rearm, &cc, 1); threads[ti].rearm = 0;
                    cont = DBG_CONTINUE;
                } else cont = DBG_EXCEPTION_NOT_HANDLED;
            } else {
                if (nexs < 4096) {
                    CONTEXT ctx; ctx.ContextFlags = CONTEXT_FULL; GetThreadContext(th, &ctx);
                    DWORD ret = 0;
                    exs[nexs].type[0] = 0;
                    if (er->ExceptionCode == 0xE06D7363 && er->NumberParameters >= 3) {
                        /* MSVC C++ throw: walk the EBP chain to the first return address in an instrumented module */
                        DWORD fp = ctx.Ebp;
                        for (int k = 0; k < 16 && fp; k++) {
                            DWORD v = 0, next = 0;
                            if (!rd(fp + 4, &v, 4) || !rd(fp, &next, 4)) break;
                            if (mod_of(v) >= 0 && mods[mod_of(v)].instrumented) { ret = v; break; }
                            fp = next;
                        }
                        /* ThrowInfo -> CatchableTypeArray -> first CatchableType -> TypeDescriptor name */
                        DWORD ti = (DWORD)er->ExceptionInformation[2], cta = 0, ct = 0, td = 0;
                        if (rd(ti + 12, &cta, 4) && rd(cta + 4, &ct, 4) && rd(ct + 4, &td, 4)) rd(td + 8, exs[nexs].type, 63);
                        exs[nexs].type[63] = 0;
                        DWORD obj = (DWORD)er->ExceptionInformation[1], strp = 0;
                        exs[nexs].text[0] = 0;
                        if (rd(obj, &strp, 4)) {   /* for 'const TCHAR*' throws, capture the message */
                            WCHAR w[100] = {0}; rd(strp, w, 198);
                            WideCharToMultiByte(CP_UTF8, 0, w, -1, exs[nexs].text, 200, NULL, NULL);
                            for (char* q = exs[nexs].text; *q; q++) if (*q == '"' || *q == 0x5C || (unsigned char)*q < 32) *q = '_';
                        }
                    }
                    exs[nexs].code = er->ExceptionCode; exs[nexs].addr = addr; exs[nexs].ret = ret; exs[nexs].mod = mod_of(ret ? ret : addr); nexs++;
                }
                cont = DBG_EXCEPTION_NOT_HANDLED;
            }
            break;
        }
        case EXIT_PROCESS_DEBUG_EVENT:
            exit_code = ev.u.ExitProcess.dwExitCode; done = 1; break;
        default: break;
        }
        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, cont);
    }
    CloseHandle(hout);
    /* the debuggee's files (UCC.exe, DLLs, logs) stay locked until its process object is gone */
    if (WaitForSingleObject(pi.hProcess, 30000) != WAIT_OBJECT_0)
        fprintf(stderr, "uctrace: debuggee process did not terminate after EXIT_PROCESS\n");
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    jout = fopen(argv[2], "w");
    if (!jout) { fprintf(stderr, "uctrace: cannot write %s\n", argv[2]); return 3; }
    fprintf(jout, "{\n \"run_id\": "); json_str(jout, getenv("UCTRACE_RUN_ID") ? getenv("UCTRACE_RUN_ID") : "");
    fprintf(jout, ",\n \"complete\": %s", done ? "true" : "false");
    fprintf(jout, ",\n \"command\": "); json_str(jout, cmd);
    fprintf(jout, ",\n \"exit_code\": %lu,\n \"threads\": %d,\n \"modules\": [\n", exit_code, nthreads);
    for (int i = 0; i < nmods; i++) {
        Mod* m = &mods[i];
        fprintf(jout, "  {\"name\": "); json_str(jout, m->name);
        fprintf(jout, ", \"path\": "); json_str(jout, m->path);
        fprintf(jout, ", \"base\": \"0x%08lx\", \"size\": %lu, \"instrumented\": %d, \"entries\": %d, \"hit\": %d, \"hit_rvas\": [",
                m->base, m->size, m->instrumented, m->nentries, m->nhit);
        for (int k = 0; k < m->nhit; k++) fprintf(jout, "%s\"%lx\"", k ? "," : "", m->hit_order[k]);
        fprintf(jout, "]}%s\n", i + 1 < nmods ? "," : "");
    }
    fprintf(jout, " ],\n \"imports\": [\n");
    int first = 1;
    for (int i = 0; i < nimps; i++) {
        if (!imps[i].total) continue;
        fprintf(jout, "%s  {\"name\": ", first ? "" : ",\n"); first = 0;
        json_str(jout, imps[i].name);
        fprintf(jout, ", \"calls_from_instrumented\": %d, \"capped\": %d, \"by_module\": {", imps[i].total, imps[i].capped >= IMPORT_CAP);
        int f2 = 1;
        for (int k = 0; k < nmods; k++) if (imps[i].count[k]) { fprintf(jout, "%s", f2 ? "" : ", "); f2 = 0; json_str(jout, mods[k].name); fprintf(jout, ": %d", imps[i].count[k]); }
        fprintf(jout, "}}");
    }
    fprintf(jout, "\n ],\n \"import_sites\": [");
    for (int i = 0; i < nsites; i++) {
        fprintf(jout, "%s\n  {\"import\": ", i ? "," : "");
        json_str(jout, imps[sites[i].imp].name);
        fprintf(jout, ", \"return_address\": \"0x%08lx\", \"extra\": \"0x%08lx\", \"count\": %d}", sites[i].ret, sites[i].ret2, sites[i].count);
    }
    fprintf(jout, "\n ],\n \"exceptions\": [");
    for (int i = 0; i < nexs; i++) {
        fprintf(jout, "%s\n  {\"code\": \"0x%08lx\", \"addr\": \"0x%08lx\", \"caller\": \"0x%08lx\", \"module\": \"%s\", \"type\": ", i ? "," : "",
                exs[i].code, exs[i].addr, exs[i].ret, exs[i].mod >= 0 ? mods[exs[i].mod].name : "?");
        json_str(jout, exs[i].type);
        fprintf(jout, ", \"text\": ");
        json_str(jout, exs[i].text);
        fprintf(jout, "}");
    }
    fprintf(jout, "\n ],\n \"controlfp_calls\": [");
    for (int i = 0; i < ncfs; i++)
        fprintf(jout, "%s{\"new\": \"0x%08lx\", \"mask\": \"0x%08lx\", \"caller\": \"0x%08lx\"}", i ? ", " : "", cfs[i].newv, cfs[i].mask, cfs[i].caller);
    fprintf(jout, "],\n \"x87_control_words_seen\": [");
    for (int i = 0; i < ncws; i++) { fprintf(jout, "%s{\"cw\": \"0x%04x\", \"first_seen_at\": ", i ? ", " : "", cws[i]); json_str(jout, cw_where[i]); fprintf(jout, "}"); }
    fprintf(jout, "]\n}\n");
    if (fclose(jout) != 0) { fprintf(stderr, "uctrace: error writing %s\n", argv[2]); return 3; }
    printf("uctrace: exit=%lu modules=%d imports_used=%d exceptions=%d\n", exit_code, nmods, nimps, nexs);
    return done ? 0 : 4;   /* 4: the debug loop ended before the debuggee's EXIT_PROCESS event */
}
