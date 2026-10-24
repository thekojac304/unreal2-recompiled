"""Compare the same x86 API calls, all RECT fields, last-error and stdcall ABI."""
import json,subprocess,sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/adjustwindowrect_boundary'
dll=out/'rectprobe.dll';rows=[]
def run(name,case=None):
    cmd=[str(out/(name+'.exe')),str(dll),str(out/((case or 'valid')+'.json'))]
    if case:cmd.append(case)
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
    row=dict(name=name,case=case,command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr);rows.append(row)
    (out/(name+'-'+(case or 'valid')+'.txt')).write_text(r.stdout+r.stderr)
    return row
native=run('native');translated=run('translated')
assert native['exit']==translated['exit']==0
assert native['stdout']==translated['stdout']
lines=native['stdout'].splitlines();assert lines[-1]=='failures=0 cases=3888'
valid=[json.loads(s)for s in lines[:-1]]
assert len(valid)==3888 and all(r['result']==1 and r['error']==r['seed'] and r['exception']==0 for r in valid)
report=json.loads((out/'valid.json').read_text());events=report['events'];pending={};pairs=[]
for e in events:
    if e['kind']=='gui_adjust_window_rect_call':
        key=(e['thread'],e['esp'],e['return']);assert key not in pending;pending[key]=e
    elif e['kind']=='gui_adjust_window_rect_return':
        key=(e['thread'],e['esp_before'],e['return']);c=pending.pop(key)
        assert e['seq']>c['seq'] and e['esp_after']==c['esp']+16 and e['actual_return']==c['return']
        pairs.append([c['seq'],e['seq']])
assert len(pairs)==3888 and not pending and report['events_dropped']==0
assert report['events_recorded']==len(events) and not any(e.get('truncated')for e in events)
negatives=[]
for case in ['null','low','uncommitted','readonly','noaccess','partial','guard','wrap']:
    n=run('native',case);t=run('translated',case);assert n['exit']==0
    measured=json.loads(n['stdout']);assert measured['exception']==(0x80000001 if case=='guard' else 0xc0000005)
    assert t['exit']==76 and 'invalid read/write guest RECT' in t['stderr'] and 'guest pointer faults unsupported' in t['stderr']
    negative=json.loads((out/(case+'.json')).read_text())
    assert not any(e['kind']=='gui_adjust_window_rect_return' for e in negative['events'])
    negatives.append(dict(case=case,native_exception=measured['exception'],translated_exit=t['exit'],explicitly_unsupported=True))
result=dict(passed=True,cases=len(valid),styles=12,rectangles=9,menus=4,seeds=3,placements=3,
    native_translated_identical=True,return_values=[1],last_error_preserved=True,paired_stdcall_calls=len(pairs),
    nonvolatile_registers_preserved=['EBP','EBX','ESI','EDI'],events_recorded=len(events),events_dropped=0,
    negatives=negatives,runs=rows)
(out/'results.json').write_text(json.dumps(result,indent=2));print('AdjustWindowRect PASS: 3888 exact native/translated calls; 8 explicit pointer diagnostics')
