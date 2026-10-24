#define xrt_mod_ehprobe xrt_mod_focusprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static XrtModule* module;
static __declspec(thread) CPU* cpu;
static uint32_t seed,error,window,read_fn,make_fn,valid_fn,destroy_fn;
static void thread_begin(void){xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;}
static void thread_end(void){xrt_baton_release();}
static void release_guest(void){xrt_baton_release();}
static void acquire_guest(void){xrt_baton_acquire();}
static void init(const char* dll) {
    xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    module=xrt_module_load(dll,&xrt_mod_focusprobe);xrt_module_bind_imports(module);
    hle_msvcr70_init();thread_begin();
    seed=xrt_module_export(module,"probe_seed",0);error=xrt_module_export(module,"probe_error",0);
    window=xrt_module_export(module,"probe_window",0);read_fn=xrt_module_export(module,"probe_read",0);
    make_fn=xrt_module_export(module,"probe_make",0);valid_fn=xrt_module_export(module,"probe_valid",0);
    destroy_fn=xrt_module_export(module,"probe_destroy",0);
}
static uint32_t call(uint32_t fn){return xrt_call_guest(cpu,fn,0,NULL,0);}
static uintptr_t make(void){return call(make_fn);}
static HWND host(uintptr_t h){return (HWND)xrt_handle_get((uint32_t)h,XH_WINDOW);}
static uintptr_t query(DWORD s,DWORD* e){uint32_t h;wr32(seed,s);h=call(read_fn);*e=rd32(error);return h;}
static int valid(uintptr_t h){wr32(window,(uint32_t)h);return (int)call(valid_fn);}
static int destroy(uintptr_t h){wr32(window,(uint32_t)h);return (int)call(destroy_fn);}
static void finish(void){xrt_report_write(0,"exited");thread_end();}
#include "driver.h"
