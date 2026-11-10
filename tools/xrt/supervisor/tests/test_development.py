"""Protocol and persistent fixture policy; no graphics or game execution."""
from pathlib import Path
import tempfile
import struct
import time
import unittest
from unittest.mock import patch, Mock
import uuid
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from supervisor import core, fixture_profiles as P
from supervisor.development import FixtureService, DesktopUnavailable, physical_gate
from supervisor.policy import State


class Protocol(unittest.TestCase):
    def setUp(self):
        stamp = time.time()
        self.batch = dict(id=str(uuid.uuid4()), started_at=stamp-1, expires_at=stamp+3600)
        self.request = dict(version=2, id=str(uuid.uuid4()), batch_id=self.batch['id'], created_at=stamp,
            expires_at=stamp+120, objective='Run fixed harmless collector fixture', profile='fast-development',
            family='collector-smoke', parameters=dict(arch='x64', case='normal'), candidate_id=str(uuid.uuid4()),
            candidate_sha256='a'*64, timeout_seconds=5)

    def test_valid_request(self):
        self.assertIs(P.parse(self.request, self.batch), self.request)

    def test_no_queue_command_or_environment_or_path_fields(self):
        for key in ('command','executable','args','cwd','environment','shell','validator','recovery_policy','physical','qualification','output','build_record'):
            with self.subTest(key=key), self.assertRaises(core.Rejected):
                P.parse(dict(self.request, **{key:'anything'}), self.batch)

    def test_strict_scalar_and_time_validation(self):
        for key, value in [('version',True),('timeout_seconds',True),('timeout_seconds',0),('timeout_seconds',61),
                           ('timeout_seconds',1.5),('candidate_id','../game'),('candidate_id','C:/game.exe'),
                           ('candidate_sha256','z'*64),('created_at',float('nan')),('expires_at',float('inf')),
                           ('created_at',time.time()-20),('expires_at',time.time()-1),('batch_id',str(uuid.uuid4()))]:
            with self.subTest(key=key,value=value), self.assertRaises(core.Rejected):
                P.parse(dict(self.request, **{key:value}), self.batch)

    def test_profile_and_argument_matrix(self):
        for family, params in [('collector-smoke',dict(arch='x64',case='normal')),
                               ('renderer-abi',dict(group=1,arch='x86',variant='native')),
                               ('renderer-group',dict(group=7,arch='x64',variant='translated')),
                               ('renderer-batch-23',{})]:
            profile = 'formal-acceptance' if family == 'renderer-batch-23' else 'fast-development'
            P.parameters(family,params,profile)
        for family, params, profile in [
            ('renderer-batch-23',{},'fast-development'), ('renderer-batch-23',dict(command='x'),'formal-acceptance'),
            ('renderer-group',dict(group=True,arch='x64',variant='native'),'fast-development'),
            ('renderer-group',dict(group=8,arch='x64',variant='native'),'fast-development'),
            ('renderer-group',dict(group=1,arch='x86',variant='translated'),'fast-development'),
            ('renderer-abi',dict(group=1,arch='x64',variant='native'),'formal-acceptance'),
            ('collector-smoke',dict(arch='../../game',case='normal'),'fast-development'),
            ('collector-smoke',dict(arch='x64',case='normal & calc'),'fast-development'),
            ('genuine',{},'fast-development')]:
            with self.subTest(family=family,params=params), self.assertRaises(core.Rejected):
                P.parameters(family,params,profile)

    def test_candidate_path_cannot_select_executable(self):
        for ident in ('../game','\\\\server\\game','C:/game.exe','foo:bar','CON',str(uuid.uuid4())+'/game.exe'):
            with self.subTest(ident=ident), self.assertRaises(core.Rejected): P.candidate_path(ident)

    def test_formal_plan_is_exactly_23_fixed_processes(self):
        items = P.plan('renderer-batch-23',{})
        self.assertEqual(len(items),23)
        self.assertEqual(len({i['name'] for i in items}),23)
        self.assertEqual(sum(i['group']==0 for i in items),2)
        self.assertTrue(all(i['exe'].is_relative_to(P.FROZEN/'build') and i['exe'].name=='fixture.exe' for i in items))
        self.assertFalse(any(i['group'] in (8,9) for i in items))


