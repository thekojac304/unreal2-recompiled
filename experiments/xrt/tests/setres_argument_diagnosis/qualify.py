"""Live debugger tests use owned fixtures exclusively. Never execute the game."""
import ctypes as C
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
from observer import capture_entry,construct
from supervisor.environment import load
from supervisor.fixture import Probe,environment
from supervisor.windows import Context


def run():
    dest=O/('non-game-'+str(uuid.uuid4()));dest.mkdir()
    helper=load('argument_frame_build_environment',W/'experiments/xrt/tests/getobject_boundary/phase.py')
    helper.O=dest;env=helper.env()
    cl=pathlib.Path(shutil.which('cl.exe',path=env.get('Path',env.get('PATH'))))
    commands=[[str(cl.with_name('ml64.exe')),'/nologo','/c','/Fo'+str(dest/'frame.obj'),str(H/'frame_fixture.asm')],
        [str(cl),'/nologo','/Od','/Zi','/fp:strict','/Fo'+str(dest/'fixture.obj'),'/Fd'+str(dest/'compile.pdb'),
         '/Fe'+str(dest/'fixture.exe'),str(H/'frame_fixture.c'),str(dest/'frame.obj'),'/link','/DEBUG','/INCREMENTAL:NO']]
    for i,cmd in enumerate(commands):
        p=subprocess.run(cmd,cwd=dest,env=env,capture_output=True,timeout=60)
        (dest/f'build-{i}.stdout.bin').write_bytes(p.stdout);(dest/f'build-{i}.stderr.bin').write_bytes(p.stderr)
        core.require(p.returncode==0,'fixture build failed: '+p.stdout.decode(errors='replace'))
    save(dest/'build.json',dict(commands=commands,sources={str(p):core.sha(p) for p in (H/'frame_fixture.c',H/'frame_fixture.asm')}))
    results=[]
    for mode in ('initial','lock','bad-return','bad-width','bad-height','bad-fullscreen','bad-depth','bad-viewport','bad-renderer','write-failure'):
        out=dest/mode;out.mkdir();sandbox=out/'sandbox';sandbox.mkdir()
        class FrameProbe(Probe):
            def on_debugbreak(self,ev):
                super().on_debugbreak(ev)
                self.sym=lambda name:self.target['guest_pointer']
                self.u64=lambda p:struct.unpack('<Q',self.mem(p,8))[0]
                self.u32=lambda p:struct.unpack('<I',self.mem(p,4))[0]
                self.words=lambda p,n:list(struct.unpack('<'+'I'*n,self.mem(p,4*n)))
                def cpu_state(p):
                    raw=self.mem(p,416);vals=struct.unpack_from('<18I',raw)
                    return dict(raw=raw.hex(),registers=dict(zip(('eax','ecx','edx','ebx','esp','ebp','esi','edi'),vals[:8])),pc=vals[17])
                self.cpu_state=cpu_state
            def update(self,ctx,resume=False):
                super().update(ctx,resume)
                actual=Context(ctx.thread)
                dr=[C.c_uint64.from_address(actual.ptr+72+8*i).value for i in range(4)]
                core.require(dr==list(self.breakpoints)+[0]*(4-len(self.breakpoints)),'live DR readback')
            def hit(self,tag,ctx,tid):
                core.require(ctx.get('rcx')==self.target['cpu'],'fixture CPU pointer')
                if mode=='write-failure':
                    real_log=self.log
                    def reject_log(kind,**kw):
                        if kind=='setres_entry_raw':raise OSError('injected evidence write failure')
                        real_log(kind,**kw)
                    self.log=reject_log
                capture_entry(self,ctx,tid,'lock' if mode=='lock' else 'initial',expected_viewport=0x2000)
        cap=FrameProbe(out,sandbox,mode);error=None
        try:
            with (out/'stdout.bin').open('xb') as stdout,(out/'stderr.bin').open('xb') as stderr:
                cap.run([str(dest/'fixture.exe'),mode],cwd=sandbox,env=environment(sandbox),stdout=stdout,stderr=stderr,timeout=15)
        except (core.Rejected,OSError) as e:error=str(e)
        core.require(cap.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'fixture resumed or cleanup failed')
        raw_rows=[r for r in cap.rows if r['kind']=='setres_entry_raw']
        if mode!='write-failure':
            core.require(len(raw_rows)==1 and raw_rows[0]['frame']==cap.target['frame'],'persisted frame differs from independently published words')
        core.require((mode in ('initial','lock'))==(error is None),'unexpected fixture result')
        core.require(any(r['kind']=='terminated_before_continue' for r in cap.rows),'live failure resumed')
        row=dict(mode=mode,passed=True,error=error,frame=cap.target['frame'],cleanup=cap.cleanup,genuine_launches=0)
        save(out/'result.json',row);results.append(row)
    # Full retained factory construction remains offline; its game creation hook must reject.
    out=dest/'offline-factory';out.mkdir()
    plan=read(OLD/'stop-mapping.json')
    cap=construct(out,plan,[])
    core.require(cap.created==0 and cap.cpu is None,'construction executed a target')
    try:cap.on_create(None)
    except core.Rejected:pass
    else:raise AssertionError('consumed identity executable')
    save(O/'fixture-validation.json',dict(passed=True,evidence=str(dest),cases=results,live_debugger=True,
         independent_frame_publisher=True,raw_record_before_validation=True,consumed_identity_launch_refused=True,
         genuine_launches=0,renderer_operations=0,candidate_instructions_executed=0))
    print('10 live non-game debugger cases PASS; raw frame persisted before every argument rejection; consumed candidate blocked.',flush=True)


if __name__=='__main__':run()
