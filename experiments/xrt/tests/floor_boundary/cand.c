/* Actual runtime adapters, CPU helpers and guest memory. Unused dependencies fail. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include "xrt_internal.h"
#define STACK_LO 0x08000000u
#define STACK_HI 0x08100000u
#define RET_SENTINEL 0x0badc0deu
__declspec(thread) XrtThread* xrt_cur;
char xrt_sandbox_root[520];
uint32_t xrt_cmdline_a,xrt_cmdline_w;
static XrtThread thr;
void xrt_log(const char* fmt,...) { (void)fmt; }
XRT_NORETURN void xrt_fatal(CPU* c,int code,const char* fmt,...) {
    va_list ap; (void)c; fprintf(stderr,"xrt_fatal (%d): ",code);
    va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(code);
}
uint32_t xrt_hle_data(const char* dll,const char* name) {
    xrt_fatal(NULL,76,"unused data import %s!%s",dll,name);
}
XRT_NORETURN void xrt_process_exit(CPU* c,uint32_t code) { xrt_fatal(c,76,"unused exit %u",code); }
uint32_t xrt_call_guest(CPU* c,uint32_t va,int n,const uint32_t* args,int stdcall) {
    (void)n; (void)args; (void)stdcall; xrt_fatal(c,76,"unused guest call %08x",va);
}
static XrtFn lookup(const char* name) {
    const XrtHle* h;
    for(h=xrt_hle_msvcr70;h->name;h++) if(!strcmp(h->name,name) && h->fn) return h->fn;
    xrt_fatal(NULL,2,"no adapter %s",name);
}
static uint32_t call_adapter(XrtFn fn,const uint32_t* args,unsigned n) {
    CPU* c=&thr.cpu; uint32_t sp=STACK_HI-256-4*(n+1); unsigned i;
    const int saved[]={EBX,EBP,ESI,EDI};
    c->r[ESP]=sp; c->rv=0; wr32(sp,RET_SENTINEL);
    for(i=0;i<n;i++) wr32(sp+4+4*i,args[i]);
    for(i=0;i<4;i++) c->r[saved[i]]=0x12345670+i;
    fn(c);
    if(c->rv!=RET_SENTINEL || c->r[ESP]!=sp+4) xrt_fatal(c,4,"cdecl return/ESP mismatch");
    for(i=0;i<4;i++) if(c->r[saved[i]]!=0x12345670+i) xrt_fatal(c,4,"callee-saved register mismatch");
    return c->r[EAX];
}
static uint64_t bits_of(double x) { uint64_t b; memcpy(&b,&x,8); return b; }
int main(int argc,char** argv) {
    FILE *in,*out; uint64_t bits,result; unsigned cw,sw,depth,i; uint32_t args[2],errp;
    XrtFn fn,ep; CPU* c=&thr.cpu;
    if(argc!=3 && argc!=4) return 2;
    xrt_mem_init(); xrt_commit(STACK_LO,STACK_HI-STACK_LO);
    thr.cpu.thread=&thr; xrt_cur=&thr;
    fn=lookup(argc==4?argv[3]:"floor"); ep=lookup("_errno");
    errp=call_adapter(ep,NULL,0);
    in=fopen(argv[1],"r"); out=fopen(argv[2],"w"); if(!in||!out)return 3;
    while(fscanf(in,"%llx %x %x %u",&bits,&cw,&sw,&depth)==4) {
        if(depth>4) return 4;
        c->top=0; xrt_fldcw(c,(uint16_t)cw); c->fsw=(uint16_t)sw;
        for(i=0;i<depth;i++) fpush(c,123.25);
        args[0]=(uint32_t)bits; args[1]=(uint32_t)(bits>>32);
        wr32(errp,0x5a5a);
        call_adapter(fn,args,2);
        result=bits_of(*ST(c,0));
        fprintf(out,"%016llx %04x %04x %u %016llx %04x %04x %d",bits,cw,sw,depth,result,c->fcw,fstatus(c),(int)rd32(errp));
        fpop(c);
        for(i=0;i<depth;i++) { fprintf(out," %016llx",bits_of(*ST(c,0))); fpop(c); }
        if(c->top!=0) return 5;
        fputc('\n',out);
    }
    fclose(in); return fclose(out)!=0;
}
