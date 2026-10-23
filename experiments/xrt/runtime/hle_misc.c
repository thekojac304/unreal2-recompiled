/* hle_misc.c - host adapters for WINMM.dll, ADVAPI32.dll and ole32.dll imports used on the measured paths (stdcall).
 * USER32, SHELL32, vorbisfile and the other ole32 imports are deliberately left unbound: calling one is fatal. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <mmsystem.h>
#include "xrt_internal.h"

static void hle_timeGetTime(CPU* c) { RET_STD(0, timeGetTime()); }
static void hle_timeBeginPeriod(CPU* c) { RET_STD(1, timeBeginPeriod(ARG(0))); }
static void hle_timeEndPeriod(CPU* c) { RET_STD(1, timeEndPeriod(ARG(0))); }

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
    {"winmm.dll", "timeGetTime", hle_timeGetTime},
    {"winmm.dll", "timeBeginPeriod", hle_timeBeginPeriod},
    {"winmm.dll", "timeEndPeriod", hle_timeEndPeriod},
    {"advapi32.dll", "GetUserNameW", hle_GetUserNameW},
    {"ole32.dll", "CoCreateGuid", hle_CoCreateGuid},
    {0},
};
