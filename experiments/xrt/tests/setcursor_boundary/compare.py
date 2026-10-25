"""Same x86 DLL: previous HCURSOR identity, state, borrowed lifetime, errors, ABI."""
import json,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[4];B=W/'experiments/xrt/build/setcursor_boundary';rows=[]
for mode in ['positive','wrong-type','invalid']:
    runs=[];report=B/(mode+'-report.json')
    for side in ['native','translated']:
        cmd=[str(B/(side+'.exe')),str(B/'cursorprobe.dll'),mode,str(report)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (B/(side+'-'+mode+'.txt')).write_text(p.stdout+p.stderr)
        runs.append(dict(side=side,command=cmd,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
    n,t=runs;assert n['exit']==0,runs
    d=json.loads(report.read_text());assert d['events_dropped']==0
    calls=[e for e in d['events']if e['kind']=='gui_set_cursor_call'];rets=[e for e in d['events']if e['kind']=='gui_set_cursor_return']
    if mode=='positive':
        assert t['exit']==0 and t['stdout']==n['stdout'] and t['stdout'].endswith('failures=0\n'),runs
        assert len(calls)==len(rets)==38
        for c,r in zip(calls,rets):
            assert c['esp']==r['esp_before'] and r['esp_after']==c['esp']+8 and r['actual_return']==c['return']
            assert r['result']==0 or 0xfb000000<=r['result']<0xfb001000
        assert 'borrowed-previous input=0 previous=5 state=0' in n['stdout']
        assert 'reuse-borrowed input=5 previous=0 state=5' in n['stdout']
    else:
        assert t['exit']==76 and 'unknown class object' in t['stderr'] and len(calls)==1 and not rets,runs
    rows.append(dict(mode=mode,passed=True,runs=runs,events_recorded=d['events_recorded'],events_dropped=0))
(B/'results.json').write_text(json.dumps(dict(passed=True,paired_calls=38,explicit_unsupported=2,runs=rows),indent=2))
print('SetCursor native/translated PASS: 38 paired calls; previous identity, NULL, shared/borrowed cursors, thread state, last-error, ABI; two explicit unsupported cases')
