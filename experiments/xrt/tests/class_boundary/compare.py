"""Compare class/GUI startup behavior using the same x86 image and real callback bridge; retain deliberate negatives."""
import ctypes, json, subprocess, sys
from pathlib import Path
ws=Path(__file__).resolve().parents[4]
out=ws/'experiments/xrt/build/class_boundary'
dll=out/'classprobe.dll'
probes=['probe_classes','probe_controls','probe_brush','probe_window','probe_mutex','probe_atoms']
cmds=[[str(out/'native.exe'),str(out),str(dll),*probes],[str(out/'translated.exe'),str(dll),str(out/'report.json'),*probes]]
results=[]
for cmd in cmds:
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 print(r.stdout,r.stderr)
ok=all(r['exit']==0 and all(f'{p} returned 0 log ' in r['stdout'] for p in probes) for r in results) and results[0]['stdout']==results[1]['stdout']
for probe, message in [('probe_bad_proc','is not a live translated function'),
                       ('probe_pointer_message','has no validated callback frame'),
                       ('probe_stale_prior','WNDPROC owner'),
                       ('probe_reloaded_prior','prior WNDPROC belongs to an earlier module mapping'),
                       ('probe_atom_cleanup','is not a live translated function')]:
 cmd=[str(out/'translated.exe'),str(dll),str(out/(probe+'.json')),probe]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 results.append({'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 ok = ok and r.returncode == 76 and message in r.stderr
ok = ok and ctypes.windll.kernel32.GlobalFindAtomW('Xrt_AbortAtom_01a166e7') == 0
(out/'results.json').write_text(json.dumps({'pass':ok,'runs':results},indent=2))
print('PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)

