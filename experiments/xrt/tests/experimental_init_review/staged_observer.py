"""Inactive exact-candidate observer. No launch/authorization/production edit API."""
from pathlib import Path
from types import MethodType
import json,struct
from physical_audit import P,F,O,core,read,save,require
from endpoint import verify_pair,verify_device,verify_transfers,u32,u64
from composition import _construct
from observer import collect_stopped

def install(cap,plan,stream,event_stream):
    retained=cap.hit;out=cap.out
    protocol=plan.get('owned_protocol') is True
    require(not protocol or plan.get('owned_fixture') is True,'protocol test cannot label a genuine candidate')
    def hit(self,tag,ctx,tid):
        if tag=='environment_gate':
            if protocol:return retained(tag,ctx,tid)
            # Full raw trace/host/CPU/frame precede any new check or native body.
            collect_stopped(self,stream,plan['symbols'],out/'graphics-entry-trace')
            raw=self.mem(ctx.get('rcx'),416);save(out/'graphics-entry.json',dict(host=ctx.snapshot(),tid=tid,cpu=raw.hex()))
            require(u64(raw,408)==ctx.get('rcx'),'graphics CPU/thread address')
            require(u32(self.mem(ctx.get('rcx')+424,4),0)==tid,'graphics host thread')
            guest=self.u64(self.sym('xrt_g'));frame=self.mem(guest+u32(raw,16),32)
            (out/'graphics-entry-frame.bin').write_bytes(frame)
            pp=self.mem(guest+u32(frame,24),52);(out/'graphics-entry-presentation.bin').write_bytes(pp)
            require(u32(frame,8)==0 and u32(frame,12)==1 and u32(pp,28)!=0 and u32(frame,20)&2,'windowed adapter-zero HAL/FPU-preserve scope')
            require(self.composed_gate_count==0,'duplicate device gate')
            # Actual tuple/capability/format/HWND/page checks stay in the unchanged
            # candidate runtime. No owned 800x600 tuple is imposed on the game.
            return retained(tag,ctx,tid)
        if tag=='init_return':
            rows,valid=collect_stopped(self,stream,plan['symbols'],out/'acceptance-endpoint-trace')
            raw=self.mem(ctx.get('rdi'),416);(out/'acceptance-endpoint-cpu.bin').write_bytes(raw)
            self.snapshot_events()
            events=read(out/'runtime-events.json')['events']
            require(Path(event_stream).read_bytes()==(out/'runtime-events.raw.bin').read_bytes(),'independent runtime stream/memory disagreement')
            pair=verify_pair(rows,raw,events,tid,ctx.get('rdi'))
            # Retain actual native device state; the trace supplies its real
            # native creation result and guest/native identity without a query.
            if not protocol:
                registry=self.mem(self.sym('d8_device'),280);(out/'acceptance-device-registry.bin').write_bytes(registry)
                verify_device(rows,registry)
            transfers=verify_transfers(rows)
            require(not valid['active_invocations'] and valid['recorded']==valid['durable_through'] and not valid['failed'],'complete flush-confirmed invocation evidence')
            save(out/'experimental-endpoint-review.json',dict(passed=True,pair=pair,integrity=valid,actual_transfers=transfers,strict_compatibility='FAILED_RETAINED',instruction_executed=False))
            result=retained(tag,ctx,tid)
            require(self.stop_requested,'endpoint did not request termination')
            save(out/'hard-stop.json',dict(hit=True,guest_address='0x1090ED5C',instruction_executed=False,owned_protocol=protocol,strict_compatibility='FAILED_RETAINED'))
            return result
        return retained(tag,ctx,tid)
    cap.hit=MethodType(hit,cap)
    return cap

def construct_review(out):
    out.mkdir(exist_ok=False)
    prepared=read(F/'candidate-observer-preparation.json');plan=dict(prepared['plan']);plan['symbols']=dict(plan['symbols'])
    from composed_live import resolve
    # The earlier review-only plan omitted these mandatory capture identities.
    extra=resolve(Path(plan['executable']),['xrt_g','d8_device','events','event_seq'])
    plan['symbols'].update(extra)
    for name,row in extra.items():require(row['rva']>0,'missing candidate evidence symbol '+name)
    cap=_construct(out,plan,out/'monitor.bin',lambda tag:(_ for _ in ()).throw(core.Rejected('owner environment checked only after separate authorization')))
    cap.allowed_modules=[plan['executable'],*read(F/'candidate-identity.json')['dependencies']]
    install(cap,plan,out/'monitor.bin',out/'runtime-stream.raw.bin')
    def refuse(self,*args,**kwargs):raise core.Rejected('inactive experimental review object: no genuine launch authorization')
    cap.run=MethodType(refuse,cap)
    try:cap.run([])
    except core.Rejected as e:rejection=str(e)
    else:raise AssertionError('candidate review object launched')
    require(cap.created==0 and cap.base==0 and not cap.threads and not cap.breakpoints,'candidate activation during construction')
    save(out/'plan.json',plan)
    return dict(passed=True,plan=plan,extra_capture_symbols=extra,run_rejection=rejection,breakpoints_activated=False,launches=0,
        changes='Staged isolated endpoint pairing/runtime stream reconciliation/native state checks; original composition, runtime, supervisor and policy unchanged.')
