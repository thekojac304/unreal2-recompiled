/* Owned non-game CPU/frame publisher. Executes neither candidate nor renderer. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char cpu[416], guest[0x10000];
static unsigned char *guest_base=guest;
extern void owned_entry(void*);
int main(int argc,char**argv) {
    uint32_t *r=(uint32_t*)cpu,*frame=(uint32_t*)(guest+0x1000);
    FILE *out; const char *mode=argc>1?argv[1]:"initial";
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    r[1]=0x3000;r[4]=0x1000;r[17]=0x11104bf5;
    frame[0]=0x11104bf8;frame[1]=0x2000;frame[2]=1540;frame[3]=945;frame[4]=0;frame[5]=32;
    *(uint32_t*)(guest+0x205c)=0x3000;
    *(uint32_t*)(guest+0x2074)=1540;*(uint32_t*)(guest+0x2078)=945;
    if(!strcmp(mode,"lock")){r[17]=0x0696d2ca;frame[0]=0x0696d2cd;}
    if(!strcmp(mode,"bad-return"))frame[0]=0xdeadbeef;
    if(!strcmp(mode,"bad-width"))frame[2]=800;
    if(!strcmp(mode,"bad-height"))frame[3]=600;
    if(!strcmp(mode,"bad-fullscreen"))frame[4]=1;
    if(!strcmp(mode,"bad-depth"))frame[5]=16;
    if(!strcmp(mode,"bad-viewport"))frame[1]=0x2100;
    if(!strcmp(mode,"bad-renderer"))*(uint32_t*)(guest+0x205c)=0x4000;
    if(fopen_s(&out,"ready.json","w"))return 2;
    fprintf(out,"{\"pid\":%lu,\"target\":%llu,\"cpu\":%llu,\"guest_pointer\":%llu,\"frame\":[%u,%u,%u,%u,%u,%u]}",
      GetCurrentProcessId(),(unsigned long long)(uintptr_t)&owned_entry,
      (unsigned long long)(uintptr_t)cpu,(unsigned long long)(uintptr_t)&guest_base,
      frame[0],frame[1],frame[2],frame[3],frame[4],frame[5]);
    fclose(out);DebugBreak();owned_entry(cpu);
    if(!fopen_s(&out,"FORBIDDEN.txt","w")){fputs("entry body executed",out);fclose(out);}
    return 3;
}
