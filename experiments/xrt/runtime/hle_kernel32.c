/* hle_kernel32.c - host adapters for the KERNEL32.dll imports used on the measured Core/UCC paths (stdcall).
 *
 * Guest handles are small table indices (never host HANDLE values). Structures that contain pointer-sized
 * fields (SYSTEM_INFO, MEMORYSTATUS, working-set sizes) are marshalled to their 32-bit layouts with the
 * values a 32-bit, non large-address-aware process would see. File-system access goes to the host file
 * system relative to the sandbox the run was started in: any create/write/attribute change, directory
 * change or deletion that resolves outside the sandbox root is refused as fatal. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"

#pragma warning(disable : 4996)   /* GetVersionExA: the guest calls it, so we must too */

/* ---------------------------------------------------------------- handles */
typedef struct HandleSlot { int type; void* host; } HandleSlot;
static HandleSlot handles[4096];
static SRWLOCK handle_lock = SRWLOCK_INIT;
#define HANDLE_BASE 0x1000u

uint32_t xrt_handle_new(int type, void* host) {
    uint32_t i;
    AcquireSRWLockExclusive(&handle_lock);
    for (i = 1; i < sizeof handles / sizeof handles[0]; i++)
        if (handles[i].type == XH_FREE) {
            handles[i].type = type;
            handles[i].host = host;
            ReleaseSRWLockExclusive(&handle_lock);
            return HANDLE_BASE + 4u * i;
        }
    ReleaseSRWLockExclusive(&handle_lock);
    xrt_fatal(NULL, XRT_EXIT_SETUP, "guest handle table full");
}

static HandleSlot* slot(uint32_t h) {
    uint32_t i;
    if (h < HANDLE_BASE || (h & 3))
        return NULL;
    i = (h - HANDLE_BASE) / 4u;
    return i < sizeof handles / sizeof handles[0] && handles[i].type != XH_FREE ? &handles[i] : NULL;
}
int xrt_handle_type(uint32_t h) { HandleSlot* s = slot(h); return s ? s->type : XH_FREE; }
void* xrt_handle_get(uint32_t h, int type) { HandleSlot* s = slot(h); return s && s->type == type ? s->host : NULL; }
void xrt_handle_free(uint32_t h) {
    HandleSlot* s = slot(h);
    if (s) {
        s->type = XH_FREE;
        s->host = NULL;
    }
}

/* ---------------------------------------------------------------- sandbox guard */
int xrt_path_is_inside_sandbox(const uint16_t* path) {
    WCHAR full[MAX_PATH * 2], root[MAX_PATH * 2];
    size_t n;
    if (!GetFullPathNameW((LPCWSTR)path, MAX_PATH * 2, full, NULL))
        return 0;
    MultiByteToWideChar(CP_ACP, 0, xrt_sandbox_root, -1, root, MAX_PATH * 2);
    n = wcslen(root);
    return !_wcsnicmp(full, root, n) && (full[n] == L'\\' || full[n] == 0);
}

static void require_sandbox(CPU* c, const uint16_t* path, const char* op) {
    if (!xrt_path_is_inside_sandbox(path)) {
        char a[600];
        WideCharToMultiByte(CP_ACP, 0, (LPCWSTR)path, -1, a, sizeof a, NULL, NULL);
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "%s outside the sandbox refused: \"%s\"", op, a);
    }
}

static void set_err_from_host(CPU* c) { xrt_set_last_error(c, GetLastError()); }

/* ---------------------------------------------------------------- files */
/* file_open events for the report: the first MAX_OPEN_EVENTS opens, with the path as the guest passed it and as
 * resolved against the current directory ("<sandbox>\..." when inside the run's sandbox) */
#define MAX_OPEN_EVENTS 512
static long open_events;
static void file_open_event(const char* path, uint32_t access, uint32_t disp, int ok) {
    char full[600], rel[620], j[700], k[700];
    size_t n = strlen(xrt_sandbox_root);
    if (InterlockedIncrement(&open_events) > MAX_OPEN_EVENTS)
        return;
    if (!GetFullPathNameA(path, sizeof full, full, NULL))
        snprintf(full, sizeof full, "%s", path);
    if (n && !_strnicmp(full, xrt_sandbox_root, n) && full[n] == '\\')
        snprintf(rel, sizeof rel, "<sandbox>%s", full + n);
    else
        snprintf(rel, sizeof rel, "%s", full);
    xrt_event("file_open", "\"path\": %s, \"resolved\": %s, \"access\": \"0x%08x\", \"disposition\": %u, \"ok\": %s",
              xrt_jstr(j, sizeof j, path), xrt_jstr(k, sizeof k, rel), access, disp, ok ? "true" : "false");
}

static uint32_t create_file(CPU* c, const uint16_t* name, uint32_t access, uint32_t share, uint32_t sa, uint32_t disp,
                            uint32_t flags, uint32_t tmpl) {
    HANDLE h;
    char a[600];
    if (sa || tmpl)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "CreateFile with security attributes or a template is not implemented");
    if (flags & FILE_FLAG_OVERLAPPED)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "overlapped file I/O is not implemented");
    if ((access & (GENERIC_WRITE | GENERIC_ALL | FILE_WRITE_DATA | FILE_APPEND_DATA | DELETE)) ||
        disp == CREATE_ALWAYS || disp == CREATE_NEW || disp == OPEN_ALWAYS || disp == TRUNCATE_EXISTING)
        require_sandbox(c, name, "file creation/write");
    h = CreateFileW((LPCWSTR)name, access, share, NULL, disp, flags, NULL);
    WideCharToMultiByte(CP_ACP, 0, (LPCWSTR)name, -1, a, sizeof a, NULL, NULL);
    file_open_event(a, access, disp, h != INVALID_HANDLE_VALUE);
    if (h == INVALID_HANDLE_VALUE) {
        set_err_from_host(c);
        xrt_log("CreateFile(\"%s\", %08x, disp %u) -> failed, error %u", a, access, disp, xrt_get_last_error(c));
        return 0xFFFFFFFFu;
    }
    {
        uint32_t g = xrt_handle_new(XH_FILE, h);
        xrt_set_last_error(c, GetLastError());     /* ERROR_ALREADY_EXISTS etc. are reported on success too */
        xrt_log("CreateFile(\"%s\", %08x, disp %u) -> handle %x", a, access, disp, g);
        return g;
    }
}

static void hle_CreateFileW(CPU* c) {
    RET_STD(7, create_file(c, (const uint16_t*)G2H(ARG(0)), ARG(1), ARG(2), ARG(3), ARG(4), ARG(5), ARG(6)));
}
static void hle_CreateFileA(CPU* c) {
    WCHAR w[MAX_PATH * 2];
    if (!MultiByteToWideChar(CP_ACP, 0, (LPCSTR)G2H(ARG(0)), -1, w, MAX_PATH * 2))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "CreateFileA: path conversion failed");
    RET_STD(7, create_file(c, (const uint16_t*)w, ARG(1), ARG(2), ARG(3), ARG(4), ARG(5), ARG(6)));
}

static HANDLE file_of(CPU* c, uint32_t h) {
    HANDLE f = (HANDLE)xrt_handle_get(h, XH_FILE);
    if (!f)
        xrt_set_last_error(c, ERROR_INVALID_HANDLE);
    return f;
}

