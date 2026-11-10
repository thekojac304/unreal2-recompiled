/* One successful device per process; real pinned DXVK calls only. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <xmmintrin.h>
#include "native_support.h"
typedef struct Args {void*fn;D8Device*device;DWORD count;const RenderRect*rects;DWORD flags,color;float z;DWORD stencil;const RECT*src,*dst;HWND override;const RGNDATA*dirty;DWORD method;} Args;
typedef __declspec(align(16)) struct ABI {DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];} ABI;
extern void render_abi(Args*,ABI*);
static DWORD phase,callbacks[8],foreign,tid;
static LRESULT CALLBACK proc(HWND w,UINT m,WPARAM a,LPARAM b){DWORD e=GetLastError();if(phase<8)callbacks[phase]++;if(GetCurrentThreadId()!=tid)foreign++;SetLastError(e);return DefWindowProcW(w,m,a,b);}
static void bytes(const BYTE*p,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static void call(Args*a,const char*tag,DWORD seed){ABI b;DWORD error,i;memset(&b,0,sizeof b);phase=a->method?3:2;SetLastError(seed);render_abi(a,&b);error=GetLastError();phase=4;
 printf("{\"kind\":\"call\",\"tag\":\"%s\",\"method\":%lu,\"hr\":%lu,\"last_error\":%lu,\"seed\":%lu,\"stack_delta\":%lu,\"regs\":[",tag,a->method,b.hr,error,seed,b.delta);for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)b.regs[i]);printf("],\"xmm\":");bytes(b.xmm,160);printf(",\"pre\":");bytes(b.pre,512);printf(",\"post\":");bytes(b.post,512);puts("}");fflush(stdout);
}
int main(int argc,char**argv){
 HMODULE lib,dep;D8Factory factory;D8Interface*p;D8Device*d=NULL;D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};WNDCLASSW wc;HWND w;char path[2048],tag[80];HRESULT hr;DWORD e,seed=18,i;Args a;RenderRect rect={8,8,64,64};RECT src={0,0,1540,945};unsigned test;
 if(argc!=4)return 2;test=strtoul(argv[2],NULL,0);seed=strtoul(argv[3],NULL,0);setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);tid=GetCurrentThreadId();
 memset(&wc,0,sizeof wc);wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XrtClearPresentNative";if(!RegisterClassW(&wc))return 3;
 w=CreateWindowExW(WS_EX_TOPMOST,wc.lpszClassName,L"Isolated D3D8 Clear / Present fixture",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!w)return 4;pp.window=w;
 ShowWindow(w,SW_SHOWNOACTIVATE);UpdateWindow(w);
 snprintf(path,sizeof path,"%s/d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
 snprintf(path,sizeof path,"%s/d3d8.dll",argv[1]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!lib||!dep)return 5;
 factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");p=factory(120);if(!p)return 6;phase=1;SetLastError(seed);hr=p->vt->CreateDevice(p,0,1,w,0x42,&pp,&d);e=GetLastError();phase=4;
 printf("{\"kind\":\"create\",\"hr\":%lu,\"last_error\":%lu,\"non_null\":%s,\"pointer_bytes\":%zu,\"attempts\":1}\n",(DWORD)hr,e,d?"true":"false",sizeof(void*));if(FAILED(hr)||!d)ExitProcess(82);
 state(d,w,"before");snapshot(d,"initial",test==0);
 memset(&a,0,sizeof a);a.device=d;a.fn=rvtable(d)[36];a.flags=1;
 if(test==1)a.color=0x00123456;
 if(test==2)a.color=0xff654321;
 if(test==3){a.count=1;a.rects=&rect;a.color=0x00224466;}
 if(test==4){a.rects=&rect;a.color=0x00446688;}
 if(test==5)a.flags=0;
 if(test==6)a.flags=0x80000000;
 if(test==7)a.flags=8;
 if(test==8)a.flags=3;
 if(test==9){a.count=1;a.rects=NULL;}
 for(i=0;i<(test==12?8u:test==14?2u:1u);i++){
  if(test==12)a.color=i%2?0x009a4b21:0x00123456;
  if(test==14)a.color=i?0:0x00123456;
  snprintf(tag,sizeof tag,"clear-%u",i);call(&a,tag,seed);snapshot(d,tag,test==0||test==1);
  a.method=1;a.fn=rvtable(d)[15];
  if(test==10)a.override=(HWND)(uintptr_t)1;
  if(test==11){DestroyWindow(w);a.override=w;}
  if(test==13)a.src=&src;
  snprintf(tag,sizeof tag,"present-%u",i);call(&a,tag,seed);
  if(test!=11)capture_window(w,tag,test==0||test==1);
  snapshot(d,tag,0);a.method=0;a.fn=rvtable(d)[36];
 }
 state(d,w,"after");phase=5;{ULONG dr=rrelease(d),pr=p->vt->Release(p);printf("{\"kind\":\"release\",\"device\":%lu,\"parent\":%lu}\n",dr,pr);}
 if(IsWindow(w))DestroyWindow(w);UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(lib);FreeLibrary(dep);
 printf("{\"kind\":\"cleanup\",\"d3d8_loaded\":%s,\"d3d9_loaded\":%s,\"window_valid\":%s,\"foreign_callbacks\":%lu,\"callbacks\":[%lu,%lu,%lu,%lu,%lu,%lu]}\n",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false",IsWindow(w)?"true":"false",foreign,callbacks[0],callbacks[1],callbacks[2],callbacks[3],callbacks[4],callbacks[5]);return 0;
}
