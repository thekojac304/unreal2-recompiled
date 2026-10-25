"""Same x86 capture probe executed natively and lifted against real USER32."""
import json, subprocess
from pathlib import Path
ws=Path(__file__).resolve().parents[4];out=ws/'experiments/xrt/build/setcapture_boundary_03';rows=[]
for mode in ['positive','borrowed','cross-thread','wrong-type']:
    runs=[]
    for side in ['native','translated']:
        report=out/(mode+'-report.json')
        command=[str(out/(side+'.exe')),str(out/'setcaptureprobe.dll'),mode]
        if side=='translated':command.append(str(report))
        run=subprocess.run(command,capture_output=True,text=True,timeout=30)
        (out/(side+'-'+mode+'.txt')).write_text(run.stdout+run.stderr)
        runs.append(dict(side=side,command=command,exit=run.returncode,stdout=run.stdout,stderr=run.stderr))
    native,translated=runs
    assert native['exit']==0,runs
    if mode!='wrong-type':assert native['stdout'].endswith('failures=0\n'),runs
    data=json.loads(report.read_text());assert data['events_dropped']==0
    pending={};pairs=[]
    for e in data['events']:
        key=(e.get('thread'),e.get('esp',e.get('esp_before')),e.get('return'))
        if e['kind']=='gui_set_capture_call':
            assert key not in pending;pending[key]=e
        elif e['kind']=='gui_set_capture_return':
            c=pending.pop(key)
            assert e['esp_after']==c['esp']+8 and e['actual_return']==c['return']
            assert e['result']==0 or 0x1000<=e['result']<0x5000 and e['result']%4==0
            pairs.append([c['seq'],e['seq']])
    unsupported=mode in ['cross-thread','wrong-type']
    if unsupported:
        assert translated['exit']==76 and len(pending)==1,runs
        fatal=next(e for e in data['events']if e['kind']=='fatal')
        assert 'SetCapture: '+('cross-thread'if mode=='cross-thread'else'wrong HWND token type')in fatal['message']
        if mode=='cross-thread':
            assert native['stdout'].count('previous=0 capture=0')==3
            assert 'worker-after-foreign capture=5' in native['stdout']
            assert translated['stdout']==native['stdout'].split('foreign-window')[0]
    else:
        assert translated['exit']==0 and translated['stdout']==native['stdout'],runs
        assert not pending
        if mode=='positive':
            for expected in ['same-a msg=00215 h=1 other=1','null-with-a seed=00005555 previous=1 capture=0 error=00005555 abi=1','invalid-with-a seed=00005555 previous=0 capture=1 error=00000578 abi=1','reentrant-transition seed=deadbeef previous=1 capture=1','reentrant-null seed=deadbeef previous=2 capture=1','msg=10215','capture-nccreate completed=1 capture=4','capture-create completed=1 capture=4']:
                assert expected in native['stdout'],expected
    rows.append(dict(mode=mode,passed=True,runs=runs,paired_returns=pairs,explicitly_unsupported=unsupported))
result=dict(passed=True,runs=rows,supported_calls=sum(len(r['paired_returns'])for r in rows if not r['explicitly_unsupported']),unsupported_cases=2,events_dropped=0)
(out/'results.json').write_text(json.dumps(result,indent=2))
print('SetCapture native/translated PASS:',result['supported_calls'],'paired calls; NULL, ownership, transitions, ReleaseCapture interaction, callbacks, reentrancy, errors, ABI; 2 explicit unsupported cases')
