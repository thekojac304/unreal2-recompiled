"""Controller rejection tests; simulated target memory never launches a game."""
import copy
import json
import pathlib
import struct
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *
import observer
from mapping import sequence


class Context:
    def __init__(self,**values):self.values=values
    def get(self,name):return self.values.get(name,0)
    def snapshot(self):
        return dict(registers={r:self.get(r) for r in ('rax','rcx','rdx','rsp','rbx','rbp','rsi','rdi','r12','r13','r14','r15')},
                    mxcsr=self.values.get('mxcsr',0x3f80),fxsave=bytes(512).hex())


class Target:
    def __init__(self):
        dest=O/('controller-test-'+str(uuid.uuid4()));dest.mkdir()
        plan=read(O/'stop-mapping.json')
        self.cap,_=observer.construct(dest,plan,lambda _:None,[])
        c=self.cap;c.cpu=0x1000;c.guest_base=0x100000000;c.base=0x140000000
        c.rows += [dict(kind='state_bridge_return') for _ in range(8)]
        self.memory={}
        c.mem=lambda p,n:bytes(self.memory.get(p+i,0) for i in range(n))
        self.cs=dict(registers={r:0 for r in ('eax','ecx','edx','ebx','esp','ebp','esi','edi')},flags={},x87={},rv=0,pc=0,fs_base=0x70000)
        c.cpu_state=lambda p:copy.deepcopy(self.cs)
        c.snapshot_events=lambda:None
        c.hwnds=lambda:[]
        c.resize_geometry=lambda:dict(client=[0,0,1540,945],style=0x04cf0000,dpi=96,focus=1)
        self.obj=dict(guest=0x30000,host=0x800000,parent=0x801000,native_vtable=0x802000,creating=0,rendering=0,native_failed=0)
        c.object_state=lambda:copy.deepcopy(self.obj)
        c.device_identity=copy.deepcopy(self.obj)
        c.setres_entry=dict(cpu=dict(pc=0x11104bf5,registers=dict(ecx=0x10000,esp=0x10000,ebx=0,esi=0,edi=0,ebp=0)),frame=[GUEST,0x18000,1540,945,0,32],classification='initial',thread=1,renderer=0x10000,viewport=0x18000)
        c.threads={1:(1,0xa00000)}
        profile=c.configuration_profile
        self.put(c.guest_base+0x10000+0x4134,struct.pack('<53I',*profile['caps']['caps']))
        for offset,v in profile['fields'].items():self.u32(c.guest_base+0x10000+int(offset,0),v)
        self.u32(c.guest_base+0x10000+0x4698,self.obj['guest']);self.u32(c.guest_base+0x18000+0x5c,0x10000)
        self.u32(c.guest_base+0x70000+0x34,18);self.u32(0xa00000+0x68,18)
        self.put(0xb00000,struct.pack('<Q',0x900000))

    def put(self,p,data):self.memory.update({p+i:b for i,b in enumerate(data)})
    def u32(self,p,v):self.put(p,struct.pack('<I',v))

    def bridge(self,index):
        c=self.cap;q=c.profile[index];c.profile_index=index
        self.cs.update(pc=q['site'],rv=0)
        self.cs['registers'].update(esp=0x58000,eax=0x1234)
        args=[q.get(k,0) for k in ('a','b','c')[:q['n']-1]]
        inp=None
        if q['slot']==42:
            inp=struct.pack('<17I',*[0x3f000000]*3,*[0x3f800000]*5,*[0]*9);args=[0x50000]
        elif q['slot'] in (37,18):
            inp=(PRIOR/'actual-gamma-ramp.bin').read_bytes() if q['slot']==18 else struct.pack('<16I',*[0x3f800000 if i in (0,5,10,15) else 0 for i in range(16)])
            args=[q['a'],0x50000]
        if inp:self.put(c.guest_base+0x50000,inp);self.put(0x700000,inp)
        frame=[q['return_pc'],self.obj['guest'],*args]
        self.put(c.guest_base+0x58000,struct.pack('<'+'I'*len(frame),*frame))
        self.put(self.obj['native_vtable']+q['slot']*8,struct.pack('<Q',0x810000))
        c.hit('profile_entry',Context(rcx=c.cpu,rsp=0xb00000),1)
        nativeargs=list(args)
        if inp:nativeargs[-1]=0x700000
        values=dict(zip(('rdx','r8','r9'),nativeargs))
        c.hit('profile_native_entry',Context(rcx=self.obj['host'],rsp=0xb00000,**values),1)

    def finish(self,hr=0,error=18):
        c=self.cap;a=c.active;q=a['q'];self.u32(0xa00000+0x68,error)
        c.hit('profile_native_return',Context(rax=hr,mxcsr=0x3fa0 if q['slot']==18 else 0x3f80),1)
        self.cs['registers'].update(esp=0x58000+4*(q['n']+1),eax=0x1234 if q['slot']==18 else 0)
        self.cs['rv']=a['frame'][0]
        c.hit('profile_bridge_return',Context(),1)


