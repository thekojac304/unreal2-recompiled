"""Execute the exact staged composition on owned non-game protocol fixtures."""
import sys,uuid,shutil,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from continuation import install
from supervisor import fixture
from supervisor.windows import Context,FilePins

def main():
    out=O/('composed-'+str(uuid.uuid4()));out.mkdir();h=helper(out);env=h.env()
    h.run(['ml64','/nologo','/c','/Fo'+str(out/'stop.obj'),H/'stop_fixture.asm'],'stop-build',environment=env)
    h.run(['ml64','/nologo','/c','/Fo'+str(out/'entry.obj'),H/'composed_fixture.asm'],'entry-build',environment=env)
    exe=out/'fixture.exe'
    h.run(['cl','/nologo','/Od','/fp:strict','/D_CRT_SECURE_NO_WARNINGS','/Fo'+str(out/'fixture.obj'),'/Fe'+str(exe),H/'composed_fixture.c',out/'stop.obj',out/'entry.obj'],'build',environment=env)
    results=[]
    for case,arg in (('success','0'),('raw-register-corruption','1'),('event-object-corruption','2'),('evidence-write-failure','0')):
        dest=out/case;dest.mkdir();sandbox=dest/'sandbox';sandbox.mkdir();checks=[]
        class Probe(fixture.Probe):
            def u64(self,address):return struct.unpack('<Q',self.mem(address,8))[0]
            def on_create(self,ev):self.breakpoints={}
            def sym(self,name):return self.symbols[name]
            def snapshot_events(self):
                if case=='evidence-write-failure':raise OSError('injected durable evidence failure')
                shutil.copy2(sandbox/'runtime-events.json',dest/'runtime-events.json')
            def on_debugbreak(self,ev):
                t=read(sandbox/'ready.json');assert t['pid']==self.process_obj.pid
                self.symbols={'xrt_fatal':t['fatal'],'d8_CreateDevice':t['create'],'xrt_g':t['guest_pointer']}
                plan=dict(entry_rva=t['entry']-self.base,entry_bytes='90',stop_rva=t['stop']-self.base,stop_bytes='895f44',stop_registers=dict(cpu='rdi'))
                base=self.base;self.base=0;install(self,plan,checks.append);self.base=base
                self.on_create(ev)
                for thread,_ in self.threads.values():self.update(Context(thread))
        probe=Probe(dest,sandbox,case);error=None
        with FilePins() as pins:
            pins.pin(exe,core.sha(exe))
            try:
                with (dest/'stdout.bin').open('xb') as stdout,(dest/'stderr.bin').open('xb') as stderr:
                    probe.run([str(exe),arg],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,timeout=15)
            except (core.Rejected,OSError) as exc:error=str(exc)
        core.require((error is None)==(case=='success'),'composed fixture expected outcome: '+str(error))
        core.require(probe.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'composed containment')
        core.require(any(r['kind']=='terminated_before_continue' for r in probe.rows),'terminated while stopped')
        core.require(checks==['target-created-before-first-resume'],'environment callback')
        core.require(any(r['kind']=='integrated_init_entry_raw' for r in probe.rows),'entry not captured')
        results.append(dict(case=case,passed=True,error=error,cleanup=probe.cleanup))
    save(O/'composed-validation.json',dict(passed=True,root=str(out),results=results,source=core.tree(H),
        original_code_executed=False,graphics=False,observer_installed=False,genuine_launches=0))
    print('Exact composed observer: success and three failure paths contained on owned code',flush=True)

if __name__=='__main__':main()
