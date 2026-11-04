/* player.c - start-up of the standalone player "Unreal II Enhanced.exe" (dev.py player-build links it with the developer
 * build's objects; the developer executable never contains it: xrt_main.c's default xrt_player_setup returns 0).
 *
 * Double-clicking the executable runs the launcher half (no game code runs in this process):
 *   1. the player's data folder, %LOCALAPPDATA%\UnrealIIEnhanced (or --data DIR): player.ini, System\ (the game's
 *      settings, a private copy of the installation's System folder), Save\, UIScripts\ (the port's menu file), Logs\;
 *   2. the Unreal II installation: --game DIR, else the remembered GamePath, else found beside this executable or
 *      through GOG's registry entry, else chosen by the player in a folder dialog; then checked (files present, every
 *      translated module byte-identical to the one this build was translated from) before anything starts;
 *   3. the data folder made ready (System copied once and refreshed when the installation's files change; the port
 *      package U2Port.u and its menu edits, port.py's MENU_EDITS/TEXT_EDITS generated into player_edits.h);
 *   4. optional --import-profile DIR: a developer play profile (User.ini, WindowsClient.ini, Save\*.usa) copied in;
 *      existing saves are never overwritten and the source is only read;
 *   5. the game process: this executable again with --xrt-child and the runtime's usual command line, in a
 *      kill-on-close Job (the DirectMusic helper and anything else it starts end with it), the session's logs in
 *      Logs\<time>\; the launcher waits, restores the desktop input settings and reports an abnormal end.
 * The game process reads the installation only through the runtime's content overlay (xrt_internal.h): the installation
 * is never written, its Save folder never used. There is no session time limit; the game's own Quit ends it.
 *
 * Options (for troubleshooting; a normal start needs none): --game DIR, --select-game, --data DIR,
 * --import-profile DIR, --diagnostics (development trace profile and strict buffer staging, the reference mode),
 * --nosound, --prepare-only (check the installation and prepare the data folder, then stop), --unattended (no dialogs: messages go to Logs\player.log; implied by the developer input variables). */
#define COBJMACROS
#include <windows.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <shellapi.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "xrt_internal.h"
#include "player_edits.h"

#define PLAYER_TITLE L"Unreal II Enhanced"
#define KEEP_SESSIONS 8
enum { EXIT_INSTALL = 3, EXIT_DATA = 4, EXIT_RUNNING = 5, EXIT_LAUNCH = 6 };

static WCHAR exe_path[MAX_PATH], exe_dir[MAX_PATH], data_dir[MAX_PATH], game_dir[MAX_PATH], log_dir[MAX_PATH];
static int unattended, diagnostics, nosound, prepare_only;
static FILE* player_log;

static void note(const WCHAR* fmt, ...) {
    va_list a;
    SYSTEMTIME t;
    if (!player_log)
        return;
    GetLocalTime(&t);
    fwprintf(player_log, L"%04u-%02u-%02u %02u:%02u:%02u ", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
    va_start(a, fmt);
    vfwprintf(player_log, fmt, a);
    va_end(a);
    fputwc(L'\n', player_log);
    fflush(player_log);
}
static void tell(UINT icon, const WCHAR* fmt, ...) {
    WCHAR text[4096];
    va_list a;
    va_start(a, fmt);
    _vsnwprintf(text, 4095, fmt, a);
    va_end(a);
    text[4095] = 0;
    note(L"%s", text);
    if (!unattended)
        MessageBoxW(NULL, text, PLAYER_TITLE, icon | MB_OK | MB_SETFOREGROUND);
}
static __declspec(noreturn) void fail(int code, const WCHAR* fmt, ...) {
    WCHAR text[4096];
    va_list a;
    va_start(a, fmt);
    _vsnwprintf(text, 4095, fmt, a);
    va_end(a);
    text[4095] = 0;
    tell(MB_ICONERROR, L"%s", text);
    ExitProcess(code);
}

/* ---------------------------------------------------------------- paths */
static int exists(const WCHAR* p) { return GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES; }
static int is_dir(const WCHAR* p) { DWORD a = GetFileAttributesW(p); return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY); }
static void join(WCHAR* out, const WCHAR* a, const WCHAR* b) { _snwprintf(out, MAX_PATH, L"%s\\%s", a, b); out[MAX_PATH - 1] = 0; }
static int inside(const WCHAR* p, const WCHAR* root) {   /* p is root or below it */
    size_t n = wcslen(root);
    return !_wcsnicmp(p, root, n) && (p[n] == 0 || p[n] == L'\\');
}
/* The runtime takes narrow (ANSI code page) paths: refuse a folder whose name the code page cannot represent. */
static int ansi_ok(const WCHAR* p) {
    char a[MAX_PATH * 2];
    BOOL lossy = FALSE;
    return WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, p, -1, a, sizeof a, NULL, &lossy) && !lossy && strlen(a) < 400;
}
/* No component of p (a full path) may be a link: the DirectMusic helper's disk guard refuses them, and the player never
 * follows a link out of the folder the user chose. */
static int has_link(const WCHAR* p) {
    WCHAR part[MAX_PATH];
    size_t i;
    DWORD a;
    for (i = 3; i <= wcslen(p); i++)
        if (p[i] == L'\\' || p[i] == 0) {
            wcsncpy(part, p, i);
            part[i] = 0;
            a = GetFileAttributesW(part);
            if (a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_REPARSE_POINT))
                return 1;
        }
    return 0;
}
static void make_dir(const WCHAR* p) {
    if (!CreateDirectoryW(p, NULL) && GetLastError() != ERROR_ALREADY_EXISTS)
        fail(EXIT_DATA, L"Cannot create the folder\n%s\n(Windows error %lu).", p, GetLastError());
}

