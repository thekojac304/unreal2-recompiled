#define xrt_mod_ehprobe xrt_mod_getobjectprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
#define COBJMACROS
#include <oleacc.h>
static uint32_t checked_callback(CPU* c,uint32_t proc,int nargs,const uint32_t* args,int stdcall) {
    CPU saved=*c;uint32_t result;DWORD error;
    result=xrt_call_guest(c,proc,nargs,args,stdcall);error=GetLastError();
    if(c->r[ESP]!=saved.r[ESP] || c->r[EBX]!=saved.r[EBX] || c->r[EBP]!=saved.r[EBP] || c->r[ESI]!=saved.r[ESI] || c->r[EDI]!=saved.r[EDI] ||
        c->fcw!=saved.fcw || c->fsw!=saved.fsw || c->top!=saved.top || memcmp(c->st,saved.st,sizeof c->st))
        xrt_fatal(c,XRT_EXIT_BADRET,"fixture: callback ABI/FPU mismatch");
    xrt_event("fixture_callback_abi","\"proc\":%u,\"message\":%u,\"esp\":%u,\"result\":%u,\"passed\":true",proc,args[1],c->r[ESP],result);
    SetLastError(error);return result;
}
/* Test-only inclusion provides an active suspended guest-host scope for real
 * host-originated accessibility requests; no production test API is added. */
#define xrt_call_guest checked_callback
#include "../../runtime/hle_gui.c"
#undef xrt_call_guest
static XrtModule* module;
static CPU* cpu;
static uint32_t mode,log_n,log_data,destroy_fn;
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static HWND make(const char* path,const char* report) {
    uint32_t token;xrt_report_path=report;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    module=xrt_module_load(path,&xrt_mod_getobjectprobe);xrt_module_bind_imports(module);hle_msvcr70_init();
    xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;
    mode=xrt_module_export(module,"probe_mode",0);log_n=xrt_module_export(module,"probe_log_n",0);log_data=xrt_module_export(module,"probe_log",0);
    destroy_fn=xrt_module_export(module,"probe_destroy",0);
    token=xrt_call_guest(cpu,xrt_module_export(module,"probe_make",0),0,NULL,0);
    callback_cpu=cpu;return window_host(token);
}
static BOOL destroy(HWND h){(void)h;return (BOOL)xrt_call_guest(cpu,destroy_fn,0,NULL,0);}
static void finish(void){
    uint32_t count=rd32(xrt_module_export(module,"probe_abi_count",0));
    uint32_t failed=rd32(xrt_module_export(module,"probe_abi_fail",0));
    fprintf(stderr,"x86 callback ABI count=%u failures=%u\n",count,failed);
    if(!count || failed)ExitProcess(9);
    xrt_report_write(0,"exited");xrt_baton_release();
}
int main(int argc,char** argv) {
    HWND h;if(argc!=3)return 2;
    h=make(argv[1],argv[2]);if(!h)return 3;
    SendMessageW(h,WM_GETOBJECT,0,(LPARAM)(LONG)-12);
    return 10; /* Must remain unreachable in the translated dialog protocol. */
}

