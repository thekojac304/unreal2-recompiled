/* uctrace - records what the ORIGINAL 32-bit UCC.exe actually executes (dependency map for X1).
 *
 * A minimal Win32 debugger (build as x86). It launches the target from the sandbox and records:
 *   - every module mapped (static and dynamic loads, in order, with base and size) and unloaded; a module mapped
 *     again (also at the same base) is a new record with its own breakpoints and hits;
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
 * UCTRACE_EVENTS=<file>: event points, one per line "<module file name> <rva hex> <label>". Every execution of
 * an event point (persistent breakpoint) is recorded in order in "events" together with the C++ exceptions,
 * which share the same sequence numbers: thread, label, address, esp, [esp] (the return address at a function
 * entry), eax, ebp. Capped at MAX_EVENTS (the JSON says how many were dropped).
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
#include <dwmapi.h>

#define MAX_MODS 512 /* The real level client loads more DLLs (including unload/reload records). */
#define MAX_BP (1 << 18)
#define IMPORT_CAP 20000

typedef struct {
    char name[64];
    char path[MAX_PATH];
    DWORD base, size, entry;
    int instrumented, dynamic, iat_done, unloaded;
    DWORD* entries; int nentries;
    DWORD* hit_order; int nhit;        /* RVAs in first-hit order */
} Mod;

typedef struct { DWORD addr; BYTE orig; int kind; int mod; int imp; int ev; int music; } BP;   /* kind: 1 func, 2 import, 3 module entry, 4 event only; ev: event point or -1 */
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
/* event points (UCTRACE_EVENTS) and the ordered event log */
#define MAX_EVENTS 200000
typedef struct { char mod[64]; DWORD rva; char label[96]; } EvPoint;
static EvPoint* evp; static int nevp;
typedef struct { int seq; int thread; int point; DWORD esp, top, eax, ebp, ecx, edx, esi, edi, args[12]; WCHAR text0[256]; int exc;
    int fp_valid, mxcsr_valid; DWORD mxcsr; FLOATING_SAVE_AREA fp;
} EvRec;
static EvRec* evlog; static int nevlog, evdropped, ev_seq;
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
static DWORD time_limit_ms;
static ULONGLONG started;
static const char* stop_label;
static unsigned stop_after = 1, stop_hits;
static const char* termination_reason = "natural";
#define MAX_CALL_RECORDS 2048
typedef struct { int imp, thread, seq; DWORD ret, args[8]; char a[3][512]; WCHAR w[3][512]; } CallRec;
static CallRec* call_records;
static int ncalls, calls_dropped;
/* Optional bounded, read-only capture of this debuggee's client rectangle at
 * the requested event stop. No input, desktop mode, or game render code changes. */
