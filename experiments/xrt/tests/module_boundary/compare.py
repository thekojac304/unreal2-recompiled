"""Require native/lifted module agreement and explicit traps at unsupported/stale export calls."""
import json, subprocess, sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4]
out=ws/'experiments/xrt/build/module_boundary'
dll=out/'moduleprobe.dll'
cmds=[[str(out/'native.exe'),str(out),str(dll),'probe_modules'],[str(out/'translated.exe'),str(dll),str(out/'report.json'),'probe_modules']]
results=[]
for cmd in cmds:
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 print(r.stdout,r.stderr)
ok=all(r['exit']==0 and 'probe_modules returned 0 log ' in r['stdout'] for r in results) and results[0]['stdout']==results[1]['stdout']
for probe, code, message in [('probe_unadapted_export', 75, 'shell32.dll!Shell_NotifyIconW'),
                       ('probe_stale_export', 75, 'after its guest module was unloaded'),
                       ('probe_transitive_identity', 76, 'host-only/transitive module membership is not modelled')]:
 cmd=[str(out/'translated.exe'),str(dll),str(out/(probe+'.json')),probe]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 ok = ok and r.returncode == code and message in r.stderr
(out/'results.json').write_text(json.dumps({'pass':ok,'runs':results},indent=2))
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
