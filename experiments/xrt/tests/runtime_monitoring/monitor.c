#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stddef.h>
#include "xrt_internal.h"
#include "monitor.h"

#define XM_MAGIC 0x31544d58u
#define XM_LIMIT 131072u
#define XM_DEPTH 128u
static HANDLE sink=INVALID_HANDLE_VALUE;
static SRWLOCK lock=SRWLOCK_INIT;
static uint64_t serial, next_invocation;
static uint32_t chain;
static struct {uint64_t host;unsigned guest,generation,iface,refs,bindings;} identities[4608];
static unsigned identity_count;
#ifdef XM_QUALIFICATION
void xm_qualification_break_sink(void){CloseHandle(sink);sink=INVALID_HANDLE_VALUE;}
#endif
static volatile LONG active, initialized;
volatile long xm_failed;
volatile uint64_t xm_committed;
XmRecord xm_pending;
static __declspec(thread) struct { unsigned depth, busy; uint64_t id[XM_DEPTH],parent[XM_DEPTH]; unsigned domain[XM_DEPTH]; const char*name[XM_DEPTH]; } tls;
typedef char cpu_fits[sizeof(CPU)<=416?1:-1];
typedef char fx_aligned[offsetof(XmHost,fx)==144?1:-1];

/* A failed write leaves the complete intended record in debugger-readable
 * xm_pending. No recursion into logging, cleanup, COM or guest execution. */
