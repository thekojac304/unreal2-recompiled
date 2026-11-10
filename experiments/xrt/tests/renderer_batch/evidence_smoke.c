/* Disposable non-graphical collector test. Never calls a graphics API. */
#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "evidence_fixture.h"
int main(int argc,char**argv){
    HMODULE m;HWND w;BOOL destroyed,unloaded;char path[2048];DWORD n;
    setvbuf(stdout,NULL,_IONBF,0);if(argc!=2)return 2;
    if(!strcmp(argv[1],"--early-exit"))return 17;
    if(!strcmp(argv[1],"--linger")){Sleep(60000);return 0;}
    if(!strcmp(argv[1],"--spawn-descendant")){
        wchar_t exe[2048],cmd[2200];STARTUPINFOW si={sizeof si};PROCESS_INFORMATION pi={0};
        GetModuleFileNameW(0,exe,2048);swprintf_s(cmd,2200,L"\"%s\" --linger",exe);
        if(!CreateProcessW(0,cmd,0,0,FALSE,CREATE_NO_WINDOW,0,0,&si,&pi))return 8;
        CloseHandle(pi.hThread);CloseHandle(pi.hProcess);
    }
    n=GetEnvironmentVariableA("XRT_SMOKE_DLL",path,sizeof path);if(!n||n>=sizeof path)return 3;
    m=LoadLibraryA(path);if(!m)return 4;
    w=CreateWindowExW(0,L"STATIC",L"Evidence fixture",0,0,0,0,0,HWND_MESSAGE,0,GetModuleHandleW(0),0);if(!w)return 5;
    ev_checkpoint("loaded");ev_event("smoke-observation","\"graphics\":false");
    destroyed=DestroyWindow(w);unloaded=FreeLibrary(m);
    printf("{\"kind\":\"smoke-cleanup\",\"destroyed\":%s,\"window_valid\":%s,\"unloaded\":%s,\"module_loaded\":%s}\n",destroyed?"true":"false",IsWindow(w)?"true":"false",unloaded?"true":"false",GetModuleHandleA(path)?"true":"false");
    ev_checkpoint("cleaned");return destroyed&&unloaded?0:6;
}
