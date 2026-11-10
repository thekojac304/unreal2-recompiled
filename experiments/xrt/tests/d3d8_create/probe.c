/* Project-owned PE32/PE32+ fixture; calls the production D8.CreateDevice slot. */
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
__declspec(dllexport) DWORD abi_data[16];
static D8Interface* parent;
static D8Device* device;
static D8Present params;
static HWND focus,window;
static unsigned callbacks;
static int in_create;
static const GUID unknown={0,0,0,{0xc0,0,0,0,0,0,0,0x46}};
static const GUID iidDevice={0x7385e5df,0x8fe8,0x41d5,{0x86,0xb6,0xd7,0xb4,0x85,0x47,0xb6,0xcf}};
static const GUID iidParent={0x1dd9e8da,0x1c77,0x4d40,{0xb0,0xcf,0x98,0xfe,0xfd,0xff,0x95,0x12}};
static const GUID missing={0xdeadbeef,0x1234,0x5678,{1,2,3,4,5,6,7,8}};
static void logv(DWORD v){probe_log[probe_log_n++]=v;}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l) {
    if(in_create && m==WM_GETICON) {
        volatile double a=1.25,b=3.5,result=a*b; /* nested CPU must be discarded */
        callbacks++;logv(device==NULL);logv(result==4.375);
        if(w==0)SendMessageW(h,WM_GETICON,1,0);
        if(probe_case==12 && w==0) {
            D8Device*other=NULL;
            parent->vt->CreateDevice(parent,0,1,focus,0x42,&params,&other);
        }
        if(probe_case==13 && w==0 && callbacks==2)logv(parent->vt->Release(parent));
        return 0;
    }
    return DefWindowProcW(h,m,w,l);
}
#if defined(_M_IX86)
HRESULT __cdecl bridge_abi(D8Interface*,HWND,D8Present*,D8Device**);
#endif
static void setup(void) {
    WNDCLASSEXW wc;memset(&wc,0,sizeof wc);wc.cbSize=sizeof wc;wc.lpfnWndProc=proc;
    wc.hInstance=(HINSTANCE)&__ImageBase;wc.lpszClassName=L"XrtProductionDevice";
    RegisterClassExW(&wc);
    focus=CreateWindowExW(0,wc.lpszClassName,L"D3D8 ownership fixture",WS_OVERLAPPEDWINDOW,0,0,1560,1000,NULL,NULL,wc.hInstance,NULL);
    window=focus;
    if(probe_case==2)window=CreateWindowExW(0,wc.lpszClassName,L"Separate presentation",WS_OVERLAPPEDWINDOW,0,0,800,600,NULL,NULL,wc.hInstance,NULL);
    parent=Direct3DCreate8(120);
    params.width=1540;params.height=945;params.format=22;params.count=1;params.multisample=0;params.swap=1;
    params.window=window;params.windowed=1;params.depth=1;params.depthformat=77;params.flags=1;params.refresh=0;params.interval=0;
}
__declspec(dllexport) int probe_main(void) {
    HRESULT hr;D8Device*q;D8Interface*p;D8Creation cp;DWORD i;
    D8Present*pp=&params;D8Device**out=&device;HWND f;UINT adapter=0,type=1;DWORD flags=0x42;
    setup();if(!parent || !focus)return 2;
    device=(D8Device*)(uintptr_t)0xa5a5a5a5;f=focus;
    if(probe_case==3)f=NULL;
    if(probe_case==4)params.window=NULL;
    if(probe_case==5){f=NULL;params.window=NULL;}
    if(probe_case==20){
        if(probe_arg<13 && probe_arg!=6)((DWORD*)&params)[probe_arg]^=1;
        if(probe_arg==13)adapter=1;if(probe_arg==14)type=2;if(probe_arg==15)flags=0x40;
    }
    if(probe_case==21)f=(HWND)GetStockObject(DEFAULT_GUI_FONT);
    if(probe_case==22)params.window=(HWND)GetStockObject(DEFAULT_GUI_FONT);
    if(probe_case==23){DestroyWindow(focus);f=focus;}
    if(probe_case==24)f=(HWND)(uintptr_t)1;
    if(probe_case==25)pp=(D8Present*)(uintptr_t)probe_arg;
    if(probe_case==26)out=(D8Device**)(uintptr_t)probe_arg;
    if(probe_case==27 || probe_case==28 || probe_case==29 || probe_case==30) {
        BYTE*b=(BYTE*)(uintptr_t)0x25000000;
        /* The translated host commits/protects these test-only pages before
         * entry. Only the HWND scalar is filled after window registration. */
        if(probe_case==27 || probe_case==28) {pp=(D8Present*)(b+4096-48);pp->window=window;}
        else out=(D8Device**)(b+4096-2);
    }
    if(probe_case==31)out=(D8Device**)((BYTE*)pp+48);
    in_create=1;SetLastError(probe_seed);
#if defined(_M_IX86)
    if(probe_case==6 || probe_case==13)hr=bridge_abi(parent,f,pp,out);else
#endif
    hr=parent->vt->CreateDevice(parent,adapter,type,f,flags,pp,out);
    in_create=0;logv(hr);logv(GetLastError());logv(device!=NULL);logv(callbacks);
    logv(params.width);logv(params.height);logv(params.format);logv(params.count);logv(params.multisample);logv(params.swap);
    logv(params.window==window);logv(params.window==NULL);logv(params.windowed);logv(params.depth);logv(params.depthformat);logv(params.flags);logv(params.refresh);logv(params.interval);
    if(FAILED(hr) || !device)return 3;
    if(probe_case==35){parent->vt->Release(parent);return parent->vt->AddRef(parent);}
    if(probe_case==32)return device->vt->QueryInterface(device,&iidDevice,(void**)(uintptr_t)probe_arg);
    if(probe_case==33)return device->vt->GetCreationParameters(device,(D8Creation*)(uintptr_t)probe_arg);
    if(probe_case==34)return device->vt->GetDirect3D(device,(D8Interface**)(uintptr_t)probe_arg);
    if(probe_case==9){logv(device->vt->AddRef(device));logv(parent->vt->AddRef(parent));return 0;}
    if(probe_case==10)return DestroyWindow(window);
    if(probe_case==11)return parent->vt->CreateDevice(parent,0,1,f,0x42,&params,&q);
    if(probe_case==1 || probe_case==8)logv(parent->vt->Release(parent));
    logv(device->vt->AddRef(device));logv(device->vt->Release(device));
    for(i=0;i<4;i++) {
        const GUID*id=i==0?&unknown:i==1?&iidDevice:i==2?&iidParent:&missing;
        q=(D8Device*)(uintptr_t)0xa5a5a5a5;
        SetLastError(18);hr=device->vt->QueryInterface(device,id,(void**)&q);logv(hr);logv(GetLastError());
        logv(SUCCEEDED(hr)?q==device:q==NULL);if(SUCCEEDED(hr))logv(q->vt->Release(q));
    }
    logv(device->vt->QueryInterface(device,&iidDevice,NULL));
    memset(&cp,0xa5,sizeof cp);logv(device->vt->GetCreationParameters(device,&cp));
    logv(cp.adapter);logv(cp.type);logv(cp.focus==f);logv(cp.flags);
    logv(device->vt->GetDirect3D(device,&p));logv(p==parent);logv(p->vt->Release(p));
    logv(device->vt->Release(device));
    if(probe_case==7)return device->vt->AddRef(device);
    if(probe_case==8)return parent->vt->AddRef(parent); /* parent first, device gone */
    if(probe_case!=1 && probe_case!=8 && probe_case!=13)logv(parent->vt->Release(parent));
    if(probe_case==2)logv(DestroyWindow(window));
    logv(DestroyWindow(focus));logv(UnregisterClassW(L"XrtProductionDevice",(HINSTANCE)&__ImageBase));
    return 0;
}
