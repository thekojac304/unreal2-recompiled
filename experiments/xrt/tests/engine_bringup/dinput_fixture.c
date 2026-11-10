#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>
#include <stdio.h>
#include "xrt_internal.h"
static unsigned checks,calls,pins[2],cases,negatives,op,callback_release;
static DWORD guest_error,result_error;static HRESULT result_hr;static CPU*active;
static HWND windows_owned[2];static jmp_buf stop;static int expected_fatal;
uint8_t*xrt_g;__declspec(thread) XrtThread*xrt_cur;
#define CHECK(v) do{checks++;if(!(v)){fprintf(stderr,"line %d %s\n",__LINE__,#v);ExitProcess(91);}}while(0)
XRT_NORETURN void xrt_fatal(CPU*c,int code,const char*fmt,...){CHECK(expected_fatal&&code==76);longjmp(stop,1);}
void xrt_event(const char*k,const char*f,...){(void)k;(void)f;}
uint32_t xrt_get_last_error(CPU*c){return guest_error;}
void xrt_set_last_error(CPU*c,uint32_t e){guest_error=e;}
int xrt_is_committed(uint32_t p,uint32_t n){return p>=0x1000&&(uint64_t)p+n<=0x10000;}
CPU*xrt_gui_callback_enter(CPU*c){CPU*old=active;active=c;return old;}
void xrt_gui_callback_leave(CPU*c){active=c;}
void*xrt_gui_device_window(CPU*c,uint32_t p){if(p==0x3000||p==0x3001)return windows_owned[p-0x3000];xrt_fatal(c,76,"unknown owned window");}
void xrt_gui_window_pin(CPU*c,uint32_t p){xrt_gui_device_window(c,p);pins[p-0x3000]++;}
void xrt_gui_window_unpin(uint32_t p){CHECK(p==0x3000||p==0x3001);CHECK(pins[p-0x3000]);pins[p-0x3000]--;}
static const GUID com_iunknown={0};
static void com_memory(CPU*c,uint32_t p,uint32_t n,const char*m){if(!xrt_is_committed(p,n))xrt_fatal(c,76,"range");}
static uint32_t com_vtable(const char**n,unsigned s){return 0x4000;}
uint32_t xrt_rt_alloc(uint32_t n,uint32_t a){return 0x5000;}
void xrt_cleanup_register(void(*fn)(void)){(void)fn;}
#include "hle_dinput.inc"
static IDirectInputDevice8WVtbl vtable;
static IDirectInputDevice8W object={&vtable};
static IDirectInputDevice8W*forward_device;
static HRESULT inner_hr;static DWORD inner_error;
static HRESULT WINAPI fake_acquire(IDirectInputDevice8W*p){CHECK(p==&object&&active&&did_lifecycle_active);calls++;if(callback_release)did_Release(active);
    if(forward_device){inner_hr=op==7?forward_device->lpVtbl->Acquire(forward_device):forward_device->lpVtbl->Unacquire(forward_device);inner_error=GetLastError();return inner_hr;}
    SetLastError(result_error);return result_hr;}
static HRESULT WINAPI fake_coop(IDirectInputDevice8W*p,HWND w,DWORD f){CHECK(w==NULL||w==windows_owned[0]||w==windows_owned[1]);CHECK(f==rd32(active->r[ESP]+12));
    if(forward_device){calls++;inner_hr=forward_device->lpVtbl->SetCooperativeLevel(forward_device,w,f);inner_error=GetLastError();return inner_hr;}return fake_acquire(p);}
static ULONG WINAPI fake_release(IDirectInputDevice8W*p){if(forward_device){ULONG n=forward_device->lpVtbl->Release(forward_device);inner_error=GetLastError();forward_device=NULL;return n;}fake_acquire(p);return 0;}
static void call(CPU*c){if(op==7)did_Acquire(c);else if(op==8)did_Unacquire(c);else if(op==2)did_Release(c);else did_SetCooperativeLevel(c);}
static void setup(CPU*c,unsigned hwnd,unsigned flags){unsigned i;memset(c,0,sizeof *c);for(i=0;i<8;i++){c->r[i]=0x12345678+i;c->st[i]=i+.5;}c->r[ESP]=0x2000;c->fcw=0x27f;c->fsw=0x4020;c->top=5;
    wr32(0x2000,0x1234abcd);wr32(0x2004,di_devices[0].guest);wr32(0x2008,hwnd);wr32(0x200c,flags);guest_error=0x12345678;calls=0;active=NULL;callback_release=0;}
