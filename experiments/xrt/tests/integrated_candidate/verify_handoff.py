"""Read-only handoff seal verification. No launch, queue or authorization path."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    m=read(O/'milestone.json')
    assert m['passed'] and not m['execution_authorized'] and m['genuine_launches']==m['physical_executions']==0
    assert m['runtime']==core.tree(RT) and m['tests_source']==core.tree(H)
    for n,digest in m['receipts'].items():assert core.sha(O/(n+'.json'))==digest,n
    for n,digest in m['deliverables'].items():assert core.sha(O/n)==digest,n
    exe,sha,pdb=identity();assert core.sha(exe)==sha==m['candidate_sha256'] and core.sha(exe.with_suffix('.pdb'))==pdb
    design=read(O/'continuation-design.json');assert not design['execution_authorized'] and not design['observer_installed']
    for n,digest in design['observer_sources'].items():assert core.sha(n)==digest,n
    assert core.sha(design['mapping_file'])==design['mapping_sha256']
    baseline=read(O/'preservation.json')
    assert all(core.tree(Path(n))==tree for n,tree in baseline['trees'].items())
    assert A.verify()==baseline['protected']
    print('Integrated handoff seal, all receipts/source identities, candidate and full preservation PASS',flush=True)

if __name__=='__main__':main()
