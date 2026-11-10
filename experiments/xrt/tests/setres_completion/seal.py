"""Seal the reviewable preparation. Does not authorize or launch a game."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import ast
from common import *


def seal():
    core.require(not (O/'seal.json').exists(),'existing qualification seal must be preserved')
    for name in ('candidate-identity.json','debugger-validation.json','controller-tests-final.json','supervisor-tests.json',
                 'helper-qualification.json','preservation-after.json','cache-control-flow/result.json'):
        core.require(read(O/name).get('passed') is True,'qualification failed: '+name)
    from supervisor.service import seal_files
    from supervisor.qualify import host_files
    from supervisor import fixture_profiles
    from gamma_guard import DesktopGamma
    # Load the retained guard's read-only collectors before collecting its full
    # import closure. Merely loading these modules performs no desktop changes.
    fixture_profiles.modules()
    import graphics_backend
    import retained_audit
    original=(W/'experiments/xrt/tests/renderer_prerequisites/service.py').read_text()
    copied=(H/'gamma_guard.py').read_text()
    def class_text(s):return ast.get_source_segment(s,next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='DesktopGamma'))
    core.require(class_text(original)==class_text(copied),'parent restoration guard changed')
    files={str(W/p):v for p,v in seal_files().items()}
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=pathlib.Path(name).absolute()
            if path.is_file() and path.is_relative_to(W):files[str(path)]=core.sha(path)
    for root in (H,O,EXE.parent,PRIOR/'runtime',W/'experiments/xrt/gen'):
        for p,digest in core.tree(root).items():files[str(root/p)]=digest
    b=read(PRIOR/'build.json')
    files[str(PRIOR/'build.json')]=core.sha(PRIOR/'build.json')
    files[str(PRIOR/'object-lineage.json')]=core.sha(PRIOR/'object-lineage.json')
    lineage_paths={str(PRIOR/'object-lineage.json'),*read(O/'candidate-identity.json')['transitive_object_records']}
    for record in lineage_paths:
        for v in read(record).values():
            if not isinstance(v,dict) or 'command' not in v:continue
            for name,digest in v.get('verified_local_headers',{}).items():files[name]=digest
            path=next((a[3:] for a in v['command'] if a.startswith('/Fo')),None)
            if path:files[path]=v['object_sha256']
    for path,digest in read(O/'candidate-identity.json')['transitive_object_records'].items():files[path]=digest
    for path,digest in read(O/'candidate-identity.json')['dependencies'].items():files[path]=digest
    for path,digest in b['toolchain'].items():files[path]=digest
    files.update(host_files())
    result=dict(passed=True,scope=SCOPE,candidate_sha256=SHA,pdb_sha256=PDB,guest_stop=GUEST,stop_rva=RVA,stop_bytes='897b44',
        maximum_launches=1,maximum_seconds=60,retry=False,genuine_authorized=False,genuine_launches=0,
        owner_phrase=PHRASE,implementation=core.tree(H),files=files,
        dependencies=read(O/'candidate-identity.json')['dependencies'],strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained')
    save(O/'seal.json',result)
    owner=load('setres_owner_readiness_check',H/'owner.py')
    owner.validate_seal()
    # This is read-only; it also verifies the live global consumed ledger and
    # existing holds. It does not create a batch, reserve a slot, or touch locks.
    owner.execution_gate()
    save(O/'seal-validation.json',dict(passed=True,files=len(files),seal_sha256=core.sha(O/'seal.json'),
        local_owner_authorization_pending=True,genuine_launches=0,production_stop=0x696f292))
    print('SEALED AND READY FOR SEPARATE LOCAL OWNER AUTHORIZATION; ZERO GENUINE LAUNCHES',flush=True)


if __name__=='__main__':seal()
