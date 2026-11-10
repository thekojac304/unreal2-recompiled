"""Read-only inventories for the redesign; never opens a genuine executable."""
import json
from pathlib import Path
from . import core


def snapshot():
    files = {}
    for name in ('HALTED.json', 'status.json', 'ledger.jsonl', 'readiness.json'):
        p = core.HOME / name
        if p.exists(): files[str(p)] = core.sha(p)
    for folder in ('requests', 'processing', 'responses', 'archive', 'evidence', 'candidates'):
        for p in (core.HOME / folder).rglob('*'):
            if p.is_file(): files[str(p)] = core.sha(core.independent(p))
    for folder in ('experiments/xrt/runtime', 'experiments/xrt/gen',
                   'experiments/xrt/dmusic_helper',
                   'experiments/xrt/build/renderer-batch-20261029-01/candidate-1',
                   'experiments/xrt/build/queryclass-20261029-01/client'):
        for p in (core.ROOT / folder).rglob('*'):
            if p.is_file(): files[str(p)] = core.sha(core.independent(p))
    strict = core.ROOT / 'out/recovery/viewport-getobject-20261028-01/strict-failures-retained.json'
    files[str(strict)] = core.sha(strict)
    from .environment import load
    retained = load('redesign_protected_assets', core.ROOT / 'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    return dict(files=files, protected=retained.D.Assets.verify(),
                ledger_rows=len(core.Ledger(core.HOME / 'ledger.jsonl').rows),
                consumed=[r for r in core.Ledger(core.HOME / 'ledger.jsonl').rows if r['kind']=='launch-claimed'])


if __name__ == '__main__':
    import sys
    out = Path(sys.argv[1])
    current = snapshot()
    if len(sys.argv) > 2:
        before = core.read_large(sys.argv[2])
        # The old idle process held source pins. Its normal STOP shutdown changed
        # only the activity word in status; retain and verify that original too.
        status = str(core.HOME/'status.json')
        original = core.read_large(out.parent/'original-halted-status.json')
        stopped = core.read_large(core.HOME/'status.json')
        core.require(core.sha(out.parent/'original-halted-status.json')==before['files'][status], 'original halted status lost')
        core.require(stopped==dict(original,state='stopped'), 'unexpected production status change')
        expected = dict(before,files=dict(before['files']))
        expected['files'][status] = current['files'][status]
        core.require(current == expected, 'production history/source/asset preservation failure')
        core.atomic(out, dict(passed=True,controlled_status_change='normal STOP shutdown; original preserved',
                             stop_retained=(core.HOME/'STOP').exists(), **current))
    else:
        core.atomic(out, current)
