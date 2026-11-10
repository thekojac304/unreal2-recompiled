"""Read-only owner gate, unchanged supervisor checks, deterministic source QA."""
import sys,uuid,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    out=O/('support-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    h.run([W/'.venv/Scripts/python.exe','-B','-I','-m','unittest','discover','-s',W/'tools/xrt/supervisor/tests','-v'],'supervisor-tests',timeout=180)
    r=read(out/'supervisor-tests.json');save(O/'supervisor-tests.json',dict(passed=True,root=str(out),receipt=r,
        stdout_sha256=core.sha(out/'supervisor-tests.stdout.txt'),stderr_sha256=core.sha(out/'supervisor-tests.stderr.txt')))
    from supervisor.environment import Desktop
    try:fingerprint=Desktop().check(out,'retained');environment=dict(passed=True,fingerprint=fingerprint)
    except Exception as e:environment=dict(passed=False,rejection=type(e).__name__+': '+str(e))
    save(O/'environment-check.json',dict(environment,root=str(out),policy_changed=False))
    fresh=out/'reproduction';shutil.copytree(FINISHED/'runtime',fresh)
    m=load('practical_recorder_reproduction',H/'transform.py');m.RT=fresh;m.H=fresh;m.main()
    core.require(core.tree(fresh)==read(O/'build.json')['runtime'],'source regeneration differs from build')
    changes=[p for p,digest in core.tree(RT).items() if digest!=core.tree(FINISHED/'runtime').get(p)]
    core.require(changes==['monitor.c','monitor.h'],'unexpected runtime/safety adapter change')
    save(O/'source-reproduction.json',dict(passed=True,root=str(fresh),runtime=core.tree(fresh),
        changed_runtime_files=changes,unchanged_safety_adapters=True,templates=core.tree(H)))
    print('Supervisor checks, read-only environment receipt, exact recorder-only regeneration complete',flush=True)

if __name__=='__main__':main()