static void hle_ReadFile(CPU* c) {
    HANDLE f = file_of(c, ARG(0));
    DWORD got = 0;
    BOOL ok;
    if (ARG(4))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "ReadFile with OVERLAPPED is not implemented");
    if (!f) {
        RET_STD(5, 0);
        return;
    }
    ok = ReadFile(f, ARG(2) ? G2H(ARG(1)) : NULL, ARG(2), &got, NULL);
    if (!ok)
        set_err_from_host(c);
    if (ARG(3))
        wr32(ARG(3), got);
    RET_STD(5, ok);
}

static void hle_WriteFile(CPU* c) {
    HANDLE f = file_of(c, ARG(0));
    DWORD put = 0;
    BOOL ok;
    if (ARG(4))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "WriteFile with OVERLAPPED is not implemented");
    if (!f) {
        RET_STD(5, 0);
        return;
    }
    ok = WriteFile(f, ARG(2) ? G2H(ARG(1)) : NULL, ARG(2), &put, NULL);
    if (!ok)
        set_err_from_host(c);
    if (ARG(3))
        wr32(ARG(3), put);
    RET_STD(5, ok);
}

static void hle_SetFilePointer(CPU* c) {
    HANDLE f = file_of(c, ARG(0));
    LONG hi = ARG(2) ? (LONG)rd32(ARG(2)) : 0;
    DWORD r;
    if (!f) {
        RET_STD(4, 0xFFFFFFFFu);
        return;
    }
    r = SetFilePointer(f, (LONG)ARG(1), ARG(2) ? &hi : NULL, ARG(3));
    if (r == INVALID_SET_FILE_POINTER)
        set_err_from_host(c);
    else
        xrt_set_last_error(c, NO_ERROR);
    if (ARG(2))
        wr32(ARG(2), (uint32_t)hi);
    RET_STD(4, r);
}

static void hle_GetFileSize(CPU* c) {
    HANDLE f = file_of(c, ARG(0));
    DWORD hi = 0, r;
    if (!f) {
        RET_STD(2, 0xFFFFFFFFu);
        return;
    }
    r = GetFileSize(f, ARG(1) ? &hi : NULL);
    if (r == INVALID_FILE_SIZE)
        set_err_from_host(c);
    if (ARG(1))
        wr32(ARG(1), hi);
    RET_STD(2, r);
}

static void hle_CloseHandle(CPU* c) {
    uint32_t h = ARG(0);
    int t = xrt_handle_type(h);
    BOOL ok = TRUE;
    if (h == 0xFFFFFFFFu) {         /* GetCurrentProcess() pseudo handle */
        RET_STD(1, 1);
        return;
    }
    if (t == XH_FILE || t == XH_THREAD) {
        ok = CloseHandle((HANDLE)xrt_handle_get(h, t));
        xrt_handle_free(h);
        if (t == XH_THREAD)
            xrt_log("CloseHandle(thread handle %x): handle closed, the thread itself keeps running", h);
    } else {
        ok = FALSE;
        xrt_set_last_error(c, ERROR_INVALID_HANDLE);
    }
    RET_STD(1, ok);
}

static void hle_SetFileAttributesW(CPU* c) {
    const uint16_t* p = (const uint16_t*)G2H(ARG(0));
    BOOL ok;
    require_sandbox(c, p, "SetFileAttributes");
    ok = SetFileAttributesW((LPCWSTR)p, ARG(1));
    if (!ok)
        set_err_from_host(c);
    RET_STD(2, ok);
}

static void hle_DeleteFileW(CPU* c) {
    const uint16_t* p = (const uint16_t*)G2H(ARG(0));
    BOOL ok;
    require_sandbox(c, p, "DeleteFile");
    ok = DeleteFileW((LPCWSTR)p);
    if (!ok)
        set_err_from_host(c);
    RET_STD(1, ok);
}

/* MoveFileW (UCC's package save: temporary file, then rename): both names must be inside the sandbox. Recorded as an
 * evidence event with both names relative to the sandbox. */
static const char* sandbox_rel(char* out, size_t n, const uint16_t* p) {
    char full[600];
    size_t k = strlen(xrt_sandbox_root);
    WCHAR w[MAX_PATH * 2];
    if (!GetFullPathNameW((LPCWSTR)p, MAX_PATH * 2, w, NULL))
        lstrcpynW(w, (LPCWSTR)p, MAX_PATH * 2);
    WideCharToMultiByte(CP_ACP, 0, w, -1, full, sizeof full, NULL, NULL);
    if (k && !_strnicmp(full, xrt_sandbox_root, k) && full[k] == '\\')
        snprintf(out, n, "<sandbox>%s", full + k);
    else
        snprintf(out, n, "%s", full);
    return out;
}
static void hle_MoveFileW(CPU* c) {
    const uint16_t *from = (const uint16_t*)G2H(ARG(0)), *to = (const uint16_t*)G2H(ARG(1));
    char a[620], b[620], j1[700], j2[700];
    BOOL ok;
    require_sandbox(c, from, "MoveFile (source)");
    require_sandbox(c, to, "MoveFile (destination)");
    ok = MoveFileW((LPCWSTR)from, (LPCWSTR)to);
    if (!ok)
        set_err_from_host(c);
    xrt_log("MoveFileW(\"%s\", \"%s\") -> %d", sandbox_rel(a, sizeof a, from), sandbox_rel(b, sizeof b, to), ok);
    xrt_event("move_file", "\"from\": %s, \"to\": %s, \"ok\": %s", xrt_jstr(j1, sizeof j1, a), xrt_jstr(j2, sizeof j2, b),
              ok ? "true" : "false");
    RET_STD(2, ok);
}

static void hle_SetCurrentDirectoryW(CPU* c) {
    const uint16_t* p = (const uint16_t*)G2H(ARG(0));
    BOOL ok;
    char a[600];
    require_sandbox(c, p, "SetCurrentDirectory");
    ok = SetCurrentDirectoryW((LPCWSTR)p);
    if (!ok)
        set_err_from_host(c);
    WideCharToMultiByte(CP_ACP, 0, (LPCWSTR)p, -1, a, sizeof a, NULL, NULL);
    xrt_log("SetCurrentDirectoryW(\"%s\") -> %d", a, ok);
    RET_STD(1, ok);
}

static void hle_GetCurrentDirectoryW(CPU* c) {
    DWORD r = GetCurrentDirectoryW(ARG(0), ARG(0) ? (LPWSTR)G2H(ARG(1)) : NULL);
    if (!r)
        set_err_from_host(c);
    RET_STD(2, r);
}

/* WIN32_FIND_DATAW has no pointer-sized fields: identical layout for 32- and 64-bit code */
typedef char find_data_layout_check[sizeof(WIN32_FIND_DATAW) == 592 ? 1 : -1];

static void hle_FindFirstFileW(CPU* c) {
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((LPCWSTR)G2H(ARG(0)), &fd);
    if (h == INVALID_HANDLE_VALUE) {
        set_err_from_host(c);
        RET_STD(2, 0xFFFFFFFFu);
        return;
    }
    memcpy(G2H(ARG(1)), &fd, sizeof fd);
    RET_STD(2, xrt_handle_new(XH_FIND, h));
}

static void hle_FindNextFileW(CPU* c) {
    WIN32_FIND_DATAW fd;
    HANDLE h = (HANDLE)xrt_handle_get(ARG(0), XH_FIND);
    BOOL ok;
    if (!h) {
        xrt_set_last_error(c, ERROR_INVALID_HANDLE);
        RET_STD(2, 0);
        return;
    }
    ok = FindNextFileW(h, &fd);
    if (ok)
        memcpy(G2H(ARG(1)), &fd, sizeof fd);
    else
        set_err_from_host(c);
    RET_STD(2, ok);
}

