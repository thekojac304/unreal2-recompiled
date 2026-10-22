/* hle_misc.c - host adapters for WINMM.dll and ADVAPI32.dll imports used on the measured paths (stdcall).
 * USER32, SHELL32, ole32 and vorbisfile imports are deliberately left unbound: calling one is fatal. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
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

const XrtHle xrt_hle_misc[] = {
    {"winmm.dll", "timeGetTime", hle_timeGetTime},
    {"winmm.dll", "timeBeginPeriod", hle_timeBeginPeriod},
    {"winmm.dll", "timeEndPeriod", hle_timeEndPeriod},
    {"advapi32.dll", "GetUserNameW", hle_GetUserNameW},
    {0},
};
