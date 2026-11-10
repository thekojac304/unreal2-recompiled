"""Additive preservation and integrity gate for the production CreateDevice phase."""
import importlib.util,json,shutil,sys,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[4]
O=W/'out/recovery/d3d8-create-20261025-01'
Q=W/'out/recovery/d3d8-depth-20261025-01'
s=importlib.util.spec_from_file_location('depth',Q/'phase.py')
F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
sha,tree=F.sha,F.tree
def git(*a):return subprocess.check_output(['git',*a],cwd=W)
def save(n,v):(O/n).write_text(json.dumps(v,indent=2))
def preflight():
    O.mkdir(parents=True,exist_ok=True);assert not(O/'preflight.json').exists()
    F.verify();b=F.read(Q/'build.json');F.P.check(F.B,b['outputs'])
    assert sha(F.B/'xrt_ucc.exe')=='74866a16b8e1dfd5b7feaa609c56538cd469bc4ee632c95a4cc829830c2d693a'
    assert tree(W/'experiments/xrt/gen')==b['sources']['experiments/xrt/gen']
    paths={p.decode()for p in(git('ls-files','-z')+git('ls-files','--others','--exclude-standard','-z')).split(b'\0')if p}
    working={}
    for rel in sorted(paths):
        if not(W/rel).is_file():continue
        dest=O/'source-preservation'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(W/rel,dest);working[rel]=sha(W/rel);assert sha(dest)==working[rel]
    (O/'unstaged-before.patch').write_bytes(git('diff','--binary'))
    (O/'staged-before.patch').write_bytes(git('diff','--cached','--binary'))
    save('preflight.json',dict(head=git('rev-parse','HEAD').decode().strip(),status=git('status','--porcelain=v1','--untracked-files=all').decode(),
        working=working,runtime=tree(W/'experiments/xrt/runtime'),generated=tree(W/'experiments/xrt/gen'),
        builds=tree(W/'experiments/xrt/build'),raw=tree(W/'experiments/xrt/results/raw'),previous=tree(W/'out/recovery/d3d8-device-20261025-01'),
        assets=F.P.A.verify(),accepted_binary=str(F.B/'xrt_ucc.exe'),accepted_sha256=sha(F.B/'xrt_ucc.exe')))
    print('PREFLIGHT PASS',flush=True)
def final():
    b=F.read(O/'preflight.json');F.verify();changed=[]
    assert tree(W/'experiments/xrt/gen')==b['generated']
    for key,root in [('builds',W/'experiments/xrt/build'),('raw',W/'experiments/xrt/results/raw'),('previous',W/'out/recovery/d3d8-device-20261025-01')]:F.P.check(root,b[key])
    for rel,h in b['working'].items():
        assert sha(O/'source-preservation'/rel)==h
        if sha(W/rel)!=h:changed.append(rel)
    allowed={'experiments/xrt/runtime/hle_d3d8.inc','experiments/xrt/runtime/hle_gui.c','experiments/xrt/runtime/xrt_internal.h','experiments/xrt/CURRENT_STATUS.md'}
    assert all(p in allowed or p.startswith('experiments/xrt/tests/d3d8_create/')for p in changed),changed
    assert sha(b['accepted_binary'])==b['accepted_sha256']
    assert git('rev-parse','HEAD').decode().strip()==b['head']=='8c6220a6baadd575340fa81e51e2fa0a2af86a8c'
    assert git('diff','--cached','--binary')==(O/'staged-before.patch').read_bytes()
    assert F.P.A.verify()==b['assets']
    save('final-integrity.json',dict(passed=True,changed=changed,preserved_working=len(b['working']),preserved_builds=len(b['builds']),preserved_raw=len(b['raw']),generated_unchanged=True,accepted_binary_unchanged=True,dependencies_verified=True,protected_assets=b['assets'],genuine_client_sessions=0,original_installation_or_saves_accessed=False))
    print('FINAL INTEGRITY PASS',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