class Queue(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=core.ROOT/'out')
        self.home = Path(self.temp.name)
        self.runner = Mock(return_value=dict(passed=True,classification='fixture-complete'))
        self.gate = Mock()
        self.service = FixtureService(self.home,qualification=True,runner=self.runner,gate=self.gate)
        self.manifest = dict(id=str(uuid.uuid4()),files={})
        self.candidate = self.home/'candidate.json'; core.atomic(self.candidate,self.manifest)
        self.validation = patch('supervisor.fixture_profiles.validate_candidate',return_value=self.manifest); self.validation.start()
        self.paths = patch('supervisor.fixture_profiles.candidate_path',return_value=self.candidate); self.paths.start()

    def tearDown(self):
        self.validation.stop(); self.paths.stop(); self.temp.cleanup()

    def request(self, *, formal=False):
        stamp=time.time(); ident=str(uuid.uuid4())
        request=dict(version=2,id=ident,batch_id=self.service.batch['id'],created_at=stamp,expires_at=stamp+120,
                     objective='Exercise persistent fixture queue safely',profile='formal-acceptance' if formal else 'fast-development',
                     family='renderer-batch-23' if formal else 'collector-smoke',parameters={} if formal else dict(arch='x64',case='normal'),
                     candidate_id=self.manifest['id'],candidate_sha256=core.sha(self.candidate),timeout_seconds=3)
        path=self.home/'requests'/(ident+'.json'); core.atomic(path,request)
        return path,request

    def test_distinct_requests_reuse_disposable_candidate(self):
        for _ in range(3):
            path,_=self.request(); self.assertTrue(self.service.process(path)['passed'])
        self.assertEqual(self.runner.call_count,3)
        self.assertFalse(self.service.halted)
        self.assertFalse(any(r['kind']=='launch-claimed' for r in self.service.ledger.rows))

    def test_replay_preserves_original_result(self):
        path,request=self.request(); first=self.service.process(path)
        response=self.home/'responses'/path.name; original=response.read_bytes()
        core.atomic(path,request); replay=self.service.process(path)
        self.assertEqual(replay['classification'],'rejected'); self.assertEqual(response.read_bytes(),original)
        self.assertEqual(self.runner.call_count,1)

    def test_routine_collector_failure_then_corrected_fixture(self):
        self.runner.side_effect=[dict(passed=False,classification='collector-implementation-error'),dict(passed=True,classification='fixture-complete')]
        path,_=self.request(); self.assertFalse(self.service.process(path)['passed'])
        path,_=self.request(); self.assertTrue(self.service.process(path)['passed']); self.assertFalse(self.service.halted)

    def test_contained_python_exception_permits_later_development(self):
        def fail(request,candidate,out,*args,**kw):
            core.atomic(out/'assurance.json',dict(cleanup_verified=True,integrity_verified=True))
            raise ValueError('injected parser error')
        self.runner.side_effect=fail
        path,_=self.request(); self.assertEqual(self.service.process(path)['classification'],'collector-implementation-error')
        self.runner.side_effect=None
        path,_=self.request(); self.assertTrue(self.service.process(path)['passed'])

    def test_missing_containment_latches_and_blocks_next_request(self):
        self.runner.side_effect=RuntimeError('missing final receipt')
        path,_=self.request(); self.assertEqual(self.service.process(path)['classification'],'security-integrity-containment')
        latch=(self.home/'HALTED.json').read_bytes()
        self.runner.side_effect=None
        path,_=self.request(); self.assertEqual(self.service.process(path)['classification'],'rejected')
        self.assertEqual((self.home/'HALTED.json').read_bytes(),latch); self.assertEqual(self.runner.call_count,1)

    def test_integrity_exception_cannot_be_marked_routine(self):
        self.runner.side_effect=core.IntegrityFailure('source changed')
        path,_=self.request(); self.service.process(path)
        self.assertEqual(self.service.operational_state,State.SAFETY_HALT)

    def test_post_run_identity_checked_on_handler_exception(self):
        self.runner.side_effect=ValueError('parser')
        with patch('supervisor.fixture_profiles.validate_candidate',side_effect=[self.manifest,core.IntegrityFailure('changed executable')]):
            path,_=self.request(); self.assertEqual(self.service.process(path)['classification'],'security-integrity-containment')

    def test_desktop_unavailable_preserves_queue_without_claim(self):
        self.gate.side_effect=DesktopUnavailable('locked')
        path,request=self.request(formal=True); original=path.read_bytes()
        self.assertIsNone(self.service.process(path)); self.assertEqual(path.read_bytes(),original)
        self.assertEqual(core.read(self.home/'status.json')['state'],'paused'); self.runner.assert_not_called()
        self.gate.side_effect=None
        self.assertTrue(self.service.process(path)['passed'])

    def test_queued_cancellation_never_launches(self):
        path,request=self.request(); core.atomic(self.home/'cancel'/(request['id']+'.json'),dict(id=request['id']))
        self.assertEqual(self.service.process(path)['classification'],'cancelled'); self.runner.assert_not_called()

    def test_unknown_blocks_formal_but_keeps_development_available(self):
        self.runner.return_value=dict(passed=False,classification='unclassified-correctness')
        path,_=self.request(); self.service.process(path)
        self.runner.return_value=dict(passed=True,classification='fixture-complete')
        path,_=self.request(); self.assertTrue(self.service.process(path)['passed'])
        path,_=self.request(formal=True); self.assertEqual(self.service.process(path)['classification'],'rejected')
        restarted=FixtureService(self.home,qualification=True,runner=self.runner,gate=self.gate)
        self.assertEqual(restarted.unresolved,self.service.unresolved)

    def test_interrupted_claim_is_safety_halt(self):
        (self.home/'processing'/(str(uuid.uuid4())+'.json')).write_text('{}')
        restarted=FixtureService(self.home,qualification=True)
        self.assertEqual(restarted.operational_state,State.SAFETY_HALT)

    def test_malformed_queue_never_reaches_runner(self):
        path,request=self.request(); request['command']='calc.exe'; core.atomic(path,request)
        self.assertEqual(self.service.process(path)['classification'],'rejected'); self.runner.assert_not_called()

    def test_stop_cannot_be_ignored(self):
        (self.home/'STOP').touch(); path,_=self.request()
        self.assertEqual(self.service.process(path)['classification'],'rejected'); self.runner.assert_not_called()

    def test_authorization_expiry_cancels_active_fixture(self):
        self.service.batch['expires_at']=time.time()-1
        self.assertTrue(self.service.cancelled(str(uuid.uuid4())))

    def test_queue_swap_during_preflight_is_detected(self):
        path,request=self.request()
        def swap(*args,**kwargs):
            core.atomic(path,dict(request,objective='Changed objective during preflight'))
        self.gate.side_effect=swap
        result=self.service.process(path)
        self.assertEqual(result['classification'],'security-integrity-containment'); self.runner.assert_not_called()

    def test_hardlinked_queue_object_is_preserved_and_halts(self):
        import os
        path,request=self.request(); other=self.home/'hardlink.json'; os.link(path,other)
        result=self.service.process(path)
        self.assertEqual(self.service.operational_state,State.SAFETY_HALT)
        self.assertTrue(path.exists()); self.assertTrue(other.exists()); self.runner.assert_not_called()

    def test_external_latch_blocks_dispatch(self):
        core.atomic(self.home/'HALTED.json',dict(reason='owner stop for integrity review'))
        path,_=self.request(); result=self.service.process(path)
        self.assertEqual(result['classification'],'rejected'); self.assertTrue(self.service.halted); self.runner.assert_not_called()

    def test_status_reader_sharing_race_is_retried(self):
        real=core.atomic; calls=[]
        def write(path,value):
            calls.append(path)
            if len(calls)==1: raise PermissionError('temporary Windows read sharing')
            return real(path,value)
        with patch('supervisor.core.atomic',side_effect=write): self.service.publish(state='waiting')
        self.assertEqual(len(calls),2); self.assertEqual(core.read(self.home/'status.json')['state'],'waiting')

    def test_status_read_replace_race_is_retried(self):
        from supervisor.development import read_status
        self.service.publish(state='waiting'); real=core.read; calls=[]
        def read(path):
            calls.append(path)
            if len(calls)==1: raise PermissionError('temporary Windows replacement')
            return real(path)
        with patch('supervisor.core.read',side_effect=read):
            self.assertEqual(read_status(self.home)['state'],'waiting')
        self.assertEqual(len(calls),2)

    def test_owner_review_requires_local_console(self):
        from supervisor.development import review
        with patch('supervisor.environment.ordinary_user'), patch('supervisor.development.sys.stdin.isatty',return_value=False):
            with self.assertRaisesRegex(core.Rejected,'local owner console'): review()

    def test_owner_review_preserves_failure_and_records_fresh_authorization(self):
        from supervisor.development import review
        failed_id=str(uuid.uuid4()); self.service.unresolved=[failed_id]
        self.service.ledger.append('fixture-unclassified',request_id=failed_id)
        self.service.halt('qualification injected containment failure')
        original=(self.home/'HALTED.json').read_bytes(); prefix=self.service.ledger.path.read_bytes()
        seal=dict(passed=True,evidence='synthetic reviewed qualification'); core.atomic(self.home/'qualification.json',seal)
        (self.home/'STOP').touch()
        phrase='REVIEW FIXTURE HOLD '+core.digest(seal)[:16]
        with patch.object(P,'HOME',self.home),patch('supervisor.environment.ordinary_user'),patch('supervisor.development.verify_seal'),\
             patch('supervisor.development.sys.stdin.isatty',return_value=True),patch('builtins.input',return_value=phrase),patch('builtins.print'):
            review()
        self.assertTrue(self.service.ledger.path.read_bytes().startswith(prefix))
        self.assertEqual(next((self.home/'owner-reviews').glob('*/HALTED.json')).read_bytes(),original)
        self.assertTrue((self.home/'STOP').exists())
        restarted=FixtureService(self.home,qualification=True)
        self.assertFalse(restarted.halted); self.assertEqual(restarted.unresolved,[])


