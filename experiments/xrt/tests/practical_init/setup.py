"""Isolated practical recorder experiment. Never launches a genuine candidate."""
from pathlib import Path
import shutil

H=Path(__file__).resolve().parent
W=H.parents[3]
OLD=H.parent/'init_runtime_finish'
O=W/'out/recovery/practical-init-20261031-01'

def main():
    O.mkdir()
    import sys
    sys.path.insert(0,str(H))
    from common import core,save,A,RT,FINISHED
    roots=[FINISHED,W/'out/recovery/runtime-monitoring-20261030-01',W/'experiments/xrt/runtime',W/'tools/xrt/supervisor',W/'experiments/xrt/gen',OLD]
    state=[W/'out/desktop-supervisor'/n for n in ('ledger.jsonl','status.json','HALTED.json','STOP','qualification.json')]
    save(O/'preservation.json',dict(trees={str(p):core.tree(p) for p in roots},
        state={str(p):core.sha(p) if p.exists() else None for p in state},protected=A.verify()))
    shutil.copytree(FINISHED/'runtime',RT)
    for name in ('typed-methods.json','sdk-prototypes.json'):
        shutil.copy2(FINISHED/name,O/name)
    from transform import main as transform
    transform()
    print('Isolated evidence and recorder runtime staged')

if __name__=='__main__':main()
