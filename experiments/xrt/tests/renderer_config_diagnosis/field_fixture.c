/* Owned raw-field publisher for hardware-debugger observation and failure cleanup. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
static unsigned char cpu[416];static unsigned char*xrt_g;
extern void field_stop(void*);
int main(int argc,char**argv){FILE*out;DWORD old;unsigned i;uint32_t*registers=(uint32_t*)cpu;const char*mode=argc>1?argv[1]:"exact";
    xrt_g=VirtualAlloc(NULL,0x80000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!xrt_g)return 2;
    registers[1]=0x10000;registers[4]=0x58000;registers[17]=0x696f31d;
    *(uint32_t*)(xrt_g+0x58000)=0x696f323;*(uint32_t*)(xrt_g+0x58004)=0x60000;*(uint32_t*)(xrt_g+0x58008)=0x50000;
#include "field_seed.inc"
    *(uint32_t*)(xrt_g+0x14698)=0x60000;*(uint32_t*)(xrt_g+0x1805c)=0x10000;
    if(!strcmp(mode,"unknown")||!strcmp(mode,"multiple"))*(uint32_t*)(xrt_g+0x140d0)=1;
    if(!strcmp(mode,"multiple"))*(uint32_t*)(xrt_g+0x14124)=2;
    if(!strcmp(mode,"invalid"))registers[1]=0;
    if(!strcmp(mode,"unreadable")&&!VirtualProtect(xrt_g+0x14000,0x1000,PAGE_NOACCESS,&old))return 3;
    if(fopen_s(&out,"ready.json","w"))return 4;
    fprintf(out,"{\"pid\":%lu,\"target\":%llu,\"cpu\":%llu,\"guest_pointer\":%llu,\"renderer\":%u}",GetCurrentProcessId(),
        (unsigned long long)(uintptr_t)&field_stop,(unsigned long long)(uintptr_t)cpu,(unsigned long long)(uintptr_t)&xrt_g,registers[1]);
    fclose(out);DebugBreak();field_stop(cpu);
    if(!fopen_s(&out,"FORBIDDEN.txt","w")){fputs("fixture instruction resumed",out);fclose(out);}
    return 7;
}
