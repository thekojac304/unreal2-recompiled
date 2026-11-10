#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <xmmintrin.h>
#include "xrt.h"
uint8_t*xrt_g;
static void fail(void){ExitProcess(91);}
void xrt_badret(CPU*c,uint32_t site,uint32_t expected){(void)c;(void)site;(void)expected;fail();}
void xrt_icall(CPU*c,uint32_t target,uint32_t site){
    uint32_t sp=c->r[ESP];(void)target;
    if(site==0x696cadb)fpush(c,pow(rdf64(sp+4),rdf64(sp+12)));
    else if(site==0x696cb1f)c->r[EAX]=(int32_t)floor((double)rdf32(sp+4)+0.5);
    else fail();
    RET(0);
}
#include "gamma_generated.inc"
#if defined(_M_IX86)
extern void gamma_native(void*,void*);
#endif
int main(int argc,char**argv){
    const float cases[][3]={{1,.5f,.5f},{2.2f,.5f,.5f},{.5f,.5f,.5f},{1,0,1},{1,1,1}};
    unsigned i,j;BYTE*arena;WORD*ramp;CPU c;
#if defined(_M_IX86)
    HMODULE mathlib;void*fn;DWORD old;__declspec(align(16))BYTE saved[512];WORD cw=0x027f;
    if(argc!=2)return 2;mathlib=LoadLibraryExA(argv[1],NULL,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);if(!mathlib)return 3;
    arena=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!arena)return 4;
    memcpy(arena,native_bytes,4096);
    for(i=0;i<sizeof relocations/sizeof relocations[0];i++)*(DWORD*)(arena+relocations[i][0])=(DWORD)(uintptr_t)(arena+relocations[i][1]);
    fn=GetProcAddress(mathlib,"floor");memcpy(arena+900,&fn,4);if(!fn)return 5;
    fn=GetProcAddress(mathlib,"_CIpow");memcpy(arena+912,&fn,4);if(!fn)return 6;
    if(!VirtualProtect(arena,4096,PAGE_EXECUTE_READ,&old))return 7;FlushInstructionCache(GetCurrentProcess(),arena,4096);
    xrt_g=VirtualAlloc(NULL,0x40000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!xrt_g)return 8;
    for(j=0;j<5;j++){
        memset(G2H(0x7000),0,0x2000);wrf32(0x8000-0x24,cases[j][0]);wrf32(0x8000-0x1c,cases[j][1]);wrf32(0x8000+8,cases[j][2]);
        _fxsave(saved);
        __asm fninit
        __asm fldcw cw
        gamma_native(arena+1024,G2H(0x8000));
        _fxrstor(saved);ramp=(WORD*)G2H(0x8000-0x628);
        printf("{\"case\":%u,\"ramp\":\"",j);for(i=0;i<1536;i++)printf("%02x",((BYTE*)ramp)[i]);puts("\"}");
    }
    FreeLibrary(mathlib);VirtualFree(arena,0,MEM_RELEASE);
#else
    (void)argc;(void)argv;arena=NULL;xrt_g=VirtualAlloc(NULL,0x40000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!xrt_g)return 8;
    for(i=0;i<sizeof constants/sizeof constants[0];i++)memcpy(G2H(constants[i].address),constants[i].bytes,constants[i].size);
    for(j=0;j<5;j++){
        memset(&c,0,sizeof c);memset(G2H(0x7000),0,0x2000);c.fcw=0x027f;c.r[EBP]=0x8000;c.r[ESP]=0x6000;
        wrf32(0x8000-0x24,cases[j][0]);wrf32(0x8000-0x1c,cases[j][1]);wrf32(0x8000+8,cases[j][2]);
        generated_gamma(&c);if(c.r[ESP]!=0x6000||c.top!=0)return 9;ramp=(WORD*)G2H(0x8000-0x628);
        printf("{\"case\":%u,\"ramp\":\"",j);for(i=0;i<1536;i++)printf("%02x",((BYTE*)ramp)[i]);puts("\"}");
    }
#endif
    VirtualFree(xrt_g,0,MEM_RELEASE);return 0;
}
