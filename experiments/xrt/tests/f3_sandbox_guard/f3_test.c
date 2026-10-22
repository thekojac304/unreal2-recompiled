/* f3_test.c - validation of claim F3: xrt_path_is_inside_sandbox (runtime/hle_kernel32.c) ignores a
 * GetFullPathNameW return value larger than its 520-WCHAR buffer.
 *
 * Part A  what GetFullPathNameW does with a too-small buffer (return value, which buffer cells it writes).
 * Part B  the real xrt_path_is_inside_sandbox (linked from hle_kernel32.obj built with the runtime's flags):
 *         decisions for >= 520-character full paths with junk / stale stack contents.
 * Part C  end to end through the real kernel32 adapter table entry "CreateFileW" with a fake guest CPU:
 *         does a stale decision let a write outside the sandbox root happen, with and without "\\?\"?
 * Part D  context: what the host OS does with the same long paths when called directly by this process
 *         (= what the original, equally non-long-path-aware UCC.exe would see).
 *
 * Usage: f3_test.exe <scratch dir>   (all files and directories are created below <scratch dir>) */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "xrt_internal.h"

extern jmp_buf f3_fatal_jmp;
extern int f3_fatal_armed;
extern char f3_fatal_msg[1200];
extern int f3_quiet_log;

#define BUFN (MAX_PATH * 2)
static WCHAR base[1024], root[1024], outside[1024];
static WCHAR long_out_dir[4096], long_in_dir[4096];

