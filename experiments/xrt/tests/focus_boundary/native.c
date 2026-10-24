#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
static HMODULE module;
static DWORD *seed,*error;
static HWND *window;
static HWND (*read_focus)(void),(*make_window)(void);
static int (*is_window)(void),(*destroy_window)(void);
static void thread_begin(void) {}
static void thread_end(void) {}
static void release_guest(void) {}
static void acquire_guest(void) {}
static void init(const char* dll) {
    module=LoadLibraryA(dll);if(!module)ExitProcess(2);
    seed=(DWORD*)GetProcAddress(module,"probe_seed");error=(DWORD*)GetProcAddress(module,"probe_error");
    window=(HWND*)GetProcAddress(module,"probe_window");
    read_focus=(HWND(*)(void))GetProcAddress(module,"probe_read");
    make_window=(HWND(*)(void))GetProcAddress(module,"probe_make");
    is_window=(int(*)(void))GetProcAddress(module,"probe_valid");
    destroy_window=(int(*)(void))GetProcAddress(module,"probe_destroy");
}
static uintptr_t make(void){return (uintptr_t)make_window();}
static HWND host(uintptr_t h){return (HWND)h;}
static uintptr_t query(DWORD s,DWORD* e){HWND h;*seed=s;h=read_focus();*e=*error;return (uintptr_t)h;}
static int valid(uintptr_t h){*window=(HWND)h;return is_window();}
static int destroy(uintptr_t h){*window=(HWND)h;return destroy_window();}
static void finish(void) {}
#include "driver.h"
