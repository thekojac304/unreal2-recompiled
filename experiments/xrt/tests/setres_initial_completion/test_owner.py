import copy
import pathlib
import sys
import unittest
import uuid
from unittest.mock import patch
from common import *
import owner
import identity as candidate_identity


class OwnerGates(unittest.TestCase):
    def test_noninteractive_cannot_launch(self):
        with patch.object(sys.stdin,'isatty',return_value=False):
            with self.assertRaises(core.Rejected):owner.run_once()
    def test_scoped_hold_readonly_and_consumption_checked(self):
        path=core.HOME/'ledger.jsonl';before=core.sha(path)
        with patch.object(candidate_identity,'consumed',return_value={'unconsumed':True}) as consumed:
            ledger=owner.execution_gate();self.assertEqual(ledger.rows[-1]['sequence'],84);consumed.assert_called_once()
        self.assertEqual(core.sha(path),before)
    def test_changed_ledger_and_unrelated_hold_reject(self):
        real=owner.read;baseline=read(O/'resolved-hold.json')
        for key in ('ledger','hold'):
            changed=copy.deepcopy(baseline)
            if key=='ledger':changed['ledger_sha256']='0'*64
            else:changed['transition']['hold']['request_id']=str(uuid.uuid4())
            with patch.object(owner,'read',side_effect=lambda p:changed if p==O/'resolved-hold.json' else real(p)):
                with self.assertRaises(core.Rejected):owner.execution_gate()
    def test_stop_file_rejects_without_consumption(self):
        home=O/('owner-stop-fixture-'+str(uuid.uuid4()));home.mkdir();(home/'STOP').write_text('fixture only')
        with patch.object(core,'HOME',home),patch.object(candidate_identity,'consumed') as consumed:
            with self.assertRaises(core.Rejected):owner.execution_gate()
            consumed.assert_not_called()
    def test_separate_stop_authorization_precedes_launch(self):
        source=(H/'owner.py').read_text()
        self.assertLess(source.index("input().strip()==STOP_PHRASE"),source.index("input().strip()==PHRASE"))
        self.assertLess(source.index("input().strip()==PHRASE"),source.index('ledger.claim('))
        self.assertLess(source.index('ledger.claim('),source.index('cap.run('))
        self.assertIn('endpoint_authorization=dict(phrase=STOP_PHRASE',source)


if __name__=='__main__':unittest.main()
