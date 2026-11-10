/* Evidence precedes validation, including unreadable stacks. No guest writes. */
#include "perf_counters.h"
static unsigned long long d8_perf_t_api,d8_perf_t_native;
static volatile LONG d8_evidence_serial;
/* Evidence is formatted only when it can still be stored: once the event timeline is full
 * (or under the quiet profile) xrt_event discards it, so encoding it is pure overhead. */
static int d8_evidence_on(void){return !xm_quiet && xrt_event_room();}
static void d8_evidence_blob(LONG id,const char*area,const void*data,unsigned bytes) {
    const BYTE*p=(const BYTE*)data;unsigned off,i,n;char hex[129];
    static const char digits[]="0123456789abcdef";
    if(!d8_evidence_on())return;
    for(off=0;off<bytes;off+=64) {
        n=bytes-off;if(n>64)n=64;
        for(i=0;i<n;i++){hex[2*i]=digits[p[off+i]>>4];hex[2*i+1]=digits[p[off+i]&15];}hex[2*n]=0;
        xrt_event("d3d8_semantic_blob","\"id\":%ld,\"area\":\"%s\",\"offset\":%u,\"size\":%u,\"hex\":\"%s\"",id,area,off,bytes,hex);
    }
}
/* Last region verified readable, valid while no overlapping guest range has been decommitted since
 * (xrt_mem_hint_valid; guest pages are never reprotected): one VirtualQuery per region, not per call. */
static struct {uint64_t lo,hi;long gen;} d8_readable_hint;
static int d8_evidence_readable(uint32_t p,uint32_t size) {
    uint64_t at=p,end=(uint64_t)p+size;long gen=xrt_mem_generation;
    if(!p || end>0x100000000ull)return 0;
    if(at>=d8_readable_hint.lo && end<=d8_readable_hint.hi &&
       xrt_mem_hint_valid(d8_readable_hint.lo,d8_readable_hint.hi,&d8_readable_hint.gen))return 1;
    if(!xrt_is_committed(p,size))return 0;
    while(at<end) {
        MEMORY_BASIC_INFORMATION m;DWORD prot;uint64_t next;
        if(!VirtualQuery(G2H((uint32_t)at),&m,sizeof m))return 0;
        prot=m.Protect&255;
        if(m.State!=MEM_COMMIT || (m.Protect&PAGE_GUARD) ||
           (prot!=PAGE_READONLY && prot!=PAGE_READWRITE && prot!=PAGE_WRITECOPY &&
            prot!=PAGE_EXECUTE_READ && prot!=PAGE_EXECUTE_READWRITE && prot!=PAGE_EXECUTE_WRITECOPY))return 0;
        next=(uint64_t)((BYTE*)m.BaseAddress-xrt_g)+m.RegionSize;if(next<=at)return 0;
        if(p>=(uint64_t)((BYTE*)m.BaseAddress-xrt_g) && end<=next){d8_readable_hint.lo=(uint64_t)((BYTE*)m.BaseAddress-xrt_g);d8_readable_hint.hi=next;d8_readable_hint.gen=gen;}
        at=next;
    }
    return 1;
}
/* Stable debugger rendezvous, without rewriting guest data or API results.
 * Phase 0=raw entry, 1=before native, 2=actual native result, 3=guest return.
 * The separate observer is never installed by the build/preparation scripts. */
__declspec(noinline) static void d8_semantic_checkpoint(CPU*c,unsigned phase,unsigned slot,
        const void*data,unsigned size,unsigned result,unsigned error) {
    DWORD saved;unsigned mxcsr;
    if(!xrt_event_room()){xrt_event_skip();return;}   /* full timeline: counted as dropped, as xrt_event would */
    saved=GetLastError();mxcsr=_mm_getcsr();
    xrt_event("d3d8_checkpoint","\"phase\":%u,\"slot\":%u,\"site\":%u,\"data\":%llu,\"size\":%u,\"result\":%u,\"error\":%u",
        phase,slot,c->pc,(unsigned long long)(uintptr_t)data,size,result,error);
    _mm_setcsr(mxcsr);SetLastError(saved);
}
__declspec(noinline) static LONG d8_api_entry(CPU*c,unsigned slot,unsigned nargs) {
    DWORD error=GetLastError(),mxcsr=_mm_getcsr();LONG id=InterlockedIncrement(&d8_evidence_serial);
    __declspec(align(16)) CONTEXT host;
    int readable;
    d8_perf_t_api=XRT_PERF_T0();xrt_perf.d3d_calls++;if(slot>=70&&slot<=73)xrt_perf.draw_calls++;
    readable=d8_evidence_readable(c->r[ESP],4*(nargs+1));
    if(d8_evidence_on()) {
    RtlCaptureContext(&host);
    xrt_event("d3d8_semantic_entry","\"id\":%ld,\"slot\":%u,\"site\":%u,\"esp\":%u,\"host_error\":%lu,\"guest_error\":%u,\"stack_readable\":%s,\"rendering\":%d,\"device\":%u,\"refs\":%u,\"host\":%llu,\"focus\":%u,\"window\":%u",
       id,slot,c->pc,c->r[ESP],error,xrt_get_last_error(c),readable?"true":"false",d8_rendering,d8_device.guest,d8_device.refs,(unsigned long long)(uintptr_t)d8_device.host,d8_device.focus,d8_device.window);
    d8_evidence_blob(id,"guest_cpu",c,sizeof *c);d8_evidence_blob(id,"host_context",&host,sizeof host);
    if(readable)d8_evidence_blob(id,"arguments",G2H(c->r[ESP]),4*(nargs+1));
    if(d8_evidence_readable(c->r[ESP],128))d8_evidence_blob(id,"stack",G2H(c->r[ESP]),128);
    }
    _mm_setcsr(mxcsr);SetLastError(error);
    d8_semantic_checkpoint(c,0,slot,NULL,0,0,error);
    if(!readable)xrt_fatal(c,76,"SAFETY: D3D8 slot %u unreadable/overflowing argument frame",slot);
    return id;
}
