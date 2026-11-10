#ifndef XRT_MONITOR_H
#define XRT_MONITOR_H
#include "xrt.h"
/* Opaque addresses are numeric evidence, NEVER permission to dereference.
 * Bytes are admitted only by explicit typed adapters or checked guest ranges. */
enum { XM_OPEN=1, XM_BEGIN=2, XM_END=3, XM_DATA=4, XM_FATAL=5, XM_CLOSE=6,
       XM_RESOURCE=7, XM_GAP=8, XM_ABORT=9 };
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
int xm_enabled(void);
CPU* xm_current_cpu(void);
void xm_mark(const void*cookie);
void xm_forget(const void*cookie);
void xm_restore(CPU*,const void*cookie,unsigned reason);
void xm_unwind(CPU*,unsigned depth,unsigned reason);
/* MASM saves/restores ALL GPRs, flags and complete legacy x87/SSE state. */
void xm_probe(CPU*,const XmRequest*);
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
