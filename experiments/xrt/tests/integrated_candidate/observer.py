"""Prepared read-only Init-return handler. No launcher, installation or grant.

The active supervisor is untouched. A future authorized observer may compose
this handler with its existing file pins, process Job, fatal handling and event
stream. This module never changes a breakpoint or resumes a process itself.
"""
import struct
from common import core,GUEST
def capture_endpoint(capture,context,mapping,*,host_address=None):
    stop=capture.base+mapping['stop_rva'] if host_address is None else host_address
    registers=context.snapshot()
    pointer=context.get(mapping['stop_registers']['cpu'])
    raw=capture.mem(pointer,416)
    # Save observations before assertions. Failure must remain stopped.
    capture.log('resource_init_endpoint_raw',host=registers,cpu_address=pointer,
                raw_cpu=raw.hex(),guest_stop=GUEST,instruction_executed=False)
    core.require(context.get('rip')==stop,'Init endpoint host instruction')
    core.require(capture.mem(stop,len(bytes.fromhex(mapping['stop_bytes'])))==bytes.fromhex(mapping['stop_bytes']),'Init endpoint bytes')
    core.require(context.get('rbx')&0xffffffff==GUEST,'Init endpoint guest boundary register')
    core.require(len(raw)==416 and struct.unpack_from('<I',raw,64)[0]==GUEST,'checked Init return CPU.rv')
    capture.stop_requested=True
    capture.log('resource_init_endpoint_stop',guest_stop=GUEST,instruction_executed=False,
                runtime_milestone_pairing_required=True,game_frame_verified=False)
    return raw
