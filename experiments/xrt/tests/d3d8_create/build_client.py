"""Rebuild all 279 accepted translation/runtime objects serially into a fresh tree."""
import importlib.util,json,os,re,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import preserve as P
W,O,F=P.W,P.O,P.F
B=W/'experiments/xrt/build/d3d8-create-20261025-01'
def main():
    assert not B.exists();B.mkdir();before=F.read(O/'preflight.json')
    assert P.tree(W/'experiments/xrt/gen')==before['generated']
    F.P.check(F.B,F.read(P.Q/'build.json')['outputs'])
    s=importlib.util.spec_from_file_location('env',W/'out/recovery/postram-20261024-174304-d3a9040d/phase.py')
    E=importlib.util.module_from_spec(s);s.loader.exec_module(E);E.OUT=O;env=E.environment()
    full=F.read(W/'out/recovery/setcapture-20261024-01/build-history/setcapture-20261024-01.json')
    base=W/'experiments/xrt/build/setcapture-20261024-01';old=F.B
    (B/'link-objects.rsp').write_text((old/'link-objects.rsp').read_text().replace(str(old),str(B)))
    sources={p:P.tree(W/p)for p in ['experiments/xrt/runtime','experiments/xrt/gen','tools/xrt']}
    rec=dict(status='BUILDING',commands=[],sources=sources,compiled_objects=0,reused_objects=0)
    P.save('build.json',rec);warnings=[]
    for template in full['commands']:
        name=template['name'];cmd=[v.replace(str(base),str(B))for v in template['command']]
        if name!='link':
            target=Path(next(v[3:]for v in cmd if v.startswith('/Fo')));target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists()
        log=B/(name+'.log');start=time.monotonic()
        with log.open('wb')as f:r=subprocess.run(cmd,cwd=W/'experiments/xrt',env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
        txt=log.read_text(errors='replace');rec['commands'].append(dict(name=name,command=cmd,exit=r.returncode,seconds=time.monotonic()-start,log_sha256=P.sha(log)))
        rec['compiled_objects']+=name!='link';warnings+=re.findall(r'^.*warning [A-Z]+\d+.*$',txt,re.M);P.save('build.json',rec)
        assert r.returncode==0 and not re.search(r'\b(?:C1001|D8040)\b',txt),('STOP compiler/linker',name,txt)
        print(len(rec['commands']),'/280',name,flush=True)
    assert all(P.tree(W/p)==d for p,d in sources.items()),'source changed during build'
    outputs={p.relative_to(B).as_posix():P.sha(p)for p in B.rglob('*')if p.is_file()and p.suffix in ['.obj','.pdb','.exe','.ilk']}
    assert sum(p.endswith('.obj')for p in outputs)==rec['compiled_objects']==279
    rec.update(status='PASS',warnings=warnings,outputs=outputs,binary_sha256=P.sha(B/'xrt_ucc.exe'),driver_sha256=P.sha(__file__))
    P.save('build.json',rec);print('FULL SERIAL BUILD PASS',rec['binary_sha256'],flush=True)
if __name__=='__main__':main()
