import json,subprocess
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/foreground_boundary';runs=[];report=out/'report.json'
for side in ['native','translated']:
    cmd=[str(out/(side+'.exe')),str(out/'foregroundprobe.dll'),'positive']
    if side=='translated':cmd.append(str(report))
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(out/(side+'.txt')).write_text(r.stdout+r.stderr)
    runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
assert all(r['exit']==0 and r['stdout'].endswith('failures=0\n')for r in runs)and runs[0]['stdout']==runs[1]['stdout'],runs
d=json.loads(report.read_text());assert d['events_dropped']==0
calls=[e for e in d['events']if e['kind']=='gui_foreground_call'];returns=[e for e in d['events']if e['kind']=='gui_foreground_return'];assert len(calls)==len(returns)==9
for c,r in zip(calls,returns):
    assert r['esp_after']==c['esp']+4 and r['actual_return']==c['return'] and r['last_error']==c['last_error']
    assert r['result']==0 or 0x1000<=r['result']<0x5000 and r['result']%4==0
(out/'results.json').write_text(json.dumps(dict(passed=True,supported_calls=9,nonnull_observations=sum(e['result']!=0 for e in returns),runs=runs,paired_returns=[[c['seq'],r['seq']]for c,r in zip(calls,returns)]),indent=2))
print('GetForegroundWindow native/translated PASS: 9 calls; actual NULL observations, last-error and zero-argument stdcall ABI; existing borrowed-HWND mapping retained')