static void hle_FindClose(CPU* c) {
    HANDLE h = (HANDLE)xrt_handle_get(ARG(0), XH_FIND);
    BOOL ok = FALSE;
    if (h) {
        ok = FindClose(h);
        xrt_handle_free(ARG(0));
    } else {
        xrt_set_last_error(c, ERROR_INVALID_HANDLE);
    }
    RET_STD(1, ok);
}

/* ---------------------------------------------------------------- process and modules */
static void hle_GetCommandLineA(CPU* c) { RET_STD(0, xrt_cmdline_a); }
static void hle_GetCurrentProcess(CPU* c) { RET_STD(0, 0xFFFFFFFFu); }
static void hle_GetLastError(CPU* c) { RET_STD(0, xrt_get_last_error(c)); }

static int is_kernel32(const char* name) {
    const char *b = name, *p;
    for (p = name; *p; p++)
        if (*p == '\\' || *p == '/' || *p == ':')
            b = p + 1;
    return !_stricmp(b, "kernel32") || !_stricmp(b, "kernel32.dll");
}

/* GetModuleHandleA: NULL is UCC.exe; a translated module its base; kernel32.dll (which every process has) the
 * runtime's handle for it (XRT_KERNEL32_HANDLE: GetProcAddress on it resolves to host adapters; the system DLL's
 * image is not mapped). Any other name is not loaded in this process: NULL, ERROR_MOD_NOT_FOUND. */
static void hle_GetModuleHandleA(CPU* c) {
    uint32_t n = ARG(0);
    XrtModule* m;
    if (!n) {
        RET_STD(1, xrt_module_get(0) ? 0x00400000u : 0);
        return;
    }
    if (is_kernel32((const char*)G2H(n))) {
        xrt_log("GetModuleHandleA(\"%s\") -> %08x (kernel32.dll: host adapters)", (const char*)G2H(n), XRT_KERNEL32_HANDLE);
        RET_STD(1, XRT_KERNEL32_HANDLE);
        return;
    }
    m = xrt_module_by_name((const char*)G2H(n));
    xrt_log("GetModuleHandleA(\"%s\") -> %08x", (const char*)G2H(n), m ? m->base : 0);
    if (!m)
        xrt_set_last_error(c, ERROR_MOD_NOT_FOUND);
    RET_STD(1, m ? m->base : 0);
}

static XrtModule* module_of_handle(uint32_t h) {
    int i;
    if (!h)
        h = 0x00400000u;
    for (i = 0; i < xrt_module_count(); i++)
        if (xrt_module_get(i)->base == h)
            return xrt_module_get(i);
    return NULL;
}

static void hle_GetModuleFileNameA(CPU* c) {
    XrtModule* m = module_of_handle(ARG(0));
    uint32_t buf = ARG(1), n = ARG(2), len;
    if (!m) {
        xrt_set_last_error(c, ERROR_MOD_NOT_FOUND);
        RET_STD(3, 0);
        return;
    }
    len = (uint32_t)strlen(m->path);
    if (!n) {
        xrt_set_last_error(c, ERROR_INSUFFICIENT_BUFFER);
        RET_STD(3, 0);
        return;
    }
    if (len >= n) {                   /* Vista+ semantics (what the original saw under WOW64) */
        memcpy(G2H(buf), m->path, n - 1);
        wr8(buf + n - 1, 0);
        xrt_set_last_error(c, ERROR_INSUFFICIENT_BUFFER);
        RET_STD(3, n);
        return;
    }
    memcpy(G2H(buf), m->path, len + 1);
    RET_STD(3, len);
}

/* LoadLibrary: a mapped translated module returns its base (one more reference). An existing DLL that is a
 * translated module linked into this host is mapped with its translated static imports and initialised
 * (xrt_load_library). A file that does not exist fails exactly as on Windows (NULL, ERROR_MOD_NOT_FOUND) - the
 * engine probes a DLL for every package, e.g. "Transient", and expects that failure. Any other existing DLL cannot
 * be emulated and is fatal. Windows appends ".dll" to a name without an extension. */
static uint64_t loadlib_missing;
static void loadlib_event(const char* path, uint32_t result, uint32_t site) {   /* evidence: file name, result, caller */
    const char *b = path, *p;
    char q[300];
    for (p = path; *p; p++)
        if (*p == '\\' || *p == '/' || *p == ':')
            b = p + 1;
    xrt_event("load_library", "\"name\": %s, \"result\": \"0x%08x\", \"site\": \"0x%08x\"", xrt_jstr(q, sizeof q, b), result,
              site);
}
static uint32_t load_library(CPU* c, WCHAR* w, const char* api, uint32_t site) {   /* w: MAX_PATH * 2 buffer */
    WCHAR sys[MAX_PATH];
    char a[600];
    XrtModule* m;
    const WCHAR *base, *q;
    for (base = q = w; *q; q++)
        if (*q == L'\\' || *q == L'/' || *q == L':')
            base = q + 1;
    if (!wcschr(base, L'.'))
        wcscat(w, L".dll");
    WideCharToMultiByte(CP_ACP, 0, w, -1, a, sizeof a, NULL, NULL);
    m = xrt_module_by_name(a);
    if (m) {
        xrt_load_library(c, m->path);
        xrt_log("%s(\"%s\") -> translated %s at %08x", api, a, m->name, m->base);
        loadlib_event(a, m->base, site);
        return m->base;
    }
    if (GetFileAttributesW(w) != INVALID_FILE_ATTRIBUTES) {
        char full[600];
        if (!GetFullPathNameA(a, sizeof full, full, NULL) || !(m = xrt_load_library(c, full)))
            xrt_fatal(c, XRT_EXIT_IMPORT, "%s(\"%s\"): the DLL exists but is not part of this translated runtime", api, a);
        xrt_log("%s(\"%s\") -> loaded translated %s at %08x", api, a, m->name, m->base);
        loadlib_event(a, m->base, site);
        return m->base;
    }
    GetSystemDirectoryW(sys, MAX_PATH);
    if (base == w) {
        WCHAR s2[MAX_PATH * 2];
        _snwprintf(s2, MAX_PATH * 2, L"%s\\%s", sys, w);
        if (GetFileAttributesW(s2) != INVALID_FILE_ATTRIBUTES)
            xrt_fatal(c, XRT_EXIT_IMPORT, "%s(\"%s\"): loading a system DLL dynamically is not supported", api, a);
    }
    loadlib_missing++;
    xrt_log("%s(\"%s\") -> NULL (no such file, ERROR_MOD_NOT_FOUND as on Windows)", api, a);
    loadlib_event(a, 0, site);
    xrt_set_last_error(c, ERROR_MOD_NOT_FOUND);
    return 0;
}

static void hle_LoadLibraryW(CPU* c) {
    WCHAR w[MAX_PATH * 2];
    uint32_t site = rd32(c->r[ESP]);
    lstrcpynW(w, (LPCWSTR)G2H(ARG(0)), MAX_PATH);
    RET_STD(1, load_library(c, w, "LoadLibraryW", site));
}

static void hle_LoadLibraryA(CPU* c) {
    WCHAR w[MAX_PATH * 2];
    uint32_t site = rd32(c->r[ESP]);
    if (!MultiByteToWideChar(CP_ACP, 0, (LPCSTR)G2H(ARG(0)), -1, w, MAX_PATH))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "LoadLibraryA: name conversion failed");
    RET_STD(1, load_library(c, w, "LoadLibraryA", site));
}