/* ---------------------------------------------------------------- the installation */
/* the folder with System\Unreal2.exe: DIR\singleplayer (GOG/retail layout), DIR, or DIR's parent when DIR is System */
static int normalize_game(const WCHAR* in, WCHAR* out) {
    WCHAR full[MAX_PATH], cand[MAX_PATH], probe[MAX_PATH], *slash;
    int k;
    if (!in[0] || !GetFullPathNameW(in, MAX_PATH, full, NULL))
        return 0;
    for (k = (int)wcslen(full); k > 3 && full[k - 1] == L'\\'; k--)
        full[k - 1] = 0;
    for (k = 0; k < 3; k++) {
        if (k == 0)
            join(cand, full, L"singleplayer");
        else if (k == 1)
            wcscpy(cand, full);
        else if ((slash = wcsrchr(wcscpy(cand, full), L'\\')) && !_wcsicmp(slash, L"\\System"))
            *slash = 0;
        else
            continue;
        join(probe, cand, L"System\\Unreal2.exe");
        if (exists(probe)) {
            wcscpy(out, cand);
            return 1;
        }
    }
    return 0;
}
static int discover(WCHAR* out) {
    static const WCHAR* const keys[] = {L"SOFTWARE\\WOW6432Node\\GOG.com\\Games\\1207658677", L"SOFTWARE\\GOG.com\\Games\\1207658677"};
    WCHAR dir[MAX_PATH], *slash, value[MAX_PATH];
    DWORD n;
    int i;
    wcscpy(dir, exe_dir);   /* the player unpacked into (a folder of) the installation */
    for (i = 0; i < 3; i++) {
        if (normalize_game(dir, out))
            return 1;
        if (!(slash = wcsrchr(dir, L'\\')) || slash - dir < 3)
            break;
        *slash = 0;
    }
    for (i = 0; i < 2; i++) {
        n = sizeof value;
        if (RegGetValueW(HKEY_LOCAL_MACHINE, keys[i], L"path", RRF_RT_REG_SZ, NULL, value, &n) == ERROR_SUCCESS &&
            normalize_game(value, out))
            return 1;
    }
    return 0;
}
static int pick_folder(WCHAR* out) {
    IFileOpenDialog* d = NULL;
    IShellItem* item = NULL;
    WCHAR* path = NULL;
    DWORD options;
    int ok = 0;
    if (unattended)
        return 0;
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    if (SUCCEEDED(CoCreateInstance(&CLSID_FileOpenDialog, NULL, CLSCTX_INPROC_SERVER, &IID_IFileOpenDialog, (void**)&d))) {
        IFileOpenDialog_GetOptions(d, &options);
        IFileOpenDialog_SetOptions(d, options | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
        IFileOpenDialog_SetTitle(d, L"Select your Unreal II: The Awakening installation folder");
        if (SUCCEEDED(IFileOpenDialog_Show(d, NULL)) && SUCCEEDED(IFileOpenDialog_GetResult(d, &item)) &&
            SUCCEEDED(IShellItem_GetDisplayName(item, SIGDN_FILESYSPATH, &path))) {
            wcsncpy(out, path, MAX_PATH - 1);
            out[MAX_PATH - 1] = 0;
            ok = 1;
        }
        if (path)
            CoTaskMemFree(path);
        if (item)
            IShellItem_Release(item);
        IFileOpenDialog_Release(d);
    }
    CoUninitialize();
    return ok;
}

static int sha256_file(const WCHAR* path, char hex[65]) {
    BCRYPT_ALG_HANDLE alg = NULL;
    BCRYPT_HASH_HANDLE h = NULL;
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    static unsigned char buf[1 << 20];
    unsigned char digest[32];
    DWORD got;
    int ok = 0, i;
    if (f == INVALID_HANDLE_VALUE)
        return 0;
    if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, 0) == 0 && BCryptCreateHash(alg, &h, NULL, 0, NULL, 0, 0) == 0) {
        while (ReadFile(f, buf, sizeof buf, &got, NULL) && got)
            BCryptHashData(h, buf, got, 0);
        ok = BCryptFinishHash(h, digest, 32, 0) == 0;
    }
    if (h)
        BCryptDestroyHash(h);
    if (alg)
        BCryptCloseAlgorithmProvider(alg, 0);
    CloseHandle(f);
    for (i = 0; ok && i < 32; i++)
        sprintf(hex + 2 * i, "%02x", digest[i]);
    return ok;
}

/* Files the game needs from the installation, and the translated modules (System\ relative) whose bytes must be those
 * the code was translated from: the runtime maps the original images as data and would refuse any other version. */
static const WCHAR* const required[] = {
    L"System\\Unreal2.ini", L"System\\User.ini", L"System\\Default.ini", L"System\\DefUser.ini", L"System\\U2Menus.int",
    L"System\\msvcr70.dll", L"System\\Core.u", L"System\\Engine.u", L"UIScripts\\U2Menus.ui", L"Maps\\CS_Intro.un2",
    L"Maps\\TutA.un2", L"Music\\Intro.con", L"Textures", L"Sounds", L"StaticMeshes", L"Meshes", L"Voice", L"Scripts",
    L"Dialog"};
