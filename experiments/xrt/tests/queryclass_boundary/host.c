#define xrt_mod_ehprobe xrt_mod_viewportprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
#define COBJMACROS
#include <oleacc.h>
#include <stdint.h>
/* Observe the real Windows call behind the adapter, including full-width
 * active-frame argument reconstruction. This wrapper supplies no result. */
static LRESULT WINAPI observed_default(HWND h,UINT msg,WPARAM wp,LPARAM lp) {
    LRESULT result=DefWindowProcW(h,msg,wp,lp);DWORD error=GetLastError();
    if(msg==WM_GETOBJECT)xrt_event("fixture_real_default","\"wparam64\":%llu,\"lparam64\":%llu,\"result\":%lld,\"last_error\":%u",
        (unsigned long long)wp,(unsigned long long)lp,(long long)result,error);
    SetLastError(error);return result;
}
static uint32_t checked_callback(CPU* c,uint32_t proc,int nargs,const uint32_t* args,int stdcall) {
    CPU saved=*c;uint32_t result;DWORD error;
    result=xrt_call_guest(c,proc,nargs,args,stdcall);error=GetLastError();
    if(c->r[ESP]!=saved.r[ESP] || c->r[EBX]!=saved.r[EBX] || c->r[EBP]!=saved.r[EBP] || c->r[ESI]!=saved.r[ESI] || c->r[EDI]!=saved.r[EDI] ||
        c->fcw!=saved.fcw || c->fsw!=saved.fsw || c->top!=saved.top || memcmp(c->st,saved.st,sizeof c->st))
        xrt_fatal(c,XRT_EXIT_BADRET,"fixture: callback ABI/FPU mismatch");
    xrt_event("fixture_callback_abi","\"proc\":%u,\"message\":%u,\"result\":%u,\"passed\":true",proc,args[1],result);
    SetLastError(error);return result;
}
#define xrt_call_guest checked_callback
#define DefWindowProcW observed_default
#include "../../runtime/hle_gui.c"
#undef DefWindowProcW
#undef xrt_call_guest
static XrtModule* module;
static CPU* cpu;
static uint32_t mode,log_n,log_data,destroy_fn;
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static HWND make(const char* path,const char* report,int ansi) {
    uint32_t token;xrt_report_path=report;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    module=xrt_module_load(path,&xrt_mod_viewportprobe);xrt_module_bind_imports(module);hle_msvcr70_init();
    xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;
    mode=xrt_module_export(module,"probe_mode",0);log_n=xrt_module_export(module,"probe_log_n",0);log_data=xrt_module_export(module,"probe_log",0);
    wr32(xrt_module_export(module,"probe_ansi",0),ansi);destroy_fn=xrt_module_export(module,"probe_destroy",0);
    token=xrt_call_guest(cpu,xrt_module_export(module,"probe_make",0),0,NULL,0);callback_cpu=cpu;
    /* Nonempty, nondefault suspended x87 state must survive every callback. */
    cpu->fcw=0x077f;cpu->fsw=0x3100;cpu->top=6;cpu->st[6]=1.25;cpu->st[7]=-2.5;
    return window_host(token);
}
static BOOL destroy(HWND h){(void)h;return (BOOL)xrt_call_guest(cpu,destroy_fn,0,NULL,0);}
static void finish(void){
    uint32_t count=rd32(xrt_module_export(module,"probe_abi_count",0)),failed=rd32(xrt_module_export(module,"probe_abi_fail",0));
    fprintf(stderr,"x86 callback ABI count=%u failures=%u\n",count,failed);if(!count||failed)ExitProcess(9);
    xrt_report_write(0,"exited");xrt_baton_release();
}
#include "driver.h"
