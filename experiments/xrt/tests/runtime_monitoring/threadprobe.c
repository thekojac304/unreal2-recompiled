#define WIN32_LEAN_AND_MEAN
#include <windows.h>
__declspec(dllexport) DWORD probe_log_n=3,probe_log[3];
static volatile DWORD done[3];
static DWORD WINAPI worker(void*p){
    DWORD i=(DWORD)(UINT_PTR)p,j;
    for(j=0;j<3;j++){SetLastError(0x12340000+i);Sleep(1);if(GetLastError()!=0x12340000+i){probe_log[i]=0xff;done[i]=1;return 1;}}
    probe_log[i]=0x30+i;done[i]=1;return 0;
}
__declspec(dllexport) int thread_run(void){
    HANDLE threads[3];DWORD i,n,tid;
    for(i=0;i<3;i++){done[i]=0;threads[i]=CreateThread(NULL,0,worker,(void*)(UINT_PTR)i,0,&tid);if(!threads[i])return -1;}
    for(n=0;n<5000 && (!done[0]||!done[1]||!done[2]);n++)Sleep(1);
    for(i=0;i<3;i++)CloseHandle(threads[i]);
    return done[0]&&done[1]&&done[2]?3:-2;
}
