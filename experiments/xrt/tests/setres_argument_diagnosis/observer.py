"""Fresh first-entry diagnostic continuation; always stops before SetRes executes.

No launcher, queue submission, authorization, ledger mutation, or candidate retry.
The existing permanent 0696D2CD endpoint is retained at its original RVA.
"""
import struct
from types import MethodType
from common import *

RVA=0x5a7f813
CALLERS={'initial':(0x11104bf5,INITIAL), 'lock':(0x0696d2ca,PRIMARY)}


def capture_entry(cap, ctx, tid, expected_caller='initial', expected_size=(1540,945), expected_viewport=None):
    """Persist raw state BEFORE assertions, including on negative fixture paths."""
    cap.cpu=ctx.get('rcx')
    cap.guest_base=cap.u64(cap.sym('xrt_g'))
    raw_cpu=cap.mem(cap.cpu,416)
    cs=cap.cpu_state(cap.cpu)
    esp=cs['registers']['esp'];renderer=cs['registers']['ecx']
    raw=cap.mem(cap.guest_base+esp,24)
    frame=list(struct.unpack('<6I',raw))
    # This must be the first durable record, even when the frame is rejected.
    cap.log('setres_entry_raw',thread=tid,host=ctx.snapshot(),cpu=cs,cpu_raw=raw_cpu.hex(),
            guest_stack_address=esp,frame_raw=raw.hex(),frame=frame,
            argument_names=['return','viewport','width','height','fullscreen','color_bits'],
            renderer_this=renderer,expected_caller=expected_caller,guest_body_executed=False)
    site,ret=CALLERS[expected_caller]
    checks=dict(caller_pc=cs['pc']==site,return_address=frame[0]==ret,
                viewport=bool(frame[1]) and (expected_viewport is None or frame[1]==expected_viewport),
                width=frame[2]==expected_size[0],height=frame[3]==expected_size[1],
                fullscreen=frame[4]==0,color_bits=frame[5]==32,renderer_this=bool(renderer))
    # Preserve source values too; failures reading sources retain the raw frame above.
    sources=dict(renderer_force_fullscreen=cap.u32(cap.guest_base+renderer+0x70),
                 renderer_device=cap.u32(cap.guest_base+renderer+0x4698),
                 viewport_size=cap.words(cap.guest_base+frame[1]+0x74,2),
                 viewport_renderer=cap.u32(cap.guest_base+frame[1]+0x5c))
    checks['viewport_renderer']=sources['viewport_renderer']==renderer
    checks['no_existing_device']=sources['renderer_device']==0
    checks['no_forced_fullscreen']=sources['renderer_force_fullscreen']==0
    cap.log('setres_entry_validation',checks=checks,sources=sources,passed=all(checks.values()))
    core.require(all(checks.values()),'SetRes entry: '+', '.join(k for k,v in checks.items() if not v))
    cap.setres_entry=dict(cpu=cs,frame=frame,host=ctx.snapshot(),sources=sources)
    cap.stop_requested=True
    cap.log('setres_entry_diagnostic_stop',guest_body_executed=False,native_device_operation_allowed=False)
    return cap.setres_entry


def construct(out, plan, dependencies):
    """Offline construction for review; caller must supply a separately qualified fresh identity later."""
    from supervisor.environment import load
    from supervisor.observer import construct as retained
    legacy=load('argument_diagnosis_legacy',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    legacy.V.EXE,legacy.V.EXPECTED=EXE,SHA
    cap=retained(legacy,out,plan,lambda _:None,[EXE,*dependencies])
    old_hit=cap.hit

    def on_create(self,ev):
        # Deliberately fail closed for this consumed identity. No game may be run by this preparation.
        raise core.Rejected('preparation only: consumed candidate cannot be retried; fresh candidate identity required')

    def hit(self,tag,ctx,tid):
        if tag=='setres_entry':return capture_entry(self,ctx,tid)
        if tag in ('bridge_entry','permanent_stop'):
            self.log('unexpected_diagnostic_boundary',tag=tag,host=ctx.snapshot())
            raise core.Rejected('first-entry diagnostic must stop before renderer/device operations')
        return old_hit(tag,ctx,tid)

    cap.on_create=MethodType(on_create,cap)
    cap.hit=MethodType(hit,cap)
    return cap
