"""No display/gamma API calls: restoration and catalog fault injection only."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prerequisite_service_tests',HERE/'service.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class RestoreTests(unittest.TestCase):
    def run_restore(self,write=True,read=True,equal=True):
        original=bytes(range(256))*6
        class Fake:
            closed=[]
            def GetDeviceGammaRamp(self,dc,data):
                data.raw=original if equal else bytes(1536)
                return read
            def SetDeviceGammaRamp(self,dc,data):
                self.restoring=data.raw[:1536]
                return write
            def DeleteDC(self,dc):self.closed.append(dc)
        with tempfile.TemporaryDirectory(dir=S.P.O) as d:
            guard=S.DesktopGamma(Path(d));guard.g=Fake();guard.dcs=[('display',1,original)]
            if write and read and equal:guard.__exit__(RuntimeError,RuntimeError('child crash'),None)
            else:
                with self.assertRaises(S.core.IntegrityFailure):guard.__exit__(None,None,None)
            self.assertEqual(guard.g.restoring,original)
            self.assertEqual(guard.g.closed,[1])
            result=S.core.read(Path(d)/'desktop-gamma-restored.json')
            self.assertEqual(result['passed'],write and read and equal)
    def test_restore_after_child_error(self):self.run_restore()
    def test_failed_write_is_not_accepted(self):self.run_restore(write=False)
    def test_failed_read_is_not_accepted(self):self.run_restore(read=False)
    def test_wrong_restored_bytes_are_not_accepted(self):self.run_restore(equal=False)
    def test_fixed_catalog_rejects_values(self):
        with self.assertRaises(S.core.Rejected):S.parameters(S.FAMILY,{'command':'anything'},'fast-development')
    def test_formal_profile_is_not_accepted(self):
        with self.assertRaises(S.core.Rejected):S.parameters(S.FAMILY,{},'formal-acceptance')
    def test_native_plan_is_fixed(self):
        plan=S.plan(S.FAMILY,{},Path('fixed'))
        self.assertEqual([(r['arch'],r['variant']) for r in plan],[('x86','native'),('x64','native'),('x64','translated')])
        self.assertTrue(all(r['exe'].name=='fixture.exe' and r['group']==8 for r in plan))


if __name__=='__main__':unittest.main()
