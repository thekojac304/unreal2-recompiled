/* Owned no-game dispatcher fixture; compiles the exact new include and wrapper. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "xrt.h"
uint8_t*xrt_g;
typedef struct {char name[32];uint32_t base;} XrtModule;
static XrtModule module={"D3DDrv.dll",0x12000000};
static int dispatches,mode;
static unsigned char memory[0x10000];
static XrtModule*xrt_module_by_addr(uint32_t target){(void)target;return &module;}
int xrt_is_committed(uint32_t p,size_t n){return p<sizeof(memory) && n<=sizeof(memory)-p;}
void xrt_event(const char*kind,const char*fmt,...) {
    char data[4096];va_list ap;int n;
    va_start(ap,fmt);n=vsnprintf(data,sizeof(data),fmt,ap);va_end(ap);
    if(n<0 || n+strlen(kind)+32>=448)exit(8);
    printf("{\"kind\":\"%s\",%s}\n",kind,data);
    SetLastError(999); /* evidence logging must not leak this host error */
}
static void dispatch(CPU*c,uint32_t target,uint32_t site,const char*what) {
    (void)target;(void)site;(void)what;dispatches++;
    if(mode==4 && dispatches==1) {
        CPU nested=*c;nested.r[ESP]=0x1100;
        memcpy(memory+0x1100,memory+0x1000,24);
        xrt_icall(&nested,target,0x0696d2ca);
    }
    c->rv=mode==3?0x11104bf8:rd32(c->r[ESP]);
    c->r[ESP]+=24;c->r[EAX]=1;c->pc=0x0696f4e9;
}
#include "setres_evidence.inc"
#include "icall_fixture.inc"
static void hexout(const void*p,unsigned n){const unsigned char*b=p;unsigned i;for(i=0;i<n;i++)printf("%02x",b[i]);}
int main(int argc,char**argv) {
    CPU c,before;uint32_t frame[]={0x11104bf8,0x2000,1540,945,0,32};uint32_t site=0x11104bf5;DWORD error;
    mode=argc>1?atoi(argv[1]):0;xrt_g=memory;memset(&c,0,sizeof(c));
    c.r[ECX]=0x3000;c.r[ESP]=0x1000;c.r[EBX]=0x12345678;c.fcw=0x27f;c.st[0]=38;
    if(mode==1){frame[0]=0x0696d2cd;site=0x0696d2ca;}
    if(mode==2)strcpy_s(module.name,sizeof(module.name),"Other.dll");
    memcpy(memory+0x1000,frame,24);
    if(mode==3)c.r[ESP]=0xfffffff0;
    before=c;SetLastError(87);xrt_icall(&c,module.base+0xe890,site);error=GetLastError();
    if(error!=87 || dispatches!=(mode==4?2:1) || c.r[EAX]!=1 || c.r[EBX]!=before.r[EBX] || c.fcw!=before.fcw || c.st[0]!=38)return 6;
    printf("{\"kind\":\"fixture_expected\",\"mode\":%d,\"last_error\":%lu,\"before\":\"",mode,error);hexout(&before,sizeof(before));
    printf("\",\"after\":\"");hexout(&c,sizeof(c));printf("\",\"frame\":\"");hexout(frame,24);puts("\"}");
    return 0;
}
