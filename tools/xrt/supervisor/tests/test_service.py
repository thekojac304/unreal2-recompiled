"""Queue state transitions with a synthetic handler; no executable is launched."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from supervisor import core as C
from supervisor.service import Service
from supervisor.policy import State, POLICY, decision


class QueueState(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=C.ROOT/'out')
        self.home=Path(self.temp.name)
        self.service=Service(self.home,0,qualification=True)
        self.exe=self.home/'dummy.exe';self.exe.write_bytes(b'never executed')
        self.candidates=[]

    def tearDown(self):
        for p in self.candidates:p.unlink(missing_ok=True)
        self.temp.cleanup()

    def request(self):
        ident=str(uuid.uuid4());manifest=dict(kind='fixture',sha256=C.sha(self.exe),dependencies={})
        path=self.home/'candidates'/(ident+'.json');C.atomic(path,manifest)
        req=dict(version=1,id=ident,batch_id=self.service.batch['id'],created_at=time.time(),expires_at=time.time()+120,
                 objective='Simulate queue handling without process execution',candidate='out/desktop-supervisor/candidates/'+ident+'.json',
                 manifest_sha256=C.sha(path),expected_stop=dict(kind='fixture-complete'),scope=C.FIXTURE_SCOPE,timeout_seconds=1)
        queued=self.home/'requests'/(ident+'.json');C.atomic(queued,req)
        return queued,req

    def test_expected_stop_then_distinct_request_keeps_waiting(self):
        result=dict(classification='expected-unsupported-method',passed=True,cleanup=dict(passed=True))
        def run(m,r,d,s,stop):
            C.atomic(d/'assurance.json',dict(cleanup_verified=True,integrity_verified=True))
            return result
        with patch('supervisor.core.validate_manifest',return_value=self.exe),patch('supervisor.fixture.run',side_effect=run) as runner:
            for _ in range(2):
                path,_=self.request();self.assertTrue(self.service.process(path)['passed']);self.assertFalse(self.service.halted)
            self.assertEqual(runner.call_count,2)

    def test_malformed_and_stale_never_reach_runner(self):
        with patch('supervisor.fixture.run') as runner:
            path,req=self.request();req['expires_at']=time.time()-1;C.atomic(path,req)
            self.assertEqual(self.service.process(path)['classification'],'rejected')
            path=self.home/'requests'/(str(uuid.uuid4())+'.json');path.write_bytes(b'{')
            self.assertEqual(self.service.process(path)['classification'],'rejected')
            runner.assert_not_called();self.assertFalse(self.service.halted)

    def test_integrity_failure_latches_batch(self):
        path,req=self.request();req['manifest_sha256']='0'*64;C.atomic(path,req)
        with patch('supervisor.fixture.run') as runner:
            self.assertEqual(self.service.process(path)['classification'],'integrity-or-unclassified-failure')
            self.assertTrue(self.service.halted);runner.assert_not_called()
            path,_=self.request();self.assertEqual(self.service.process(path)['classification'],'rejected')

    def test_interrupted_processing_is_never_retried(self):
        (self.home/'processing'/(str(uuid.uuid4())+'.json')).write_text('{}')
        restarted=Service(self.home,0,qualification=True)
        self.assertTrue(restarted.halted)

    def hold(self, **facts):
        out=self.home/'evidence'/uuid.uuid4().hex;out.mkdir()
        C.atomic(out/'original.json',dict(failure='retained'))
        finding=decision({},assurance=dict(cleanup_verified=True,integrity_verified=True,**facts))
        self.service.apply_decision(finding,out)
        return out

    def authorize(self):
        self.service.batch['recovery_policy']=POLICY
        self.service.bind_seal(dict(files={},host_files={}))
        self.service.ledger.append('batch-authorized',batch=self.service.batch,genuine_owner_console=False,
                                  qualification_sha256=self.service.seal_identity)

    def test_contained_unknown_is_diagnostic_but_never_routine(self):
        self.hold()
        self.assertEqual(self.service.operational_state,State.DIAGNOSTIC_HOLD)
        self.assertEqual(self.service.hold['category'],'unclassified-correctness-failure')
        self.authorize()
        with patch('supervisor.recovery.validate') as validator:
            self.assertFalse(self.service.try_recover());validator.assert_not_called()

    def test_diagnostics_continue_but_game_requests_are_rejected(self):
        self.hold(fixture_defect=True)
        self.service.batch['genuine_limit']=2
        path,req=self.request();req.update(scope=C.SCOPE,expected_stop=dict(kind='permanent-stop',guest_address='0x0696f292'));C.atomic(path,req)
        with patch('supervisor.genuine.run') as game:
            self.assertIn('DIAGNOSTIC HOLD',self.service.process(path)['reason']);game.assert_not_called()
        def run(m,r,d,s,stop):
            C.atomic(d/'assurance.json',dict(cleanup_verified=True,integrity_verified=True))
            return dict(classification='fixture-complete',passed=True)
        with patch('supervisor.core.validate_manifest',return_value=self.exe),patch('supervisor.fixture.run',side_effect=run):
            path,_=self.request();self.assertTrue(self.service.process(path)['passed'])
        self.assertEqual(self.service.operational_state,State.DIAGNOSTIC_HOLD)

    def test_qualified_recovery_preserves_evidence_batch_and_ledger(self):
        out=self.hold(fixture_defect=True);original=(out/'original.json').read_bytes();self.authorize()
        batch=dict(self.service.batch);prefix=self.service.ledger.path.read_bytes()
        with patch('supervisor.service.verify_seal'),patch('supervisor.recovery.validate',return_value=dict(passed=True)):
            self.assertTrue(self.service.try_recover())
        self.assertEqual(self.service.operational_state,State.RUNNING)
        self.assertEqual(self.service.batch,batch);self.assertTrue(self.service.ledger.path.read_bytes().startswith(prefix))
        self.assertEqual((out/'original.json').read_bytes(),original)

    def test_unresolved_guard_cannot_recover_even_after_passing_diagnostic(self):
        self.hold(guard_failed_closed=True);self.authorize()
        with patch('supervisor.recovery.validate') as validator:
            self.assertFalse(self.service.try_recover());validator.assert_not_called()
        self.assertEqual(self.service.operational_state,State.DIAGNOSTIC_HOLD)

    def test_failed_validation_does_not_clear_hold(self):
        self.hold(fixture_defect=True);self.authorize()
        with patch('supervisor.service.verify_seal'),patch('supervisor.recovery.validate',return_value=dict(passed=False)):
            self.assertFalse(self.service.try_recover())
        self.assertEqual(self.service.operational_state,State.DIAGNOSTIC_HOLD)

    def test_no_policy_or_no_authorization_or_expired_batch_cannot_recover(self):
        self.hold(fixture_defect=True)
        with patch('supervisor.recovery.validate') as validator:
            self.assertFalse(self.service.try_recover())
            self.service.batch['recovery_policy']=POLICY
            self.assertFalse(self.service.try_recover())
            self.authorize();self.service.batch['expires_at']=time.time()-1
            self.assertFalse(self.service.try_recover());validator.assert_not_called()

    def test_authorization_expiring_during_validation_cannot_recover(self):
        self.hold(fixture_defect=True);self.authorize()
        def expired(*_):
            self.service.batch['expires_at']=time.time()-1
            return dict(passed=True)
        with patch('supervisor.service.verify_seal'),patch('supervisor.recovery.validate',side_effect=expired):
            self.assertFalse(self.service.try_recover())
        self.assertEqual(self.service.operational_state,State.DIAGNOSTIC_HOLD)

    def test_unknown_following_routine_cannot_be_laundered_by_success(self):
        self.hold(fixture_defect=True);self.hold();self.authorize()
        self.assertEqual(len(self.service.hold['failures']),2)
        self.assertFalse(self.service.try_recover())

    def test_evidence_or_enforcement_tamper_is_safety_halt(self):
        out=self.hold(fixture_defect=True);self.authorize();(out/'original.json').write_text('corrupt')
        with patch('supervisor.service.verify_seal'),patch('supervisor.recovery.validate') as validator:
            self.assertFalse(self.service.try_recover());validator.assert_not_called()
        self.assertEqual(self.service.operational_state,State.SAFETY_HALT)

    def test_safety_halt_survives_restart_and_never_rewrites_first_latch(self):
        self.service.halt('first integrity failure');original=(self.home/'HALTED.json').read_bytes()
        self.service.halt('second integrity failure');self.assertEqual((self.home/'HALTED.json').read_bytes(),original)
        restarted=Service(self.home,0,qualification=True)
        self.assertEqual(restarted.operational_state,State.SAFETY_HALT)
        self.assertFalse(restarted.try_recover())

    def test_restart_cannot_renew_held_batch_authorization(self):
        self.hold(fixture_defect=True);self.authorize()
        restarted=Service(self.home,1,qualification=True);restarted.batch['recovery_policy']=POLICY
        self.assertEqual(restarted.operational_state,State.DIAGNOSTIC_HOLD)
        self.assertFalse(restarted.try_recover())

    def test_exception_cannot_skip_identity_check(self):
        path,_=self.request()
        def run(m,r,d,s,stop):
            C.atomic(d/'assurance.json',dict(cleanup_verified=True,integrity_verified=True,fixture_defect=True))
            raise C.Rejected('contained harness error')
        with patch('supervisor.core.validate_manifest',side_effect=[self.exe,C.IntegrityFailure('changed binary')]),patch('supervisor.fixture.run',side_effect=run):
            self.service.process(path)
        self.assertEqual(self.service.operational_state,State.SAFETY_HALT)

    def test_security_source_change_during_recovery_requires_review(self):
        self.hold(fixture_defect=True);self.authorize()
        with patch('supervisor.service.verify_seal',side_effect=C.IntegrityFailure('qualified source changed')),patch('supervisor.recovery.validate') as validator:
            self.assertFalse(self.service.try_recover());validator.assert_not_called()
        self.assertEqual(self.service.operational_state,State.SAFETY_HALT)

    def test_stop_or_exhausted_batch_cannot_recover(self):
        self.hold(fixture_defect=True);self.authorize();(self.home/'STOP').touch()
        with patch('supervisor.recovery.validate') as validator:
            self.assertFalse(self.service.try_recover());validator.assert_not_called()
        (self.home/'STOP').unlink()
        self.service.qualification=False;self.service.desktop=__import__('unittest.mock',fromlist=['Mock']).Mock()
        self.service.ledger.append('batch-authorized',batch=self.service.batch,genuine_owner_console=True,
                                  qualification_sha256=self.service.seal_identity)
        with patch('supervisor.service.verify_seal'),patch('supervisor.recovery.validate',return_value=dict(passed=True)):
            self.assertFalse(self.service.try_recover())  # zero authorized genuine slots
        self.assertEqual(self.service.operational_state,State.DIAGNOSTIC_HOLD)

    def test_queue_cannot_supply_recovery_flags(self):
        path,req=self.request();req['recovery_policy']=POLICY;C.atomic(path,req)
        with patch('supervisor.fixture.run') as runner:
            self.assertEqual(self.service.process(path)['classification'],'rejected');runner.assert_not_called()

    def test_owner_review_requires_local_interactive_console(self):
        from supervisor.service import review_halt
        with patch('supervisor.environment.ordinary_user'),patch('supervisor.service.sys.stdin.isatty',return_value=False):
            with self.assertRaisesRegex(C.Rejected,'owner console'):review_halt()

    def test_guard_blocker_survives_later_routine_failures(self):
        self.hold(guard_failed_closed=True);self.hold(fixture_defect=True);self.authorize()
        self.assertTrue(self.service.hold['isolation_guard_unresolved'])
        self.assertFalse(self.service.try_recover())

    def test_owner_review_archives_original_halt_and_preserves_consumed_identity(self):
        from supervisor.service import review_halt
        self.service.ledger.append('launch-claimed',request_id=str(uuid.uuid4()),batch_id='prior',sha256='c'*64)
        self.service.halt('synthetic containment failure')
        prefix=self.service.ledger.path.read_bytes();latch=(self.home/'HALTED.json').read_bytes()
        seal=dict(passed=True,helper_guard=dict(guard_verified=True),evidence='synthetic non-game qualification')
        C.atomic(self.home/'qualification.json',seal)
        phrase='REVIEW SAFETY HALT '+C.digest(seal)[:16]
        (self.home/'STOP').touch()
        with patch.object(C,'HOME',self.home),patch('supervisor.environment.ordinary_user'),patch('supervisor.service.verify_seal'),\
                patch('supervisor.service.sys.stdin.isatty',return_value=True),patch('builtins.input',return_value=phrase),patch('builtins.print'):
            review_halt()
        self.assertTrue(self.service.ledger.path.read_bytes().startswith(prefix))
        self.assertEqual(next((self.home/'owner-reviews').glob('*/HALTED.json')).read_bytes(),latch)
        self.assertTrue((self.home/'STOP').exists())
        restarted=Service(self.home,1,qualification=True)
        self.assertEqual(restarted.operational_state,State.RUNNING)
        with self.assertRaises(C.Rejected):
            restarted.ledger.claim(dict(id=str(uuid.uuid4())),dict(kind='genuine',sha256='c'*64),restarted.batch)


class Classification(unittest.TestCase):
    def test_validator_integrity_fault_is_not_downgraded_to_routine_failure(self):
        from supervisor.recovery import validate
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=C.ROOT/'out') as d:
            out=Path(d)
            C.atomic(out/'independent-failure.json',dict(safety_halt=True,reason='process tree cleanup incomplete'))
            with patch('supervisor.recovery.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'')):
                with self.assertRaisesRegex(C.IntegrityFailure,'cleanup incomplete'):
                    validate(out,dict(fixture_sha256='f'*64,helper={}),dict(failures=[]),{})

    def test_validator_crash_without_cleanup_evidence_is_safety_failure(self):
        from supervisor.recovery import validate
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=C.ROOT/'out') as d:
            with patch('supervisor.recovery.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'')):
                with self.assertRaisesRegex(C.IntegrityFailure,'crashed'):
                    validate(Path(d),dict(fixture_sha256='f'*64,helper={}),dict(failures=[]),{})

    def test_evidence_based_failure_matrix(self):
        safe=dict(cleanup_verified=True,integrity_verified=True)
        for facts,category,recoverable in [({},'unclassified-correctness-failure',False),
              (dict(fixture_defect=True),'routine-fixture-defect',True),
              (dict(routine_observer_defect=True),'routine-observer-defect',True),
              (dict(helper_startup_failed=True),'contained-helper-startup',True),
              (dict(documented_x87_difference=True),'documented-experimental-x87-difference',False)]:
            with self.subTest(category=category):
                d=decision({},assurance=dict(safe,**facts));self.assertEqual(d['state'],State.DIAGNOSTIC_HOLD)
                self.assertEqual(d['category'],category);self.assertEqual(d['recoverable'],recoverable)
        for assurance in ({},dict(safe,cleanup_verified=False),dict(safe,integrity_verified=False)):
            self.assertEqual(decision({},assurance=assurance)['state'],State.SAFETY_HALT)
        self.assertEqual(decision({},error=C.IntegrityFailure('host crash'),assurance=safe)['state'],State.SAFETY_HALT)
        self.assertEqual(decision({},assurance=dict(safe,unexpected_host_crash=True))['state'],State.SAFETY_HALT)

    def test_expected_compatibility_boundary_requires_success_and_cleanup(self):
        result=dict(classification='expected-unsupported-method',passed=True)
        self.assertEqual(decision(result,assurance=dict(cleanup_verified=True,integrity_verified=True))['state'],State.RUNNING)
        self.assertEqual(decision(result)['state'],State.SAFETY_HALT)


if __name__=='__main__':unittest.main()
