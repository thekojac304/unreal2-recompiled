#define xrt_mod_ehprobe xrt_mod_rectprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static CPU* cpu;
static uint32_t rect_arg,style_arg,menu_arg,seed_arg,result_arg,error_arg,abi_arg,run;
static unsigned char* buffer;
static uintptr_t base;
static void init(const char* dll,const char* report) {
    XrtModule* m;
    xrt_report_path=report;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    m=xrt_module_load(dll,&xrt_mod_rectprobe);xrt_module_bind_imports(m);
    hle_msvcr70_init();cpu=&xrt_thread_main(0x100000)->cpu;xrt_baton_acquire();
#define EXPORT(v,n) v=xrt_module_export(m,n,0);if(!v)ExitProcess(2)
    EXPORT(rect_arg,"probe_rect");EXPORT(style_arg,"probe_style");EXPORT(menu_arg,"probe_menu");
    EXPORT(seed_arg,"probe_seed");EXPORT(result_arg,"probe_result");EXPORT(error_arg,"probe_error");
    EXPORT(abi_arg,"probe_abi");EXPORT(run,"probe_run");
#undef EXPORT
    base=0x40000000u;xrt_commit((uint32_t)base,0x3000);buffer=G2H((uint32_t)base);
}
static DWORD invoke(uintptr_t p,DWORD style,DWORD menu,DWORD seed) {
    wr32(rect_arg,(uint32_t)p);wr32(style_arg,style);wr32(menu_arg,menu);wr32(seed_arg,seed);
    xrt_call_guest(cpu,run,0,NULL,0);return 0;
}
static DWORD result(void){return rd32(result_arg);}
static DWORD error(void){return rd32(error_arg);}
static DWORD abi(int i){return rd32(abi_arg+4*i);}
static void protect(unsigned offset,DWORD protection){DWORD old;if(!VirtualProtect(buffer+offset,0x1000,protection,&old))ExitProcess(2);}
static void finish(void){xrt_report_write(0,"exited");xrt_baton_release();}
#include "driver.h"