static DWORD capture_pid;
static HWND capture_window;
static BOOL CALLBACK capture_enum(HWND h, LPARAM unused) {
    DWORD pid=0; RECT r;
    GetWindowThreadProcessId(h,&pid);
    if(pid==capture_pid && IsWindowVisible(h) && GetClientRect(h,&r) && r.right>=320 && r.bottom>=200) {
        capture_window=h; return FALSE;
    }
    (void)unused; return TRUE;
}
static void capture_client(void) {
    const char* path=getenv("UCTRACE_CAPTURE_CLIENT");
    RECT r={0}; HDC source=NULL,dc=NULL; HBITMAP bitmap=NULL; HGDIOBJ old=NULL;
    BITMAPINFO info; BITMAPFILEHEADER file; void* pixels=NULL; FILE* f=NULL;
    DWORD bytes; BOOL ok=FALSE; WCHAR title[256];
    POINT origin={0,0};
    DPI_AWARENESS_CONTEXT previous_dpi;
    if(!path) return;
    previous_dpi=SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    capture_pid=GetProcessId(hProc); capture_window=NULL;
    EnumWindows(capture_enum,0);
    if(!capture_window || !GetClientRect(capture_window,&r)) goto done;
    if(r.right>4096 || r.bottom>4096) goto done;
    /* A window DC can contain another application's pixels under DWM occlusion.
     * Refuse such a capture instead of treating desktop content as game output. */
    for(int i=0;i<5;i++) {
        POINT p={i==0?r.right/2:(i&1?1:r.right-2),i==0?r.bottom/2:(i&2?1:r.bottom-2)};
        if(!ClientToScreen(capture_window,&p) || GetAncestor(WindowFromPoint(p),GA_ROOT)!=capture_window) {
            fprintf(stderr,"client_capture skipped: game client is occluded at sample %d\n",i);
            goto done;
        }
    }
    memset(&info,0,sizeof info); info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth=r.right; info.bmiHeader.biHeight=-r.bottom;
    info.bmiHeader.biPlanes=1; info.bmiHeader.biBitCount=32; info.bmiHeader.biCompression=BI_RGB;
    bytes=r.right*r.bottom*4;
    /* Window DCs can return stale GDI pixels underneath a D3D swapchain. Use
     * the composed desktop, cropped to this PID-checked client rectangle. */
    if(!ClientToScreen(capture_window,&origin)) goto done;
    DwmFlush();
    source=GetDC(NULL); if(!source) goto done;
    dc=CreateCompatibleDC(source); if(!dc) goto done;
    bitmap=CreateDIBSection(source,&info,DIB_RGB_COLORS,&pixels,NULL,0); if(!bitmap) goto done;
    old=SelectObject(dc,bitmap);
    if(!BitBlt(dc,0,0,r.right,r.bottom,source,origin.x,origin.y,SRCCOPY|CAPTUREBLT)) goto done;
    GdiFlush();
    memset(&file,0,sizeof file); file.bfType=0x4d42; file.bfOffBits=sizeof file+sizeof(BITMAPINFOHEADER); file.bfSize=file.bfOffBits+bytes;
    f=fopen(path,"wb"); if(!f) goto done;
    ok=fwrite(&file,sizeof file,1,f)==1 && fwrite(&info.bmiHeader,sizeof(BITMAPINFOHEADER),1,f)==1 && fwrite(pixels,bytes,1,f)==1;
done:
    if(f) fclose(f);
    if(old) SelectObject(dc,old);
    if(bitmap) DeleteObject(bitmap);
    if(dc) DeleteDC(dc);
    if(source) ReleaseDC(NULL,source);
    title[0]=0;
    if(capture_window) GetWindowTextW(capture_window,title,256);
    fprintf(stderr,"client_capture source=composed-desktop-client-crop ok=%d pid=%lu hwnd=%p dimensions=%ldx%ld path=%s title=%ls error=%lu\n",ok,capture_pid,capture_window,capture_window?r.right:0,capture_window?r.bottom:0,path,title,GetLastError());
    if(previous_dpi) SetThreadDpiAwarenessContext(previous_dpi);
}

static HANDLE thread_handle(DWORD tid) {
    for (int i = 0; i < nthreads; i++) if (threads[i].tid == tid) return threads[i].h;
    return NULL;
}
static int thread_index(DWORD tid) {
    for (int i = 0; i < nthreads; i++) if (threads[i].tid == tid) return i;
    return -1;
}
static BOOL rd(DWORD a, void* b, SIZE_T n) { SIZE_T got; return ReadProcessMemory(hProc, (LPCVOID)(ULONG_PTR)a, b, n, &got) && got == n; }
/* Optional sidecar: only DirectMusic points, bounded pointer snapshots. Original
 * memory is never modified by this observer (apart from normal debugger INT3s). */
