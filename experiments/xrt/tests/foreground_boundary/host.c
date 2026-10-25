#define xrt_mod_ehprobe xrt_mod_foregroundprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
typedef uint32_t DATA;
static DATA pointer,seed,error,abi,rect,run_fn;static CPU* cpu;
static void init(const char* path){XrtModule*m;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);m=xrt_module_load(path,&xrt_mod_foregroundprobe);xrt_module_bind_imports(m);hle_msvcr70_init();xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;
#define GET(n,s) n=xrt_module_export(m,s,0)
    GET(pointer,"probe_pointer");GET(seed,"probe_seed");GET(error,"probe_error");GET(abi,"probe_abi");GET(rect,"probe_rect");GET(run_fn,"probe_run");
#undef GET
}
static DWORD get(DATA p,unsigned i){return rd32(p+4*i);}
static void put(DATA p,unsigned i,DWORD v){wr32(p+4*i,v);}
static DWORD address(DATA p){return p;}
static DWORD run(void){return (DWORD)xrt_call_guest(cpu,run_fn,0,NULL,0);}
static void finish(void){xrt_report_write(0,"exited");xrt_baton_release();}
static HWND host(DWORD h){return (HWND)xrt_handle_get(h,XH_WINDOW);}
#include "driver.h"
