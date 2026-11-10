"""Independent saved-evidence audit. No process creation or queue API."""
from pathlib import Path
import sys,json,ctypes as C,hashlib,zlib,struct
H=Path(__file__).resolve().parent;W=H.parents[3]
P=H.parent/'practical_init';F=W/'out/recovery/final-init-review-20261030-01'
O=W/'out/recovery/experimental-init-policy-review-20261030-01'
sys.path.insert(0,str(P))
from common import core,read,save,RT,A
from reader import Record,decode,require

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def manifest(root):return {str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file()}
def one(items,message):
    require(len(items)==1,message);return items[0]
def saved_capture(q):
    size=C.sizeof(Record);c=read(q/'counters.json')
    for n,bytes_ in [('xm_committed',8),('xm_recorded',8),('xm_written',8),('xm_buffer_count',4),('xm_profile',4),('xm_failed',4)]:
        raw=(q/(n+'.bin')).read_bytes();require(len(raw)==bytes_,'counter byte count');require(int.from_bytes(raw,'little')==c[n],'counter JSON/raw mismatch')
    durable,recorded,written,count=[c[n] for n in ('xm_committed','xm_recorded','xm_written','xm_buffer_count')]
    require(0<=durable<=written<=recorded<=131072 and recorded-durable==count<=4096,'counter/tail bounds')
    disk=(q/'stream.bin').read_bytes();tail=(q/'tail.bin').read_bytes();pending=(q/'pending.bin').read_bytes()
    require(len(tail)==count*size and durable*size<=len(disk)<=recorded*size,'disk/tail byte bounds')
    combined=disk[:durable*size]+tail
    require(combined==(q/'recovered.bin').read_bytes(),'reconstruction mismatch')
    require(disk==combined[:len(disk)],'disk/memory disagreement')
    p=Record.from_buffer_copy(pending);require(len(pending)==size and p.crc==zlib.crc32(pending[:Record.crc.offset]),'pending checksum')
    require(p.sequence==recorded and pending==combined[-size:],'unaccounted pending record')
    rows,valid=decode(q/'recovered.bin',closed=False,committed=recorded)
    require(c['xm_failed']==0 and c['xm_profile']==1,'failed or wrong profile')
    return rows,dict(counters=c,integrity=valid,record_size=size,durable_prefix=durable,unflushed_tail=count)

