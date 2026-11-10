#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <oleacc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static HMODULE module;
static DWORD *mode,*log_n,*log_data;
static UINT_PTR (*make_fn)(void);
static BOOL (*destroy_fn)(void);
static DWORD get(DWORD* p,unsigned i){return p[i];}
static void put(DWORD* p,DWORD v){*p=v;}
static HWND make(const char* path,const char* report,int ansi) {
    (void)report;module=LoadLibraryA(path);if(!module)exit(2);
    mode=(DWORD*)GetProcAddress(module,"probe_mode");log_n=(DWORD*)GetProcAddress(module,"probe_log_n");log_data=(DWORD*)GetProcAddress(module,"probe_log");
    *(DWORD*)GetProcAddress(module,"probe_ansi")=ansi;
    make_fn=(UINT_PTR(*)(void))GetProcAddress(module,"probe_make");destroy_fn=(BOOL(*)(void))GetProcAddress(module,"probe_destroy");
    return (HWND)make_fn();
}
static BOOL destroy(HWND h){(void)h;return destroy_fn();}
static void finish(void){
#ifdef _M_IX86
    DWORD count=*(DWORD*)GetProcAddress(module,"probe_abi_count"),failed=*(DWORD*)GetProcAddress(module,"probe_abi_fail");
    fprintf(stderr,"x86 callback ABI count=%lu failures=%lu\n",count,failed);if(!count||failed)exit(9);
#endif
}
#include "driver.h"
