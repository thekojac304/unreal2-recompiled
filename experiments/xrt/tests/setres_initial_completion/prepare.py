"""Preservation, isolated instrumentation and serial candidate build; no game execution."""
import difflib
import pathlib
import shutil
import subprocess
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def preserve():
    core.require(not O.exists(),'preserve existing preparation')
    O.mkdir()
    roots=[OLD,DIAG,PRIOR,core.HOME,W/'experiments/xrt/runtime',W/'experiments/xrt/gen',W/'tools/xrt']
    consumed={}
    claimed={r['sha256'] for r in core.Ledger(core.HOME/'ledger.jsonl').rows if r['kind']=='launch-claimed'}
    for p in (W/'out').rglob('launch.json'):
        try:d=read(p)
        except (ValueError,KeyError):continue
        if d.get('sha256') in claimed and d.get('executable'):
            exe=pathlib.Path(d['executable'])
            if exe.is_file():consumed[str(exe)]=core.sha(exe);roots.append(exe.parent)
    roots += [W/'sandbox_cmp/setres-fa3b112f-189a-422b-ac3c-ea197a910de6',W/'sandbox_cmp/setres-13a98b68-bf93-4196-825c-773a1b66f474']
    trees={str(p):core.tree(p) for p in dict.fromkeys(roots)}
    source={str(p):core.sha(p) for base in [W/'experiments/xrt/tests',W/'notes'] for p in base.rglob('*')
            if p.is_file() and not p.is_relative_to(H) and '__pycache__' not in p.parts}
    source.update({str(p):core.sha(p) for p in W.glob('*.md')})
    preserved=O/'preserved';preserved.mkdir()
    for p in [OLD/'HALTED.json',OLD/'OWNER-ATTEMPT-CONSUMED.json',core.HOME/'ledger.jsonl']:
        shutil.copy2(p,preserved/p.name)
    shutil.copytree(OLD/'owner-fa3b112f-189a-422b-ac3c-ea197a910de6',preserved/'complete-consumed-attempt')
    strict=read(OLD/'preservation.json')['strict_failure_files']
    strict.update({str(PRIOR/'physical-gamma-audit.json'):core.sha(PRIOR/'physical-gamma-audit.json')})
    for path,digest in strict.items():core.require(core.sha(path)==digest,'strict failure changed')
    shutil.copytree(DIAG/'strict-failures',preserved/'strict-failures')
    for name,args in [('git-head',['rev-parse','HEAD']),('git-status',['status','--short']),('git-diff',['diff','--binary'])]:
        r=subprocess.run(['git',*args],cwd=W,capture_output=True,check=True);(O/(name+'.txt')).write_bytes(r.stdout)
    import asset_boundary
    save(O/'preservation.json',dict(trees=trees,source_files=source,strict_files=strict,consumed=consumed,
         claimed_sha256=sorted(claimed),protected=asset_boundary.verify(),genuine_launches=0))
    print('Consumed trees, sandboxes, global ledger, source state and strict failures preserved.',flush=True)


