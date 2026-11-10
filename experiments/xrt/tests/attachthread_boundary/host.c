#define xrt_mod_ehprobe xrt_mod_attachprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
#include <string.h>
static CPU* cpu;
static uint32_t probe_from,probe_to,probe_attach,probe_seed,probe_result,probe_error,probe_abi,run_fn;
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static void call_probe(void){xrt_call_guest(cpu,run_fn,0,NULL,0);}
#include "driver.h"
int main(int argc,char** argv) {
    XrtModule* m;int result;if(argc!=4)return 2;
    xrt_report_path=argv[3];xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    m=xrt_module_load(argv[1],&xrt_mod_attachprobe);xrt_module_bind_imports(m);
    cpu=&xrt_thread_main(0x100000)->cpu;xrt_baton_acquire();
#define DATA(n) n=xrt_module_export(m,#n,0);if(!n)return 2
    DATA(probe_from);DATA(probe_to);DATA(probe_attach);DATA(probe_seed);DATA(probe_result);DATA(probe_error);DATA(probe_abi);
#undef DATA
    run_fn=xrt_module_export(m,"probe_run",0);if(!run_fn)return 2;
    if(!strcmp(argv[2],"mismatch"))cpu->thread->guest_tid^=1;
    if(!strcmp(argv[2],"expired"))cpu->thread->state=2;
    if(!strcmp(argv[2],"no-thread")) {
        const XrtHle* h;
        uint32_t esp=cpu->r[ESP];
        wr32(esp,0x12345678);wr32(esp+4,GetCurrentThreadId());
        wr32(esp+8,GetCurrentThreadId());wr32(esp+12,1);
        cpu->thread=NULL;
        for(h=xrt_hle_gui;h->dll;h++)if(!strcmp(h->name,"AttachThreadInput")){h->fn(cpu);return 9;}
        return 10;
    }
    result=drive(argv[2]);xrt_report_write(result,"exited");return result;
}
