/* Host adapters for measured WINMM, ADVAPI32, OLE32, DirectInput and launcher USER32 calls (stdcall).
 * Window and callback marshalling lives in hle_gui.c. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <mmsystem.h>
#include "xrt_internal.h"
#include "hle_com.inc"
#include "hle_dinput.inc"
#include "hle_d3d8.inc"

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

/* WinDrv temporarily disables StickyKeys hotkeys during its client lifetime.
 * The only measured structure is two DWORDs; never persist it to the profile.
 * Restore the exact host state at normal/handled-fatal shutdown. */
static STICKYKEYS saved_sticky;
static int sticky_saved;
static void restore_sticky(void) {
    if(sticky_saved) {
        BOOL ok=SystemParametersInfoW(SPI_SETSTICKYKEYS,sizeof saved_sticky,&saved_sticky,0);
        xrt_event("sticky_restore","\"result\": %u, \"flags\": %u",ok,saved_sticky.dwFlags);
        sticky_saved=0;
    }
}
/* The timeout watchdog cannot safely release COM objects while the guest thread
 * may be inside one of their methods. Restore only the session setting there;
 * process teardown reclaims the COM objects. Normal/fatal cleanup owns Release. */
void xrt_cleanup_input_settings(void) { restore_sticky(); }
static void system_parameters(CPU*c,int wide) {
    STICKYKEYS keys;
    BOOL ok;
    uint32_t action=ARG(0),size=ARG(1),p=ARG(2),flags=ARG(3);
    if((action!=SPI_GETSTICKYKEYS && action!=SPI_SETSTICKYKEYS) || size!=8 || flags)
        xrt_fatal(c,XRT_EXIT_UNSUPPORTED,"SystemParametersInfo: unmeasured action %u size %u flags %u",action,size,flags);
    di_memory(c,p,8);
    keys.cbSize=rd32(p); keys.dwFlags=rd32(p+4);
    if(action==SPI_SETSTICKYKEYS && !sticky_saved) {
        saved_sticky.cbSize=sizeof saved_sticky;
        if(!SystemParametersInfoW(SPI_GETSTICKYKEYS,sizeof saved_sticky,&saved_sticky,0))
            xrt_fatal(c,XRT_EXIT_SETUP,"cannot preserve StickyKeys state");
        sticky_saved=1; xrt_cleanup_register(restore_sticky);
    }
    SetLastError(xrt_get_last_error(c));
    ok=wide?SystemParametersInfoW(action,size,&keys,flags):SystemParametersInfoA(action,size,&keys,flags);
    xrt_set_last_error(c,GetLastError());
    wr32(p,keys.cbSize); wr32(p+4,keys.dwFlags);
    xrt_event("system_parameters","\"action\": %u, \"flags\": %u, \"result\": %u",action,keys.dwFlags,ok);
    RET_STD(4,ok);
}
static void hle_SystemParametersInfoA(CPU*c) {system_parameters(c,0);}
static void hle_SystemParametersInfoW(CPU*c) {system_parameters(c,1);}

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
    XRT_DINPUT_BINDINGS
    XRT_D3D8_BINDINGS
    {"user32.dll","SystemParametersInfoA",hle_SystemParametersInfoA},
    {"user32.dll","SystemParametersInfoW",hle_SystemParametersInfoW},
    {"user32.dll", "FindWindowExA", hle_FindWindowExA},
    {"user32.dll", "RegisterWindowMessageW", hle_RegisterWindowMessageW},
    {"winmm.dll", "timeGetTime", hle_timeGetTime},
    {"winmm.dll", "timeBeginPeriod", hle_timeBeginPeriod},
    {"winmm.dll", "timeEndPeriod", hle_timeEndPeriod},
    {"advapi32.dll", "GetUserNameW", hle_GetUserNameW},
    {"ole32.dll", "CoCreateGuid", hle_CoCreateGuid},
    {0},
};
