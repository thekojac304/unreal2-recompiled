"""Live non-game iterations through the production state machine and validator."""
import time
import uuid
from pathlib import Path
from unittest.mock import patch
from . import core
from .policy import State, POLICY, decision
from .service import Service, seal_files


def qualify(out, exe, helper):
    from .qualify import request
    home=out/'autonomy-queue'
    service=Service(home,2,qualification=True)
    seal=dict(files=seal_files(),host_files={},fixture_sha256=core.sha(exe),helper=helper)
    service.bind_seal(seal)
    service.batch['recovery_policy']=POLICY
    service.ledger.append('batch-authorized',batch=service.batch,genuine_owner_console=False,
                          qualification_sha256=service.seal_identity,qualification_only=True)
    # A synthetic old consumed identity tests the exact durable no-retry gate.
    consumed='d'*64
    service.ledger.append('launch-claimed',request_id=str(uuid.uuid4()),batch_id='synthetic-older-batch',
                          sha256=consumed,qualification_only=True)
    prefix=service.ledger.path.read_bytes()
    iterations=[]
    for iteration in range(2):
        # Inject a non-security observer/reporting defect *after* actual fixture
        # execution and cleanup. The independent interpreter reruns the failed
        # exact profile with the injection removed, as well as all safety gates.
        from .fixture import run as real_fixture
        def observer_defect(m,r,d,s,stop):
            result=real_fixture(m,r,d,s,stop)
            core.atomic(d/'assurance.json',dict(cleanup_verified=True,integrity_verified=True,routine_observer_defect=True))
            result.update(passed=False,classification='unclassified-discrepancy',error='qualification-injected reporting defect')
            return result
        with patch('supervisor.fixture.run',side_effect=observer_defect):
            failed=service.process(request(service,exe,'ok-a'))
        core.require(service.operational_state==State.DIAGNOSTIC_HOLD and not failed['passed'], 'contained fixture did not hold')
        failed_bytes=(Path(failed['evidence'])/'result.json').read_bytes()
        game=request(service,exe,'ok-a'); data=core.read(game)
        data.update(scope=core.SCOPE,expected_stop=dict(kind='permanent-stop',guest_address='0x0696f292'))
        core.atomic(game,data)
        blocked=service.process(game)
        core.require(blocked['classification']=='rejected' and 'DIAGNOSTIC HOLD' in blocked['reason'], 'held genuine request reached execution')
        diagnostic=service.process(request(service,exe,'hard-stop'))
        core.require(diagnostic['passed'] and service.operational_state==State.DIAGNOSTIC_HOLD,'diagnostic cleared hold')
        core.require(service.try_recover() and service.operational_state==State.RUNNING,'independent recovery failed')
        core.require((Path(failed['evidence'])/'result.json').read_bytes()==failed_bytes,'failed attempt rewritten')
        iterations.append(dict(iteration=iteration+1,failed=failed,blocked=blocked,diagnostic=diagnostic,qualified_recovery=True))
    core.require(service.ledger.path.read_bytes().startswith(prefix),'ledger history changed')
    try:
        service.ledger.claim(dict(id=str(uuid.uuid4())),dict(kind='genuine',sha256=consumed),service.batch)
        raise AssertionError('consumed synthetic identity accepted')
    except core.Rejected:pass
    unresolved=service.process(request(service,exe,'routine-failure'))
    core.require(service.operational_state==State.DIAGNOSTIC_HOLD,'routine defect not held')
    core.require(not service.try_recover() and service.operational_state==State.DIAGNOSTIC_HOLD,
                 'validator ignored the exact still-failing fixture profile')
    # Use the actual failed-closed helper evidence, without relaunching a game.
    evidence=out/'guard-hold-evidence';evidence.mkdir()
    core.atomic(evidence/'helper-proof.json',core.read(out/'helper-guard/result.json'))
    finding=decision({},assurance=dict(cleanup_verified=True,integrity_verified=True,guard_failed_closed=True))
    service.apply_decision(finding,evidence)
    core.require(not service.try_recover() and service.operational_state==State.DIAGNOSTIC_HOLD,'guard hold recovered automatically')
    # Actual manifest hash mismatch, rather than a self-reported safety label.
    tampered=request(service,exe,'ok-b'); data=core.read(tampered);data['manifest_sha256']='0'*64;core.atomic(tampered,data)
    safety=service.process(tampered)
    core.require(service.operational_state==State.SAFETY_HALT,'integrity violation did not halt')
    original=(home/'HALTED.json').read_bytes()
    rejected=service.process(request(service,exe,'ok-a'))
    core.require(rejected['classification']=='rejected' and not service.try_recover(),'safety halt overridden')
    core.require((home/'HALTED.json').read_bytes()==original,'halt record rewritten')
    restarted=Service(home,0,qualification=True)
    core.require(restarted.operational_state==State.SAFETY_HALT,'restart bypassed halt')
    result=dict(passed=True,iterations=iterations,unresolved_guard_recovery_refused=True,integrity_halt=safety,
                halt_cannot_be_overridden=True,ledger_prefix_unchanged=True,consumed_identity_retained=True,
                unresolved_fixture_recheck_refused=True,unresolved_fixture=unresolved,
                independent_validator_processes=3,successful_recoveries=2,injected_reporting_defects=True,genuine_sessions=0)
    core.atomic(out/'autonomy-result.json',result)
    return result
