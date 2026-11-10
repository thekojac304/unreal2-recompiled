"""Call-aware evidence/return negatives; no game execution."""
import copy
import struct
import unittest
from test_observer import Target,Context
from common import *
import evidence


class Evidence(unittest.TestCase):
    def target(self,frame=None,site=0x11104bf5):
        t=Target();c=t.cap;c.setres_entry=None
        t.cs['registers'].update(ecx=0x10000,esp=0x58000);t.cs['pc']=site
        t.put(c.sym('xrt_g'),struct.pack('<Q',c.guest_base))
        t.u32(c.guest_base+0x10000+0x4698,0)
        t.put(c.guest_base+0x58000,struct.pack('<6I',*(frame or [GUEST,0x18000,1540,945,0,32])))
        c.breakpoints[0x5555]='setres_entry'
        return t
    def test_initial_captured_and_classified(self):
        t=self.target();t.cap.hit('setres_entry',Context(rcx=t.cap.cpu,rip=0x5555),1)
        self.assertEqual(t.cap.setres_entry['classification'],'initial')
        self.assertEqual(len(t.cap.setres_entry['cpu_raw']),832)
        self.assertFalse(getattr(t.cap,'stop_requested',False))
    def test_lock_separate_and_rejected_before_device(self):
        t=self.target([0x696d2cd,0x18000,1540,945,0,32],0x696d2ca)
        with self.assertRaises(core.Rejected):t.cap.hit('setres_entry',Context(rcx=t.cap.cpu,rip=0x5555),1)
        row=next(r for r in t.cap.rows if r['kind']=='setres_entry_raw')
        self.assertEqual(row['classification'],'lock-recovery')
    def test_each_argument_failure_keeps_exact_raw_frame(self):
        for index,value in [(0,0x1234),(1,0x18004),(2,800),(3,600),(4,1),(5,16)]:
            with self.subTest(index=index):
                frame=[GUEST,0x18000,1540,945,0,32];frame[index]=value;t=self.target(frame)
                with self.assertRaises(core.Rejected):t.cap.hit('setres_entry',Context(rcx=t.cap.cpu,rip=0x5555),1)
                row=next(r for r in t.cap.rows if r['kind']=='setres_entry_raw')
                self.assertEqual(row['frame'],frame);self.assertEqual(bytes.fromhex(row['frame_raw']),struct.pack('<6I',*frame))
    def test_evidence_write_failure_rejects_before_state_acceptance(self):
        t=self.target();c=t.cap;log=c.log
        def broken(kind,**v):
            if kind=='setres_entry_raw':raise OSError('fixture evidence disk error')
            return log(kind,**v)
        c.log=broken
        with self.assertRaises(OSError):c.hit('setres_entry',Context(rcx=c.cpu,rip=0x5555),1)
        self.assertIsNone(c.setres_entry)
    def test_entry_source_read_failure_keeps_cpu_and_frame(self):
        t=self.target();c=t.cap;mem=c.mem
        def broken(p,n):
            if n==0x4700:raise OSError('fixture unreadable renderer')
            return mem(p,n)
        c.mem=broken
        with self.assertRaises(OSError):c.hit('setres_entry',Context(rcx=c.cpu,rip=0x5555),1)
        self.assertTrue(any(r['kind']=='setres_entry_raw' for r in c.rows))
    def test_each_return_pair_failure_rejected(self):
        for bad in ('eax','esp','rv','ebx','thread','caller','renderer'):
            with self.subTest(bad=bad):
                t=Target();c=t.cap;t.cs.update(rv=GUEST,pc=0x696f4e9);t.cs['registers'].update(esp=0x10018,eax=1)
                tid=1
                if bad=='eax':t.cs['registers']['eax']=0
                if bad=='esp':t.cs['registers']['esp']+=4
                if bad=='rv':t.cs['rv']=0x696d2cd
                if bad=='ebx':t.cs['registers']['ebx']=2
                if bad=='thread':tid=2
                if bad=='caller':c.setres_entry['classification']='lock-recovery'
                if bad=='renderer':t.u32(c.guest_base+0x18000+0x5c,0x10004)
                with self.assertRaises(core.Rejected):evidence.completed(c,Context(rip=c.base+RVA,rdi=c.cpu,rbx=GUEST),tid,read(O/'stop-mapping.json'))
                self.assertTrue(any(r['kind']=='initial_setres_return_raw' for r in c.rows))


class NativeFlow(unittest.TestCase):
    def states(self,raw):
        import capstone
        from nativeflow import propagate
        m=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);m.detail=True
        ins=list(m.disasm(bytes.fromhex(raw),0x1000));return ins,propagate(ins,m)
    def test_spilled_cpu_and_return_constants(self):
        ins,s=self.states('48894d10488b7d10bbf84b1011448d6bfd458bc5e800000000895f44c3')
        call=next(i for i in ins if i.mnemonic=='call')
        self.assertEqual(s[call.address]['rdi'],'cpu');self.assertEqual(s[call.address]['r8'],0x11104bf5)
        self.assertEqual(s[call.address]['rbx'],GUEST)
    def test_conflicting_branch_join_discards_constant(self):
        ins,s=self.states('85c07407bb01000000eb05bb0200000089d8c3')
        self.assertNotIn('rbx',s[ins[-2].address])
    def test_call_invalidates_volatile(self):
        ins,s=self.states('b901000000bb02000000e80000000089d8c3')
        self.assertNotIn('rcx',s[ins[-2].address]);self.assertEqual(s[ins[-2].address]['rbx'],2)


if __name__=='__main__':unittest.main()
