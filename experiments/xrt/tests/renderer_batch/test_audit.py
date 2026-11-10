"""Negative tests of evidence parsing. Synthetic rows are NOT GPU evidence."""
import copy,unittest
import desktop_batch as D

class EvidenceAudit(unittest.TestCase):
    def rows(self,group=1):
        pre=bytearray(512);pre[:2]=b'\x7f\x02';state=[]
        for c in D.P.read(D.P.O/'cases.json')['cases']:
            if c['group']!=group:continue
            for seed in [18,0,0x13572468,0xffffffff]:
                for _ in range(2):
                    state.append(dict(c,kind='call',seed=seed,error=seed,hr=None if group==8 else 0,stack_delta=0,fpu_preserved=True,pre=pre.hex(),post=pre.hex()))
                    state.append(dict(kind='readback',slot=c['slot'],hr=0,equal=True,value=1,extra=0))
        if group==8:state.append(dict(kind='gamma-restored',equal=True))
        state.append(dict(kind='summary',passed=True,graphics=True))
        return state
    def rejected(self,rows,group=1):
        with self.assertRaises((AssertionError,KeyError,ValueError)):D.audit(rows,group)
    def test_parser_schema_only(self):self.assertEqual(len(D.audit(self.rows(),1)),16)
    def test_missing_call(self):r=self.rows();r.pop(0);self.rejected(r)
    def test_duplicate_case(self):r=self.rows();r[16]=copy.deepcopy(r[0]);self.rejected(r)
    def test_hresult_failure(self):r=self.rows();r[0]['hr']=0x8876086c;self.rejected(r)
    def test_stack_failure(self):r=self.rows();r[0]['stack_delta']=4;self.rejected(r)
    def test_readback_failure(self):r=self.rows();r[1]['equal']=False;self.rejected(r)
    def test_forged_fpu_pass(self):r=self.rows();p=bytearray.fromhex(r[0]['post']);p[2]^=0x20;r[0]['post']=p.hex();self.rejected(r)
    def test_gamma_is_void(self):r=self.rows(8);r[0]['hr']=0;self.rejected(r,8)
    def test_gamma_restore_required(self):r=self.rows(8);r.pop(-2);self.rejected(r,8)
    def test_wrong_readback_slot(self):r=self.rows();r[1]['slot']=63;self.rejected(r)
if __name__=='__main__':unittest.main()
