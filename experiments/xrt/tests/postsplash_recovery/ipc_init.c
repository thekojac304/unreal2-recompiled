/* Exact production transport/helper and captured InitAudio tuple. */
#include <windows.h>
#include <objbase.h>
#include <stdio.h>
#include "../../runtime/dmusic_pipe.h"
int wmain(int argc,WCHAR**argv){
    DmbConnection c;DmbMessage m;ULONGLONG start;uint32_t perf;HANDLE child;
    if(argc!=3)return 2;
    if(FAILED(CoInitializeEx(NULL,COINIT_APARTMENTTHREADED)))return 3;
    if(!dmb_connect(&c,argv[1],argv[2],0,NULL,NULL)){printf("connect failed: %s\n",c.error);return 4;}
    dmb_message(&m,DMB_CREATE,0);m.v[0]=DMB_LOADER;
    if(!dmb_exchange(&c,&m)||m.v[0]||!m.v[1])return 5;
    dmb_message(&m,DMB_CREATE,0);m.v[0]=DMB_PERFORMANCE;
    if(!dmb_exchange(&c,&m)||m.v[0]||!m.v[1])return 6;perf=m.v[1];
    printf("Performance8 %08x object=1\n",m.v[0]);fflush(stdout);
    start=GetTickCount64();dmb_message(&m,DMB_INIT_AUDIO,perf);m.v[0]=8;m.v[1]=128;m.v[2]=63;
    puts("InitAudio enter path=8 channels=128 flags=63");fflush(stdout);
    child=c.process;DuplicateHandle(GetCurrentProcess(),child,GetCurrentProcess(),&child,0,FALSE,DUPLICATE_SAME_ACCESS);
    if(!dmb_exchange(&c,&m)){
        printf("transport failed: %s elapsed_ms=%llu\n",c.error,GetTickCount64()-start);fflush(stdout);
        if(WaitForSingleObject(child,2000)!=WAIT_OBJECT_0)return 7;CloseHandle(child);CoUninitialize();return 20;
    }
    printf("InitAudio return %08x object=%u elapsed_ms=%llu\n",m.v[0],m.v[1]!=0,GetTickCount64()-start);fflush(stdout);
    dmb_message(&m,DMB_CLOSE,perf);if(!dmb_exchange(&c,&m))return 8;
    dmb_message(&m,DMB_SHUTDOWN,0);if(!dmb_exchange(&c,&m))return 9;
    dmb_disconnect(&c);CloseHandle(child);CoUninitialize();puts("cleanup passed");return 0;
}
