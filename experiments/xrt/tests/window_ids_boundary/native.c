#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static DWORD *window,*output,*seed,*error,*abi,*pid,*tid;
static DWORD(*run_fn)(void),(*make_fn)(void),(*destroy_fn)(void);
static unsigned char*buffer;static uintptr_t base;
static DWORD get(DWORD*p,unsigned i){return p[i];}
static void put(DWORD*p,DWORD v){*p=v;}
static uintptr_t call(DWORD(*fn)(void)){return fn();}
static void init(const char*dll,const char*report) {
    HMODULE m=LoadLibraryA(dll);(void)report;if(!m)ExitProcess(2);
#define DATA(n,s) n=(DWORD*)GetProcAddress(m,s)
    DATA(window,"probe_window");DATA(output,"probe_output");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");DATA(pid,"probe_pid");DATA(tid,"probe_tid");
#undef DATA
#define FN(n,s) n=(DWORD(*)(void))GetProcAddress(m,s)
    FN(run_fn,"probe_run");FN(make_fn,"probe_make");FN(destroy_fn,"probe_destroy");
#undef FN
    buffer=VirtualAlloc(NULL,0x3000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);base=(uintptr_t)buffer;if(!buffer)ExitProcess(3);
}
static uintptr_t wrong(void){return 0x77777777;}
static void finish(void){}
static void thread_begin(void){}
static void thread_end(void){}
static void release_guest(void){}
static void acquire_guest(void){}
#include "driver.h"
