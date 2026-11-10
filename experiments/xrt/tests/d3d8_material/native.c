/* Native-only readback oracle. No game and no production GetMaterial bridge. */
#define WIN32_LEAN_AND_MEAN
#include "../../runtime/d3d8_device_abi.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
typedef struct Material { DWORD words[17]; } Material;
typedef HRESULT(WINAPI*SetFn)(D8Device*,const Material*);
typedef HRESULT(WINAPI*GetFn)(D8Device*,Material*);
typedef struct Args{void*fn;D8Device*device;const Material*material;}Args;
typedef __declspec(align(16))struct ABI{DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];}ABI;
extern void material_abi(Args*,ABI*);
static unsigned inside,callbacks,foreign;static DWORD tid;
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){DWORD e=GetLastError();if(inside)callbacks++;if(GetCurrentThreadId()!=tid)foreign++;SetLastError(e);return DefWindowProcW(h,m,w,l);}
static void bytes(const BYTE*p,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static void snapshot(D8Device*d,unsigned ordinal){Material m;unsigned i;HRESULT hr=((GetFn)(*(void***)d)[43])(d,&m);printf("{\"kind\":\"material\",\"ordinal\":%u,\"hr\":%lu,\"words\":[",ordinal,(DWORD)hr);for(i=0;i<17;i++)printf("%s%lu",i?",":"",m.words[i]);puts("]}");}
int main(int argc,char**argv){
 HMODULE lib,dep;D8Interface*p;D8Device*d=NULL;D8Factory factory;WNDCLASSW wc;HWND w;char path[2048];D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};Args a;ABI b;HRESULT hr;DWORD seed,e,i,j,which;ULONG dr,pr;
 Material m={{0x3f000000,0x3f000000,0x3f000000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0x3f800000,0,0,0,0,0,0,0,0,0}},before;
 if(argc!=4)return 2;tid=GetCurrentThreadId();setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 memset(&wc,0,sizeof wc);wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XrtMaterialNative";if(!RegisterClassW(&wc))return 3;
 w=CreateWindowExW(0,wc.lpszClassName,L"Disposable material oracle",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!w)return 4;pp.window=w;
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
 snprintf(path,sizeof path,"%s/d3d8.dll",argv[1]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!lib||!dep)return 5;
 factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");p=factory(120);if(!p)return 6;hr=p->vt->CreateDevice(p,0,1,w,0x42,&pp,&d);if(FAILED(hr)||!d)return 7;
 which=strtoul(argv[2],NULL,0);seed=strtoul(argv[3],NULL,0);if(which==1)memset(&m,0,sizeof m);before=m;
 a.device=d;a.fn=(*(void***)d)[42];a.material=which==2?NULL:&m;
 snapshot(d,0);
 for(i=0;i<4;i++){
  memset(&b,0,sizeof b);SetLastError(seed);inside=1;material_abi(&a,&b);e=GetLastError();inside=0;
  printf("{\"kind\":\"call\",\"ordinal\":%lu,\"hr\":%lu,\"last_error\":%lu,\"input_unchanged\":%s,\"delta\":%lu,\"regs\":[",i,b.hr,e,!memcmp(&m,&before,sizeof m)?"true":"false",b.delta);for(j=0;j<8;j++)printf("%s%llu",j?",":"",(unsigned long long)b.regs[j]);printf("],\"xmm\":");bytes(b.xmm,160);printf(",\"pre\":");bytes(b.pre,512);printf(",\"post\":");bytes(b.post,512);puts("}");snapshot(d,i+1);
 }
 {D8Interface*q=NULL;D8Creation cp;ULONG add=d->vt->AddRef(d),balance=d->vt->Release(d);hr=d->vt->GetDirect3D(d,&q);printf("{\"kind\":\"identity\",\"parent_hr\":%lu,\"same_parent\":%s,\"add\":%lu,\"balance\":%lu,\"parent_release\":%lu,",(DWORD)hr,q==p?"true":"false",add,balance,q?q->vt->Release(q):999);hr=d->vt->GetCreationParameters(d,&cp);printf("\"creation_hr\":%lu,\"same_window\":%s,\"flags\":%lu}\n",(DWORD)hr,cp.focus==w?"true":"false",cp.flags);}
 dr=d->vt->Release(d);pr=p->vt->Release(p);DestroyWindow(w);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);
 printf("{\"kind\":\"cleanup\",\"device_release\":%lu,\"parent_release\":%lu,\"window_valid\":%s,\"d3d8_loaded\":%s,\"d3d9_loaded\":%s,\"callbacks\":%u,\"foreign_callbacks\":%u}\n",dr,pr,IsWindow(w)?"true":"false",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false",callbacks,foreign);return 0;
}