def stage():
    core.require((O/'preservation.json').exists() and not RT.exists(),'fresh preserved staging required')
    shutil.copytree(PRIOR/'runtime',RT)
    shutil.copy2(H/'setres_evidence.inc',RT/'setres_evidence.inc')
    p=RT/'xrt_loader.c';before=p.read_text()
    old='void xrt_icall(CPU* c, uint32_t target, uint32_t site) { dispatch(c, target, site, "indirect call"); }'
    core.require(before.count(old)==1,'dispatcher anchor')
    after=before.replace(old,'#include "setres_evidence.inc"\n'+(H/'icall.inc').read_text().strip())
    p.write_text(after)
    (O/'runtime.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='consumed/xrt_loader.c',tofile='fresh/xrt_loader.c')))
    original=core.tree(PRIOR/'runtime');fresh=core.tree(RT)
    core.require([k for k in original if original[k]!=fresh[k]]==['xrt_loader.c'],'runtime scope changed')
    core.require(set(fresh)-set(original)=={'setres_evidence.inc'},'unexpected new runtime file')
    save(O/'source-change.json',dict(passed=True,changed=['xrt_loader.c'],added=['setres_evidence.inc'],
         rationale='Persist call-aware raw CPU/frame evidence before SetRes function-entry assertions, with paired return evidence. No guest CPU/result/configuration or renderer allowlist changes.',
         runtime=fresh,genuine_launches=0))
    print('Staged evidence-only dispatcher change; all renderer sources byte-identical.',flush=True)


def build():
    core.require(read(O/'instrumentation-validation.json')['passed'],'instrumentation fixtures required before candidate build')
    b=read(PRIOR/'build.json');previous=pathlib.Path(b['root']);origin=read(PRIOR/'object-lineage.json')
    core.require(core.tree(previous)==b['outputs'] and core.tree(W/'experiments/xrt/gen')==b['generated'],'consumed build/generated identity')
    target=W/'experiments/xrt/build/setres-initial-completion-20261029-01'/str(uuid.uuid4());target.mkdir(parents=True)
    helper=load('initial_setres_build_tools',H.parent/'getobject_boundary/phase.py');helper.O=O/'client-build';helper.O.mkdir();env=helper.env()
    lineage={};copied={};changed='obj/rt/xrt_loader.obj'
    for rel,row in origin.items():
        core.require(core.sha(previous/rel)==row['object_sha256'] and core.sha(row['source'])==row['source_sha256'],'inherited object/source identity')
        for path,digest in row.get('verified_local_headers',{}).items():core.require(core.sha(path)==digest,'inherited header identity')
        if rel==changed:continue
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest)
        copied[rel]=core.sha(dest)
        lineage[rel]=dict(row,reused=True,reused_in_this_candidate=True,inherited_from=str(PRIOR/'object-lineage.json'))
    cmd=origin[changed]['command']
    old_source=pathlib.Path(origin[changed]['source']);old_output=pathlib.Path(next(s[3:] for s in cmd if s.startswith('/Fo')))
    cmd=[s.replace(str(old_source.parent),str(RT)).replace(str(old_output.parent),str(target/'obj/rt')) for s in cmd]
    helper.run(cmd,'xrt_loader',cwd=W/'experiments/xrt',environment=env,timeout=60)
    obj=target/changed
    lineage[changed]=dict(source=str(RT/'xrt_loader.c'),source_sha256=core.sha(RT/'xrt_loader.c'),object_sha256=core.sha(obj),command=cmd,
         reused=False,reused_in_this_candidate=False,verified_local_headers={str(RT/n):digest for n,digest in core.tree(RT).items() if n.endswith(('.h','.inc'))})
    link=[s.replace(str(previous),str(target)) for s in b['commands'][-1]['command']]
    (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
    helper.run(link,'link',cwd=W/'experiments/xrt',environment=env,timeout=60)
    core.require(len(copied)==278 and len(lineage)==279,'object census')
    save(O/'object-lineage.json',lineage)
    save(O/'build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),generated=b['generated'],
         binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),compiled_objects=1,reused_objects=278,reused_object_hashes=copied,
         commands=[read(helper.O/(n+'.json')) for n in ('xrt_loader','link')],inherited_build=str(PRIOR/'build.json'),inherited_build_sha256=core.sha(PRIOR/'build.json'),
         toolchain=b['toolchain'],gamma_profile=b['gamma_profile'],genuine_launches=0,execution_authorized=False))
    print('Fresh candidate built from genuine dispatcher instrumentation change and 278 verified inherited objects.',flush=True)


def verify_preservation():
    p=read(O/'preservation.json')
    for root,expected in p['trees'].items():core.require(core.tree(pathlib.Path(root))==expected,'preserved tree changed: '+root)
    for path,digest in {**p['source_files'],**p['strict_files']}.items():core.require(core.sha(path)==digest,'preserved source/failure changed: '+path)
    extended=read(O/'preservation-extended.json')
    for root,expected in extended['trees'].items():core.require(core.tree(pathlib.Path(root))==expected,'additional consumed build changed: '+root)
    import asset_boundary
    core.require(asset_boundary.verify()==p['protected'],'protected originals/saves changed')
    save(O/'preservation-after.json',dict(passed=True,trees=len(p['trees']),source_files=len(p['source_files']),
         protected_equal=True,ledger_unchanged=True,genuine_launches=0,production_stop_changes=0))


def extend_preservation():
    core.require(not (O/'preservation-extended.json').exists(),'retain extended preservation')
    p=read(O/'preservation.json');candidates={}
    for path in (W/'out/recovery').rglob('launch.json'):
        try:d=read(path);exe=pathlib.Path(d.get('executable',''))
        except (ValueError,TypeError):continue
        if exe.name=='xrt_ucc.exe' and exe.is_file():candidates[str(exe)]=core.sha(exe)
    for path in (core.HOME/'candidates').glob('*.json'):
        d=read(path)
        if d.get('sha256') in p['claimed_sha256']:
            exe=W/d['executable'];core.require(core.sha(exe)==d['sha256'],'claimed historical identity changed')
            candidates[str(exe)]=d['sha256']
    core.require(set(p['claimed_sha256']).issubset(set(candidates.values())),'historical claimed candidate missing')
    roots={str(pathlib.Path(exe).parent) for exe in candidates if str(pathlib.Path(exe).parent) not in p['trees']}
    save(O/'preservation-extended.json',dict(passed=True,candidates=candidates,trees={root:core.tree(pathlib.Path(root)) for root in sorted(roots)},
         all_global_claimed_candidates_accounted=True,genuine_launches=0))
    print('All six globally consumed identities plus earlier launched builds accounted for and preserved.',flush=True)


if __name__=='__main__':
    core.require(sys.argv[1:] in (['preserve'],['stage'],['build'],['verify_preservation'],['extend_preservation']),'preparation subcommand')
    globals()[sys.argv[1]]()
