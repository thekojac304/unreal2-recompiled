/* Project-owned PE32/PE32+ client of production typed CreateDevice/Clear/Present. */
#define WIN32_LEAN_AND_MEAN
#include "../../runtime/d3d8_device_abi.h"
#include <stdint.h>
extern IMAGE_DOS_HEADER __ImageBase;
__declspec(dllimport) D8Interface* WINAPI Direct3DCreate8(UINT);
int _fltused;
#pragma function(memcpy,memset)
void* __cdecl memcpy(void*d,const void*s,size_t n){size_t i;for(i=0;i<n;i++)((volatile BYTE*)d)[i]=((const volatile BYTE*)s)[i];return d;}
void* __cdecl memset(void*d,int v,size_t n){size_t i;for(i=0;i<n;i++)((volatile BYTE*)d)[i]=(BYTE)v;return d;}
__declspec(dllexport) DWORD probe_log[512],probe_log_n,probe_case,probe_arg,probe_seed=18;
__declspec(dllexport) DWORD abi_data[16],abi_clear[16],abi_present[16];
static D8Interface*parent;static D8Device*device;static HWND window;static int active;static DWORD callbacks;
typedef HRESULT(WINAPI*ClearFn)(D8Device*,DWORD,const RECT*,DWORD,DWORD,float,DWORD);
typedef HRESULT(WINAPI*PresentFn)(D8Device*,const RECT*,const RECT*,HWND,const RGNDATA*);
static ClearFn clearfn;static PresentFn presentfn;
static void logv(DWORD v){probe_log[probe_log_n++]=v;}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){
 if(active && m==WM_GETICON){volatile double a=1.25,b=3.5;callbacks++;logv(a*b==4.375);logv(device!=NULL);
  if(probe_case==70)device->vt->Release(device);
  if(probe_case==71)clearfn(device,0,NULL,1,0,0.0f,0);
  if(probe_case==72)DestroyWindow(window);
  if(w==0)SendMessageW(h,WM_GETICON,1,0);return 0;
 }return DefWindowProcW(h,m,w,l);
}
#if defined(_M_IX86)
HRESULT __cdecl bridge_abi(D8Device*,DWORD,DWORD,const RECT*,DWORD,DWORD,DWORD,DWORD,const RECT*,const RECT*,HWND,const RGNDATA*);
#endif
__declspec(dllexport) int probe_main(void){
 WNDCLASSEXW wc;D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0};D8Creation cp;HRESULT hr;DWORD i,color=0,count=0,flags=1,zbits=0,stencil=0;RECT r={8,8,64,64};const RECT*rects=NULL,*src=NULL,*dst=NULL;HWND override=NULL,focus;const RGNDATA*dirty=NULL;D8Device*thisdev;
 memset(&wc,0,sizeof wc);wc.cbSize=sizeof wc;wc.lpfnWndProc=proc;wc.hInstance=(HINSTANCE)&__ImageBase;wc.lpszClassName=L"XrtRenderProductionProbe";
 if(!RegisterClassExW(&wc))return 2;
 window=CreateWindowExW(WS_EX_TOPMOST,wc.lpszClassName,L"Isolated translated Clear / Present fixture",WS_POPUP,20,20,1540,945,NULL,NULL,wc.hInstance,NULL);if(!window)return 3;
 ShowWindow(window,SW_SHOWNOACTIVATE);UpdateWindow(window);pp.window=window;
 focus=window;
 if(probe_case>=50 && probe_case<=57){
  DWORD tuple=(probe_case-50)%4;
  if(tuple==0){focus=NULL;pp.window=NULL;}
  if(tuple==1)focus=NULL;
  if(tuple==2)pp.window=NULL;
  if(tuple==3)pp.window=CreateWindowExW(0,wc.lpszClassName,L"Separate unmeasured render window",WS_POPUP,0,0,1540,945,NULL,NULL,wc.hInstance,NULL);
 }
 parent=Direct3DCreate8(120);if(!parent)return 4;
 SetLastError(probe_seed);hr=parent->vt->CreateDevice(parent,0,1,focus,0x42,&pp,&device);logv(hr);logv(GetLastError());logv(device!=NULL);if(FAILED(hr)||!device)return 5;
 clearfn=(ClearFn)(*(void***)device)[36];presentfn=(PresentFn)(*(void***)device)[15];thisdev=device;
 if(probe_case>=54 && probe_case<=57)return presentfn(device,NULL,NULL,NULL,NULL);
 if(probe_case==1)color=0x00123456;if(probe_case==2)color=0xff654321;
 if(probe_case==3){count=1;rects=&r;color=0x224466;}
 if(probe_case==4){rects=&r;color=0x446688;}
 if(probe_case==20)flags=probe_arg;
 if(probe_case==21)count=probe_arg;
 if(probe_case==22){count=1;rects=(const RECT*)(uintptr_t)probe_arg;}
 if(probe_case==23)src=(const RECT*)(uintptr_t)probe_arg;
 if(probe_case==24)dst=(const RECT*)(uintptr_t)probe_arg;
 if(probe_case==25)override=window;
 if(probe_case==26)dirty=(const RGNDATA*)(uintptr_t)probe_arg;
 if(probe_case==27||probe_case==28){device->vt->Release(device);}
 if(probe_case==29)thisdev=(D8Device*)parent;
 if(probe_case==30){count=1;rects=(const RECT*)(uintptr_t)(0x25001000-12);color=0x224466;}
 if(probe_case==31)zbits=probe_arg;
 if(probe_case==32)stencil=probe_arg;
 if(probe_case==33){count=1;rects=&r;((DWORD*)&r)[probe_arg%4]=0xffffffff;}
 if(probe_case==34){count=0;rects=(const RECT*)(uintptr_t)probe_arg;}
 if(probe_case==40){typedef HRESULT(WINAPI*Any)(D8Device*);return ((Any)(*(void***)device)[probe_arg])(device);}
 for(i=0;i<(probe_case==5||probe_case==8?8u:probe_case==7?2u:1u);i++){
  if(probe_case==5||probe_case==8)color=i%2?0x9a4b21:0x123456;
  if(probe_case==7)color=i?0:0x123456;
  active=1;SetLastError(probe_seed);
  if(probe_case==28)presentfn(thisdev,NULL,NULL,NULL,NULL);
#if defined(_M_IX86)
  if(probe_case==6||probe_case==8||probe_case>=70)hr=bridge_abi(thisdev,0,count,rects,flags,color,zbits,stencil,src,dst,override,dirty);else
#endif
  {float z;memcpy(&z,&zbits,4);hr=clearfn(thisdev,count,rects,flags,color,z,stencil);}
  active=0;logv(hr);logv(GetLastError());memcpy(abi_clear,abi_data,sizeof abi_data);
  if(probe_case==8)logv(abi_data[8]);
  active=1;SetLastError(probe_seed);
#if defined(_M_IX86)
  if(probe_case==6||probe_case==8||probe_case>=70)hr=bridge_abi(thisdev,1,0,NULL,0,0,0,0,src,dst,override,dirty);else
#endif
  hr=presentfn(thisdev,src,dst,override,dirty);
  active=0;logv(hr);logv(GetLastError());memcpy(abi_present,abi_data,sizeof abi_data);
  if(probe_case==8)logv(abi_data[8]);
 }
 logv(callbacks);logv(device->vt->GetCreationParameters(device,&cp));logv(cp.adapter);logv(cp.type);logv(cp.focus==window);logv(cp.flags);
 logv(device->vt->AddRef(device));logv(device->vt->Release(device));logv(device->vt->Release(device));logv(parent->vt->Release(parent));logv(DestroyWindow(window));logv(UnregisterClassW(wc.lpszClassName,wc.hInstance));return 0;
}