static const char* const modules[] = {
    "Unreal2.exe", "Core.dll", "Engine.dll", "Window.dll", "GlmLib.dll", "Plugins\\UnrImp.gpi", "WinDrv.dll", "D3DDrv.dll",
    "ParticleSystems.dll", "Legend.dll", "UI.dll", "Fire.dll", "U2.dll", "U2Dialog.dll", "U2AI.dll", "Editor.dll",
    "ALAudio.dll", "vorbisfile.dll", "ogg.dll", "vorbis.dll"};

/* NULL when DIR is a usable installation, else why not (shown to the player) */
static const WCHAR* check_game(const WCHAR* dir) {
    static WCHAR why[1024];
    WCHAR p[MAX_PATH], w[64];
    char hex[65];
    size_t i;
    if (!ansi_ok(dir))
        return L"The folder name contains characters this port cannot pass to the game. Move or rename the installation "
               L"folder (letters, digits and spaces of your Windows language work).";
    if (has_link(dir))
        return L"The folder (or a folder above it) is a link (junction or symbolic link). Select the real folder.";
    if (inside(data_dir, dir) || inside(dir, data_dir))
        return L"The installation folder and the player's data folder must be separate.";
    for (i = 0; i < sizeof required / sizeof required[0]; i++) {
        join(p, dir, required[i]);
        if (!exists(p)) {
            _snwprintf(why, 1023, L"Required game file or folder missing:\n%s\n\nCheck that the installation is complete "
                                  L"(Unreal II: The Awakening, single player).", p);
            return why;
        }
    }
    join(p, dir, L"Music");
    if (has_link(p))
        return L"The installation's Music folder is a link; music cannot be read from it.";
    for (i = 0; i < sizeof modules / sizeof modules[0]; i++) {
        const XrtLiftedModule* l = xrt_lifted_find(modules[i]);
        MultiByteToWideChar(CP_ACP, 0, modules[i], -1, w, 64);
        _snwprintf(p, MAX_PATH, L"%s\\System\\%s", dir, w);
        if (!l)
            continue;   /* a build without the sound modules: ALAudio and the Ogg libraries are not translated */
        if (!sha256_file(p, hex)) {
            _snwprintf(why, 1023, L"Required game file missing or unreadable:\n%s", p);
            return why;
        }
        if (strcmp(hex, l->sha256)) {
            _snwprintf(why, 1023, L"%s is not the version this port was made for (Unreal II: The Awakening Special Edition, "
                                  L"as sold by GOG).\n\nFile: %s\nSHA-256: %hs\nexpected: %hs", w, p, hex, l->sha256);
            return why;
        }
    }
    return NULL;
}

/* ---------------------------------------------------------------- the data folder */
static int same_file(const WCHAR* a, const WCHAR* b) {   /* by size and last-write time (CopyFileW keeps the time) */
    WIN32_FILE_ATTRIBUTE_DATA x, y;
    return GetFileAttributesExW(a, GetFileExInfoStandard, &x) && GetFileAttributesExW(b, GetFileExInfoStandard, &y) &&
           x.nFileSizeLow == y.nFileSizeLow && x.nFileSizeHigh == y.nFileSizeHigh &&
           !CompareFileTime(&x.ftLastWriteTime, &y.ftLastWriteTime);
}
/* Copy the installation's System folder (recursively) into the data folder: new or changed files only, never the logs,
 * the player's ini files once they exist, nor the menu text the port edits (written below). */
