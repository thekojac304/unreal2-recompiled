import copy
import struct
import sys
import unittest
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import observer

class Context:
    def __init__(self,**values):self.values=values
    def get(self,name):return self.values.get(name,0)
    def snapshot(self):
        names=('rax','rcx','rdx','r8','r9','rsp','rbx','rbp','rsi','rdi','r12','r13','r14','r15')
        return dict(registers={r:self.get(r) for r in names},mxcsr=self.values.get('mxcsr',0x1f80),fxsave=self.values.get('fxsave',bytes(512).hex()))

class Target:
    def __init__(self):
        self.out=O/('semantic-controller-'+str(uuid.uuid4()));self.out.mkdir()
        self.cap,_=observer.construct(self.out,read(O/'stop-mapping.json'),lambda _:None,[])
        self.mem={};c=self.cap;c.cpu=0x1000;c.guest_base=0x100000000;c.base=0x140000000
        c.mem=lambda p,n:bytes(self.mem.get(p+i,0) for i in range(n))
        self.u64(c.sym('xrt_g'),c.guest_base)
        self.cs=dict(registers={r:0 for r in ('eax','ecx','edx','ebx','esp','ebp','esi','edi')},rv=0,pc=0x696f336,fs_base=0x70000,flags={},x87={})
        self.cs['registers']['esp']=0x3000;c.cpu_state=lambda p:copy.deepcopy(self.cs)
        c.object_state=lambda:dict(host=0x800000,native_vtable=0x802000,guest=0x4000,guest_refs=1,parent_state=dict(host=0x801000))
        c.hwnds=lambda:[];c.snapshot_events=lambda:None;c.threads={1:(1,0xa00000)}
        self.put(c.guest_base+0x3000,struct.pack('<4I',0x696f33c,0x4000,14,32));self.u64(0x800000,0x802000);self.u64(0x802000+50*8,0x900000)
        self.u64(0xb00000,0xc00000);self.u64(0xd00000,0xd00100);self.sync()
    def put(self,p,data):self.mem.update({p+i:b for i,b in enumerate(data)})
    def u32(self,p,v):self.put(p,struct.pack('<I',v))
    def u64(self,p,v):self.put(p,struct.pack('<Q',v))
    def sync(self):
        raw=bytearray(416)
        for i,r in enumerate(('eax','ecx','edx','ebx','esp','ebp','esi','edi')):struct.pack_into('<I',raw,4*i,self.cs['registers'][r])
        struct.pack_into('<3I',raw,60,self.cs['fs_base'],self.cs['rv'],self.cs['pc']);self.put(0x1000,raw)
    def checkpoint(self,phase,result=0,error=18):
        for i,v in enumerate((0,result,error)):self.u32(0xb00000+40+i*8,v)
        return self.cap.hit('semantic_checkpoint',Context(rcx=0x1000,rdx=phase,r8=50,rsp=0xb00000),1)
    def native(self,**overrides):
        values=dict(rcx=0x800000,rdx=14,r8=32,rsp=0xd00000);values.update(overrides)
        self.cap.hit('semantic_native_entry',Context(**values),1)
    def returned(self,result=0,error=87,**overrides):
        self.u32(0xa00000+0x68,error);values=dict(rax=result,rsp=0xd00008);values.update(overrides)
        self.cap.hit('semantic_native_return',Context(**values),1)
    def complete(self,result=0,error=87,bad_esp=False):
        self.checkpoint(2,result,error);self.cs['registers']['esp']+=12 if bad_esp else 16
        self.cs['registers']['eax']=result;self.cs['rv']=0x696f33c;self.sync();self.u32(self.cap.guest_base+0x70000+0x34,error)
        self.checkpoint(3,result,error)
    def through_native(self):self.checkpoint(0);self.checkpoint(1);self.native()

