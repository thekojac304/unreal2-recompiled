#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <xmmintrin.h>
int main(int argc,char**argv) {
    HMODULE backend,probe;DWORD*i,*n,*abi,k;int(__cdecl*fn)(void);int r;
    if(argc!=7)return 2;
    backend=LoadLibraryExA(argv[1],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    probe=LoadLibraryExA(argv[2],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!backend||!probe){printf("load %lu\n",GetLastError());return 2;}
    *(DWORD*)GetProcAddress(probe,"probe_case")=strtoul(argv[3],NULL,0);
    *(DWORD*)GetProcAddress(probe,"probe_arg")=strtoul(argv[4],NULL,0);
    *(DWORD*)GetProcAddress(probe,"probe_seed")=strtoul(argv[5],NULL,0);
    _mm_setcsr(0x3f80);fn=(int(__cdecl*)(void))GetProcAddress(probe,"probe_main");r=fn();
    printf("returned %u log",r);i=(DWORD*)GetProcAddress(probe,"probe_log");n=(DWORD*)GetProcAddress(probe,"probe_log_n");
    for(k=0;k<*n;k++)printf(" %u",i[k]);printf("\nabi");abi=(DWORD*)GetProcAddress(probe,"abi_data");
    for(k=0;k<16;k++)printf(" %u",abi[k]);printf("\nmxcsr %u\n",_mm_getcsr());
    /* The intentional outstanding-reference probe must retain both modules
     * until process teardown. Normal cases have already released their COM refs. */
    if(r==0 && strtoul(argv[3],NULL,0)!=9){FreeLibrary(probe);FreeLibrary(backend);}
    return r;
}
