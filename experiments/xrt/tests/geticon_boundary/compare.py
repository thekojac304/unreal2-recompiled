"""Native x86 and translated identical DLL: typed icons, nested callbacks, ABI."""
import json,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[4];B=W/'experiments/xrt/build/geticon_boundary_02'
rows=[]
for mode,c in [('positive',c)for c in range(4)]+[(m,0)for m in ['wrong-type','selector','dpi']]:
    runs=[]
    for side in ['native','translated']:
        report=B/f'{mode}-{c}-report.json'
        cmd=[str(B/(side+'.exe')),str(B/'geticonprobe.dll'),mode,str(c),str(report)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (B/f'{side}-{mode}-{c}.txt').write_text(p.stdout+p.stderr)
        runs.append(dict(side=side,command=cmd,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
    n,t=runs;assert n['exit']==0,runs
    data=json.loads(report.read_text());assert data['events_dropped']==0
    if mode=='positive':
        assert n['stdout'].endswith('failures=0\n'),runs
        assert t['exit']==0 and t['stdout']==n['stdout'],runs
        assert n['stdout'].count('sample ')==289
        assert n['stdout'].count('callback ')==1012
        assert any(e['kind']=='gui_get_icon_callback_return' and e['icon'] for e in data['events'])
        assert all(e['icon']==0 or 0xfb000000<=e['icon']<0xfb001000 for e in data['events'] if e['kind']=='gui_get_icon_callback_return')
    else:
        assert t['exit']==76,runs
        fatal=next(e for e in data['events']if e['kind']=='fatal')
        assert ('unknown class object' if mode=='wrong-type' else 'unmeasured selector/DPI')in fatal['message']
    rows.append(dict(mode=mode,class_icons=c,passed=True,runs=runs,events_recorded=data['events_recorded'],events_dropped=data['events_dropped']))
result=dict(passed=True,runs=rows,samples=1156,callback_records=4048,explicit_unsupported=3)
(B/'results.json').write_text(json.dumps(result,indent=2));print('WM_GETICON native/translated PASS: 1156 samples, 4048 callback records; three explicit unsupported cases')
