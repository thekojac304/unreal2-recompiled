"""Read-only acquisition of a consumed owner run. No launch entry point."""
import hashlib, importlib.util, json, shutil, subprocess, sys, zipfile
from pathlib import Path
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[4]
OLD=W/'out/recovery/getobject-recovery-20261028-01'
O=W/'out/recovery/postsplash-recovery-20261028-01'
B=W/'experiments/xrt/build/getobject-recovery-20261028-01/client'
SB=W/'sandbox_cmp/getobject-recovery-20261028-01'
R=W/'experiments/xrt/results/raw/level/20261028-051527-43a41550-candidate'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
def files(p):return sorted(f for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
def tree(p):return {f.relative_to(p).as_posix():sha(f) for f in files(p)}
def check(root,entries):
    for rel,h in entries.items():assert sha(root/rel)==h,('integrity',str(root),rel)
def archive(name,paths):
    manifest={}
    with zipfile.ZipFile(O/name,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for p in sorted(set(paths)):
            rel=p.relative_to(W).as_posix();h=sha(p);z.write(p,rel);assert sha(p)==h,rel;manifest[rel]=h
    with zipfile.ZipFile(O/name) as z:
        for rel,h in manifest.items():
            with z.open(rel) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==h,rel
    print('ARCHIVED AND VERIFIED',name,len(manifest),flush=True)
    return dict(path=name,sha256=sha(O/name),files=manifest)
def main():
    O.mkdir()
    check(OLD,read(OLD/'artifact-manifest.json'))
    check(W,read(OLD/'current-sources.json'))
    build=read(OLD/'build.json');check(B,build['outputs'])
    assert sha(B/'xrt_ucc.exe')=='695f9af04f7b39436cb011e5aea3e30004db0bcb9a29c441fce34f588881d52c'
    assert (OLD/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    sys.path.insert(0,str(W/'tools/xrt'));import asset_boundary
    assets=asset_boundary.verify();assert assets==read(OLD/'preservation.json')['protected_assets']
    sb=tree(SB);before=read(R/'meta.json')['before']
    changed={rel:dict(before=before.get(rel),after=sb.get(rel)) for rel in before.keys()|sb.keys() if before.get(rel)!=sb.get(rel)}
    def mutable(rel):
        s=rel.lower();return s.startswith(('save/','cache/')) or s=='system/golem.u' or (s.startswith('system/') and s.endswith(('.ini','.log')))
    assert all(mutable(rel) for rel in changed),changed
    save(O/'sandbox-manifest.json',dict(root=str(SB),files=sb,changed_since_launch=changed))
    for name,args in [('head',['rev-parse','HEAD']),('status',['status','--porcelain=v1','-uall']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
        (O/('git-'+name+'.txt')).write_bytes(subprocess.check_output(['git',*args],cwd=W))
    sources=[W/rel for rel in read(OLD/'current-sources.json')]
    sources+=files(W/'experiments/xrt/tests/postsplash_recovery')
    archives=[archive('source-state.zip',sources),archive('exact-build.zip',files(B)),
        archive('consumed-evidence.zip',files(OLD)+files(R)),archive('complete-sandbox.zip',files(SB))]
    evidence={f.relative_to(W).as_posix():sha(f) for f in files(OLD)+files(R)}
    save(O/'preservation.json',dict(passed=True,archives=archives,consumed_evidence=evidence,
        original_sources=read(OLD/'current-sources.json'),build=build,protected_assets=assets,sandbox_files=len(sb),sandbox_changes=changed,
        user_reported_visual='Owner saw Unreal II splash; no captured rendered game frame',genuine_sessions_launched=0))
    print('PRESERVATION PASS',flush=True)
if __name__=='__main__':main()
