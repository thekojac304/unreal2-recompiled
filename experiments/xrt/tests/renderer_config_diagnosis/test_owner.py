import sys
import unittest
from unittest.mock import patch
from common import *
import owner
import identity as candidate_identity


class Owner(unittest.TestCase):
    def test_unknown_configuration_is_diagnostic_and_never_success(self):
        self.assertEqual(owner.classify_failure(core.Rejected('renderer configuration diagnostic stop: 0x40d0 expected 32, observed 64')),'diagnostic-configuration-stop')
        self.assertEqual(owner.classify_failure(core.IntegrityFailure('hash mismatch')),'safety-integrity-failure')
        self.assertEqual(owner.classify_failure(core.Rejected('x87 change')),'unclassified-correctness-failure')
    def test_noninteractive_cannot_launch(self):
        with patch.object(sys.stdin,'isatty',return_value=False):
            with self.assertRaises(core.Rejected):owner.run_once()
    def test_bound_hold_is_readonly(self):
        path=core.HOME/'ledger.jsonl';before=core.sha(path)
        with patch.object(candidate_identity,'consumed',return_value={'unconsumed':True}):
            ledger=owner.execution_gate();self.assertEqual(ledger.rows[-1]['sequence'],88)
        self.assertEqual(core.sha(path),before)


if __name__=='__main__':unittest.main()
