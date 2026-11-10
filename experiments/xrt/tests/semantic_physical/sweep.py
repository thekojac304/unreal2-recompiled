import argparse
import time
import uuid
from recheck import OUT, core
from build import build
from submit import run
from audit import audit

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('groups',type=int,nargs='+');args=p.parse_args()
    path=OUT/('sweep-'+str(uuid.uuid4())+'.json');results=[]
    try:
        for group in args.groups:
            for arch,variant in (('x86','native'),('x64','native'),('x64','translated')):
                spec=build(group,arch,variant)
                response=run(spec['candidate_id'])
                if response['operational_state']=='SAFETY HALT' or response['classification']=='security-integrity-containment':
                    raise RuntimeError('Safety halt: '+str(response))
                result=audit(response['id'])
                results.append(dict(group=group,arch=arch,variant=variant,candidate=spec['candidate_id'],request=response['id'],passed=result['passed']))
                core.atomic(path,dict(complete=False,results=results,updated_at=time.time()))
        core.atomic(path,dict(complete=True,results=results,updated_at=time.time()))
    except BaseException as error:
        core.atomic(path,dict(complete=False,error=repr(error),results=results,updated_at=time.time()))
        raise
