/* hle_misc.c - host adapters for WINMM.dll, ADVAPI32.dll and ole32.dll imports used on the measured paths (stdcall).
 * USER32 only supports the launcher queries below; window creation/callbacks remain explicitly unsupported. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <mmsystem.h>
#include "xrt_internal.h"

static void hle_timeGetTime(CPU* c) { RET_STD(0, timeGetTime()); }
static void hle_timeBeginPeriod(CPU* c) { RET_STD(1, timeBeginPeriod(ARG(0))); }
static void hle_timeEndPeriod(CPU* c) { RET_STD(1, timeEndPeriod(ARG(0))); }

/* Resolve the host system library, never a DLL next to the guest. No guest callback is passed to USER32. */
static FARPROC user32_symbol(CPU* c, const char* name) {
    static HMODULE user32;
    FARPROC fn;
    if (!user32) user32 = LoadLibraryExW(L"user32.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    fn = user32 ? GetProcAddress(user32, name) : NULL;
    if (!fn) xrt_fatal(c, XRT_EXIT_SETUP, "host USER32 service unavailable: %s", name);
    return fn;
}
static void hle_FindWindowExA(CPU* c) {
    typedef HWND (WINAPI* Fn)(HWND, HWND, LPCSTR, LPCSTR);
    Fn fn;
    HWND result;
    uint32_t cls = ARG(2), title = ARG(3);
    if (ARG(0) || ARG(1))
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "FindWindowExA: non-null parent/previous window is unsupported");
    fn = (Fn)user32_symbol(c, "FindWindowExA");
    SetLastError(xrt_get_last_error(c));
    result = fn(NULL, NULL,
             cls ? (cls < 0x10000u ? MAKEINTATOM(cls) : (LPCSTR)G2H(cls)) : NULL,
             title ? (LPCSTR)G2H(title) : NULL);
    if (result)
        xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "FindWindowExA found an external window; launcher interprocess protocol unsupported");
    xrt_set_last_error(c, GetLastError());
    xrt_event("find_window", "\"result\": 0");
    RET_STD(4, 0); /* actual host query returned NULL */
}
static void hle_RegisterWindowMessageW(CPU* c) {
    typedef UINT (WINAPI* Fn)(LPCWSTR);
    UINT result = ((Fn)user32_symbol(c, "RegisterWindowMessageW"))((LPCWSTR)G2H(ARG(0)));
    if (!result) xrt_set_last_error(c, GetLastError());
    RET_STD(1, result);
}

static void hle_GetUserNameW(CPU* c) {
    DWORD n = rd32(ARG(1));
    BOOL ok = GetUserNameW((LPWSTR)G2H(ARG(0)), &n);
    if (!ok)
        xrt_set_last_error(c, GetLastError());
    wr32(ARG(1), n);
    RET_STD(2, ok);
}

/* CoCreateGuid (Core's appCreateGuid: package GUIDs). A fresh host GUID, as random as the original's; each value is
 * recorded as an evidence event, so a GUID found in a written package can be traced to the call that made it. */
static void hle_CoCreateGuid(CPU* c) {
    GUID g;
    HRESULT hr = CoCreateGuid(&g);
    char hex[33];
    int k;
    if (SUCCEEDED(hr))
        memcpy(G2H(ARG(0)), &g, 16);
    for (k = 0; k < 16; k++)          /* the 16 bytes in memory order: as a package header stores them */
        sprintf(hex + 2 * k, "%02x", SUCCEEDED(hr) ? ((const uint8_t*)&g)[k] : 0);
    xrt_event("create_guid", "\"result\": \"0x%08x\", \"bytes\": \"%s\"", (uint32_t)hr, hex);
    RET_STD(1, (uint32_t)hr);
}

const XrtHle xrt_hle_misc[] = {
    {"user32.dll", "FindWindowExA", hle_FindWindowExA},
    {"user32.dll", "RegisterWindowMessageW", hle_RegisterWindowMessageW},
    {"winmm.dll", "timeGetTime", hle_timeGetTime},
    {"winmm.dll", "timeBeginPeriod", hle_timeBeginPeriod},
    {"winmm.dll", "timeEndPeriod", hle_timeEndPeriod},
    {"advapi32.dll", "GetUserNameW", hle_GetUserNameW},
    {"ole32.dll", "CoCreateGuid", hle_CoCreateGuid},
    {0},
};