static unsigned copy_system(const WCHAR* from, const WCHAR* to, int top) {
    WIN32_FIND_DATAW fd;
    WCHAR pattern[MAX_PATH], src[MAX_PATH], dst[MAX_PATH];
    HANDLE h;
    unsigned copied = 0;
    size_t n;
    join(pattern, from, L"*");
    if ((h = FindFirstFileW(pattern, &fd)) == INVALID_HANDLE_VALUE)
        fail(EXIT_INSTALL, L"Cannot read the installation folder\n%s", from);
    make_dir(to);
    do {
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..") || (fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT))
            continue;
        join(src, from, fd.cFileName);
        join(dst, to, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            copied += copy_system(src, dst, 0);
            continue;
        }
        n = wcslen(fd.cFileName);
        if (top && (n > 4 && (!_wcsicmp(fd.cFileName + n - 4, L".log") || (!_wcsicmp(fd.cFileName + n - 4, L".ini") && exists(dst)))))
            continue;
        if (top && (!_wcsicmp(fd.cFileName, L"U2Menus.int") || !_wcsicmp(fd.cFileName, L"U2Port.u")))
            continue;
        if (same_file(src, dst))
            continue;
        SetFileAttributesW(dst, FILE_ATTRIBUTE_NORMAL);
        if (!CopyFileW(src, dst, FALSE))
            fail(EXIT_DATA, L"Cannot copy\n%s\nto\n%s\n(Windows error %lu).", src, dst, GetLastError());
        SetFileAttributesW(dst, FILE_ATTRIBUTE_NORMAL);   /* a read-only installation file stays writable for the game */
        copied++;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return copied;
}
/* The installation's folders (empty) in the data folder: the game changes into content folders (GlmLib walks Meshes\
 * with _chdir and _findfirst("*.gem")); the runtime's overlay then lists and reads their files from the installation. */
static unsigned mirror_dirs(const WCHAR* from, const WCHAR* to, int top) {
    WIN32_FIND_DATAW fd;
    WCHAR pattern[MAX_PATH], src[MAX_PATH], dst[MAX_PATH];
    HANDLE h;
    unsigned made = 0;
    join(pattern, from, L"*");
    if ((h = FindFirstFileW(pattern, &fd)) == INVALID_HANDLE_VALUE)
        return 0;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || (fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) ||
            !wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..") ||
            (top && (!_wcsicmp(fd.cFileName, L"Save") || !_wcsicmp(fd.cFileName, L"System"))))
            continue;
        join(src, from, fd.cFileName);
        join(dst, to, fd.cFileName);
        if (CreateDirectoryW(dst, NULL))
            made++;
        else if (GetLastError() != ERROR_ALREADY_EXISTS)
            fail(EXIT_DATA, L"Cannot create the folder\n%s\n(Windows error %lu).", dst, GetLastError());
        made += mirror_dirs(src, dst, 0);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return made;
}
static char* read_all(const WCHAR* path, size_t* size) {
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    LARGE_INTEGER n;
    char* buf = NULL;
    DWORD got = 0;
    if (f == INVALID_HANDLE_VALUE)
        return NULL;
    if (GetFileSizeEx(f, &n) && n.QuadPart < (64 << 20) && (buf = (char*)malloc((size_t)n.QuadPart + 1)) &&
        ReadFile(f, buf, (DWORD)n.QuadPart, &got, NULL) && got == (DWORD)n.QuadPart) {
        buf[got] = 0;
        *size = got;
    } else {
        free(buf);
        buf = NULL;
    }
    CloseHandle(f);
    return buf;
}
static void write_all(const WCHAR* path, const char* data, size_t size) {
    HANDLE f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD put = 0;
    if (f == INVALID_HANDLE_VALUE || !WriteFile(f, data, (DWORD)size, &put, NULL) || put != size) {
        if (f != INVALID_HANDLE_VALUE)
            CloseHandle(f);
        fail(EXIT_DATA, L"Cannot write\n%s\n(Windows error %lu).", path, GetLastError());
    }
    CloseHandle(f);
}
static const char* find_bytes(const char* hay, size_t n, const char* needle, size_t k) {
    size_t i;
    for (i = 0; k <= n && i <= n - k; i++)
        if (hay[i] == needle[0] && !memcmp(hay + i, needle, k))
            return hay + i;
    return NULL;
}
/* port.py edit(): every anchor must occur exactly once, replacements applied in order (texts already CRLF) */
static void apply_edits(const WCHAR* from, const WCHAR* to, const char* const (*edits)[2], size_t count) {
    size_t size, i, k, m;
    char* text = read_all(from, &size);
    if (!text)
        fail(EXIT_INSTALL, L"Cannot read\n%s", from);
    for (i = 0; i < count; i++) {
        const char *old = edits[i][0], *new_ = edits[i][1], *at;
        k = strlen(old);
        m = strlen(new_);
        if (!(at = find_bytes(text, size, old, k)) || find_bytes(at + 1, size - (size_t)(at + 1 - text), old, k))
            fail(EXIT_INSTALL, L"%s differs from the version this port's menus were made for (edit %u of %u).\n\nThe "
                               L"installation may be modified or a different release.", from, (unsigned)i + 1, (unsigned)count);
        {
            size_t pos = (size_t)(at - text);
            char* grown = (char*)malloc(size - k + m + 1);
            if (!grown)
                fail(EXIT_DATA, L"Out of memory");
            memcpy(grown, text, pos);
            memcpy(grown + pos, new_, m);
            memcpy(grown + pos + m, text + pos + k, size - pos - k + 1);
            free(text);
            text = grown;
            size = size - k + m;
        }
    }
    write_all(to, text, size);
    free(text);
}
static void prepare_data(void) {
    WCHAR from[MAX_PATH], to[MAX_PATH], p[MAX_PATH];
    unsigned copied;
    join(from, game_dir, L"System");
    join(to, data_dir, L"System");
    copied = copy_system(from, to, 1);
    join(p, exe_dir, L"port\\U2Port.u");
    join(to, data_dir, L"System\\U2Port.u");
    if (!CopyFileW(p, to, FALSE))
        fail(EXIT_LAUNCH, L"The player files are incomplete: cannot copy\n%s\n(Windows error %lu).", p, GetLastError());
    join(from, game_dir, L"System\\U2Menus.int");
    join(to, data_dir, L"System\\U2Menus.int");
    apply_edits(from, to, player_text_edits, sizeof player_text_edits / sizeof player_text_edits[0]);
    join(p, data_dir, L"UIScripts");
    make_dir(p);
    join(from, game_dir, L"UIScripts\\U2Menus.ui");
    join(to, data_dir, L"UIScripts\\U2Menus.ui");
    apply_edits(from, to, player_menu_edits, sizeof player_menu_edits / sizeof player_menu_edits[0]);
    join(p, data_dir, L"Save");
    make_dir(p);
    join(p, data_dir, L"Temp");
    make_dir(p);
    note(L"data folder ready: %u installation file(s) copied or refreshed, %u installation folder(s) mirrored", copied,
         mirror_dirs(game_dir, data_dir, 1));
}

