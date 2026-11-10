/* Live debugger fixture for production entry/return capture and exact raw event pair. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "xrt.h"
static unsigned char guest[0x80000];uint8_t*xrt_g=guest;
static CPU cpu;
static char event_data[64][448];static char(*events)[448]=event_data;static LONG64 event_seq;
static const char*mode;
typedef struct {const char*name;uint32_t base;} XrtModule;
static XrtModule module={"D3DDrv.dll",0x6960000};
static XrtModule*xrt_module_by_addr(uint32_t t){(void)t;return &module;}
int xrt_is_committed(uint32_t p,size_t n){return p<sizeof(guest)&&n<=sizeof(guest)-p;}
void xrt_event(const char*kind,const char*fmt,...) {
    char data[4096];va_list ap;int n;LONG64 seq=++event_seq;
    va_start(ap,fmt);n=vsnprintf(data,sizeof(data),fmt,ap);va_end(ap);
    if(n<0 || seq>64)exit(5);
    n=snprintf(event_data[seq-1],448,"{\"seq\":%lld,\"thread\":0,\"kind\":\"%s\",%s}",seq,kind,data);
    if(n>=448)exit(6);
}
extern void paired_entry(CPU*);
extern void paired_invoke(CPU*);
extern void paired_return(void);
static void dispatch(CPU*c,uint32_t target,uint32_t site,const char*what) {
    (void)target;(void)site;(void)what;paired_entry(c);
    c->rv=rd32(c->r[ESP]);c->r[ESP]+=24;c->r[EAX]=1;c->pc=0x696f4e9;
    *(uint32_t*)(guest+0x14698)=0x60000;
    if(!strcmp(mode,"bad-eax"))c->r[EAX]=0;
    if(!strcmp(mode,"bad-esp"))c->r[ESP]+=4;
    if(!strcmp(mode,"bad-nonvolatile"))c->r[EBX]++;
    if(!strcmp(mode,"bad-return"))c->rv=0x696d2cd;
}
#include "setres_evidence.inc"
#include "icall_fixture.inc"
int main(int argc,char**argv) {
    FILE*out;uint32_t frame[]={0x11104bf8,0x18000,1540,945,0,32};uint32_t site=0x11104bf5;
    mode=argc>1?argv[1]:"initial";SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    cpu.r[ECX]=0x10000;cpu.r[ESP]=0x58000;cpu.fs_base=0x70000;cpu.pc=site;cpu.fcw=0x27f;
    *(uint32_t*)(guest+0x70004)=0x80000;*(uint32_t*)(guest+0x70008)=0x1000;
    *(uint32_t*)(guest+0x1805c)=0x10000;*(uint32_t*)(guest+0x18074)=1540;*(uint32_t*)(guest+0x18078)=945;
    if(!strcmp(mode,"lock")){frame[0]=0x696d2cd;site=cpu.pc=0x696d2ca;}
    if(!strcmp(mode,"bad-width"))frame[2]=800;
    memcpy(guest+0x58000,frame,24);
    if(fopen_s(&out,"ready.json","w"))return 2;
    fprintf(out,"{\"pid\":%lu,\"entry\":%llu,\"endpoint\":%llu,\"cpu\":%llu,\"guest_pointer\":%llu,\"events\":%llu,\"event_seq\":%llu}",GetCurrentProcessId(),
        (unsigned long long)(uintptr_t)&paired_entry,(unsigned long long)(uintptr_t)&paired_return,
        (unsigned long long)(uintptr_t)&cpu,(unsigned long long)(uintptr_t)&xrt_g,
        (unsigned long long)(uintptr_t)&events,(unsigned long long)(uintptr_t)&event_seq);
    fclose(out);DebugBreak();
    xrt_icall(&cpu,0x696e890,site);paired_invoke(&cpu);
    if(!fopen_s(&out,"FORBIDDEN.txt","w")){fputs("guest-next-instruction executed",out);fclose(out);}
    return 3;
}
