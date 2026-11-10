#ifndef XRT_MONITOR_H
#define XRT_MONITOR_H
#include "xrt.h"
/* Opaque addresses are numeric evidence, NEVER permission to dereference.
 * Bytes are admitted only by explicit typed adapters or checked guest ranges. */
enum { XM_OPEN=1, XM_BEGIN=2, XM_END=3, XM_DATA=4, XM_FATAL=5, XM_CLOSE=6,
       XM_RESOURCE=7, XM_GAP=8, XM_ABORT=9, XM_CHECKPOINT=10, XM_OMITTED=11 };
enum { XM_ADAPTER=1, XM_NATIVE=2, XM_CALLBACK=3, XM_LIFETIME=4, XM_SUPPORT=5 };
enum { XM_U32=1, XM_I32=2, XM_OPAQUE=3, XM_GUEST_ADDRESS=4, XM_HOST_BYTES=5 };
typedef struct XmValue { uint32_t type, bytes; uint64_t value; } XmValue;
typedef struct XmRequest {
    uint32_t event, domain, slot, count;
    const char *name;
    uint64_t result;
    uint32_t guest, generation, interface_id, refs, bindings;
    uint32_t blob_size;
    const void *blob; /* trusted typed local span, max 256, never inferred */
    uint64_t host; /* opaque identity only */
    XmValue values[12];
} XmRequest;
typedef struct XmHost { uint64_t gpr[16], rip, flags; unsigned char fx[512]; } XmHost;
/* Stable little-endian format, fixed-size records. Raw CPU.thread is opaque. */
typedef struct XmRecord {
    uint32_t magic, version, size, event;
    uint64_t sequence, invocation, parent;
    uint32_t thread, depth, domain, slot;
    uint32_t error, guest_error, cpu_size, stack_size;
    uint32_t guest, generation, interface_id, refs, bindings, count, blob_size, flags;
    uint64_t result, host;
    char name[128];
    unsigned char cpu[416], stack[128];
    XmHost context;
    XmValue values[12];
    unsigned char blob[256];
    uint32_t previous_crc, crc;
} XmRecord;
void xm_init(const char *path);
void xm_close(void);
void xm_checkpoint(CPU*,const char*name);
extern volatile uint64_t xm_recorded, xm_written, xm_flushes;
extern volatile unsigned xm_buffer_count, xm_profile;
extern unsigned xm_quiet; /* developer quiet profile: no routine records */
extern XmRecord xm_buffer[4096];
int xm_enabled(void);
CPU* xm_current_cpu(void);
unsigned xm_depth(void);
void xm_mark(const void*cookie);
void xm_forget(const void*cookie);
void xm_restore(CPU*,const void*cookie,unsigned reason);
void xm_unwind(CPU*,unsigned depth,unsigned reason);
/* MASM saves/restores ALL GPRs, flags and complete legacy x87/SSE state. */
void xm_probe(CPU*,const XmRequest*);
/* Quiet profile: routine records are dropped before the probe saves any host state. */
/* (round 4: the routine-event test is shared with the xm_scope/xm_native/xm_resource fast paths in monitor.c, which
 * return before building a request; the first-character test only skips the strcmp, same answer) */
static __inline int xm_quiet_routine(unsigned event,const char*name) {
    return xm_quiet && (event==XM_BEGIN||event==XM_END||event==XM_DATA||event==XM_RESOURCE||event==XM_OMITTED) &&
           !(name && name[0]=='U' && !strcmp(name,"UGameEngine.Init"));
}
static __inline int xm_quiet_drop(const XmRequest*q) { return xm_quiet_routine(q->event,q->name); }
static __inline void xm_probe_gated(CPU*c,const XmRequest*q) { if(!xm_quiet_drop(q))xm_probe(c,q); }
#define xm_probe xm_probe_gated
void xm_scope(CPU*,unsigned event,unsigned domain,const char*name,uint64_t result);
void xm_native(CPU*,unsigned event,const char*name,uint64_t host,uint64_t result);
void xm_resource(CPU*,unsigned iface,unsigned guest,unsigned generation,
                 uint64_t host,unsigned refs,unsigned bindings,const char*name);
void xm_blob(CPU*,const char*name,const void*trusted,unsigned size);
void xm_span(CPU*,const char*name,const void*trusted,unsigned size);
void xm_guest(CPU*,const char*name,unsigned address,unsigned size);
void xm_values(CPU*,const char*name,unsigned count,const XmValue*);
__declspec(noreturn) void xm_failure(unsigned reason);
extern volatile long xm_failed;
extern volatile uint64_t xm_committed;
extern XmRecord xm_pending;
#endif
