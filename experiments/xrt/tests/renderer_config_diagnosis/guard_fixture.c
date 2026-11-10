/* Owned profile-guard contract: no native D3D operations or game code. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "xrt.h"
typedef struct {uint32_t guest;} D8DeviceObject;
uint8_t*xrt_g;
static unsigned char memory[0x20000];static jmp_buf failure;static unsigned fatal_code;
void xrt_fatal(CPU*c,unsigned code,const char*fmt,...){(void)c;(void)fmt;fatal_code=code;longjmp(failure,1);}
static void d8_device_memory(CPU*c,uint32_t p,unsigned n,int w){(void)w;if(p<0x1000||p>=sizeof(memory)||n>sizeof(memory)-p)xrt_fatal(c,76,"memory");}
static uint32_t guard_read(uint32_t p){if(p==0x697e04c)return 0x19000;return *(uint32_t*)(memory+p);}
#define rd32 guard_read
#include "production_guard.inc"
#undef rd32
int main(void){CPU c;D8DeviceObject obj;unsigned i,j;static const unsigned values[]={32,1,2,64,0};xrt_g=memory;memset(&c,0,sizeof(c));obj.guest=0x4000;
    for(j=0;j<5;j++) {
        memset(memory,0,sizeof(memory));c.pc=0x696f336;c.r[EBP]=0x17000;*(uint32_t*)(memory+0x16fec)=0x10000;
#include "seed_profile.inc"
        *(uint32_t*)(memory+0x140d0)=values[j];*(uint32_t*)(memory+0x14698)=obj.guest;d8_profile_renderer=0;fatal_code=0;
        if(!setjmp(failure))d8_production_profile(&c,&obj,3);
        if((fatal_code==0)!=(values[j]==32))return 4;
        printf("raw=%u accepted=%u code=%u\n",values[j],fatal_code==0,fatal_code);
    }
    return 0;
}
