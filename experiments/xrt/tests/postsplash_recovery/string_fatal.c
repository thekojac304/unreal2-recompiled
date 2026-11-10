/* Non-game live debugger target. Fatal body must never execute. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include "../../runtime/xrt.h"
uint8_t* xrt_g;
static CPU cpu;
static char text[160]="fixture transport failure 100% %x (Win32 123)";
static const char* forbidden;
__declspec(noinline) void xrt_fatal(CPU*c,unsigned code,const char*format,...) {
    FILE*f=fopen(forbidden,"wb");if(f){fputs("fatal body executed",f);fclose(f);}ExitProcess(code);(void)c;(void)format;
}
int main(int argc,char**argv){
    if(argc!=3)return 2;forbidden=argv[1];
    xrt_g=VirtualAlloc(NULL,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!xrt_g)return 3;
    cpu.r[ESP]=0x11000;cpu.fs_base=0x10000;cpu.pc=0x12345678;cpu.fcw=0x027f;
    wr32(0x10004,0x12000);wr32(0x10008,0x11000);
    xrt_fatal(&cpu,76,"%s",!strcmp(argv[2],"unreadable")?(const char*)1:text);
    return 4;
}
