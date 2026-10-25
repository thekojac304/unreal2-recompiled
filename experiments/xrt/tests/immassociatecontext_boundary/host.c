#define xrt_mod_ehprobe xrt_mod_immprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
#include <imm.h>
static XrtModule* module;
static __declspec(thread) CPU* cpu;
static uint32_t window,context,seed,error,abi,run_fn,make_fn,destroy_fn;
static void thread_begin(void){xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;}
static void thread_end(void){xrt_baton_release();}
static void release_guest(void){xrt_baton_release();}
static void acquire_guest(void){xrt_baton_acquire();}
static void init(const char* dll) {
    xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    module=xrt_module_load(dll,&xrt_mod_immprobe);xrt_module_bind_imports(module);hle_msvcr70_init();thread_begin();
    window=xrt_module_export(module,"probe_window",0);context=xrt_module_export(module,"probe_context",0);
    seed=xrt_module_export(module,"probe_seed",0);error=xrt_module_export(module,"probe_error",0);abi=xrt_module_export(module,"probe_abi",0);
    run_fn=xrt_module_export(module,"probe_run",0);make_fn=xrt_module_export(module,"probe_make",0);destroy_fn=xrt_module_export(module,"probe_destroy",0);
}
static uintptr_t make(void){return xrt_call_guest(cpu,make_fn,0,NULL,0);}
static HWND host_window(uintptr_t h){return (HWND)xrt_handle_get((uint32_t)h,XH_WINDOW);}
/* HIMC is stored first in the private bridge record; inspect only in this test host. */
static HIMC host_context(uintptr_t h){void* p=xrt_handle_get((uint32_t)h,XH_IMC);return p?*(HIMC*)p:NULL;}
static uintptr_t query(uintptr_t w,uintptr_t h,DWORD s,DWORD* e,DWORD out[5]) {
    uint32_t r;unsigned i;wr32(window,(uint32_t)w);wr32(context,(uint32_t)h);wr32(seed,s);
    r=xrt_call_guest(cpu,run_fn,0,NULL,0);*e=rd32(error);for(i=0;i<5;i++)out[i]=rd32(abi+4*i);return r;
}
static int destroy(uintptr_t h){wr32(window,(uint32_t)h);return (int)xrt_call_guest(cpu,destroy_fn,0,NULL,0);}
static void finish(void){xrt_report_write(0,"exited");thread_end();}
#include "driver.h"