/* GetPrivateProfileStringA: the host API on the same arguments (a file name without a path is read from the
 * Windows directory, as for the original; reading outside the sandbox is allowed, writing profile strings is not
 * bound). Recorded as an evidence event. */
static void hle_GetPrivateProfileStringA(CPU* c) {
    LPCSTR app = ARG(0) ? (LPCSTR)G2H(ARG(0)) : NULL, key = ARG(1) ? (LPCSTR)G2H(ARG(1)) : NULL;
    LPCSTR def = ARG(2) ? (LPCSTR)G2H(ARG(2)) : NULL, file = ARG(5) ? (LPCSTR)G2H(ARG(5)) : NULL;
    DWORD r = GetPrivateProfileStringA(app, key, def, ARG(3) ? (LPSTR)G2H(ARG(3)) : NULL, ARG(4), file);
    char q1[300], q2[300], q3[300];
    xrt_set_last_error(c, GetLastError());
    xrt_event("profile_read", "\"file\": %s, \"section\": %s, \"key\": %s, \"result\": %u", xrt_jstr(q1, sizeof q1, file ? file : ""),
              xrt_jstr(q2, sizeof q2, app ? app : ""), xrt_jstr(q3, sizeof q3, key ? key : ""), r);
    RET_STD(6, r);
}

static void hle_FreeLibrary(CPU* c) {
    XrtModule* m = module_of_handle(ARG(0));
    RET_STD(1, m ? xrt_free_library(c, m) : 0);
}

/* GetProcAddress: a translated module's export; on kernel32.dll's handle the stub of the host adapter of that name.
 * A kernel32 function without an adapter (or looked up by ordinal) is fatal: whether the original's kernel32 would
 * have returned it or NULL is not modelled. */
static uint64_t gpa_calls, gpa_misses;
static void hle_GetProcAddress(CPU* c) {
    XrtModule* m = module_of_handle(ARG(0));
    uint32_t n = ARG(1), r;
    if (ARG(0) == XRT_KERNEL32_HANDLE) {
        char q[300];
        if (!(n >> 16))
            xrt_fatal(c, XRT_EXIT_IMPORT, "GetProcAddress(kernel32.dll, ordinal %u) is not supported", n);
        if (!(r = xrt_hle_proc("kernel32.dll", (const char*)G2H(n))))
            xrt_fatal(c, XRT_EXIT_IMPORT, "GetProcAddress(kernel32.dll, \"%s\"): no host adapter for this function",
                      (const char*)G2H(n));
        gpa_calls++;
        xrt_log("GetProcAddress(kernel32.dll, \"%s\") -> adapter stub %08x", (const char*)G2H(n), r);
        xrt_event("get_proc_address", "\"module\": \"kernel32.dll\", \"name\": %s, \"result\": \"0x%08x\"",
                  xrt_jstr(q, sizeof q, (const char*)G2H(n)), r);
        RET_STD(2, r);
        return;
    }
    if (!m || !ARG(0))
        xrt_fatal(c, XRT_EXIT_IMPORT, "GetProcAddress on module handle %08x, which is not a translated module", ARG(0));
    gpa_calls++;
    r = (n >> 16) ? xrt_module_export(m, (const char*)G2H(n), 0) : xrt_module_export(m, NULL, n & 0xFFFF);
    if (!r) {
        gpa_misses++;
        xrt_set_last_error(c, ERROR_PROC_NOT_FOUND);
    }
    RET_STD(2, r);
}

/* FreeConsole (GlmLib.dll's initialisation calls it once). The console is not modelled: in the measured runs the
 * guest's stdout is a file (redirected by the harness), whose later output FreeConsole does not affect; the host
 * keeps its console. With stdout on a console the original would lose its later output: not modelled. */
static void hle_FreeConsole(CPU* c) {
    xrt_log("FreeConsole: recorded; the console is not modelled (the host keeps its console)");
    xrt_event("free_console", NULL);
    RET_STD(0, 1);
}

static void hle_SetConsoleCtrlHandler(CPU* c) {
    char d[512];
    xrt_describe(d, sizeof d, ARG(0));
    xrt_log("SetConsoleCtrlHandler(%s, %u): recorded; console control events are not forwarded to the guest", d, ARG(1));
    RET_STD(2, 1);
}

static void hle_GetProcessWorkingSetSize(CPU* c) {
    SIZE_T mn = 0, mx = 0;
    BOOL ok;
    if (ARG(0) != 0xFFFFFFFFu)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "GetProcessWorkingSetSize on a process other than the current one");
    ok = GetProcessWorkingSetSize(GetCurrentProcess(), &mn, &mx);
    wr32(ARG(1), (uint32_t)(mn > 0xFFFFFFFFu ? 0xFFFFFFFFu : mn));
    wr32(ARG(2), (uint32_t)(mx > 0xFFFFFFFFu ? 0xFFFFFFFFu : mx));
    RET_STD(3, ok);
}

/* SYSTEM_INFO as a 32-bit process under WOW64 sees it */
static void hle_GetSystemInfo(CPU* c) {
    SYSTEM_INFO si;
    uint32_t p = ARG(0);
    GetNativeSystemInfo(&si);
    wr16(p + 0, PROCESSOR_ARCHITECTURE_INTEL);
    wr16(p + 2, 0);
    wr32(p + 4, si.dwPageSize);
    wr32(p + 8, 0x00010000u);
    wr32(p + 12, 0x7FFEFFFFu);
    wr32(p + 16, (uint32_t)si.dwActiveProcessorMask);
    wr32(p + 20, si.dwNumberOfProcessors > 32 ? 32 : si.dwNumberOfProcessors);
    wr32(p + 24, PROCESSOR_INTEL_PENTIUM);
    wr32(p + 28, si.dwAllocationGranularity);
    wr16(p + 32, si.wProcessorLevel);
    wr16(p + 34, si.wProcessorRevision);
    RET_STD(1, 0);
}

/* MEMORYSTATUS for a non large-address-aware 32-bit process under WOW64: physical memory is capped at 2 GB
 * and page-file figures at 4 GB - 1 (both observed in the original's UCC.log: Phys=2097151K Pagef=4194303K);
 * the virtual figures describe the guest's 2 GB user space. */
static void hle_GlobalMemoryStatus(CPU* c) {
    MEMORYSTATUSEX ms;
    uint32_t p = ARG(0);
    uint64_t a, f, b;
    uint32_t hw;
    ms.dwLength = sizeof ms;
    GlobalMemoryStatusEx(&ms);
    xrt_heap_stats(&a, &f, &b, &hw);
#define CAP2G(v) ((uint32_t)((v) > 0x7FFFFFFFull ? 0x7FFFFFFFull : (v)))
#define CAP4G(v) ((uint32_t)((v) > 0xFFFFFFFFull ? 0xFFFFFFFFull : (v)))
    wr32(p + 0, 32);
    wr32(p + 4, ms.dwMemoryLoad);
    wr32(p + 8, CAP2G(ms.ullTotalPhys));
    wr32(p + 12, CAP2G(ms.ullAvailPhys));
    wr32(p + 16, CAP4G(ms.ullTotalPageFile));
    wr32(p + 20, CAP4G(ms.ullAvailPageFile));
    wr32(p + 24, 0x7FFE0000u);
    wr32(p + 28, 0x7FFE0000u - hw - 0x01000000u);
#undef CAP2G
#undef CAP4G
    RET_STD(1, 0);
}

