"""Same x86 DLL under USER32 and xlift: identities, focus, errors, callbacks, ABI."""
import json, subprocess
from pathlib import Path

ws = Path(__file__).resolve().parents[4]
out = ws / 'experiments/xrt/build/setfocus_boundary'
rows = []
for mode in ['positive', 'borrowed', 'cross-thread', 'wrong-type']:
    runs = []
    for side in ['native', 'translated']:
        report = out / (mode + '-report.json')
        command = [str(out / (side + '.exe')), str(out / 'setfocusprobe.dll'), mode]
        if side == 'translated':
            command.append(str(report))
        run = subprocess.run(command, capture_output=True, text=True, timeout=30)
        (out / (side + '-' + mode + '.txt')).write_text(run.stdout + run.stderr)
        runs.append(dict(side=side, command=command, exit=run.returncode,
                         stdout=run.stdout, stderr=run.stderr))
    native, translated = runs
    assert native['exit'] == 0, runs
    if mode != 'wrong-type':
        assert native['stdout'].endswith('failures=0\n'), runs
    data = json.loads(report.read_text())
    assert data['events_dropped'] == 0
    pending = {}
    pairs = []
    for event in data['events']:
        key = (event.get('thread'), event.get('esp', event.get('esp_before')), event.get('return'))
        if event['kind'] == 'gui_set_focus_call':
            assert key not in pending
            pending[key] = event
        elif event['kind'] == 'gui_set_focus_return':
            call = pending.pop(key)
            assert event['esp_after'] == call['esp'] + 8
            assert event['actual_return'] == call['return']
            assert event['result'] == 0 or (0x1000 <= event['result'] < 0x5000 and event['result'] % 4 == 0)
            pairs.append([call['seq'], event['seq']])
    unsupported = mode in ['cross-thread', 'wrong-type']
    if unsupported:
        assert translated['exit'] == 76 and len(pending) == 1, runs
        fatal = next(e for e in data['events'] if e['kind'] == 'fatal')
        assert 'SetFocus: ' + ('cross-thread' if mode == 'cross-thread' else 'wrong HWND token type') in fatal['message']
        if mode == 'cross-thread':
            assert native['stdout'].count('error=00000005 abi=1') == 3
            assert translated['stdout'] == native['stdout'].split('foreign-window')[0]
    else:
        assert translated['exit'] == 0 and translated['stdout'] == native['stdout'], runs
        assert not pending
        if mode == 'positive':
            assert 'a-to-b seed=00005555 previous=1 focus=2' in native['stdout']
            assert 'b-to-a seed=00005555 previous=2 focus=1' in native['stdout']
            assert 'focus-nccreate completed=1 focus=4' in native['stdout']
            assert 'focus-create completed=1 focus=4' in native['stdout']
            assert 'msg=10007' in native['stdout'] and 'msg=10008' in native['stdout']
    rows.append(dict(mode=mode, passed=True, runs=runs, paired_returns=pairs,
                     explicitly_unsupported=unsupported))
result = dict(passed=True, runs=rows,
              supported_calls=sum(len(r['paired_returns']) for r in rows if not r['explicitly_unsupported']),
              unsupported_cases=2, events_dropped=0)
(out / 'results.json').write_text(json.dumps(result, indent=2))
print('SetFocus native/translated PASS:', result['supported_calls'],
      'paired calls; previous HWND, focus, last-error, callbacks, creation, ABI; 2 explicit unsupported cases')