def audit():
    sealed=read(F/'review-seal.json')
    # Owner action legitimately replaces the latest environment observation.
    # Preserve the original seal and record this one documented operational delta.
    deltas={n:dict(sealed=d,current=digest(F/n)) for n,d in sealed['files'].items() if digest(F/n)!=d}
    require(set(deltas)<= {'environment-review.json'},'unexpected sealed preparation change')
    for n,d in sealed['sources'].items():require(digest(H.parent/'final_init_review'/n)==d,'sealed preparation source changed')
    package=read(F/'physical-plan.json');plan=package['plan']
    for p,d in {**package['inputs'],**package['dependencies'],plan['executable']:plan['sha256'],str(Path(plan['executable']).with_suffix('.pdb')):plan['pdb_sha256']}.items():require(digest(p)==d,'physical input identity '+p)
    # Reuse the independent candidate/object/source verifier without invoking a suite.
    sys.path.insert(0,str(H.parent/'final_init_review'));import review as prepared
    prepared.verify()
    consumed=read(F/'physical-consumed.json');q=Path(consumed['evidence']);require(q.parent==F and consumed['fixture_sha256']==plan['sha256'] and not consumed['genuine_candidate_consumed'],'physical binding')
    before=manifest(q)
    rows=[json.loads(s) for s in (q/'debug-observations.jsonl').read_text().splitlines()]
    require([r['index'] for r in rows]==list(range(1,len(rows)+1)),'debug log gap/reorder')
    require(all(a['monotonic']<=b['monotonic'] for a,b in zip(rows,rows[1:])),'debug timestamp order')
    launch=one([r for r in rows if r['kind']=='launch'],'one launch')
    created=one([r for r in rows if r['kind']=='process_created'],'one process')
    require(launch['command']==[plan['executable'],'--owned-graphics'] and launch['timeout_seconds']==60 and Path(launch['cwd'])==q/'sandbox','fixed command/timeout/sandbox')
    require(launch['pid']==created['pid'],'process mismatch')
    assignment=one([r for r in rows if r['kind']=='job_assigned_before_continue'],'Job before continue')
    require(assignment['index']<created['index'],'Job ordering')
    from supervisor.environment import Desktop,gate
    desktop=Desktop();fingerprints=[]
    for tag in ('owner-preflight','target-created-before-first-resume','before-CreateDevice','after-cleanup'):
        fingerprints.append(gate(read(q/(tag+'-environment.json')),desktop.expected,desktop.owner))
    require(all(x==fingerprints[0] for x in fingerprints),'environment drift')
    child=one([json.loads(s) for s in (q/'stdout.txt').read_text().splitlines() if 'owned-context' in s],'child context')
    require(child['pid']==launch['pid'] and child['session']==fingerprints[0]['session'] and child['station']=='WinSta0' and child['desktop']=='Default','child/owner desktop identity')
    expected=[created['base']+plan['symbols'][n]['rva'] for n in ('xrt_fatal','xm_failure')]+[created['base']+plan['stop_rva'],created['base']+plan['symbols']['d8_CreateDevice']['rva']]
    rb=[r for r in rows if r['kind']=='composed_all_thread_readback']
    require(len(set(expected))==4 and rb,'four critical stops')
    for r in rb:require(r['addresses']==expected and r['dr']==expected and r['dr7']&0xffff00ff==0x55,'critical DR readback mismatch')
    # Every CREATE_PROCESS/CREATE_THREAD must be followed by a readback for its TID.
    events=[r for r in rows if r['kind']=='debug_event'];thread_events=[r for r in events if r['code'] in (2,3)]
    for ev in thread_events:
        next_ev=next((r['index'] for r in events if r['index']>ev['index']),len(rows)+1)
        require(any(ev['index']<r['index']<next_ev and r['tid']==ev['tid'] for r in rb),'new thread continued without readback')
    early,early_result=saved_capture(q/'environment_gate-graphics-trace')
    final,final_result=saved_capture(q/'init_return-trace')
    second,second_result=saved_capture(q/'init_return-graphics-trace')
    require((q/'init_return-trace/recovered.bin').read_bytes()==(q/'init_return-graphics-trace/recovered.bin').read_bytes()==(q/'sandbox/trace.bin').read_bytes(),'endpoint disk/capture mismatch')
    require(early_result['unflushed_tail']>0 and final_result['unflushed_tail']==0 and final_result['integrity']['active_invocations']==0,'tail preservation/full endpoint flush')
    require(bytes(early[-1])==bytes(final[len(early)-1]),'early snapshot not final prefix')
    call=one([r for r in final if r.name==b'D8Interface.CreateDevice' and r.event==2],'one native CreateDevice')
    ret=one([r for r in final if r.name==b'D8Interface.CreateDevice' and r.event==3],'one native return')
    require(ret.result==0 and call.host==ret.host and call.invocation==ret.invocation,'native result/parent identity')
    for name in ('GetDeviceCaps','GetAdapterDisplayMode','CheckDeviceType','CheckDeviceMultiSampleType','CheckDepthStencilMatch'):
        require(any(r.name==('D8Interface.'+name).encode() and r.event==3 and r.result==0 for r in final),'live graphics preflight missing '+name)
    blobs=lambda name:one([bytes(r.blob[:r.blob_size]) for r in final if r.name==name and r.blob_size],'typed native output')
    native_device=int.from_bytes(blobs(b'D8Interface.CreateDevice.output6'),'little')
    reg=(q/'device-registry.bin').read_bytes();require(len(reg)==280 and int.from_bytes(reg[24:32],'little')==native_device and native_device,'native device registry join')
    device_created=one([r for r in final if r.event==7 and r.name==b'created' and r.interface_id==2],'device creation lifetime')
    require(device_created.host==native_device and device_created.guest==int.from_bytes(reg[:4],'little') and device_created.refs==1,'guest/native lifetime identity')
    frame=struct.unpack('<8I',(q/'creation-frame.bin').read_bytes());pp=struct.unpack('<13I',(q/'presentation.bin').read_bytes())
    require(frame[2:4]==(0,1) and frame[5]==0x22 and pp==(800,600,22,1,0,1,frame[4],1,1,75,0,0,0),'physical tuple mismatch')
    cp=blobs(b'D8Device.GetCreationParameters.output1');adapter,type_,focus,flags=struct.unpack('<IIQI',cp[:20])
    require((adapter,type_,flags)==(0,1,0x22) and focus,'native creation parameters')
    stdout=[json.loads(s) for s in (q/'stdout.txt').read_text().splitlines()]
    guest_cp=one([r for r in stdout if r['kind']=='owned-creation-readback'],'guest creation readback')
    require(guest_cp==dict(kind='owned-creation-readback',adapter=0,type=1,focus=frame[4],flags=0x22,device=device_created.guest,parent=frame[1]),'guest/native parameters/identity')
    gpu=one([r for r in stdout if r['kind']=='backend-adapter'],'backend identity')
    require((gpu['vendor'],gpu['device'])==(0x10de,0x2b85),'physical GPU identity')
    luid=f"{gpu['luid_high']&0xffffffff:08x}:{gpu['luid_low']:08x}"
    require(luid in {p['source']['adapter'] for p in read(q/'before-CreateDevice-environment.json')['query_display_config']['active']['paths']},'backend LUID/display join')
    modules=[r for r in rows if r['kind']=='module_identity']
    for r in modules:require(digest(r['path'])==r['sha256'],'observed module hash drift '+r['path'])
    for p,d in package['dependencies'].items():
        if Path(p).name.lower() in ('d3d8.dll','d3d9.dll'):require(any(Path(r['path'])==Path(p) and r['sha256']==d for r in modules),'pinned backend not mapped')
    require(any(Path(r['path']).name.lower()=='nvoglv64.dll' and r['system_dependency'] for r in modules),'NVIDIA Vulkan ICD missing')
    mappings=[]
    for j,r in enumerate(rows):
        if r['kind']=='module_loaded':
            ident=rows[j+1];require(ident['kind']=='module_identity','module base/path pairing')
            import pefile
            with pefile.PE(ident['path'],fast_load=True) as pe:mappings.append((r['base'],r['base']+pe.OPTIONAL_HEADER.SizeOfImage,ident['path']))
    vtable=struct.unpack('<97Q',(q/'native-device-vtable.bin').read_bytes())
    require(all(any(lo<=p<hi and Path(name).name.lower()=='d3d8.dll' for lo,hi,name in mappings) for p in vtable),'native vtable target outside pinned D3D8 image')
    init=[r for r in final if r.name==b'UGameEngine.Init'];require(len(init)==2 and [r.event for r in init]==[2,3] and init[0].invocation==init[1].invocation and init[0].thread==init[1].thread,'owned Init pairing')
    endpoint=one([r for r in rows if r['kind']=='composed_stopped_host' and r['tag']=='init_return'],'endpoint stopped host')
    registers=endpoint['host']['registers'];require(registers['rip']==created['base']+plan['stop_rva'] and registers['rbx']&0xffffffff==0x1090ed5c,'endpoint host identity')
    cpu=(q/'init_return-cpu.bin').read_bytes();require(int.from_bytes(cpu[64:68],'little')==0x1090ed5c and cpu[68:72]==b'\0'*4,'endpoint return/store-before-instruction')
    term=one([r for r in rows if r['kind']=='terminated_before_continue'],'one termination before continue');require(term['index']>endpoint['index'] and term['tid']==endpoint['tid'],'termination ordering')
    result=read(q/'result.json');require(result['error'] is None and result['terminated_while_stopped'] and result['cleanup']['passed'] and result['cleanup']['remaining_job_processes']==0 and not result['cleanup']['watchdog'] and result['cleanup']['kill_on_close'],'contained physical result')
    require(result['cleanup']['seconds']<=60 and not result['candidate_executed'] and not result['policy_activated'],'scope/timeout')
    require(read(q/'protected-before.json')==read(q/'protected-after.json')==A.verify(),'protected assets')
    # Report CPU/FPU/error observations, never compare after deleting/rewriting bits.
    native_state=dict(entry_fcw=int.from_bytes(bytes(call.context.fx[:2]),'little'),return_fcw=int.from_bytes(bytes(ret.context.fx[:2]),'little'),
        entry_fsw=int.from_bytes(bytes(call.context.fx[2:4]),'little'),return_fsw=int.from_bytes(bytes(ret.context.fx[2:4]),'little'),
        entry_mxcsr=int.from_bytes(bytes(call.context.fx[24:28]),'little'),return_mxcsr=int.from_bytes(bytes(ret.context.fx[24:28]),'little'),
        actual_last_error=ret.error,actual_hresult=ret.result,guest_adapter_return_error=one([r for r in final if r.name==b'D8.CreateDevice' and r.event==3],'adapter return').guest_error)
    require(before==manifest(q),'physical evidence changed during audit')
    return dict(passed=True,evidence=str(q),input_manifest=before,preparation_seal_sha256=digest(F/'review-seal.json'),legitimate_seal_deltas=deltas,
        candidate_sha256=package['candidate_sha256'],owned_fixture_sha256=plan['sha256'],physical_gpu='NVIDIA RTX 5090',adapter_luid=luid,
        process_seconds=result['cleanup']['seconds'],records=len(final),record_size=C.sizeof(Record),tail_capacity_bytes=4096*C.sizeof(Record),
        native_calls=sum(r.event==2 and r.domain==2 for r in final),native_returns=sum(r.event==3 and r.domain==2 for r in final),
        readbacks=len(rb),threads=len({r['tid'] for r in rb}),early_snapshot=early_result,endpoint_snapshot=final_result,native_state=native_state,
        limits=['Exact candidate runtime objects relinked into owned host; no candidate main or game module executed.','One 800x600 windowed HAL tuple; not the genuine Init path or arbitrary configurations.','No Present/texture/DirectInput call occurred in this prerequisite; retained differences remain unresolved.','Probe FPU snapshots are not exact volatile state at every native instruction.','Terminated with a live native device; no normal COM release or window cleanup inferred.'],
        strict_compatibility='FAILED_RETAINED',genuine_launches=0,production_policy_changed=False)

if __name__=='__main__':
    O.mkdir(exist_ok=True);result=audit();save(O/'physical-audit.json',result)
    print(json.dumps({k:result[k] for k in ('passed','records','native_calls','readbacks','threads','native_state')},indent=2))
