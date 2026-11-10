import pathlib
import shutil
import struct
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
from profile_gate import capture,require_exact
from supervisor.fixture import Probe,environment


def run():
    out=O/('field-debugger-'+str(uuid.uuid4()));out.mkdir();helper=load('field_capture_build',H.parent/'getobject_boundary/phase.py');helper.O=out;env=helper.env()
    profile=read(O/'configuration-profile.json');seed='\n'.join(f'    *(uint32_t*)(xrt_g+0x10000+{off})={v}u;' for off,v in profile['fields'].items())
    seed+='\n'+'\n'.join(f'    *(uint32_t*)(xrt_g+0x14134+4*{i})={v}u;' for i,v in enumerate(profile['caps']['caps']))
    (out/'field_seed.inc').write_text(seed)
    cl=pathlib.Path(shutil.which('cl.exe',path=env.get('Path',env.get('PATH'))))
    helper.run([cl.with_name('ml64.exe'),'/nologo','/c','/Fo'+str(out/'stop.obj'),H/'field_fixture.asm'],'asm',environment=env)
    helper.run([cl,'/nologo','/Od','/Zi','/I'+str(out),'/Fo'+str(out/'fixture.obj'),'/Fd'+str(out/'compile.pdb'),'/Fe'+str(out/'fixture.exe'),H/'field_fixture.c',out/'stop.obj','/link','/DEBUG','/INCREMENTAL:NO'],'build',environment=env)
    cases=[]
    for mode in ('exact','unknown','multiple','invalid','unreadable','write-failure'):
        dest=out/mode;dest.mkdir();sandbox=dest/'sandbox';sandbox.mkdir()
        class FieldProbe(Probe):
            def on_debugbreak(self,ev):
                super().on_debugbreak(ev);self.cpu=self.target['cpu'];self.guest_base=struct.unpack('<Q',self.mem(self.target['guest_pointer'],8))[0]
                self.setres_entry=dict(renderer=self.target['renderer'],viewport=0x18000,cpu=dict(registers=dict(ecx=self.target['renderer'])))
            def hit(self,tag,ctx,tid):
                raw=self.mem(self.cpu,416);v=struct.unpack_from('<18I',raw);cpu=dict(raw=raw.hex(),registers=dict(zip(('eax','ecx','edx','ebx','esp','ebp','esi','edi'),v[:8])),pc=v[17])
                frame=list(struct.unpack('<3I',self.mem(self.guest_base+cpu['registers']['esp'],12)))
                if mode=='write-failure':
                    original=self.log
                    def broken(kind,**values):
                        if kind=='renderer_profile_field' and values['offset']=='0x4124':raise OSError('injected evidence write failure')
                        original(kind,**values)
                    self.log=broken
                result=capture(self,self.target['renderer'],profile,cpu,frame,dict(guest=0x60000,host=0x800000,parent=0x801000),ctx)
                require_exact(result);self.stop_requested=True
        cap=FieldProbe(dest,sandbox,mode);error=None
        try:
            with (dest/'stdout.bin').open('xb') as stdout,(dest/'stderr.bin').open('xb') as stderr:
                cap.run([str(out/'fixture.exe'),mode],cwd=sandbox,env=environment(sandbox),stdout=stdout,stderr=stderr,timeout=15)
        except (core.Rejected,OSError) as e:error=str(e)
        core.require(cap.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'field fixture cleanup/continue error')
        core.require((mode=='exact')==(error is None),'field fixture outcome')
        fields=[r for r in cap.rows if r['kind']=='renderer_profile_field']
        core.require(len(fields)==(2 if mode=='write-failure' else 10),'field evidence lost/short-circuited')
        if mode=='multiple':core.require('0x40d0' in error and '0x4124' in error,'individual mismatches missing')
        core.require(any(r['kind']=='renderer_profile_context' for r in cap.rows),'CPU/frame/identity evidence missing')
        cases.append(dict(mode=mode,passed=True,error=error,fields_recorded=len(fields),cleanup=cap.cleanup))
    save(O/'field-debugger-validation.json',dict(passed=True,evidence=str(out),cases=cases,all_fields_before_aggregate_assertions=True,
        invalid_unreadable_multiple_and_write_failures=True,genuine_launches=0,candidate_instructions_executed=0))
    print('6 live debugger field/evidence/negative cases PASS; terminate-before-continue and cleanup verified.',flush=True)


if __name__=='__main__':run()
