"""Independent fail-closed completeness and numerical checks; never launches a child.

No fixture pass boolean substitutes for raw ABI, process, ownership or OS evidence.
"""
from pathlib import Path
import struct, subprocess, sys
import prepare_evidence as E
from module_identity import verify_snapshot
P=E.P
class Incomplete(ValueError):pass
def need(v,why):
    if not v:raise Incomplete(why)
def read(p):return P.core.read_large(p)
def rows(p):return [P.core.loads(line) for line in p.read_bytes().splitlines()]
def machine(path):
    with Path(path).open('rb') as f:
        h=f.read(64);need(h[:2]==b'MZ','PE DOS header');f.seek(struct.unpack_from('<I',h,60)[0]);h=f.read(6)
    need(h[:4]==b'PE\0\0','PE header');return struct.unpack_from('<H',h,4)[0]
def subsystem(path):
    with Path(path).open('rb') as f:
        h=f.read(64);f.seek(struct.unpack_from('<I',h,60)[0]+24+68);return struct.unpack('<H',f.read(2))[0]
def one(rs,kind):
    found=[r for r in rs if r.get('kind')==kind];need(len(found)==1,'missing/duplicate '+kind);return found[0]

def environment(s,*,physical):
    for k in ['pid','collector_pid','filetime','creation_filetime','image','image_sha256','owner_sid','user','domain','window_station','desktop']:
        need(s[k], 'missing environment '+k)
    need(s['owner_sid'].startswith('S-1-'),'owner SID')
    if physical:
        need(s['session']==s['collector_session']==s['active_console'] and s['session']!=0,'active console/session mismatch')
        need(s['protocol']==0 and s['connect_state']==0 and s['remote'] is False,'physical console not active')
        need(s['window_station'].lower()=='winsta0' and s['desktop'].lower()==s['input_desktop'].lower()=='default','input desktop/window station')
        need(s['station_flags_ok'] and s['station_flags']&1,'window station not visible')
        need(s['display_status']==0 and s['paths'] and s['dxgi_hr']==0 and s['adapters'] and s['display_devices'],'missing display/GPU topology')
        for p in s['paths']:
            need(p['source_status']==p['target_status']==0 and p['gdi_name'] and p['monitor_path'] and p['width']>0 and p['height']>0 and p['refresh_d']>0,'incomplete display path')

