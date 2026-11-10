/* Non-game control-flow oracle: exact generated cache body, owned dependencies. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "xrt.h"
uint8_t* xrt_g;
volatile long xrt_preempt_req;
void xrt_preempt(CPU*c){(void)c;ExitProcess(90);}
static unsigned char xrt_hits_D3DDrv[1024];
void xrt_badret(CPU*c,uint32_t s,uint32_t e){(void)c;fprintf(stderr,"badret %x %x",s,e);ExitProcess(91);}
static void f_6961020(CPU*c){
    uint32_t s=c->r[ESP];memcpy(G2H(rd32(s+4)),G2H(rd32(s+8)),rd32(s+12));RET(0);
}
static void f_697cda8(CPU*c){
    double value=*ST(c,0);
    if(value!=-.5)ExitProcess(92);
    c->r[EAX]=0;c->r[EDX]=0;fpop(c);RET(0);
}
void xrt_icall(CPU*c,uint32_t target,uint32_t site){
    uint32_t s=c->r[ESP];unsigned slot=target,n;
    switch(slot){case 50:case 37:case 61:case 85:n=3;break;case 63:case 83:n=4;break;case 76:n=2;break;default:ExitProcess(93);}
    printf("{\"slot\":%u,\"site\":%u,\"a\":%u,\"b\":%u,\"c\":%u}\n",slot,site,rd32(s+8),n>=3&&slot!=37?rd32(s+12):0,n>=4?rd32(s+16):0);
    c->r[EAX]=0;RET(n*4);
}
#include "cache_generated.inc"
int main(void){
    CPU c={0};FILE*f;unsigned i;size_t bytes;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    xrt_g=VirtualAlloc(NULL,0x7000000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!xrt_g)return 2;
    if(fopen_s(&f,"original-data.bin","rb"))return 3;
    bytes=fread(G2H(0x6960000),1,0x50000,f);fclose(f);if(bytes<0x20000)return 4;
    wr32(0x697e04c,0x60000);wr32(0x60000,0);
    wr32(0x20000,0x10000);wr32(0x10000+0x4698,0x30000);wr32(0x30000,0x40000);
    wr32(0x10000+0x41c8,8);wr32(0x10000+0x41f0,16);wr32(0x10000+0x4650,1);wr32(0x10000+0x412c,0xbf000000);
    for(i=0;i<97;i++)wr32(0x40000+i*4,i);
    c.fcw=0x27f;c.r[ESP]=0x58000;c.r[ECX]=0x20000;
    wr32(0x58000,0x696f4c2);wr32(0x58004,0x10000);
    f_6977800(&c);
    if(c.rv!=0x696f4c2||c.r[ESP]!=0x58008)return 5;
    VirtualFree(xrt_g,0,MEM_RELEASE);return 0;
}
