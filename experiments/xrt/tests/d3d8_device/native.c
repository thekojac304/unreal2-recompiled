/* Disposable native CreateDevice oracle. Never linked into the runtime/client. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <xmmintrin.h>
#include "../../runtime/d3d8_abi.h"
typedef struct DeviceVT {
    HRESULT(WINAPI*qi)(D8Device*,REFIID,void**);
    ULONG(WINAPI*add)(D8Device*);ULONG(WINAPI*release)(D8Device*);
    HRESULT(WINAPI*cooperative)(D8Device*);UINT(WINAPI*memory)(D8Device*);
    HRESULT(WINAPI*discard)(D8Device*,DWORD);
    HRESULT(WINAPI*parent)(D8Device*,D8Interface**);
    HRESULT(WINAPI*caps)(D8Device*,D8Caps*);
    HRESULT(WINAPI*display)(D8Device*,D8Mode*);
    HRESULT(WINAPI*creation)(D8Device*,void*);
    void*unused[6];
    HRESULT(WINAPI*backbuffer)(D8Device*,UINT,UINT,void**);
} DeviceVT;
struct D8Device {const DeviceVT*vt;};
typedef struct Creation {UINT adapter,type;HWND focus;DWORD flags;} Creation;
typedef struct Args {void*fn;D8Interface*parent;UINT adapter,type;HWND focus;DWORD flags;D8Present*pp;D8Device**out;} Args;
typedef __declspec(align(16)) struct ABI {
    DWORD hr,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];
} ABI;
extern void device_abi(Args*,ABI*);
typedef char checkABI[offsetof(ABI,pre)==240&&offsetof(ABI,post)==752?1:-1];
static const GUID iidUnknown={0,0,0,{0xc0,0,0,0,0,0,0,0x46}};
static const GUID iidDevice={0x7385e5df,0x8fe8,0x41d5,{0x86,0xb6,0xd7,0xb4,0x85,0x47,0xb6,0xcf}};
static const GUID iidParent={0x1dd9e8da,0x1c77,0x4d40,{0xb0,0xcf,0x98,0xfe,0xfd,0xff,0x95,0x12}};
static const GUID iidDevice9={0xd0223b96,0xbf7a,0x43fd,{0x92,0xbd,0xa4,0x3b,0x0d,0x82,0xb9,0xeb}};
static const GUID iidBogus={0xdeadbeef,0x1234,0x5678,{1,2,3,4,5,6,7,8}};
static DWORD mainThread,phase;static unsigned msgCount,reentrant,foreignThread;
static struct {UINT msg;DWORD tid,phase;ULONG_PTR hwnd,wp,lp;} messages[512];
static LRESULT CALLBACK wndproc(HWND w,UINT m,WPARAM wp,LPARAM lp) {
    DWORD error=GetLastError(),tid=GetCurrentThreadId();
    if(phase==1)reentrant++;if(tid!=mainThread)foreignThread++;
    if(msgCount<512){messages[msgCount].msg=m;messages[msgCount].tid=tid;messages[msgCount].phase=phase;messages[msgCount].hwnd=(ULONG_PTR)w;messages[msgCount].wp=wp;messages[msgCount].lp=(ULONG_PTR)lp;msgCount++;}
    SetLastError(error);return DefWindowProcW(w,m,wp,lp);
}
static void pump(void){MSG m;while(PeekMessageW(&m,NULL,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);}}
static unsigned threads(void){THREADENTRY32 e;unsigned n=0;HANDLE h=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);e.dwSize=sizeof e;if(h!=INVALID_HANDLE_VALUE){if(Thread32First(h,&e))do{if(e.th32OwnerProcessID==GetCurrentProcessId())n++;}while(Thread32Next(h,&e));CloseHandle(h);}return n;}
static void resources(const char*tag){DWORD n=0;GetProcessHandleCount(GetCurrentProcess(),&n);printf("{\"kind\":\"resources\",\"tag\":\"%s\",\"handles\":%lu,\"threads\":%u,\"user\":%lu,\"gdi\":%lu}\n",tag,n,threads(),GetGuiResources(GetCurrentProcess(),GR_USEROBJECTS),GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS));}
static void ppjson(const D8Present*p){printf("[%u,%u,%u,%u,%u,%u,%llu,%ld,%ld,%u,%u,%u,%u]",p->width,p->height,p->format,p->count,p->multisample,p->swap,(unsigned long long)(ULONG_PTR)p->window,p->windowed,p->depth,p->depthformat,p->flags,p->refresh,p->interval);}
static void bytes(const BYTE*p,unsigned n){unsigned i;putchar('"');for(i=0;i<n;i++)printf("%02x",p[i]);putchar('"');}
static DWORD exCode,exError,exAccess;static ULONG_PTR exAddress;
static int caught(EXCEPTION_POINTERS*p){exCode=p->ExceptionRecord->ExceptionCode;exError=GetLastError();exAccess=(DWORD)p->ExceptionRecord->ExceptionInformation[0];exAddress=p->ExceptionRecord->ExceptionInformation[1];return EXCEPTION_EXECUTE_HANDLER;}
static void identity(D8Device*d,D8Interface*p){
    const GUID*ids[]={&iidUnknown,&iidDevice,&iidParent,&iidDevice9,&iidBogus};unsigned i;HRESULT hr;void*q;ULONG count;Creation cp;D8Caps caps;D8Mode mode;D8Interface*par=NULL;
    for(i=0;i<5;i++){q=(void*)(ULONG_PTR)0xa5a5a5a5;SetLastError(18);hr=d->vt->qi(d,ids[i],&q);printf("{\"kind\":\"qi\",\"iid_case\":%u,\"hr\":%lu,\"output\":%llu,\"same\":%s,\"last_error\":%lu",i,(DWORD)hr,(unsigned long long)(ULONG_PTR)q,q==d?"true":"false",GetLastError());if(SUCCEEDED(hr)&&q){count=((D8Device*)q)->vt->release(q);printf(",\"release\":%lu",count);}puts("}");}
    SetLastError(18);hr=d->vt->qi(d,&iidDevice,NULL);printf("{\"kind\":\"qi_null\",\"hr\":%lu,\"error\":%lu}\n",(DWORD)hr,GetLastError());
    count=d->vt->add(d);printf("{\"kind\":\"device_add\",\"count\":%lu}\n",count);count=d->vt->release(d);printf("{\"kind\":\"device_balance\",\"count\":%lu}\n",count);
    count=p->vt->AddRef(p);printf("{\"kind\":\"parent_add_with_device\",\"count\":%lu}\n",count);count=p->vt->Release(p);printf("{\"kind\":\"parent_balance\",\"count\":%lu}\n",count);
    hr=d->vt->parent(d,&par);printf("{\"kind\":\"get_parent\",\"hr\":%lu,\"same\":%s",(DWORD)hr,par==p?"true":"false");if(SUCCEEDED(hr)&&par)printf(",\"release\":%lu",par->vt->Release(par));puts("}");
    memset(&cp,0xa5,sizeof cp);hr=d->vt->creation(d,&cp);printf("{\"kind\":\"creation_parameters\",\"hr\":%lu,\"adapter\":%u,\"type\":%u,\"focus\":%llu,\"flags\":%lu}\n",(DWORD)hr,cp.adapter,cp.type,(unsigned long long)(ULONG_PTR)cp.focus,cp.flags);
    memset(&caps,0xa5,sizeof caps);hr=d->vt->caps(d,&caps);printf("{\"kind\":\"caps\",\"hr\":%lu,\"bytes\":",(DWORD)hr);bytes((BYTE*)&caps,sizeof caps);puts("}");
    memset(&mode,0xa5,sizeof mode);hr=d->vt->display(d,&mode);printf("{\"kind\":\"display\",\"hr\":%lu,\"mode\":[%u,%u,%u,%u]}\n",(DWORD)hr,mode.width,mode.height,mode.refresh,mode.format);
    {void*surface=NULL;DWORD desc[8];void**vt;typedef HRESULT(WINAPI*GetDesc)(void*,void*);typedef ULONG(WINAPI*Rel)(void*);
    hr=d->vt->backbuffer(d,0,0,&surface);printf("{\"kind\":\"backbuffer\",\"hr\":%lu,\"non_null\":%s",(DWORD)hr,surface?"true":"false");if(SUCCEEDED(hr)&&surface){vt=*(void***)surface;memset(desc,0xa5,sizeof desc);hr=((GetDesc)vt[8])(surface,desc);printf(",\"desc_hr\":%lu,\"desc\":[%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu],\"release\":%lu",(DWORD)hr,desc[0],desc[1],desc[2],desc[3],desc[4],desc[5],desc[6],desc[7],((Rel)vt[2])(surface));}puts("}");}
}
static int one(D8Interface*p,HWND focus,HWND device,const char*name,DWORD seed,unsigned repetition){
    D8Present pp={1540,945,22,1,0,1,NULL,1,1,77,1,0,0},before;D8Present*present=&pp;D8Device*out=(D8Device*)(ULONG_PTR)0xa5a5a5a5;D8Device**output=&out;
    UINT adapter=0,type=1;DWORD flags=0x42,error;HRESULT hr=(HRESULT)0xdeadbeef;ABI abi;Args args;DWORD old=0;BYTE*mem=NULL;ULONG n;LONG_PTR fproc,dproc;unsigned startmsg=msgCount,i;BOOL useabi=!strncmp(name,"abi",3);
    pp.window=focus;
    if(!strcmp(name,"adapter_count"))adapter=p->vt->GetAdapterCount(p);
    if(!strcmp(name,"adapter_ffff"))adapter=65535;
    if(!strcmp(name,"adapter_max"))adapter=0xffffffff;
    if(!strcmp(name,"abi_invalid_adapter"))adapter=0xffffffff;
    if(!strcmp(name,"abi_invalid_depth"))pp.depthformat=71;
    if(!strncmp(name,"type_",5))type=(UINT)strtoul(name+5,NULL,0);
    if(!strcmp(name,"focus_null"))focus=NULL;if(!strcmp(name,"focus_invalid"))focus=(HWND)(ULONG_PTR)1;
    if(!strcmp(name,"device_null"))pp.window=NULL;if(!strcmp(name,"device_invalid"))pp.window=(HWND)(ULONG_PTR)1;
    if(!strcmp(name,"both_null")){focus=NULL;pp.window=NULL;}
    if(!strcmp(name,"both_invalid")){focus=(HWND)(ULONG_PTR)1;pp.window=focus;}
    if(!strcmp(name,"separate_window"))pp.window=device;
    if(!strcmp(name,"separate_zero")){pp.window=device;pp.width=pp.height=0;}
    if(!strcmp(name,"dimensions_zero")){pp.width=pp.height=0;}
    if(!strcmp(name,"width_zero"))pp.width=0;
    if(!strcmp(name,"width_over_cap")){pp.width=16385;pp.height=1;}
    if(!strcmp(name,"height_over_cap")){pp.width=1;pp.height=16385;}
    if(!strncmp(name,"depth_",6))pp.depthformat=(UINT)strtoul(name+6,NULL,0);
    if(!strcmp(name,"format_invalid"))pp.format=0xffffffff;
    if(!strcmp(name,"format_unknown"))pp.format=0;
    if(!strcmp(name,"count_zero"))pp.count=0;if(!strcmp(name,"count_4"))pp.count=4;
    if(!strcmp(name,"swap_zero"))pp.swap=0;if(!strcmp(name,"swap_invalid"))pp.swap=0xffffffff;
    if(!strcmp(name,"copy_two")){pp.swap=3;pp.count=2;}
    if(!strcmp(name,"multisample_invalid"))pp.multisample=17;
    if(!strcmp(name,"interval_one"))pp.interval=1;
    if(!strcmp(name,"refresh_windowed"))pp.refresh=60;
    if(!strcmp(name,"flags_invalid"))pp.flags=0xffffffff;
    if(!strcmp(name,"behavior_zero"))flags=0;
    if(!strcmp(name,"abi_no_preserve"))flags=0x40;
    if(!strcmp(name,"pp_null"))present=NULL;
    if(!strcmp(name,"pp_one"))present=(D8Present*)(ULONG_PTR)1;
    if(!strcmp(name,"out_null"))output=NULL;
    if(!strcmp(name,"out_one"))output=(D8Device**)(ULONG_PTR)1;
    if(!strcmp(name,"out_readonly")||!strcmp(name,"pp_readonly")||!strcmp(name,"pp_noaccess")||!strcmp(name,"out_noaccess")){
        mem=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!mem)return 10;
        if(!strncmp(name,"out_",4)){memcpy(mem,&out,sizeof out);output=(D8Device**)mem;}else{memcpy(mem,&pp,sizeof pp);present=(D8Present*)mem;}
        VirtualProtect(mem,4096,strstr(name,"noaccess")?PAGE_NOACCESS:PAGE_READONLY,&old);
    }
    before=pp;memset(&abi,0,sizeof abi);args.fn=(void*)p->vt->CreateDevice;args.parent=p;args.adapter=adapter;args.type=type;args.focus=focus;args.flags=flags;args.pp=present;args.out=output;
    fproc=focus&&IsWindow(focus)?GetWindowLongPtrW(focus,GWLP_WNDPROC):0;dproc=IsWindow(pp.window)?GetWindowLongPtrW(pp.window,GWLP_WNDPROC):0;
    resources("before_create");exCode=exError=exAccess=0;exAddress=0;phase=1;SetLastError(seed);
    __try{if(useabi){device_abi(&args,&abi);hr=(HRESULT)abi.hr;}else hr=p->vt->CreateDevice(p,adapter,type,focus,flags,present,output);error=GetLastError();}
    __except(caught(GetExceptionInformation())){error=exError;}
    phase=2;
    printf("{\"kind\":\"pointer_context\",\"parameters\":%llu,\"output_address\":%llu,\"call_thread\":%lu,\"focus_owner_thread\":%lu,\"device_owner_thread\":%lu}\n",(unsigned long long)(ULONG_PTR)present,(unsigned long long)(ULONG_PTR)output,GetCurrentThreadId(),GetWindowThreadProcessId(focus,NULL),GetWindowThreadProcessId(pp.window,NULL));
    if(mem){VirtualProtect(mem,4096,PAGE_READWRITE,&old);if(output==(D8Device**)mem)memcpy(&out,mem,sizeof out);if(present==(D8Present*)mem)memcpy(&pp,mem,sizeof pp);}
    printf("{\"kind\":\"create\",\"case\":\"%s\",\"rep\":%u,\"adapter\":%u,\"type\":%u,\"flags\":%lu,\"seed\":%lu,\"hr\":%lu,\"last_error\":%lu,\"output\":%llu,\"exception\":%lu,\"exception_access\":%lu,\"exception_address\":%llu,\"focus\":%llu,\"before\":",name,repetition,adapter,type,flags,seed,(DWORD)hr,error,(unsigned long long)(ULONG_PTR)out,exCode,exAccess,(unsigned long long)exAddress,(unsigned long long)(ULONG_PTR)focus);ppjson(&before);printf(",\"after\":");ppjson(&pp);printf(",\"raw_before\":");bytes((BYTE*)&before,sizeof before);printf(",\"raw_after\":");bytes((BYTE*)&pp,sizeof pp);printf(",\"focus_subclassed\":%s,\"device_subclassed\":%s,\"messages_during_create\":%u}\n",fproc&&GetWindowLongPtrW(focus,GWLP_WNDPROC)!=fproc?"true":"false",dproc&&GetWindowLongPtrW(pp.window,GWLP_WNDPROC)!=dproc?"true":"false",msgCount-startmsg);
    if(useabi&&!exCode){printf("{\"kind\":\"abi\",\"case\":\"%s\",\"delta\":%lu,\"regs\":[",name,abi.delta);for(i=0;i<8;i++)printf("%s%llu",i?",":"",(unsigned long long)abi.regs[i]);printf("],\"xmm\":");bytes(abi.xmm,160);printf(",\"fx_pre\":");bytes(abi.pre,512);printf(",\"fx_post\":");bytes(abi.post,512);puts("}");}
    if(exCode){puts("{\"kind\":\"isolated_exception_exit\",\"orderly_cleanup\":false}");fflush(stdout);ExitProcess(90);}
    if(SUCCEEDED(hr)&&out&&out!=(D8Device*)(ULONG_PTR)0xa5a5a5a5){
        identity(out,p);
        if(!strcmp(name,"parent_first")){n=p->vt->Release(p);printf("{\"kind\":\"parent_external_release_first\",\"count\":%lu}\n",n);{D8Interface*q=NULL;HRESULT h=out->vt->parent(out,&q);printf("{\"kind\":\"parent_after_external_release\",\"hr\":%lu,\"same\":%s,\"balance\":%lu}\n",(DWORD)h,q==p?"true":"false",q?q->vt->Release(q):0);}n=out->vt->release(out);printf("{\"kind\":\"device_final_release\",\"count\":%lu}\n",n);out=NULL;}
        else{n=out->vt->release(out);printf("{\"kind\":\"device_final_release\",\"count\":%lu}\n",n);}
    }
    phase=3;pump();Sleep(25);resources("after_release");
    printf("{\"kind\":\"window_after_release\",\"focus_valid\":%s,\"focus_proc_restored\":%s,\"device_proc_restored\":%s}\n",IsWindow(focus)?"true":"false",!fproc||GetWindowLongPtrW(focus,GWLP_WNDPROC)==fproc?"true":"false",!dproc||GetWindowLongPtrW(pp.window,GWLP_WNDPROC)==dproc?"true":"false");
    if(mem)VirtualFree(mem,0,MEM_RELEASE);return !strcmp(name,"parent_first")?1:0;
}
typedef struct Worker {D8Interface*p;HWND focus,device;DWORD seed;int result;}Worker;
static DWORD WINAPI worker(void*arg){Worker*w=arg;w->result=one(w->p,w->focus,w->device,"cross_thread",w->seed,0);return 0;}
int main(int argc,char**argv){
    HMODULE dep,lib;D8Factory factory;D8Interface*p;char path[2048];HWND focus,device;WNDCLASSW wc;unsigned i,reps=1;DWORD seed=18,pid;ULONG n;int released=0;const char*name;
    setvbuf(stdout,NULL,_IONBF,0);SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);mainThread=GetCurrentThreadId();
    if(argc<3)return 2;name=argv[2];if(argc>3)seed=strtoul(argv[3],NULL,0);if(argc>4)reps=strtoul(argv[4],NULL,0);
    memset(&wc,0,sizeof wc);wc.lpfnWndProc=wndproc;wc.hInstance=GetModuleHandleW(NULL);wc.lpszClassName=L"XRT_CreateDevice_Oracle_Owned";if(!RegisterClassW(&wc))return 3;
    focus=CreateWindowExW(0,wc.lpszClassName,L"CreateDevice fixture focus",WS_OVERLAPPEDWINDOW,0,0,1560,1000,NULL,NULL,wc.hInstance,NULL);
    device=CreateWindowExW(0,wc.lpszClassName,L"CreateDevice fixture secondary",WS_OVERLAPPEDWINDOW,0,0,800,600,NULL,NULL,wc.hInstance,NULL);if(!focus||!device)return 4;
    pump();phase=0;resources("before_load");
    snprintf(path,sizeof path,"%s\\d3d9.dll",argv[1]);dep=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    snprintf(path,sizeof path,"%s\\d3d8.dll",argv[1]);lib=LoadLibraryExA(path,NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!dep||!lib)return 5;
    factory=(D8Factory)GetProcAddress(lib,"Direct3DCreate8");if(!factory||!(p=factory(120)))return 6;
    printf("{\"kind\":\"setup\",\"pointer_bytes\":%zu,\"present_bytes\":%zu,\"window_offset\":%zu,\"windowed_offset\":%zu,\"interval_offset\":%zu,\"creation_bytes\":%zu,\"adapters\":%u,\"thread\":%lu,\"process\":%lu,\"focus\":%llu,\"device\":%llu,\"window_thread\":%lu,\"window_process\":",sizeof(void*),sizeof(D8Present),offsetof(D8Present,window),offsetof(D8Present,windowed),offsetof(D8Present,interval),sizeof(Creation),p->vt->GetAdapterCount(p),mainThread,GetCurrentProcessId(),(unsigned long long)(ULONG_PTR)focus,(unsigned long long)(ULONG_PTR)device,GetWindowThreadProcessId(focus,&pid));printf("%lu}\n",pid);
    resources("factory_ready");
    {RECT fr,dr;GetClientRect(focus,&fr);GetClientRect(device,&dr);printf("{\"kind\":\"client_dimensions\",\"focus\":[%ld,%ld],\"device\":[%ld,%ld]}\n",fr.right-fr.left,fr.bottom-fr.top,dr.right-dr.left,dr.bottom-dr.top);}
    if(!strcmp(name,"cross_thread")){Worker w;HANDLE h;w.p=p;w.focus=focus;w.device=device;w.seed=seed;w.result=0;h=CreateThread(NULL,0,worker,&w,0,NULL);if(!h)return 8;while(WaitForSingleObject(h,0)!=WAIT_OBJECT_0){MsgWaitForMultipleObjects(1,&h,FALSE,1000,QS_ALLINPUT);pump();}CloseHandle(h);released=w.result;}
    else for(i=0;i<reps;i++){released=one(p,focus,device,name,seed,i);if(released)break;}
    if(!released){n=p->vt->Release(p);printf("{\"kind\":\"parent_final_release\",\"count\":%lu}\n",n);}
    FreeLibrary(lib);FreeLibrary(dep);printf("{\"kind\":\"unload\",\"d3d8_loaded\":%s,\"d3d9_loaded\":%s}\n",GetModuleHandleW(L"d3d8.dll")?"true":"false",GetModuleHandleW(L"d3d9.dll")?"true":"false");
    DestroyWindow(device);DestroyWindow(focus);UnregisterClassW(wc.lpszClassName,wc.hInstance);pump();resources("final");
    printf("{\"kind\":\"callbacks\",\"reentrant\":%u,\"foreign_thread\":%u,\"messages\":[",reentrant,foreignThread);for(i=0;i<msgCount;i++)printf("%s[%u,%lu,%lu,%llu,%llu,%llu]",i?",":"",messages[i].msg,messages[i].tid,messages[i].phase,(unsigned long long)messages[i].hwnd,(unsigned long long)messages[i].wp,(unsigned long long)messages[i].lp);puts("]}");
    return 0;
}
