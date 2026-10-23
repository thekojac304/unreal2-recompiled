"""Fresh isolated processes: actual native HRESULT/refcount/identity versus lifted PE32 client."""
import json,subprocess,uuid,hashlib
from pathlib import Path
WS=Path(__file__).resolve().parents[4]
B=WS/'experiments/xrt/build/directmusic_com'
OUT=WS/'experiments/xrt/results/raw/directmusic'/('com-'+uuid.uuid4().hex[:12])
OUT.mkdir(parents=True)
runs=[];ok=True
for probe in ['probe_sta','probe_mta','probe_loader','probe_uninitialized','probe_cleanup','probe_worker']:
    pair=[]
    for arch in ['native','translated']:
        cmd=([str(B/'native.exe'),str(B),str(B/'comprobe.dll')] if arch=='native' else
             [str(B/'translated.exe'),str(B/'comprobe.dll'),str(OUT/(probe+'.json'))])+[probe]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        pair.append(dict(arch=arch,command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    good=all(r['exit']==0 and f'{probe} returned 0 log ' in r['stdout'] for r in pair) and pair[0]['stdout']==pair[1]['stdout']
    ok &= good;runs+=pair;print(probe,'PASS' if good else 'FAIL',pair[1]['stdout'].strip())
    if not good:print(pair)
    if probe in ['probe_cleanup','probe_worker']:
        t=json.loads((OUT/(probe+'.json')).read_text())
        refs=3 if probe=='probe_cleanup' else 2
        owner=0 if probe=='probe_cleanup' else 1
        ok &= any(e['kind']=='com_cleanup' and e['thread']==owner and e['references_released']==refs and e['apartment_references_balanced']==2 for e in t['events'])
for probe,message in [('probe_stale','stale or unknown'),('probe_unsupported','IDirectMusicLoader8::GetObject is unsupported'),
                      ('probe_unbalanced','no apartment reference'),('probe_wrong_thread','owning host apartment')]:
    cmd=[str(B/'translated.exe'),str(B/'comprobe.dll'),str(OUT/(probe+'.json')),probe]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    good=r.returncode==76 and message in r.stderr;ok &= good
    runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr));print(probe,'PASS' if good else 'FAIL')
record={'pass':ok,'runs':runs,'binaries':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [B/'native.exe',B/'translated.exe',B/'comprobe.dll']}}
(OUT/'result.json').write_text(json.dumps(record,indent=2));(B/'latest.json').write_text(json.dumps({'evidence':str(OUT.relative_to(WS))}))
print(OUT);raise SystemExit(0 if ok else 1)
