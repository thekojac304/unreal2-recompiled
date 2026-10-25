#define xrt_mod_ehprobe xrt_mod_geticonprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static XrtModule* module;
static CPU* cpu;
static uint32_t window,seed,error,abi,mode,nested,selector,dpi,icons,log_n,log_data;
static uint32_t run_fn,make_fn,destroy_fn,focus_fn;
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static uintptr_t call(uint32_t fn){return xrt_call_guest(cpu,fn,0,NULL,0);}
static void init(const char* dll,unsigned c,const char* report){
    uint32_t fn;xrt_report_path=report;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    module=xrt_module_load(dll,&xrt_mod_geticonprobe);xrt_module_bind_imports(module);hle_msvcr70_init();
    xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;
#define DATA(n,s) n=xrt_module_export(module,s,0)
    DATA(window,"probe_window");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");
    DATA(mode,"probe_mode");DATA(nested,"probe_nested");DATA(selector,"probe_selector");DATA(dpi,"probe_dpi");
    DATA(icons,"probe_icons");DATA(log_n,"probe_log_n");DATA(log_data,"probe_log");
    DATA(run_fn,"probe_run");DATA(make_fn,"probe_make");DATA(destroy_fn,"probe_destroy");DATA(focus_fn,"probe_focus");
    wr32(xrt_module_export(module,"probe_class",0),c);DATA(fn,"probe_init");if(!call(fn))ExitProcess(3);
#undef DATA
}
static HWND window_host(uintptr_t h){return (HWND)xrt_handle_get((uint32_t)h,XH_WINDOW);}
static HICON icon_host(uintptr_t h){
    if(h==get(icons,0))return LoadIconW(NULL,MAKEINTRESOURCEW(32512));
    if(h==get(icons,1))return LoadIconW(NULL,MAKEINTRESOURCEW(32513));
    if(h==get(icons,2))return (HICON)LoadCursorW(NULL,MAKEINTRESOURCEW(32512));
    return NULL;
}
static int valid_icon_token(uintptr_t h){return h>=0xfb000000u && h<0xfb001000u && h%16==0;}
static void finish(void){xrt_report_write(0,"exited");xrt_baton_release();}
#include "driver.h"
