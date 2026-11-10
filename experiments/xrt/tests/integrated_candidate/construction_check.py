"""Construct the actual candidate observer without creating any process."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from continuation import construct
from supervisor.windows import BoundedLoop

def main():
    out=O/('construction-'+str(uuid.uuid4()));out.mkdir()
    plan=read(O/'stop-mapping.json');checks=[]
    allowed=[identity()[0],*[Path(n) for n in read(O/'candidate-identity.json')['dependencies']]]
    capture=construct(out,plan,checks.append,allowed)
    assert capture.created==0 and capture.base==0 and not capture.breakpoints and not checks
    assert capture.run.__func__ is BoundedLoop.run and capture._fatal_evidence_installed
    assert capture.out==out and capture.init_entry is None
    assert all(callable(getattr(capture,n)) for n in ('snapshot_events','u64','mem','log','sym','module_record'))
    save(O/'construction-validation.json',dict(passed=True,candidate_sha256=identity()[1],
        observer_sources={str(H/n):core.sha(H/n) for n in ('continuation.py','observer.py','hardware_fixture.py','common.py')},
        retained_bounded_loop=True,retained_fatal_evidence=True,allowed_modules=[str(p) for p in allowed],
        process_created=False,candidate_executed=False,authorization_changed=False))
    print('Actual candidate observer factory/composition constructed; no process created',flush=True)

if __name__=='__main__':main()
