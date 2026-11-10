"""Fresh non-game receipts without modifying the sealed semantic handoff.

Only owned diagnostic executables may run. The candidate is never executed.
"""
import json
import io
import shutil
import sys
import time
import unittest
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE.parents[3]
SOURCE = HERE.parent / 'semantic_compat'
PRIOR = WORK / 'out/recovery/semantic-compat-20261029-01'
OUT = WORK / 'out/recovery/semantic-physical-20261030-01'
sys.path.insert(0, str(SOURCE))
import common
from common import core


def seal_check():
    seal = core.read_large(PRIOR / 'handoff-seal.json')
    changed = []
    for name, expected in seal['files'].items():
        path = core.independent(name)
        if core.sha(path) != expected:
            changed.append(name)
    result = dict(passed=not changed, checked_at=time.time(), files=len(seal['files']),
                  seal_sha256=core.sha(PRIOR / 'handoff-seal.json'), changed=changed,
                  candidate_instructions_executed=0)
    core.atomic(OUT / 'prior-seal-verification.json', result)
    core.require(not changed, 'sealed semantic package changed: ' + str(changed))
    print('Prior seal PASS:', len(seal['files']), 'files', flush=True)


def setup():
    OUT.mkdir(parents=True, exist_ok=True)
    # Preserve the complete old output package; redirected verifier outputs go here.
    for name in ('build.json', 'object-lineage.json', 'contracts.json', 'preservation.json'):
        source, target = PRIOR / name, OUT / name
        if target.exists():
            core.require(core.sha(source) == core.sha(target), 'copied input changed')
        else:
            shutil.copy2(source, target)
    common.O = OUT


def main():
    setup()
    command = sys.argv[1]
    if command == 'verify':
        seal_check()
        import verify
        verify.main()
    elif command == 'observer':
        # Run with the redirected common module so test-created evidence also
        # stays in this new package, rather than appending to the prior handoff.
        import test_observer
        root = OUT / ('observer-tests-' + str(uuid.uuid4()))
        root.mkdir()
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromModule(test_observer))
        (root / 'unittest.txt').write_text(stream.getvalue(), encoding='utf-8')
        core.atomic(OUT / 'final-observer-tests.json', dict(passed=result.wasSuccessful(),
            root=str(root), tests=result.testsRun,
            observer_sha256=core.sha(SOURCE / 'observer.py'),
            command=[sys.executable, '-B', '-I', str(Path(__file__)), 'observer'],
            exit=0 if result.wasSuccessful() else 1))
        core.require(result.wasSuccessful(), 'final observer tests failed')
        print('Final observer:', result.testsRun, 'PASS', flush=True)
        import live_observer
        live_observer.main()
    elif command == 'hardware':
        import qualify
        qualify.main()
    elif command == 'preservation':
        seal_check()
        import finalize
        finalize.preservation()
    elif command == 'availability':
        result = {}
        for name in ('desktop-fixtures', 'desktop-prerequisites'):
            path = WORK / 'out' / name / 'status.json'
            status = core.read(path)
            result[name] = dict(saved_status=status, sha256=core.sha(path),
                                expired=status['batch']['expires_at'] <= time.time(),
                                heartbeat_age_seconds=time.time()-status.get('updated_at', 0))
        core.atomic(OUT / 'physical-availability.json', dict(observed_at=time.time(), services=result))
        print(json.dumps(result, indent=2))
    else:
        raise ValueError('expected verify, observer, hardware, preservation or availability')


if __name__ == '__main__':
    main()
