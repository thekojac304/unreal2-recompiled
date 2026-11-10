import sys,unittest,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from observer import capture_endpoint
from common import GUEST,core
class Context:
    def __init__(self):self.registers=dict(rip=0x1020,rdi=0x2000,rbx=GUEST)
    def get(self,k):return self.registers[k]
    def snapshot(self):return self.registers.copy()
class Capture:
    base=0x1000
    def __init__(self):self.rows=[];self.stop_requested=False;self.raw=bytearray(416);struct.pack_into('<I',self.raw,64,GUEST);self.code=bytes.fromhex('895f44')
    def mem(self,p,n):return self.code[:n] if p==0x1020 else bytes(self.raw[:n])
    def log(self,kind,**fields):self.rows.append(dict(kind=kind,**fields))
class Tests(unittest.TestCase):
    def setUp(self):self.capture=Capture();self.context=Context();self.plan=dict(stop_rva=0x20,stop_bytes='895f44',stop_registers=dict(cpu='rdi'))
    def test_stop(self):
        raw=capture_endpoint(self.capture,self.context,self.plan);self.assertEqual(len(raw),416);self.assertTrue(self.capture.stop_requested)
    def test_rejections_preserve_raw(self):
        for field in ('rip','rbx','rv','bytes','short'):
            with self.subTest(field=field):
                self.setUp()
                if field in ('rip','rbx'):self.context.registers[field]^=1
                elif field=='rv':self.capture.raw[64]^=1
                elif field=='bytes':self.capture.code=b'\x90'*3
                else:self.capture.raw=self.capture.raw[:100]
                with self.assertRaises(core.Rejected):capture_endpoint(self.capture,self.context,self.plan)
                self.assertFalse(self.capture.stop_requested);self.assertEqual(self.capture.rows[0]['kind'],'resource_init_endpoint_raw')
if __name__=='__main__':unittest.main()
