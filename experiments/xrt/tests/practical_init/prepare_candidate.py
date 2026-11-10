"""Concrete candidate observer construction for review, never process execution."""
import sys,uuid
from pathlib import Path
from types import MethodType
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from composition import _construct

def prepare(out):
    ident=read(O/'candidate-identity.json');mapping=read(O/'stop-mapping.json');linked=read(O/'monitor-linked.json')
    exe,sha,pdb=identity()
    core.require(core.sha(exe)==ident['sha256']==mapping['sha256']==linked['sha256']==sha,'candidate pins')
    core.require(core.sha(exe.with_suffix('.pdb'))==pdb==ident['pdb_sha256'],'PDB pin')
    symbols=dict(mapping['symbols']);symbols.update(linked['symbols'])
    names=['xrt_fatal','xm_failure','xm_pending','xm_committed','xm_recorded','xm_written',
        'xm_buffer_count','xm_profile','xm_failed','xm_buffer','d8_CreateDevice']
    core.require(all(name in symbols for name in names),'required actual candidate symbols')
    points=[symbols['xrt_fatal']['rva'],symbols['xm_failure']['rva'],mapping['stop_rva'],symbols['d8_CreateDevice']['rva']]
    core.require(len(set(points))==4 and mapping['stop_bytes']=='895f44','four distinct candidate critical slots')
    for dep,digest in ident['dependencies'].items():core.require(core.sha(core.independent(dep))==digest,'dependency pin')
    plan=dict(owned_fixture=False,review_only=True,executable=str(exe),sha256=sha,pdb_sha256=pdb,
        symbols=symbols,stop_rva=mapping['stop_rva'],stop_bytes=mapping['stop_bytes'],
        environment_gate_symbol='d8_CreateDevice',limits=dict(launches=1,timeout_seconds=60,retry=False))
    # _construct binds exactly the same tested four-slot handlers. No fake
    # owned-fixture label is used. run is unavailable in this review object.
    def environment(tag):raise core.Rejected('owner desktop/environment gate has not passed')
    cap=_construct(out,plan,out/'unlaunched-trace.bin',environment)
    cap.allowed_modules=[str(exe),*ident['dependencies']]
    def refuse(self,*args,**kwargs):raise core.Rejected('candidate review object cannot launch; experimental owner authorization absent')
    cap.run=MethodType(refuse,cap)
    try:cap.run([])
    except core.Rejected as e:rejection=str(e)
    else:raise AssertionError('review object allowed a launch')
    core.require(cap.created==0 and cap.base==0 and not cap.threads,'candidate executed during review construction')
    return dict(passed=True,plan=plan,critical_rvas=points,production_factory=True,
        isolated_handle_ownership=True,handlers_shared_with_owned_composition=True,
        actual_candidate_instructions_executed=0,run_rejection=rejection,
        candidate_activation=False,production_policy_changed=False)

if __name__=='__main__':
    out=O/('candidate-observer-'+str(uuid.uuid4()));out.mkdir()
    save(O/'candidate-observer-preparation.json',dict(prepare(out),root=str(out),runtime=core.tree(RT),
        source_sha256=core.sha(Path(__file__)),composition_sha256=core.sha(H/'composition.py')))
    print('Actual candidate PE/PDB/symbol-bound four-slot observer constructed for review; run refused, no launch',flush=True)
