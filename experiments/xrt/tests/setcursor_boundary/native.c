#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static DWORD *cursor,*seed,*error,*abi,*cursors,*icon;
static DWORD(*run_fn)(void);
static DWORD get(DWORD*p,unsigned i){return p[i];}
static void put(DWORD*p,DWORD v){*p=v;}
static void init(const char*dll,const char*report) {
    HMODULE m=LoadLibraryA(dll);DWORD(*fn)(void);(void)report;if(!m)ExitProcess(2);
#define DATA(n,s) n=(DWORD*)GetProcAddress(m,s)
    DATA(cursor,"probe_cursor");DATA(seed,"probe_seed");DATA(error,"probe_error");DATA(abi,"probe_abi");DATA(cursors,"probe_cursors");DATA(icon,"probe_icon");
#undef DATA
    run_fn=(DWORD(*)(void))GetProcAddress(m,"probe_run");fn=(DWORD(*)(void))GetProcAddress(m,"probe_init");if(!fn())ExitProcess(3);
}
static uintptr_t call(DWORD(*fn)(void)){return fn();}
static int valid_cursor_token(uintptr_t v){return v!=0;}
static void finish(void){}
static void thread_begin(void){}
static void thread_end(void){}
static void release_guest(void){}
static void acquire_guest(void){}
#include "driver.h"
