/* Actual runtime import table, CPU and guest memory; no test-only tolower. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"
#include "corpus.h"
#define STACK_LO 0x08000000u
#define STACK_HI 0x08100000u
#define RET_SENTINEL 0x0badc0deu
__declspec(thread) XrtThread* xrt_cur;
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a,xrt_cmdline_w;
static XrtThread thr;
void xrt_log(const char* fmt,...) { (void)fmt; }
XRT_NORETURN void xrt_fatal(CPU*c,int code,const char*fmt,...) {
    va_list ap;(void)c;va_start(ap,fmt);vfprintf(stderr,fmt,ap);va_end(ap);exit(code);
}
uint32_t xrt_hle_data(const char*dll,const char*name) {xrt_fatal(NULL,76,"unused data %s!%s",dll,name);}
XRT_NORETURN void xrt_process_exit(CPU*c,uint32_t code) {xrt_fatal(c,76,"unused exit %u",code);}
uint32_t xrt_call_guest(CPU*c,uint32_t va,int n,const uint32_t*args,int stdcall) {
    (void)n;(void)args;(void)stdcall;xrt_fatal(c,76,"unused guest %x",va);
}
static XrtFn lookup(const char*name) {
    const XrtHle*h;for(h=xrt_hle_msvcr70;h->name;h++)if(!strcmp(h->name,name)&&h->fn)return h->fn;
    xrt_fatal(NULL,75,"msvcr70.dll!%s has no host implementation; non-C locale/MBCS configuration unsupported",name);
}
static uint32_t call(XrtFn fn,uint32_t x) {
    CPU*c=&thr.cpu;uint32_t sp=STACK_HI-256;
    c->r[ESP]=sp;wr32(sp,RET_SENTINEL);wr32(sp+4,x);fn(c);
    if(c->rv!=RET_SENTINEL||c->r[ESP]!=sp+4)xrt_fatal(c,4,"cdecl mismatch");return c->r[EAX];
}
int main(int argc,char**argv) {
    FILE*out;unsigned i,j;uint32_t err,x,r;XrtFn fn;
    const int saved[]={EBX,EBP,ESI,EDI};
    if(argc!=2 && argc!=3)return 2;
    xrt_mem_init();xrt_commit(STACK_LO,STACK_HI-STACK_LO);thr.cpu.thread=&thr;xrt_cur=&thr;
    if(argc==3 && strcmp(argv[2],"--sweep")){lookup(argv[2]);return 9;}
    fn=lookup("tolower");err=call(lookup("_errno"),0);
    if(argc==3) {
        uint64_t differences=0;x=0;
        do {r=call(fn,x);if(r!=(x-65u<26u?x+32u:x))differences++;}while(++x);
        printf("sweep 4294967296 differences %llu\n",differences);return differences!=0;
    }
    out=fopen(argv[1],"w");if(!out)return 3;
    for(i=0;i<CASES;i++) {
        x=sample(i);wr32(err,0x5a5a);SetLastError(0x12345678);
        for(j=0;j<4;j++)thr.cpu.r[saved[j]]=0x12345670+j;
        r=call(fn,x);
        for(j=0;j<4;j++)if(thr.cpu.r[saved[j]]!=0x12345670+j)return 4;
        fprintf(out,"%08x %08x %08x %08x %08lx 1\n",x,r,0,rd32(err),GetLastError());
    }
    /* Runtime per-thread errno identity and preservation across switching. */
    for(i=1;i<=2;i++) {uint32_t p;thr.index=i;p=call(lookup("_errno"),0);if(p==err||rd32(p))return 5;wr32(p,0x1357+i);call(fn,'A');if(rd32(p)!=0x1357+i)return 6;}
    thr.index=0;if(call(lookup("_errno"),0)!=err||rd32(err)!=0x5a5a)return 7;
    return fclose(out)!=0;
}