static void positive(CPU*c){CPU expected=*c;expected.rv=0x1234abcd;expected.r[ESP]+=op==13?16:8;expected.r[EAX]=op==2?0:(DWORD)result_hr;
    call(c);CHECK(!memcmp(c,&expected,sizeof *c));CHECK(guest_error==result_error&&!active&&!did_lifecycle_active&&calls==1);cases++;}
static void negative(CPU*c,unsigned allowed){CPU before=*c;expected_fatal=1;if(!setjmp(stop)){call(c);CHECK(0);}expected_fatal=0;
    CHECK(calls==allowed&&!memcmp(c,&before,sizeof *c));active=NULL;did_lifecycle_active=0;callback_release=0;negatives++;}
static int native_differential(void){
    typedef HRESULT(WINAPI*Factory)(HINSTANCE,DWORD,REFIID,void**,IUnknown*);
    HMODULE dll=LoadLibraryExW(L"dinput8.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);Factory factory;
    IDirectInput8W*parent_input=NULL;IDirectInputDevice8W*devices[2]={0};HRESULT hr;DWORD error;CPU c,expected;
    unsigned i,j,n;const unsigned ops[][3]={{8,0,0},{13,0x3000,6},{7,0,0},{7,0,0},{8,0,0},{8,0,0},
      {13,0x3001,10},{7,0,0},{8,0,0},{13,0x3000,0},{13,0x3000,3},{13,0x3000,6},{7,0,0},{8,0,0}};
    CHECK(dll);factory=(Factory)GetProcAddress(dll,"DirectInput8Create");CHECK(factory);
    CHECK(SUCCEEDED(factory(GetModuleHandleW(NULL),0x800,&di_iid8w,(void**)&parent_input,NULL))&&parent_input);
    for(i=0;i<2;i++){
        CHECK(SUCCEEDED(parent_input->lpVtbl->CreateDevice(parent_input,&GUID_SysMouse,&devices[i],NULL))&&devices[i]);
        CHECK(SUCCEEDED(devices[i]->lpVtbl->SetDataFormat(devices[i],&c_dfDIMouse2)));
    }
    vtable.Acquire=fake_acquire;vtable.Unacquire=fake_acquire;vtable.SetCooperativeLevel=fake_coop;vtable.Release=fake_release;
    forward_device=devices[1];di_devices[0].guest=0x5000;di_devices[0].refs=1;di_devices[0].input=&object;
    for(i=0;i<sizeof ops/sizeof ops[0];i++){
        HWND w=ops[i][1]?windows_owned[ops[i][1]-0x3000]:NULL;op=ops[i][0];
        SetLastError(0x12345678);
        hr=op==7?devices[0]->lpVtbl->Acquire(devices[0]):op==8?devices[0]->lpVtbl->Unacquire(devices[0]):devices[0]->lpVtbl->SetCooperativeLevel(devices[0],w,ops[i][2]);
        error=GetLastError();setup(&c,ops[i][1],ops[i][2]);expected=c;expected.r[EAX]=(unsigned)hr;expected.r[ESP]+=op==13?16:8;expected.rv=0x1234abcd;
        call(&c);expected.r[EAX]=(unsigned)inner_hr;CHECK(!memcmp(&c,&expected,sizeof c));CHECK(guest_error==inner_error&&!active&&!did_lifecycle_active);
        printf("{\"sample\":%u,\"slot\":%u,\"flags\":%u,\"native_hresult\":%u,\"native_last_error\":%lu,\"translated_hresult\":%u,\"translated_last_error\":%lu,\"actual_native_transfer_equal\":true,\"independent_invocations_equal\":%s}\n",i,op,ops[i][2],(unsigned)hr,error,(unsigned)inner_hr,inner_error,hr==inner_hr&&error==inner_error?"true":"false");
    }
    devices[0]->lpVtbl->Unacquire(devices[0]);devices[1]->lpVtbl->Unacquire(devices[1]);
    CHECK(devices[0]->lpVtbl->Release(devices[0])==0);op=2;setup(&c,0,0);did_Release(&c);CHECK(!di_devices[0].refs&&!di_devices[0].input&&!pins[0]&&!pins[1]);
    CHECK(parent_input->lpVtbl->Release(parent_input)==0);CHECK(FreeLibrary(dll));
    CHECK(DestroyWindow(windows_owned[0])&&DestroyWindow(windows_owned[1]));CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));
    printf("{\"passed\":true,\"native_lifecycle_samples\":14,\"remaining_refs\":0,\"remaining_window_pins\":0}\n");return 0;
}
int main(int argc,char**argv){
    CPU c;unsigned i,j;DWORD old;HRESULT results[]={S_OK,S_FALSE,E_FAIL};
    xrt_g=VirtualAlloc(NULL,0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);CHECK(xrt_g);
    windows_owned[0]=CreateWindowExW(0,L"STATIC",L"owned lifecycle",WS_OVERLAPPED,0,0,80,60,NULL,NULL,GetModuleHandleW(NULL),NULL);
    windows_owned[1]=CreateWindowExW(0,L"STATIC",L"owned replacement",WS_OVERLAPPED,0,0,80,60,NULL,NULL,GetModuleHandleW(NULL),NULL);CHECK(windows_owned[0]&&windows_owned[1]);
    if(argc==2&&!strcmp(argv[1],"--native"))return native_differential();
    vtable.Acquire=fake_acquire;vtable.Unacquire=fake_acquire;vtable.SetCooperativeLevel=fake_coop;vtable.Release=fake_release;
    di_devices[0].guest=0x5000;di_devices[0].refs=1;di_devices[0].input=&object;
    for(i=0;i<3;i++)for(j=0;j<3;j++){op=i==0?7:i==1?8:13;setup(&c,0x3000,6);result_hr=results[j];result_error=j?87:0xffffffff;positive(&c);}
    CHECK(pins[0]==1&&di_devices[0].window==0x3000);
    op=13;setup(&c,0x3001,10);result_hr=E_FAIL;positive(&c);CHECK(pins[0]==1&&!pins[1]&&di_devices[0].window==0x3000);
    setup(&c,0x3001,10);result_hr=S_OK;positive(&c);CHECK(!pins[0]&&pins[1]==1);
    for(i=0;i<32;i++){setup(&c,0x3001,i);result_hr=E_INVALIDARG;positive(&c);CHECK(!pins[0]&&pins[1]==1);}
    setup(&c,0,10);result_hr=S_OK;positive(&c);CHECK(!pins[1]&&!di_devices[0].window);
    setup(&c,0x3000,6);positive(&c);CHECK(pins[0]==1);
    setup(&c,0x4444,6);negative(&c,0);
    setup(&c,0x3000,32);negative(&c,0);
    setup(&c,0x3000,6);c.r[ESP]=0xfffffff0;negative(&c,0);
    setup(&c,0x3000,6);CHECK(VirtualProtect(G2H(0x2000),4096,PAGE_NOACCESS,&old));negative(&c,0);CHECK(VirtualProtect(G2H(0x2000),4096,old,&old));
    op=7;setup(&c,0,0);di_devices[0].refs=0;negative(&c,0);di_devices[0].refs=1;
    setup(&c,0,0);callback_release=1;negative(&c,1);
    op=2;setup(&c,0,0);positive(&c);CHECK(!pins[0]&&!pins[1]&&!di_devices[0].input&&!di_devices[0].window);
    CHECK(DestroyWindow(windows_owned[0])&&DestroyWindow(windows_owned[1]));CHECK(VirtualFree(xrt_g,0,MEM_RELEASE));
    printf("{\"passed\":true,\"cases\":%u,\"negatives\":%u,\"checks\":%u,\"protocol_double\":true}\n",cases,negatives,checks);return 0;
}
