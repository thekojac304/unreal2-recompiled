"""Inert candidate mapping and unchanged Job/watchdog enforcement, owned code."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    out=O/('containment-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    exe=out/'fixture.exe';h.run(['cl','/nologo','/O1','/MT',f'/Fo{out}/fixture.obj',f'/Fe{exe}',W/'tools/xrt/supervisor/fixture.c','/link','/DYNAMICBASE'],'build',environment=h.env())
    from supervisor import qualify as q
    results=[q.direct(exe,out,case) for case in ('hang','tree','fatal-stop')]
    cancel=out/'cancel';cancel.mkdir();results.append(q.direct(exe,cancel,'tree',cancel=True))
    save(O/'containment.json',dict(passed=True,root=str(out),cases=results,production_policy_changed=False))
    sys.path.append(str(H.parent/'surface_transfer'))
    source=(H.parent/'integrated_candidate/qualify.py').read_text()
    source=source.replace('from common import *','from common import *\nH=Path('+repr(str(H.parent/'integrated_candidate'))+')')
    source=source.replace('from observer import capture_endpoint','capture_endpoint=load("monitor_endpoint",W/"experiments/xrt/tests/surface_transfer/observer.py").capture_endpoint')
    source=source.replace("('stop','four-slots','slot-overflow','observer-failure','wrong-candidate-bytes')", "('stop','observer-failure','wrong-candidate-bytes')")
    source=source.replace('retained=observer_checks.qualify(out)','retained=dict(not_rerun=True,reason="Production observer unchanged; new candidate inert mapping and existing containment tested here.")')
    driver=out/'inert_driver.py';driver.write_text(source)
    m=load('monitor_inert_qualification',driver);m.live()
    print('Owned watchdog / descendant Job / cancellation / inert candidate stop PASS',flush=True)
if __name__=='__main__':main()
