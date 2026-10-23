/* Identical x86 source is executed by Windows and lifted into the actual x64 runtime. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
__declspec(dllexport) int probe_log[128], probe_log_n;
/* Keep a real SHELL32 import in the fixture, as in Window.dll. */
__declspec(dllexport) FARPROC shell_import(void) { return (FARPROC)ShellExecuteW; }
static int failures;
static void expect(int value, int wanted) {
    probe_log[probe_log_n++] = value;
    if (value != wanted) failures++;
}
__declspec(dllexport) int probe_modules(void) {
    HMODULE k, s, a, b, self;
    FARPROC p;
    char path[600];
    k = GetModuleHandleA("KERNEL32");
    expect(k != NULL, 1);
    expect(k == GetModuleHandleW(L"kernel32.DLL"), 1);
    expect(GetModuleHandleA(NULL) == GetModuleHandleW(NULL), 1);
    s = GetModuleHandleW(L"SHELL32.DLL");
    expect(s != NULL, 1);
    expect(s == GetModuleHandleA("shell32"), 1);
    expect(GetModuleHandleW(L"C:\\no-such-directory\\shell32.dll") == NULL, 1);
    expect(GetLastError(), ERROR_MOD_NOT_FOUND);
    expect(GetModuleHandleW(L"xrt-never-loaded-unique.dll") == NULL, 1);
    expect(GetLastError(), ERROR_MOD_NOT_FOUND);
    expect(GetProcAddress(s, "Shell_NotifyIconW") != NULL, 1);
    expect(GetProcAddress(s, "SHGetSpecialFolderPathW") != NULL, 1);
    expect(GetProcAddress(k, "GetLastError") == (FARPROC)GetLastError, 1);
    expect(GetProcAddress(k, "getlasterror") == NULL, 1);
    expect(GetLastError(), ERROR_PROC_NOT_FOUND);
    expect(GetProcAddress(k, "XrtNoSuchExport") == NULL, 1);
    expect(GetLastError(), ERROR_PROC_NOT_FOUND);
    self = GetModuleHandleA("moduleprobe.dll");
    expect(self != NULL, 1);
    expect(GetModuleFileNameA(self, path, sizeof path) > 0, 1);
    expect(self == GetModuleHandleA(path), 1);
    expect(GetModuleHandleA("C:\\no-such-directory\\moduleprobe.dll") == NULL, 1);
    expect(GetLastError(), ERROR_MOD_NOT_FOUND);
    expect(GetProcAddress(self, "probe_log") == (FARPROC)probe_log, 1);
    expect(GetModuleFileNameA(self, path, sizeof path) > 0, 1);
    p = GetProcAddress(k, "GetLastError");
    expect(((DWORD(WINAPI*)(void))p)(), ERROR_SUCCESS);
    expect(GetModuleHandleW(L"RICHED32.DLL") == NULL, 1);
    a = LoadLibraryW(L"RICHED32.DLL");
    expect(a != NULL, 1);
    b = LoadLibraryA("riched32");
    expect(a == b, 1);
    expect(a == GetModuleHandleW(L"riched32.dll"), 1);
    expect(GetModuleFileNameA(a, path, sizeof path) > 0, 1);
    expect(FreeLibrary(a), 1);
    expect(b == GetModuleHandleA("RICHED32.DLL"), 1);
    expect(FreeLibrary(b), 1);
    expect(GetModuleHandleW(L"RICHED32.DLL") == NULL, 1);
    expect(GetLastError(), ERROR_MOD_NOT_FOUND);
    expect(FreeLibrary(b), 0);
    expect(GetLastError(), ERROR_MOD_NOT_FOUND);
    expect(FreeLibrary(NULL), 0);
    expect(GetLastError(), ERROR_MOD_NOT_FOUND);
    return failures;
}
__declspec(dllexport) int probe_unadapted_export(void) {
    /* Getting a real export is allowed. Calling an unimplemented ABI must remain an explicit trap. */
    FARPROC p = GetProcAddress(GetModuleHandleW(L"SHELL32.DLL"), "Shell_NotifyIconW");
    return ((int(WINAPI*)(DWORD, void*))p)(0, NULL);
}
__declspec(dllexport) int probe_stale_export(void) {
    HMODULE m = LoadLibraryW(L"WINMM.DLL");
    FARPROC p = GetProcAddress(m, "timeGetTime");
    if (!m || !p) return 3;
    FreeLibrary(m);
    return ((int(WINAPI*)(void))p)();
}
__declspec(dllexport) int probe_transitive_identity(void) {
    return GetModuleHandleW(L"ntdll.dll") != NULL;
}
