"""Additive read-only observer. Hardware debug registers are its only target writes."""
import ctypes as C
from ctypes import wintypes as T
import struct
from types import MethodType
from common import *
from mapping import sequence
from supervisor.observer import construct as retained_construct
from supervisor.windows import Context
from supervisor.windows import api
import evidence
import profile_gate

NONVOL = ('rbx','rbp','rsi','rdi','r12','r13','r14','r15')


def hardware(capture, ctx, plan, resume=False):
    hard=capture.base+plan['stop_rva']
    capture.breakpoints[hard]='setres_completion_stop'
    addresses=list(capture.breakpoints)
    if len(addresses)>4:
        deferred=[a for a in addresses if capture.breakpoints[a] in ('bridge_return','render_bridge_return','state_bridge_return','profile_bridge_return')]
        core.require(len(addresses)==5 and len(deferred)==1,'breakpoint slot budget')
        addresses.remove(deferred[0])
    core.require(hard in addresses and len(addresses)<=4,'permanent endpoint absent')
    ctx.arm(addresses,resume)
    actual=Context(ctx.thread)
    dr=[C.c_uint64.from_address(actual.ptr+72+8*i).value for i in range(4)]
    dr7=C.c_uint64.from_address(actual.ptr+112).value
    core.require(dr==addresses+[0]*(4-len(addresses)) and dr7&0xffff00ff==sum(1<<(2*i) for i in range(len(addresses))),'live DR readback')
    capture.log('breakpoints_readback',thread_handle=int(ctx.thread),addresses=addresses,dr=dr,dr7=dr7,
                guest_stop='0x11104bf8',permanent_stop_present=True)


def native_abi(before, after, gamma=False):
    core.require(all(before['registers'][r]==after['registers'][r] for r in NONVOL),'native nonvolatile GPR change')
    a,b=bytes.fromhex(before['fxsave']),bytes.fromhex(after['fxsave'])
    # x87 control/status/tag, 80-bit registers, and nonvolatile XMM6..15.
    core.require(a[:5]==b[:5] and a[32:160]==b[32:160] and a[256:416]==b[256:416],'native x87/nonvolatile XMM change')
    core.require(after['mxcsr']==(before['mxcsr']|0x20 if gamma else before['mxcsr']),'unclassified native MXCSR difference')


def returned(entry, after, frame, n, void=False):
    core.require(after['registers']['esp']==entry['registers']['esp']+4*(n+1) and after['rv']==frame[0], 'guest return/stack discrepancy')
    core.require(after['flags']==entry['flags'] and after['x87']==entry['x87'],'guest CPU/FPU change')
    for r in ('ecx','edx','ebx','ebp','esi','edi'):
        core.require(after['registers'][r]==entry['registers'][r],'guest register changed: '+r)
    core.require(after['registers']['eax']==(entry['registers']['eax'] if void else 0),'failed/incorrect guest return')


