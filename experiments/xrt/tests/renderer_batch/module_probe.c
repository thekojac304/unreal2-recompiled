/* Non-graphical Windows path-identity probe. No D3D device or game code. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#include <stdio.h>
#include "evidence_fixture.h"
int main(void){
    wchar_t path[32768],mapped[32768];HMODULE image;DWORD n;BOOL released;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    n=GetWindowsDirectoryW(path,32000);if(!n||n>=32000)return 2;
    wcscat_s(path,32768,L"\\System32\\version.dll");
    image=LoadLibraryExW(path,NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);if(!image)return 3;
    n=GetMappedFileNameW(GetCurrentProcess(),image,mapped,32768);if(!n||n>=32767)return 4;
    ev_checkpoint("loaded");
    released=FreeLibrary(image);
    ev_checkpoint("cleaned");
    printf("{\"kind\":\"module-path-probe\",\"base\":%llu,\"released\":%s,\"requested_system32\":true,\"graphics\":false}\n",
           (unsigned long long)(uintptr_t)image,released?"true":"false");
    return released?0:5;
}