/* ---------------------------------------------------------------- profile import */
/* replace the body of [WinDrv.WindowsClient] (dev.py replace_ini_section) */
static int replace_section(char** text, size_t* size, const char* body, size_t blen) {
    static const char head[] = "[WinDrv.WindowsClient]";
    const char *s = *text, *at = NULL, *start, *end;
    size_t i;
    char* out;
    for (i = 0; i + sizeof head - 1 <= *size; i++)
        if ((i == 0 || s[i - 1] == '\n') && !memcmp(s + i, head, sizeof head - 1) &&
            (s[i + sizeof head - 1] == '\r' || s[i + sizeof head - 1] == '\n')) {
            at = s + i;
            break;
        }
    if (!at || !(start = memchr(at, '\n', *size - (size_t)(at - s))))
        return 0;
    for (end = ++start; end < s + *size && *end != '[';) {   /* end: the start of the next section's line */
        const char* nl = (const char*)memchr(end, '\n', (size_t)(s + *size - end));
        end = nl ? nl + 1 : s + *size;
    }
    if (!(out = (char*)malloc(*size + blen + 1)))
        return 0;
    memcpy(out, s, (size_t)(start - s));
    memcpy(out + (start - s), body, blen);
    memcpy(out + (start - s) + blen, end, (size_t)(s + *size - end) + 1);
    *size = (size_t)(start - s) + blen + (size_t)(s + *size - end);
    free(*text);
    *text = out;
    return 1;
}
static void backup(const WCHAR* path, const WCHAR* stamp) {
    WCHAR b[MAX_PATH];
    int k;
    if (!exists(path))
        return;
    for (k = 1; k < 100; k++) {   /* never over an earlier backup */
        _snwprintf(b, MAX_PATH, k == 1 ? L"%s.before-import-%s" : L"%s.before-import-%s-%d", path, stamp, k);
        if (CopyFileW(path, b, TRUE))
            return;
        if (GetLastError() != ERROR_FILE_EXISTS)
            break;
    }
    fail(EXIT_DATA, L"Cannot back up\n%s", path);
}
static void import_profile(const WCHAR* dir, const WCHAR* stamp) {
    WCHAR src[MAX_PATH], dst[MAX_PATH], pattern[MAX_PATH];
    WIN32_FIND_DATAW fd;
    HANDLE h;
    unsigned saves = 0, kept = 0;
    char *ini, *body;
    size_t isize, bsize;
    if (!is_dir(dir))
        fail(EXIT_DATA, L"--import-profile: not a folder:\n%s", dir);
    join(src, dir, L"User.ini");
    join(dst, data_dir, L"System\\User.ini");
    if (exists(src)) {
        backup(dst, stamp);
        if (!CopyFileW(src, dst, FALSE))
            fail(EXIT_DATA, L"Cannot import\n%s", src);
    }
    join(src, dir, L"WindowsClient.ini");
    join(dst, data_dir, L"System\\Unreal2.ini");
    if (exists(src)) {
        if (!(body = read_all(src, &bsize)) || !(ini = read_all(dst, &isize)) || !replace_section(&ini, &isize, body, bsize))
            fail(EXIT_DATA, L"Cannot import the display settings\n%s", src);
        backup(dst, stamp);
        write_all(dst, ini, isize);
        free(ini);
        free(body);
    }
    join(pattern, dir, L"Save\\*.usa");
    if ((h = FindFirstFileW(pattern, &fd)) != INVALID_HANDLE_VALUE) {
        do {
            _snwprintf(src, MAX_PATH, L"%s\\Save\\%s", dir, fd.cFileName);
            _snwprintf(dst, MAX_PATH, L"%s\\Save\\%s", data_dir, fd.cFileName);
            if (CopyFileW(src, dst, TRUE))
                saves++;
            else
                kept++;   /* a save of that name exists: the player's own is never overwritten */
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    tell(MB_ICONINFORMATION, L"Profile imported from\n%s\n\nSettings: %s. Saved games: %u copied, %u not copied because a "
                             L"save of the same name already exists. The source folder was not changed.",
         dir, exists(src) ? L"User.ini and display settings" : L"User.ini", saves, kept);
}

/* ---------------------------------------------------------------- session logs */
static int session_name(const WCHAR* n) { return wcslen(n) == 15 && n[8] == L'-' && iswdigit(n[0]) && iswdigit(n[14]); }
static int by_name(const void* a, const void* b) { return wcscmp((const WCHAR*)a, (const WCHAR*)b); }
static void prune_sessions(const WCHAR* logs) {   /* keep the newest KEEP_SESSIONS session folders (flat, ours) */
    static WCHAR names[256][16];
    WCHAR pattern[MAX_PATH], dir[MAX_PATH], file[MAX_PATH];
    WIN32_FIND_DATAW fd;
    HANDLE h;
    int n = 0, i;
    join(pattern, logs, L"*");
    if ((h = FindFirstFileW(pattern, &fd)) == INVALID_HANDLE_VALUE)
        return;
    do
        if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && !(fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) &&
            session_name(fd.cFileName) && n < 256)
            wcscpy(names[n++], fd.cFileName);
    while (FindNextFileW(h, &fd));
    FindClose(h);
    qsort(names, (size_t)n, sizeof names[0], by_name);
    for (i = 0; i < n - KEEP_SESSIONS; i++) {
        join(dir, logs, names[i]);
        join(pattern, dir, L"*");
        if ((h = FindFirstFileW(pattern, &fd)) != INVALID_HANDLE_VALUE) {
            do
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                    join(file, dir, fd.cFileName);
                    DeleteFileW(file);
                }
            while (FindNextFileW(h, &fd));
            FindClose(h);
        }
        RemoveDirectoryW(dir);
    }
}

