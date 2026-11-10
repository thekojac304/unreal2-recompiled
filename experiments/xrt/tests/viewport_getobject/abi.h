#include <stddef.h>
typedef struct Args {void* fn;HWND h;UINT msg;WPARAM wp;LPARAM lp;} Args;
typedef __declspec(align(16)) struct ABI {DWORD result,delta;uint64_t regs[8];BYTE xmm[160],pad[8],pre[512],post[512];} ABI;
extern void window_abi(Args*,ABI*);
typedef char abi_layout[offsetof(ABI,pre)==240 && offsetof(ABI,post)==752?1:-1];
static LRESULT abi_call(void* fn,HWND h,WPARAM wp,LPARAM lp) {
    Args a;ABI b;unsigned i;DWORD error;int regs=1,xmm=1,fpu,mx;
    static const uint64_t expected[]={0x1111111112345678ull,0x2222222223456789ull,0x333333333456789aull,0x44444444456789abull,
        0x5555555556789abcull,0x666666666789abcdull,0x77777777789abcdeull,0x8888888889abcdefull};
    a.fn=fn;a.h=h;a.msg=WM_GETOBJECT;a.wp=wp;a.lp=lp;memset(&b,0,sizeof b);
#ifdef xrt_mod_ehprobe
    {CPU saved=*cpu;
#endif
    window_abi(&a,&b);error=GetLastError();
#ifdef xrt_mod_ehprobe
    if(memcmp(&saved,cpu,sizeof saved))xrt_fatal(cpu,XRT_EXIT_BADRET,"fixture: suspended CPU changed");
    xrt_event("fixture_suspended_cpu","\"passed\":true");}
#endif
#ifdef _M_IX86
    for(i=0;i<4;i++)if(b.regs[i]!=(DWORD)expected[i])regs=0;
#else
    for(i=0;i<8;i++)if(b.regs[i]!=expected[i])regs=0;
    for(i=0;i<40;i++) {
        static const DWORD seed[]={0x12345678,0x23456789,0x3456789a,0x456789ab};
        if(((DWORD*)b.xmm)[i]!=seed[i%4])xmm=0;
    }
#endif
    fpu=!memcmp(b.pre,b.post,5);
    for(i=0;i<8;i++)if(memcmp(b.pre+32+i*16,b.post+32+i*16,10))fpu=0;
    mx=!memcmp(b.pre+24,b.post+24,4);
    fprintf(stderr,"host ABI delta=%lu gpr=%d xmm=%d x87=%d mxcsr=%d\n",b.delta,regs,xmm,fpu,mx);
    if(b.delta||!regs||!xmm||!fpu||!mx)exit(9);
    SetLastError(error);return (LRESULT)(LONG)b.result;
}
