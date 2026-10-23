"""Native PE32 / translated DirectInput comparison with deliberate unsupported cases."""
import json, subprocess, sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4]
out=ws/'experiments/xrt/build/input_boundary'
dll=out/'inputprobe.dll'
probes=['probe_creation','probe_sticky','probe_lifetime','probe_leak']
results=[]
for cmd in [[str(out/'native.exe'),str(out),str(dll),*probes],
            [str(out/'translated.exe'),str(dll),str(out/'report.json'),*probes]]:
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    results.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(r.stdout,r.stderr)
ok=all(r['exit']==0 and all(f'{p} returned 0 log ' in r['stdout'] for p in probes) for r in results) and results[0]['stdout']==results[1]['stdout']
report=json.loads((out/'report.json').read_text())
ok=ok and any(e['kind']=='dinput_cleanup' and e['references_released']==2 for e in report['events'])
for probe,message in [('probe_stale','stale or unknown guest COM interface'),
                      ('probe_unmeasured','IDirectInput8W::GetDeviceStatus is unmeasured'),
                      ('probe_ansi','successful unmodelled IID'),
                      ('probe_aggregate','COM aggregation is unmeasured')]:
    cmd=[str(out/'translated.exe'),str(dll),str(out/(probe+'.json')),probe]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    results.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    ok=ok and r.returncode==76 and message in r.stderr
(out/'results.json').write_text(json.dumps({'pass':ok,'runs':results},indent=2))
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
