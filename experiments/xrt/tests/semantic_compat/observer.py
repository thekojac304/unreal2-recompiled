"""Separate semantic observer proposal. No launch, queue or policy-changing API.

Uses the retained contained debugger and permanent DR readback. Runtime checkpoints
make complete inputs/results available without assuming a fixed call sequence.
"""
import struct
from types import MethodType
from common import *
from supervisor.observer import construct as factory
NARGS={18:3,37:3,42:2,50:3,61:3,63:4,76:2,83:4,85:3,36:7,15:5,100:7}
NONVOL=('ebx','esi','edi','ebp')
HOST_NONVOL=('rbx','rbp','rsi','rdi','r12','r13','r14','r15')

def hardware(capture,ctx,plan,resume=False):
    """Use the unchanged previously qualified DR reservation/readback function."""
    import ast
    import ctypes as C
    from supervisor.windows import Context
    source=(H.parent/'renderer_config_diagnosis/observer.py').read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='hardware')
    scope={'C':C,'Context':Context,'core':core}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<retained hardware readback>','exec'),scope)
    return scope['hardware'](capture,ctx,plan,resume)

def native_abi_errors(before,after):
    errors=['native_nonvolatile_'+r for r in HOST_NONVOL if before['registers'][r]!=after['registers'][r]]
    if after['registers']['rsp']!=before['registers']['rsp']+8:errors.append('native_stack_return')
    a,b=bytes.fromhex(before['fxsave']),bytes.fromhex(after['fxsave'])
    if a[256:416]!=b[256:416]:errors.append('native_nonvolatile_XMM6_15')
    if a[:2]!=b[:2]:errors.append('native_x87_control')
    if (before['mxcsr']^after['mxcsr'])&0xffc0:errors.append('native_MXCSR_control')
    return errors

def discrepancies(before,after,frame,n,slot,result):
    """List individual ABI violations. No S_OK or canonical UBOOL expectation."""
    errors=[]
    for name,good in [('stack_cleanup',after['registers']['esp']==before['registers']['esp']+4*(n+1)),
                      ('return_address',after['rv']==frame[0])]:
        if not good:errors.append(name)
    for r in NONVOL:
        if after['registers'][r]!=before['registers'][r]:errors.append('nonvolatile_'+r)
    if slot!=18 and after['registers']['eax']!=result:errors.append('native_hresult_transfer')
    return errors

def initial_checks(cs,frame,renderer_binding):
    checks=dict(caller=frame[0]==GUEST and cs['pc']==0x11104bf5,
                viewport=bool(frame[1]),renderer_binding=renderer_binding==cs['registers']['ecx'],
                renderer=bool(cs['registers']['ecx']))
    return [name for name,good in checks.items() if not good]

