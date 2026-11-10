#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>
#include <stdio.h>
#include <intrin.h>
#include "xrt_internal.h"
#include "monitor_com.inc"
uint8_t*xrt_g;
static volatile LONG checks, callbacks;
static unsigned mode;
static CPU main_cpu;
static HANDLE start_event;
static D8DeviceVtable device_vt;
static D8Device device={&device_vt};
extern int xm_fpu_oracle(CPU*,const XmRequest*);
#define CHECK(x) do{InterlockedIncrement(&checks);if(!(x)){fprintf(stderr,"check line %d: %s\n",__LINE__,#x);ExitProcess(91);}}while(0)
static void setup(CPU*c,unsigned index){
    memset(c,0,sizeof *c);c->r[ESP]=0x2000+index*0x2000;c->fs_base=0x1000+index*0x100;
    c->r[EBP]=c->r[ESP]+32;c->pc=0x12340000+index;c->fcw=0x27f;c->fsw=0x4020;
    wr32(c->fs_base+0x34,0x13572468);wr32(c->r[ESP],0xabcdef00+index);
}
static HRESULT WINAPI level(D8Device*p){CHECK(p==&device);SetLastError(0x22446688);return S_FALSE;}
static HRESULT WINAPI viewport(D8Device*p,D8Viewport*out){CHECK(p==&device);out->x=77;out->height=88;SetLastError(0xaabbccdd);return E_FAIL;}
static LRESULT CALLBACK wndproc(HWND h,UINT m,WPARAM wp,LPARAM lp){
    LRESULT ret;
    if(m!=WM_APP+31 && m!=WM_APP+32)return DefWindowProcW(h,m,wp,lp);
    xm_scope(&main_cpu,XM_BEGIN,XM_CALLBACK,"owned.WndProc",m);InterlockedIncrement(&callbacks);
    if(m==WM_APP+31){xm_scope(&main_cpu,XM_BEGIN,XM_NATIVE,"USER32.SendMessageW",m);
        ret=SendMessageW(h,WM_APP+32,wp+1,lp);xm_scope(&main_cpu,XM_END,XM_NATIVE,"USER32.SendMessageW",ret);}
    else {ret=XM_TestCooperativeLevel(&main_cpu,&device);CHECK(ret==S_FALSE);}
    xm_scope(&main_cpu,XM_END,XM_CALLBACK,"owned.WndProc",ret);return ret;
}
static DWORD WINAPI worker(void*param){
    CPU c;unsigned i,index=(unsigned)(uintptr_t)param;setup(&c,index);WaitForSingleObject(start_event,INFINITE);
    for(i=0;i<8;i++){CPU before=c;DWORD error=0x99880000+index;
        SetLastError(error);xm_scope(&c,XM_BEGIN,XM_ADAPTER,"owned.worker",index);
        CHECK(GetLastError()==error&&!memcmp(&c,&before,sizeof c));
        CHECK(XM_TestCooperativeLevel(&c,&device)==S_FALSE&&GetLastError()==0x22446688);
        xm_scope(&c,XM_END,XM_ADAPTER,"owned.worker",i);
        CHECK(GetLastError()==0x22446688&&!memcmp(&c,&before,sizeof c));
    }return 0;
}
static void input(void){
    IDirectInput8W*p=NULL;IDirectInputDevice8W*d=NULL;HRESULT hr;unsigned i;
    HMODULE dll=LoadLibraryExW(L"dinput8.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);
    typedef HRESULT(WINAPI*Factory)(HINSTANCE,DWORD,REFIID,void**,IUnknown*);
    Factory factory=(Factory)GetProcAddress(dll,"DirectInput8Create");CHECK(factory);
    xm_native(&main_cpu,XM_BEGIN,"DINPUT8.DirectInput8Create",0,0);
    hr=factory(GetModuleHandleW(NULL),0x800,&IID_IDirectInput8W,(void**)&p,NULL);
    xm_native(&main_cpu,XM_END,"DINPUT8.DirectInput8Create",0,(unsigned)hr);CHECK(SUCCEEDED(hr)&&p);
    xm_resource(&main_cpu,3,0x4100,1,(uint64_t)p,1,0,"created");
    hr=XM_CreateDevice(&main_cpu,p,&GUID_SysMouse,&d,NULL);CHECK(SUCCEEDED(hr)&&d);
    xm_resource(&main_cpu,4,0x4200,1,(uint64_t)d,1,0,"created");
    CHECK(SUCCEEDED(XM_SetDataFormat(&main_cpu,d,&c_dfDIMouse2)));
    {DIPROPDWORD prop={{sizeof prop,sizeof prop.diph,0,DIPH_DEVICE},16};
     hr=XM_SetProperty(&main_cpu,d,DIPROP_BUFFERSIZE,&prop.diph);}
    hr=XM_SetCooperativeLevel(&main_cpu,d,NULL,DISCL_NONEXCLUSIVE|DISCL_BACKGROUND);
    for(i=0;i<2;i++){hr=XM_Acquire(&main_cpu,d);hr=XM_Unacquire(&main_cpu,d);}
    CHECK(XM_Release(&main_cpu,d)==0);xm_resource(&main_cpu,4,0x4200,1,0,0,0,"destroyed");
    CHECK(XM_Release(&main_cpu,p)==0);xm_resource(&main_cpu,3,0x4100,1,0,0,0,"destroyed");
    FreeLibrary(dll);
}
int main(int argc,char**argv){
    HANDLE threads[3];unsigned i;WNDCLASSW wc={0};HWND window;CPU before;
    __declspec(align(16)) unsigned char fx_before[512],fx_after[512];
    CHECK(argc==3);mode=(unsigned)atoi(argv[2]);
    xrt_g=VirtualAlloc(NULL,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);CHECK(xrt_g);setup(&main_cpu,0);
    if(mode>=7){FILE*f=fopen("ready.json","wb");CHECK(f);
        fprintf(f,"{\"pid\":%lu,\"probe\":%llu,\"failure\":%llu,\"pending\":%llu,\"committed\":%llu}",GetCurrentProcessId(),
            (uint64_t)(uintptr_t)xm_probe,(uint64_t)(uintptr_t)xm_failure,(uint64_t)(uintptr_t)&xm_pending,(uint64_t)(uintptr_t)&xm_committed);
        fclose(f);
        f=fopen("symbols.json","wb");CHECK(f);
        fprintf(f,"{\"xm_recorded\":%llu,\"xm_written\":%llu,\"xm_buffer_count\":%llu,\"xm_profile\":%llu,\"xm_failed\":%llu,\"xm_buffer\":%llu}",
          (uint64_t)(uintptr_t)&xm_recorded,(uint64_t)(uintptr_t)&xm_written,(uint64_t)(uintptr_t)&xm_buffer_count,
          (uint64_t)(uintptr_t)&xm_profile,(uint64_t)(uintptr_t)&xm_failed,(uint64_t)(uintptr_t)xm_buffer);
        fclose(f);DebugBreak();}
    xm_init(argv[1]);device_vt.TestCooperativeLevel=level;device_vt.GetViewport=viewport;
    xm_resource(&main_cpu,2,0x4000,1,(uint64_t)&device,1,0,"created");
    if(mode==9){xm_scope(&main_cpu,XM_DATA,0,"unflushed.accepted",77);DebugBreak();xm_close();return 0;}
    if(mode==10){extern void xm_qualification_hold_drain(void);xm_qualification_hold_drain();for(i=0;i<4098;i++)xm_scope(&main_cpu,XM_DATA,0,"exhaustion",i);ExitProcess(92);}
    if(mode==11){extern void xm_qualification_fail_flush(void);xm_qualification_fail_flush();xm_checkpoint(&main_cpu,"flush-failure");ExitProcess(92);}
    if(mode==12){extern void xm_qualification_partial_write(void);xm_qualification_partial_write();xm_checkpoint(&main_cpu,"partial-write");ExitProcess(92);}
    if(mode==13){for(i=0;i<131074;i++)xm_scope(&main_cpu,XM_DATA,0,"record-limit",i);ExitProcess(92);}
    if(mode==14){xm_span(&main_cpu,"resource.map.upload",(void*)1,1048576);xm_checkpoint(&main_cpu,"omission-checkpoint");DebugBreak();xm_close();return 0;}
    if(mode==1||mode==8){extern void xm_qualification_break_sink(void);xm_qualification_break_sink();xm_scope(&main_cpu,XM_BEGIN,XM_NATIVE,"must-fail-before-native",0);xm_checkpoint(&main_cpu,"broken-sink-checkpoint");ExitProcess(92);}
    if(mode==2){xm_scope(&main_cpu,XM_BEGIN,XM_NATIVE,"watchdog-owned",0);Sleep(INFINITE);}
    if(mode==3){xm_scope(&main_cpu,XM_BEGIN,XM_NATIVE,"wrong-end",0);xm_scope(&main_cpu,XM_END,XM_CALLBACK,"wrong-end",0);ExitProcess(92);}
    if(mode==4){xm_guest(&main_cpu,"unreadable",0xffffffff,16);ExitProcess(92);}
    if(mode==5){xm_scope(&main_cpu,XM_BEGIN,XM_NATIVE,"incomplete",0);return 0;}
    if(mode==6){xm_scope(&main_cpu,XM_FATAL,0,"owned unsupported method",76);ExitProcess(76);}
    {XmRequest q={0};q.event=XM_DATA;q.name="owned.nondefault-fpu";
     SetLastError(0x55667788);CHECK(xm_fpu_oracle(&main_cpu,&q));CHECK(GetLastError()==0x55667788);}
    before=main_cpu;SetLastError(0xdeadbeef);_fxsave64(fx_before);
    xm_scope(&main_cpu,XM_BEGIN,XM_ADAPTER,"owned.outer",0);
    _fxsave64(fx_after);CHECK(GetLastError()==0xdeadbeef&&!memcmp(&before,&main_cpu,sizeof before));
    /* FXSAVE reserved bytes and volatile XMM scratch are not FPU semantics.
     * Exact x87 registers plus CW/SW/TW/op/IP/DP and MXCSR must be preserved. */
    CHECK(!memcmp(fx_before,fx_after,160));
    {D8Viewport v;memset(&v,0xcc,sizeof v);CHECK(XM_GetViewport(&main_cpu,&device,&v)==E_FAIL);
     CHECK(v.x==77&&v.height==88&&v.y==0xcccccccc&&GetLastError()==0xaabbccdd);}
    wc.lpfnWndProc=wndproc;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"OwnedMonitorFixture";
    CHECK(RegisterClassW(&wc));window=CreateWindowW(wc.lpszClassName,L"",0,0,0,0,0,HWND_MESSAGE,NULL,wc.hInstance,NULL);CHECK(window);
    xm_scope(&main_cpu,XM_BEGIN,XM_NATIVE,"USER32.SendMessageW",0);
    CHECK(SendMessageW(window,WM_APP+31,1,0)==S_FALSE);
    xm_scope(&main_cpu,XM_END,XM_NATIVE,"USER32.SendMessageW",S_FALSE);CHECK(callbacks==2);
    DestroyWindow(window);UnregisterClassW(wc.lpszClassName,wc.hInstance);
    input();xm_scope(&main_cpu,XM_END,XM_ADAPTER,"owned.outer",0);
    start_event=CreateEventW(NULL,TRUE,FALSE,NULL);CHECK(start_event);
    for(i=0;i<3;i++){threads[i]=CreateThread(NULL,0,worker,(void*)(uintptr_t)(i+1),0,NULL);CHECK(threads[i]);}
    SetEvent(start_event);CHECK(WaitForMultipleObjects(3,threads,TRUE,15000)==WAIT_OBJECT_0);
    for(i=0;i<3;i++)CloseHandle(threads[i]);CloseHandle(start_event);
    xm_resource(&main_cpu,2,0x4000,1,0,0,0,"destroyed");xm_close();if(mode==7)DebugBreak();
    printf("{\"checks\":%ld,\"callbacks\":%ld,\"record_size\":%u,\"cpu_size\":%u,\"committed\":%llu}\n",checks,callbacks,(unsigned)sizeof(XmRecord),(unsigned)sizeof(CPU),xm_committed);
    return 0;
}
