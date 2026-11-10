#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <xmmintrin.h>
int main(int argc,char**argv){
 HMODULE backend,probe;DWORD*i,*n,k;unsigned j;int(__cdecl*fn)(void);int r;const char*names[]={"abi_clear","abi_present"};
 if(argc!=7)return 2;backend=LoadLibraryExA(argv[1],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);probe=LoadLibraryExA(argv[2],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!backend||!probe)return 3;
 *(DWORD*)GetProcAddress(probe,"probe_case")=strtoul(argv[3],NULL,0);*(DWORD*)GetProcAddress(probe,"probe_arg")=strtoul(argv[4],NULL,0);*(DWORD*)GetProcAddress(probe,"probe_seed")=strtoul(argv[5],NULL,0);_mm_setcsr(0x3f80);fn=(int(__cdecl*)(void))GetProcAddress(probe,"probe_main");r=fn();
 printf("returned %u log",r);i=(DWORD*)GetProcAddress(probe,"probe_log");n=(DWORD*)GetProcAddress(probe,"probe_log_n");for(k=0;k<*n;k++)printf(" %u",i[k]);
 for(j=0;j<2;j++){printf("\n%s",names[j]);i=(DWORD*)GetProcAddress(probe,names[j]);for(k=0;k<16;k++)printf(" %u",i[k]);}printf("\nmxcsr %u\n",_mm_getcsr());FreeLibrary(probe);FreeLibrary(backend);printf("unload %u %u\n",GetModuleHandleW(L"d3d8.dll")!=NULL,GetModuleHandleW(L"d3d9.dll")!=NULL);return r;
}
