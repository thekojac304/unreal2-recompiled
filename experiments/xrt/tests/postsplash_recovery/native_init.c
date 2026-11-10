/* Bounded, project-owned native InitAudio characterization. No game entry. */
#define COBJMACROS
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include <stdlib.h>
#include "../../dmusic_helper/file_guard.h"
typedef HRESULT(WINAPI*InitAudio)(IUnknown*,IUnknown**,IUnknown**,HWND,DWORD,DWORD,DWORD,void*);
typedef HRESULT(WINAPI*CloseDown)(IUnknown*);
int wmain(int argc,WCHAR**argv){
    GUID g[4];FILE*f;IUnknown*perf=NULL,*sound=NULL;HRESULT hr;ULONGLONG start;int guarded;
    if(argc!=4)return 2;guarded=_wtoi(argv[3]);
    f=_wfopen(argv[1],L"rb");if(!f)return 2;if(fread(g,sizeof g,1,f)!=1){fclose(f);return 2;}fclose(f);
    if(guarded&&!guard_install(argv[2]))return 3;
    hr=CoInitializeEx(NULL,COINIT_APARTMENTTHREADED);if(FAILED(hr))return 4;
    hr=CoCreateInstance(&g[2],NULL,3,&g[3],(void**)&perf);
    printf("Performance8 %08lx object=%u\n",(DWORD)hr,perf!=NULL);fflush(stdout);
    if(FAILED(hr)||!perf)return 5;
    start=GetTickCount64();puts("InitAudio enter path=8 channels=128 flags=63");fflush(stdout);
    hr=((InitAudio)(*(void***)perf)[44])(perf,NULL,&sound,NULL,8,128,63,NULL);
    printf("InitAudio return %08lx object=%u elapsed_ms=%llu last_error=%lu\n",(DWORD)hr,sound!=NULL,GetTickCount64()-start,GetLastError());fflush(stdout);
    if(sound)IUnknown_Release(sound);
    ((CloseDown)(*(void***)perf)[38])(perf);IUnknown_Release(perf);CoUninitialize();puts("cleanup passed");return 0;
}
