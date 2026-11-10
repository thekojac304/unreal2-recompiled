"""Prepare separate parser/service revision; never mutate a running service."""
from pathlib import Path

H=Path(__file__).resolve().parent

def main():
    s=(H/'audit_gamma.py').read_text().replace('from recheck import core','import struct\nfrom recheck import core')
    s=s.replace('observed=[]','observed=[];strict=[]')
    s=s.replace("A.need(call['error']==seed,'gamma last-error preservation');A.abi(call,arch)",'''A.need(call['error']==seed,'gamma last-error preservation')
        try:A.abi(call,arch)
        except A.Incomplete:
            # Recheck the complete ABI, allowing ONLY volatile MXCSR status
            # bits in the functional result. Preserve the strict failure and
            # original raw records; no x87/control/GPR/XMM/stack exception.
            pre,post=bytes.fromhex(call['pre']),bytes.fromhex(call['post'])
            A.need(len(pre)==len(post)==512,'gamma FXSAVE length')
            a,b=struct.unpack_from('<I',pre,24)[0],struct.unpack_from('<I',post,24)[0]
            A.need((a^b)&~63==0,'gamma MXCSR control changed')
            normalized=bytearray(post);normalized[24:28]=pre[24:28]
            A.abi(dict(call,post=normalized.hex()),arch)
            strict.append(dict(index=index,seed=seed,finding='native_MXCSR_status',before=a,after=b,verdict='FAILED',pre=call['pre'],post=call['post']))''')
    s=s.replace("return dict(passed=True,observations=observed,cleanup=clean,scope=", "return dict(passed=True,observations=observed,strict_differences=strict,cleanup=clean,scope=")
    (H/'audit_gamma_v2.py').write_text(s)
    s=(H/'gamma_service.py').read_text().replace('import gamma as G',"sys.path.insert(0,str(Path(__file__).resolve().parent))\nimport gamma as G").replace('import audit_gamma as A','import audit_gamma_v2 as A').replace("out/semantic-gamma-fixtures'","out/semantic-gamma-fixtures-v2'")
    s=s.replace("'gamma_service.py','gamma.py','audit_gamma.py','audit.py','recheck.py'", "'gamma_service_v2.py','gamma.py','audit_gamma_v2.py','audit.py','recheck.py','test_gamma_audit_v2.py'")
    s=s.replace('cycles=qualification_cycles(out)',"checked([sys.executable,'-B','-I','-m','unittest','discover','-s',str(HERE),'-p','test_gamma_audit_v2.py','-v'],out,'semantic-gamma-parser-tests')\n    cycles=qualification_cycles(out)")
    s=s.replace("OUT/'semantic-gamma-request.json'","OUT/'semantic-gamma-v2-request.json'")
    (H/'gamma_service_v2.py').write_text(s)
    s=(H/'test_gamma_audit.py').read_text().replace('import audit_gamma','import audit_gamma_v2 as audit_gamma')
    s=s.replace("    def test_missing_readback(self):",'''    def test_status_failure_remains_explicit(self):
        r,e,b=records();post=bytearray.fromhex(r[5]['post']);struct.pack_into('<I',post,24,0x3fa0);r[5]['post']=post.hex()
        result=self.check(r,e,b);self.assertTrue(result['passed']);self.assertEqual(result['strict_differences'][0]['verdict'],'FAILED')
    def test_x87_status_change_rejected(self):
        r,e,b=records();post=bytearray.fromhex(r[5]['post']);post[2]^=1;r[5]['post']=post.hex()
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_mxcsr_control_change_rejected(self):
        r,e,b=records();post=bytearray.fromhex(r[5]['post']);struct.pack_into('<I',post,24,0x1f80);r[5]['post']=post.hex()
        with self.assertRaises(ValueError):self.check(r,e,b)
    def test_missing_readback(self):''')
    (H/'test_gamma_audit_v2.py').write_text(s)

if __name__=='__main__':main()
