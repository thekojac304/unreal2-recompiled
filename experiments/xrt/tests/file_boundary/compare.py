"""Compare binary FILE operations against the real msvcr70, including stream state and deliberate unsupported cases."""
import json, subprocess, sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4]
out=ws/'experiments/xrt/build/file_boundary'
dll=out/'fileprobe.dll'
cmds=[[str(out/'native.exe'),str(out),str(dll),'probe_file','probe_seek'],[str(out/'translated.exe'),str(dll),str(out/'report.json'),'probe_file','probe_seek']]
results=[]
for cmd in cmds:
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 print(r.stdout,r.stderr)
ok=all(r['exit']==0 and all(p+' returned 0 log ' in r['stdout'] for p in ['probe_file','probe_seek']) for r in results) and results[0]['stdout']==results[1]['stdout']
for probe,message in [('probe_text_read','fread text translation is not implemented'),
                      ('probe_invalid_file','binary stream was not returned by live fopen'),
                      ('probe_large_read','fread size overflow/large transfer is unmeasured')]:
 cmd=[str(out/'translated.exe'),str(dll),str(out/(probe+'.json')),probe]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 ok = ok and r.returncode == 76 and message in r.stderr
(out/'results.json').write_text(json.dumps({'pass':ok,'runs':results},indent=2))
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)