class Candidate(unittest.TestCase):
    def setUp(self):
        P.modules()
        self.temp=tempfile.TemporaryDirectory(dir=core.ROOT/'out'); self.root=Path(self.temp.name)
        self.ident=str(uuid.uuid4()); self.params=dict(arch='x64',case='normal')
        src=self.root/'sources'; b=self.root/'build'; src.mkdir(); b.mkdir()
        for name in ('evidence_smoke.c','evidence_fixture.h','evidence_dummy.c'): (src/name).write_bytes(b'fixture source')
        pe=bytearray(512); pe[:2]=b'MZ'; struct.pack_into('<I',pe,60,128); pe[128:132]=b'PE\0\0'
        struct.pack_into('<H',pe,132,0x8664); struct.pack_into('<H',pe,128+24+68,2)
        (b/'smoke.exe').write_bytes(pe)
        for name in ('smoke.obj','disposable.dll','dummy.obj'): (b/name).write_bytes(b'output')
        ins,outs=P.recipe_files('collector-smoke',self.params,self.root)
        tool=self.root/'compiler.exe'; tool.write_bytes(b'only hashed, never launched')
        record=dict(recipe='desktop-fixture-v1',family='collector-smoke',parameters=self.params,arch='x64',fp='/fp:strict',
                    inputs=P.identities(ins),outputs=P.identities(outs),toolchain=P.identities([tool]))
        core.atomic(b/'build-record.json',record)
        self.manifest=dict(version=1,id=self.ident,family='collector-smoke',parameters=self.params,
                           files=P.identities(P.expected_files('collector-smoke',self.params,self.root)),build_record=str(b/'build-record.json'))
        self.path=self.root/'candidate.json'; core.atomic(self.path,self.manifest)
        self.request=dict(candidate_id=self.ident,candidate_sha256=core.sha(self.path),family='collector-smoke',parameters=self.params,profile='fast-development')
        self.paths=patch('supervisor.fixture_profiles.candidate_path',return_value=self.path); self.paths.start()

    def tearDown(self): self.paths.stop(); self.temp.cleanup()

    def rewrite(self):
        core.atomic(self.path,self.manifest); self.request['candidate_sha256']=core.sha(self.path)

    def test_exact_inventory_and_pe_identity(self): self.assertEqual(P.validate_candidate(self.request),self.manifest)

    def test_arbitrary_executable_field_rejected(self):
        self.manifest['executable']='C:/Windows/System32/cmd.exe'; self.rewrite()
        with self.assertRaises(core.Rejected): P.validate_candidate(self.request)

    def test_extra_file_inventory_rejected(self):
        self.manifest['files']['C:/arbitrary.exe']='a'*64; self.rewrite()
        with self.assertRaisesRegex(core.Rejected,'recipe inventory'): P.validate_candidate(self.request)

    def test_binary_or_source_changes_fail_integrity(self):
        (self.root/'build/smoke.exe').write_bytes(b'changed')
        with self.assertRaises(core.IntegrityFailure): P.validate_candidate(self.request)

    def test_missing_recipe_input_rejected(self):
        self.manifest['files'].pop(str(self.root/'sources/evidence_smoke.c')); self.rewrite()
        with self.assertRaisesRegex(core.Rejected,'recipe inventory'): P.validate_candidate(self.request)

    def test_wrong_architecture_rejected_even_with_updated_digest(self):
        exe=self.root/'build/smoke.exe'; data=bytearray(exe.read_bytes()); struct.pack_into('<H',data,132,0x14c); exe.write_bytes(data)
        self.manifest['files'][str(exe)]=core.sha(exe); self.rewrite()
        with self.assertRaisesRegex(core.Rejected,'PE architecture'): P.validate_candidate(self.request)

    def test_duplicate_manifest_keys_rejected(self):
        raw=self.path.read_text(); self.path.write_text(raw.replace('"version": 1','"version": 1, "version": 1'))
        self.request['candidate_sha256']=core.sha(self.path)
        with self.assertRaisesRegex(core.Rejected,'duplicate candidate'): P.validate_candidate(self.request)


