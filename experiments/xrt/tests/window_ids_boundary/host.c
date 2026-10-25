#define xrt_mod_ehprobe xrt_mod_idprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static __declspec(thread) CPU*cpu;
static uint32_t window,output,seed,error,abi,pid,tid,run_fn,make_fn,destroy_fn;
static unsigned char*buffer;static uintptr_t base;
static void thread_begin(void){xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;}
static void thread_end(void){xrt_baton_release();}
static void release_guest(void){xrt_baton_release();}
static void acquire_guest(void){xrt_baton_acquire();}
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static uintptr_t call(uint32_t fn){return xrt_call_guest(cpu,fn,0,NULL,0);}
static void init(const char*dll,const char*report) {
    XrtModule*m;xrt_report_path=report;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    m=xrt_module_load(dll,&xrt_mod_idprobe);xrt_module_bind_imports(m);hle_msvcr70_init();thread_begin();
#define DATA(n,s) n=xrt_module_export(m,s,0)
    DATA(window,"probe_window");DATA(output,"probe_output");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");DATA(pid,"probe_pid");DATA(tid,"probe_tid");DATA(run_fn,"probe_run");DATA(make_fn,"probe_make");DATA(destroy_fn,"probe_destroy");
#undef DATA
    base=0x40000000;xrt_commit((uint32_t)base,0x3000);buffer=G2H((uint32_t)base);
}
static uintptr_t wrong(void){return xrt_handle_new(XH_MUTEX,NULL);}
static void finish(void){xrt_report_write(0,"exited");thread_end();}
#include "driver.h"
