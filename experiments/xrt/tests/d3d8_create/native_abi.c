/* One native creation per process; ownership calls only. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "../../runtime/d3d8_device_abi.h"
typedef struct Args {void*fn;D8Interface*parent;UINT adapter,type;HWND focus;DWORD flags;D8Present*pp;D8Device**out;} Args;
typedef __declspec(align(16)) struct ABI {DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];} ABI;
extern void device_abi(Args*,ABI*);
static void bytes(const BYTE*b,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",b[i]);putchar('"');}
int main(int argc,char**argv) {
    WNDCLASSW wc={0};HWND w;HMODULE dep,lib;char path[1024];D8Factory factory;D8Interface*p;D8Device*d=NULL;
    D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};Args a;ABI b;unsigned i;DWORD error;ULONG dn,pn;
    if(argc!=3)return 2;wc.lpfnWndProc=DefWindowProcW;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XrtNativeDeviceABI";
    if(!RegisterClassW(&wc))return 2;
    w=CreateWindowExW(0,wc.lpszClassName,L"Native ABI",WS_OVERLAPPEDWINDOW,0,0,1560,1000,NULL,NULL,wc.hInstance,NULL);if(!w)return 2;
    snprintf(path,sizeof path,"%s/d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path,sizeof path,"%s/d3d8.dll",argv[1]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!dep||!lib)return 2;factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");p=factory(120);if(!p)return 2;
    pp.window=w;pp.depthformat=(UINT)strtoul(argv[2],NULL,0);memset(&b,0,sizeof b);
    a.fn=(void*)p->vt->CreateDevice;a.parent=p;a.adapter=0;a.type=1;a.focus=w;a.flags=0x42;a.pp=&pp;a.out=&d;
    SetLastError(18);device_abi(&a,&b);error=GetLastError();
    printf("{\"hr\":%lu,\"last_error\":%lu,\"non_null\":%s,\"stack_delta\":%lu,\"regs\":[",b.hr,error,d?"true":"false",b.delta);
    for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)b.regs[i]);
    printf("],\"xmm\":");bytes(b.xmm,160);printf(",\"pre\":");bytes(b.pre,512);printf(",\"post\":");bytes(b.post,512);
    printf(",\"depth\":%u",pp.depthformat);
    if(FAILED((HRESULT)b.hr)) {printf(",\"modules_retained\":true,\"attempts\":1}\n");return 0;}
    dn=d->vt->Release(d);pn=p->vt->Release(p);FreeLibrary(lib);FreeLibrary(dep);
    printf(",\"device_release\":%lu,\"parent_release\":%lu,\"d3d8_loaded\":%s,\"d3d9_loaded\":%s}\n",dn,pn,GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false");
    DestroyWindow(w);UnregisterClassW(wc.lpszClassName,wc.hInstance);return 0;
}
