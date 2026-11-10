/* Non-game host. Links the candidate's existing runtime objects, never its
 * main or generated guest objects. There is no original image/module load. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <d3d9.h>
#include "xrt_internal.h"
#include "d3d8_abi.h"
#include "d3d8_device_abi.h"
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a,xrt_cmdline_w;
const char* xrt_report_path;
const XrtLiftedModule* xrt_lifted_find(const char*n){(void)n;return NULL;}
int xrt_lifted_overlap(uint32_t a,uint32_t n,uint32_t*e){(void)a;(void)n;(void)e;return 0;}
void xrt_dll_thread_notify(CPU*c,uint32_t reason){(void)c;(void)reason;}
XrtModule* xrt_load_library(CPU*c,const char*p){(void)p;xrt_fatal(c,76,"owned host refuses guest module load");}
int xrt_free_library(CPU*c,XrtModule*m){(void)m;xrt_fatal(c,76,"owned host refuses guest module unload");}
void xrt_report_write(uint32_t n,const char*s){(void)n;(void)s;}
XRT_NORETURN void xrt_process_exit(CPU*c,uint32_t n){xrt_fatal(c,76,"unexpected owned process exit %u",n);}
extern void owned_invoke(void*,unsigned);
__declspec(noinline) void owned_gate(CPU*c){static volatile unsigned count;count++;(void)c;}
static void backend_identity(void){
 typedef HRESULT(WINAPI*Create)(UINT,IDirect3D9Ex**);HMODULE dep=GetModuleHandleW(L"d3d9.dll");
 Create fn=dep?(Create)GetProcAddress(dep,"Direct3DCreate9Ex"):NULL;IDirect3D9Ex*p=NULL;LUID luid={0};D3DADAPTER_IDENTIFIER9 id={0};
 HRESULT hr=fn?fn(32,&p):E_NOINTERFACE;
 if(FAILED(hr)||!p)ExitProcess(93);
 hr=p->lpVtbl->GetAdapterLUID(p,0,&luid);if(FAILED(hr))ExitProcess(93);
 hr=p->lpVtbl->GetAdapterIdentifier(p,0,0,&id);if(FAILED(hr))ExitProcess(93);
 printf("{\"kind\":\"backend-adapter\",\"ordinal\":0,\"luid_low\":%lu,\"luid_high\":%ld,\"vendor\":%lu,\"device\":%lu}\n",luid.LowPart,luid.HighPart,id.VendorId,id.DeviceId);
 p->lpVtbl->Release(p);fflush(stdout);
}
static uint32_t invoke(CPU*c,const char*dll,const char*name,unsigned n,const uint32_t*a){
 const char*stub=NULL;XrtFn fn=xrt_lookup(xrt_hle_proc(dll,name),&stub);unsigned i;uint32_t sp=c->r[ESP];
 if(!fn)xrt_fatal(c,76,"missing owned adapter %s",name);
 for(i=n;i>0;i--)push32(c,a[i-1]);push32(c,0x12345678);
 xm_scope(c,XM_BEGIN,XM_ADAPTER,name,0);fn(c);xm_scope(c,XM_END,XM_ADAPTER,name,c->r[EAX]);
 if(c->rv!=0x12345678||c->r[ESP]!=sp)xrt_fatal(c,76,"owned call return mismatch");return c->r[EAX];
}
static DWORD WINAPI worker(void*p){(void)p;Sleep(5);return 0;}
static void context_identity(void){
 char station[256]={0},desktop[256]={0};DWORD n=0,session=0;
 if(!GetUserObjectInformationA(GetProcessWindowStation(),UOI_NAME,station,sizeof station,&n)||
    !GetUserObjectInformationA(GetThreadDesktop(GetCurrentThreadId()),UOI_NAME,desktop,sizeof desktop,&n)||
    !ProcessIdToSessionId(GetCurrentProcessId(),&session))ExitProcess(93);
 printf("{\"kind\":\"owned-context\",\"pid\":%lu,\"session\":%lu,\"station\":\"%s\",\"desktop\":\"%s\"}\n",GetCurrentProcessId(),session,station,desktop);fflush(stdout);
}
int main(int argc,char**argv){
 static XrtThread owned;XrtThread*t=&owned;CPU*c;uint32_t a[12]={0},window,parent,device,pp,out,cp;HANDLE w;
 if(argc!=2||(strcmp(argv[1],"--owned-graphics")&&strcmp(argv[1],"--owned-protocol")&&strcmp(argv[1],"--owned-predevice")))return 2;
 if(!GetCurrentDirectoryA(sizeof xrt_sandbox_root,xrt_sandbox_root))return 3;
 xm_init(getenv("XRT_MONITOR_STREAM"));xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
 /* The owned host has no mapped executable in the guest loader. Construct its
  * fixture CPU/TEB directly instead of calling the game-process thread setup. */
 t->host_tid=t->guest_tid=GetCurrentThreadId();t->state=1;c=&t->cpu;
 c->thread=t;c->fcw=0x027f;c->fs_base=xrt_rt_alloc(4096,4096);
 c->r[ESP]=xrt_rt_alloc(65536,16)+65536-256;xrt_cur=t;xrt_baton_acquire();
 xrt_event("owned_host_start","\"game_modules\":0");
 context_identity();
 xm_scope(c,XM_BEGIN,XM_ADAPTER,"UGameEngine.Init",0x1098f460);
 if(!strcmp(argv[1],"--owned-protocol")){owned_gate(c);goto finish;}
 /* A real USER32 builtin window is registered by the unchanged GUI adapter. */
 a[1]=xrt_guest_strdup_a("STATIC");a[2]=xrt_guest_strdup_a("Owned Init graphics prerequisite");
 a[3]=WS_POPUP;a[4]=20;a[5]=20;a[6]=800;a[7]=600;
 window=invoke(c,"user32.dll","CreateWindowExA",12,a);if(!window)xrt_fatal(c,76,"owned window failed");
 parent=0;
 if(strcmp(argv[1],"--owned-predevice")){a[0]=120;parent=invoke(c,"d3d8.dll","Direct3DCreate8",1,a);if(!parent)xrt_fatal(c,76,"owned factory failed");}
 pp=xrt_rt_alloc(52,4);out=xrt_rt_alloc(4,4);cp=xrt_rt_alloc(16,4);
 {uint32_t words[13]={800,600,22,1,0,1,0,1,1,75,0,0,0};words[6]=window;memcpy(G2H(pp),words,52);}
 a[0]=parent;a[1]=0;a[2]=1;a[3]=window;a[4]=0x22;a[5]=pp;a[6]=out;
 if(invoke(c,"xrt.com","D8.CreateDevice",7,a)!=0 || !(device=rd32(out)))xrt_fatal(c,76,"owned CreateDevice failed");
 a[0]=device;a[1]=cp;
 if(invoke(c,"xrt.com","D8Device.GetCreationParameters",2,a)!=0)xrt_fatal(c,76,"owned creation readback failed");
 printf("{\"kind\":\"owned-creation-readback\",\"adapter\":%u,\"type\":%u,\"focus\":%u,\"flags\":%u,\"device\":%u,\"parent\":%u}\n",rd32(cp),rd32(cp+4),rd32(cp+8),rd32(cp+12),device,parent);fflush(stdout);
 if(rd32(cp)!=0||rd32(cp+4)!=1||rd32(cp+8)!=window||rd32(cp+12)!=0x22)xrt_fatal(c,76,"owned native identity readback mismatch");
 backend_identity();
finish:
 w=CreateThread(NULL,0,worker,NULL,0,NULL);if(!w||WaitForSingleObject(w,5000)!=WAIT_OBJECT_0)xrt_fatal(c,76,"owned worker failed");CloseHandle(w);
 /* No native result or CPU/FPU/error is normalized. The owned protocol sets
  * its own return sentinel; no genuine Init function has been called. */
 xm_scope(c,XM_END,XM_ADAPTER,"UGameEngine.Init",0);c->rv=0x1090ed5c;
 owned_invoke(c,0x1090ed5c);ExitProcess(92);
}