class Checks(unittest.TestCase):
    def test_success_and_native_failures_are_transferred(self):
        for result in (0,0x80004005,0x8876086c):
            t=Target();t.through_native();t.returned(result);t.complete(result)
            self.assertEqual(t.cap.operations[0]['result'],result)
            self.assertFalse(t.cap.entries)
    def test_noncanonical_bool_is_not_rewritten(self):
        t=Target();t.through_native();t.returned();t.complete()
        args=next(r for r in t.cap.rows if r['kind']=='semantic_native_arguments')['arguments']
        self.assertEqual(args[2],32)
    def test_wrong_native_scalar_stops_with_evidence(self):
        t=Target();t.checkpoint(0);t.checkpoint(1)
        with self.assertRaisesRegex(core.Rejected,'native arguments'):t.native(r8=1)
        self.assertTrue(any(r['kind']=='semantic_native_arguments' and r['discrepancies']==['argument_2'] for r in t.cap.rows))
    def test_stack_corruption_is_fatal(self):
        t=Target();t.through_native();t.returned()
        with self.assertRaisesRegex(core.Rejected,'stack_cleanup'):t.complete(bad_esp=True)
    def test_native_nonvolatile_corruption_is_fatal(self):
        t=Target();t.through_native()
        with self.assertRaisesRegex(core.Rejected,'native_nonvolatile_rbx'):t.returned(rbx=1)
    def test_native_xmm_corruption_is_fatal(self):
        t=Target();t.through_native();fx=bytearray(512);fx[256]=1
        with self.assertRaisesRegex(core.Rejected,'XMM6_15'):t.returned(fxsave=fx.hex())
    def test_native_status_is_separate(self):
        t=Target();t.through_native();fx=bytearray(512);fx[24]=0x20
        t.returned(mxcsr=0x1fa0,fxsave=fx.hex());t.complete()
        self.assertTrue(any(r['kind']=='strict_differential' for r in t.cap.rows))
    def test_error_transfer_mismatch_is_fatal(self):
        t=Target();t.through_native();t.returned(error=87)
        with self.assertRaisesRegex(core.Rejected,'last-error differs'):t.checkpoint(2,error=18)
    def test_callback_supported_and_suspended_cpu_checked(self):
        t=Target();t.through_native();t.u64(0xe00000,0xe00100)
        t.cap.hit('semantic_callback',Context(rsp=0xe00000),1)
        t.cap.hit('semantic_callback_return',Context(rsp=0xe00008),1)
        t.returned();t.complete();self.assertFalse(t.cap.callback_frames)
    def test_callback_cpu_corruption_stops(self):
        t=Target();t.through_native();t.u64(0xe00000,0xe00100)
        t.cap.hit('semantic_callback',Context(rsp=0xe00000),1);t.u32(0x1000+72,1)
        with self.assertRaisesRegex(core.Rejected,'corrupted suspended CPU'):t.cap.hit('semantic_callback_return',Context(rsp=0xe00008),1)
    def test_unpaired_checkpoint_is_unknown_stop(self):
        t=Target()
        with self.assertRaisesRegex(core.Rejected,'unpaired'):t.checkpoint(1)
    def test_read_error_preserves_host_prefix(self):
        t=Target();t.cap.mem=lambda p,n:(_ for _ in ()).throw(OSError('unreadable'))
        with self.assertRaises(OSError):t.checkpoint(0)
        self.assertTrue(any(r['kind']=='semantic_raw_host' for r in t.cap.rows))
    def test_initial_frame_uses_correct_caller_and_semantic_dimensions(self):
        cs=dict(pc=0x11104bf5,registers=dict(ecx=0x10000))
        self.assertEqual(observer.initial_checks(cs,[GUEST,0x20000,800,600,0,16],0x10000),[])
        self.assertEqual(observer.initial_checks(cs,[GUEST,0x20000,0,0,32,0],0x10000),[])
        self.assertIn('caller',observer.initial_checks(cs,[0x696d2cd,0x20000,800,600,0,32],0x10000))
    def stop_target(self,value):
        t=Target();plan=read(O/'stop-mapping.json');e=copy.deepcopy(t.cs)
        t.cap.setres_entry=dict(cpu=e,frame=[GUEST,0x18000,800,600,0,32],thread=1,renderer=0x10000)
        t.cs['registers']['esp']+=24;t.cs['registers']['eax']=value;t.cs['rv']=GUEST;t.cs['pc']=0x696f4e9;t.sync()
        t.u32(t.cap.guest_base+0x18000+0x5c,0x10000);t.u32(t.cap.guest_base+0x10000+0x4698,0x4000)
        t.put(t.cap.base+plan['stop_rva'],bytes.fromhex(plan['stop_bytes']))
        values={'rip':t.cap.base+plan['stop_rva'],plan['stop_registers']['cpu']:t.cap.cpu,plan['stop_registers']['return_value']:GUEST}
        return t,values
    def test_nonzero_ubool_completion_and_zero_failure_are_distinct(self):
        for value in (0,1,32):
            t,values=self.stop_target(value);t.cap.hit('setres_completion_stop',Context(**values),1)
            result=read(t.out/'hard-stop.json')
            self.assertEqual(result['outcome'],'initial-setres-complete' if value else 'initial-setres-failed')
    def test_wrong_endpoint_register_is_fatal(self):
        t,values=self.stop_target(1);plan=read(O/'stop-mapping.json');values[plan['stop_registers']['cpu']]+=4
        with self.assertRaisesRegex(core.Rejected,'unsafe initial'):t.cap.hit('setres_completion_stop',Context(**values),1)

if __name__=='__main__':unittest.main()
