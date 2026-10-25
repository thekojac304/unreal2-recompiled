#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <imm.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static HMODULE module;
static DWORD *window,*context,*seed,*error,*abi;
static DWORD (*run_fn)(void),(*make_fn)(void),(*destroy_fn)(void);
static void thread_begin(void) {}
static void thread_end(void) {}
static void release_guest(void) {}
static void acquire_guest(void) {}
static void init(const char* dll) {
    module=LoadLibraryA(dll);if(!module)ExitProcess(2);
    window=(DWORD*)GetProcAddress(module,"probe_window");context=(DWORD*)GetProcAddress(module,"probe_context");
    seed=(DWORD*)GetProcAddress(module,"probe_seed");error=(DWORD*)GetProcAddress(module,"probe_error");
    abi=(DWORD*)GetProcAddress(module,"probe_abi");
    run_fn=(DWORD(*)(void))GetProcAddress(module,"probe_run");
    make_fn=(DWORD(*)(void))GetProcAddress(module,"probe_make");destroy_fn=(DWORD(*)(void))GetProcAddress(module,"probe_destroy");
}
static uintptr_t make(void){return make_fn();}
static HWND host_window(uintptr_t h){return (HWND)h;}
static HIMC host_context(uintptr_t h){return (HIMC)h;}
static uintptr_t query(uintptr_t w,uintptr_t h,DWORD s,DWORD* e,DWORD out[5]) {
    DWORD r;*window=(DWORD)w;*context=(DWORD)h;*seed=s;r=run_fn();*e=*error;memcpy(out,abi,20);return r;
}
static int destroy(uintptr_t h){*window=(DWORD)h;return (int)destroy_fn();}
static void finish(void) {}
#include "driver.h"
