"""Void gamma, raw readback, CPU/ABI and restoration checks. No launch API."""
import struct
from recheck import core
from supervisor import fixture_profiles as F
from audit import expected_cpu


def numerical(rows,events,arch,translated,ramp):
    _,A,_=F.modules();count=16
    A.need([r['kind'] for r in rows]==['semantic-create','semantic-ownership','semantic-caps','backend-adapter','gamma-saved']+['semantic-call','semantic-readback']*count+['gamma-restored','semantic-cleanup','semantic-summary'],'complete gamma stream')
    saved=A.one(rows,'gamma-saved');restored=A.one(rows,'gamma-restored');A.need(saved['bytes']==restored['bytes'] and len(bytes.fromhex(saved['bytes']))==1536,'device gamma restoration')
    own=A.one(rows,'semantic-ownership');A.need(own==dict(kind='semantic-ownership',add=2,balance=1,parent_hr=0,same_parent=True,parent_release=2,creation_hr=0,same_window=True,flags=66),'gamma COM ownership')
    clean=A.one(rows,'semantic-cleanup');A.need(all(clean[k] is True for k in ('destroyed','unregistered','free_d3d8','free_d3d9','guest_freed')),'gamma resource cleanup');A.need(all(clean[k] in (0,False) for k in ('device_release','parent_release','window_valid','d3d8_loaded','d3d9_loaded')),'gamma final refs/modules')
    summary=A.one(rows,'semantic-summary');A.need(summary==dict(kind='semantic-summary',calls=16,translated=translated,group=8),'gamma summary')
    linear=b''.join((v*257).to_bytes(2,'little') for _ in range(3) for v in range(256));observed=[];strict=[]
    calls=rows[5:-3:2];reads=rows[6:-3:2]
    for i,(call,read) in enumerate(zip(calls,reads)):
        index,seed_index=divmod(i,4);kind,flag=divmod(index,2);seed=[0,18,0x13572468,0xffffffff][seed_index]
        A.need(call['index']==index and call['slot']==18 and call['a']==flag and call['input_kind']==kind and call['seed']==seed and call['hr'] is None and not call['rejected'],'gamma void/sample identity')
        A.need(call['error']==seed,'gamma last-error preservation')
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
            strict.append(dict(index=index,seed=seed,finding='native_MXCSR_status',before=a,after=b,verdict='FAILED',pre=call['pre'],post=call['post']))
        expected=(linear if kind else ramp).hex();A.need(call['input']==read['bytes']==expected and read['hr'] is None,'gamma exact copied input/readback; no invented HRESULT')
        if translated:A.need(call['cpu']==call['expected_cpu']==expected_cpu(call),'gamma EAX/CPU/RET12 preservation')
        observed.append(dict(index=index,flag=flag,input_kind=kind,seed=seed,error=call['error'],hr=None,readback=read['bytes']))
    phases=[e['payload'] for e in events if e['event']=='d3d8_checkpoint']
    if translated:
        A.need(len(phases)==64 and [e['phase'] for e in phases]==[0,1,2,3]*16,'gamma paired checkpoints')
        for i in range(16):A.need(all(e['slot']==18 for e in phases[i*4:i*4+4]) and phases[i*4+2]['error']==phases[i*4+3]['error']==calls[i]['error'],'gamma actual last-error transfer')
    else:A.need(not events,'native gamma runtime events')
    return dict(passed=True,observations=observed,strict_differences=strict,cleanup=clean,scope='windowed backend gamma readback; no visible/fullscreen effect inferred')


def capture(directory,item,build,ramp):
    E,A,_=F.modules();pair=E.P.G.verified_pair(item['arch'])
    rows,snapshot,events=A.process(directory,physical=True,expected_exe=item['exe'],expected_args=['--physical',pair,'--gamma-physical'],expected_build=build,expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
    gpu=A.adapter(rows,snapshot,directory,item['arch']);A.need(gpu['adapter']['vendor']==0x10de,'physical NVIDIA')
    result=numerical(rows,events,item['arch'],item['variant']=='translated',ramp);result['gpu']=gpu
    return result
