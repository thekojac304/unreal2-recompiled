import json,subprocess
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/setactive_boundary_03';rows=[]
for mode in ['positive','borrowed','wrong-type']:
    runs=[];report=out/(mode+'-report.json')
    for side in ['native','translated']:
        cmd=[str(out/(side+'.exe')),str(out/'setactiveprobe.dll'),mode]
        if side=='translated':cmd.append(str(report))
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(out/(side+'-'+mode+'.txt')).write_text(r.stdout+r.stderr);runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    d=json.loads(report.read_text());assert d['events_dropped']==0
    if mode!='wrong-type':
        assert all(r['exit']==0 and r['stdout'].endswith('failures=0\n')for r in runs)and runs[0]['stdout']==runs[1]['stdout'],runs
        calls=[e for e in d['events']if e['kind']=='gui_set_active_call'];rets=[e for e in d['events']if e['kind']=='gui_set_active_return'];assert len(calls)==len(rets)==(12 if mode=='positive'else 3)
        for c,r in zip(calls,rets):assert r['esp_before']==c['esp']and r['esp_after']==c['esp']+8 and r['actual_return']==c['return']
    else:
        assert runs[1]['exit']==76 and any(e['kind']=='fatal'and 'wrong HWND token type'in e['message']for e in d['events']),runs
    rows.append(dict(mode=mode,passed=True,runs=runs))
(out/'results.json').write_text(json.dumps(dict(passed=True,supported_calls=15,runs=rows),indent=2));print('SetActiveWindow native/translated PASS: 15 calls, previous HWND including borrowed identity, last-error, callbacks, stdcall ABI; wrong-type guard')
