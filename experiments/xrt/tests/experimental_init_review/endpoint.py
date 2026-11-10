"""Shared endpoint acceptance checks. Inspect raw state; never normalize it."""
import struct
from physical_audit import require
u32=lambda b,o:struct.unpack_from('<I',b,o)[0]
u64=lambda b,o:struct.unpack_from('<Q',b,o)[0]

def verify_pair(records,raw,events,host_tid,cpu_pointer):
    scopes=[r for r in records if r.name==b'UGameEngine.Init']
    require(len(scopes)==2 and [r.event for r in scopes]==[2,3],'exactly one Init entry/normal return')
    a,b=scopes
    require(a.result==0x1038f460 and a.domain==b.domain==1,'genuine Init marker/domain')
    require(a.invocation==b.invocation and a.thread==b.thread==host_tid,'Init invocation/host thread')
    before=bytes(a.cpu);after=bytes(b.cpu)
    require(a.cpu_size==b.cpu_size==len(raw)==416,'complete Init CPU')
    require(u64(before,408)==u64(after,408)==cpu_pointer!=0,'Init CPU/thread identity (CPU first in XrtThread)')
    require(raw==after,'endpoint/stopped-monitor CPU disagreement')
    require(u32(after,16)==u32(before,16)+4 and u32(after,64)==0x1090ed5c,'Init stack/return')
    require(u32(before,68)==0x1090ed59 and u32(after,68)==0x1038fba9,'Init original caller/RET site')
    require(all(u32(after,o)==u32(before,o) for o in (12,20,24,28)),'Init nonvolatile registers')
    require(events and [r.get('seq') for r in events]==list(range(1,len(events)+1)),'complete ordered runtime events')
    require(not any(r.get('truncated') or r.get('kind') in ('engine_tick_call','engine_tick_return','level_tick_call','level_tick_return','fatal','timeout') for r in events),'tick/fatal/truncated event')
    calls=[r for r in events if r.get('kind')=='engine_init_call'];returns=[r for r in events if r.get('kind')=='engine_init_return']
    require(len(calls)==len(returns)==1,'one independent runtime Init pair')
    c,d=calls[0],returns[0]
    require(c['seq']<d['seq'] and type(c.get('thread')) is int and c['thread']>=0 and c['thread']==d.get('thread'),'runtime Init ordering/thread')
    require(c.get('this')==d.get('this')==u32(before,4)!=0,'runtime Init object')
    require(c.get('esp')==d.get('esp_before')==u32(before,16) and d.get('esp_after')==u32(after,16),'independent stack agreement')
    require(c.get('return')==d.get('return')==d.get('actual_return')==0x1090ed5c,'independent return agreement')
    return dict(passed=True,engine_object=c['this'],host_thread=host_tid,cpu_pointer=cpu_pointer,entry_sequence=a.sequence,return_sequence=b.sequence,main_loop_ticks=0)

def verify_device(records,registry):
    native=[r for r in records if r.name==b'D8Interface.CreateDevice' and r.event==3]
    require(len(native)==1 and native[0].result==0,'one successful actual native CreateDevice')
    created=[r for r in records if r.event==7 and r.interface_id==2 and r.name==b'created']
    require(len(registry)==280 and len(created)==1 and created[0].guest==u32(registry,0) and created[0].host==u64(registry,24) and u32(registry,4)>0,'live guest/native device identity')
    return dict(guest=created[0].guest,native=created[0].host,refs=u32(registry,4))

def verify_transfers(records):
    begins={r.invocation:r for r in records if r.event==2}
    ends={r.invocation:r for r in records if r.event==3}
    checked=[]
    for r in records:
        if r.event!=3 or r.name not in (b'D8Interface.CreateDevice',b'D8Device.CreateTexture',b'IDirectInputDevice8W.Acquire'):continue
        parent=r.parent
        while parent and begins[parent].domain!=1:parent=begins[parent].parent
        require(parent in ends,'native transfer has no completed adapter')
        a=ends[parent]
        require(a.guest_error==r.error and a.result&0xffffffff==r.result&0xffffffff,'actual native result/error transfer disagreement')
        checked.append(dict(method=r.name.decode(),sequence=r.sequence,native_hresult=r.result&0xffffffff,native_last_error=r.error,guest_last_error=a.guest_error))
    return checked