def construct(out,plan,check_environment,dependencies):
    l=legacy()
    # Replace only this in-memory instance's historical 40-byte layout assertion
    # with the exact candidate's independently checked PDB symbols/layout.
    core.require(plan['device_layout_verified'],'candidate device layout not verified')
    l.S.symbols=lambda:plan['symbols']
    cap=factory(l,out,plan,check_environment,[identity()[0],*dependencies])
    fatal_hit=cap.hit;cap.operations=[];cap.entries={};cap.native_active=None;cap.setres_entry=None
    cap.callback_frames=[];cap.strict_discrepancies=[]
    old_objects=cap.object_state
    def objects(self):
        row=old_objects();raw=self.mem(self.sym('d8_device'),plan['device_layout']['size'])
        row.update(registry_size=len(raw),registry_raw=raw.hex(),live_caps=list(struct.unpack_from('<53I',raw,40)),caps_valid=struct.unpack_from('<I',raw,252)[0])
        return row
    cap.object_state=MethodType(objects,cap)
    # Readback implementation is copied unchanged from the previously qualified
    # observer; its only endpoint parameter remains the separately reviewed plan.

    def idle(self):
        self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.sym('d8_semantic_checkpoint'):'semantic_checkpoint'}
        if self.setres_entry is None:self.breakpoints[self.sym('f_696e890')]='semantic_setres_entry'

    def raw(self,tag,ctx,tid):
        # This record is durable even if a subsequent target read fails.
        self.log('semantic_raw_host',tag=tag,thread=tid,host=ctx.snapshot())
        self.log('semantic_raw_host_stack',tag=tag,raw=self.mem(ctx.get('rsp'),96).hex())
        if self.cpu:
            cpu=self.cpu_state(self.cpu);self.log('semantic_raw_cpu',tag=tag,cpu=cpu,raw=self.mem(self.cpu,416).hex())
            self.log('semantic_raw_objects',tag=tag,objects=self.object_state(),hwnds=self.hwnds())
        return self.cpu_state(self.cpu) if self.cpu else None

    def hit(self,tag,ctx,tid):
        try:
            self.log('semantic_raw_host',tag=tag,thread=tid,host=ctx.snapshot())
            if tag in ('semantic_checkpoint','semantic_setres_entry'):
                self.cpu=ctx.get('rcx');self.guest_base=self.u64(self.sym('xrt_g'))
            cs=raw(self,tag,ctx,tid)
            if tag=='semantic_setres_entry':
                esp=cs['registers']['esp'];core.require(esp+24<=0x100000000,'unsafe SetRes argument frame overflow')
                frame=self.words(self.guest_base+esp,6);r=cs['registers']['ecx']
                self.log('semantic_setres_frame',frame=frame)
                core.require(r and r+0x469c<=0x100000000 and frame[1] and frame[1]+0x184<=0x100000000,'unsafe SetRes object range')
                self.log('semantic_setres_raw',frame=frame,renderer_raw=self.guest(r,0x469c).hex(),viewport_raw=self.guest(frame[1],0x184).hex())
                binding=self.u32(self.guest_base+frame[1]+0x5c);errors=initial_checks(cs,frame,binding)
                self.log('semantic_setres_checks',discrepancies=errors)
                core.require(not errors,'unsafe/unknown initial SetRes: '+', '.join(errors))
                self.setres_entry=dict(cpu=cs,frame=frame,thread=tid,renderer=r);idle(self);return
            if tag=='semantic_checkpoint':
                phase,slot=ctx.get('rdx')&0xffffffff,ctx.get('r8')&0xffffffff
                p=ctx.get('r9');rsp=ctx.get('rsp');size=self.u32(rsp+40);result=self.u32(rsp+48);error=self.u32(rsp+56)
                row=dict(phase=phase,slot=slot,size=size,result=result,last_error=error,data_pointer=p,
                         host=ctx.snapshot(),cpu=cs,objects=self.object_state())
                self.log('semantic_checkpoint_raw',**row)
                if p and size:self.log('semantic_native_structure',slot=slot,phase=phase,address=p,raw=self.mem(p,size).hex())
                if phase==0:
                    if slot not in NARGS:
                        self.log('semantic_auxiliary_com_entry',slot=slot);return
                    frame=self.words(self.guest_base+cs['registers']['esp'],NARGS[slot]+1)
                    self.log('semantic_argument_frame',slot=slot,frame=frame,raw=self.guest(cs['registers']['esp'],4*len(frame)).hex())
                    core.require(slot not in self.entries,'unsafe nested device operation')
                    self.entries[slot]=dict(cpu=cs,frame=frame,thread=tid,cpu_raw=self.mem(self.cpu,416));return
                core.require(slot in self.entries,'unpaired semantic checkpoint')
                entry=self.entries[slot]
                if phase==1:
                    core.require(self.native_active is None,'unsafe overlapping native operation')
                    obj=row['objects'];host=obj['parent_state']['host'] if slot==100 else obj['host']
                    core.require(host,'stale native object')
                    native=self.u64(self.u64(host)+(15 if slot==100 else slot)*8)
                    entry.update(host=host,slot=slot,input=p,input_bytes=self.mem(p,size) if p and size else b'',suspended=self.mem(self.cpu,416))
                    self.native_active=entry
                    self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',native:'semantic_native_entry',self.sym('invoke_gui_proc'):'semantic_callback'};return
                if phase==2:
                    core.require(entry.get('native_return_seen'),'missing independently captured native return')
                    core.require(slot==18 or result==entry['actual_hresult'],'native checkpoint HRESULT differs')
                    core.require(error==entry['actual_error'],'native checkpoint last-error differs')
                    entry.update(result=result,error=error);return
                if phase==3:
                    errors=discrepancies(entry['cpu'],cs,entry['frame'],NARGS[slot],slot,entry['result'])
                    if slot==100:
                        obj=self.object_state();native=entry['native_device_output'];f=entry['frame'];pp=entry['native_pp_after']
                        native_window=struct.unpack_from('<Q',pp,24)[0]
                        window=next((r['guest'] for r in self.hwnds() if r['native']==native_window),None) if native_window else 0
                        if window is None:errors.append('presentation_window_ownership')
                        else:
                            expected_pp=pp[:24]+struct.pack('<I',window)+pp[32:56]
                            if self.guest(f[6],52)!=expected_pp:errors.append('presentation_output_transfer')
                        token=self.u32(self.guest_base+f[7]);success=entry['result']<0x80000000
                        if token!=(obj['guest'] if success and native else 0):errors.append('creation_guest_output_identity')
                        if success and (not native or obj['host']!=native or not obj['guest_refs']):errors.append('creation_native_output_identity')
                    before_raw=bytearray(entry['cpu_raw']);after_raw=self.mem(self.cpu,416)
                    for lo,hi in ((0,4),(16,20),(64,68),(142,144)):before_raw[lo:hi]=after_raw[lo:hi]
                    if bytes(before_raw)!=after_raw:errors.append('guest_cpu_outside_return_and_status')
                    if self.u32(self.guest_base+cs['fs_base']+0x34)!=entry['error']:errors.append('last_error_transfer')
                    self.log('semantic_abi_evaluation',slot=slot,discrepancies=errors)
                    core.require(not errors,'unsafe ABI discrepancy: '+', '.join(errors))
                    if cs['x87']!=entry['cpu']['x87']:
                        self.strict_discrepancies.append(dict(slot=slot,finding='guest_x87',before=entry['cpu']['x87'],after=cs['x87']))
                        self.log('strict_differential',**self.strict_discrepancies[-1])
                    self.operations.append(dict(slot=slot,result=None if slot==18 else result,last_error=error,outcome='valid-supported' if slot==18 or result<0x80000000 else 'valid-native-failure'))
                    del self.entries[slot];self.native_active=None;idle(self);return
                raise RuntimeError('unknown checkpoint phase; evidence preserved')
            if tag=='semantic_native_entry':
                entry=self.native_active;core.require(ctx.get('rcx')==entry['host'],'native COM identity')
                slot=entry['slot'];n=NARGS[slot];rsp=ctx.get('rsp')
                args=[ctx.get(r) for r in ('rcx','rdx','r8','r9')][:n]
                args += [self.u64(rsp+40+8*i) for i in range(max(0,n-4))]
                expected=entry['frame'][1:];expected[0]=entry['host'];pointer_indices={42:1,37:2,18:2,36:2}
                wide={0}
                if slot in pointer_indices:
                    index=pointer_indices[slot];guest_pointer=expected[index];expected[index]=entry['input'];wide.add(index)
                    entry['guest_input_pointer']=guest_pointer
                    if entry['input_bytes']:
                        core.require(entry['input_bytes']==self.guest(guest_pointer,len(entry['input_bytes'])),'typed native copy differs from guest input')
                        core.require(not self.guest_base<=entry['input']<self.guest_base+0x100000000,'guest pointer forwarded to native')
                wide.update({61:{2},83:{2},85:{1},15:{1,2,3,4}}.get(slot,set()))
                if slot==100:
                    if expected[3]:
                        window=next((row for row in self.hwnds() if row['guest']==expected[3]),None)
                        core.require(window is not None,'CreateDevice focus ownership');expected[3]=window['native']
                    guest_pp=self.guest(entry['frame'][6],52);token=struct.unpack_from('<I',guest_pp,24)[0]
                    presentation=next((r['native'] for r in self.hwnds() if r['guest']==token),None) if token else 0
                    self.log('semantic_creation_input',guest=guest_pp.hex(),native=entry['input_bytes'].hex(),window_token=token)
                    core.require(presentation is not None,'CreateDevice presentation ownership')
                    core.require(entry['input_bytes']==guest_pp[:24]+struct.pack('<Q',presentation)+guest_pp[28:],'typed CreateDevice presentation differs')
                    core.require(not self.guest_base<=entry['input']<self.guest_base+0x100000000,'guest CreateDevice presentation forwarded')
                    expected[5]=entry['input'];wide.update((3,5,6))
                    # &device is a native output local; it must not be the guest output.
                    expected[6]=args[6]
                    core.require(not self.guest_base<=args[6]<self.guest_base+0x100000000,'guest CreateDevice output forwarded')
                    entry['device_output']=args[6]
                    self.log('semantic_creation_output_before',address=args[6],raw=self.mem(args[6],8).hex())
                errors=['argument_'+str(i) for i,(observed,wanted) in enumerate(zip(args,expected))
                        if (observed if i in wide else observed&0xffffffff)!=wanted]
                self.log('semantic_native_arguments',slot=slot,arguments=args,expected=expected,discrepancies=errors,host=ctx.snapshot(),raw_stack=self.mem(rsp,96).hex())
                core.require(not errors,'native arguments differ: '+', '.join(errors))
                entry.update(native_context=ctx.snapshot(),native_return=self.u64(ctx.get('rsp')))
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',entry['native_return']:'semantic_native_return',self.sym('invoke_gui_proc'):'semantic_callback'};return
            if tag=='semantic_callback':
                core.require(self.native_active is not None,'callback without native context')
                self.callback_frames.append(dict(cpu_raw=self.mem(self.cpu,416),return_host=self.u64(ctx.get('rsp'))))
                self.log('semantic_callback_context',host=ctx.snapshot(),depth=len(self.callback_frames))
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.callback_frames[-1]['return_host']:'semantic_callback_return',self.sym('invoke_gui_proc'):'semantic_callback'};return
            if tag=='semantic_callback_return':
                callback=self.callback_frames.pop();core.require(callback['cpu_raw']==self.mem(self.cpu,416),'callback corrupted suspended CPU')
                address=self.callback_frames[-1]['return_host'] if self.callback_frames else self.native_active['native_return']
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',address:'semantic_callback_return' if self.callback_frames else 'semantic_native_return',self.sym('invoke_gui_proc'):'semantic_callback'};return
            if tag=='semantic_native_return':
                entry=self.native_active;error=self.u32(self.threads[tid][1]+0x68)
                self.log('semantic_native_result',slot=entry['slot'],hresult=None if entry['slot']==18 else ctx.get('rax')&0xffffffff,last_error=error,host=ctx.snapshot())
                if entry.get('device_output'):
                    entry['native_device_output']=self.u64(entry['device_output'])
                    entry['native_pp_after']=self.mem(entry['input'],56)
                    self.log('semantic_creation_output_after',address=entry['device_output'],raw=self.mem(entry['device_output'],8).hex(),presentation=entry['native_pp_after'].hex())
                core.require(entry['suspended']==self.mem(self.cpu,416),'native call corrupted suspended CPU')
                if entry['input_bytes'] and entry['slot']!=100:
                    host_data=self.mem(entry['input'],len(entry['input_bytes']));guest_data=self.guest(entry['guest_input_pointer'],len(entry['input_bytes']))
                    self.log('semantic_const_input_after',slot=entry['slot'],host=host_data.hex(),guest=guest_data.hex(),original=entry['input_bytes'].hex())
                    core.require(host_data==entry['input_bytes'],'native modified const input structure')
                    core.require(guest_data==entry['input_bytes'],'guest input changed during native call; callback ordering requires characterization')
                frame=entry['frame'];core.require(self.guest(entry['cpu']['registers']['esp'],4*len(frame))==struct.pack('<'+'I'*len(frame),*frame),'native changed guest argument frame')
                entry.update(native_return_seen=True,actual_hresult=ctx.get('rax')&0xffffffff,actual_error=error)
                # FPU status discrepancies are recorded individually, not waived
                # and not used as unrelated experimental admission policy.
                before,after=entry['native_context'],ctx.snapshot()
                errors=native_abi_errors(before,after);self.log('semantic_native_abi',discrepancies=errors)
                core.require(not errors,'unsafe native ABI: '+', '.join(errors))
                a,b=bytes.fromhex(before['fxsave']),bytes.fromhex(after['fxsave'])
                for name,start,end in [('native_x87_status',2,5),('native_x87_registers',32,160),('native_MXCSR_status',24,28)]:
                    if a[start:end]!=b[start:end]:
                        self.log('strict_differential',finding=name,slot=entry['slot'],before=a[start:end].hex(),after=b[start:end].hex())
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.sym('d8_semantic_checkpoint'):'semantic_checkpoint'};return
            if tag=='setres_completion_stop':
                e=self.setres_entry
                core.require(e and not self.entries and self.native_active is None,'incomplete native operation at stop')
                regs=plan['stop_registers'];native_stop=self.base+plan['stop_rva'];obj=self.object_state()
                checks=dict(stack=cs['registers']['esp']==e['cpu']['registers']['esp']+24,
                    return_pc=cs['rv']==GUEST and cs['pc']==0x696f4e9,same_thread=tid==e['thread'],
                    nonvolatile=all(cs['registers'][r]==e['cpu']['registers'][r] for r in NONVOL),
                    host_pc=ctx.get('rip')==native_stop,cpu_register=ctx.get(regs['cpu'])==self.cpu,
                    return_register=ctx.get(regs['return_value'])&0xffffffff==GUEST,
                    instruction=self.mem(native_stop,len(bytes.fromhex(plan['stop_bytes'])))==bytes.fromhex(plan['stop_bytes']),
                    viewport_renderer=self.u32(self.guest_base+e['frame'][1]+0x5c)==e['renderer'])
                if cs['registers']['eax']:
                    checks['live_device']=bool(obj['host'] and obj['guest'] and obj['guest_refs'])
                    checks['renderer_device']=self.u32(self.guest_base+e['renderer']+0x4698)==obj['guest']
                outcome='initial-setres-complete' if cs['registers']['eax'] else 'initial-setres-failed'
                self.log('semantic_initial_return',checks=checks,return_value=cs['registers']['eax'],operations=self.operations,outcome=outcome,instruction_executed=False)
                core.require(all(checks.values()),'unsafe initial SetRes return')
                self.snapshot_events()
                save(out/'hard-stop.json',dict(hit=True,guest_address='0x11104bf8',native_address=ctx.get('rip'),instruction_executed=False,
                    return_value=cs['registers']['eax'],outcome=outcome,operations=self.operations,strict_discrepancies=self.strict_discrepancies))
                self.stop_requested=True;return
            return fatal_hit(tag,ctx,tid)
        except BaseException:
            self.snapshot_events();raise

    def on_create(self,ev):
        core.require(self.mem(self.base+plan['stop_rva'],len(bytes.fromhex(plan['stop_bytes'])))==bytes.fromhex(plan['stop_bytes']),'candidate endpoint bytes')
        idle(self);check_environment('target-created-before-first-resume')
    cap.on_create=MethodType(on_create,cap);cap.hit=MethodType(hit,cap)
    cap.update=MethodType(lambda self,ctx,resume=False:hardware(self,ctx,plan,resume),cap)
    cap.ready=MethodType(idle,cap)
    return cap,l