/* ---------------------------------------------------------------- helpers */
static void make_deep(WCHAR* out, size_t outn, const WCHAR* parent, size_t min_total) {
    /* creates parent\ddd...\ddd... (200-char components) until the directory path is >= min_total chars */
    WCHAR ext[4200];
    swprintf(out, outn, L"%ls", parent);
    while (wcslen(out) < min_total) {
        size_t k = wcslen(out);
        out[k++] = L'\\';
        for (int i = 0; i < 200; i++)
            out[k++] = L'd';
        out[k] = 0;
        swprintf(ext, 4200, L"\\\\?\\%ls", out);
        if (!CreateDirectoryW(ext, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
            printf("CreateDirectoryW failed: %lu\n", GetLastError());
            exit(2);
        }
    }
}

static int exists_ext(const WCHAR* path) {
    WCHAR ext[4200];
    if (path[0] == L'\\' && path[1] == L'\\')
        swprintf(ext, 4200, L"%ls", path);
    else
        swprintf(ext, 4200, L"\\\\?\\%ls", path);
    return GetFileAttributesW(ext) != INVALID_FILE_ATTRIBUTES;
}

static void delete_ext(const WCHAR* path) {
    WCHAR ext[4200];
    if (path[0] == L'\\' && path[1] == L'\\')
        swprintf(ext, 4200, L"%ls", path);
    else
        swprintf(ext, 4200, L"\\\\?\\%ls", path);
    DeleteFileW(ext);
}

/* ---------------------------------------------------------------- Part A */
static void probe(const char* label, const WCHAR* path) {
    static WCHAR big[40000];
    WCHAR buf[BUFN];
    DWORD rb, r, changed = 0, first = 0xFFFFFFFF, last = 0, prefix_ok = 1, zeros = 0;
    rb = GetFullPathNameW(path, 40000, big, NULL);
    for (int i = 0; i < BUFN; i++)
        buf[i] = 0xABCD;
    SetLastError(0);
    r = GetFullPathNameW(path, BUFN, buf, NULL);
    for (DWORD i = 0; i < BUFN; i++) {
        if (buf[i] == 0)
            zeros++;
        if (buf[i] != 0xABCD) {
            changed++;
            if (first == 0xFFFFFFFF)
                first = i;
            last = i;
            if (i < rb && buf[i] != big[i])
                prefix_ok = 0;
        }
    }
    printf("  %-40s input %4zu full %4lu r=%4lu %-9s written %lu", label, wcslen(path), rb, r,
           r == 0 ? "(error)" : r < BUFN ? "(fits)" : "(too small", changed);
    if (r >= BUFN)
        printf(", buf[0]=%#x, nonzero cells %lu (stale/fill cells left: %lu)", buf[0], BUFN - zeros, BUFN - changed);
    else if (changed)
        printf(" [%lu..%lu]%s, zero cells %lu", first, last, prefix_ok ? " = full path" : " (not the full path)", zeros);
    printf("\n");
}

static void part_a(void) {
    WCHAR p[4200];
    size_t rl = wcslen(root);
    printf("Part A: GetFullPathNameW(path, %d, buf, NULL) with buf pre-filled with 0xABCD\n", BUFN);
    /* absolute DOS paths whose full length is around the buffer size */
    for (size_t want = 517; want <= 523; want++) {
        char label[64];
        swprintf(p, 4200, L"%ls\\", root);
        while (wcslen(p) < want)
            wcscat(p, L"a");
        p[want] = 0;
        snprintf(label, sizeof label, "absolute, full length %zu", want);
        probe(label, p);
    }
    swprintf(p, 4200, L"%ls\\System\\x.log", root);
    probe("absolute short (in sandbox)", p);
    swprintf(p, 4200, L"%ls\\x.txt", long_out_dir);
    probe("absolute long (outside)", p);
    swprintf(p, 4200, L"\\\\?\\%ls\\x.txt", long_out_dir);
    probe("\\\\?\\ long (outside)", p);
    swprintf(p, 4200, L"\\\\?\\%ls\\System\\x.log", root);
    probe("\\\\?\\ short (in sandbox)", p);
    /* relative path resolved against the current directory (= root\System) */
    p[0] = 0;
    while (wcslen(p) < 600)
        wcscat(p, L"r");
    probe("relative 600 chars (cwd = root\\System)", p);
    /* raw string long, normalised path short */
    swprintf(p, 4200, L"%ls", root);
    while (wcslen(p) < 700)
        wcscat(p, L"\\x\\..");
    wcscat(p, L"\\System\\x.log");
    probe("long raw, short after .. collapse", p);
    /* relative path that resolves outside the sandbox */
    swprintf(p, 4200, L"..\\..\\outside\\");
    while (wcslen(p) < 600)
        wcscat(p, L"q");
    probe("relative ..\\..\\outside 600 chars", p);
    swprintf(p, 4200, L"\\\\server\\share\\");
    while (wcslen(p) < 600)
        wcscat(p, L"q");
    probe("UNC 600 chars", p);
    (void)rl;
}

/* ---------------------------------------------------------------- Part B */
__declspec(noinline) static void scribble(WCHAR v) {
    volatile WCHAR junk[8192];
    for (int i = 0; i < 8192; i++)
        junk[i] = v;
}
__declspec(noinline) static int guard(const WCHAR* p) { return xrt_path_is_inside_sandbox((const uint16_t*)p); }

static void part_b(void) {
    static WCHAR in_short[1024], in_long[4200], out_long[4200], out_long_ext[4200];
    int r1, r2, r3, r4, r5;
    swprintf(in_short, 1024, L"%ls\\System\\a.log", root);
    swprintf(in_long, 4200, L"%ls\\x.txt", long_in_dir);
    swprintf(out_long, 4200, L"%ls\\x.txt", long_out_dir);
    swprintf(out_long_ext, 4200, L"\\\\?\\%ls\\x.txt", long_out_dir);
    printf("Part B: real xrt_path_is_inside_sandbox (1 = inside / allowed, 0 = outside / fatal)\n");
    printf("  sandbox root: %ls (%zu chars)\n", root, wcslen(root));
    printf("  long in-sandbox path %zu chars, long outside path %zu chars\n", wcslen(in_long), wcslen(out_long));
    scribble(0xABCD);
    r1 = guard(in_long);
    scribble(0xABCD);
    r2 = guard(out_long);
    r3 = guard(in_short);     /* leaves "<root>\System\a.log" in the callee's stack frame */
    r4 = guard(out_long);     /* same depth: GetFullPathNameW too small -> stale buffer decides */
    guard(in_short);
    r5 = guard(out_long_ext);
    {
        static WCHAR rel_out[4200];
        int r6;
        swprintf(rel_out, 4200, L"..\\..\\outside\\");
        while (wcslen(rel_out) < 600)
            wcscat(rel_out, L"q");
        guard(in_short);
        r6 = guard(rel_out);
        printf("  B6 after an inside call, relative ..\\..\\outside\\<600> -> %d %s\n", r6,
               r6 ? "(ALLOWED: stale buffer)" : "");
    }
    printf("  B1 junk stack, long path INSIDE sandbox         -> %d %s\n", r1, r1 ? "" : "(refused: spurious fatal)");
    printf("  B2 junk stack, long path OUTSIDE sandbox        -> %d\n", r2);
    printf("  B3 short path inside sandbox                    -> %d\n", r3);
    printf("  B4 right after B3, long path OUTSIDE sandbox    -> %d %s\n", r4, r4 ? "(ALLOWED: stale buffer from B3)" : "");
    printf("  B5 after an inside call, \\\\?\\ long path OUTSIDE -> %d %s\n", r5, r5 ? "(ALLOWED: stale buffer)" : "");
}

/* ---------------------------------------------------------------- Part C */
#define G_STR 0x00010000u
#define G_STR2 0x00020000u
#define G_STACK 0x000F0000u

static XrtFn adapter(const char* name) {
    for (const XrtHle* h = xrt_hle_kernel32; h->name; h++)
        if (!strcmp(h->name, name))
            return h->fn;
    printf("no adapter %s\n", name);
    exit(2);
}

static void put_wstr(uint32_t ga, const WCHAR* s) { memcpy(G2H(ga), s, (wcslen(s) + 1) * 2); }

/* CreateFileW(name, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL), the arguments the
 * guest's file writer (UCC.exe 0x402756) passes; returns the guest handle, or 0xDEAD0000|code on fatal */
static CPU cpu;
__declspec(noinline) static uint32_t guest_create(XrtFn fn, uint32_t gname) {
    uint32_t sp = G_STACK;
    uint32_t args[7] = {gname, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0};
    int code;
    for (int i = 6; i >= 0; i--) {
        sp -= 4;
        wr32(sp, args[i]);
    }
    sp -= 4;
    wr32(sp, 0x12345678u);
    cpu.r[ESP] = sp;
    f3_fatal_armed = 1;
    if ((code = setjmp(f3_fatal_jmp)) != 0) {
        f3_fatal_armed = 0;
        return 0xDEAD0000u | (uint32_t)code;
    }
    fn(&cpu);
    f3_fatal_armed = 0;
    return cpu.r[EAX];
}

static void report_c(const char* label, uint32_t h, const WCHAR* target) {
    printf("  %-52s -> ", label);
    if ((h & 0xFFFF0000u) == 0xDEAD0000u)
        printf("xrt_fatal(%u) \"%.60s...\"", h & 0xFFFF, f3_fatal_msg);
    else if (h == 0xFFFFFFFFu)
        printf("INVALID_HANDLE_VALUE, guest last error %u", xrt_get_last_error(&cpu));
    else
        printf("guest handle %#x", h);
    printf("; target exists afterwards: %s\n", exists_ext(target) ? "YES" : "no");
}

static void close_guest(uint32_t h) {
    if (h && h != 0xFFFFFFFFu && (h & 0xFFFF0000u) != 0xDEAD0000u) {
        HANDLE f = (HANDLE)xrt_handle_get(h, XH_FILE);
        CloseHandle(f);
        xrt_handle_free(h);
    }
}

static void part_c(void) {
    static WCHAR in_short[1024], out_ext[4200], out_dos[4200], in_dos[4200], in_ext[4200];
    XrtFn create = adapter("CreateFileW");
    uint32_t h1, h2;
    swprintf(in_short, 1024, L"%ls\\System\\a.log", root);
    swprintf(out_ext, 4200, L"\\\\?\\%ls\\pwn.txt", long_out_dir);
    swprintf(out_dos, 4200, L"%ls\\pwn2.txt", long_out_dir);
    swprintf(in_dos, 4200, L"%ls\\legit.txt", long_in_dir);
    swprintf(in_ext, 4200, L"\\\\?\\%ls\\legit2.txt", long_in_dir);
    printf("Part C: real kernel32 adapter CreateFileW(GENERIC_WRITE, CREATE_ALWAYS) with a fake guest CPU\n");

    /* C1: in-sandbox write, then \\?\ long outside path from the same host stack depth */
    put_wstr(G_STR, in_short);
    put_wstr(G_STR2, out_ext);
    h1 = guest_create(create, G_STR);
    h2 = guest_create(create, G_STR2);
    report_c("C1a short in-sandbox file", h1, in_short);
    report_c("C1b then \\\\?\\ long path OUTSIDE the sandbox", h2, out_ext);
    close_guest(h1);
    close_guest(h2);

    /* C2: same, DOS long path (no \\?\) outside */
    put_wstr(G_STR2, out_dos);
    h1 = guest_create(create, G_STR);
    h2 = guest_create(create, G_STR2);
    report_c("C2 then DOS long path OUTSIDE the sandbox", h2, out_dos);
    close_guest(h1);
    close_guest(h2);

    /* C3: junk stack, legitimate long in-sandbox paths */
    put_wstr(G_STR2, in_dos);
    scribble(0xABCD);
    h2 = guest_create(create, G_STR2);
    report_c("C3a junk stack, DOS long path INSIDE sandbox", h2, in_dos);
    close_guest(h2);
    put_wstr(G_STR2, in_ext);
    scribble(0xABCD);
    h2 = guest_create(create, G_STR2);
    report_c("C3b junk stack, \\\\?\\ long path INSIDE sandbox", h2, in_ext);
    close_guest(h2);
    /* C4: short \\?\ path inside the sandbox (not part of F3: control for the prefix comparison) */
    {
        static WCHAR in_short_ext[1100];
        swprintf(in_short_ext, 1100, L"\\\\?\\%ls\\System\\b.log", root);
        put_wstr(G_STR2, in_short_ext);
        h2 = guest_create(create, G_STR2);
        report_c("C4 control: short \\\\?\\ path INSIDE sandbox", h2, in_short_ext);
        close_guest(h2);
    }
}

/* ---------------------------------------------------------------- Part D */
static void part_d(void) {
    static WCHAR p[4200];
    typedef BOOLEAN(NTAPI * AreLong)(void);
    AreLong are_long = (AreLong)GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlAreLongPathsEnabled");
    HANDLE h;
    printf("Part D: host OS, called directly by this (unmanifested, like the original UCC.exe) process\n");
    printf("  RtlAreLongPathsEnabled() = %d\n", are_long ? are_long() : -1);
    swprintf(p, 4200, L"%ls\\direct.txt", long_out_dir);
    h = CreateFileW(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    printf("  CreateFileW(DOS long path, %zu chars)   -> %s, error %lu\n", wcslen(p),
           h == INVALID_HANDLE_VALUE ? "INVALID_HANDLE_VALUE" : "opened", h == INVALID_HANDLE_VALUE ? GetLastError() : 0);
    if (h != INVALID_HANDLE_VALUE)
        CloseHandle(h);
    swprintf(p, 4200, L"\\\\?\\%ls\\direct2.txt", long_out_dir);
    h = CreateFileW(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    printf("  CreateFileW(\\\\?\\ long path, %zu chars) -> %s, error %lu\n", wcslen(p),
           h == INVALID_HANDLE_VALUE ? "INVALID_HANDLE_VALUE" : "opened", h == INVALID_HANDLE_VALUE ? GetLastError() : 0);
    if (h != INVALID_HANDLE_VALUE)
        CloseHandle(h);
    swprintf(p, 4200, L"%ls", long_in_dir);
    {
        BOOL ok = SetCurrentDirectoryW(p);
        DWORD e = GetLastError();
        printf("  SetCurrentDirectoryW(DOS long dir, %zu chars) -> %d, error %lu\n", wcslen(p), ok, e);
    }
    /* raw string >= 520 chars that normalises to a short path inside the sandbox */
    swprintf(p, 4200, L"%ls", root);
    while (wcslen(p) < 700)
        wcscat(p, L"\\x\\..");
    wcscat(p, L"\\System\\collapse.txt");
    h = CreateFileW(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    printf("  CreateFileW(raw %zu chars, normalises short, in sandbox) -> %s, error %lu\n", wcslen(p),
           h == INVALID_HANDLE_VALUE ? "INVALID_HANDLE_VALUE" : "opened", h == INVALID_HANDLE_VALUE ? GetLastError() : 0);
    if (h != INVALID_HANDLE_VALUE)
        CloseHandle(h);
    printf("  xrt_path_is_inside_sandbox(same path) -> %d\n", xrt_path_is_inside_sandbox((const uint16_t*)p));
}

int main(int argc, char** argv) {
    static WCHAR files[8][4200];
    if (argc < 2) {
        printf("usage: f3_test <scratch dir>\n");
        return 2;
    }
    {
        WCHAR arg[1024];
        MultiByteToWideChar(CP_ACP, 0, argv[1], -1, arg, 1024);
        GetFullPathNameW(arg, 1024, base, NULL);
    }
    swprintf(root, 1024, L"%ls\\root", base);
    swprintf(outside, 1024, L"%ls\\outside", base);
    CreateDirectoryW(base, NULL);
    CreateDirectoryW(root, NULL);
    {
        WCHAR sys[1100];
        swprintf(sys, 1100, L"%ls\\System", root);
        CreateDirectoryW(sys, NULL);
        SetCurrentDirectoryW(sys);
    }
    CreateDirectoryW(outside, NULL);
    make_deep(long_out_dir, 4096, outside, 560);
    make_deep(long_in_dir, 4096, root, 560);
    /* remove leftovers of a previous run */
    swprintf(files[0], 4200, L"%ls\\pwn.txt", long_out_dir);
    swprintf(files[1], 4200, L"%ls\\pwn2.txt", long_out_dir);
    swprintf(files[2], 4200, L"%ls\\legit.txt", long_in_dir);
    swprintf(files[3], 4200, L"%ls\\legit2.txt", long_in_dir);
    swprintf(files[4], 4200, L"%ls\\direct.txt", long_out_dir);
    swprintf(files[5], 4200, L"%ls\\direct2.txt", long_out_dir);
    for (int i = 0; i < 6; i++)
        delete_ext(files[i]);
    WideCharToMultiByte(CP_ACP, 0, root, -1, xrt_sandbox_root, sizeof xrt_sandbox_root, NULL, NULL);
    xrt_g = (uint8_t*)VirtualAlloc(NULL, 0x100000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    f3_quiet_log = 1;

    part_a();
    part_b();
    part_c();
    part_d();
    return 0;
}
