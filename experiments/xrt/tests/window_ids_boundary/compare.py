"""Native x86 and identical translated DLL: HWND ownership, optional DWORD, ABI."""
import json,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[4];B=W/'experiments/xrt/build/window_ids_boundary';rows=[]
for mode in ['positive','wrong-type','bad-output']:
    runs=[];report=B/(mode+'-report.json')
    for side in ['native','translated']:
        cmd=[str(B/(side+'.exe')),str(B/'idprobe.dll'),mode,str(report)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (B/(side+'-'+mode+'.txt')).write_text(p.stdout+p.stderr);runs.append(dict(side=side,command=cmd,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
    n,t=runs;assert n['exit']==0,runs;d=json.loads(report.read_text());assert d['events_dropped']==0
    calls=[e for e in d['events']if e['kind']=='gui_window_ids_call'];rets=[e for e in d['events']if e['kind']=='gui_window_ids_return']
    if mode=='positive':
        assert t['exit']==0 and n['stdout']==t['stdout'] and t['stdout'].endswith('failures=0\n'),runs
        assert len(calls)==len(rets)==34
        for c,r in zip(calls,rets):
            assert r['esp_before']==c['esp'] and r['esp_after']==c['esp']+12 and r['actual_return']==c['return']
        assert n['stdout'].count('worker-from-main')==3 and n['stdout'].count('error=00000578')==15
    else:
        assert t['exit']==76 and len(calls)==1 and not rets,runs
        assert ('wrong HWND token type' if mode=='wrong-type' else 'invalid four-byte output')in t['stderr']
        if mode=='bad-output':assert 'exception=c0000005' in n['stdout'],runs
    rows.append(dict(mode=mode,passed=True,runs=runs,events_recorded=d['events_recorded'],events_dropped=0))
(B/'results.json').write_text(json.dumps(dict(passed=True,paired_calls=34,explicit_unsupported=2,runs=rows),indent=2))
print('GetWindowThreadProcessId native/translated PASS: 34 paired queries; owner IDs, optional/unaligned/page-crossing DWORD, invalid/dead HWND, last-error, ABI; two explicit unsupported cases')
