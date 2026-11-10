import argparse
import uuid
from recheck import OUT,core
from build import build
from submit import run
from audit_creation import audit
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('configs',type=int,nargs='+');args=p.parse_args();results=[];path=OUT/('creation-sweep-'+str(uuid.uuid4())+'.json')
    try:
        for config in args.configs:
            for arch,variant in (('x86','native'),('x64','native'),('x64','translated')):
                spec=build(1,arch,variant,config);response=run(spec['candidate_id']);result=audit(response['id']);results.append(dict(config=config,arch=arch,variant=variant,request=response['id'],candidate=spec['candidate_id']))
                core.atomic(path,dict(complete=False,results=results))
        core.atomic(path,dict(complete=True,results=results))
    except BaseException as error:
        core.atomic(path,dict(complete=False,error=repr(error),results=results));raise
