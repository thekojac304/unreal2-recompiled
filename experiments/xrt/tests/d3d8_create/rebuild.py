"""Fresh serial runtime rebuild, reusing verified generated objects from the full build."""
import importlib.util,json,re,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import preserve as P
W,O,F=P.W,P.O,P.F
OLD=W/'experiments/xrt/build/d3d8-create-20261025-01';B=W/'experiments/xrt/build/d3d8-create-20261025-02'
b=F.read(O/'build.json');assert b['status']=='PASS';F.P.check(OLD,b['outputs'])
now=P.tree(W/'experiments/xrt/runtime');assert {p for p in now if now[p]!=b['sources']['experiments/xrt/runtime'][p]}=={'hle_d3d8_device.inc'}
assert P.tree(W/'experiments/xrt/gen')==b['sources']['experiments/xrt/gen']
if B.exists():assert all(p.suffix=='.obj'for p in B.rglob('*')if p.is_file()),'only the preserved pre-compilation object copy may resume'
else:B.mkdir()
copied={}
for rel,h in b['outputs'].items():
    if rel.endswith('.obj')and not rel.startswith('obj/rt/'):
        d=B/rel;d.parent.mkdir(parents=True,exist_ok=True)
        if not d.exists():shutil.copy2(OLD/rel,d)
        assert P.sha(d)==h;copied[rel]=h
assert len(copied)==265
(B/'link-objects.rsp').write_text((OLD/'link-objects.rsp').read_text().replace(str(OLD),str(B)))
s=importlib.util.spec_from_file_location('env',W/'out/recovery/postram-20261024-174304-d3a9040d/phase.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E);E.OUT=O;env=E.environment()
rec=dict(status='BUILDING',sources={p:P.tree(W/p)for p in ['experiments/xrt/runtime','experiments/xrt/gen','tools/xrt']},commands=[],compiled_objects=0,reused_objects=265,reused_object_hashes=copied,full_build_identity=P.sha(O/'build.json'),full_build=str(OLD),warnings=[])
for template in b['commands']:
    if template['name']!='link' and not template['name'].startswith('compile-hle_')and template['name']not in ['compile-'+p.stem for p in(W/'experiments/xrt/runtime').glob('xrt_*.c')]:continue
    name=template['name'];cmd=[v.replace(str(OLD),str(B))for v in template['command']]
    if name!='link':Path(next(v[3:]for v in cmd if v.startswith('/Fo'))).parent.mkdir(parents=True,exist_ok=True)
    log=B/(name+'.log');t=time.monotonic()
    with log.open('wb')as f:r=subprocess.run(cmd,cwd=W/'experiments/xrt',env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
    text=log.read_text(errors='replace');assert not re.search(r'\b(?:C1001|D8040)\b',text)and r.returncode==0,(name,text)
    rec['commands'].append(dict(name=name,command=cmd,exit=r.returncode,seconds=time.monotonic()-t,log_sha256=P.sha(log)));rec['compiled_objects']+=name!='link';rec['warnings']+=re.findall(r'^.*warning [A-Z]+\d+.*$',text,re.M);P.save('build-02.json',rec);print(name,flush=True)
assert rec['compiled_objects']==14
assert all(P.tree(W/p)==h for p,h in rec['sources'].items())
rec.update(status='PASS',binary_sha256=P.sha(B/'xrt_ucc.exe'),outputs={p.relative_to(B).as_posix():P.sha(p)for p in B.rglob('*')if p.is_file()and p.suffix in ['.obj','.pdb','.exe','.ilk']})
P.save('build-02.json',rec);print('SERIAL REBUILD PASS',rec['binary_sha256'],flush=True)
