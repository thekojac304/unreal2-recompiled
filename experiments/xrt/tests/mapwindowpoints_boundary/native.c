#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static DWORD *from,*to,*points,*count,*seed,*result,*error,*abi;
static DWORD(*run_fn)(void);static unsigned char*buffer;static uintptr_t base;
static DWORD get(DWORD*p,unsigned i){return p[i];}
static void put(DWORD*p,DWORD v){*p=v;}
static uintptr_t call(DWORD(*fn)(void)){return fn();}
static void init(const char*dll,const char*report) {
    HMODULE m=LoadLibraryA(dll);(void)report;if(!m)ExitProcess(2);
#define DATA(n,s) n=(DWORD*)GetProcAddress(m,s)
    DATA(from,"probe_from");DATA(to,"probe_to");DATA(points,"probe_points");DATA(count,"probe_count");DATA(seed,"probe_seed");DATA(result,"probe_result");DATA(error,"probe_error");DATA(abi,"probe_abi");
#undef DATA
    run_fn=(DWORD(*)(void))GetProcAddress(m,"probe_run");buffer=VirtualAlloc(NULL,0x3000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);base=(uintptr_t)buffer;if(!buffer)ExitProcess(3);
}
static uintptr_t token(HWND h){return (uintptr_t)h;}
static uintptr_t wrong(void){return 0x77777777;}
static void finish(void){}
#include "driver.h"
