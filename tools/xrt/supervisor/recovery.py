"""Fixed independent non-game validator. No queue-selected commands or imports."""
import subprocess
import sys
from . import core


def validate(out, seal, hold, batch):
    fixture_rechecks = []
    from pathlib import Path
    for failure in hold['failures']:
        parent=Path(failure['path']).parent
        if (parent/'candidate.json').exists() and (parent/'request.json').exists():
            m=core.read(parent/'candidate.json'); r=core.read(parent/'request.json')
            if m.get('kind')=='fixture':
                fixture_rechecks.append(dict(case=m['fixture_case'],expected_stop=r['expected_stop']))
    payload = dict(seal_sha256=core.digest(seal), hold_sha256=core.digest(hold), batch_sha256=core.digest(batch),
                   fixture_sha256=seal['fixture_sha256'], helper=seal['helper'], fixture_rechecks=fixture_rechecks)
    core.atomic(out/'validation-input.json',payload)
    # Separate interpreter; the failed observer instance cannot certify its repair.
    try:
        p = subprocess.run([sys.executable,'-B','-I',str(core.ROOT/'tools/xrt/supervisor/recovery_worker.py'),str(out)],
                           cwd=core.ROOT,capture_output=True,timeout=60)
    except subprocess.TimeoutExpired as e:
        raise core.IntegrityFailure('independent validator lost; final containment/cleanup unverified') from e
    (out/'validator.stdout.bin').write_bytes(p.stdout); (out/'validator.stderr.bin').write_bytes(p.stderr)
    if p.returncode!=0:
        failure=out/'independent-failure.json'
        if not failure.exists():
            raise core.IntegrityFailure('validator crashed without final safety evidence')
        error=core.read(failure)
        if error.get('safety_halt') is True:
            raise core.IntegrityFailure('validator safety failure: '+error['reason'])
        return dict(passed=False,reason='independent non-game validation failed',exit=p.returncode,failure=error)
    result = core.read(out/'independent-result.json')
    core.require(result.get('bindings')==payload,'recovery validation identity mismatch')
    core.require(result.get('genuine_sessions')==0 and result.get('helper_guard',{}).get('guard_verified') is True
                 and result.get('observer',{}).get('passed') is True
                 and len(result.get('watchdog_and_cleanup',[]))==3
                 and all(r.get('passed') is True and r.get('cleanup',{}).get('passed') is True
                         for r in result['watchdog_and_cleanup']), 'independent recovery gates incomplete')
    return result