/* ---------------------------------------------------------------- environment */
static void env_set(const WCHAR* k, const WCHAR* v) { SetEnvironmentVariableW(k, v); }
static void env_default(const WCHAR* k, const WCHAR* v) { if (!GetEnvironmentVariableW(k, NULL, 0)) SetEnvironmentVariableW(k, v); }
static void drop_dxvk_environment(void) {
    WCHAR* block = GetEnvironmentStringsW(), *p, name[256];
    WCHAR* names = (WCHAR*)calloc(32768, sizeof(WCHAR));
    size_t used = 0, n;
    for (p = block; p && *p; p += wcslen(p) + 1)
        if (!_wcsnicmp(p, L"DXVK_", 5) && (n = wcscspn(p, L"=")) < 255 && used + n + 1 < 32768) {
            wcsncpy(names + used, p, n);
            used += n + 1;
        }
    if (block)
        FreeEnvironmentStringsW(block);
    for (p = names; names && *p; p += wcslen(p) + 1) {
        wcscpy(name, p);
        SetEnvironmentVariableW(name, NULL);
    }
    free(names);
}
static int startup_fullscreen(void) {
    WCHAR ini[MAX_PATH], v[16];
    join(ini, data_dir, L"System\\Unreal2.ini");
    GetPrivateProfileStringW(L"WinDrv.WindowsClient", L"StartupFullscreen", L"False", v, 16, ini);
    return !_wcsicmp(v, L"True");
}