def abi(call,arch):
    need(call['regs']==([0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else
        [0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]),'raw GPR preservation')
    xmm=bytes.fromhex(call['xmm']);need(len(xmm)==160,'missing XMM observation')
    if arch=='x64':need(xmm==struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10,'raw XMM6..15 preservation')
    else:need(xmm==bytes(160),'x86 has no ABI nonvolatile XMM registers')
    pre,post=[bytes.fromhex(call[k]) for k in ['pre','post']]
    need(len(pre)==len(post)==512,'FXSAVE length')
    need(pre[:2]==b'\x7f\x02' and pre[24:28]==struct.pack('<I',0x3f80),'x87/MXCSR seed')
    for a,b in [(0,5),(24,28),(32,42),(48,58)]:need(pre[a:b]==post[a:b],'raw x87/MXCSR preservation')
    need(call.get('stack_delta',call.get('delta'))==0,'native stack preservation')

def process(d,*,physical,expected_exe,expected_args,expected_build=None,expected_backend=None):
    r=read(d/'process.json');ex=read(d/'exit.json');need(r['schema']==2 and r['physical']==physical and not r['forced_cleanup'],'process capture mode/forced cleanup')
    cmd=[str(expected_exe.resolve()),*map(str,expected_args)]
    need(r['command']==cmd and r['command_line']==subprocess.list2cmdline(cmd) and Path(r['cwd'])==d.resolve(),'exact command/cwd binding')
    need(r['executable_sha256']==P.core.sha(expected_exe),'executable hash')
    if expected_build:
        need(Path(r['build_record'])==expected_build and r['build_record_sha256']==P.core.sha(expected_build),'build identity')
        build=read(expected_build);need(build['fp']=='/fp:strict' and build['inputs'] and build['outputs'],'source/build record')
        for path,digest in {**build['inputs'],**build['outputs']}.items():need(P.core.sha(Path(path))==digest,'source/build drift '+path)
        need(build['toolchain'],'compiler/linker identity missing')
        for path,digest in build['toolchain'].items():need(P.core.sha(Path(path))==digest,'compiler/linker identity changed')
        need(build['outputs'][str(expected_exe)]==r['executable_sha256'],'build executable binding')
        need(build['arch'] in ['x86','x64'] and machine(expected_exe)==(0x14c if build['arch']=='x86' else 0x8664),'build architecture')
        need(subsystem(expected_exe)==2,'fixture must not create an implicit console host')
    backend={str(p):P.core.sha(p) for p in (expected_backend or [])};need(r['backend']==backend,'backend identity')
    before,after=read(d/'owner-before.json'),read(d/'owner-after.json')
    for s in [before,after]:
        verify_snapshot(s)
        environment(s,physical=physical);need(s['pid']==r['owner_pid'] and s['owner_sid']==r['owner_sid'],'owner session identity')
    need(before['filetime']<=r['start_filetime']<r['finish_filetime']<=after['filetime'],'capture time bounds')
    need(before['module_identity']['finish_filetime']<=r['start_filetime'],'owner module observation outside preflight')
    suspended=read(d/'suspended.json');environment(suspended,physical=physical)
    verify_snapshot(suspended,pre_resume=True)
    need(ex['pid']==suspended['pid']==r['pid'] and ex['creation_filetime']==suspended['creation_filetime'],'PID reuse/creation identity')
    need(ex['wait']==ex['exit']==ex['active_processes']==ex['terminated_processes']==0 and ex['total_processes']==1,'process-tree exit/cleanup')
    need(ex['job_query_ok'] and ex['assigned_before_resume'] and ex['kill_on_close'],'job containment')
    need(r['start_filetime']<=ex['creation_filetime']<ex['exit_filetime']<=ex['observed_filetime']<=r['finish_filetime'],'actual process lifecycle times')
    snapshots=[]
    for phase in ['loaded','cleaned']:
        s=read(d/(phase+'-environment.json'));self=read(d/(phase+'-self.json'));environment(s,physical=physical)
        need(s['pid']==self['pid']==r['pid'] and s['creation_filetime']==ex['creation_filetime'],'child snapshot identity')
        need(s['owner_sid']==r['owner_sid'] and s['collector_pid']==r['owner_pid'],'child owner/collector binding')
        need(s['image_sha256']==r['executable_sha256'] and Path(s['image']).resolve()==expected_exe.resolve(),'actual process image')
        need(self['phase']==phase and self['tid']>0 and self['session']==s['session']==before['session'],'child session receipt')
        for k in ['window_station','desktop','input_desktop']:need(self[k]==s[k]==before[k]==after[k],'child desktop binding '+k)
        need(s['paths']==before['paths']==after['paths'] and s['adapters']==before['adapters']==after['adapters'],'display topology/adapter changed')
        need(ex['creation_filetime']<=self['filetime']<=s['filetime']<ex['exit_filetime'],'contemporaneous checkpoint')
        need(s['module_identity']['finish_filetime']<ex['exit_filetime'],'module observation outside child lifetime')
        verify_snapshot(s)
        need(s['modules_complete'] and s['modules'],'module enumeration incomplete')
        for m in s['modules']:need(m['path'] and m['sha256']==P.core.sha(Path(m['path'])) and m['machine']==machine(m['path']),'loaded module identity')
        snapshots.append(s)
    need(snapshots[0]['filetime']<read(d/'cleaned-self.json')['filetime'],'checkpoint order')
    for phase in ['suspended','loaded','cleaned']:
        job=read(d/(phase+'-job.json'))
        need(job['complete'] and job['assigned']==job['total_processes']==1 and job['pids']==[r['pid']],'job process membership '+phase)
        need(ex['creation_filetime']<=job['filetime']<ex['exit_filetime'],'job membership time')
        need(job['processes']==[dict(pid=r['pid'],query_ok=True,image=suspended['image'],creation_filetime=ex['creation_filetime'])],'job image identity '+phase)
    for path,digest in backend.items():
        loaded=[m for m in snapshots[0]['modules'] if Path(m['path']).resolve()==Path(path).resolve()]
        need(len(loaded)==1 and loaded[0]['sha256']==digest,'backend not observed loaded')
        need(not any(Path(m['path']).resolve()==Path(path).resolve() for m in snapshots[1]['modules']),'backend not unloaded')
    stream=rows(d/'runtime-events.jsonl');receipt=read(d/'cleaned-self.json')['runtime_stream']
    need(receipt==dict(attempted=len(stream),written=len(stream),write_errors=0,transport='synchronous-file',dropped_event_count=None),'runtime write receipt (no invented drop count)')
    for i,event in enumerate(stream,1):
        need(event['sequence']==i and event['pid']==r['pid'] and event['tid']==read(d/'loaded-self.json')['tid'],'runtime event sequence/PID')
        need(snapshots[0]['filetime']<=event['filetime']<=read(d/'cleaned-self.json')['filetime'],'runtime event time')
    need((d/'stderr.txt').read_bytes()==b'','fixture stderr')
    return rows(d/'stdout.txt'),snapshots[0],stream

def adapter(rs,s,d,arch):
    luid=one(rs,'backend-adapter');need(luid['hr']==0 and luid['ordinal']==0 and luid['query_parent_release']==0,'backend adapter LUID query')
    adapters=[a for a in s['adapters'] if (a['luid_low'],a['luid_high'])==(luid['luid_low'],luid['luid_high'])]
    need(len(adapters)==1 and adapters[0]['flags']&2==0,'unique physical adapter LUID')
    a=adapters[0];need(a['vendor'] in [0x10de,0x1002,0x8086] and a['device']>0,'physical PCI adapter')
    need(any((p['source_luid_low'],p['source_luid_high'])==(a['luid_low'],a['luid_high']) for p in s['paths']),'selected GPU not in active display topology')
    vendor={0x10de:'nvidia',0x1002:'advanced micro devices',0x8086:'intel'}[a['vendor']]
    drivers=[m for m in s['modules'] if vendor in m['company'].lower() and m['version_ok'] and m['version_ms'] and Path(m['path']).suffix.lower()=='.dll']
    need(drivers,'no loaded physical GPU driver binary identity')
    # Require the actual Vulkan ICD, rather than a vendor overlay/helper module.
    icds=[m for m in drivers if any(n in Path(m['path']).name.lower() for n in ['nvoglv','nv-vk','amdvlk','amd-vulkan','vulkan','igvk'])]
    need(icds and all(m['machine']==(0x14c if arch=='x86' else 0x8664) for m in icds),'no loaded vendor Vulkan ICD of expected architecture')
    logs=list(d.glob('*_d3d9.log'));need(len(logs)==1,'backend log missing')
    log=logs[0].read_text();need('DXVK: v3.1.1' in log and 'Creating device:' in log and a['name']+':' in log,'backend selected GPU/log binding')
    need(not any(x.startswith(('err:','warn:')) for x in log.splitlines()),'backend log error/warning')
    return dict(adapter=a,driver_modules=icds,backend_log_sha256=P.core.sha(logs[0]))

def group(d,group,arch,translated):
    name=P.GROUPS[group];exe=E.O/'build'/f'{name}-{arch}-{"translated" if translated else "native"}'/'fixture.exe';pair=P.G.verified_pair(arch)
    build=read(exe.parent/'build-record.json')
    need(build['group']==group and build['arch']==arch and build['translated']==translated and build['original_snapshot_sha256']==P.core.sha(P.O/'snapshots'/name/'snapshot.json'),'group source/build scope')
    rs,s,events=process(d,physical=True,expected_exe=exe,expected_args=['--physical',pair],expected_build=exe.parent/'build-record.json',expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
    info=adapter(rs,s,d,arch);ident=one(rs,'adapter-identity')
    need(ident['hr']==ident['caps_hr']==0 and len(ident['caps'])==53,'actual native caps')
    # DXVK 3.1.1 intentionally reports SubSysId=Revision=0. Physical PCI values
    # come from DXGI, not these emulated D3D fields. LUID is the primary join.
    need(all(ident[k]==info['adapter'][k] for k in ['vendor','device']),'D3D8/physical adapter identity')
    observations=group_observations(rs,group,arch,translated,events)
    return observations,dict(group=group,name=name,variant=exe.parent.name,calls=len(observations),physical_evidence_complete=True,production_accepted=False,**info)

def group_observations(rs,group,arch,translated,events):
    own=one(rs,'ownership');need(own==dict(kind='ownership',add=2,balance=1,parent_hr=0,same_parent=True,parent_release=2,creation_hr=0,same_window=True,flags=66),'COM identity/reference counts')
    need(one(rs,'release')==dict(kind='release',device_release=0,parent_release=0),'final COM references')
    need(one(rs,'lifecycle')==dict(kind='lifecycle',destroyed=True,unregistered=True,window_valid=False,free_d3d8=True,free_d3d9=True,d3d8_loaded=False,d3d9_loaded=False),'window/module lifecycle')
    need(one(rs,'create')==dict(kind='create',hr=0,nonnull=True),'CreateDevice')
    profiles=[c for c in read(P.O/'cases.json')['cases'] if c['group']==group]
    expected=[(c,seed) for c in profiles for seed in [18,0,0x13572468,0xffffffff] for _ in range(2)]
    need(one(rs,'summary')==dict(kind='summary',passed=True,calls=len(expected),graphics=True,translated=translated),'group summary')
    kinds=['create','ownership','adapter-identity','backend-adapter']+['call','readback']*len(expected)+['release','lifecycle','summary']
    need([r['kind'] for r in rs]==kinds,'complete ordered fixture stream')
    observations=[]
    for i,(case,seed) in enumerate(expected):
        c,b=rs[4+2*i:6+2*i];abi(c,arch)
        need(all(c[k]==case[k] for k in ['group','site','config','slot','a','b','c']) and c['seed']==c['error']==seed and c['hr']==0 and c['fpu_preserved'] is True,'call result/profile/last error')
        need(b['slot']==case['slot'] and b['hr']==0 and b['equal'] is True,'typed readback')
        if case['slot'] in [50,63,76]:need(b['value']==(case['b'] if case['slot']==50 else case['c'] if case['slot']==63 else 2),'readback value')
        if case['slot'] in [83,85]:need(b['extra']==0,'readback stride/base')
        observations.append(tuple(c[k] for k in ['group','site','config','slot','a','b','c','seed','error','hr'])+(b['slot'],b['hr'],b['equal'],b['value'],b['extra']))
    ev_expected=[(kind,c['site'],c['slot']) for c,_ in expected for kind in ['adapter-enter','adapter-leave']] if translated else []
    need([(e['event'],e['payload']['site'],e['payload']['slot']) for e in events]==ev_expected,'instrumented runtime boundary event completeness')
    need(len(D.audit(rs,group))==len(expected),'original unchanged assertions')
    return observations

def preflight(d,arch):
    exe=E.O/'build'/('preflight-'+arch)/'fixture.exe';pair=P.G.verified_pair(arch)
    build=read(exe.parent/'build-record.json');need(build['group']==0 and build['arch']==arch and build['translated'] is False,'preflight build scope')
    rs,s,events=process(d,physical=True,expected_exe=exe,expected_args=[pair,148,1,18,0],expected_build=exe.parent/'build-record.json',expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
    adapter(rs,s,d,arch);need(not events,'preflight runtime events')
    need(rs[0]['kind']=='create' and rs[0]['hr']==0 and rs[0]['device'],'native tuple CreateDevice')
    need([r['kind'] for r in rs]==['create','backend-adapter','state']+['call','state']*4+['identity','cleanup'],'preflight observation completeness')
    states=[r for r in rs if r['kind']=='state'];need([s['ordinal'] for s in states]==list(range(5)),'state snapshots')
    for i,c in enumerate(r for r in rs if r['kind']=='call'):
        abi(c,arch);need(c['ordinal']==i and c['hr']==0 and c['last_error']==18,'preflight call')
        need(states[i+1]['values'][148]==[0,1] and all(states[i]['values'][k]==states[i+1]['values'][k] for k in range(256) if k!=148),'state 148 isolation')
    need(one(rs,'identity')==dict(kind='identity',parent_hr=0,same_parent=True,add=2,balance=1,parent_release=2,creation_hr=0,same_window=True,flags=66),'preflight ownership')
    need(rs[-1]==dict(kind='cleanup',device_release=0,parent_release=0,window_valid=False,d3d8_loaded=False,d3d9_loaded=False,callbacks=0,foreign_callbacks=0),'preflight cleanup')
    return dict(arch=arch,passed=True)

def batch(root):
    reports=[];expected={'preflight-x86','preflight-x64'}
    pre=[preflight(root/('preflight-'+a),a) for a in ['x86','x64']]
    for g in range(1,8):
        observed=[]
        for arch,translated in [('x86',False),('x64',False),('x64',True)]:
            name=f'{P.GROUPS[g]}-{arch}-{"translated" if translated else "native"}';expected.add(name)
            observations,report=group(root/name,g,arch,translated);observed.append(observations);reports.append(report)
        need(observed[0]==observed[1]==observed[2],'functional differential discrepancy')
    need({d.name for d in root.iterdir() if d.is_dir()}==expected and len(expected)==23,'batch process scope')
    strict=read(P.O/'strict-failures.json')
    need(strict['x87']==strict['wndproc_equality']==strict['strict_native_x86_compatibility']=='FAILED','historical strict assertions')
    need(P.core.sha(Path(strict['historical_source']))==strict['historical_source_sha256'],'strict source identity')
    return dict(schema=2,functional_differential='PASSED',physical_evidence_completeness='PASSED',groups=reports,preflights=pre,
        process_count=23,group_calls=sum(r['calls'] for r in reports),group_readbacks=sum(r['calls'] for r in reports),
        production_accepted=False,production_assessment='HELD_EXISTING_QUALIFICATION_GATES',
        strict_x87='FAILED',strict_wndproc='FAILED',strict_native_x86='FAILED',
        remaining=['Actual renderer configuration/caps must be bound to a production profile; these seven groups use sealed measurement samples.',
                   'Real ResizeViewport/Win32 callback equality, genuine material/SetRes/outer initialization and rendered presentation remain unqualified.',
                   'Runtime stream is instrumented fixture service telemetry; full production runtime event-loss instrumentation is outside this batch.'],genuine_launches=0)

# Keep the original parser as an additional check, never as the completeness oracle.
import desktop_batch as D