static void hle_GetVersionExA(CPU* c) {
    OSVERSIONINFOEXA v;
    uint32_t p = ARG(0), size = rd32(p);
    BOOL ok;
    if (size != sizeof(OSVERSIONINFOA) && size != sizeof(OSVERSIONINFOEXA)) {
        xrt_set_last_error(c, ERROR_INSUFFICIENT_BUFFER);
        RET_STD(1, 0);
        return;
    }
    memset(&v, 0, sizeof v);
    v.dwOSVersionInfoSize = size;
    ok = GetVersionExA((LPOSVERSIONINFOA)&v);
    if (ok)
        memcpy(G2H(p), &v, size);
    RET_STD(1, ok);
}

static void hle_GetComputerNameW(CPU* c) {
    DWORD n = rd32(ARG(1));
    BOOL ok = GetComputerNameW((LPWSTR)G2H(ARG(0)), &n);
    if (!ok)
        set_err_from_host(c);
    wr32(ARG(1), n);
    RET_STD(2, ok);
}

static void hle_MultiByteToWideChar(CPU* c) {
    int r = MultiByteToWideChar(ARG(0), ARG(1), (LPCSTR)G2H(ARG(2)), (int)ARG(3), ARG(5) ? (LPWSTR)G2H(ARG(4)) : NULL,
                                (int)ARG(5));
    if (!r)
        set_err_from_host(c);
    RET_STD(6, (uint32_t)r);
}

static void hle_WideCharToMultiByte(CPU* c) {
    BOOL used = FALSE;
    int r;
    if (ARG(6))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "WideCharToMultiByte with a default character is not implemented");
    r = WideCharToMultiByte(ARG(0), ARG(1), (LPCWSTR)G2H(ARG(2)), (int)ARG(3), ARG(5) ? (LPSTR)G2H(ARG(4)) : NULL,
                            (int)ARG(5), NULL, ARG(7) ? &used : NULL);
    if (ARG(7))
        wr32(ARG(7), used);
    if (!r)
        set_err_from_host(c);
    RET_STD(8, (uint32_t)r);
}

static void hle_GetTickCount(CPU* c) { RET_STD(0, GetTickCount()); }

/* time and identity sources (GlmLib.dll's CRT startup derives its /GS cookie from these; the values are host
 * values, as nondeterministic as in the original) */
static void hle_GetSystemTimeAsFileTime(CPU* c) {
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    wr32(ARG(0), ft.dwLowDateTime);
    wr32(ARG(0) + 4, ft.dwHighDateTime);
    RET_STD(1, 0);
}
static void hle_GetCurrentProcessId(CPU* c) { RET_STD(0, rd32(c->fs_base + 0x20)); }
static void hle_GetCurrentThreadId(CPU* c) { RET_STD(0, c->thread->guest_tid); }
static void hle_QueryPerformanceCounter(CPU* c) {
    LARGE_INTEGER v;
    QueryPerformanceCounter(&v);
    wr32(ARG(0), v.LowPart);
    wr32(ARG(0) + 4, (uint32_t)v.HighPart);
    RET_STD(1, 1);
}
static void hle_QueryPerformanceFrequency(CPU* c) {
    LARGE_INTEGER v;
    QueryPerformanceFrequency(&v);
    wr32(ARG(0), v.LowPart);
    wr32(ARG(0) + 4, (uint32_t)v.HighPart);
    RET_STD(1, 1);
}

/* Interlocked*: guest threads run one at a time (execution baton), so a plain read-modify-write is atomic */
static void hle_InterlockedIncrement(CPU* c) {
    uint32_t v = rd32(ARG(0)) + 1;
    wr32(ARG(0), v);
    RET_STD(1, v);
}
static void hle_InterlockedDecrement(CPU* c) {
    uint32_t v = rd32(ARG(0)) - 1;
    wr32(ARG(0), v);
    RET_STD(1, v);
}

static void hle_ExitProcess(CPU* c) {
    xrt_stdout_flush();
    xrt_process_exit(c, ARG(0));
}

/* ---------------------------------------------------------------- threads and synchronisation */
static void hle_Sleep(CPU* c) {
    XrtThread* t = c->thread;
    t->sleeps++;
    if (xrt_exiting) {                /* other threads are already terminated: keep the baton */
        Sleep(ARG(0));
    } else {
        xrt_baton_release();
        Sleep(ARG(0));
        xrt_baton_acquire();
    }
    RET_STD(1, 0);
}

static void hle_CreateThread(CPU* c) {
    uint32_t tid = 0, h;
    if (ARG(0))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "CreateThread with security attributes is not implemented");
    if (ARG(4) & ~(uint32_t)STACK_SIZE_PARAM_IS_A_RESERVATION)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "CreateThread flags %08x are not implemented", ARG(4));
    h = xrt_thread_create(c, ARG(1), ARG(2), ARG(3), &tid);
    if (ARG(5))
        wr32(ARG(5), tid);
    RET_STD(6, h);
}

static void hle_ExitThread(CPU* c) {
    xrt_log("ExitThread(%u) on thread %d", ARG(0), c->thread->index);
    xrt_event("exit_thread", "\"code\": %u", ARG(0));
    xrt_thread_exit(c, ARG(0));
}

/* CRITICAL_SECTION: the guest object (24 bytes) is keyed to a host critical section by its guest address */
typedef struct CsMap { uint32_t guest; CRITICAL_SECTION* host; } CsMap;
static CsMap csmap[1024];
static int ncs;
static SRWLOCK cs_lock = SRWLOCK_INIT;

static CRITICAL_SECTION* cs_find(CPU* c, uint32_t g, int create, int remove) {
    int i;
    CRITICAL_SECTION* r = NULL;
    AcquireSRWLockExclusive(&cs_lock);
    for (i = 0; i < ncs; i++)
        if (csmap[i].guest == g) {
            r = csmap[i].host;
            if (remove)
                csmap[i] = csmap[--ncs];
            break;
        }
    if (!r && create) {
        if (ncs == (int)(sizeof csmap / sizeof csmap[0])) {
            ReleaseSRWLockExclusive(&cs_lock);
            xrt_fatal(c, XRT_EXIT_SETUP, "too many critical sections");
        }
        r = (CRITICAL_SECTION*)malloc(sizeof *r);
        InitializeCriticalSection(r);
        csmap[ncs].guest = g;
        csmap[ncs].host = r;
        ncs++;
    }
    ReleaseSRWLockExclusive(&cs_lock);
    if (!r && !create)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "critical section %08x used without InitializeCriticalSection", g);
    return r;
}

