"""Run the very same x86 GUI fixture natively and lifted; require expected successful result and identical logs."""
import json, subprocess, sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4]
out=ws/'experiments/xrt/build/gui_boundary'
dll=out/'guiprobe.dll'
cmds=[[str(out/'native.exe'),str(out),str(dll),'probe_gui'],[str(out/'translated.exe'),str(dll),str(out/'report.json'),'probe_gui']]
results=[]
for cmd in cmds:
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 print(r.stdout,r.stderr)
ok=all(r['exit']==0 and 'probe_gui returned 0 log ' in r['stdout'] for r in results) and results[0]['stdout']==results[1]['stdout']
(out/'results.json').write_text(json.dumps({'pass':ok,'runs':results},indent=2))
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
