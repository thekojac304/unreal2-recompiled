#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
static DWORD *probe_from,*probe_to,*probe_attach,*probe_seed,*probe_result,*probe_error,*probe_abi;
static DWORD (*run_fn)(void);
static DWORD get(DWORD* p,unsigned i){return p[i];}
static void put(DWORD* p,DWORD v){*p=v;}
static void call_probe(void){run_fn();}
#include "driver.h"
int main(int argc,char** argv) {
    HMODULE m;if(argc!=3)return 2;
    m=LoadLibraryA(argv[1]);if(!m)return 2;
#define DATA(n) n=(DWORD*)GetProcAddress(m,#n);if(!n)return 2
    DATA(probe_from);DATA(probe_to);DATA(probe_attach);DATA(probe_seed);DATA(probe_result);DATA(probe_error);DATA(probe_abi);
#undef DATA
    run_fn=(DWORD(*)(void))GetProcAddress(m,"probe_run");if(!run_fn)return 2;
    return drive(argv[2]);
}
