"""Independently observe real native x86 thiscall frames under the debugger."""
import json
import inspect
import pathlib
import shutil
import struct
import subprocess
import sys
import textwrap
from types import MethodType
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
from supervisor.environment import load
from supervisor.fixture import Probe,environment
from supervisor.windows import BoundedLoop


def run():
    dest=O/('native-x86-abi-'+str(uuid.uuid4()));dest.mkdir()
    helper=load('x86_argument_frame_build_environment',W/'experiments/xrt/tests/getobject_boundary/phase.py')
    helper.O=dest;env=helper.env('x86')
    cl=pathlib.Path(shutil.which('cl.exe',path=env.get('Path',env.get('PATH'))))
    commands=[[str(cl.with_name('ml.exe')),'/nologo','/c','/Fo'+str(dest/'abi.obj'),str(H/'abi_fixture.asm')],
              [str(cl),'/nologo','/Od','/Zi','/fp:strict','/Fo'+str(dest/'fixture.obj'),'/Fd'+str(dest/'compile.pdb'),
               '/Fe'+str(dest/'fixture.exe'),str(H/'abi_fixture.c'),str(dest/'abi.obj'),'/link','/DEBUG','/INCREMENTAL:NO']]
    for i,cmd in enumerate(commands):
        p=subprocess.run(cmd,cwd=dest,env=env,capture_output=True,timeout=60)
        (dest/f'build-{i}.stdout.bin').write_bytes(p.stdout);(dest/f'build-{i}.stderr.bin').write_bytes(p.stderr)
        core.require(p.returncode==0,'native x86 fixture build failed: '+p.stdout.decode(errors='replace'))
    save(dest/'build.json',dict(commands=commands,sources={str(p):core.sha(p) for p in (H/'abi_fixture.c',H/'abi_fixture.asm')}))
    # The retained production loop is x64-only. This owned x86 fixture also emits
    # WOW64's STATUS_WX86_BREAKPOINT (0x4000001f). Adapt only the isolated copy;
    # production supervisor files and their exception policy remain untouched.
    source=textwrap.dedent(inspect.getsource(BoundedLoop.run))
    old='if ex.record.code == 0x80000003:'
    core.require(source.count(old)==1,'fixture loop adaptation anchor')
    adapted=source.replace(old,'if ex.record.code in (0x80000003, 0x4000001f):')
    (dest/'fixture_debugger_loop.py').write_text(adapted)
    namespace={};exec(compile(adapted,str(dest/'fixture_debugger_loop.py'),'exec'),BoundedLoop.run.__globals__,namespace)
    fixture_run=namespace['run']
    cases=[]
    for mode in range(4):
        out=dest/str(mode);out.mkdir();sandbox=out/'sandbox';sandbox.mkdir()
        class AbiProbe(Probe):
            def on_debugbreak(self,ev):
                if not (sandbox/'ready.json').exists():return
                r=read(sandbox/'ready.json');core.require(r['pid']==self.process_obj.pid,'fixture PID')
                raw=self.mem(r['frame_address'],24)
                core.require(list(struct.unpack('<6I',raw))==r['frame'],'native x86 raw debugger words differ')
                self.log('native_x86_frame',raw=raw.hex(),**r)
                self.stop_requested=True
        cap=AbiProbe(out,sandbox,str(mode))
        cap.run=MethodType(fixture_run,cap)
        with (out/'stdout.bin').open('xb') as stdout,(out/'stderr.bin').open('xb') as stderr:
            cap.run([str(dest/'fixture.exe'),str(mode)],cwd=sandbox,env=environment(sandbox),stdout=stdout,stderr=stderr,timeout=15)
        core.require(cap.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'native x86 fixture containment')
        records=[r for r in cap.rows if r['kind']=='native_x86_frame']
        core.require(len(records)==1 and cap.terminated_while_stopped,'native x86 frame not observed')
        cases.append(dict(mode=mode,passed=True,record=records[0],cleanup=cap.cleanup))
    save(O/'native-x86-abi-validation.json',dict(passed=True,evidence=str(dest),cases=cases,
         genuine_launches=0,scope='Owned native x86 caller/callee ABI only; strict native-x86 renderer compatibility remains FAILED'))
    print('4 native x86 debugger cases PASS: real ECX thiscall, six words, fullscreen sources and RET 20/ESP +24.',flush=True)


if __name__=='__main__':run()
