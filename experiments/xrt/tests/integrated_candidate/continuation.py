"""Staged observer composition only. No launcher, service mutation or authorization."""
import struct
from types import MethodType
from common import core,GUEST,legacy
from observer import capture_endpoint
from hardware_fixture import hardware

def construct(out,plan,check_environment,allowed_modules):
    from supervisor.observer import construct as retained_construct
    core.require(plan['device_layout_verified'] and plan['device_layout']['size']==280,'candidate PDB registry layout')
    retained=legacy();old_symbols=retained.S.symbols
    # Instance-local substitution of a freshly PDB-verified symbol/layout map;
    # the historical constructor's 40-byte registry assertion is obsolete.
    retained.S.symbols=lambda:plan['symbols']
    try:capture=retained_construct(retained,out,plan,check_environment,allowed_modules)
    finally:retained.S.symbols=old_symbols
    old_objects=capture.object_state
    def objects(self):
        row=old_objects();raw=self.mem(self.sym('d8_device'),plan['device_layout']['size'])
        row.update(registry_size=len(raw),registry_raw=raw.hex(),children=struct.unpack_from('<I',raw,20)[0],
                   live_caps=list(struct.unpack_from('<53I',raw,40)),caps_valid=struct.unpack_from('<I',raw,252)[0])
        return row
    capture.object_state=MethodType(objects,capture)
    capture.out=out
    return install(capture,plan,check_environment)

def verify_pair(entry,raw,events,tid,cpu_pointer):
    core.require(entry is not None,'Init entry missing')
    before=bytes.fromhex(entry['raw'])
    core.require(len(before)==len(raw)==416,'complete paired CPU')
    core.require(entry['tid']==tid and entry['cpu']==cpu_pointer,'Init thread/CPU identity')
    u=lambda b,o:struct.unpack_from('<I',b,o)[0]
    core.require(u(raw,16)==u(before,16)+4 and u(raw,64)==GUEST,'Init return stack/address')
    core.require(u(before,68)==0x1090ed59 and u(raw,68)==0x1038fba9,'original Init caller/RET instruction')
    core.require(all(u(raw,o)==u(before,o) for o in (12,20,24,28)),'Init guest nonvolatile registers')
    core.require([r.get('seq') for r in events]==list(range(1,len(events)+1)) and events,'complete ordered runtime events')
    core.require(not any(r.get('truncated') for r in events),'truncated runtime evidence')
    core.require(not any(r.get('kind') in ('engine_tick_call','engine_tick_return','level_tick_call','level_tick_return','fatal','timeout') for r in events),'tick/fatal before endpoint')
    calls=[r for r in events if r.get('kind')=='engine_init_call']
    returns=[r for r in events if r.get('kind')=='engine_init_return']
    core.require(len(calls)==len(returns)==1,'exactly one Init call/return required')
    a,b=calls[0],returns[0]
    core.require(type(a.get('thread')) is int and a['thread']>=0 and a['thread']==b.get('thread'),'runtime Init thread')
    core.require(a['seq']<b['seq'] and a.get('this')==b.get('this')==u(before,4)!=0,'Init object/order')
    core.require(a.get('esp')==b.get('esp_before')==u(before,16) and b.get('esp_after')==u(raw,16),'runtime/raw stack agreement')
    core.require(a.get('return')==b.get('return')==b.get('actual_return')==GUEST,'runtime/raw return agreement')
    return dict(passed=True,engine_object=a['this'],runtime_thread=a['thread'],host_thread=tid,
                entry_seq=a['seq'],return_seq=b['seq'],game_scene_verified=False)

def install(capture,plan,check_environment):
    """Compose an already constructed bounded observer; never run or authorize it.

    The caller retains FilePins, module allowlist, Job/watchdog, fatal capture,
    event snapshot and cleanup. All four initial hardware slots are explicit.
    """
    core.require(capture.base==0 and not capture.breakpoints,'unexecuted observer required')
    fatal_hit=capture.hit
    capture.init_entry=None
    def on_create(self,ev):
        for rva,hexbytes in ((plan['stop_rva'],plan['stop_bytes']),(plan['entry_rva'],plan['entry_bytes'])):
            expected=bytes.fromhex(hexbytes)
            core.require(self.mem(self.base+rva,len(expected))==expected,'Init mapped code identity')
        self.breakpoints={self.base+plan['entry_rva']:'init_entry',self.base+plan['stop_rva']:'init_return',
                          self.sym('xrt_fatal'):'fatal_entry',self.sym('d8_CreateDevice'):'init_create_device'}
        check_environment('target-created-before-first-resume')
    def update(self,ctx,resume=False):
        hardware(self,ctx,dict(plan,endpoint_tag='init_return',inert_candidate=False),resume)
    def hit(self,tag,ctx,tid):
        if tag=='init_create_device':
            check_environment('before-CreateDevice');return
        if tag=='init_entry':
            core.require(self.init_entry is None,'duplicate Init entry')
            pointer=ctx.get('rcx');raw=self.mem(pointer,416)
            self.log('integrated_init_entry_raw',tid=tid,cpu=pointer,raw=raw.hex(),host=ctx.snapshot())
            core.require(len(raw)==416,'Init entry CPU size')
            self.guest_base=self.u64(self.sym('xrt_g'));self.cpu=pointer
            esp=struct.unpack_from('<I',raw,16)[0]
            core.require(self.mem(self.guest_base+esp,4)==struct.pack('<I',GUEST),'Init original caller return')
            self.init_entry=dict(tid=tid,cpu=pointer,raw=raw.hex())
            return
        if tag=='init_return':
            raw=capture_endpoint(self,ctx,plan)
            self.snapshot_events()
            data=core.read_large(self.out/'runtime-events.json')
            core.require(data['events_dropped']==0,'dropped runtime evidence')
            result=verify_pair(self.init_entry,raw,data['events'],tid,ctx.get(plan['stop_registers']['cpu']))
            self.log('integrated_init_verified',**result)
            core.atomic(self.out/'hard-stop.json',dict(hit=True,guest_address=hex(GUEST),native_address=ctx.get('rip'),
                instruction_executed=False,init_pair=result,terminated_before_continue_required=True))
            return
        core.require(tag=='fatal_entry','unexpected continuation breakpoint')
        fatal_hit(tag,ctx,tid)
        self.snapshot_events()
        raise core.Rejected('fatal before Init return; no retry')
    for name,fn in (('on_create',on_create),('update',update),('hit',hit)):
        setattr(capture,name,MethodType(fn,capture))
    return capture
