#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
typedef DWORD* DATA;
static HMODULE module;static DATA window,seed,error,abi,wide,style,wp,lp,trigger,log_n,log_data;static DWORD(*run_fn)(void),(*make_fn)(void),(*destroy_fn)(void);
static void init(const char* path){module=LoadLibraryA(path);if(!module)ExitProcess(2);
#define GET(n,s) n=(DATA)GetProcAddress(module,s)
    GET(window,"probe_window");    GET(seed,"probe_seed");    GET(error,"probe_error");    GET(abi,"probe_abi");    GET(wide,"probe_wide");    GET(style,"probe_style");    GET(wp,"probe_wp");    GET(lp,"probe_lp");    GET(trigger,"probe_trigger");    GET(log_n,"probe_log_n");    GET(log_data,"probe_log");
#undef GET
run_fn=(DWORD(*)(void))GetProcAddress(module,"probe_run");make_fn=(DWORD(*)(void))GetProcAddress(module,"probe_make");destroy_fn=(DWORD(*)(void))GetProcAddress(module,"probe_destroy");}
static DWORD get(DATA p,unsigned i){return p[i];}
static void put(DATA p,unsigned i,DWORD v){p[i]=v;}
static DWORD address(DATA p){return (DWORD)p;}
static DWORD call(DWORD(*fn)(void)){return fn();}
static void finish(void){}
static DWORD deliver(DWORD h,DWORD w,DWORD l){return (DWORD)SendMessageA((HWND)h,0xae,w,l);}
#include "driver.h"
