"""Live new observer on owned protocol doubles, under retained Job/watchdog.

No graphics backend or original game module is loaded. Candidate is not executed.
Actual candidate mapping/permanent-stop testing is a separate qualification.
"""
import json
import struct
import sys
from pathlib import Path
from types import MethodType
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import observer
from supervisor import fixture
from supervisor.windows import Context,FilePins

def main():
    fixture_root=Path(read(O/'contracts.json')['root']);exe=fixture_root/'x64/fixture.exe';pinned=core.sha(exe)
    root=O/('live-semantic-'+str(uuid.uuid4()));root.mkdir();results=[]
    for case in ('success','native-failure','matrix','material','gamma','clear','callback','create','create-nullfocus','create-failure','corrupt-cpu','write-failure'):
        dest=root/case;dest.mkdir();sandbox=dest/'sandbox';sandbox.mkdir()
        template,_=observer.construct(dest,read(O/'stop-mapping.json'),lambda _:None,[])
        class Trace(fixture.Probe):
            def __init__(self):
                super().__init__(dest,sandbox,case);self.operations=[];self.entries={};self.native_active=None
                self.setres_entry={'owned_fixture':True};self.callback_frames=[];self.strict_discrepancies=[];self.cpu=None
            def sym(self,name):
                return self.symbols[name]
            def on_debugbreak(self,ev):
                self.target=core.read(self.sandbox/'ready.json');core.require(self.target['pid']==self.process_obj.pid,'owned trace PID')
                t=self.target;self.cpu=t['cpu'];self.guest_base=self.u64(t['guest_pointer'])
                self.symbols=dict(xrt_g=t['guest_pointer'],d8_device=t['registry'],d8_semantic_checkpoint=t['checkpoint'],xrt_fatal=t['fatal'],invoke_gui_proc=t['callback'])
                self.plan=dict(stop_rva=t['stop']-self.base)
                self.breakpoints={t['checkpoint']:'semantic_checkpoint',t['fatal']:'fatal_entry'}
                for thread,_ in self.threads.values():self.update(Context(thread))
                self.log('owned_protocol_only',candidate_executed=False,graphics=False,real_GUI_callback=False)
            def update(self,ctx,resume=False):
                if not hasattr(self,'plan'):ctx.arm([],resume);return
                observer.hardware(self,ctx,self.plan,resume)
            def object_state(self):
                raw=self.mem(self.sym('d8_device'),280);g,refs,focus,window,presents=struct.unpack_from('<5I',raw);host,parent=struct.unpack_from('<2Q',raw,24)
                return dict(guest=g,guest_refs=refs,focus=focus,window=window,presents=presents,host=host,parent=parent,
                            parent_state=dict(host=self.u64(self.target['parent']+16)),
                            native_vtable=self.u64(host) if host else 0,registry_raw=raw.hex(),live_caps=list(struct.unpack_from('<53I',raw,40)))
            def hwnds(self):return [dict(guest=v,native=v) for v in (0x1234,0x1235)]
            def snapshot_events(self):
                p=self.sandbox/'runtime-protocol.jsonl'
                if p.exists():
                    rows=[json.loads(s) for s in p.read_text().splitlines()]
                    core.require([r['seq'] for r in rows]==list(range(1,len(rows)+1)),'owned event order')
                    save(self.out/'runtime-protocol.json',dict(events=rows,sha256=core.sha(p),dropped=0,protocol_double=True))
            def hit(self,tag,ctx,tid):
                if tag=='fatal_entry':
                    # This Probe owns a different process handle interface from
                    # the retained game's fatal collector. Capture its actual
                    # fatal arguments locally; the retained collector itself
                    # is exercised separately by qualify.py.
                    data=bytearray();p=ctx.get('r8')
                    for i in range(1024):
                        b=self.mem(p+i,1)
                        if b==b'\0':break
                        data.extend(b)
                    self.log('owned_fatal_entry',code=ctx.get('rdx'),format=data.decode(errors='replace'),host=ctx.snapshot())
                    self.snapshot_events()
                    raise core.Rejected('owned native failure requires teardown')
                if tag=='setres_completion_stop':
                    self.log('owned_marker_before_continue',operations=self.operations,entries=len(self.entries),host=ctx.snapshot())
                    core.require(len(self.operations)==1 and not self.entries and self.native_active is None,'owned operation did not complete')
                    self.snapshot_events();self.stop_requested=True;return
                return template.hit.__func__(self,tag,ctx,tid)
            def log(self,kind,**values):
                if case=='write-failure' and kind=='semantic_native_arguments':raise OSError('injected durable evidence failure')
                super().log(kind,**values)
        probe=Trace()
        for name in ('cpu_state','u64','u32','words','guest'):
            setattr(probe,name,MethodType(getattr(template,name).__func__,probe))
        error=None
        with FilePins() as pins:
            pins.pin(exe,pinned)
            try:
                with (dest/'stdout.bin').open('xb') as stdout,(dest/'stderr.bin').open('xb') as stderr:
                    probe.run([str(exe),case],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,timeout=20)
            except (OSError,core.Rejected) as exc:error=str(exc)
        negative=case in ('corrupt-cpu','write-failure','create-failure')
        core.require((bool(error) if negative else error is None),'unexpected live observer outcome: '+str(error))
        core.require(probe.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'live observer containment/marker')
        core.require(any(r['kind']=='terminated_before_continue' for r in probe.rows),'fixture resumed after stop/error')
        if not negative or case=='create-failure':
            core.require(any(r['kind']=='semantic_native_result' for r in probe.rows),'missing independent native result')
            protocol=read(dest/'runtime-protocol.json')['events']
            core.require([r['phase'] for r in protocol if r['kind']=='d3d8_checkpoint']==[0,1,2,3],'complete runtime phases')
        row=dict(case=case,passed=True,error=error,cleanup=probe.cleanup,operations=probe.operations)
        save(dest/'result.json',row);results.append(row)
    save(O/'live-observer-validation.json',dict(passed=True,root=str(root),cases=results,protocol_double=True,physical_GPU=False,genuine_launches=0,candidate_instructions_executed=0,
        observer_sha256=core.sha(H/'observer.py'),fixture_sha256=pinned,runtime=core.tree(RT)))
    print('Twelve live semantic observer/native/creation/void/callback/evidence-failure protocol cases PASS.',flush=True)
if __name__=='__main__':main()
