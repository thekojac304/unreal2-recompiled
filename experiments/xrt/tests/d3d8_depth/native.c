/* First measure invalid adapter access in a native-only SEH oracle. */
#define main retained_main
#include "../d3d8_modes/native.c"
#undef main
#include "../../runtime/d3d8_abi.h"
#include "corpus.h"
static DWORD caught_error,caught_code;
static int capture(EXCEPTION_POINTERS*p) {
    caught_error=GetLastError();caught_code=p->ExceptionRecord->ExceptionCode;
    return caught_code==EXCEPTION_ACCESS_VIOLATION?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH;
}
#if defined(_M_X64)
extern void depth_abi64(void*,D8Interface*,UINT,UINT,UINT,UINT,UINT,DWORD*);
#endif
int main(int argc,char**argv) {
    HMODULE dep,backend;D8Interface*d;D8Factory factory;char path[2048];
    UINT n,a,k,s,i,faults=0;static const DWORD seeds[]={0,18,0x13572468,0xffffffff};HRESULT hr;DWORD error;
#if defined(_M_X64)
    DWORD words64[58];
#endif
    if(argc<4||strcmp(argv[3],"--depth-safety-abi"))return retained_main(argc,argv);
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    snprintf(path,sizeof path,"%s\\d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path,sizeof path,"%s\\d3d8.dll",argv[1]);backend=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!dep||!backend)return 2;factory=(D8Factory)GetProcAddress(backend,"Direct3DCreate8");
    if(!factory||!(d=factory(120)))return 3;n=d->vt->GetAdapterCount(d);if(n>8)return 4;
    for(a=0;a<n+5;a++)for(k=0;k<DEPTH_CASES;k++)for(s=0;s<4;s++) {
        UINT adapter=depth_adapter(a,n);const UINT*p=depth_cases[k];
        caught_error=caught_code=0;hr=(HRESULT)0xdeadbeef;SetLastError(seeds[s]);
        __try {hr=d->vt->CheckDepthStencilMatch(d,adapter,p[0],p[1],p[2],p[3]);error=GetLastError();}
        __except(capture(GetExceptionInformation())) {error=caught_error;}
        if(caught_code)faults++;
        printf("safety %u %u %lu %lu %lu %lu\n",adapter,k,seeds[s],(DWORD)hr,error,caught_code);
    }
    if(faults)return 8; /* Never send a faulting tuple to the unguarded ABI wrapper. */
#if defined(_M_X64)
    for(a=0;a<n+5;a++)for(k=0;k<DEPTH_CASES;k++) {
        UINT adapter=depth_adapter(a,n);const UINT*p=depth_cases[k];
        memset(words64,0,sizeof words64);SetLastError(18);
        depth_abi64((void*)d->vt->CheckDepthStencilMatch,d,adapter,p[0],p[1],p[2],p[3],words64);error=GetLastError();
        printf("abi64 %u %u %lu log",adapter,k,error);
        for(i=0;i<58;i++)printf(" %lu",words64[i]);puts("");
    }
#endif
    i=d->vt->Release(d);printf("depth_cleanup %u\n",i);if(i)return 6;
    FreeLibrary(backend);FreeLibrary(dep);if(GetModuleHandleA("d3d8.dll")||GetModuleHandleA("d3d9.dll"))return 7;return 0;
}
