"""Owned-only runtime collector composed with the production debugger factory.

No launch API, authorization, policy edit, or genuine activation is provided.
"""
import ctypes as C
from types import MethodType
from pathlib import Path
from common import *
from observer import collect_stopped
from supervisor.observer import construct as production_factory
from supervisor.windows import Context


def construct(out,plan,stream,check_environment):
    core.require(plan.get('owned_fixture') is True,'genuine monitoring activation remains unqualified')
    l=legacy();l.V.EXE=Path(plan['executable']);l.V.EXPECTED=plan['sha256']
    l.S.symbols=lambda:dict(plan['symbols'])
    cap=production_factory(l,out,plan,check_environment,[plan['executable']])
    retained_fatal=cap.hit;cap.out=Path(out);cap.composed_gate_count=0
    def points(self):
        p={self.sym('xrt_fatal'):'fatal_entry',self.sym('xm_failure'):'monitor_failure',
           self.base+plan['stop_rva']:'init_return',self.sym('owned_gate'):'environment_gate'}
        core.require(len(p)==4,'four distinct critical boundaries required')
        return p
    def on_create(self,ev):
        self.log('composed_owned_only',genuine_activation=False,source_sha256=core.sha(Path(__file__)))
        self.log('endpoint_identity_raw',actual=self.mem(self.base+plan['stop_rva'],3).hex(),expected='895f44')
        core.require(self.mem(self.base+plan['stop_rva'],3)==b'\x89\x5f\x44','owned endpoint bytes')
        self.breakpoints=points(self);check_environment('target-created-before-first-resume')
    def update(self,ctx,resume=False):
        addresses=list(points(self));self.breakpoints=points(self)
        for tid,(handle,_) in self.threads.items():
            target=ctx if int(handle)==int(ctx.thread) else Context(handle)
            target.arm(addresses,resume and int(handle)==int(ctx.thread))
            actual=Context(handle)
            dr=[C.c_uint64.from_address(actual.ptr+72+8*i).value for i in range(4)]
            dr7=C.c_uint64.from_address(actual.ptr+112).value
            self.log('composed_all_thread_readback',tid=tid,addresses=addresses,dr=dr,dr7=dr7,host=actual.snapshot())
            core.require(dr==addresses and dr7&0xffff00ff==0x55,'all-thread critical readback')
    def capture(self,tag,ctx,tid):
        self.log('composed_stopped_host',tag=tag,tid=tid,host=ctx.snapshot())
        # Evidence is copied before interpretation and before a retained handler
        # can reject the state. Pending failure bytes survive a broken sink.
        for name,n in [('xm_pending',1856),('xm_committed',8)]:
            if name=='xm_pending':
                from reader import Record
                n=C.sizeof(Record)
            raw=self.mem(self.sym(name),n)
            (self.out/(tag+'-'+name+'.bin')).write_bytes(raw)
        if Path(stream).exists():
            try:return collect_stopped(self,stream,plan['symbols'],self.out/(tag+'-trace'))
            except ValueError as e:self.log('composed_trace_rejected',tag=tag,reason=str(e));raise
        return None
    def hit(self,tag,ctx,tid):
        if tag=='environment_gate':
            self.log('composed_environment_gate',host=ctx.snapshot(),tid=tid)
            check_environment('before-CreateDevice');self.composed_gate_count+=1;return
        if tag=='fatal_entry':
            try:capture(self,tag,ctx,tid)
            finally:retained_fatal(tag,ctx,tid)
        if tag=='monitor_failure':
            try:capture(self,tag,ctx,tid)
            finally:raise core.Rejected('monitor failure captured before continuation')
        core.require(tag=='init_return','unknown composed stop')
        rows,valid=capture(self,tag,ctx,tid)
        self.log('composed_endpoint_cpu_raw',raw=self.mem(ctx.get('rdi'),416).hex())
        core.require(ctx.get('rip')==self.base+plan['stop_rva'] and ctx.get('rbx')&0xffffffff==GUEST,'exact owned endpoint registers')
        core.require(self.mem(ctx.get('rdi')+0x40,4)==GUEST.to_bytes(4,'little'),'verified owned return value')
        core.require(valid['active_invocations']==0 and self.composed_gate_count==1,'pending invocation or absent graphics gate')
        init=[r for r in rows if r.name==b'UGameEngine.Init']
        core.require(len(init)==2 and [r.event for r in init]==[2,3] and init[0].invocation==init[1].invocation,'paired owned Init scope')
        self.log('composed_init_return',instruction_executed=False,raw_pc=self.mem(ctx.get('rdi')+0x44,4).hex(),integrity=valid)
        self.stop_requested=True
    cap.on_create=MethodType(on_create,cap);cap.update=MethodType(update,cap);cap.hit=MethodType(hit,cap)
    return cap
