/* Additional guest TEB and thread-state checks, using the same adapter harness. */
#define main corpus_main
#include "cand.c"
#undef main
int main(void) {
    unsigned i;uint32_t p[3];XrtFn fn;
    xrt_mem_init();xrt_commit(STACK_LO,STACK_HI-STACK_LO);
    thr.cpu.thread=&thr;xrt_cur=&thr;
    thr.teb=xrt_rt_alloc(0x1000,16);thr.cpu.fs_base=thr.teb;
    fn=lookup("tolower");
    for(i=0;i<3;i++) {
        thr.index=i;p[i]=call(lookup("_errno"),0);wr32(p[i],0x1357+i);
        if(i && p[i]==p[i-1])return 1;
    }
    for(i=0;i<CASES;i++) {
        uint32_t x=sample(i);thr.index=i%3;thr.rand_seed=0x76543210;
        wr32(thr.teb+0x34,0x23456789);SetLastError(0x12345678);
        if(call(fn,x)!=(x-65u<26u?x+32u:x))return 2;
        if(rd32(thr.teb+0x34)!=0x23456789||GetLastError()!=0x12345678)return 3;
        if(rd32(p[thr.index])!=0x1357+(unsigned)thr.index||thr.rand_seed!=0x76543210)return 4;
    }
    puts("397314 guest TEB/thread-state cases passed");return 0;
}
