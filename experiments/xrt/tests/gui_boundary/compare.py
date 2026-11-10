"""Run the very same x86 GUI fixture natively and lifted; require expected successful result and identical logs."""
import json, subprocess, sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4]
out=ws/'experiments/xrt/build/gui_boundary'
dll=out/'guiprobe.dll'
results=[]
ok=True
for function in ['probe_gui','probe_keys']:
 cmds=[[str(out/'native.exe'),str(out),str(dll),function],[str(out/'translated.exe'),str(dll),str(out/(function+'.json')),function]]
 rows=[]
 for cmd in cmds:
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
  row={'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};results.append(row);rows.append(row)
 ok &= all(r['exit']==0 and function+' returned 0 log ' in r['stdout'] for r in rows) and rows[0]['stdout']==rows[1]['stdout']
 print(function,'PASS' if ok else 'FAIL')
r=subprocess.run([str(out/'translated.exe'),str(dll),str(out/'unsupported-key.json'),'probe_keys_unsupported'],capture_output=True,text=True,timeout=30)
ok &= r.returncode==76 and 'unmeasured virtual key' in r.stderr
results.append(dict(negative='unsupported key 256',exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
(out/'results.json').write_text(json.dumps({'pass':ok,'runs':results},indent=2))
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
