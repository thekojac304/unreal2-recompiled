"""Read-only saved physical evidence audit. Cannot grant or replace acceptance."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from package_audit import validate
from supervisor import fixture_profiles as F
import gpu_evidence

def compare(directories):
    core.require(len(directories)==3,'three saved physical capture directories required')
    package=read(O/'gpu-qualification-package.json');E,A,_=F.modules();groups=[];physical=[]
    for row,d in zip(package['candidates'],directories):
        candidate=validate(row);root=F.candidate_path(candidate['id']).parent
        item=F.plan('renderer-group',row['parameters'],root)[0]
        pair=E.P.G.verified_pair(item['arch'])
        rows,snapshot,events=A.process(d,physical=True,expected_exe=item['exe'],expected_args=['--physical',pair],
            expected_build=Path(candidate['build_record']),expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
        info=A.adapter(rows,snapshot,d,item['arch'])
        groups.append(gpu_evidence.read_rows(d/'stdout.txt'))
        physical.append(dict(candidate_id=candidate['id'],capture=str(d),runtime_events=len(events),**info))
    result=gpu_evidence.compare(groups)
    result.update(physical_evidence=physical,physical_process_checks_passed=True,
        collector_verdict_overridden=False,execution_authorized=False,
        limitation='Supplemental saved-evidence result only. Existing collector failures and historical strict failures remain authoritative; owner review and separate genuine authorization are still required.')
    return result

if __name__=='__main__':print(json.dumps(compare([Path(p) for p in sys.argv[1:]]),indent=2))