class Controller(unittest.TestCase):
    def test_all_239_native_pairs_and_resize_then_endpoint(self):
        t=Target();c=t.cap
        for i,q in enumerate(c.profile):
            if q.get('kind')=='resize':
                c.profile_index=i;t.cs['pc']=0x696f48d;t.cs['registers']['esp']=0x58000
                t.put(c.guest_base+0x58000,struct.pack('<4I',0x696f493,16,1540,945))
                c.hit('resize_entry',Context(rcx=c.cpu,rsp=0xb00000),1)
                c.hit('resize_callback',Context(rcx=0x333,rdx=0x47,rsp=0xb00000),1)
                c.hit('resize_callback_return',Context(),1)
                t.cs['rv']=0x696f493;t.cs['registers'].update(esp=0x58010,eax=1)
                c.hit('resize_return',Context(),1)
            else:t.bridge(i);t.finish()
        t.cs.update(rv=GUEST,pc=0x696f4e9);t.cs['registers'].update(esp=0x10018,eax=1)
        c.hit('setres_completion_stop',Context(rip=c.base+RVA,rdi=c.cpu,rbx=GUEST),1)
        self.assertTrue(c.stop_requested)
        self.assertEqual(len(c.completed),240)

    def test_failed_hresult_stops(self):
        t=Target();t.bridge(0)
        with self.assertRaises(core.Rejected):t.finish(hr=0x80004005)

    def test_last_error_difference_stops(self):
        t=Target();t.bridge(0)
        with self.assertRaises(core.Rejected):t.finish(error=0)

    def test_native_input_mutation_stops(self):
        t=Target();t.bridge(0);t.u32(0x700000,0)
        with self.assertRaises(core.Rejected):t.finish()

    def test_unexpected_method_stops_before_native(self):
        t=Target()
        with self.assertRaises(RuntimeError):t.cap.hit('unexpected_profile_operation',Context(),1)

    def test_unexpected_native_callback_stops(self):
        t=Target()
        with self.assertRaises(RuntimeError):t.cap.hit('profile_callback_refused',Context(),1)

    def test_renderer_identity_change_stops(self):
        t=Target();t.obj['host']+=8
        with self.assertRaises(core.Rejected):t.bridge(0)

    def test_capability_change_stops(self):
        t=Target();t.u32(t.cap.guest_base+0x14134,0)
        with self.assertRaises(core.Rejected):t.bridge(0)

    def test_wrong_stack_return_stops(self):
        a=dict(registers=dict(esp=100,eax=9,ecx=0,edx=0,ebx=0,ebp=0,esi=0,edi=0),flags={},x87={})
        b=copy.deepcopy(a);b.update(rv=33);b['registers'].update(esp=112,eax=0)
        with self.assertRaises(core.Rejected):observer.returned(a,b,[33],3)

    def test_unclassified_x87_and_mxcsr_not_normalized(self):
        a=Context().snapshot();b=copy.deepcopy(a);b['mxcsr']|=0x20
        with self.assertRaises(core.Rejected):observer.native_abi(a,b)
        observer.native_abi(a,b,gamma=True)
        raw=bytearray.fromhex(b['fxsave']);raw[32]=1;b['fxsave']=raw.hex()
        with self.assertRaises(core.Rejected):observer.native_abi(a,b,gamma=True)

    def test_historical_production_endpoint_still_rejects_advance(self):
        batch=dict(id=str(uuid.uuid4()),started_at=100,expires_at=1000,genuine_limit=1)
        ident=str(uuid.uuid4())
        req=dict(version=1,id=ident,batch_id=batch['id'],created_at=101,expires_at=300,objective='Reject endpoint advance in historical production parser',
                 candidate='out/desktop-supervisor/candidates/'+ident+'.json',manifest_sha256='a'*64,
                 expected_stop=dict(kind='permanent-stop',guest_address='0x0696d2cd'),scope=core.SCOPE,timeout_seconds=60)
        with self.assertRaises(core.Rejected):core.parse_request(req,batch,now=102)


if __name__=='__main__':unittest.main(verbosity=2)
