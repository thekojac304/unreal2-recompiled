"""Live composed debugger test, exclusively owned native protocol code."""
import sys, struct, shutil, uuid, os, json
from pathlib import Path
from types import MethodType
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from composition import install, semantic
from supervisor import fixture
from supervisor.windows import Context, FilePins

def main():
    root=O/('live-'+str(uuid.uuid4()));root.mkdir();h=helper(root);env=h.env()
    src=H.parent/'integrated_candidate'
    for name in ('stop_fixture','composed_fixture'):
        h.run(['ml64','/nologo','/c','/Fo'+str(root/(name+'.obj')),src/(name+'.asm')],name,environment=env)
    exe=root/'protocol.exe'
    h.run(['cl','/nologo','/Od','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',
           '/Fo'+str(root/'protocol.obj'),'/Fe'+str(exe),H/'protocol.c',
           root/'stop_fixture.obj',root/'composed_fixture.obj'],'build',environment=env)
    mapping=read(O/'composed-mapping.json')
    results=[]
    for case,arg in (('success','0'),('native-failure','1'),('unqualified-texture','2'),
                     ('callback-corruption','3'),('fatal-in-callback','4'),('watchdog','5'),
                     ('evidence-write-failure','0'),('init-corruption','7'),('readback-failure','0'),
                     ('precision-risk-no-policy','8'),('callback-checkpoint-gap','9')):
        out=root/case;out.mkdir();sandbox=out/'sandbox';sandbox.mkdir()
        template,_=semantic.construct(out,mapping,lambda _:None,[])
        class Probe(fixture.Probe):
            def __init__(self):
                super().__init__(out,sandbox,case)
                self.operations=[];self.entries={};self.native_active=None;self.callback_frames=[]
                self.strict_discrepancies=[];self.setres_entry=None;self.cpu=None;self.guest_base=0
                self.monitor_generation=0;self.installed=False;self.symbols={}
            def sym(self,name):return self.symbols[name]
            def log(self,kind,**fields):
                if case=='evidence-write-failure' and kind=='semantic_native_arguments':
                    raise OSError('injected evidence write failure')
                # fsync makes evidence a precondition for assertion/continuation.
                row=dict(kind=kind,**fields)
                with (self.out/'debug-events.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
                self.rows.append(row)
                if case=='readback-failure' and kind=='monitor_readback' and self.monitor_generation>=3:
                    raise core.Rejected('injected readback evidence failure')
            def on_debugbreak(self,ev):
                t=read(sandbox/'ready.json');core.require(t['pid']==self.process_obj.pid,'owned PID')
                self.target=t
                self.symbols=dict(xrt_fatal=t['fatal'],xrt_g=t['guest_pointer'],
                    d8_semantic_checkpoint=t['checkpoint'],invoke_gui_proc=t['callback'])
                self.guest_base=self.u64(t['guest_pointer']);self.cpu=t['cpu']
                plan=dict(entry_rva=t['entry']-self.base,entry_bytes='90',stop_rva=t['stop']-self.base,
                          stop_bytes='895f44',stop_registers=dict(cpu='rdi'))
                base=self.base;self.base=0
                install(self,plan,lambda _:None,owned_fixture=True)
                self.base=base;self.installed=True;self.on_create(ev)
                self.update(Context(self.threads[ev.tid][0]))
            def object_state(self):
                raw=self.mem(self.target['registry'],280)
                host=struct.unpack_from('<Q',raw,24)[0]
                return dict(guest=struct.unpack_from('<I',raw)[0],guest_refs=struct.unpack_from('<I',raw,4)[0],
                    host=host,parent=0,parent_state=dict(host=0),registry_raw=raw.hex(),
                    native_vtable=self.u64(host),live_caps=list(struct.unpack_from('<53I',raw,40)))
            def hwnds(self):return []
            def snapshot_events(self):
                if (sandbox/'runtime-events.json').exists():
                    shutil.copy2(sandbox/'runtime-events.json',out/'runtime-events.json')
            def hit(self,tag,ctx,tid):
                if tag=='fatal_entry':
                    self.log('owned_fatal_raw',host=ctx.snapshot(),code=ctx.get('rdx'),
                             raw_cpu=self.mem(ctx.get('rcx'),416).hex())
                    raise core.Rejected('owned fatal before Init return')
                return template.hit.__func__(self,tag,ctx,tid)
        probe=Probe()
        for name in ('cpu_state','u64','u32','words','guest'):
            setattr(probe,name,MethodType(getattr(template,name).__func__,probe))
        error=None
        with FilePins() as pins:
            pins.pin(exe,core.sha(exe))
            try:
                with (out/'stdout.bin').open('xb') as stdout,(out/'stderr.bin').open('xb') as stderr:
                    probe.run([str(exe),arg],cwd=sandbox,env=fixture.environment(sandbox),
                              stdout=stdout,stderr=stderr,timeout=3 if case=='watchdog' else 20)
            except Exception as exc:error=type(exc).__name__+': '+str(exc)
        expected_success=case in ('success','native-failure','callback-checkpoint-gap')
        row=dict(case=case,error=error,cleanup=probe.cleanup,operations=probe.operations,
                 counts=getattr(probe,'monitor_counts',{}),expected_success=expected_success,
                 genuine_launches=0,graphics=False,protocol_double=True)
        save(out/'result.json',row)
        core.require((error is None)==expected_success,'unexpected composed outcome '+case+': '+str(error))
        expected_errors={
            'unqualified-texture':'unqualified native signature: 20',
            'callback-corruption':'callback corrupted suspended CPU',
            'fatal-in-callback':'owned fatal before Init return',
            'watchdog':'watchdog or local stop',
            'evidence-write-failure':'injected evidence write failure',
            'init-corruption':'Init guest nonvolatile registers',
            'readback-failure':'injected readback evidence failure',
            'precision-risk-no-policy':'strict state discrepancy'}
        if not expected_success:
            core.require(expected_errors[case] in error,'wrong refusal cause: '+str(error))
        if case=='unqualified-texture':
            core.require(not row['counts'].get('semantic_native_entry') and not probe.operations,
                         'unknown signature reached a native entry')
        if case=='precision-risk-no-policy':
            core.require(any(r['kind']=='strict_differential' for r in probe.rows),'precision evidence absent')
        if case=='fatal-in-callback':
            core.require(any(r['kind']=='owned_fatal_raw' for r in probe.rows),'fatal evidence absent')
        core.require(probe.cleanup['passed'] and not (sandbox/'FORBIDDEN.txt').exists(),'contained protocol')
        if case=='watchdog':core.require(probe.cleanup['watchdog'],'watchdog did not fire')
        else:core.require(any(r['kind']=='terminated_before_continue' for r in probe.rows),'resumed stopped target')
        if expected_success:
            core.require(len(probe.operations)==2,'whole interval operation count')
            core.require(row['counts']['semantic_callback']==row['counts']['semantic_callback_return']==4,'nested callback pairs')
            core.require(row['counts']['semantic_native_entry']==row['counts']['semantic_native_return']==2,'independent native pairs')
            core.require(row['counts']['init_entry']==row['counts']['init_return']==1,'Init pair')
            core.require(all(op['last_error']==87 and op['result']==(0x80004005 if case=='native-failure' else 0)
                             for op in probe.operations),'actual native result/error changed')
            generations={}
            for r in probe.rows:
                if r['kind']=='monitor_schedule':generations[r['generation']]=dict(expected=set(r['threads']),actual=set(),points=r['points'])
                if r['kind']=='monitor_readback':generations[r['generation']]['actual'].add(r['tid'])
            core.require(all(g['expected']==g['actual'] for g in generations.values()),'all-thread readback incomplete')
            core.require(max(len(g['actual']) for g in generations.values())>=3,'existing and new thread coverage')
        row['passed']=True;save(out/'result.json',row);results.append(row)
        if case=='callback-checkpoint-gap':
            core.require((sandbox/'UNOBSERVED-CHECKPOINT.txt').exists(),'adversarial callback checkpoint not exercised')
            core.require(not any(r['kind']=='monitor_checkpoint_dispatch' and r['slot']==20 for r in probe.rows),
                         'scheduler behavior changed; re-evaluate callback coverage')
            row.update(passed=False,qualification_passed=False,harness_verified_gap=True,
                       finding='Phase-zero checkpoint inside callback was not trapped; no real resource API executed.')
            save(out/'result.json',row)
        print(case,'MONITORING QUALIFICATION FAILED (gap reproduced)' if case=='callback-checkpoint-gap' else 'PASS',flush=True)
    save(O/'live-validation.json',dict(passed=True,root=str(root),results=results,
        fixture_sha256=core.sha(exe),source=core.tree(H),genuine_execution_ready=False,
        full_monitoring_qualification_passed=False,
        limitation='Detailed 12-signature renderer handler plus owned Init/callback protocol; not full runtime domain qualification.'))

if __name__=='__main__':main()
