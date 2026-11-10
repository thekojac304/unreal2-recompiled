#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
static DWORD *cfg_word,*cfg_mask,*cfg_enable,*cfg_mips,*cfg_filter;
static DWORD(*run_fn)(void);
static DWORD get(DWORD*p,unsigned i){return p[i];}
static void put(DWORD*p,DWORD v){*p=v;}
static void call_probe(void){run_fn();}
#include "driver.h"
int main(int argc,char**argv){HMODULE m;if(argc!=2)return 2;m=LoadLibraryA(argv[1]);if(!m)return 3;
#define DATA(n) n=(DWORD*)GetProcAddress(m,#n);if(!n)return 4
    DATA(cfg_word);DATA(cfg_mask);DATA(cfg_enable);DATA(cfg_mips);DATA(cfg_filter);
    run_fn=(DWORD(*)(void))GetProcAddress(m,"probe_run");if(!run_fn)return 5;return drive();}
