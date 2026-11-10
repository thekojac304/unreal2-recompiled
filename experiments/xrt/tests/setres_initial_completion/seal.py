"""Seal qualified preparation; does not authorize or launch the game."""
import ast
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def seal():
    core.require(not (O/'seal.json').exists(),'retain existing seal')
    from package import gates
    gates()
    from mapping import resolve
    core.require(resolve()==read(O/'stop-mapping.json'),'exact PE/PDB mapping changed')
    from prepare import verify_preservation
    verify_preservation()
    fixture=read(PRIOR/'fixture-validation.json')
    core.require(fixture['passed'] and fixture['runtime']==core.tree(PRIOR/'runtime') and fixture['result']['positive_calls']==24 and fixture['result']['negative_guards']==6,'retained self-thread USER32 guards incomplete')
    core.require(core.sha(RT/'hle_gui.c')==core.sha(PRIOR/'runtime/hle_gui.c'),'cross-thread guards changed')
    from supervisor.service import seal_files
    from supervisor.qualify import host_files
    from supervisor import fixture_profiles
    fixture_profiles.modules()
    import graphics_backend,retained_audit,owner
    from gamma_guard import DesktopGamma
    def class_text(source):return ast.get_source_segment(source,next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='DesktopGamma'))
    core.require(class_text((H/'gamma_guard.py').read_text())==class_text((H.parent/'renderer_prerequisites/service.py').read_text()),'gamma restoration guard changed')
    files={str(W/p):v for p,v in seal_files().items()}
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=pathlib.Path(name).absolute()
            if path.is_file() and path.is_relative_to(W):files[str(path)]=core.sha(path)
    for root in (H,O,EXE.parent,RT,PRIOR/'runtime',W/'experiments/xrt/gen'):
        for p,digest in core.tree(root).items():files[str(root/p)]=digest
    b=read(O/'build.json');ci=read(O/'candidate-identity.json')
    records={str(O/'object-lineage.json'),*ci['transitive_object_records']}
    for record in records:
        files[record]=core.sha(record)
        for value in read(record).values():
            if not isinstance(value,dict) or 'command' not in value:continue
            files[value['source']]=value['source_sha256']
            files.update(value.get('verified_local_headers',{}))
            output=next((a[3:] for a in value['command'] if a.startswith('/Fo')),None)
            if output:files[output]=value['object_sha256']
    for path,digest in {**ci['dependencies'],**b['toolchain'],**host_files()}.items():files[path]=digest
    for name in ('build.json','object-lineage.json','fixture-validation.json','configuration-profile.json','physical-gamma-audit.json','actual-gamma-ramp.bin'):
        files[str(PRIOR/name)]=core.sha(PRIOR/name)
    for path,digest in fixture['sources'].items():files[path]=digest
    for p,digest in core.tree(pathlib.Path(fixture['root'])).items():files[str(pathlib.Path(fixture['root'])/p)]=digest
    for path,digest in read(O/'resolved-hold.json')['evidence'].items():files[path]=digest
    save(O/'seal.json',dict(passed=True,scope=SCOPE,candidate_sha256=SHA,pdb_sha256=PDB,guest_stop=GUEST,stop_rva=RVA,stop_bytes=read(O/'stop-mapping.json')['stop_bytes'],
         maximum_launches=1,maximum_seconds=60,retry=False,genuine_authorized=False,genuine_launches=0,
         owner_phrase=PHRASE,separate_stop_phrase=STOP_PHRASE,separate_owner_stop_authorization_pending=True,
         implementation=core.tree(H),files=files,dependencies=ci['dependencies'],strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained'))
    owner.validate_seal();owner.execution_gate()
    save(O/'seal-validation.json',dict(passed=True,files=len(files),seal_sha256=core.sha(O/'seal.json'),
         candidate_unconsumed=True,genuine_launches=0,genuine_authorized=False,local_owner_authorization_pending=True,
         separate_stop_authorization_pending=True,production_stop_unchanged=True,ready_for_separate_owner_action=True))
    print('SEALED: ready for separate local stop-scope and one-shot owner authorization. Zero genuine launches.',flush=True)


if __name__=='__main__':seal()