class Gate(unittest.TestCase):
    def test_qualification_flag_cannot_bypass_graphics_gate(self):
        P.modules()
        with tempfile.TemporaryDirectory(dir=core.ROOT/'out') as d:
            root=Path(d); (root/'evidence').mkdir()
            with patch('supervisor.environment.ordinary_user'), patch('evidence_capture.Collector.snapshot',return_value={}),\
                 patch('evidence_check.environment',side_effect=__import__('evidence_check').Incomplete('not physical')):
                with self.assertRaises(DesktopUnavailable): physical_gate(root,dict(family='renderer-group'),qualification=True)

    def failure(self,error):
        from supervisor.development import run_fixture
        with tempfile.TemporaryDirectory(dir=core.ROOT/'out') as d:
            root=Path(d); out=root/'result'; out.mkdir()
            request=dict(family='renderer-group',parameters=dict(group=7,arch='x64',variant='translated'),timeout_seconds=1)
            candidate=dict(id=str(uuid.uuid4()),files={},build_record=str(root/'build.json'))
            item=dict(name='fvf-x64-translated',arch='x64',variant='translated',group=7,exe=root/'fixture.exe')
            with patch('supervisor.fixture_profiles.candidate_path',return_value=root/'candidate.json'),\
                 patch('supervisor.fixture_profiles.plan',return_value=[item]),patch('supervisor.development.physical_gate'),\
                 patch('supervisor.fixture_collector.capture',side_effect=error):
                return run_fixture(request,candidate,out,lambda:False,lambda:None,qualification=True)

    def test_environment_loss_is_distinct_from_parser_error_and_no_device_is_inferred(self):
        _,A,_=P.modules()
        for error,category in [(A.Incomplete('input desktop unavailable'),'environment-unavailable'),(ValueError('parser defect'),'collector-implementation-error')]:
            with self.subTest(category=category):
                result=self.failure(error)
                self.assertEqual(result['classification'],category)
                self.assertIsNone(result['graphics_devices_created']); self.assertEqual(result['process_count'],0)

    def test_unresolved_mapped_module_identity_closes_execution(self):
        _,_,original=P.modules()
        with self.assertRaisesRegex(core.IntegrityFailure,'loaded-module integrity'):
            self.failure(original.IdentityIncomplete('unresolved mapped image'))


if __name__=='__main__':
    P.modules()
    unittest.main()
