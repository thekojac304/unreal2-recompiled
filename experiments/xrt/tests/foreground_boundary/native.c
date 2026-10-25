#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
typedef DWORD* DATA;
static HMODULE module;static DATA pointer,seed,error,abi,rect;static DWORD(*run_fn)(void);
static void init(const char* path){module=LoadLibraryA(path);if(!module)ExitProcess(2);
#define GET(n,s) n=(DATA)GetProcAddress(module,s)
    GET(pointer,"probe_pointer");GET(seed,"probe_seed");GET(error,"probe_error");GET(abi,"probe_abi");GET(rect,"probe_rect");
#undef GET
    run_fn=(DWORD(*)(void))GetProcAddress(module,"probe_run");}
static DWORD get(DATA p,unsigned i){return p[i];}
static void put(DATA p,unsigned i,DWORD v){p[i]=v;}
static DWORD address(DATA p){return (DWORD)p;}
static DWORD run(void){return run_fn();}
static void finish(void){}
static HWND host(DWORD h){return (HWND)h;}
#include "driver.h"
