"""Fresh incremental runtime builds and independent verification; never launches a game."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import struct
import sys
import time

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W/'tools/xrt'))
from supervisor import core, service
from supervisor.environment import load
from supervisor.plan import resolve
from supervisor.observer import construct
import asset_boundary as A


def authorization():
    q=core.read_large(core.HOME/'qualification.json'); service.verify_seal(q)
    s=core.read(core.HOME/'status.json'); ledger=core.Ledger(core.HOME/'ledger.jsonl')
    owners=[r for r in ledger.rows if r['kind']=='batch-authorized' and r['batch']['id']==s['batch']['id']]
    assert len(owners)==1
    owner=owners[0]
    assert owner['genuine_owner_console'] and owner['qualification_sha256']==core.digest(q)
    assert owner['batch']==s['batch'] and s['batch']['recovery_policy']=='contained-development-v1'
    assert s['state']=='waiting' and s['operational_state']=='RUNNING'
    assert not (core.HOME/'STOP').exists() and not (core.HOME/'HALTED.json').exists()
    used=sum(r['kind']=='launch-claimed' and r['batch_id']==s['batch']['id'] for r in ledger.rows)
    assert time.time()<s['batch']['expires_at'] and used<s['batch']['genuine_limit']
    return q,s,ledger,owner


def build(O):
    q,s,ledger,owner=authorization()
    O.mkdir(); B=W/'experiments/xrt/build'/O.name; B.mkdir()
    spec=importlib.util.spec_from_file_location('development_queryclass_builder',W/'experiments/xrt/tests/queryclass_boundary/run.py')
    driver=importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
    F=driver.F; F.O=O; F.B=B
    old=core.read_large(W/'out/recovery/viewport-getobject-20261028-01/build.json')
    previous=Path(old['root']); assert core.tree(previous)==old['outputs']
    runtime=core.tree(W/'experiments/xrt/runtime'); generated=core.tree(W/'experiments/xrt/gen')
    assert generated==old['generated']
    assert {n:h for n,h in runtime.items() if n.endswith('.h')}=={n:h for n,h in old['runtime'].items() if n.endswith('.h')}
    core.atomic(O/'inherited-build.json',old)
    core.atomic(O/'preservation.json',dict(authorization=owner,protected_inputs=A.verify(),runtime=runtime,generated=generated,
        strict_failures=core.read_large(W/'out/recovery/viewport-getobject-20261028-01/strict-failures-retained.json')))
    target=B/'client'; target.mkdir(); F.O=O/'client-build'; F.O.mkdir(); environment=F.env()
    before=A.verify(); copied={}; commands=[]
    for rel,h in old['outputs'].items():
        if rel.endswith('.obj') and not rel.startswith('obj/rt/'):
            dest=target/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(previous/rel,dest)
            assert core.sha(dest)==h; copied[rel]=h
    for row in old['commands']:
        original=row['command']; link=Path(original[0]).name.lower()=='link.exe'
        if not link and not any('/obj/rt/' in x.replace('\\','/') for x in original):continue
        cmd=[x.replace(str(previous),str(target)) for x in original]
        if link:
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
            name='link'
        else:
            obj=Path(next(x[3:] for x in cmd if x.startswith('/Fo')))
            obj.parent.mkdir(parents=True,exist_ok=True); assert not obj.exists(); name=obj.stem
        F.run(cmd,name,cwd=W/'experiments/xrt',environment=environment,timeout=180)
        commands.append(F.read(F.O/(name+'.json')))
    assert runtime==core.tree(W/'experiments/xrt/runtime') and generated==core.tree(W/'experiments/xrt/gen')
    assert A.verify()==before
    outputs=core.tree(target); assert sum(n.endswith('.obj') for n in outputs)==279
    exe_hash=core.sha(target/'xrt_ucc.exe')
    assert not any(r['kind']=='launch-claimed' and r['sha256']==exe_hash for r in core.Ledger(core.HOME/'ledger.jsonl').rows)
    core.atomic(O/'build.json',dict(passed=True,root=str(target),outputs=outputs,runtime=runtime,generated=generated,
        binary_sha256=exe_hash,pdb_sha256=core.sha(target/'xrt_ucc.pdb'),commands=commands,
        compiled_objects=14,reused_objects=265,reused_object_hashes=copied,inherited_build_sha256=core.sha(O/'inherited-build.json'),
        builder_sha256=core.sha(Path(__file__)),authorization_before_build=owner,protected_inputs=before))
    print('FRESH RUNTIME BUILD',exe_hash,flush=True)


def verify(O):
    q,s,ledger,owner=authorization()
    bp=O/'build.json'; b=core.read_large(bp); target=Path(b['root'])
    old=core.read_large(O/'inherited-build.json'); previous=Path(old['root'])
    assert b['passed'] and core.tree(target)==b['outputs'] and core.tree(previous)==old['outputs']
    assert core.tree(W/'experiments/xrt/runtime')==b['runtime'] and core.tree(W/'experiments/xrt/gen')==b['generated']
    assert b['compiled_objects']==14 and b['reused_objects']==265
    assert {n:h for n,h in b['runtime'].items() if n.endswith('.h')}=={n:h for n,h in old['runtime'].items() if n.endswith('.h')}
    lineage={}
    for source_build,reused in [(old,True),(b,False)]:
        for row in source_build['commands']:
            cmd=row['command']; assert row['exit']==0
            if Path(cmd[0]).name.lower()=='link.exe':continue
            obj=Path(next(x[3:] for x in cmd if x.startswith('/Fo'))); root=previous if reused else target
            rel=obj.relative_to(root).as_posix()
            if reused and rel.startswith('obj/rt/'):continue
            assert rel not in lineage and '/fp:strict' in cmd
            src=[W/'experiments/xrt'/x for x in cmd if x.lower().endswith('.c')]
            assert len(src)==1 and src[0].is_file()
            actual=target/rel; assert struct.unpack('<H',actual.read_bytes()[:2])[0]==0x8664
            if reused: assert core.sha(actual)==b['reused_object_hashes'][rel]==old['outputs'][rel]
            lineage[rel]=dict(source=src[0].relative_to(W).as_posix(),source_sha256=core.sha(src[0]),
                object_sha256=core.sha(actual),reused=reused,command=cmd)
    assert len(lineage)==279
    links=[r['command'] for r in b['commands'] if Path(r['command'][0]).name.lower()=='link.exe']; assert len(links)==1
    rsp=Path(next(x[1:] for x in links[0] if x.startswith('@')))
    linked=[Path(x.strip().strip('"')) for x in rsp.read_text().splitlines() if x.strip()]
    assert len(linked)==279 and set(linked)=={target/n for n in lineage}
    m=dict(version=1,kind='genuine',executable=(target/'xrt_ucc.exe').relative_to(W).as_posix(),sha256=b['binary_sha256'],
        pdb_sha256=b['pdb_sha256'],build_record=bp.relative_to(W).as_posix(),build_record_sha256=core.sha(bp),
        fixture_case=None,dependencies=q['candidate_dependencies'],sources={(W/'experiments/xrt/runtime'/n).relative_to(W).as_posix():h for n,h in b['runtime'].items()})
    core.validate_manifest(m,dict(scope=core.SCOPE))
    assert not any(r['kind']=='launch-claimed' and r['sha256']==m['sha256'] for r in ledger.rows)
    legacy=load('development_offline_observer',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    legacy.V.EXE=target/'xrt_ucc.exe'; legacy.V.EXPECTED=m['sha256']
    plan=resolve(legacy.S,legacy.E,legacy.V,m['pdb_sha256']); assert plan['static_mapping_verified'] and plan['guest_stop']==0x696f292
    od=O/'offline-observer'; od.mkdir()
    capture=construct(legacy,od,plan,lambda _:None,[target/'xrt_ucc.exe',*[W/n for n in m['dependencies']]])
    assert capture.created==0 and capture.module_record.__self__ is capture
    core.atomic(O/'object-lineage.json',lineage); core.atomic(O/'candidate-preview.json',m); core.atomic(O/'debugger-plan.json',plan)
    core.atomic(O/'verification.json',dict(passed=True,compiled_runtime_objects=14,verified_reused_generated_objects=265,
        complete_source_object_link_lineage=True,candidate_sha256=m['sha256'],pdb_sha256=m['pdb_sha256'],unconsumed=True,
        permanent_stop_mapping_verified=True,complete_observer_constructed=True,authorization=owner,
        qualification_digest=core.digest(q),protected_inputs=A.verify(),strict_x87=q['strict_x87'],
        strict_wndproc=q['strict_wndproc_equality'],genuine_launches=0,verifier_sha256=core.sha(Path(__file__))))
    print('INDEPENDENT CANDIDATE VERIFICATION PASS',m['sha256'],flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('action',choices=['build','verify']); ap.add_argument('phase')
    args=ap.parse_args(); assert all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.phase)
    globals()[args.action](W/'out/recovery'/args.phase)
