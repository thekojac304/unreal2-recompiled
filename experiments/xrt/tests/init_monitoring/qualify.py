"""Retained hardware mapping, production fatal capture and containment checks."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    # Reuse retained qualification unchanged, redirected only to fresh receipts.
    sys.path.insert(0,str(H.parent/'integrated_candidate'))
    m=load('init_monitoring_inert_qualification',H.parent/'integrated_candidate/qualify.py')
    m.H=H.parent/'integrated_candidate';m.live()
    from supervisor import qualify as q
    out=O/('containment-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    exe=out/'fixture.exe'
    h.run(['cl','/nologo','/O1','/MT','/Fo'+str(out/'fixture.obj'),'/Fe'+str(exe),
           W/'tools/xrt/supervisor/fixture.c','/link','/DYNAMICBASE'],'build',environment=h.env())
    results=[q.direct(exe,out,case) for case in ('hang','tree','fatal-stop')]
    cancel=out/'cancel';cancel.mkdir();results.append(q.direct(exe,cancel,'tree',cancel=True))
    save(O/'containment-validation.json',dict(passed=True,results=results,root=str(out),
        fixture_sha256=core.sha(exe),genuine_launches=0,policy_changed=False))
    print('Independent watchdog, descendant Job cleanup and cancellation PASS',flush=True)

if __name__=='__main__':main()