__declspec(noinline) __declspec(noreturn) void xm_failure(unsigned reason) {
    InterlockedExchange(&xm_failed,(LONG)reason);
    TerminateProcess(GetCurrentProcess(),0xe04d0000u|reason);
    for(;;){}
}
static unsigned crc32(const void *data,unsigned n) {
    const unsigned char*p=data;unsigned crc=~0u,i;
    while(n--){crc^=*p++;for(i=0;i<8;i++)crc=(crc>>1)^(0xedb88320u& (0u-(crc&1)));}
    return ~crc;
}
static int readable(const void*p,size_t n) {
    uintptr_t at=(uintptr_t)p,end=at+n;
    if(!at||end<at)return 0;
    while(at<end){MEMORY_BASIC_INFORMATION m;DWORD prot;uintptr_t next;
        if(!VirtualQuery((void*)at,&m,sizeof m))return 0;
        prot=m.Protect&255;
        if(m.State!=MEM_COMMIT||(m.Protect&(PAGE_GUARD|PAGE_NOACCESS))||
           !(prot==PAGE_READONLY||prot==PAGE_READWRITE||prot==PAGE_WRITECOPY||
             prot==PAGE_EXECUTE_READ||prot==PAGE_EXECUTE_READWRITE||prot==PAGE_EXECUTE_WRITECOPY))return 0;
        next=(uintptr_t)m.BaseAddress+m.RegionSize;if(next<=at)return 0;at=next;
    }return 1;
}
static int copy_guest(void*out,uint32_t address,unsigned size) {
    if(!xrt_g||!address||(uint64_t)address+size>0x100000000ull||!readable(G2H(address),size))return 0;
    __try {memcpy(out,G2H(address),size);} __except(EXCEPTION_EXECUTE_HANDLER){return 0;}
    return 1;
}
int xm_enabled(void){return initialized!=0;}
/* Only xm_probe calls this. Host state restored by assembly on every return. */
void xm_emit(CPU*c,const XmRequest*q,const XmHost*host) {
    DWORD saved=GetLastError(),written;XmRecord r;unsigned i;int bad=0;
    if(!initialized)return;
    if(tls.busy)xm_failure(1);
    tls.busy=1;
    memset(&r,0,sizeof r);r.magic=XM_MAGIC;r.version=1;r.size=sizeof r;
    r.event=q->event;r.domain=q->domain;r.slot=q->slot;r.thread=GetCurrentThreadId();
    r.error=saved;r.result=q->result;r.host=q->host;r.guest=q->guest;
    r.generation=q->generation;r.interface_id=q->interface_id;r.refs=q->refs;r.bindings=q->bindings;
    r.context=*host;
    if(q->count>12||q->blob_size>256)bad=2;
    else {r.count=q->count;r.blob_size=q->blob_size;memcpy(r.values,q->values,q->count*sizeof(XmValue));
        /* The producer supplies a typed local span; invalid spans fail closed. */
        if(q->blob_size){if(!readable(q->blob,q->blob_size))bad=3;
            else {__try {memcpy(r.blob,q->blob,q->blob_size);}__except(EXCEPTION_EXECUTE_HANDLER){bad=3;}}}
    }
    if(q->name){for(i=0;i<sizeof r.name-1 && q->name[i];i++)r.name[i]=q->name[i];if(q->name[i])bad=4;}
    if(c){r.cpu_size=sizeof *c;memcpy(r.cpu,c,sizeof *c);
        if(copy_guest(r.stack,c->r[ESP],128))r.stack_size=128;else r.flags|=1;
        if(!copy_guest(&r.guest_error,c->fs_base+0x34,4))r.flags|=2;
    }
    AcquireSRWLockExclusive(&lock);
    if(q->event==XM_RESOURCE && q->guest){
        for(i=0;i<identity_count;i++)if(identities[i].guest==q->guest && identities[i].generation==q->generation && identities[i].iface==q->interface_id)break;
        if(i==identity_count){if(identity_count==4608)bad=15;else identity_count++;}
        if(!bad){identities[i].host=q->host;identities[i].guest=q->guest;identities[i].generation=q->generation;
            identities[i].iface=q->interface_id;identities[i].refs=q->refs;identities[i].bindings=q->bindings;}
    }
    if(q->domain==XM_NATIVE && q->host){
        unsigned matches=0;
        for(i=0;i<identity_count;i++)if(identities[i].host==q->host && (identities[i].refs||identities[i].bindings)){
            matches++;r.guest=identities[i].guest;r.generation=identities[i].generation;r.refs=identities[i].refs;r.bindings=identities[i].bindings;
            /* Buffer wrapper's canonical vertex type is resolved by registry. */
            if(!r.interface_id || r.interface_id==106)r.interface_id=identities[i].iface;
        }
        if(matches!=1){r.flags|=4;r.guest=0;r.generation=0;}
        if(matches>1)bad=16;
    }
    if(serial>=XM_LIMIT)bad=5;
    if(q->event==XM_BEGIN){
        if(tls.depth>=XM_DEPTH)bad=6;
        else {unsigned d=tls.depth++;tls.parent[d]=d?tls.id[d-1]:0;
            tls.id[d]=++next_invocation;tls.domain[d]=q->domain;tls.name[d]=q->name;InterlockedIncrement(&active);}
    }
    if(tls.depth){r.invocation=tls.id[tls.depth-1];r.parent=tls.parent[tls.depth-1];}
    else {r.invocation=++next_invocation;r.parent=0;}
    r.depth=tls.depth;
    if(q->event==XM_END && (!tls.depth||tls.domain[tls.depth-1]!=q->domain||
       !q->name||!tls.name[tls.depth-1]||strcmp(q->name,tls.name[tls.depth-1])))bad=7;
    if(q->event==XM_CLOSE&&active)bad=8;
    if(bad){r.event=XM_GAP;r.result=bad;}
    r.sequence=++serial;r.previous_crc=chain;r.crc=crc32(&r,offsetof(XmRecord,crc));
    xm_pending=r;MemoryBarrier();
    if(!WriteFile(sink,&r,sizeof r,&written,NULL)||written!=sizeof r||!FlushFileBuffers(sink))xm_failure(9);
    chain=r.crc;xm_committed=r.sequence;
    if(bad)xm_failure(bad);
    if(q->event==XM_END){tls.depth--;InterlockedDecrement(&active);}
    ReleaseSRWLockExclusive(&lock);tls.busy=0;SetLastError(saved);
}
void xm_scope(CPU*c,unsigned event,unsigned domain,const char*name,uint64_t result) {
    XmRequest q={0};q.event=event;q.domain=domain;q.name=name;q.result=result;xm_probe(c,&q);
}
void xm_native(CPU*c,unsigned event,const char*name,uint64_t host,uint64_t result) {
    XmRequest q={0};q.event=event;q.domain=XM_NATIVE;q.name=name;q.host=host;q.result=result;xm_probe(c,&q);
}
void xm_resource(CPU*c,unsigned iface,unsigned guest,unsigned generation,uint64_t host,unsigned refs,unsigned bindings,const char*name) {
    XmRequest q={0};q.event=XM_RESOURCE;q.domain=XM_LIFETIME;q.name=name;q.guest=guest;
    q.generation=generation;q.interface_id=iface;q.host=host;q.refs=refs;q.bindings=bindings;xm_probe(c,&q);
}
void xm_blob(CPU*c,const char*name,const void*trusted,unsigned size) {
    XmRequest q={0};q.event=XM_DATA;q.name=name;q.blob=trusted;q.blob_size=size;xm_probe(c,&q);
}
void xm_span(CPU*c,const char*name,const void*trusted,unsigned size) {
    unsigned off;XmValue v[2]={{XM_U32,4,size},{XM_U32,4,0}};
    if(size>16384){xm_scope(c,XM_GAP,0,"typed span capacity",size);xm_failure(17);}
    for(off=0;off<size;off+=256){unsigned n=size-off;if(n>256)n=256;
        v[1].value=off;xm_values(c,name,2,v);xm_blob(c,name,(const unsigned char*)trusted+off,n);}
}
void xm_values(CPU*c,const char*name,unsigned count,const XmValue*v) {
    XmRequest q={0};q.event=XM_DATA;q.name=name;q.count=count;
    if(count<=12)memcpy(q.values,v,count*sizeof *v);xm_probe(c,&q);
}
void xm_guest(CPU*c,const char*name,unsigned address,unsigned size) {
    DWORD saved=GetLastError();unsigned char bytes[256];XmRequest q={0};
    if(!initialized)return;
    q.event=XM_DATA;q.name=name;q.guest=address;
    if(size>sizeof bytes||!copy_guest(bytes,address,size)){q.event=XM_GAP;q.result=10;}
    else {q.blob=bytes;q.blob_size=size;}
    SetLastError(saved);xm_probe(c,&q);if(q.event==XM_GAP)xm_failure(10);
}
void xm_init(const char*path) {
    DWORD saved=GetLastError();
    if(!path||!*path)xm_failure(11);
    if(InterlockedCompareExchange(&initialized,1,0))xm_failure(12);
    sink=CreateFileA(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_WRITE_THROUGH,NULL);
    if(sink==INVALID_HANDLE_VALUE)xm_failure(13);
    SetLastError(saved);xm_scope(NULL,XM_OPEN,0,"xrt.monitor.v1",0);
}
void xm_close(void) {
    DWORD saved=GetLastError();
    xm_scope(NULL,XM_CLOSE,0,"xrt.monitor.v1",0);
    /* Test/owned orderly shutdown only; genuine bounded termination uses the
     * independently captured committed counter and live pending record. */
    if(!CloseHandle(sink))xm_failure(14);sink=INVALID_HANDLE_VALUE;initialized=0;SetLastError(saved);
}
