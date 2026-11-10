"""Fresh serial runtime build using explicitly hash-verified unchanged client/Engine objects."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import asset_boundary as A
import run_xrt as R
from fresh_checkpoint import hashes
WS=Path(R.WS)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proof',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();proof=json.loads(a.proof.read_text());source=Path(proof['build']);out=a.out.resolve()
    out.relative_to(WS/'experiments/xrt/build')
    if out.exists():raise RuntimeError('fresh output directory required')
    old=json.loads((source/'client-identity.json').read_text())
    assert A.sha(source/'client-identity.json')==proof['identity_sha256']
    assert old['runtime']==proof['runtime']
    current_headers={p:h for p,h in hashes(WS/'experiments/xrt/runtime').items() if p.endswith('.h')}
    assert current_headers==proof['headers'],'changed compilation headers require full rebuild'
    assert R.tree_digest(str(WS/'experiments/xrt/gen'))==old['generated']
    assert R.file_identity(source/'xrt_ucc.exe')==old['binary']
    assert hashes(source/'obj')==old['objects']
    base=WS/old['base_identity']['path']
    cmd=[sys.executable,'-I',str(WS/'tools/xrt/client_identity.py'),'--base',str(base.parent),'--out',str(out)]
    before=A.verify();subprocess.run(cmd,cwd=WS,check=True)
    copied={}
    for folder in ['client','engine']:
        shutil.copytree(source/'obj'/folder,out/'obj'/folder)
        copied.update({folder+'/'+p:h for p,h in hashes(out/'obj'/folder).items()})
    assert all(old['objects'][p]==h for p,h in copied.items())
    (out/'obj/rt').mkdir()
    vc=r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat'
    rt=out/'obj/rt'
    script=out/'runtime-build.cmd'
    script.write_text('\n'.join(['@echo off',f'call "{vc}" x64 >nul || exit /b 1',
        f'cd /d "{WS / "experiments/xrt"}"',
        f'cl /nologo /c /O2 /Zi /fp:strict /W4 /wd4100 /wd4201 /wd4127 /wd4324 /D_CRT_SECURE_NO_WARNINGS /DXRT_WITH_UNREAL2 /errorReport:none /Iruntime /Fo"{rt}\\\\" /Fd"{rt}\\\\" runtime\\*.c || exit /b 1',
        f'link /nologo /DEBUG /STACK:0x10000000 /OUT:"{out / "xrt_ucc.exe"}" @"{out / "base-objects.rsp"}" "{out / "obj/engine"}\\*.obj" "{out / "obj/client"}\\*.obj" "{rt}\\*.obj" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib || exit /b 1','']))
    with (out/'runtime-build.txt').open('wb') as f:
        subprocess.run(['cmd','/d','/c',str(script)],cwd=WS,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
    subprocess.run(cmd+['--record'],cwd=WS,check=True)
    assert current_headers=={p:h for p,h in hashes(WS/'experiments/xrt/runtime').items() if p.endswith('.h')}
    assert A.verify()==before
    (out/'reuse.json').write_text(json.dumps(dict(source_identity=R.file_identity(source/'client-identity.json'),
        proof=R.file_identity(a.proof),copied_objects=copied,runtime_build_script=R.file_identity(script),
        driver=R.file_identity(Path(__file__)),integrity=before),indent=2))
    print(out,flush=True)
    return 0
if __name__=='__main__':sys.exit(main())
