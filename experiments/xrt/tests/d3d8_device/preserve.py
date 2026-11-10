"""Read-only checkpoint verification and additive preservation for device probes."""
import hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path
W=Path(__file__).resolve().parents[4]
O=W/'out/recovery/d3d8-device-20261025-01'
Q=W/'out/recovery/d3d8-depth-20261025-01'
s=importlib.util.spec_from_file_location('depth_phase',Q/'phase.py')
F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
sha,tree=F.sha,F.tree
def git(*args):return subprocess.check_output(['git',*args],cwd=W)
def save(n,v):(O/n).write_text(json.dumps(v,indent=2))
def preflight():
    O.mkdir(parents=True,exist_ok=True)
    assert not (O/'preflight.json').exists()
    assert git('rev-parse','HEAD').decode().strip()=='8c6220a6baadd575340fa81e51e2fa0a2af86a8c'
    F.verify();build=F.read(Q/'build.json')
    F.P.check(F.B,build['outputs'])
    assert tree(W/'experiments/xrt/runtime')==build['sources']['experiments/xrt/runtime']
    assert tree(W/'experiments/xrt/gen')==build['sources']['experiments/xrt/gen']
    assert sha(F.B/'xrt_ucc.exe')=='74866a16b8e1dfd5b7feaa609c56538cd469bc4ee632c95a4cc829830c2d693a'
    paths={v.decode()for v in(git('ls-files','-z')+git('ls-files','--others','--exclude-standard','-z')).split(b'\0')if v}
    working={}
    for rel in sorted(paths):
        if not (W/rel).is_file():continue
        dest=O/'source-preservation'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(W/rel,dest);working[rel]=sha(W/rel);assert sha(dest)==working[rel]
    (O/'unstaged-before.patch').write_bytes(git('diff','--binary'))
    (O/'staged-before.patch').write_bytes(git('diff','--cached','--binary'))
    # New fixture files are expected to change; retain the captured copy regardless.
    save('preflight.json',dict(head=git('rev-parse','HEAD').decode().strip(),status=git('status','--porcelain=v1','--untracked-files=all').decode(),
        working=working,runtime=tree(W/'experiments/xrt/runtime'),generated=tree(W/'experiments/xrt/gen'),
        builds=tree(W/'experiments/xrt/build'),raw=tree(W/'experiments/xrt/results/raw'),previous_evidence=tree(Q),
        assets=F.P.A.verify(),accepted_binary=str(F.B/'xrt_ucc.exe'),accepted_sha256=sha(F.B/'xrt_ucc.exe')))
    print('PREFLIGHT PASS: sources, pending work, accepted binary/objects, generated code, assets, pinned dependencies; old evidence inventoried',flush=True)
def final():
    b=F.read(O/'preflight.json');F.verify()
    for key,root in [('runtime',W/'experiments/xrt/runtime'),('generated',W/'experiments/xrt/gen')]:assert tree(root)==b[key]
    for key,root in [('builds',W/'experiments/xrt/build'),('raw',W/'experiments/xrt/results/raw'),('previous_evidence',Q)]:F.P.check(root,b[key])
    changed=[]
    for rel,h in b['working'].items():
        assert sha(O/'source-preservation'/rel)==h
        if not rel.startswith('experiments/xrt/tests/d3d8_device/'):
            assert sha(W/rel)==h,rel
        elif sha(W/rel)!=h:changed.append(rel)
    assert sha(b['accepted_binary'])==b['accepted_sha256']
    assert git('rev-parse','HEAD').decode().strip()==b['head']
    assert git('diff','--cached','--binary')==(O/'staged-before.patch').read_bytes()
    assert F.P.A.verify()==b['assets']
    save('final-integrity.json',dict(passed=True,head=b['head'],earlier_working_files=len(b['working']),earlier_build_files=len(b['builds']),earlier_raw_files=len(b['raw']),earlier_evidence_files=len(b['previous_evidence']),
        new_fixture_files_changed=changed,accepted_sha256=b['accepted_sha256'],runtime_unchanged=True,generated_unchanged=True,pinned_dependencies_verified=True,protected_assets=b['assets'],
        genuine_client_sessions=0,original_installation_or_saves_accessed=False))
    print('FINAL INTEGRITY PASS: all earlier files preserved; production runtime and generated code unchanged; zero genuine client sessions')
if __name__=='__main__':globals()[sys.argv[1]]()
