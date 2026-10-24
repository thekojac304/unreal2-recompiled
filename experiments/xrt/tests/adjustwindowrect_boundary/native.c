#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
static DWORD *rect_arg,*style_arg,*menu_arg,*seed_arg,*result_arg,*error_arg,*abi_arg;
static DWORD (*run)(void);
static unsigned char* buffer;
static uintptr_t base;
static void init(const char* dll,const char* report) {
    HMODULE m; (void)report;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
    m=LoadLibraryA(dll);if(!m)ExitProcess(2);
#define EXPORT(v,n) v=(void*)GetProcAddress(m,n);if(!v)ExitProcess(2)
    EXPORT(rect_arg,"probe_rect");EXPORT(style_arg,"probe_style");EXPORT(menu_arg,"probe_menu");
    EXPORT(seed_arg,"probe_seed");EXPORT(result_arg,"probe_result");EXPORT(error_arg,"probe_error");
    EXPORT(abi_arg,"probe_abi");
    run=(DWORD(*)(void))GetProcAddress(m,"probe_run");if(!run)ExitProcess(2);
#undef EXPORT
    buffer=VirtualAlloc(NULL,0x4000,MEM_RESERVE,PAGE_NOACCESS);
    if(!buffer||!VirtualAlloc(buffer,0x3000,MEM_COMMIT,PAGE_READWRITE))ExitProcess(2);
    base=(uintptr_t)buffer;
}
static DWORD invoke(uintptr_t p,DWORD style,DWORD menu,DWORD seed) {
    DWORD exception=0;*rect_arg=(DWORD)p;*style_arg=style;*menu_arg=menu;*seed_arg=seed;
    __try {run();} __except(EXCEPTION_EXECUTE_HANDLER) {exception=GetExceptionCode();}
    return exception;
}
static DWORD result(void){return *result_arg;}
static DWORD error(void){return *error_arg;}
static DWORD abi(int i){return abi_arg[i];}
static void protect(unsigned offset,DWORD protection){DWORD old;if(!VirtualProtect(buffer+offset,0x1000,protection,&old))ExitProcess(2);}
static void finish(void){}
#include "driver.h"
