/* Disposable oracle: fixture-only native readback never enters production. */
#define WIN32_LEAN_AND_MEAN
#include "../../runtime/d3d8_device_abi.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <xmmintrin.h>
typedef HRESULT(WINAPI*SetFn)(D8Device*,DWORD,DWORD);
typedef HRESULT(WINAPI*GetFn)(D8Device*,DWORD,DWORD*);
typedef struct Args{void*fn;D8Device*device;DWORD state,value;}Args;
typedef __declspec(align(16))struct ABI{DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];}ABI;
extern void state_abi(Args*,ABI*);
static unsigned inside,callbacks,foreign;static DWORD tid;
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){DWORD e=GetLastError();if(inside)callbacks++;if(GetCurrentThreadId()!=tid)foreign++;SetLastError(e);return DefWindowProcW(h,m,w,l);}
static void bytes(const BYTE*p,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static void snapshot(D8Device*d,unsigned ordinal){unsigned i;DWORD v;HRESULT hr;GetFn get=(GetFn)(*(void***)d)[51];printf("{\"kind\":\"state\",\"ordinal\":%u,\"values\":[",ordinal);for(i=0;i<256;i++){v=0xa5a5a5a5;hr=get(d,i,&v);printf("%s[%lu,%lu]",i?",":"",(DWORD)hr,v);}puts("]}");}
int main(int argc,char**argv){
 HMODULE lib,dep;D8Interface*p;D8Device*d=NULL;D8Factory factory;WNDCLASSW wc;HWND w;char path[2048];D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};Args a;ABI b;HRESULT hr;DWORD seed,e,i,prime;ULONG dr,pr;SetFn set;
 if(argc!=6)return 2;tid=GetCurrentThreadId();setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 memset(&wc,0,sizeof wc);wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XrtStateNative";if(!RegisterClassW(&wc))return 3;
 w=CreateWindowExW(0,wc.lpszClassName,L"Isolated native SetRenderState fixture",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!w)return 4;pp.window=w;
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
 snprintf(path,sizeof path,"%s/d3d8.dll",argv[1]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!lib||!dep)return 5;
 factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");p=factory(120);if(!p)return 6;hr=p->vt->CreateDevice(p,0,1,w,0x42,&pp,&d);e=GetLastError();printf("{\"kind\":\"create\",\"hr\":%lu,\"last_error\":%lu,\"device\":%llu}\n",(DWORD)hr,e,(unsigned long long)(uintptr_t)d);if(FAILED(hr)||!d)return 7;
 a.device=d;a.fn=(*(void***)d)[50];a.state=strtoul(argv[2],NULL,0);a.value=strtoul(argv[3],NULL,0);seed=strtoul(argv[4],NULL,0);prime=strtoul(argv[5],NULL,0);set=(SetFn)a.fn;
 if(prime){hr=set(d,a.state,a.value^1);printf("{\"kind\":\"prime\",\"hr\":%lu,\"value\":%lu}\n",(DWORD)hr,a.value^1);}
 snapshot(d,0);
 for(i=0;i<4;i++){
  memset(&b,0,sizeof b);SetLastError(seed);inside=1;state_abi(&a,&b);e=GetLastError();inside=0;
  printf("{\"kind\":\"call\",\"ordinal\":%lu,\"hr\":%lu,\"last_error\":%lu,\"delta\":%lu,\"regs\":[",i,b.hr,e,b.delta);for(pr=0;pr<8;pr++)printf("%s%llu",pr?",":"",(unsigned long long)b.regs[pr]);printf("],\"xmm\":");bytes(b.xmm,160);printf(",\"pre\":");bytes(b.pre,512);printf(",\"post\":");bytes(b.post,512);puts("}");snapshot(d,i+1);
 }
 {D8Interface*q=NULL;D8Creation cp;ULONG add=d->vt->AddRef(d),balance=d->vt->Release(d);hr=d->vt->GetDirect3D(d,&q);printf("{\"kind\":\"identity\",\"parent_hr\":%lu,\"same_parent\":%s,\"add\":%lu,\"balance\":%lu,\"parent_release\":%lu,",(DWORD)hr,q==p?"true":"false",add,balance,q?q->vt->Release(q):999);hr=d->vt->GetCreationParameters(d,&cp);printf("\"creation_hr\":%lu,\"same_window\":%s,\"flags\":%lu}\n",(DWORD)hr,cp.focus==w?"true":"false",cp.flags);}
 dr=d->vt->Release(d);pr=p->vt->Release(p);DestroyWindow(w);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);
 printf("{\"kind\":\"cleanup\",\"device_release\":%lu,\"parent_release\":%lu,\"window_valid\":%s,\"d3d8_loaded\":%s,\"d3d9_loaded\":%s,\"callbacks\":%u,\"foreign_callbacks\":%u}\n",dr,pr,IsWindow(w)?"true":"false",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false",callbacks,foreign);return 0;
}