/* ---------------------------------------------------------------- launcher */
static __declspec(noreturn) void launcher(void) {
    int argc = 0, i, select = 0;
    WCHAR** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    WCHAR game_arg[MAX_PATH] = L"", data_arg[MAX_PATH] = L"", import_arg[MAX_PATH] = L"", ini[MAX_PATH], p[MAX_PATH],
          stamp[32], cmd[4096], remembered[MAX_PATH], chosen[MAX_PATH], helper[MAX_PATH], dxvk[MAX_PATH], tmp[MAX_PATH];
    const WCHAR* why;
    SYSTEMTIME t;
    HANDLE single, job, out_log;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting = {0};
    STARTUPINFOW si = {sizeof si};
    PROCESS_INFORMATION pi = {0};
    SECURITY_ATTRIBUTES sa = {sizeof sa, NULL, TRUE};
    STICKYKEYS keys = {sizeof keys};
    RECT clip;
    BOOL have_keys, have_clip;
    DWORD code = 0, remaining = 0;
    char* report;
    size_t rsize;
    const char* outcome;

    GetModuleFileNameW(NULL, exe_path, MAX_PATH);
    wcscpy(exe_dir, exe_path);
    *wcsrchr(exe_dir, L'\\') = 0;
    unattended = GetEnvironmentVariableW(L"XRT_DEV_INPUT", NULL, 0) || GetEnvironmentVariableW(L"XRT_DEV_NO_INPUT", NULL, 0);
    for (i = 1; argv && i < argc; i++)   /* before any message about the other options */
        unattended |= !wcscmp(argv[i], L"--unattended");
    for (i = 1; argv && i < argc; i++) {
        WCHAR* value = i + 1 < argc ? argv[i + 1] : NULL;
        if (!wcscmp(argv[i], L"--game") && value)
            wcsncpy(game_arg, argv[++i], MAX_PATH - 1);
        else if (!wcscmp(argv[i], L"--data") && value)
            wcsncpy(data_arg, argv[++i], MAX_PATH - 1);
        else if (!wcscmp(argv[i], L"--import-profile") && value)
            wcsncpy(import_arg, argv[++i], MAX_PATH - 1);
        else if (!wcscmp(argv[i], L"--select-game"))
            select = 1;
        else if (!wcscmp(argv[i], L"--diagnostics"))
            diagnostics = 1;
        else if (!wcscmp(argv[i], L"--nosound"))
            nosound = 1;
        else if (!wcscmp(argv[i], L"--unattended"))
            unattended = 1;
        else if (!wcscmp(argv[i], L"--prepare-only"))
            prepare_only = 1;
        else
            fail(EXIT_LAUNCH, L"Unknown option: %s\n\nOptions: --game DIR, --select-game, --data DIR, --import-profile DIR, "
                              L"--diagnostics, --nosound, --prepare-only, --unattended", argv[i]);
    }

    /* 1. data folder */
    if (data_arg[0]) {
        if (!GetFullPathNameW(data_arg, MAX_PATH, data_dir, NULL))
            fail(EXIT_DATA, L"--data: invalid folder %s", data_arg);
    } else {
        WCHAR* local = NULL;
        if (FAILED(SHGetKnownFolderPath(&FOLDERID_LocalAppData, 0, NULL, &local)))
            fail(EXIT_DATA, L"Cannot find the local application data folder.");
        join(data_dir, local, L"UnrealIIEnhanced");
        CoTaskMemFree(local);
    }
    make_dir(data_dir);
    if (!ansi_ok(data_dir) || has_link(data_dir))
        fail(EXIT_DATA, L"The data folder\n%s\ncannot be used (a link, or characters the game cannot use). Start the player "
                        L"with --data and a plain folder.", data_dir);
    join(p, data_dir, L"Logs");
    make_dir(p);
    join(p, data_dir, L"Logs\\player.log");
    player_log = _wfopen(p, L"a, ccs=UTF-8");
    note(L"start %s (data %s)", exe_path, data_dir);
    single = CreateMutexW(NULL, FALSE, L"Local\\UnrealIIEnhancedPlayer");
    if (!single || GetLastError() == ERROR_ALREADY_EXISTS)
        fail(EXIT_RUNNING, L"Unreal II Enhanced is already running.");

    /* 2. installation */
    join(ini, data_dir, L"player.ini");
    if (!exists(ini)) {   /* UTF-16 file: WritePrivateProfileStringW then keeps any folder name */
        HANDLE f = CreateFileW(ini, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
        DWORD put;
        if (f != INVALID_HANDLE_VALUE) {
            WriteFile(f, "\xff\xfe", 2, &put, NULL);
            CloseHandle(f);
        }
    }
    GetPrivateProfileStringW(L"Player", L"GamePath", L"", remembered, MAX_PATH, ini);
    why = NULL;
    if (game_arg[0]) {
        if (!normalize_game(game_arg, game_dir))
            fail(EXIT_INSTALL, L"No Unreal II installation (System\\Unreal2.exe) found in\n%s", game_arg);
        why = check_game(game_dir);
    } else if (!select && remembered[0] && normalize_game(remembered, game_dir) && !(why = check_game(game_dir))) {
        ;
    } else if (!select && discover(game_dir) && !(why = check_game(game_dir))) {
        note(L"installation found: %s", game_dir);
    } else {
        if (why)
            tell(MB_ICONWARNING, L"The Unreal II installation\n%s\ncannot be used:\n\n%s", game_dir, why);
        else if (!unattended)
            tell(MB_ICONINFORMATION, L"Unreal II Enhanced plays the original Unreal II: The Awakening, which you need to "
                                     L"have installed (Special Edition, e.g. from GOG).\n\nPlease select the game's "
                                     L"installation folder (the one containing \"singleplayer\" or \"System\"). It is only "
                                     L"read, never changed.");
        for (;;) {
            if (!pick_folder(chosen))
                fail(EXIT_INSTALL, L"No Unreal II installation selected. Start the player again to choose one%s.",
                     unattended ? L" (or pass --game DIR)" : L"");
            if (!normalize_game(chosen, game_dir)) {
                tell(MB_ICONWARNING, L"No Unreal II installation (System\\Unreal2.exe) was found in\n%s\n\nSelect the "
                                     L"folder that contains \"singleplayer\" or \"System\".", chosen);
                continue;
            }
            if (!(why = check_game(game_dir)))
                break;
            tell(MB_ICONWARNING, L"The Unreal II installation\n%s\ncannot be used:\n\n%s", game_dir, why);
        }
    }
    if (why)
        fail(EXIT_INSTALL, L"The Unreal II installation\n%s\ncannot be used:\n\n%s", game_dir, why);
    WritePrivateProfileStringW(L"Player", L"GamePath", game_dir, ini);
    note(L"installation %s verified", game_dir);

    /* 3. data folder contents, 4. import */
    prepare_data();
    GetLocalTime(&t);
    _snwprintf(stamp, 32, L"%04u%02u%02u-%02u%02u%02u", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
    if (import_arg[0]) {
        WCHAR full[MAX_PATH];
        if (!GetFullPathNameW(import_arg, MAX_PATH, full, NULL) || inside(full, data_dir) || inside(full, game_dir))
            fail(EXIT_DATA, L"--import-profile: choose a profile folder outside the installation and the data folder.");
        import_profile(full, stamp);
    }
    if (prepare_only) {
        tell(MB_ICONINFORMATION, L"Installation checked and data folder prepared (--prepare-only); the game was not started.\n\n"
                                 L"Installation: %s\nData: %s", game_dir, data_dir);
        ExitProcess(0);
    }

    /* 5. the game process */
    if (!GetEnvironmentVariableW(L"XRT_DEV_OUTPUT", log_dir, MAX_PATH)) {
        join(p, data_dir, L"Logs");
        prune_sessions(p);
        _snwprintf(log_dir, MAX_PATH, L"%s\\Logs\\%s", data_dir, stamp);
        make_dir(log_dir);
        env_set(L"XRT_DEV_OUTPUT", log_dir);
    }
    join(helper, exe_dir, L"dmusic_helper.exe");
    join(dxvk, exe_dir, L"dxvk");
    join(p, dxvk, L"d3d8.dll");
    if (!exists(helper) || !exists(p))
        fail(EXIT_LAUNCH, L"The player files are incomplete (dmusic_helper.exe, dxvk\\d3d8.dll beside the executable). "
                          L"Unpack the whole distribution again.");
    env_set(L"XRT_CONTENT_ROOT", game_dir);
    join(tmp, data_dir, L"Temp");
    env_set(L"TEMP", tmp);
    env_set(L"TMP", tmp);
    env_set(L"XRT_DMUSIC_BACKEND", L"ipc");
    env_set(L"XRT_DMUSIC_HELPER", helper);
    env_set(L"XRT_D3D8_DIR", dxvk);
    drop_dxvk_environment();
    join(p, log_dir, L"dxvk.conf");
    write_all(p, "", 0);
    env_set(L"DXVK_CONFIG", L"");
    env_set(L"DXVK_CONFIG_FILE", p);
    env_set(L"DXVK_LOG_PATH", log_dir);
    env_set(L"DXVK_SHADER_CACHE", L"0");
    join(p, log_dir, L"monitor.bin");
    env_set(L"XRT_MONITOR_STREAM", p);
    env_default(L"XRT_MONITOR_PROFILE", diagnostics ? L"development" : L"quiet");
    env_default(L"XRT_DEV_STAGING", diagnostics ? L"strict" : L"guard");   /* play default: guard (owner decision R4) */
    env_default(L"XRT_DEV_SCENE", L"0");          /* continue past Init, no world-frame stop (dev.py --play) */
    env_default(L"XRT_DEV_ALLOW_MAPS", L"*");
    env_default(L"XRT_DEV_CAPTURE", L"shots");     /* no frame readbacks unless an input script asks for one */
    if (!nosound)
        env_default(L"XRT_DEV_SOUND", L"on");
    _snwprintf(cmd, 4096, L"\"%s\" --xrt-child --guest \"%s\\System\\Unreal2.exe\" --log \"%s\\xrt.log\" --report "
                          L"\"%s\\runtime-report.json\" --run-id player-%s -- CS_Intro.un2%s%s -NOMMX -NOSSE",
               exe_path, data_dir, log_dir, log_dir, stamp, startup_fullscreen() ? L"" : L" -windowed",
               nosound ? L" -nosound" : L"");
    note(L"game process: %s", cmd);

    job = CreateJobObjectW(NULL, NULL);
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits))
        fail(EXIT_LAUNCH, L"Cannot create the game's process group (Windows error %lu).", GetLastError());
    out_log = GetStdHandle(STD_OUTPUT_HANDLE);   /* started by the developer harness (contain.exe): its console.txt */
    if (!out_log || out_log == INVALID_HANDLE_VALUE || GetFileType(out_log) == FILE_TYPE_UNKNOWN) {
        join(p, log_dir, L"console.txt");
        out_log = CreateFileW(p, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    }
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = si.hStdError = out_log;
    si.hStdInput = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
    have_keys = SystemParametersInfoW(SPI_GETSTICKYKEYS, sizeof keys, &keys, 0);
    have_clip = GetClipCursor(&clip);
    join(p, data_dir, L"System");
    if (out_log == INVALID_HANDLE_VALUE ||
        !CreateProcessW(exe_path, cmd, NULL, NULL, TRUE, CREATE_SUSPENDED, NULL, p, &si, &pi))
        fail(EXIT_LAUNCH, L"Cannot start the game (Windows error %lu).", GetLastError());
    if (!AssignProcessToJobObject(job, pi.hProcess)) {
        TerminateProcess(pi.hProcess, EXIT_LAUNCH);
        fail(EXIT_LAUNCH, L"Cannot start the game in its process group (Windows error %lu).", GetLastError());
    }
    AllowSetForegroundWindow(pi.dwProcessId);
    ResumeThread(pi.hThread);
    note(L"game process %lu started; logs in %s", pi.dwProcessId, log_dir);
    WaitForSingleObject(pi.hProcess, INFINITE);
    if (!GetExitCodeProcess(pi.hProcess, &code))
        code = 125;
    /* the helper and anything else the game started end with it */
    TerminateJobObject(job, code);
    {
        ULONGLONG until = GetTickCount64() + 5000;
        do {
            if (!QueryInformationJobObject(job, JobObjectBasicAccountingInformation, &accounting, sizeof accounting, NULL)) {
                remaining = MAXDWORD;
                break;
            }
            if (!(remaining = accounting.ActiveProcesses))
                break;
            Sleep(20);
        } while (GetTickCount64() < until);
    }
    CloseHandle(job);
    if (have_keys)
        SystemParametersInfoW(SPI_SETSTICKYKEYS, sizeof keys, &keys, 0);
    if (have_clip)
        ClipCursor(&clip);
    else
        ClipCursor(NULL);
    join(p, log_dir, L"runtime-report.json");
    report = read_all(p, &rsize);
    outcome = report ? strstr(report, "\"outcome\": \"") : NULL;
    {
        char what[160] = "no runtime report";
        WCHAR wwhat[160];
        if (outcome) {
            outcome += 12;
            _snprintf(what, sizeof what - 1, "%.*s", (int)strcspn(outcome, "\""), outcome);
        }
        MultiByteToWideChar(CP_ACP, 0, what, -1, wwhat, 160);
        note(L"game process ended: exit %lu, outcome %s, processes left %lu", code, wwhat, remaining);
        join(p, log_dir, L"session.json");
        {
            char j[512];
            int n = _snprintf(j, sizeof j, "{\"exit_code\": %lu, \"outcome\": \"%s\", \"remaining_processes\": %lu, "
                                           "\"game_pid\": %lu}\n", code, what, remaining, pi.dwProcessId);
            write_all(p, j, (size_t)(n > 0 ? n : 0));
        }
        if (!(code == 0 && !strcmp(what, "exited")))
            tell(MB_ICONWARNING, L"Unreal II Enhanced stopped unexpectedly (exit %lu: %s).\n\nYour saved games are kept in\n"
                                 L"%s\\Save\n\nLogs for a report: %s", code, wwhat, data_dir, log_dir);
    }
    free(report);
    if (player_log)
        fclose(player_log);
    ExitProcess(code);
}

/* xrt_main.c: 1 in the game process (argv now the runtime's own), never returns in the launcher */
int xrt_player_setup(int* argc, char*** argv) {
    DWORD n;
    if (*argc >= 2 && !strcmp((*argv)[1], "--xrt-child")) {
        n = GetEnvironmentVariableA("XRT_CONTENT_ROOT", xrt_content_root, sizeof xrt_content_root);
        if (!n || n >= sizeof xrt_content_root) {
            fprintf(stderr, "player: the game process needs its installation (XRT_CONTENT_ROOT)\n");
            ExitProcess(EXIT_LAUNCH);
        }
        (*argv)[1] = (*argv)[0];
        (*argv)++;
        (*argc)--;
        return 1;
    }
    launcher();
}
