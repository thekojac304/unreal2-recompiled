"""Native x86 IMM32 and actual lifted import boundary; no assumed handle bits."""
import json,subprocess,sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/immassociatecontext_boundary'
rows=[];pairs=[]
for mode in ['positive','invalid','unknown-context','wrong-type','cross-window','cross-restore','cross-context','dead-thread-context']:
    runs=[]
    for side in ['native','translated']:
        report=out/(mode+'-report.json');cmd=[str(out/(side+'.exe')),str(out/'immprobe.dll'),mode]
        if side=='translated':cmd.append(str(report))
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (out/(side+'-'+mode+'-comparison.txt')).write_text(r.stdout+r.stderr)
        runs.append(dict(side=side,command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    native,translated=runs;assert native['exit']==0,(mode,native)
    events=json.loads(report.read_text());pending={};local=[]
    for e in events['events']:
        key=(e.get('thread'),e.get('esp',e.get('esp_before')),e.get('return'))
        if e['kind']=='gui_imm_associate_context_call':
            assert key not in pending;pending[key]=e
        elif e['kind']=='gui_imm_associate_context_return':
            c=pending.pop(key);assert e['esp_after']==c['esp']+12 and e['actual_return']==c['return']
            assert e['result']==0 or (0x1000<=e['result']<0x5000 and e['result']%4==0)
            local.append([c['seq'],e['seq']])
    assert events['events_dropped']==0
    if mode in ['positive','invalid']:
        assert translated['exit']==0 and native['stdout']==translated['stdout'],(mode,runs)
        assert not pending
        if mode=='positive':assert len(local)==56 and translated['stdout'].endswith('failures=0\n')
        else:assert len(local)==12
    else:
        assert translated['exit']==76 and len(pending)==1,(mode,runs)
        fatal=next(e for e in events['events'] if e['kind']=='fatal')
        assert 'ImmAssociateContext:' in fatal['message'] and any(s in fatal['message'] for s in ['cross-thread','foreign or expired','unknown or wrong-type'])
    rows.append(dict(mode=mode,passed=True,runs=runs,paired_returns=local,explicitly_unsupported=mode not in ['positive','invalid']))
    pairs+=local
result=dict(passed=True,runs=rows,positive_calls=56,invalid_calls=12,unsupported_cases=6,paired_returns=len(pairs),events_dropped=0)
(out/'results.json').write_text(json.dumps(result,indent=2));print('IMM32 native/translated PASS: 56 identity/state/last-error/ABI calls, 12 invalid HWND calls, 6 explicit unsupported cases')
