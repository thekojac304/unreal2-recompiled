/* Forced include for the unchanged Engine lift only. Direct calls otherwise
 * bypass the loader dispatcher. Preserve history/preemption and checked returns. */
#include "xrt.h"
void xrt_world_enter(CPU*,uint32_t);
void xrt_world_return(CPU*);
#undef XRT_ENTER
#define XRT_ENTER(va) do { c->hist[c->hpos++ & (XRT_HIST - 1)] = (va); xrt_world_enter(c,(va)); if (xrt_preempt_req) xrt_preempt(c); } while (0)
#undef CALL
#define CALL(fn,nxt,site) do { push32(c,(nxt)); fn(c); if(c->rv!=(nxt))xrt_badret(c,(site),(nxt)); xrt_world_return(c); } while (0)
#undef ICALL
#define ICALL(t,nxt,site) do { uint32_t t__=(t); push32(c,(nxt)); xrt_icall(c,t__,(site)); if(c->rv!=(nxt))xrt_badret(c,(site),(nxt)); xrt_world_return(c); } while (0)
