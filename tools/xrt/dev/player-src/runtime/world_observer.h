/* Forced include for the unchanged Engine lift only. Direct calls otherwise
 * bypass the loader dispatcher. Preserve history/preemption and checked returns. */
#include "xrt.h"
void xrt_world_enter(CPU*,uint32_t);
void xrt_world_return(CPU*);
#undef XRT_ENTER
#define XRT_ENTER(va) do { c->hist[c->hpos++ & (XRT_HIST - 1)] = (va); xrt_world_enter(c,(va)); if (xrt_preempt_req) xrt_preempt(c); } while (0)
#undef CALL
#undef ICALL
#ifdef XRT_RV_ABI
/* xlift --opt rv: the callee returns its return address instead of storing c->rv; the observer's return check and
 * xrt_world_return (which matches pending world calls by c->rv) get it from the return value. */
#define CALL(fn,nxt,site) do { uint32_t rv__; push32(c,(nxt)); rv__=fn(c); c->rv=rv__; if(rv__!=(nxt))xrt_badret(c,(site),(nxt)); xrt_world_return(c); } while (0)
#define ICALL(t,nxt,site) do { uint32_t t__=(t),rv__; push32(c,(nxt)); rv__=xrt_icall(c,t__,(site)); c->rv=rv__; if(rv__!=(nxt))xrt_badret(c,(site),(nxt)); xrt_world_return(c); } while (0)
#else
#define CALL(fn,nxt,site) do { push32(c,(nxt)); fn(c); if(c->rv!=(nxt))xrt_badret(c,(site),(nxt)); xrt_world_return(c); } while (0)
#define ICALL(t,nxt,site) do { uint32_t t__=(t); push32(c,(nxt)); xrt_icall(c,t__,(site)); if(c->rv!=(nxt))xrt_badret(c,(site),(nxt)); xrt_world_return(c); } while (0)
#endif
#undef ICALLI
#define ICALLI(t,nxt,site) ICALL(t,nxt,site)   /* observed units keep the observer's return check after every call */
