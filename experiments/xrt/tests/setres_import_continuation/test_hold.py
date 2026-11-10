import copy
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
import identity
import owner


class ResolvedHold(unittest.TestCase):
    def test_exact_diagnosed_hold_is_read_only(self):
        before=core.sha(core.HOME/'ledger.jsonl')
        ledger=owner.execution_gate()
        self.assertEqual(before,core.sha(ledger.path))
        self.assertEqual(ledger.rows[-1]['sequence'],80)

    def test_other_hold_rejected(self):
        actual=core.Ledger(core.HOME/'ledger.jsonl');rows=copy.deepcopy(actual.rows)
        rows[-1]['hold']['request_id']='unrelated'
        with patch.object(core,'Ledger',return_value=SimpleNamespace(rows=rows,path=actual.path)):
            with self.assertRaises(core.Rejected):owner.execution_gate()


class ImportAudit(unittest.TestCase):
    def events(self):
        return [dict(kind='gui_attach_thread_input_call',**{'from':100,'to':100,'attach':1,'esp':0x1000,'return':0x11104a4e}),
                dict(kind='gui_attach_thread_input_return',**{'from':100,'to':100,'attach':1,'result':0,'last_error':87,'esp_before':0x1000,'esp_after':0x1010,'actual_return':0x11104a4e})]

    def test_native_failure_is_the_expected_result(self):owner.audit_attach(self.events())

    def test_original_branch_may_omit_the_call(self):self.assertEqual(owner.audit_attach([]),0)

    def test_fabricated_success_rejected(self):
        e=self.events();e[1]['result']=1
        with self.assertRaises(core.Rejected):owner.audit_attach(e)

    def test_error_loss_rejected(self):
        e=self.events();e[1]['last_error']=0
        with self.assertRaises(core.Rejected):owner.audit_attach(e)

    def test_cross_thread_rejected(self):
        e=self.events();e[0]['to']=101
        with self.assertRaises(core.Rejected):owner.audit_attach(e)

    def test_incorrect_stdcall_pop_rejected(self):
        e=self.events();e[1]['esp_after']-=4
        with self.assertRaises(core.Rejected):owner.audit_attach(e)

    def test_missing_return_rejected(self):
        with self.assertRaises(core.Rejected):owner.audit_attach(self.events()[:1])

    def test_any_ledger_change_rejected(self):
        sha=core.sha
        def changed(path):return '0'*64 if pathlib.Path(path)==core.HOME/'ledger.jsonl' else sha(path)
        with patch.object(core,'sha',side_effect=changed):
            with self.assertRaises(core.Rejected):owner.execution_gate()

    def test_resolution_evidence_change_rejected(self):
        target=next(iter(read(O/'resolved-hold.json')['evidence']));sha=core.sha
        def changed(path):return '0'*64 if str(path)==target else sha(path)
        with patch.object(core,'sha',side_effect=changed):
            with self.assertRaises(core.Rejected):owner.execution_gate()

    def test_consumed_executable_still_rejected(self):
        with patch.object(identity,'SHA','d6071f6563300dc4ae04b77d35943625f5b4274bb58db4a04ed6aee22b58d158'):
            with self.assertRaises(core.Rejected):identity.consumed()

    def test_stop_remains_effective(self):
        exists=pathlib.Path.exists
        def stopped(path):return True if path==O/'STOP' else exists(path)
        with patch.object(pathlib.Path,'exists',stopped):
            with self.assertRaises(core.Rejected):owner.execution_gate()


if __name__=='__main__':unittest.main(verbosity=2)
