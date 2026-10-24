"""Same x86 probe, native USER32 oracle, typed host identity and paired ABI evidence."""
import json,subprocess,sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/focus_boundary'
dll=out/'focusprobe.dll';rows=[]
for name,cmd in [('native',[str(out/'native.exe'),str(dll)]),('translated',[str(out/'translated.exe'),str(dll),str(out/'report.json')])]:
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    rows.append(dict(name=name,command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    (out/(name+'-comparison.txt')).write_text(r.stdout+r.stderr)
report=json.loads((out/'report.json').read_text());events=report['events']
calls=[e for e in events if e['kind']=='gui_get_focus_call'];returns=[e for e in events if e['kind']=='gui_get_focus_return']
pending={};pairs=[]
for e in events:
    key=(e.get('thread'),e.get('esp',e.get('esp_before')),e.get('return'))
    if e['kind']=='gui_get_focus_call':
        assert key not in pending;pending[key]=e
    elif e['kind']=='gui_get_focus_return':
        c=pending.pop(key)
        assert e['seq']>c['seq'] and e['esp_after']==c['esp']+4 and e['actual_return']==c['return']
        assert e['result']==0 or (0x1000<e['result']<0x5000 and e['result']%4==0)
        pairs.append([c['seq'],e['seq']])
ok=all(r['exit']==0 and r['stdout'].endswith('failures=0\n') for r in rows)
ok &= rows[0]['stdout']==rows[1]['stdout'] and len(pairs)==48 and not pending and report['events_dropped']==0
result=dict(passed=ok,runs=rows,focus_reads=len(pairs),paired_events=pairs,events_dropped=report['events_dropped'])
(out/'results.json').write_text(json.dumps(result,indent=2));print('GetFocus native/translated', 'PASS' if ok else 'FAIL',len(pairs),'paired reads');sys.exit(0 if ok else 1)
