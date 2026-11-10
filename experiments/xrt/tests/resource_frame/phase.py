"""Preserve, stage, compile and inspect; never executes a genuine candidate."""
import sys, shutil, uuid, json, collections, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

def stage():
    O.mkdir()
    roots = [PRIOR, EVIDENCE, W/'experiments/xrt/runtime', W/'experiments/xrt/gen', W/'tools/xrt/supervisor']
    save(O/'preservation.json', dict(trees={str(p):core.tree(p) for p in roots}, protected=A.verify(), genuine_launches=0))
    shutil.copytree(PRIOR/'runtime', RT)
    print('Preserved and staged', RT, flush=True)

def audit():
    rows = [json.loads(s) for s in (EVIDENCE/'debug-observations.jsonl').read_text().splitlines()]
    events = read(EVIDENCE/'runtime-events.json')['events']
    def one(kind, **fields):
        found = [r for r in rows if r['kind']==kind and all(r.get(k)==v for k,v in fields.items())]
        assert len(found)==1, (kind,fields,len(found))
        return found[0]
    entry=one('semantic_raw_cpu',tag='semantic_setres_entry')
    ret=one('semantic_raw_cpu',tag='setres_completion_stop')
    frame=one('semantic_setres_frame')['frame']
    initial=one('semantic_initial_return')
    a,b=entry['cpu'],ret['cpu']
    assert frame[0]==0x11104bf8 and b['registers']['eax']==1
    assert b['registers']['esp']==a['registers']['esp']+24 and b['rv']==0x11104bf8
    for reg in ('ebx','ebp','esi','edi'): assert a['registers'][reg]==b['registers'][reg]
    bounds=[e for e in events if e['kind']=='setres_boundary']
    assert len(bounds)==2 and [e['phase'] for e in bounds]==['entry','return']
    for tag,cpu in [('entry',entry),('return',ret)]:
        chunks=[e for e in events if e['kind']=='setres_raw' and e['phase']==tag and e['area']=='cpu']
        assert [e['offset'] for e in chunks]==[0,128,256,384]
        assert ''.join(e['hex'] for e in chunks)==cpu['raw']
    assert all(initial['checks'].values()) and initial['instruction_executed'] is False
    ops=initial['operations']; slots={o['slot'] for o in ops}
    checkpoints=[r for r in rows if r['kind']=='semantic_checkpoint_raw' and r['slot'] in slots]
    native=[r for r in rows if r['kind']=='semantic_native_result']
    assert len(checkpoints)==4*len(ops) and len(native)==len(ops)
    for i,(op,n) in enumerate(zip(ops,native)):
        rs=checkpoints[4*i:4*i+4]
        assert [r['phase'] for r in rs]==[0,1,2,3]
        assert all(r['slot']==op['slot'] for r in rs)
        assert rs[2]['last_error']==rs[3]['last_error']==op['last_error']==n['last_error']
        assert (n['slot'],n['hresult'])==(op['slot'],op['result'])
        if op['slot']!=18: assert rs[2]['result']==rs[3]['result']==op['result']
        else: assert op['result'] is None
    for kind in ('semantic_native_arguments','semantic_native_abi','semantic_abi_evaluation'):
        checks=[r for r in rows if r['kind']==kind]
        assert len(checks)==len(ops) and all(not r['discrepancies'] for r in checks)
    cleanup=read(EVIDENCE/'cleanup.json'); stop=read(EVIDENCE/'hard-stop.json')
    assert cleanup['passed'] and cleanup['remaining_job_processes']==0 and cleanup['kill_on_close']
    assert stop['hit'] and stop['instruction_executed'] is False and stop['guest_address']=='0x11104bf8'
    gamma=read(EVIDENCE/'desktop-gamma-restored.json')
    assert gamma['passed'] and gamma['displays']
    assert all(d['before_read'] and d['after_read'] and d['set_original'] and d['equal'] and
        d['before']==d['after'] for d in gamma['displays'])
    save(O/'setres-independent-audit.json',dict(passed=True,source=str(EVIDENCE),files=core.tree(EVIDENCE),
        entry_cpu=a,return_cpu=b,frame=frame,viewport=hex(frame[1]),operation_count=len(ops),
        operation_counts=dict(collections.Counter(o['slot'] for o in ops)),last_errors=dict(collections.Counter(o['last_error'] for o in ops)),
        identity_checks=initial['checks'],raw_objects=[r for r in rows if r['kind']=='semantic_raw_objects' and r.get('tag') in ('semantic_setres_entry','setres_completion_stop')],
        strict_differences=[r for r in rows if r['kind']=='strict_differential'],gamma_restoration=gamma,
        cleanup=cleanup,hardware_stop=stop,strict_compatibility='FAILED retained',
        normal_guest_cleanup_claimed=False,game_frame_verified=False))
    print('SetRes independently paired:',len(ops),'operations; EAX=1 ESP',hex(b['registers']['esp']),flush=True)

