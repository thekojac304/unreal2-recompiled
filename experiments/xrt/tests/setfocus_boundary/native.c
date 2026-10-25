#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static HMODULE module;
static DWORD *window,*seed,*error,*abi,*mode,*trigger,*target,*log_n,*log_data,*parent;
static DWORD (*run_fn)(void),(*make_fn)(void),(*read_fn)(void),(*destroy_fn)(void),(*init_fn)(void);
static void thread_begin(void){}
static void thread_end(void){}
static void release_guest(void){}
static void acquire_guest(void){}
static DWORD get(DWORD* p,unsigned i){return p[i];}
static void put(DWORD* p,DWORD v){*p=v;}
static void init(const char* dll){
    module=LoadLibraryA(dll);if(!module)ExitProcess(2);
#define DATA(n,s) n=(DWORD*)GetProcAddress(module,s)
    DATA(window,"probe_window");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");
    DATA(mode,"probe_mode");DATA(trigger,"probe_trigger");DATA(target,"probe_target");
    DATA(log_n,"probe_log_n");DATA(log_data,"probe_log");
    DATA(parent,"probe_parent");
#undef DATA
#define FN(n,s) n=(DWORD(*)(void))GetProcAddress(module,s)
    FN(run_fn,"probe_run");FN(make_fn,"probe_make");FN(read_fn,"probe_read");FN(destroy_fn,"probe_destroy");FN(init_fn,"probe_init");
#undef FN
    if(!init_fn())ExitProcess(3);
}
static uintptr_t call(DWORD(*fn)(void)){return fn();}
static HWND host(uintptr_t h){return (HWND)h;}
static uintptr_t wrong(void){return 0x77777777;}
static void finish(void){}
#include "driver.h"