static void hle_InitializeCriticalSection(CPU* c) {
    uint32_t g = ARG(0);
    cs_find(c, g, 1, 0);
    memset(G2H(g), 0, 24);
    wr32(g + 4, 0xFFFFFFFFu);        /* LockCount = -1, as after a real initialisation */
    RET_STD(1, 0);
}
static void hle_DeleteCriticalSection(CPU* c) {
    CRITICAL_SECTION* cs = cs_find(c, ARG(0), 0, 1);
    DeleteCriticalSection(cs);
    free(cs);
    RET_STD(1, 0);
}
static void hle_EnterCriticalSection(CPU* c) {
    CRITICAL_SECTION* cs = cs_find(c, ARG(0), 0, 0);
    if (!TryEnterCriticalSection(cs)) {
        c->thread->cs_waits++;
        xrt_baton_release();        /* the owner needs the baton to reach LeaveCriticalSection */
        EnterCriticalSection(cs);
        xrt_baton_acquire();
    }
    RET_STD(1, 0);
}
static void hle_LeaveCriticalSection(CPU* c) {
    LeaveCriticalSection(cs_find(c, ARG(0), 0, 0));
    RET_STD(1, 0);
}
static void hle_InitializeCriticalSectionAndSpinCount(CPU* c) {   /* the spin count has no observable effect here */
    uint32_t g = ARG(0);
    cs_find(c, g, 1, 0);
    memset(G2H(g), 0, 24);
    wr32(g + 4, 0xFFFFFFFFu);
    RET_STD(2, 1);
}

/* ---------------------------------------------------------------- what a DLL's static CRT uses (UnrImp.gpi)
 * GlmLib's plugin links its own C runtime (LIBCMT) instead of msvcr70.dll, so its startup and shutdown use these
 * Win32 services directly. */
static void hle_SetLastError(CPU* c) {
    xrt_set_last_error(c, ARG(0));
    RET_STD(1, 0);
}

/* TLS: the 64 slots of the guest TEB (offset 0xE10), as in Windows. TlsAlloc hands out the lowest free index and,
 * like TlsFree, clears that slot in every thread. The index values differ from the original's (system DLLs hold
 * lower ones there); the guest only uses them as keys. Expansion slots (index >= 64) are not modelled. */
static uint64_t tls_used;
static void tls_clear(uint32_t i) {
    int k;
    for (k = 0; k < xrt_thread_count(); k++)
        wr32(xrt_thread_get(k)->teb + 0xE10 + 4 * i, 0);
}
static void hle_TlsAlloc(CPU* c) {
    uint32_t i;
    for (i = 0; i < 64 && (tls_used >> i & 1); i++)
        ;
    if (i == 64)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "TlsAlloc: the 64 TEB slots are used up (expansion slots are not modelled)");
    tls_used |= 1ull << i;
    tls_clear(i);
    xrt_event("tls_alloc", "\"index\": %u", i);
    RET_STD(0, i);
}
static void hle_TlsFree(CPU* c) {
    uint32_t i = ARG(0);
    if (i >= 64 || !(tls_used >> i & 1)) {
        xrt_set_last_error(c, ERROR_INVALID_PARAMETER);
        RET_STD(1, 0);
        return;
    }
    tls_used &= ~(1ull << i);
    tls_clear(i);
    xrt_event("tls_free", "\"index\": %u", i);
    RET_STD(1, 1);
}
static void hle_TlsGetValue(CPU* c) {
    uint32_t i = ARG(0);
    if (i >= 64) {
        xrt_set_last_error(c, ERROR_INVALID_PARAMETER);
        RET_STD(1, 0);
        return;
    }
    xrt_set_last_error(c, ERROR_SUCCESS);   /* as documented: success clears the last error */
    RET_STD(1, rd32(c->fs_base + 0xE10 + 4 * i));
}
static void hle_TlsSetValue(CPU* c) {
    uint32_t i = ARG(0);
    if (i >= 64) {
        xrt_set_last_error(c, ERROR_INVALID_PARAMETER);
        RET_STD(2, 0);
        return;
    }
    wr32(c->fs_base + 0xE10 + 4 * i, ARG(1));
    RET_STD(2, 1);
}

/* Private heaps: a HeapCreate heap is a 16-byte runtime object (its address is the handle; the guest never reads
 * it) whose blocks come from the guest heap and are recorded with their heap; HeapDestroy frees the blocks still
 * live in it. Only what the plugin's CRT uses is modelled: a growable heap (maximum size 0) with flags 0 or
 * HEAP_NO_SERIALIZE, and HEAP_ZERO_MEMORY on allocation. A block of another heap, or the process heap, is fatal. */
typedef struct HeapBlock { uint32_t heap, p; } HeapBlock;
static HeapBlock* hblocks;
static int nhblocks, hblocks_cap;
static uint32_t heaps[16];
static int nheaps;
static int heap_known(uint32_t h) {
    int i;
    for (i = 0; i < nheaps; i++)
        if (heaps[i] == h)
            return 1;
    return 0;
}
static int heap_block(CPU* c, uint32_t h, uint32_t p, const char* api) {
    int i;
    if (!heap_known(h))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "%s on heap %08x, which is not a HeapCreate heap of this runtime", api, h);
    for (i = nhblocks - 1; i >= 0; i--)
        if (hblocks[i].p == p) {
            if (hblocks[i].heap != h)
                break;
            return i;
        }
    xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "%s(%08x, %08x): not a live block of that heap", api, h, p);
}
static void hle_HeapCreate(CPU* c) {
    uint32_t h;
    if ((ARG(0) & ~(uint32_t)HEAP_NO_SERIALIZE) || ARG(2))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "HeapCreate(flags %08x, maximum %08x) is not modelled", ARG(0), ARG(2));
    if (nheaps == (int)(sizeof heaps / sizeof heaps[0]))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "too many private heaps");
    h = xrt_rt_alloc(16, 16);
    heaps[nheaps++] = h;
    xrt_event("heap_create", "\"heap\": \"0x%08x\"", h);
    RET_STD(3, h);
}
static void hle_HeapAlloc(CPU* c) {
    uint32_t h = ARG(0), flags = ARG(1), size = ARG(2), p;
    if (!heap_known(h))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "HeapAlloc on heap %08x, which is not a HeapCreate heap of this runtime", h);
    if (flags & ~(uint32_t)(HEAP_ZERO_MEMORY | HEAP_NO_SERIALIZE))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "HeapAlloc flags %08x are not modelled", flags);
    if (!(p = xrt_heap_alloc(size))) {
        RET_STD(3, 0);
        return;
    }
    if (flags & HEAP_ZERO_MEMORY)
        memset(G2H(p), 0, size);
    if (nhblocks == hblocks_cap) {
        hblocks_cap = hblocks_cap ? 2 * hblocks_cap : 256;
        if (!(hblocks = (HeapBlock*)realloc(hblocks, hblocks_cap * sizeof *hblocks)))
            xrt_fatal(c, XRT_EXIT_SETUP, "host out of memory");
    }
    hblocks[nhblocks].heap = h;
    hblocks[nhblocks++].p = p;
    RET_STD(3, p);
}
static void hle_HeapFree(CPU* c) {
    int i;
    if (!ARG(2)) {
        RET_STD(3, 1);
        return;
    }
    i = heap_block(c, ARG(0), ARG(2), "HeapFree");
    hblocks[i] = hblocks[--nhblocks];
    xrt_heap_free(c, ARG(2));
    RET_STD(3, 1);
}
static void hle_HeapSize(CPU* c) {
    heap_block(c, ARG(0), ARG(2), "HeapSize");
    RET_STD(3, xrt_heap_msize(c, ARG(2)));
}
static void hle_HeapDestroy(CPU* c) {
    uint32_t h = ARG(0);
    int i, n = 0;
    if (!heap_known(h))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "HeapDestroy on heap %08x, which is not a HeapCreate heap of this runtime", h);
    for (i = nhblocks - 1; i >= 0; i--)
        if (hblocks[i].heap == h) {
            xrt_heap_free(c, hblocks[i].p);
            hblocks[i] = hblocks[--nhblocks];
            n++;
        }
    for (i = 0; i < nheaps; i++)
        if (heaps[i] == h)
            heaps[i] = heaps[--nheaps];
    xrt_event("heap_destroy", "\"heap\": \"0x%08x\", \"live_blocks_freed\": %d", h, n);
    RET_STD(1, 1);
}

