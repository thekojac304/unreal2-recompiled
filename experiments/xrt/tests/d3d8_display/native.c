/* Native-only pointer probes catch access violations within a disposable process. */
#define main retained_main
#include "../d3d8_modes/native.c"
#undef main
#include "../../runtime/d3d8_abi.h"
static DWORD caught_error,caught_code,access_kind;static ULONG_PTR fault_address;
static int capture(EXCEPTION_POINTERS*p) {
    caught_error=GetLastError();caught_code=p->ExceptionRecord->ExceptionCode;
    access_kind=(DWORD)p->ExceptionRecord->ExceptionInformation[0];
    fault_address=p->ExceptionRecord->ExceptionInformation[1];
    return caught_code==EXCEPTION_ACCESS_VIOLATION?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH;
}
#if defined(_M_X64)
extern void display_abi64(void*,D8Interface*,UINT,D8Mode*,DWORD*);
#endif
int main(int argc,char**argv) {
    HMODULE dep,backend;D8Interface*d;D8Factory factory;char path[2048];
    UINT n,a,p,s,i;static const DWORD seeds[]={0,18,0x13572468,0xffffffff};
    BYTE*area;DWORD old;D8Mode*out;HRESULT hr;DWORD error;
#if defined(_M_X64)
    DWORD words64[58];
#endif
    if(argc<4||strcmp(argv[3],"--pointers-and-abi"))return retained_main(argc,argv);
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    snprintf(path,sizeof path,"%s\\d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path,sizeof path,"%s\\d3d8.dll",argv[1]);backend=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!dep||!backend)return 2;factory=(D8Factory)GetProcAddress(backend,"Direct3DCreate8");
    if(!factory||!(d=factory(120)))return 3;n=d->vt->GetAdapterCount(d);if(n>8)return 4;
    area=VirtualAlloc(NULL,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!area)return 5;
    for(a=0;a<n+3;a++)for(p=0;p<5;p++)for(s=0;s<4;s++) {
        UINT adapter=a<n+1?a:(a==n+1?0xffff:0xffffffff);
        VirtualProtect(area,8192,PAGE_READWRITE,&old);memset(area,0xa5,8192);
        out=p==0?NULL:(p==1?(D8Mode*)(ULONG_PTR)1:(D8Mode*)(area+(p==4?4088:0)));
        if(p==2)VirtualProtect(area,4096,PAGE_NOACCESS,&old);
        if(p==3)VirtualProtect(area,4096,PAGE_READONLY,&old);
        if(p==4)VirtualProtect(area+4096,4096,PAGE_NOACCESS,&old);
        caught_error=caught_code=access_kind=0;fault_address=0;hr=(HRESULT)0xdeadbeef;
        SetLastError(seeds[s]);
        __try {hr=d->vt->GetAdapterDisplayMode(d,adapter,out);error=GetLastError();}
        __except(capture(GetExceptionInformation())) {error=caught_error;}
        VirtualProtect(area,8192,PAGE_READWRITE,&old);
        printf("pointer adapter=%u case=%u seed=%lu hr=%08lx error=%lu exception=%08lx access=%lu fault_offset=%lld bytes=",adapter,p,seeds[s],(DWORD)hr,error,caught_code,access_kind,
            caught_code?(long long)(fault_address-(ULONG_PTR)out):0);
        for(i=0;i<32;i++)printf("%02x",area[(p==4?4080:0)+i]);puts("");
    }
#if defined(_M_X64)
    for(a=0;a<n+2;a++)for(s=0;s<4;s++) {
        UINT adapter=a<n+1?a:0xffffffff;
        memset(area,0xa5,16);memset(words64,0,sizeof words64);SetLastError(seeds[s]);
        display_abi64((void*)d->vt->GetAdapterDisplayMode,d,adapter,(D8Mode*)area,words64);error=GetLastError();
        printf("abi64 adapter=%u seed=%lu error=%lu log",adapter,seeds[s],error);
        for(i=0;i<58;i++)printf(" %lu",words64[i]);printf(" output");for(i=0;i<4;i++)printf(" %lu",((DWORD*)area)[i]);puts("");
    }
#endif
    VirtualFree(area,0,MEM_RELEASE);i=d->vt->Release(d);printf("pointer_cleanup %u\n",i);if(i)return 6;
    FreeLibrary(backend);FreeLibrary(dep);if(GetModuleHandleA("d3d8.dll")||GetModuleHandleA("d3d9.dll"))return 7;return 0;
}
