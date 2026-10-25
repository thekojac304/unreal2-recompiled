/* Same scalar calls in a PE32 fixture and native PE32/PE32+ references. */
#define WIN32_LEAN_AND_MEAN
#include "../../runtime/d3d8_device_abi.h"
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllimport)D8Interface*WINAPI Direct3DCreate8(UINT);
int _fltused;
#pragma function(memcpy,memset)
void*__cdecl memcpy(void*d,const void*s,size_t n){size_t i;for(i=0;i<n;i++)((volatile BYTE*)d)[i]=((const volatile BYTE*)s)[i];return d;}
void*__cdecl memset(void*d,int v,size_t n){size_t i;for(i=0;i<n;i++)((volatile BYTE*)d)[i]=(BYTE)v;return d;}
__declspec(dllexport)DWORD probe_case,probe_arg,probe_seed=18,probe_log[512],probe_log_n,abi_data[16],abi_clear[16],abi_present[16];
static D8Device*d;static HWND window;static unsigned active,callbacks;
typedef HRESULT(WINAPI*SetFn)(D8Device*,DWORD,DWORD);
static void logv(DWORD v){probe_log[probe_log_n++]=v;}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){if(active&&m==WM_GETICON){volatile double a=1.25,b=3.5;callbacks++;logv(a*b==4.375);if(probe_case==70)d->vt->Release(d);if(probe_case==71)((SetFn)(*(void***)d)[50])(d,7,1);if(probe_case==72)DestroyWindow(window);if(!w)SendMessageW(h,m,1,0);return 0;}return DefWindowProcW(h,m,w,l);}
#ifdef _M_IX86
HRESULT __cdecl bridge_abi(D8Device*,DWORD,DWORD);
#endif
__declspec(dllexport)int probe_main(void){
 WNDCLASSEXW wc;D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};D8Interface*p,*original,*q=NULL;D8Creation cp;HRESULT hr;DWORD i,state=probe_case,value=probe_arg;SetFn set;D8Device*thisdev;
 memset(&wc,0,sizeof wc);wc.cbSize=sizeof wc;wc.lpfnWndProc=proc;wc.hInstance=(HINSTANCE)&__ImageBase;wc.lpszClassName=L"XrtStateProduction";if(!RegisterClassExW(&wc))return 2;
 window=CreateWindowExW(0,wc.lpszClassName,L"Isolated translated SetRenderState fixture",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!window)return 3;pp.window=window;
 p=Direct3DCreate8(120);if(!p)return 4;original=p;hr=p->vt->CreateDevice(p,0,1,window,0x42,&pp,&d);logv(hr);logv(d!=NULL);if(FAILED(hr)||!d)return 5;set=(SetFn)(*(void***)d)[50];thisdev=d;
 if(state>=70&&state<=72){state=7;value=1;}
 if(state==250){thisdev=(D8Device*)1;state=7;value=1;}
 if(state==251){d->vt->Release(d);state=7;value=1;}
 if(state==252){state=7;value=1;set=(SetFn)(*(void***)d)[51];}
 if(state==253){logv(p->vt->Release(p));p=NULL;state=7;value=1;}
 if(state==254){thisdev=(D8Device*)p;state=7;value=1;}
 if(state==256){thisdev=NULL;state=7;value=1;}
 for(i=0;i<4;i++){
  active=1;SetLastError(probe_seed);
#ifdef _M_IX86
  /* Negative identity calls use the slot saved from the valid device above.
   * Never load a vtable from an invalid, stale, wrong-type or NULL this. */
  if(probe_case==250||probe_case==251||probe_case==252||probe_case==254||probe_case==256)hr=set(thisdev,state,value);else hr=bridge_abi(thisdev,state,value);
  memcpy(abi_clear,abi_data,sizeof abi_data);
#else
  hr=set(thisdev,state,value);
#endif
  logv(hr);logv(GetLastError());active=0;
 }
 logv(callbacks);logv(d->vt->AddRef(d));logv(d->vt->Release(d));hr=d->vt->GetDirect3D(d,&q);logv(hr);logv(q==original);logv(q->vt->Release(q));hr=d->vt->GetCreationParameters(d,&cp);logv(hr);logv(cp.focus==window);logv(cp.flags);logv(d->vt->Release(d));if(p)logv(p->vt->Release(p));logv(DestroyWindow(window));logv(UnregisterClassW(wc.lpszClassName,wc.hInstance));return 0;
}