/* Standard handles: the host process's own, as XH_STD guest handles (the original and this host are started by the
 * same harness with the same standard handles). Reading or writing them through kernel32 is not modelled (ReadFile
 * and WriteFile accept only file handles); the guest's console output goes through its CRT's stdout. */
static uint32_t std_handles[3];
static uint32_t std_guest(DWORD which) {   /* STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE */
    HANDLE h = GetStdHandle(which);
    uint32_t k = (uint32_t)(-(int)which) - 10;
    if (h == INVALID_HANDLE_VALUE)
        return 0xFFFFFFFFu;
    if (!h)
        return 0;
    if (!std_handles[k])
        std_handles[k] = xrt_handle_new(XH_STD, h);
    return std_handles[k];
}
static void hle_GetStdHandle(CPU* c) {
    DWORD which = ARG(0);
    uint32_t h;
    if (which != STD_INPUT_HANDLE && which != STD_OUTPUT_HANDLE && which != STD_ERROR_HANDLE) {
        xrt_set_last_error(c, ERROR_INVALID_HANDLE);
        RET_STD(1, 0xFFFFFFFFu);
        return;
    }
    if ((h = std_guest(which)) == 0xFFFFFFFFu)
        set_err_from_host(c);
    RET_STD(1, h);
}
static void hle_GetFileType(CPU* c) {
    uint32_t h = ARG(0);
    HANDLE host = xrt_handle_type(h) == XH_STD ? xrt_handle_get(h, XH_STD) : xrt_handle_get(h, XH_FILE);
    DWORD t;
    if (!host) {
        xrt_set_last_error(c, ERROR_INVALID_HANDLE);
        RET_STD(1, FILE_TYPE_UNKNOWN);
        return;
    }
    t = GetFileType(host);
    xrt_set_last_error(c, GetLastError());
    RET_STD(1, t);
}
static void hle_SetHandleCount(CPU* c) { RET_STD(1, ARG(0)); }   /* Windows NT: no effect, returns its argument */

/* STARTUPINFOA: the host process's (strings copied to guest memory once; standard handles as XH_STD handles). A
 * CRT handle-inheritance block (cbReserved2) is not modelled: fatal. */
static void hle_GetStartupInfoA(CPU* c) {
    static uint32_t desktop, title;
    STARTUPINFOA si;
    uint32_t p = ARG(0);
    GetStartupInfoA(&si);
    if (si.cbReserved2)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "GetStartupInfoA: the host was started with a CRT handle block (cbReserved2 %u)",
                  si.cbReserved2);
    if (si.lpDesktop && !desktop)
        desktop = xrt_guest_strdup_a(si.lpDesktop);
    if (si.lpTitle && !title)
        title = xrt_guest_strdup_a(si.lpTitle);
    memset(G2H(p), 0, 68);
    wr32(p + 0, 68);
    wr32(p + 8, desktop);
    wr32(p + 12, title);
    wr32(p + 16, si.dwX);
    wr32(p + 20, si.dwY);
    wr32(p + 24, si.dwXSize);
    wr32(p + 28, si.dwYSize);
    wr32(p + 32, si.dwXCountChars);
    wr32(p + 36, si.dwYCountChars);
    wr32(p + 40, si.dwFillAttribute);
    wr32(p + 44, si.dwFlags);
    wr16(p + 48, si.wShowWindow);
    if (si.dwFlags & STARTF_USESTDHANDLES) {
        const DWORD which[3] = {STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE};
        HANDLE given[3] = {si.hStdInput, si.hStdOutput, si.hStdError};
        int k;
        for (k = 0; k < 3; k++) {
            if (given[k] && given[k] != INVALID_HANDLE_VALUE && given[k] != GetStdHandle(which[k]))
                xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "GetStartupInfoA: startup handle %d is not the standard handle", k);
            wr32(p + 56 + 4 * k, given[k] == INVALID_HANDLE_VALUE ? 0xFFFFFFFFu : given[k] ? std_guest(which[k]) : 0);
        }
    }
    RET_STD(1, 0);
}

/* Environment block: empty - the same deliberate limitation as msvcr70's __getmainargs (the guest gets no
 * environment). The block is a guest heap allocation released by FreeEnvironmentStringsW. */
static uint32_t env_blocks[8];
static void hle_GetEnvironmentStringsW(CPU* c) {
    uint32_t p = xrt_heap_alloc(4);
    int k;
    if (!p)
        xrt_fatal(c, XRT_EXIT_SETUP, "guest heap exhausted");
    wr32(p, 0);
    for (k = 0; k < 8 && env_blocks[k]; k++)
        ;
    if (k == 8)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "too many environment blocks");
    env_blocks[k] = p;
    xrt_event("environment_block", "\"entries\": 0");
    RET_STD(0, p);
}
static void hle_FreeEnvironmentStringsW(CPU* c) {
    int k;
    for (k = 0; k < 8 && env_blocks[k] != ARG(0); k++)
        ;
    if (k == 8 || !ARG(0))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "FreeEnvironmentStringsW(%08x): not a block from GetEnvironmentStringsW", ARG(0));
    env_blocks[k] = 0;
    xrt_heap_free(c, ARG(0));
    RET_STD(1, 1);
}

/* Recorded only: an unhandled guest exception is fatal in this runtime, so the filter is never called. Returns the
 * previously recorded filter (none before the first call; the original's would be one msvcr70 installed). */
static uint32_t unhandled_filter;
static void hle_SetUnhandledExceptionFilter(CPU* c) {
    uint32_t prev = unhandled_filter;
    char d[512];
    unhandled_filter = ARG(0);
    xrt_describe(d, sizeof d, ARG(0));
    xrt_log("SetUnhandledExceptionFilter(%s): recorded; never called (an unhandled guest exception is fatal)", d);
    xrt_event("unhandled_exception_filter", "\"filter\": \"0x%08x\", \"previous\": \"0x%08x\"", ARG(0), prev);
    RET_STD(1, prev);
}

/* IsProcessorFeaturePresent, consistent with the CPUID policy (xrt_cpu.c): SIMD features absent; the FDIV-erratum
 * query of the CRT's startup (PF_FLOATING_POINT_PRECISION_ERRATA) is the host's answer. Other features: fatal. */
static void hle_IsProcessorFeaturePresent(CPU* c) {
    uint32_t f = ARG(0);
    switch (f) {
    case PF_FLOATING_POINT_PRECISION_ERRATA:
        RET_STD(1, IsProcessorFeaturePresent(f) ? 1 : 0);
        return;
    case PF_MMX_INSTRUCTIONS_AVAILABLE:
    case PF_XMMI_INSTRUCTIONS_AVAILABLE:
    case PF_3DNOW_INSTRUCTIONS_AVAILABLE:
    case PF_XMMI64_INSTRUCTIONS_AVAILABLE:
    case PF_SSE3_INSTRUCTIONS_AVAILABLE:
        RET_STD(1, 0);
        return;
    default:
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "IsProcessorFeaturePresent(%u) is not modelled", f);
    }
}

/* Code-page and locale services: the host's, on the same arguments (the original ran on the same system, so the
 * ANSI code page and the tables are the ones it saw; nothing is substituted). */