static void music_memory(FILE* f,DWORD addr) {
    BYTE data[96];
    fprintf(f,"{\"address\":\"%08lx\",\"bytes\":\"",addr);
    if(rd(addr,data,sizeof data)) for(unsigned i=0;i<sizeof data;i++) fprintf(f,"%02x",data[i]);
    fputs("\"}",f);
}
static void music_write(const char* label,int seq,int thread,const CONTEXT* ctx,const DWORD* saved) {
    const char* path=getenv("UCTRACE_MUSIC_LOG");
    static FILE* f;
    DWORD stack[16]={0};
    if(!path)return;
    if(!f) { f=fopen(path,"w"); if(!f) {fputs("music sidecar open failed\n",stderr);exit(5);} }
    if(saved)memcpy(stack,saved,sizeof stack);else rd(ctx->Esp,stack,sizeof stack);
    fprintf(f,"{\"seq\":%d,\"thread\":%d,\"label\":\"%s\",\"eax\":\"%08lx\",\"esp\":\"%08lx\",\"eip\":\"%08lx\",\"stack\":[",
            seq,thread,label,ctx->Eax,ctx->Esp,ctx->Eip);
    for(int i=0;i<16;i++)fprintf(f,"%s\"%08lx\"",i?",":"",stack[i]);
    fputs("],\"pointers\":[",f);
    for(int i=0;i<16;i++){if(i)fputc(',',f);music_memory(f,stack[i]);}
    fputs("],\"esi\":",f);music_memory(f,ctx->Esi);
    fputs(",\"ecx\":",f);music_memory(f,ctx->Ecx);
    if(!strncmp(label,"AActor.event",12)) {
        DWORD world=0;BOOL readable=rd(ctx->Ecx+0xd4,&world,4);
        fprintf(f,",\"actor_world\":\"%08lx\",\"actor_world_readable\":%s",world,readable?"true":"false");
    }
    fputs("}\n",f);fflush(f);
}
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
static void bp_map_insert(int i) {
    unsigned h = (bps[i].addr * 2654435761u) & (bpmap_size - 1);
    while (bpmap[h] >= 0) h = (h + 1) & (bpmap_size - 1);
    bpmap[h] = i;
}
static int bp_add(DWORD a, int kind, int mod, int imp) {
    if (bp_find(a) >= 0) return -1;
    if (nbps >= MAX_BP) { fprintf(stderr, "uctrace: too many breakpoints\n"); exit(5); }
    BYTE orig, cc = 0xCC;
    if (!rd(a, &orig, 1) || !wr(a, &cc, 1)) return -1;
    BP* b = &bps[nbps]; b->addr = a; b->orig = orig; b->kind = kind; b->mod = mod; b->imp = imp; b->ev = -1; b->music=0;
    bp_map_insert(nbps);
    return nbps++;
}
/* A module was unmapped: its breakpoints (and import breakpoints on targets inside it) die with it, so a later
 * mapping at the same addresses gets fresh ones. */
static void bp_forget_range(DWORD lo, DWORD hi) {
    int i;
    for (i = 0; i < nbps; i++)
        if (bps[i].addr >= lo && bps[i].addr < hi) bps[i].addr = 0;
    memset(bpmap, 0xFF, bpmap_size * sizeof(int));
    for (i = 0; i < nbps; i++)
        if (bps[i].addr) bp_map_insert(i);
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
    for (int i = 0; i < nmods; i++) if (!mods[i].unloaded && a >= mods[i].base && a < mods[i].base + mods[i].size) return i;
    return -1;
}

static void add_module(DWORD base, const char* path, int dynamic) {
    if (nmods >= MAX_MODS) { fprintf(stderr, "uctrace: module capacity exceeded\n"); exit(5); }
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
    for (int i = 0; i < nevp; i++) {
        if (_stricmp(evp[i].mod, m->name)) continue;
        int bi = bp_find(base + evp[i].rva);
        if (bi < 0) bi = bp_add(base + evp[i].rva, 4, idx, -1);
        if (bi >= 0) bps[bi].ev = i;
        else fprintf(stderr, "uctrace: cannot set event point %s+%lx\n", m->name, evp[i].rva);
    }
}

static void load_event_points(const char* path) {
    FILE* f = fopen(path, "r");
    char line[256];
    if (!f) { fprintf(stderr, "uctrace: cannot read %s\n", path); exit(2); }
    evp = malloc(4096 * sizeof(EvPoint));
    while (fgets(line, sizeof line, f) && nevp < 4096) {
        EvPoint* e = &evp[nevp];
        unsigned rva;
        int used = 0;
        if (line[0] == '#' || sscanf(line, "%63s %x %n", e->mod, &rva, &used) < 2) continue;
        e->rva = rva;
        strncpy(e->label, line + used, 95);
        e->label[95] = 0;
        e->label[strcspn(e->label, "\r\n")] = 0;
        nevp++;
    }
    fclose(f);
    evlog = malloc(MAX_EVENTS * sizeof(EvRec));
}

#include "music_trace.inc"

