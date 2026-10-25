import json,subprocess
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/window_ae_boundary_03';rows=[]
for mode in ['positive','wrong-wp','wrong-lp']:
    runs=[]
    for side in (['native','translated']if mode=='positive'else['translated']):
        report=out/(mode+'-report.json');cmd=[str(out/(side+'.exe')),str(out/'aeprobe.dll'),mode]
        if side=='translated':cmd.append(str(report))
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(out/(side+'-'+mode+'.txt')).write_text(r.stdout+r.stderr)
        runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    d=json.loads(report.read_text());assert d['events_dropped']==0
    if mode=='positive':
        assert all(r['exit']==0 and r['stdout'].endswith('failures=0\n')for r in runs)and runs[0]['stdout']==runs[1]['stdout'],runs
        callbacks=[e for e in d['events']if e['kind']=='gui_ae_callback_return'];assert len(callbacks)==24
        assert all(e['wparam']==8 and e['lparam']==0 for e in callbacks)
    else:assert runs[0]['exit']==76 and any(e['kind']=='fatal'and'window callback 0xae: unmeasured arguments'in e['message']for e in d['events']),runs
    rows.append(dict(mode=mode,passed=True,runs=runs))
(out/'results.json').write_text(json.dumps(dict(passed=True,outer_calls=24,callback_returns=24,explicitly_unsupported=2,runs=rows),indent=2))
print('Window 0xae native/translated PASS: 24 outer calls, 24 callback returns; A/W, popup/overlapped, real default processing, last-error and ABI; 2 guarded argument cases')