static void hle_GetACP(CPU* c) { RET_STD(0, GetACP()); }
static void hle_GetCPInfo(CPU* c) {
    CPINFO ci;
    BOOL ok = GetCPInfo(ARG(0), &ci);
    if (ok)
        memcpy(G2H(ARG(1)), &ci, sizeof ci);
    else
        set_err_from_host(c);
    RET_STD(2, ok);
}
static void hle_GetStringTypeW(CPU* c) {
    BOOL ok = GetStringTypeW(ARG(0), (LPCWCH)G2H(ARG(1)), (int)ARG(2), (LPWORD)G2H(ARG(3)));
    if (!ok)
        set_err_from_host(c);
    RET_STD(4, ok);
}
static void hle_LCMapStringW(CPU* c) {
    int r = LCMapStringW(ARG(0), ARG(1), (LPCWSTR)G2H(ARG(2)), (int)ARG(3), ARG(5) ? (LPWSTR)G2H(ARG(4)) : NULL,
                         (int)ARG(5));
    if (!r)
        set_err_from_host(c);
    RET_STD(6, (uint32_t)r);
}

const XrtHle xrt_hle_kernel32[] = {
    {"kernel32.dll", "CreateFileW", hle_CreateFileW},
    {"kernel32.dll", "CreateFileA", hle_CreateFileA},
    {"kernel32.dll", "ReadFile", hle_ReadFile},
    {"kernel32.dll", "WriteFile", hle_WriteFile},
    {"kernel32.dll", "SetFilePointer", hle_SetFilePointer},
    {"kernel32.dll", "GetFileSize", hle_GetFileSize},
    {"kernel32.dll", "CloseHandle", hle_CloseHandle},
    {"kernel32.dll", "SetFileAttributesW", hle_SetFileAttributesW},
    {"kernel32.dll", "DeleteFileW", hle_DeleteFileW},
    {"kernel32.dll", "MoveFileW", hle_MoveFileW},
    {"kernel32.dll", "SetCurrentDirectoryW", hle_SetCurrentDirectoryW},
    {"kernel32.dll", "GetCurrentDirectoryW", hle_GetCurrentDirectoryW},
    {"kernel32.dll", "FindFirstFileW", hle_FindFirstFileW},
    {"kernel32.dll", "FindNextFileW", hle_FindNextFileW},
    {"kernel32.dll", "FindClose", hle_FindClose},
    {"kernel32.dll", "GetCommandLineA", hle_GetCommandLineA},
    {"kernel32.dll", "GetCurrentProcess", hle_GetCurrentProcess},
    {"kernel32.dll", "GetLastError", hle_GetLastError},
    {"kernel32.dll", "GetModuleHandleA", hle_GetModuleHandleA},
    {"kernel32.dll", "GetModuleFileNameA", hle_GetModuleFileNameA},
    {"kernel32.dll", "LoadLibraryW", hle_LoadLibraryW},
    {"kernel32.dll", "LoadLibraryA", hle_LoadLibraryA},
    {"kernel32.dll", "GetPrivateProfileStringA", hle_GetPrivateProfileStringA},
    {"kernel32.dll", "FreeLibrary", hle_FreeLibrary},
    {"kernel32.dll", "GetProcAddress", hle_GetProcAddress},
    {"kernel32.dll", "SetConsoleCtrlHandler", hle_SetConsoleCtrlHandler},
    {"kernel32.dll", "FreeConsole", hle_FreeConsole},
    {"kernel32.dll", "GetProcessWorkingSetSize", hle_GetProcessWorkingSetSize},
    {"kernel32.dll", "GetSystemInfo", hle_GetSystemInfo},
    {"kernel32.dll", "GlobalMemoryStatus", hle_GlobalMemoryStatus},
    {"kernel32.dll", "GetVersionExA", hle_GetVersionExA},
    {"kernel32.dll", "GetComputerNameW", hle_GetComputerNameW},
    {"kernel32.dll", "MultiByteToWideChar", hle_MultiByteToWideChar},
    {"kernel32.dll", "WideCharToMultiByte", hle_WideCharToMultiByte},
    {"kernel32.dll", "GetTickCount", hle_GetTickCount},
    {"kernel32.dll", "GetSystemTimeAsFileTime", hle_GetSystemTimeAsFileTime},
    {"kernel32.dll", "GetCurrentProcessId", hle_GetCurrentProcessId},
    {"kernel32.dll", "GetCurrentThreadId", hle_GetCurrentThreadId},
    {"kernel32.dll", "QueryPerformanceCounter", hle_QueryPerformanceCounter},
    {"kernel32.dll", "QueryPerformanceFrequency", hle_QueryPerformanceFrequency},
    {"kernel32.dll", "InterlockedIncrement", hle_InterlockedIncrement},
    {"kernel32.dll", "InterlockedDecrement", hle_InterlockedDecrement},
    {"kernel32.dll", "ExitProcess", hle_ExitProcess},
    {"kernel32.dll", "Sleep", hle_Sleep},
    {"kernel32.dll", "CreateThread", hle_CreateThread},
    {"kernel32.dll", "ExitThread", hle_ExitThread},
    {"kernel32.dll", "InitializeCriticalSection", hle_InitializeCriticalSection},
    {"kernel32.dll", "DeleteCriticalSection", hle_DeleteCriticalSection},
    {"kernel32.dll", "EnterCriticalSection", hle_EnterCriticalSection},
    {"kernel32.dll", "LeaveCriticalSection", hle_LeaveCriticalSection},
    {"kernel32.dll", "InitializeCriticalSectionAndSpinCount", hle_InitializeCriticalSectionAndSpinCount},
    {"kernel32.dll", "SetLastError", hle_SetLastError},
    {"kernel32.dll", "TlsAlloc", hle_TlsAlloc},
    {"kernel32.dll", "TlsFree", hle_TlsFree},
    {"kernel32.dll", "TlsGetValue", hle_TlsGetValue},
    {"kernel32.dll", "TlsSetValue", hle_TlsSetValue},
    {"kernel32.dll", "HeapCreate", hle_HeapCreate},
    {"kernel32.dll", "HeapAlloc", hle_HeapAlloc},
    {"kernel32.dll", "HeapFree", hle_HeapFree},
    {"kernel32.dll", "HeapSize", hle_HeapSize},
    {"kernel32.dll", "HeapDestroy", hle_HeapDestroy},
    {"kernel32.dll", "GetStdHandle", hle_GetStdHandle},
    {"kernel32.dll", "GetFileType", hle_GetFileType},
    {"kernel32.dll", "SetHandleCount", hle_SetHandleCount},
    {"kernel32.dll", "GetStartupInfoA", hle_GetStartupInfoA},
    {"kernel32.dll", "GetEnvironmentStringsW", hle_GetEnvironmentStringsW},
    {"kernel32.dll", "FreeEnvironmentStringsW", hle_FreeEnvironmentStringsW},
    {"kernel32.dll", "SetUnhandledExceptionFilter", hle_SetUnhandledExceptionFilter},
    {"kernel32.dll", "IsProcessorFeaturePresent", hle_IsProcessorFeaturePresent},
    {"kernel32.dll", "GetACP", hle_GetACP},
    {"kernel32.dll", "GetCPInfo", hle_GetCPInfo},
    {"kernel32.dll", "GetStringTypeW", hle_GetStringTypeW},
    {"kernel32.dll", "LCMapStringW", hle_LCMapStringW},
    {0},
};
