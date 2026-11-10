"""Fresh interpreters, frozen runtime, all owned monitoring/containment suites."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    out=O/('qualification-'+str(uuid.uuid4()));out.mkdir();h=helper(out);before=core.tree(RT)
    commands=[['live.py'],['adapter_checks.py','contracts'],['resource_trace.py'],['dinput_trace.py'],
              ['guest_threads.py'],['nonlocal.py','eh'],['nonlocal.py','dmusic'],['nonlocal.py','ipc'],
              ['composed_live.py'],['qualify.py'],['adapter_checks.py','gui']]
    receipts=[]
    for i,args in enumerate(commands):
        cmd=[W/'.venv/Scripts/python.exe','-B','-I',H/args[0],*args[1:]]
        h.run(cmd,f'suite-{i:02d}',timeout=300)
        core.require(core.tree(RT)==before,'runtime changed during final qualification')
        receipts.append(str(out/f'suite-{i:02d}.json'))
    save(O/'qualification.json',dict(passed=True,root=str(out),runtime=before,commands=commands,receipts={p:core.sha(p) for p in receipts},genuine_launches=0))
    print('Complete owned monitoring / native oracles / containment suites PASS',flush=True)

if __name__=='__main__':main()
