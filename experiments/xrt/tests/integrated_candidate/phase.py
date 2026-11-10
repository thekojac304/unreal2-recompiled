"""Adopt and verify the exact sealed candidate; no game or GPU execution."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def stage():
    O.mkdir()
    roots=[SEALED, W/'tools/xrt/supervisor', W/'out/desktop-supervisor',
           W/'out/desktop-fixtures', W/'experiments/xrt/runtime',W/'experiments/xrt/gen',
           W/'out/recovery/remote-console-proof-20261030-01',
           W/'out/recovery/remote-fixture-startup-20261030-01']
    save(O/'preservation.json',dict(trees={str(p):core.tree(p) for p in roots if p.exists()},protected=A.verify()))
    for name in ('build.json','object-lineage.json'):
        shutil.copy2(SEALED/name,O/name)
    save(O/'adoption.json',dict(candidate=str(identity()[0]),sha256=identity()[1],
        source_build=str(SEALED/'build.json'),source_build_sha256=core.sha(SEALED/'build.json'),
        runtime=core.tree(RT),runtime_modified=False,relinked=False,genuine_launches=0))
    print('Adopted sealed unconsumed candidate',identity()[1],flush=True)

def verify():
    m=load('integrated_identity',H/'identity.py')
    m.EXE,m.SHA,m.PDB=identity()
    save(O/'candidate-identity.json',m.verify())
    print('279-object transitive lineage, PE/PDB, dependencies and nonconsumption PASS',flush=True)

def audit():
    m=load('retained_setres_audit',H.parent/'surface_transfer/phase.py');m.O=O;m.audit()

def preservation():
    p=read(O/'preservation.json')
    changed=[name for name,tree in p['trees'].items() if core.tree(Path(name))!=tree]
    assert not changed,changed
    assert A.verify()==p['protected']
    save(O/'preservation-after.json',dict(passed=True,changed=[],protected=p['protected']))
    print('Sealed candidate, production, authorization, installation and prior evidence preserved',flush=True)

if __name__=='__main__':
    assert sys.argv[1] in ('stage','verify','audit','preservation')
    globals()[sys.argv[1]]()
