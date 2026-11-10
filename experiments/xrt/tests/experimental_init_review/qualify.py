"""Owned protocol live qualification and raw-capture rejection tests only."""
from pathlib import Path
import sys,uuid,shutil,struct
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
from physical_audit import *
from staged_observer import install,construct_review
from endpoint import verify_device,verify_transfers
from common import helper
from composition import construct
from composed_live import resolve
from supervisor import fixture
from supervisor.windows import FilePins
from launch_adapter import compose,prepare

def main():
    O.mkdir(exist_ok=True);out=O/('qualification-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    # Exact runtime objects already verified by the physical package; no game TU.
    b=read(F/'build.json');lineage=read(W/'out/recovery/practical-init-20261031-01/object-lineage.json')
    objects=[Path(b['root'])/r for r in lineage if r.startswith('obj/rt/') and Path(r).name!='xrt_main.obj']+[Path(b['root'])/'obj/msvcr70/pow_sse2.obj']
    prefix=(H.parent/'final_init_review/owned_graphics.c').read_text().split('static void backend_identity',1)[0]
    (out/'host.c').write_text(prefix+(H/'owned_protocol_body.c').read_text())
    # Independent compile-time layout verification; nothing is executed here.
    (out/'layout.c').write_text('#include "xrt_internal.h"\n#include <stddef.h>\n_Static_assert(sizeof(CPU)==416,"CPU");\n_Static_assert(offsetof(CPU,thread)==408,"CPU thread");\n_Static_assert(offsetof(XrtThread,cpu)==0,"CPU first");\n_Static_assert(offsetof(XrtThread,host_tid)==424,"host tid");\n')
    env=h.env()
    h.run(['cl','/nologo','/c','/std:c11','/O2','/Zi','/fp:strict',f'/I{RT}',f'/Fo{out}/layout.obj',out/'layout.c'],'layout',environment=env)
    h.run(['cl','/nologo','/c','/std:c11','/O2','/Zi','/fp:strict',f'/I{RT}',f'/Fo{out}/host.obj',f'/Fd{out}/compile.pdb',out/'host.c'],'owned',environment=env)
    h.run(['ml64','/nologo','/c','/Zi',f'/Fo{out}/stop.obj',H.parent/'integrated_candidate/stop_fixture.asm'],'stop',environment=env)
    exe=out/'owned_protocol.exe'
    h.run(['link','/nologo','/DEBUG','/INCREMENTAL:NO',f'/OUT:{exe}',out/'host.obj',out/'stop.obj',*objects,'winmm.lib','advapi32.lib','ole32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/STACK:0x10000000'],'link',environment=env)
    symbols=resolve(exe,['xrt_fatal','xm_failure','xm_pending','xm_committed','xm_recorded','xm_written','xm_buffer_count','xm_profile','xm_failed','xm_buffer','owned_gate','owned_stop','xrt_g','d8_device','events','event_seq'])
    plan=dict(owned_fixture=True,owned_protocol=True,executable=str(exe),sha256=digest(exe),symbols=symbols,stop_rva=symbols['owned_stop']['rva'],stop_bytes='895f44',environment_gate_symbol='owned_gate')
    results=[]
    for case in ('success','tick','nonvolatile','missing-return'):
        d=out/case;d.mkdir();sb=d/'sandbox';sb.mkdir();stream=d/'monitor.bin';events=d/'runtime-stream.raw.bin'
        cap=compose(None,d,plan,lambda tag:None,[str(exe)])
        env=fixture.environment(sb);env['XRT_MONITOR_STREAM']=str(stream);env['XRT_EVENT_STREAM']=str(events);error=None
        with FilePins() as pins:
            pins.pin(exe,digest(exe));pins.pin(exe.with_suffix('.pdb'),digest(exe.with_suffix('.pdb')))
            try:
                with (d/'stdout.txt').open('xb') as stdout,(d/'stderr.txt').open('xb') as stderr:
                    cap.run([str(exe),case],cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=60)
            except (ValueError,RuntimeError) as e:error=str(e)
        require(cap.cleanup['passed'] and any(r['kind']=='terminated_before_continue' for r in cap.rows),'contained before continuation')
        require((case=='success' and error is None and cap.terminated_while_stopped) or (case!='success' and error),'protocol outcome '+case+str(error))
        results.append(dict(case=case,error=error,cleanup=cap.cleanup,evidence=str(d)))
    q=Path(read(F/'physical-consumed.json')['evidence']);records,_=saved_capture(q/'init_return-trace');registry=(q/'device-registry.bin').read_bytes()
    device=verify_device(records,registry)
    transfers=verify_transfers(records)
    # Exercise the newly staged genuine graphics-entry branch on the sealed
    # owned predevice host, stopping before its first instruction/body.
    from types import MethodType
    pre=out/'graphics-entry';pre.mkdir();sb=pre/'sandbox';sb.mkdir();stream=pre/'monitor.bin'
    physical_plan=read(F/'physical-plan.json')['plan']
    cap=compose(None,pre,physical_plan,lambda tag:None,[physical_plan['executable']]);installed=cap.hit
    def prehit(self,tag,ctx,tid):
        installed(tag,ctx,tid)
        if tag=='environment_gate':self.stop_requested=True
    cap.hit=MethodType(prehit,cap);env=fixture.environment(sb);env['XRT_MONITOR_STREAM']=str(stream)
    with FilePins() as pins:
        pins.pin(Path(physical_plan['executable']),physical_plan['sha256'])
        with (pre/'stdout.txt').open('xb') as stdout,(pre/'stderr.txt').open('xb') as stderr:
            cap.run([physical_plan['executable'],'--owned-predevice'],cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=60)
    require(cap.cleanup['passed'] and cap.terminated_while_stopped,'graphics entry containment')
    require(not any(Path(r.get('path','')).name.lower() in ('d3d8.dll','d3d9.dll') for r in cap.rows if r['kind']=='module_identity'),'graphics backend executed in predevice test')
    negative=[]
    for field in ('guest_error','result'):
        mutated=[Record.from_buffer_copy(bytes(r)) for r in records]
        outer=next(r for r in mutated if r.event==3 and r.name==b'D8.CreateDevice')
        setattr(outer,field,getattr(outer,field)^0x80)
        try:verify_transfers(mutated)
        except ValueError as e:negative.append(dict(field=field,rejection=str(e)))
        else:raise AssertionError('altered actual native transfer accepted')
    for offset in (0,4,24):
        bad=bytearray(registry)
        if offset==4:bad[4:8]=b'\0'*4
        else:bad[offset]^=0x80
        try:verify_device(records,bad)
        except ValueError as e:negative.append(dict(offset=offset,rejection=str(e)))
        else:raise AssertionError('native registry substitution accepted')
    src=q/'init_return-trace'
    for name in ('counter','tail','pending'):
        d=out/('capture-'+name);shutil.copytree(src,d)
        p=d/({'counter':'xm_recorded.bin','tail':'tail.bin','pending':'pending.bin'}[name]);raw=bytearray(p.read_bytes())
        if name=='tail':raw+=b'\0'
        else:raw[0]^=1
        p.write_bytes(raw)
        try:saved_capture(d)
        except ValueError as e:negative.append(dict(kind=name,rejection=str(e)))
        else:raise AssertionError('invalid stopped capture accepted')
    inactive=construct_review(out/'inactive-candidate')
    _,launch_source,launch_diff=prepare()
    (out/'isolated-launch-profile.txt').write_bytes(launch_source.encode('utf-8'))
    (out/'launch-profile.diff').write_bytes(launch_diff.encode('utf-8'))
    for token in ('A.check_writable(sandbox)','shutil.copytree(A.source(), sandbox, dirs_exist_ok=True)',
                  'with R.CaseLock("level"), R.CaseLock("graphics-client-session")',
                  'desktop.owner.restore_and_check(input_before)','A.check_run_inputs(before, after)',
                  'capture.run(cmd, cwd=sandbox / "System"','timeout=request["timeout_seconds"], stop=stop)',
                  '"runtime stream gaps"','"stream/stopped-memory discrepancy"'):
        require(token in launch_source,'retained launch protection missing: '+token)
    from owner_run import authorize
    auth_tests=[]
    for typed,console in (('wrong',True),('expected',False)):
        try:authorize(typed,'expected',console)
        except ValueError as e:auth_tests.append(str(e))
        else:raise AssertionError('unauthorized console predicate accepted')
    authorize('expected','expected',True) # Predicate only; no authorization receipt or launch.
    test_ledger=core.Ledger(out/'test-only-consumption.jsonl')
    batch=dict(id=str(uuid.uuid4()),genuine_limit=1);request=dict(id=str(uuid.uuid4()));fake=dict(kind='genuine',sha256='0'*64)
    test_ledger.claim(request,fake,batch);ledger_rejections=[]
    for sha in ('0'*64,'1'*64):
        try:test_ledger.claim(dict(id=str(uuid.uuid4())),dict(kind='genuine',sha256=sha),batch)
        except core.Rejected as e:ledger_rejections.append(str(e))
        else:raise AssertionError('one-shot consumption bypass')
    require(len(test_ledger.rows)==1,'failed claim appended ledger')
    save(O/'observer-qualification.json',dict(passed=True,root=str(out),cases=results,physical_device_validation=device,actual_native_transfers=transfers,graphics_entry=dict(passed=True,evidence=str(pre),cleanup=cap.cleanup,backend_loaded=False),negative_mutations=negative,
        inactive_candidate=inactive,launch_profile_source_sha256=digest(out/'isolated-launch-profile.txt'),authorization_predicate_rejections=auth_tests,test_only_consumption_rejections=ledger_rejections,
        sources=core.tree(H),runtime=core.tree(RT),candidate_executed=False,graphics_executed=False,production_changed=False,
        scope='Live exact-runtime-object owned Init protocol; actual saved physical device state; inactive candidate PE/PDB-bound construction. No genuine instruction executed.'))
    print('Owned endpoint/event pairing, no-tick/nonvolatile negatives, saved physical device and capture rejection checks PASS',flush=True)

if __name__=='__main__':main()
