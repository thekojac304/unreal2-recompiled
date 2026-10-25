import json,subprocess
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/clipcursor_boundary_03';rows=[]
for mode in ['positive','nonnull']:
    runs=[]
    for side in ['native','translated']:
        report=out/(mode+'-report.json');cmd=[str(out/(side+'.exe')),str(out/'clipprobe.dll'),mode]
        if side=='translated':cmd.append(str(report))
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (out/(side+'-'+mode+'.txt')).write_text(r.stdout+r.stderr)
        runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    n,t=runs;assert n['exit']==0 and 'clip-restored=1 failures=0'in n['stdout'],runs
    d=json.loads(report.read_text());assert d['events_dropped']==0
    calls=[e for e in d['events']if e['kind']=='gui_clip_cursor_call'];returns=[e for e in d['events']if e['kind']=='gui_clip_cursor_return']
    if mode=='positive':
        assert t['exit']==0 and n['stdout']==t['stdout'],runs
        assert len(calls)==len(returns)==6
        for c,r in zip(calls,returns):assert c['rect']==0 and r['result']==1 and r['last_error']==c['last_error'] and r['esp_after']==c['esp']+8 and r['actual_return']==c['return']
    else:assert t['exit']==76 and not returns and any(e['kind']=='fatal'and'ClipCursor: non-NULL'in e['message']for e in d['events']),runs
    rows.append(dict(mode=mode,passed=True,runs=runs,paired_returns=[[c['seq'],r['seq']]for c,r in zip(calls,returns)]))
(out/'results.json').write_text(json.dumps(dict(passed=True,supported_calls=6,explicitly_unsupported=1,runs=rows),indent=2))
print('ClipCursor(NULL) native/translated PASS: 6 calls, real clip reset, seeded last-error, ABI, original clip restored; non-NULL explicitly unsupported')
