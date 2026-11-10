"""Durable debugger evidence before argument, identity, HRESULT or ABI checks."""
import struct
from common import *
CALLERS={0x11104bf8:('initial',0x11104bf5),0x696d2cd:('lock-recovery',0x696d2ca)}


def boundary(cap,tag,ctx,tid):
    host=ctx.snapshot()
    cap.log('raw_boundary_host',tag=tag,thread=tid,host=host)
    try:
        cpu=ctx.get('rcx') if tag=='setres_entry' else cap.cpu
        cap.log('raw_boundary_host_stack',tag=tag,address=ctx.get('rsp'),raw=cap.mem(ctx.get('rsp'),64).hex())
        if not cpu:return
        raw=cap.mem(cpu,416);cap.log('raw_boundary_cpu',tag=tag,address=cpu,raw=raw.hex())
        cs=cap.cpu_state(cpu);base=cap.u64(cap.sym('xrt_g'));esp=cs['registers']['esp']
        cap.log('raw_boundary_frame',tag=tag,address=esp,raw=cap.mem(base+esp,24).hex())
        high,low=cap.words(base+cs['fs_base']+4,2)
        count=min(64,(high-esp)//4) if low<=esp<high else 6
        cap.log('raw_boundary_stack',tag=tag,cpu=cs,address=esp,raw=cap.mem(base+esp,4*count).hex(),
                bounds=dict(low=low,high=high),captured_words=count)
        if tag!='setres_entry' and getattr(cap,'guest_base',None):
            cap.log('raw_com_identity',tag=tag,objects=cap.object_state(),hwnds=cap.hwnds())
        if tag in ('profile_native_entry','profile_native_return') and hasattr(cap,'active'):
            a=cap.active;q=a['q'];p=None;n=0
            if tag=='profile_native_entry' and q['slot'] in (18,37,42):
                args=[ctx.get(r) for r in ('rdx','r8','r9')][:q['n']-1];p=args[-1];n=1536 if q['slot']==18 else 64 if q['slot']==37 else 68
            elif a.get('native_input_pointer'):p=a['native_input_pointer'];n=len(a['input'])
            if p:cap.log('raw_native_input',tag=tag,address=p,raw=cap.mem(p,n).hex())
        if tid in cap.threads:
            cap.log('raw_last_error',tag=tag,native=cap.u32(cap.threads[tid][1]+0x68),guest=cap.u32(base+cs['fs_base']+0x34))
    except BaseException as e:
        cap.log('raw_boundary_read_failure',tag=tag,error=repr(e));raise


def entry(cap,ctx,tid):
    cap.cpu=ctx.get('rcx');cap.guest_base=cap.u64(cap.sym('xrt_g'))
    cs=cap.cpu_state(cap.cpu);esp=cs['registers']['esp'];raw=cap.mem(cap.guest_base+esp,24)
    frame=list(struct.unpack('<6I',raw));renderer=cs['registers']['ecx']
    classification,site=CALLERS.get(frame[0],('unknown',None))
    result=dict(cpu=cs,cpu_raw=cap.mem(cap.cpu,416).hex(),frame=frame,frame_raw=raw.hex(),host=ctx.snapshot(),thread=tid,
                classification=classification,expected_site=site,renderer=renderer,viewport=frame[1])
    cap.log('setres_entry_raw',**result)
    # Collect object bytes before checking identity or argument expectations.
    renderer_raw=cap.mem(cap.guest_base+renderer,0x4700).hex()
    cap.log('setres_renderer_raw',address=renderer,raw=renderer_raw)
    viewport_raw=cap.mem(cap.guest_base+frame[1],0x184).hex()
    cap.log('setres_viewport_raw',address=frame[1],raw=viewport_raw)
    sources=dict(renderer_raw=renderer_raw,viewport_raw=viewport_raw,
        viewport_renderer=cap.u32(cap.guest_base+frame[1]+0x5c),viewport_size=cap.words(cap.guest_base+frame[1]+0x74,2),
        renderer_fullscreen=cap.u32(cap.guest_base+renderer+0x70),renderer_device=cap.u32(cap.guest_base+renderer+0x4698))
    result['sources']=sources;cap.log('setres_identity_raw',**sources)
    checks=dict(initial_caller=classification=='initial',caller_site=cs['pc']==site,viewport_nonzero=bool(frame[1]),
                renderer_nonzero=bool(renderer),viewport_renderer=sources['viewport_renderer']==renderer,
                width=frame[2]==1540,height=frame[3]==945,fullscreen=frame[4]==0,color_bits=frame[5]==32,
                no_existing_device=sources['renderer_device']==0)
    cap.log('setres_entry_checks',classification=classification,checks=checks)
    core.require(all(checks.values()),'initial SetRes entry: '+', '.join(k for k,v in checks.items() if not v))
    return result


def completed(cap,ctx,tid,plan):
    cs=cap.cpu_state(cap.cpu);e=cap.setres_entry
    cap.log('initial_setres_return_raw',cpu=cs,cpu_raw=cap.mem(cap.cpu,416).hex(),host=ctx.snapshot(),thread=tid,
            original_frame=cap.mem(cap.guest_base+e['cpu']['registers']['esp'],24).hex(),objects=cap.object_state())
    r=plan['stop_registers'];checks=dict(host_pc=ctx.get('rip')==cap.base+plan['stop_rva'],cpu_identity=ctx.get(r['cpu'])==cap.cpu,
         expected_return_register=ctx.get(r['return_value'])&0xffffffff==GUEST,
         initial_caller=e['classification']=='initial' and e['frame'][0]==GUEST and e['cpu']['pc']==0x11104bf5,
         same_thread=tid==e['thread'],return_value=cs['registers']['eax']==1,
         return_pc=cs['rv']==GUEST and cs['pc']==0x696f4e9,
         esp24=cs['registers']['esp']==e['cpu']['registers']['esp']+24,
         nonvolatile=all(cs['registers'][k]==e['cpu']['registers'][k] for k in ('ebx','esi','edi','ebp')),
         viewport_renderer=cap.u32(cap.guest_base+e['viewport']+0x5c)==e['renderer'],
         renderer_device=cap.u32(cap.guest_base+e['renderer']+0x4698)==cap.object_state()['guest'])
    cap.log('initial_setres_return_checks',checks=checks)
    core.require(all(checks.values()),'initial SetRes return: '+', '.join(k for k,v in checks.items() if not v))
    return cs


def runtime_pair(events,entry_record,return_record):
    bounds=[e for e in events if e['kind']=='setres_boundary']
    core.require(len(bounds)==2 and [e['phase'] for e in bounds]==['entry','return'],'one paired initial SetRes runtime invocation')
    a,b=bounds
    core.require(a['id']==b['id'] and a['site']==b['site']==0x11104bf5 and a['return']==b['return']==GUEST and
                 a['target']==b['target']==0x696e890,'runtime invocation/caller identity')
    for phase,record in [('entry',entry_record),('return',return_record)]:
        chunks=[e for e in events if e['kind']=='setres_raw' and e['phase']==phase and e['area']=='cpu' and e['id']==a['id']]
        core.require([e['offset'] for e in chunks]==[0,128,256,384] and all(e['size']==416 for e in chunks),'complete runtime CPU chunks')
        core.require(''.join(e['hex'] for e in chunks)==record['cpu_raw'],'runtime/debugger raw CPU differs')
    frames=[e for e in events if e['kind']=='setres_raw' and e['phase']=='entry' and e['area']=='frame']
    core.require(len(frames)==1 and frames[0]['hex']==entry_record['frame_raw'],'runtime/debugger raw frame differs')
    core.require(b['esp']==a['esp']+24 and b['eax']==1 and b['rv']==GUEST,'runtime SetRes return outcome')
