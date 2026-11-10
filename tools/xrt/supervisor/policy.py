"""Operational policy. Only sealed code supplies facts; queue JSON cannot."""
from enum import StrEnum
from . import core


class State(StrEnum):
    RUNNING = 'RUNNING'
    DIAGNOSTIC_HOLD = 'DIAGNOSTIC HOLD'
    SAFETY_HALT = 'SAFETY HALT'


POLICY = 'contained-development-v1'
RECOVERABLE = frozenset(('routine-fixture-defect', 'routine-observer-defect', 'contained-helper-startup'))


def decision(observed, *, error=None, assurance=None):
    """Missing containment/integrity evidence always closes the execution gate."""
    a = assurance or {}
    safe = (a.get('cleanup_verified') is True and a.get('integrity_verified') is True)
    if isinstance(error, core.IntegrityFailure) or not safe or a.get('unexpected_host_crash') is True:
        return dict(state=State.SAFETY_HALT, category='security-integrity-containment',
                    recoverable=False, reason=str(error or 'containment/integrity evidence missing'))
    c = observed.get('classification')
    if error is None and c in ('fixture-complete', 'expected-unsupported-method', 'permanent-stop') and observed.get('passed') is True:
        return dict(state=State.RUNNING, category=('expected-compatibility-boundary' if c=='expected-unsupported-method' else c),
                    recoverable=False, reason='verified expected stop')
    # These are explicit observer-supplied facts, never request-supplied labels.
    if a.get('guard_failed_closed') is True:
        return dict(state=State.DIAGNOSTIC_HOLD, category='contained-helper-startup', recoverable=False,
                    isolation_guard_unresolved=True, reason='guard failed closed; independent guard verification and owner review required')
    if a.get('helper_startup_failed') is True:
        category = 'contained-helper-startup'
    elif a.get('routine_observer_defect') is True:
        category = 'routine-observer-defect'
    elif a.get('fixture_defect') is True:
        category = 'routine-fixture-defect'
    elif a.get('documented_x87_difference') is True:
        # A documented experiment is still a strict failure, never a renderer pass.
        category = 'documented-experimental-x87-difference'
    else:
        category = 'unclassified-correctness-failure'
    return dict(state=State.DIAGNOSTIC_HOLD, category=category,
                recoverable=category in RECOVERABLE, reason=str(error or c or 'unknown correctness failure'))


def recovery_allowed(hold, batch, *, now):
    return (batch.get('recovery_policy') == POLICY and hold.get('batch_id') == batch['id']
            and batch['started_at'] <= now < batch['expires_at']
            and hold.get('recoverable') is True and hold.get('category') in RECOVERABLE
            and not hold.get('isolation_guard_unresolved'))
