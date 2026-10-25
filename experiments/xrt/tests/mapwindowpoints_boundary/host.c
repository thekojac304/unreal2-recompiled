#define xrt_mod_ehprobe xrt_mod_mapprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static CPU*cpu;static uint32_t from,to,points,count,seed,result,error,abi,run_fn;
static unsigned char*buffer;static uintptr_t base;
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static uintptr_t call(uint32_t fn){return xrt_call_guest(cpu,fn,0,NULL,0);}
static void init(const char*dll,const char*report) {
    XrtModule*m;xrt_report_path=report;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);m=xrt_module_load(dll,&xrt_mod_mapprobe);xrt_module_bind_imports(m);hle_msvcr70_init();xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;
#define DATA(n,s) n=xrt_module_export(m,s,0)
    DATA(from,"probe_from");DATA(to,"probe_to");DATA(points,"probe_points");DATA(count,"probe_count");DATA(seed,"probe_seed");DATA(result,"probe_result");DATA(error,"probe_error");DATA(abi,"probe_abi");DATA(run_fn,"probe_run");
#undef DATA
    base=0x40000000;xrt_commit((uint32_t)base,0x3000);buffer=G2H((uint32_t)base);
}
static uintptr_t token(HWND h){return xrt_handle_new(XH_WINDOW,h);}
static uintptr_t wrong(void){return xrt_handle_new(XH_MUTEX,NULL);}
static void finish(void){xrt_report_write(0,"exited");xrt_baton_release();}
#include "driver.h"
