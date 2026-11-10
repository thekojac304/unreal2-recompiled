"""Owned live debugger executes production evidence-first entry and paired return handlers."""
import pathlib
import shutil
import sys
import types
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
import evidence
import observer
from supervisor import fixture
from supervisor.windows import Context


def run():
    out=O/('paired-debugger-'+str(uuid.uuid4()));out.mkdir()
    helper=load('paired_setres_build_environment',H.parent/'getobject_boundary/phase.py');helper.O=out;env=helper.env()
    cl=pathlib.Path(shutil.which('cl.exe',path=env.get('Path',env.get('PATH'))))
    (out/'icall_fixture.inc').write_text((H/'icall.inc').read_text())
    helper.run([cl.with_name('ml64.exe'),'/nologo','/c','/Fo'+str(out/'pair.obj'),H/'pair_fixture.asm'],'asm',cwd=out,environment=env)
    helper.run([cl,'/nologo','/Od','/Zi','/fp:strict','/D_CRT_SECURE_NO_WARNINGS','/I'+str(RT),'/I'+str(out),
        '/Fo'+str(out/'fixture.obj'),'/Fd'+str(out/'compile.pdb'),'/Fe'+str(out/'fixture.exe'),H/'pair_fixture.c',out/'pair.obj','/link','/DEBUG','/INCREMENTAL:NO'],'build',cwd=out,environment=env)
    plan=read(O/'stop-mapping.json');cases=[]
    for mode in ('initial','lock','bad-width','bad-eax','bad-esp','bad-nonvolatile','bad-return'):
        dest=out/mode;dest.mkdir();sandbox=dest/'sandbox';sandbox.mkdir()
        cap,l=observer.construct(dest,plan,lambda _:None,[])
        cap.allowed_modules=[out/'fixture.exe']
        cap.on_create=types.MethodType(lambda self,ev:setattr(self,'breakpoints',{}),cap)
        cap.update=types.MethodType(lambda self,ctx,resume=False:ctx.arm(list(self.breakpoints),resume),cap)
        def on_debugbreak(self,ev):
            target=read(sandbox/'ready.json');core.require(target['pid']==self.process_obj.pid,'owned fixture pid')
            self.base=target['endpoint']-plan['stop_rva']
            self.sym=lambda name:target[{'xrt_g':'guest_pointer','event_seq':'event_seq','events':'events'}[name]]
            self.breakpoints={target['entry']:'setres_entry',target['endpoint']:'setres_completion_stop'}
            self.profile_index=len(self.profile);self.completed=self.profile.copy()
            self.object_state=lambda:dict(guest=0x60000,host=0x800000,parent=0x801000)
            self.hwnds=lambda:[]
            core.require(self.mem(target['endpoint'],3)==bytes.fromhex(plan['stop_bytes']),'owned exact endpoint bytes')
            for thread,_ in self.threads.values():self.update(Context(thread))
        cap.on_debugbreak=types.MethodType(on_debugbreak,cap)
        error=None
        try:
            with (dest/'stdout.bin').open('xb') as stdout,(dest/'stderr.bin').open('xb') as stderr:
                cap.run([str(out/'fixture.exe'),mode],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,timeout=15)
        except core.Rejected as e:error=str(e)
        core.require(cap.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'paired debugger cleanup/stop failure')
        core.require((mode=='initial')==(error is None),'paired debugger expected outcome')
        core.require(any(r['kind']=='terminated_before_continue' for r in cap.rows),'resumed owned fixture after rejection')
        if mode=='initial':
            e=next(r for r in cap.rows if r['kind']=='setres_entry_raw');r=next(r for r in cap.rows if r['kind']=='initial_setres_return_raw')
            evidence.runtime_pair(read(dest/'runtime-events.json')['events'],e,r)
        else:core.require(any(r['kind']=='setres_entry_raw' for r in cap.rows),'failure raw frame lost')
        row=dict(mode=mode,passed=True,error=error,cleanup=cap.cleanup);save(dest/'result.json',row);cases.append(row)
    save(O/'paired-debugger-validation.json',dict(passed=True,evidence=str(out),cases=cases,production_entry_return_handlers=True,
        runtime_debugger_raw_equality=True,profile_completion_simulated=True,
        scope='Owned CPU/COM fixtures only; full renderer sequence separately controller-tested and retained measured profile stays exact',
        genuine_launches=0,candidate_instructions_executed=0))
    print('7 production-handler live debugger cases PASS; exact raw runtime/CPU/frame pairing and stop before next instruction.',flush=True)


if __name__=='__main__':run()
