#define xrt_mod_ehprobe xrt_mod_aeprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
typedef uint32_t DATA;
static DATA window,seed,error,abi,wide,style,wp,lp,trigger,log_n,log_data,run_fn,make_fn,destroy_fn;static CPU* cpu;
static void init(const char* path){XrtModule*m;xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);m=xrt_module_load(path,&xrt_mod_aeprobe);xrt_module_bind_imports(m);hle_msvcr70_init();xrt_baton_acquire();cpu=&xrt_thread_main(0x100000)->cpu;
#define GET(n,s) n=xrt_module_export(m,s,0)
    GET(window,"probe_window");    GET(seed,"probe_seed");    GET(error,"probe_error");    GET(abi,"probe_abi");    GET(wide,"probe_wide");    GET(style,"probe_style");    GET(wp,"probe_wp");    GET(lp,"probe_lp");    GET(trigger,"probe_trigger");    GET(log_n,"probe_log_n");    GET(log_data,"probe_log");GET(run_fn,"probe_run");GET(make_fn,"probe_make");GET(destroy_fn,"probe_destroy");
#undef GET
}
static DWORD get(DATA p,unsigned i){return rd32(p+4*i);}
static void put(DATA p,unsigned i,DWORD v){wr32(p+4*i,v);}
static DWORD address(DATA p){return p;}
static DWORD call(DATA fn){return (DWORD)xrt_call_guest(cpu,fn,0,NULL,0);}
static void finish(void){xrt_report_write(0,"exited");xrt_baton_release();}
#include "../../runtime/hle_gui.c"
static DWORD deliver(DWORD h,DWORD w,DWORD l){LRESULT r;CPU* saved=callback_cpu;callback_cpu=cpu;r=SendMessageA((HWND)xrt_handle_get(h,XH_WINDOW),0xae,w,l);callback_cpu=saved;return (DWORD)r;}
#include "driver.h"
