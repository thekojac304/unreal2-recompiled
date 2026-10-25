#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static HMODULE module;
static DWORD *window,*seed,*error,*abi,*mode,*nested,*selector,*dpi,*icons,*log_n,*log_data;
static DWORD (*run_fn)(void),(*make_fn)(void),(*destroy_fn)(void),(*focus_fn)(void);
static DWORD get(DWORD* p,unsigned i){return p[i];}
static void put(DWORD* p,DWORD v){*p=v;}
static void init(const char* dll,unsigned c,const char* report){
    DWORD(*fn)(void);(void)report;module=LoadLibraryA(dll);if(!module)ExitProcess(2);
#define DATA(n,s) n=(DWORD*)GetProcAddress(module,s)
    DATA(window,"probe_window");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");
    DATA(mode,"probe_mode");DATA(nested,"probe_nested");DATA(selector,"probe_selector");DATA(dpi,"probe_dpi");
    DATA(icons,"probe_icons");DATA(log_n,"probe_log_n");DATA(log_data,"probe_log");
#undef DATA
#define FN(n,s) n=(DWORD(*)(void))GetProcAddress(module,s)
    FN(run_fn,"probe_run");FN(make_fn,"probe_make");FN(destroy_fn,"probe_destroy");FN(focus_fn,"probe_focus");
    *(DWORD*)GetProcAddress(module,"probe_class")=c;FN(fn,"probe_init");if(!fn())ExitProcess(3);
#undef FN
}
static uintptr_t call(DWORD(*fn)(void)){return fn();}
static HWND window_host(uintptr_t h){return (HWND)h;}
static HICON icon_host(uintptr_t h){return (HICON)h;}
static int valid_icon_token(uintptr_t h){return h!=0;}
static void finish(void){}
#include "driver.h"