def construct(out, plan, check_environment, dependencies):
    l=legacy()
    # All original CreateDevice/Clear/Present/first-eight-state checks and fatal
    # string capture are retained through this same production factory.
    cap=retained_construct(l,out,plan,check_environment,[EXE,*dependencies])
    old_hit, old_ready=cap.hit, cap.ready
    cap.profile=sequence();cap.profile_index=0;cap.setres_entry=None;cap.completed=[]
    cap.configuration_profile=read(O/'configuration-profile.json')

    def resize_geometry(self):
        obj=self.object_state();windows=[v for v in self.hwnds() if v['guest']==obj['window']]
        core.require(len(windows)==1,'ResizeViewport registered HWND identity')
        row=windows[0];u=C.WinDLL('user32',use_last_error=True)
        outer,client=T.RECT(),T.RECT()
        core.require(api(u,'GetWindowRect',[T.HWND,C.POINTER(T.RECT)])(row['native'],C.byref(outer)) and
                     api(u,'GetClientRect',[T.HWND,C.POINTER(T.RECT)])(row['native'],C.byref(client)),'ResizeViewport geometry read')
        style=api(u,'GetWindowLongW',[T.HWND,C.c_int],C.c_long)(row['native'],-16)&0xffffffff
        dpi=api(u,'GetDpiForWindow',[T.HWND],T.UINT)(row['native'])
        class GUI(C.Structure):
            _fields_=[('size',T.DWORD),('flags',T.DWORD),('windows',T.HWND*6),('caret',T.RECT)]
        info=GUI();info.size=C.sizeof(info)
        core.require(api(u,'GetGUIThreadInfo',[T.DWORD,C.c_void_p])(row['actual_thread'],C.byref(info)),'ResizeViewport GUI thread observation')
        return dict(hwnd=row,outer=[outer.left,outer.top,outer.right,outer.bottom],client=[client.left,client.top,client.right,client.bottom],
                    style=style,dpi=dpi,focus=info.windows[1],capture=info.windows[2])

    def on_create(self, ev):
        core.require(self.mem(self.base+plan['stop_rva'],len(bytes.fromhex(plan['stop_bytes'])))==bytes.fromhex(plan['stop_bytes']),'live candidate endpoint bytes')
        self.breakpoints={self.sym('d8_CreateDevice'):'bridge_entry',self.sym('xrt_fatal'):'fatal_entry'}
        save(out/'launch.json',dict(pid=ev.pid,session=l.E.I.session(ev.pid),executable=str(EXE),sha256=SHA,
             guest_stop='0x11104bf8',stop_address=self.base+plan['stop_rva'],no_retry=True,runtime_watchdog_ms=60000))
        check_environment('target-created-before-first-resume')
        self.breakpoints[self.sym('f_696e890')]='setres_entry'
        save(out/'launch-endpoint.json',dict(executable_sha256=SHA,pdb_sha256=PDB,guest_stop=GUEST,
            native_stop=self.base+plan['stop_rva'],instruction_executed=False,maximum_seconds=60,retry=False))

    def ready(self):
        states=[r for r in self.rows if r['kind']=='state_bridge_return']
        if len(states)<8:
            old_ready();return
        self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.sym('d8_render_ready'):'unexpected_profile_operation'}
        if self.profile_index<len(self.profile):
            q=self.profile[self.profile_index]
            name='f_11104f20' if q.get('kind')=='resize' else 'd8_device_'+q['method']
            self.breakpoints[self.sym(name)]='resize_entry' if q.get('kind')=='resize' else 'profile_entry'

    def profile_frame(self, q, ctx):
        cpu=self.cpu_state(self.cpu);n=q['n'];frame=self.words(self.guest_base+cpu['registers']['esp'],n+1)
        objects=self.object_state()
        renderer=self.setres_entry['cpu']['registers']['ecx']
        field_evidence=profile_gate.capture(self,renderer,self.configuration_profile,cpu,frame,objects,ctx)
        profile_gate.require_exact(field_evidence)
        core.require(ctx.get('rcx')==self.cpu,'CPU identity changed')
        core.require(cpu['pc']==q['site'] and frame[0]==q['return_pc'] and frame[1]==objects['guest'],'renderer site/return/device argument')
        core.require(objects['guest']==self.device_identity['guest'] and objects['host']==self.device_identity['host'] and objects['parent']==self.device_identity['parent'],'COM/device identity changed')
        core.require(not objects['creating'] and not objects['rendering'] and not objects['native_failed'],'device state invalid')
        pointer=None;data=b''
        if q['slot']==42:
            pointer=frame[2];data=self.guest(pointer,68)
            core.require(data==struct.pack('<17I',*[0x3f000000]*3,*[0x3f800000]*5,*[0]*9),'material bytes changed')
        elif q['slot'] in (37,18):
            core.require(frame[2]==q['a'],'transform/gamma argument')
            pointer=frame[3];data=self.guest(pointer,1536 if q['slot']==18 else 64)
            expected=(PRIOR/'actual-gamma-ramp.bin').read_bytes() if q['slot']==18 else struct.pack('<16I',*[0x3f800000 if i in (0,5,10,15) else 0 for i in range(16)])
            core.require(data==expected,'input bytes changed')
        else:
            core.require(frame[2:]==[q[k] for k in ('a','b','c')[:n-1]],'configured tuple/order changed')
        return cpu,frame,objects,pointer,data

    def hit(self, tag, ctx, tid):
        if tag=='setres_entry':
            observed=evidence.entry(self,ctx,tid)
            core.require(self.setres_entry is None,'reentered SetRes')
            self.setres_entry=observed
            self.log(tag,**self.setres_entry)
            del self.breakpoints[ctx.get('rip')];return
        if tag=='unexpected_profile_operation':
            raise RuntimeError('unexpected renderer method/order; stopped at common readiness gate before native call')
        if tag=='profile_entry':
            q=self.profile[self.profile_index]
            cs,frame,obj,pointer,data=profile_frame(self,q,ctx)
            self.active=dict(q=q,cpu=cs,frame=frame,objects=obj,input_pointer=pointer,input=data,bridge_return=self.u64(ctx.get('rsp')))
            self.log(tag,index_in_profile=self.profile_index,expected=q,cpu=cs,guest_stack=frame,objects=obj,input_bytes=data.hex(),host=ctx.snapshot())
            native=self.u64(obj['native_vtable']+q['slot']*8)
            self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',native:'profile_native_entry',self.sym('invoke_gui_proc'):'profile_callback_refused'}
            return
        if tag=='profile_callback_refused':
            self.log(tag,host=ctx.snapshot(),cpu=self.cpu_state(self.cpu))
            raise RuntimeError('unqualified callback during native renderer operation')
        if tag=='profile_native_entry':
            a=self.active;q=a['q'];host=ctx.snapshot();rsp=ctx.get('rsp')
            core.require(ctx.get('rcx')==a['objects']['host'],'native device identity')
            args=[ctx.get(r) for r in ('rdx','r8','r9')][:q['n']-1]
            if q['slot'] in (42,37,18):
                p=args[-1];core.require(self.mem(p,len(a['input']))==a['input'],'native copied input mismatch')
                core.require(p!=self.guest_base+a['input_pointer'],'native received guest pointer')
                a['native_input_pointer']=p
                if q['slot']!=42:core.require(args[0]&0xffffffff==q['a'],'native pointer method argument')
            else:core.require([v&0xffffffff for v in args]==a['frame'][2:],'native arguments changed')
            a.update(native_host=host,suspended=self.mem(self.cpu,416),native_return=self.u64(rsp))
            a['last_error_before']=self.u32(self.threads[tid][1]+0x68)
            core.require(a['last_error_before']==self.u32(self.guest_base+a['cpu']['fs_base']+0x34),'native input last-error mismatch')
            self.log(tag,index_in_profile=self.profile_index,method=q['method'],host=host,arguments=args,cpu=self.cpu_state(self.cpu),last_error=a['last_error_before'])
            self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',a['native_return']:'profile_native_return',self.sym('invoke_gui_proc'):'profile_callback_refused'}
            return
        if tag=='profile_native_return':
            a=self.active;q=a['q'];host=ctx.snapshot();void=q['slot']==18
            error=self.u32(self.threads[tid][1]+0x68)
            self.log(tag,index_in_profile=self.profile_index,method=q['method'],host=host,hresult=None if void else ctx.get('rax')&0xffffffff,
                last_error=error,raw_rax=ctx.get('rax'),cpu=self.cpu_state(self.cpu))
            core.require(self.mem(self.cpu,416)==a['suspended'],'suspended CPU changed during native call')
            core.require(self.guest(a['cpu']['registers']['esp'],4*(q['n']+1))==struct.pack('<'+'I'*len(a['frame']),*a['frame']),'native changed guest call frame')
            if a['input_pointer']:
                core.require(self.guest(a['input_pointer'],len(a['input']))==a['input'] and self.mem(a['native_input_pointer'],len(a['input']))==a['input'],'native changed input memory')
            native_abi(a['native_host'],host,void)
            core.require(void or ctx.get('rax')&0xffffffff==0,'failed actual HRESULT')
            core.require(error==a['last_error_before'],'unclassified native last-error effect')
            a['last_error']=error
            self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',a['bridge_return']:'profile_bridge_return',self.sym('invoke_gui_proc'):'profile_callback_refused'}
            return
        if tag=='profile_bridge_return':
            a=self.active;q=a['q'];cs=self.cpu_state(self.cpu)
            returned(a['cpu'],cs,a['frame'],q['n'],q['slot']==18)
            obj=self.object_state()
            core.require(obj==a['objects'],'bridge COM/device/renderer state changed')
            core.require(self.u32(self.guest_base+cs['fs_base']+0x34)==a['last_error'],'guest/native last-error discrepancy')
            self.log(tag,index_in_profile=self.profile_index,method=q['method'],cpu=cs,host=ctx.snapshot(),last_error=a['last_error'],objects=obj)
            self.completed.append(q);self.profile_index+=1;self.ready();return
        if tag=='resize_entry':
            core.require(ctx.get('rcx')==self.cpu,'ResizeViewport CPU identity')
            cs=self.cpu_state(self.cpu);frame=self.words(self.guest_base+cs['registers']['esp'],4)
            core.require(cs['pc']==0x696f48d and frame==[0x696f493,16,1540,945],'ResizeViewport flags/dimensions')
            self.resize=dict(cpu=cs,frame=frame,return_host=self.u64(ctx.get('rsp')),callbacks=[],geometry=self.resize_geometry())
            self.log(tag,cpu=cs,guest_stack=frame,host=ctx.snapshot(),geometry=self.resize['geometry'])
            self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.resize['return_host']:'resize_return',self.sym('invoke_gui_proc'):'resize_callback'};return
        if tag=='resize_callback':
            core.require(not hasattr(self,'callback_active'),'nested ResizeViewport callback')
            self.callback_active=dict(raw=self.mem(self.cpu,416),host=ctx.snapshot(),return_host=self.u64(ctx.get('rsp')))
            args=dict(hwnd=ctx.get('rcx'),message=ctx.get('rdx'),wparam=ctx.get('r8'),lparam=ctx.get('r9'))
            self.resize['callbacks'].append(args);self.log(tag,arguments=args,cpu=self.cpu_state(self.cpu),host=ctx.snapshot())
            self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.callback_active['return_host']:'resize_callback_return',self.resize['return_host']:'resize_return'};return
        if tag=='resize_callback_return':
            core.require(self.mem(self.cpu,416)==self.callback_active['raw'],'callback changed suspended CPU/FPU')
            native_abi(self.callback_active['host'],ctx.snapshot())
            self.log(tag,cpu=self.cpu_state(self.cpu),host=ctx.snapshot());del self.callback_active
            self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.resize['return_host']:'resize_return',self.sym('invoke_gui_proc'):'resize_callback'};return
        if tag=='resize_return':
            cs=self.cpu_state(self.cpu);entry=self.resize['cpu']
            core.require(cs['registers']['eax']==1 and cs['rv']==0x696f493 and cs['registers']['esp']==entry['registers']['esp']+16,'ResizeViewport failed return/ret12')
            core.require(cs['x87']==entry['x87'] and all(cs['registers'][r]==entry['registers'][r] for r in ('ebx','esi','edi','ebp')),'ResizeViewport CPU/FPU preservation')
            geometry=self.resize_geometry()
            core.require(geometry['client']==[0,0,1540,945] and geometry['style']==0x04cf0000 and geometry['dpi']==96,'ResizeViewport unqualified client/style/DPI')
            core.require(geometry['focus']==self.resize['geometry']['focus'],'ResizeViewport changed focus')
            self.log(tag,cpu=cs,host=ctx.snapshot(),last_error=self.u32(self.threads[tid][1]+0x68),geometry=geometry,callbacks=self.resize['callbacks'])
            self.completed.append(self.profile[self.profile_index]);self.profile_index+=1;self.ready();return
        if tag=='setres_completion_stop':
            cs=evidence.completed(self,ctx,tid,plan)
            core.require(self.profile_index==len(self.profile) and len(self.completed)==240,'incomplete configured sequence')
            self.log(tag,cpu=cs,host=ctx.snapshot(),guest_stack=self.words(self.guest_base+cs['registers']['esp'],12),objects=self.object_state(),instruction_executed=False)
            self.snapshot_events()
            save(out/'hard-stop.json',dict(hit=True,guest_address='0x11104bf8',native_address=ctx.get('rip'),instruction_executed=False,
                 configured_calls=238,material_calls=1,resize_returns=1,SetRes_eax=1,SetRes_argument_cleanup=20,guest_stack_delta=24))
            self.stop_requested=True;return
        old_hit(tag,ctx,tid)
        if tag=='bridge_return': self.device_identity=self.object_state()
        # The old ready() deliberately drops SetRes entry once CreateDevice starts;
        # it has already been captured. No earlier endpoint is installed here.

    def guarded_hit(self,tag,ctx,tid):
        try:
            evidence.boundary(self,tag,ctx,tid)
            return hit(self,tag,ctx,tid)
        except BaseException:
            try:self.snapshot_events()
            except BaseException as e:self.log('snapshot_failure',error=str(e))
            raise

    cap.on_create=MethodType(on_create,cap);cap.ready=MethodType(ready,cap)
    cap.update=MethodType(lambda self,ctx,resume=False:hardware(self,ctx,plan,resume),cap)
    cap.hit=MethodType(guarded_hit,cap)
    cap.resize_geometry=MethodType(resize_geometry,cap)
    return cap,l
