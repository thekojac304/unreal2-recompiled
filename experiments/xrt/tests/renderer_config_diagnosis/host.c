#define xrt_mod_ehprobe xrt_mod_cfgprobe
#define main unused_probe_main
#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"
#undef main
static CPU*cpu;static uint32_t cfg_word,cfg_mask,cfg_enable,cfg_mips,cfg_filter,run_fn;
static DWORD get(uint32_t p,unsigned i){return rd32(p+4*i);}
static void put(uint32_t p,DWORD v){wr32(p,v);}
static void call_probe(void){xrt_call_guest(cpu,run_fn,0,NULL,0);}
#include "driver.h"
int main(int argc,char**argv){XrtModule*m;int result;if(argc!=3)return 2;
    xrt_report_path=argv[2];xrt_events_init();xrt_mem_init();xrt_diag_init(NULL);
    m=xrt_module_load(argv[1],&xrt_mod_cfgprobe);xrt_module_bind_imports(m);cpu=&xrt_thread_main(0x100000)->cpu;xrt_baton_acquire();
#define DATA(n) n=xrt_module_export(m,#n,0);if(!n)return 4
    DATA(cfg_word);DATA(cfg_mask);DATA(cfg_enable);DATA(cfg_mips);DATA(cfg_filter);
    run_fn=xrt_module_export(m,"probe_run",0);if(!run_fn)return 5;
    result=drive();xrt_report_write(result,"exited");return result;}