def build():
    b=read(PRIOR/'build.json'); origin=read(PRIOR/'object-lineage.json'); previous=Path(b['root'])
    assert core.tree(previous)==b['outputs'] and core.tree(W/'experiments/xrt/gen')==b['generated']
    target=W/'experiments/xrt/build/resource-frame-20261030-01'/str(uuid.uuid4());target.mkdir(parents=True)
    logs=O/('build-'+str(uuid.uuid4()));logs.mkdir();h=helper(logs);env=h.env()
    changed={'obj/rt/hle_misc.obj'};lineage={};copied={}
    for rel,row in origin.items():
        assert core.sha(previous/rel)==row['object_sha256'] and core.sha(row['source'])==row['source_sha256']
        for name,digest in row.get('verified_local_headers',{}).items(): assert core.sha(name)==digest
        if rel in changed: continue
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest);copied[rel]=core.sha(dest)
        lineage[rel]=dict(row,reused=True,reused_in_this_candidate=True,inherited_from=str(PRIOR/'object-lineage.json'))
    for rel in sorted(changed):
        name=Path(rel).stem;row=origin[rel];old_source=Path(row['source']);old_output=Path(next(s[3:] for s in row['command'] if s.startswith('/Fo')))
        cmd=[s.replace(str(old_source.parent),str(RT)).replace(str(old_output.parent),str(target/'obj/rt')) for s in row['command']]
        if '/showIncludes' not in cmd:cmd.insert(1,'/showIncludes')
        h.run(cmd,name,cwd=W/'experiments/xrt',environment=env,timeout=120)
        lineage[rel]=dict(source=str(RT/(name+'.c')),source_sha256=core.sha(RT/(name+'.c')),object_sha256=core.sha(target/rel),command=cmd,
            reused=False,reused_in_this_candidate=False,verified_local_headers={str(RT/n):v for n,v in core.tree(RT).items() if n.endswith(('.h','.inc'))})
    link=[s.replace(str(previous),str(target)) for s in b['commands'][-1]['command']]
    (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
    h.run(link,'link',cwd=W/'experiments/xrt',environment=env,timeout=120)
    save(O/'object-lineage.json',lineage)
    save(O/'build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),generated=b['generated'],
        binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),compiled_objects=1,reused_objects=278,reused_object_hashes=copied,
        commands=[read(logs/(n+'.json')) for n in ('hle_misc','link')],inherited_build=str(PRIOR/'build.json'),inherited_build_sha256=core.sha(PRIOR/'build.json'),
        toolchain=b['toolchain'],gamma_profile=b['gamma_profile'],genuine_launches=0,execution_authorized=False))
    print('Built fresh unexecuted candidate',target,flush=True)

def verify():
    m=load('bringup_identity',H.parent/'renderer_config_diagnosis/identity.py')
    b=read(O/'build.json');m.O=O;m.RT=RT;m.EXE=Path(b['root'])/'xrt_ucc.exe';m.SHA=b['binary_sha256'];m.PDB=b['pdb_sha256']
    save(O/'candidate-identity.json',m.verify());print('Independent lineage / PE / PDB / nonconsumption PASS',flush=True)

def preservation():
    p=read(O/'preservation.json');changed=[]
    for root,tree in p['trees'].items():
        if core.tree(Path(root))!=tree:changed.append(root)
    protected=A.verify();assert protected==p['protected']
    save(O/'preservation-after.json',dict(passed=not changed,changed=changed,protected=protected,genuine_launches=0))
    assert not changed;print('Preservation PASS',flush=True)

if __name__=='__main__':
    assert sys.argv[1] in ('stage','audit','build','verify','preservation')
    globals()[sys.argv[1]]()

