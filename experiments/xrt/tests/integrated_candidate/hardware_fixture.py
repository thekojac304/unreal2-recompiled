"""Hardware policy for owned non-game probes only; no launch authorization."""
import ctypes as C
from supervisor import core
from supervisor.windows import Context

def hardware(capture,ctx,plan,resume=False):
    hard=capture.base+plan['stop_rva']
    capture.breakpoints[hard]=plan.get('endpoint_tag','inert_init_return')
    addresses=list(capture.breakpoints)
    core.require(hard in addresses and len(addresses)<=4,'permanent endpoint / four-slot budget')
    ctx.arm(addresses,resume)
    actual=Context(ctx.thread)
    dr=[C.c_uint64.from_address(actual.ptr+72+8*i).value for i in range(4)]
    dr7=C.c_uint64.from_address(actual.ptr+112).value
    core.require(dr==addresses+[0]*(4-len(addresses)) and
        dr7&0xffff00ff==sum(1<<(2*i) for i in range(len(addresses))),'live DR readback')
    capture.log('breakpoints_readback',thread_handle=int(ctx.thread),addresses=addresses,dr=dr,dr7=dr7,
        guest_stop='0x1090ed5c',permanent_stop_present=True,inert_candidate=plan.get('inert_candidate',True))
