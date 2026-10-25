#define xrt_mod_ehprobe xrt_mod_setfocusprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static XrtModule* module;
static __declspec(thread) CPU* cpu;
static uint32_t window,seed,error,abi,mode,trigger,target,log_n,log_data,parent;
static uint32_t run_fn,make_fn,read_fn,destroy_fn,init_fn;
static void thread_begin(void){xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;}
static void thread_end(void){xrt_baton_release();}
static void release_guest(void){xrt_baton_release();}
static void acquire_guest(void){xrt_baton_acquire();}
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static uintptr_t call(uint32_t fn){return xrt_call_guest(cpu,fn,0,NULL,0);}
static void init(const char* dll){
    xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    module=xrt_module_load(dll,&xrt_mod_setfocusprobe);xrt_module_bind_imports(module);hle_msvcr70_init();thread_begin();
#define DATA(n,s) n=xrt_module_export(module,s,0)
    DATA(window,"probe_window");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");
    DATA(mode,"probe_mode");DATA(trigger,"probe_trigger");DATA(target,"probe_target");
    DATA(log_n,"probe_log_n");DATA(log_data,"probe_log");
    DATA(parent,"probe_parent");
    DATA(run_fn,"probe_run");DATA(make_fn,"probe_make");DATA(read_fn,"probe_read");DATA(destroy_fn,"probe_destroy");DATA(init_fn,"probe_init");
#undef DATA
    if(!call(init_fn))ExitProcess(3);
}
static HWND host(uintptr_t h){return (HWND)xrt_handle_get((uint32_t)h,XH_WINDOW);}
static uintptr_t wrong(void){return xrt_handle_new(XH_MUTEX,NULL);}
static void finish(void){xrt_report_write(0,"exited");thread_end();}
#include "driver.h"
