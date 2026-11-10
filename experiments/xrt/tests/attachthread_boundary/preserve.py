"""Read/copy evidence only; never loads or executes a candidate."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

W = Path(__file__).resolve().parents[4]
O = W / 'out/recovery/attachthread-setres-20261029-01'
OLD = W / 'out/recovery/setres-completion-20261029-01'
ATTEMPT = OLD / 'owner-13a98b68-bf93-4196-825c-773a1b66f474'
SANDBOX = W / 'sandbox_cmp/setres-13a98b68-bf93-4196-825c-773a1b66f474'
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core


def main():
    core.require(not O.exists(), 'refuse to replace preserved evidence')
    O.mkdir(parents=True)
    candidate = Path(json.loads((ATTEMPT/'launch.json').read_text())['executable'])
    core.require(core.sha(candidate) == 'd6071f6563300dc4ae04b77d35943625f5b4274bb58db4a04ed6aee22b58d158', 'consumed identity changed')
    roots = [OLD, SANDBOX, candidate.parent, core.HOME, W/'tools/xrt/supervisor',
             W/'experiments/xrt/runtime', W/'experiments/xrt/gen', W/'experiments/xrt/tests/setres_completion',
             W/'out/recovery/renderer-gamma-integration-20261029-01']
    trees = {str(p): core.tree(p) for p in roots}
    for source, dest in [(OLD,O/'preserved/attempt-package'), (SANDBOX,O/'preserved/complete-sandbox'),
                         (candidate.parent,O/'preserved/consumed-build'), (core.HOME,O/'preserved/supervisor'),
                         (W/'experiments/xrt/runtime',O/'preserved/production-runtime')]:
        shutil.copytree(source,dest)
        core.require(core.tree(dest)==trees[str(source)], 'copy verification failed: '+str(source))
    for name,args in [('git-head',['rev-parse','HEAD']),('git-status',['status','--short']),('git-diff',['diff','--binary'])]:
        r=subprocess.run(['git',*args],cwd=W,capture_output=True,check=True)
        (O/(name+'.txt')).write_bytes(r.stdout)
    from supervisor.environment import load
    legacy=load('attachthread_preserve_legacy',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    protected=legacy.D.Assets.verify()
    core.atomic(O/'preservation.json',dict(trees=trees,protected=protected,genuine_launches=0,
        consumed_sha256=core.sha(candidate),complete_sandbox_copied=True,original_failure_retained=True))
    print('Consumed package, complete sandbox, build, ledger and runtime copied and verified; protected assets verified.',flush=True)


if __name__=='__main__': main()
