"""Live hardware qualification on project-owned non-game code only."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import ctypes as C
import json
import subprocess
import uuid
from common import *
from hardware_fixture import hardware
from supervisor import fixture, observer_checks
from supervisor.windows import Context,FilePins


EXE,SHA,PDB=identity()
RVA=read(O/'stop-mapping.json')['stop_rva']

def live():
    out=O/('non-game-'+str(uuid.uuid4()));out.mkdir()
    build=out/'build';build.mkdir()
    helper=load('setres_fixture_build_environment',W/'experiments/xrt/tests/getobject_boundary/phase.py')
    helper.O=out;env=helper.env()
    cl=pathlib.Path(next(k for k in read(PRIOR/'build.json')['toolchain'] if k.endswith('cl.exe')))
    commands=[[str(cl.with_name('ml64.exe')),'/nologo','/c','/Zi','/Fo'+str(build/'stop.obj'),str(H/'stop_fixture.asm')],
        [str(cl),'/nologo','/Od','/Zi','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',
         '/DCANDIDATE_PATH="'+EXE.as_posix()+'"','/Fo'+str(build/'fixture.obj'),'/Fd'+str(build/'compiler.pdb'),
         '/Fe'+str(build/'fixture.exe'),str(H/'stop_fixture.c'),str(build/'stop.obj'),'/link','/DEBUG','/INCREMENTAL:NO']]
    for i,cmd in enumerate(commands):
        p=subprocess.run(cmd,cwd=build,env=env,capture_output=True,timeout=60)
        (out/f'build-{i}.stdout.bin').write_bytes(p.stdout);(out/f'build-{i}.stderr.bin').write_bytes(p.stderr)
        core.require(p.returncode==0,'non-game stop fixture build')
    save(out/'build.json',dict(commands=commands,source={str(p):core.sha(p) for p in (H/'stop_fixture.c',H/'stop_fixture.asm')},outputs=core.tree(build)))
    results=[]
    for case in ('stop','four-slots','slot-overflow','observer-failure','wrong-candidate-bytes'):
        dest=out/case;dest.mkdir();sandbox=dest/'sandbox';sandbox.mkdir()
        class Probe(fixture.Probe):
            def __init__(self):
                super().__init__(dest,sandbox,case);self.mapped=False;self.seen_threads=set()
            def on_create(self,ev):self.breakpoints={}
            def on_debugbreak(self,ev):
                self.target=core.read(sandbox/'ready.json')
                core.require(self.target['pid']==self.process_obj.pid,'fixture pid')
                self.base=self.target['candidate_base']
                core.require(self.mem(self.base+RVA,3)==(b'\x89\x5f\x44' if case!='wrong-candidate-bytes' else b'\x90'*3),'mapped candidate byte identity')
                core.require(self.mem(self.target['sentinel'],3)==b'\x89\x5f\x44','owned exact instruction')
                self.breakpoints={self.target['sentinel']:'owned-sentinel'};self.mapped=True
                if case in ('four-slots','slot-overflow'):
                    for offset in ([3,6] if case=='four-slots' else [3,6,9]):self.breakpoints[self.base+RVA+offset]='inert-extra-slot'
                for thread,_ in self.threads.values():self.update(Context(thread))
                self.log('candidate_mapped_no_execute',candidate_base=self.base,stop=self.base+RVA,bytes='895f44',sha256=SHA,pdb_sha256=PDB,entrypoint_called=False)
            def update(self,ctx,resume=False):
                if not self.mapped:ctx.arm([],resume);return
                hardware(self,ctx,dict(stop_rva=RVA),resume)
                self.seen_threads.add(int(ctx.thread))
            def hit(self,tag,ctx,tid):
                core.require(tag=='owned-sentinel' and ctx.get('rip')==self.target['sentinel'],'non-game sentinel tag')
                core.require(ctx.get('rdi')==self.target['cpu'] and ctx.get('rbx')&0xffffffff==GUEST,'exact target register semantics')
                core.require(self.mem(self.target['cpu']+0x44,4)==b'\x55'*4,'P write occurred')
                core.require(self.mem(self.base+RVA,3)==b'\x89\x5f\x44','mapped candidate changed')
                self.log('owned_stop_before_exact_instruction',host=ctx.snapshot(),candidate_instruction_executed=False,sentinel_unchanged=True)
                if case=='observer-failure':raise RuntimeError('intentional observer failure at pending hardware stop')
                self.stop_requested=True
        probe=Probe();error=None
        with FilePins() as pins:
            pins.pin(EXE,SHA);pins.pin(EXE.with_suffix('.pdb'),PDB)
            try:
                with (dest/'stdout.bin').open('xb') as stdout,(dest/'stderr.bin').open('xb') as stderr:
                    probe.run([str(build/'fixture.exe')],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,timeout=15)
            except RuntimeError as e:error=str(e)
            except core.Rejected as e:error=str(e)
        core.require(probe.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'stop fixture containment')
        core.require((case in ('stop','four-slots') and probe.terminated_while_stopped) or (case not in ('stop','four-slots') and error),'expected fixture outcome')
        if case not in ('wrong-candidate-bytes','slot-overflow'):core.require(len(probe.seen_threads)>=2,'main and newly created thread live readback')
        core.require(any(r['kind']=='terminated_before_continue' for r in probe.rows),'failure resumed live fixture')
        row=dict(case=case,passed=True,error=error,hardware_threads=len(probe.seen_threads),cleanup=probe.cleanup,genuine_launches=0,candidate_instructions_executed=0)
        save(dest/'result.json',row);results.append(row)
    # Exercise the entire retained factory/dispatch/fatal/module paths too.
    retained=observer_checks.qualify(out)
    result=dict(passed=True,evidence=str(out),cases=results,retained_observer=retained,genuine_launches=0,
        exact_candidate_mapped_with_SEC_IMAGE_NO_EXECUTE=True,actual_candidate_endpoint_hit=False,
        scope='Live DR readback at exact inert candidate RVA plus terminate-before-identical-owned-instruction; candidate never executed')
    save(out/'result.json',result);save(O/'debugger-validation.json',result)
    print('NON-GAME EXACT CANDIDATE MAPPING / HARDWARE READBACK / OWNED STOP / FAILURE CLEANUP PASS',flush=True)


if __name__=='__main__':live()