static void log_event(int point, int exc, int thread, const CONTEXT* ctx) {
    int seq = ++ev_seq;
    if (!evlog) return;
    if (nevlog >= MAX_EVENTS) { evdropped++; return; }
    EvRec* r = &evlog[nevlog++];
    r->seq = seq; r->thread = thread; r->point = point; r->exc = exc;
    music_observe(point,seq,thread,ctx);
    r->esp = ctx->Esp; r->eax = ctx->Eax; r->ebp = ctx->Ebp; r->top = 0;
    r->ecx = ctx->Ecx; r->edx = ctx->Edx; r->esi = ctx->Esi; r->edi = ctx->Edi;
    r->fp_valid = 0;
    r->mxcsr_valid = 0;
    /* Read a separate context: observation must not write FPU state back through SetThreadContext. */
    if (getenv("UCTRACE_FPU") && thread >= 0 && thread < nthreads) {
        CONTEXT fp; memset(&fp, 0, sizeof fp); fp.ContextFlags = CONTEXT_FLOATING_POINT;
        if (GetThreadContext(threads[thread].h, &fp)) { r->fp = fp.FloatSave; r->fp_valid = 1; }
        fp.ContextFlags = CONTEXT_EXTENDED_REGISTERS;
        if (GetThreadContext(threads[thread].h, &fp)) { memcpy(&r->mxcsr, fp.ExtendedRegisters+24, 4); r->mxcsr_valid = 1; }
    }
    memset(r->args, 0, sizeof r->args);
    rd(ctx->Esp + 4, r->args, sizeof r->args);
    memset(r->text0, 0, sizeof r->text0);
    if (point >= 0) rd(r->args[0], r->text0, sizeof r->text0 - sizeof(WCHAR));
    rd(ctx->Esp, &r->top, 4);
    if (point >= 0 && stop_label && !strcmp(evp[point].label, stop_label) && ++stop_hits == stop_after) {
        if(getenv("UCTRACE_CLOSE_ON_STOP")) {
            capture_window=NULL;capture_pid=GetProcessId(hProc);EnumWindows(capture_enum,0);
            if(!capture_window || !PostMessageW(capture_window,WM_CLOSE,0,0)) {fputs("controlled WM_CLOSE failed\n",stderr);exit(5);}
            fputs("controlled WM_CLOSE posted to debuggee window\n",stderr);
            return; /* keep tracing real cleanup until natural exit, with deadline fallback */
        }
        termination_reason = "event_limit";
        capture_client();
        if (!TerminateProcess(hProc, 0xE0000001u)) { fprintf(stderr, "uctrace: controlled stop failed\n"); exit(5); }
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

/* ANSI (CP_ACP) string -> ASCII-only JSON string: non-ASCII characters become \uXXXX of their UTF-16 value */
static void json_wstr(FILE* f, const WCHAR* w) {
    fputc('"', f);
    for (; *w; w++) {
        if (*w < 0x20 || *w >= 0x7F) { fprintf(f, "\\u%04x", (unsigned)*w); continue; }
        if (*w == '"' || *w == '\\') fputc('\\', f);
        fputc((char)*w, f);
    }
    fputc('"', f);
}
static void json_str(FILE* f, const char* s) {
    int n = MultiByteToWideChar(CP_ACP, 0, s, -1, NULL, 0);
    WCHAR* w = n > 0 ? malloc(n * sizeof(WCHAR)) : NULL;
    if (!w || !MultiByteToWideChar(CP_ACP, 0, s, -1, w, n)) { fputs("\"<unconvertible>\"", f); free(w); return; }
    json_wstr(f, w);
    free(w);
}

/* the raw remainder of the command line after `skip` arguments (same tokenizer as xrt_main.c's: whitespace
 * separated, double quotes toggle), so the debuggee sees exactly the argument text the harness passed */
static const WCHAR* raw_args_after(const WCHAR* p, int skip) {
    int inq = 0;
    while (skip-- > 0) {
        while (*p == L' ' || *p == L'\t') p++;
        while (*p && (inq || (*p != L' ' && *p != L'\t'))) { if (*p == L'"') inq = !inq; p++; }
    }
    while (*p == L' ' || *p == L'\t') p++;
    return p;
}

typedef struct { DWORD code, addr, ret; int mod; char type[64]; char text[201]; } ExRec;
#define MAX_EXCEPTIONS 32768
static ExRec exs[MAX_EXCEPTIONS]; static int nexs, exceptions_dropped;
typedef struct { DWORD newv, mask, caller; } CfRec;
static CfRec cfs[256]; static int ncfs;

int main(int argc, char** argv) {
    if (argc < 5) { fprintf(stderr, "usage: uctrace <entries-dir> <out.json> <stdout-file> <exe> [args...]\n"); return 2; }
    strncpy(entries_dir, argv[1], MAX_PATH - 1);
    if (getenv("UCTRACE_TIMEOUT_MS")) time_limit_ms = strtoul(getenv("UCTRACE_TIMEOUT_MS"), NULL, 10);
    stop_label = getenv("UCTRACE_STOP_LABEL");
    if (getenv("UCTRACE_STOP_AFTER")) stop_after = strtoul(getenv("UCTRACE_STOP_AFTER"), NULL, 10);
    if ((getenv("UCTRACE_TIMEOUT_MS") && !time_limit_ms) || !stop_after) return 2;
    if (getenv("UCTRACE_EVENTS")) load_event_points(getenv("UCTRACE_EVENTS"));
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
    if (nsite_names) call_records = calloc(MAX_CALL_RECORDS, sizeof(CallRec));
    bpmap = malloc(bpmap_size * sizeof(int));
    memset(bpmap, 0xFF, bpmap_size * sizeof(int));
    /* debuggee command line: the exe (quoted only when it contains blanks, as subprocess.list2cmdline and
     * xrt_ucc.exe do) followed by the raw argument text after <exe> on our own command line */
    WCHAR wexe[MAX_PATH], wcmd[8192];
    char cmd[8192];
    const WCHAR* rest = raw_args_after(GetCommandLineW(), 5);
    MultiByteToWideChar(CP_ACP, 0, argv[4], -1, wexe, MAX_PATH);
    _snwprintf(wcmd, 8191, wcschr(wexe, L' ') || wcschr(wexe, L'\t') ? L"\"%s\"%s%s" : L"%s%s%s", wexe, *rest ? L" " : L"", rest);
    wcmd[8191] = 0;
    WideCharToMultiByte(CP_ACP, 0, wcmd, -1, cmd, sizeof cmd, NULL, NULL);
    char dir[MAX_PATH]; strncpy(dir, argv[4], MAX_PATH - 1);
    char* sl = strrchr(dir, '\\'); if (sl) *sl = 0;
    WCHAR wdir[MAX_PATH];
    MultiByteToWideChar(CP_ACP, 0, dir, -1, wdir, MAX_PATH);
    SECURITY_ATTRIBUTES sa = {sizeof sa, NULL, TRUE};
    HANDLE hout = CreateFileA(argv[3], GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, 0, NULL);
    STARTUPINFOW si = {sizeof si}; PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESTDHANDLES; si.hStdOutput = hout; si.hStdError = hout; si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    if (!CreateProcessW(NULL, wcmd, NULL, NULL, TRUE, DEBUG_ONLY_THIS_PROCESS, NULL, wdir, &si, &pi)) {
        fprintf(stderr, "CreateProcess failed %lu\n", GetLastError()); return 1;
    }
    DWORD exit_code = 0; int done = 0;
    started = GetTickCount64();
    DEBUG_EVENT ev;
    while (!done) {
        if (time_limit_ms && GetTickCount64() - started >= time_limit_ms && !strcmp(termination_reason, "natural")) {
            termination_reason = "time_limit";
            if (!TerminateProcess(pi.hProcess, 0xE0000002u)) { fprintf(stderr, "uctrace: timeout termination failed\n"); return 5; }
        }
        if (!WaitForDebugEvent(&ev, time_limit_ms ? 100 : INFINITE)) {
            if (GetLastError() == ERROR_SEM_TIMEOUT) continue;
            break;
        }
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
        case UNLOAD_DLL_DEBUG_EVENT: {
            DWORD base = (DWORD)(ULONG_PTR)ev.u.UnloadDll.lpBaseOfDll;
            int mi = mod_of(base);
            if (mi >= 0 && mods[mi].base == base) {
                bp_forget_range(mods[mi].base, mods[mi].base + mods[mi].size);
                mods[mi].unloaded = 1;
            }
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
                if(b->music) {
                    int ti=thread_index(ev.dwThreadId);
                    music_break(&ctx,ti);
                    if(ti>=0){ctx.EFlags|=0x100;threads[ti].rearm=addr;}
                }
                if (b->ev >= 0) {
                    int ti = thread_index(ev.dwThreadId);
                    log_event(b->ev, -1, ti, &ctx);
                    if (ti >= 0) { ctx.EFlags |= 0x100; threads[ti].rearm = addr; }   /* persistent: re-arm after one step */
                }
                if (b->kind == 4) {
                    /* event point only */
                } else if (b->kind == 1 || b->kind == 3) {
                    if (b->mod >= 0 && b->kind == 1) { Mod* m = &mods[b->mod]; m->hit_order[m->nhit++] = addr - m->base; }
                    order_counter++;
                    if (b->kind == 3 || (b->mod >= 0 && addr == mods[b->mod].entry)) hook_imports(b->mod);
                    if (b->ev < 0) b->kind = 0;   /* one-shot (an event point keeps it armed) */
                    else b->kind = 4;
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
                            if (ncalls < MAX_CALL_RECORDS) {
                                CallRec* r = &call_records[ncalls++];
                                r->imp = b->imp; r->thread = thread_index(ev.dwThreadId); r->seq = ++ev_seq; r->ret = ret;
                                rd(ctx.Esp + 4, r->args, sizeof r->args);
                                for (int k = 0; k < 3; k++) {
                                    rd(r->args[k], r->a[k], sizeof r->a[k] - 1);
                                    rd(r->args[k], r->w[k], sizeof r->w[k] - sizeof(WCHAR));
                                }
                            } else calls_dropped++;
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
                if (nexs < MAX_EXCEPTIONS) {
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
                    exs[nexs].code = er->ExceptionCode; exs[nexs].addr = addr; exs[nexs].ret = ret; exs[nexs].mod = mod_of(ret ? ret : addr);
                    if (evlog) log_event(-1, nexs, thread_index(ev.dwThreadId), &ctx);
                    nexs++;
                } else exceptions_dropped++;
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
    int terminated = WaitForSingleObject(pi.hProcess, 30000) == WAIT_OBJECT_0;
    if (!terminated) {
        fprintf(stderr, "uctrace: debuggee process did not terminate after EXIT_PROCESS\n");
        done = 0;                         /* report the trace as incomplete (exit status 4) */
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    jout = fopen(argv[2], "w");
    if (!jout) { fprintf(stderr, "uctrace: cannot write %s\n", argv[2]); return 3; }
    fprintf(jout, "{\n \"run_id\": "); json_str(jout, getenv("UCTRACE_RUN_ID") ? getenv("UCTRACE_RUN_ID") : "");
    fprintf(jout, ",\n \"complete\": %s", done ? "true" : "false");
    fprintf(jout, ",\n \"debuggee_terminated\": %s", terminated ? "true" : "false");
    fprintf(jout, ",\n \"termination_reason\": \"%s\", \"time_limit_ms\": %lu, \"stop_hits\": %u",
            termination_reason, time_limit_ms, stop_hits);
    fprintf(jout, ",\n \"command\": "); json_wstr(jout, wcmd);
    fprintf(jout, ",\n \"exit_code\": %lu,\n \"threads\": %d,\n \"modules\": [\n", exit_code, nthreads);
    for (int i = 0; i < nmods; i++) {
        Mod* m = &mods[i];
        fprintf(jout, "  {\"name\": "); json_str(jout, m->name);
        fprintf(jout, ", \"path\": "); json_str(jout, m->path);
        fprintf(jout, ", \"base\": \"0x%08lx\", \"size\": %lu, \"unloaded\": %d, \"instrumented\": %d, \"entries\": %d, \"hit\": %d, \"hit_rvas\": [",
                m->base, m->size, m->unloaded, m->instrumented, m->nentries, m->nhit);
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
    fprintf(jout, "\n ],\n \"calls_dropped\": %d, \"selected_calls\": [", calls_dropped);
    for (int i = 0; i < ncalls; i++) {
        CallRec* r = &call_records[i];
        fprintf(jout, "%s\n {\"seq\": %d, \"thread\": %d, \"import\": ", i ? "," : "", r->seq, r->thread);
        json_str(jout, imps[r->imp].name);
        fprintf(jout, ", \"return_address\": \"0x%08lx\", \"args\": [", r->ret);
        for (int k = 0; k < 8; k++) fprintf(jout, "%s\"%08lx\"", k ? "," : "", r->args[k]);
        fputs("], \"diagnostic_ansi\": [", jout);
        for (int k = 0; k < 3; k++) { if (k) fputc(',', jout); json_str(jout, r->a[k]); }
        fputs("], \"diagnostic_wide\": [", jout);
        for (int k = 0; k < 3; k++) { if (k) fputc(',', jout); json_wstr(jout, r->w[k]); }
        fputs("]}", jout);
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
    fprintf(jout, "\n ],\n \"exceptions_dropped\": %d,\n \"controlfp_calls\": [", exceptions_dropped);
    for (int i = 0; i < ncfs; i++)
        fprintf(jout, "%s{\"new\": \"0x%08lx\", \"mask\": \"0x%08lx\", \"caller\": \"0x%08lx\"}", i ? ", " : "", cfs[i].newv, cfs[i].mask, cfs[i].caller);
    fprintf(jout, "],\n \"event_points\": %d,\n \"events_dropped\": %d,\n \"events\": [", nevp, evdropped);
    for (int i = 0; i < nevlog; i++) {
        EvRec* r = &evlog[i];
        fprintf(jout, "%s\n  {\"seq\": %d, \"thread\": %d, ", i ? "," : "", r->seq, r->thread);
        if (r->point >= 0) {
            fprintf(jout, "\"kind\": \"point\", \"label\": "); json_str(jout, evp[r->point].label);
            fprintf(jout, ", \"module\": "); json_str(jout, evp[r->point].mod);
            fprintf(jout, ", \"rva\": \"0x%lx\"", evp[r->point].rva);
        } else {
            fprintf(jout, "\"kind\": \"exception\", \"index\": %d, \"code\": \"0x%08lx\", \"caller\": \"0x%08lx\"",
                    r->exc, exs[r->exc].code, exs[r->exc].ret);
        }
        fprintf(jout, ", \"esp\": \"0x%08lx\", \"stack_top\": \"0x%08lx\", \"eax\": \"0x%08lx\", \"ebp\": \"0x%08lx\", "
                "\"ecx\": \"0x%08lx\", \"edx\": \"0x%08lx\", \"esi\": \"0x%08lx\", \"edi\": \"0x%08lx\", \"stack_args\": [",
                r->esp, r->top, r->eax, r->ebp, r->ecx, r->edx, r->esi, r->edi);
        for (int k = 0; k < 12; k++) fprintf(jout, "%s\"%08lx\"", k ? "," : "", r->args[k]);
        fputs("], \"diagnostic_arg0_wide\": ", jout);
        json_wstr(jout, r->text0);
        if (r->fp_valid) {
            fprintf(jout, ", \"x87\": {\"cw\": \"%04lx\", \"sw\": \"%04lx\", \"tag\": \"%04lx\", \"registers80\": [",
                    r->fp.ControlWord & 0xffff, r->fp.StatusWord & 0xffff, r->fp.TagWord & 0xffff);
            for (int k = 0; k < 8; k++) {
                fprintf(jout, "%s\"", k ? "," : "");
                for (int j = 9; j >= 0; j--) fprintf(jout, "%02x", r->fp.RegisterArea[10*k+j]);
                fputc('"', jout);
            }
            fputs("]}", jout);
        }
        if (r->mxcsr_valid) fprintf(jout, ", \"mxcsr\": \"%08lx\"", r->mxcsr);
        fputs("}", jout);
    }
    fprintf(jout, "\n ],\n \"x87_control_words_seen\": [");
    for (int i = 0; i < ncws; i++) { fprintf(jout, "%s{\"cw\": \"0x%04x\", \"first_seen_at\": ", i ? ", " : "", cws[i]); json_str(jout, cw_where[i]); fprintf(jout, "}"); }
    fprintf(jout, "]\n}\n");
    if (fclose(jout) != 0) { fprintf(stderr, "uctrace: error writing %s\n", argv[2]); return 3; }
    printf("uctrace: exit=%lu modules=%d imports_used=%d exceptions=%d\n", exit_code, nmods, nimps, nexs);
    return done ? 0 : 4;   /* 4: the debug loop ended before the debuggee's EXIT_PROCESS event */
}
