"""Submit one authorized disposable fixture and provision its missing log parent.

The live qualified service calls physical_gate(out), which expects out/evidence
to exist. Provision ONLY that empty directory for this identified request. This
does not change enforcement or any gate result; the service still collects and
validates its physical-desktop snapshot before spawning the child.
"""
import argparse
import threading
import time
from recheck import OUT, core
from supervisor import development as D, fixture_profiles as F


def run(candidate):
    started=time.time();done=threading.Event();provisioned=[];errors=[]
    def prepare():
        try:
            while not done.is_set():
                for folder in (F.HOME/'evidence').iterdir():
                    if not folder.is_dir() or folder.name.startswith('gate-') or folder.stat().st_mtime < started-1:
                        continue
                    path=folder/'request.json'
                    if not path.exists():continue
                    request=core.read(path)
                    if request.get('candidate_id') != candidate:continue
                    core.uuid_text(folder.name)
                    target=core.independent(folder/'evidence')
                    if not target.exists():
                        target.mkdir()
                        provisioned.append(dict(request=request['id'],path=str(target),time=time.time()))
                done.wait(.01)
        except BaseException as error:
            errors.append(repr(error))
    worker=threading.Thread(target=prepare,daemon=True);worker.start()
    try:
        ident=D.submit(candidate,'Measure actual semantic adapter/native GPU behavior with full raw ABI, readbacks, identities and cleanup; historical parser verdict retained separately',60)
        print('Submitted',ident,flush=True)
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            path=F.HOME/'responses'/(ident+'.json')
            if path.exists():
                result=core.read(path)
                core.atomic(OUT/('request-'+ident+'.json'),dict(request_id=ident,candidate=candidate,
                    response=result,log_parent_provisioning=provisioned,provisioning_errors=errors))
                print(result['classification'],result.get('reason'),flush=True)
                return result
            if errors:raise RuntimeError(errors)
            done.wait(.2)
        raise TimeoutError('Request remains pending; inspect service, never replay its ID')
    finally:
        done.set();worker.join(3)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate');run(p.parse_args().candidate)
