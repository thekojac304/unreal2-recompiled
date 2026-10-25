"""Same x86 DLL: complete POINT bytes, packed displacement, errors, and ABI."""
import json,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[4];B=W/'experiments/xrt/build/mapwindowpoints_boundary_02';rows=[]
for mode in ['positive','wrong-type','count-zero','bad-points']:
    runs=[];report=B/(mode+'-report.json')
    for side in ['native','translated']:
        cmd=[str(B/(side+'.exe')),str(B/'mapprobe.dll'),mode,str(report)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (B/(side+'-'+mode+'.txt')).write_text(p.stdout+p.stderr);runs.append(dict(side=side,command=cmd,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
    n,t=runs;assert n['exit']==0,runs;d=json.loads(report.read_text());assert d['events_dropped']==0
    calls=[e for e in d['events']if e['kind']=='gui_map_points_call'];rets=[e for e in d['events']if e['kind']=='gui_map_points_return']
    if mode=='positive':
        assert t['exit']==0 and n['stdout']==t['stdout'] and t['stdout'].endswith('failures=0\n'),runs
        assert len(calls)==len(rets)==627
        for c,r in zip(calls,rets):assert r['esp_before']==c['esp'] and r['esp_after']==c['esp']+20 and r['actual_return']==c['return']
        assert 'mapping=1-to-0 map n=2 pattern=0' in n['stdout']
        assert 'mapping=3-to-1 map n=2' in n['stdout'] and n['stdout'].count('error=00000578')==27
    else:
        assert t['exit']==76 and len(calls)==1 and not rets,runs
        assert {'wrong-type':'wrong HWND token type','count-zero':'unmeasured point count','bad-points':'invalid guest point array'}[mode]in t['stderr']
        if mode=='bad-points':assert 'exception=c0000005' in n['stdout'],runs
    rows.append(dict(mode=mode,passed=True,runs=runs,events_recorded=d['events_recorded'],events_dropped=0))
(B/'results.json').write_text(json.dumps(dict(passed=True,paired_calls=627,explicit_unsupported=3,runs=rows),indent=2))
print('MapWindowPoints native/translated PASS: 627 paired queries; exact genuine rectangle, screen/child/mirrored spaces, 1..4 points, packed delta, output guards, invalid/dead HWND, last-error, ABI; three explicit unsupported cases')
