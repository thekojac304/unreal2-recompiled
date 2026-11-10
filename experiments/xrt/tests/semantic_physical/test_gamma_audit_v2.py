"""Parser rejection tests only. Synthetic records are never GPU qualification."""
import copy
import struct
import unittest
import audit_gamma_v2 as audit_gamma
from audit import expected_cpu


def records(translated=False):
    ramp=b''.join((i*257).to_bytes(2,'little') for _ in range(3) for i in range(256))
    fx=bytearray(512);struct.pack_into('<H',fx,0,0x27f);struct.pack_into('<I',fx,24,0x3f80)
    rows=[dict(kind='semantic-create'),dict(kind='semantic-ownership',add=2,balance=1,parent_hr=0,same_parent=True,parent_release=2,creation_hr=0,same_window=True,flags=66),dict(kind='semantic-caps'),dict(kind='backend-adapter'),dict(kind='gamma-saved',bytes=ramp.hex())]
    events=[]
    for i in range(16):
        index,j=divmod(i,4);kind,flag=divmod(index,2);seed=[0,18,0x13572468,0xffffffff][j]
        call=dict(kind='semantic-call',index=index,slot=18,a=flag,input_kind=kind,seed=seed,error=seed,hr=None,rejected=False,input=ramp.hex(),stack_delta=0,
            regs=[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef],
            xmm=(struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10).hex(),pre=fx.hex(),post=fx.hex())
        call['cpu']=call['expected_cpu']=expected_cpu(call)
        rows.extend([call,dict(kind='semantic-readback',hr=None,bytes=ramp.hex())])
        if translated:events.extend(dict(event='d3d8_checkpoint',payload=dict(phase=p,slot=18,error=seed)) for p in range(4))
    rows.extend([dict(kind='gamma-restored',bytes=ramp.hex()),dict(kind='semantic-cleanup',device_release=0,parent_release=0,window_valid=False,d3d8_loaded=False,d3d9_loaded=False,destroyed=True,unregistered=True,free_d3d8=True,free_d3d9=True,guest_freed=True),dict(kind='semantic-summary',calls=16,translated=translated,group=8)])
    return rows,events,ramp


class GammaParser(unittest.TestCase):
    def check(self,rows,events,ramp,translated=False):return audit_gamma.numerical(rows,events,'x64',translated,ramp)
    def test_complete_protocol(self):
        for translated in (False,True):
            r,e,b=records(translated);self.assertTrue(self.check(r,e,b,translated)['passed'])
    def test_status_failure_remains_explicit(self):
        r,e,b=records();post=bytearray.fromhex(r[5]['post']);struct.pack_into('<I',post,24,0x3fa0);r[5]['post']=post.hex()
        result=self.check(r,e,b);self.assertTrue(result['passed']);self.assertEqual(result['strict_differences'][0]['verdict'],'FAILED')
    def test_x87_status_change_rejected(self):
        r,e,b=records();post=bytearray.fromhex(r[5]['post']);post[2]^=1;r[5]['post']=post.hex()
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_mxcsr_control_change_rejected(self):
        r,e,b=records();post=bytearray.fromhex(r[5]['post']);struct.pack_into('<I',post,24,0x1f80);r[5]['post']=post.hex()
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_missing_readback(self):
        r,e,b=records();del r[6]
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_void_hresult_cannot_be_invented(self):
        r,e,b=records();r[5]['hr']=0
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_device_restore_is_exact(self):
        r,e,b=records();r[-3]['bytes']='00'*1536
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_raw_readback_is_checked(self):
        r,e,b=records();r[6]['bytes']='00'*1536
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_cpu_eax_corruption(self):
        r,e,b=records(True);r[5]['cpu']='ffffffff'+r[5]['cpu'][8:]
        with self.assertRaises(ValueError):self.check(r,e,b,True)
    def test_missing_native_checkpoint(self):
        r,e,b=records(True);del e[2]
        with self.assertRaises(ValueError):self.check(r,e,b,True)
    def test_control_state_corruption(self):
        r,e,b=records();r[5]['post']='7f06'+r[5]['post'][4:]
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_remaining_com_reference(self):
        r,e,b=records();r[-2]['device_release']=1
        with self.assertRaises(ValueError):self.check(r,e,b)


if __name__=='__main__':unittest.main()
