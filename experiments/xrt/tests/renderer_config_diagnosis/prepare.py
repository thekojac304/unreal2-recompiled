"""Isolated exact profile correction and justified fresh candidate build."""
import difflib
import pathlib
import shutil
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def stage():
    core.require(read(O/'boolean-characterization.json')['passed'] and not RT.exists(),'independent characterization and fresh runtime required')
    profile=read(PRIOR/'configuration-profile.json');core.require(profile['fields']['0x40d0']==1,'prior profile changed')
    original=core.digest(profile)
    profile['fields']['0x40d0']=32
    profile['measurement_revision']=dict(changed_only='fields[0x40d0]: 1 -> 32',original_profile_sha256=core.sha(PRIOR/'configuration-profile.json'),
        measured_renderer_entry=str(O/'renderer-fields.json'),characterization=str(O/'boolean-characterization.json'),
        semantic_change='none: UseTrilinear remains enabled, sampler MIPFILTER remains 2',unknown_configurations='diagnostic stop; exact raw 0x20 only')
    save(O/'configuration-profile.json',profile)
    shutil.copytree(LAST/'runtime',RT)
    p=RT/'integrated_renderer.inc';before=p.read_text();old='if(rd32(r+0x40d0)!=1u)'
    core.require(before.count(old)==1,'exact stale raw field guard')
    after=before.replace(old,'if(rd32(r+0x40d0)!=32u)');p.write_text(after)
    (O/'runtime.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='consumed/integrated_renderer.inc',tofile='fresh/integrated_renderer.inc')))
    parent=core.tree(LAST/'runtime');fresh=core.tree(RT)
    core.require([n for n in parent if parent[n]!=fresh[n]]==['integrated_renderer.inc'],'unrelated runtime change')
    core.require(core.sha(RT/'batch_cases.inc')==core.sha(LAST/'runtime/batch_cases.inc'),'native tuple profile changed')
    save(O/'source-change.json',dict(passed=True,changed=['integrated_renderer.inc'],compiled_translation_unit='hle_gui.c',
        rationale='Replace unmeasured canonical Boolean assumption with measured exact UseTrilinear raw 0x20; retain identical native sampler tuple2 and all unsupported traps',
        runtime=fresh,profile_before_digest=original,raw_boolean_acceptance='only 0x20; raw1/2/64 are not accepted',allowlist_broadened=False,genuine_launches=0))
    print('Staged one exact raw field guard/profile correction; native tuples and all other runtime files unchanged.',flush=True)


def build():
    core.require(read(O/'runtime-guard-validation.json')['passed'],'runtime guard fixtures required')
    b=read(LAST/'build.json');previous=pathlib.Path(b['root']);origin=read(LAST/'object-lineage.json')
    core.require(core.tree(previous)==b['outputs'] and core.tree(W/'experiments/xrt/gen')==b['generated'],'consumed build/generated identity')
    target=W/'experiments/xrt/build/renderer-config-diagnosis-20261029-01'/str(uuid.uuid4());target.mkdir(parents=True)
    helper=load('renderer_config_build_tools',H.parent/'getobject_boundary/phase.py');helper.O=O/'client-build';helper.O.mkdir();env=helper.env()
    lineage={};copied={};changed='obj/rt/hle_gui.obj'
    for rel,row in origin.items():
        core.require(core.sha(previous/rel)==row['object_sha256'] and core.sha(row['source'])==row['source_sha256'],'inherited object/source identity')
        for path,digest in row.get('verified_local_headers',{}).items():core.require(core.sha(path)==digest,'inherited header identity')
        if rel==changed:continue
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest);copied[rel]=core.sha(dest)
        lineage[rel]=dict(row,reused=True,reused_in_this_candidate=True,inherited_from=str(LAST/'object-lineage.json'))
    cmd=origin[changed]['command'];old_source=pathlib.Path(origin[changed]['source']);old_output=pathlib.Path(next(s[3:] for s in cmd if s.startswith('/Fo')))
    cmd=[s.replace(str(old_source.parent),str(RT)).replace(str(old_output.parent),str(target/'obj/rt')) for s in cmd]
    helper.run(cmd,'hle_gui',cwd=W/'experiments/xrt',environment=env,timeout=60)
    lineage[changed]=dict(source=str(RT/'hle_gui.c'),source_sha256=core.sha(RT/'hle_gui.c'),object_sha256=core.sha(target/changed),command=cmd,
        reused=False,reused_in_this_candidate=False,verified_local_headers={str(RT/n):v for n,v in core.tree(RT).items() if n.endswith(('.h','.inc'))})
    link=[s.replace(str(previous),str(target)) for s in b['commands'][-1]['command']]
    (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
    helper.run(link,'link',cwd=W/'experiments/xrt',environment=env,timeout=60)
    core.require(len(lineage)==279 and len(copied)==278,'object census')
    save(O/'object-lineage.json',lineage)
    save(O/'build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),generated=b['generated'],
        binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),compiled_objects=1,reused_objects=278,reused_object_hashes=copied,
        commands=[read(helper.O/(n+'.json')) for n in ('hle_gui','link')],inherited_build=str(LAST/'build.json'),inherited_build_sha256=core.sha(LAST/'build.json'),
        toolchain=b['toolchain'],gamma_profile=b['gamma_profile'],genuine_launches=0,execution_authorized=False))
    print('Fresh source-justified candidate built; consumed executable was not run.',flush=True)


if __name__=='__main__':
    core.require(sys.argv[1:] in (['stage'],['build']),'preparation command');globals()[sys.argv[1]]()
