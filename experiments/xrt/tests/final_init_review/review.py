"""Narrow final review. Never launches the candidate or submits a queue request."""
from pathlib import Path
import sys, json, uuid, runpy, shutil
H=Path(__file__).resolve().parent
W=H.parents[3]
P=H.parent/'practical_init'
sys.path.insert(0,str(P))
import common as C
from common import core,read,save
BASE=C.O
O=W/'out/recovery/final-init-review-20261030-01'

def configure():
    C.O=O
    for n in ('build.json','candidate-identity.json','stop-mapping.json','monitor-linked.json'):
        if not (O/n).exists():shutil.copy2(BASE/n,O/n)

def verify():
    seal=read(BASE/'seal.json')
    for n,d in seal['files'].items():
        core.require(core.sha(BASE/n)==d,'baseline receipt '+n)
    sources=read(BASE/'source-identity.json')
    for n,d in sources['files'].items():core.require(core.sha(Path(sources['source_root'])/n)==d,'baseline source '+n)
    b=read(BASE/'build.json');lineage=read(BASE/'object-lineage.json')
    core.require(b['binary_sha256']=='a63ed6204a5f459bfba16feff019d5aecb0b42165dabc8b9477907d2369f06d7','exact candidate')
    core.require(core.tree(Path(b['root']))==b['outputs'],'candidate build tree changed')
    core.require(core.tree(C.RT)==b['runtime'],'runtime changed')
    for rel,r in lineage.items():
        core.require(core.sha(Path(b['root'])/rel)==r['object_sha256'],'object '+rel)
        core.require(core.sha(r['source'])==r['source_sha256'],'source '+rel)
        for p,d in r.get('verified_local_headers',{}).items():core.require(core.sha(p)==d,'header '+p)
    return b,lineage

def build():
    configure();b,lineage=verify();out=O/('graphics-build-'+str(uuid.uuid4()));out.mkdir()
    helper=C.helper(out);env=helper.env();exe=out/'owned_graphics.exe'
    helper.run(['cl','/nologo','/c','/std:c11','/O2','/Zi','/fp:strict',f'/I{C.RT}',f'/Fo{out}/owned.obj',f'/Fd{out}/owned.pdb',H/'owned_graphics.c'],'owned-compile',environment=env)
    helper.run(['ml64','/nologo','/c','/Zi',f'/Fo{out}/stop.obj',H.parent/'integrated_candidate/stop_fixture.asm'],'owned-stop',environment=env)
    objs=[Path(b['root'])/r for r in lineage if r.startswith('obj/rt/') and Path(r).name!='xrt_main.obj']
    objs.append(Path(b['root'])/'obj/msvcr70/pow_sse2.obj')
    helper.run(['link','/nologo','/DEBUG','/INCREMENTAL:NO',f'/OUT:{exe}',out/'owned.obj',out/'stop.obj',*objs,'winmm.lib','advapi32.lib','ole32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/STACK:0x10000000'],'owned-link',environment=env)
    from composed_live import resolve
    names=['xrt_fatal','xm_failure','xm_pending','xm_committed','xm_recorded','xm_written','xm_buffer_count','xm_profile','xm_failed','xm_buffer','d8_CreateDevice','owned_gate','owned_stop','d8_device','xrt_g','events','event_seq']
    symbols=resolve(exe,names)
    plan=dict(owned_fixture=True,executable=str(exe),sha256=core.sha(exe),pdb_sha256=core.sha(exe.with_suffix('.pdb')),symbols=symbols,stop_rva=symbols['owned_stop']['rva'],stop_bytes='895f44',environment_gate_symbol='d8_CreateDevice')
    inputs={str(H/'owned_graphics.c'):core.sha(H/'owned_graphics.c'),str(H/'review.py'):core.sha(H/'review.py')}
    inputs.update({str(p):core.sha(p) for p in objs})
    for p in list(P.glob('*.py'))+list((W/'tools/xrt/supervisor').glob('*.py')):inputs[str(p)]=core.sha(p)
    # Bind the retained observer's transitive workspace imports too.
    from supervisor.environment import Desktop
    import types
    pending=[*list(sys.modules.values()),C.legacy(),Desktop().owner];seen=set()
    while pending:
        m=pending.pop()
        if id(m) in seen:continue
        seen.add(id(m))
        p=Path(getattr(m,'__file__','') or '')
        if p.is_absolute() and p.is_relative_to(W) and p.is_file():
            inputs[str(p)]=core.sha(p)
            pending.extend(v for v in vars(m).values() if isinstance(v,types.ModuleType))
    ident=read(BASE/'candidate-identity.json');deps=ident['dependencies']
    save(O/'physical-plan.json',dict(passed=True,plan=plan,inputs=inputs,dependencies=deps,candidate_sha256=b['binary_sha256'],runtime_objects=len(objs)-1,unexecuted_crt_object='pow_sse2.obj',generated_game_objects=0,candidate_main_linked=False,physical_executions=0,owner_run_required=True,limits=dict(seconds=60,retry=False),scope='Exact existing candidate runtime objects relinked into non-game owned host; candidate PE remains inert. Relocations/RVAs differ; actual candidate execution is not claimed.'))

def protocol():
    configure();verify()
    from composition import construct
    from supervisor.windows import FilePins
    from supervisor import fixture
    package=read(O/'physical-plan.json');plan=dict(package['plan']);plan['environment_gate_symbol']='owned_gate'
    out=O/('exact-objects-protocol-'+str(uuid.uuid4()));out.mkdir();sb=out/'sandbox';sb.mkdir();stream=sb/'trace.bin'
    cap=construct(out,plan,stream,lambda tag:None);exe=Path(plan['executable'])
    with FilePins() as pins:
        pins.pin(exe,plan['sha256']);pins.pin(exe.with_suffix('.pdb'),plan['pdb_sha256'])
        env=fixture.environment(sb);env['XRT_MONITOR_STREAM']=str(stream)
        with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
            cap.run([str(exe),'--owned-protocol'],cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=60)
    core.require(cap.cleanup['passed'] and cap.terminated_while_stopped,'exact object protocol containment')
    rows=[r for r in cap.rows if r['kind']=='composed_all_thread_readback']
    core.require(len({r['tid'] for r in rows})>=2,'exact object new thread readback')
    save(O/'exact-objects-protocol.json',dict(passed=True,root=str(out),cleanup=cap.cleanup,threads=len({r['tid'] for r in rows}),integrity=read(out/'init_return-trace/result.json'),graphics_executed=False,candidate_executed=False))

def capture_entry(cap,ctx,out,plan):
    from observer import collect_stopped
    collect_stopped(cap,out/'sandbox/trace.bin',plan['symbols'],out/'environment_gate-graphics-trace')
    raw=cap.mem(ctx.get('rcx'),416);(out/'environment_gate-cpu.bin').write_bytes(raw)
    cap.log('graphics_state_raw',tag='environment_gate',host=ctx.snapshot(),cpu=raw.hex())
    addr=int.from_bytes(raw[16:20],'little');guestbase=int.from_bytes(cap.mem(cap.sym('xrt_g'),8),'little')
    frame=cap.mem(guestbase+addr,32);(out/'creation-frame.bin').write_bytes(frame)
    words=[int.from_bytes(frame[i:i+4],'little') for i in range(0,32,4)]
    pp=cap.mem(guestbase+words[6],52);(out/'presentation.bin').write_bytes(pp)
    core.require(words[2:4]==[0,1] and words[5]==0x22,'unexpected adapter/type/behavior')
    expected=[800,600,22,1,0,1,words[4],1,1,75,0,0,0]
    core.require(pp==b''.join(v.to_bytes(4,'little') for v in expected),'presentation tuple')

def predevice():
    configure();verify()
    from composition import construct
    from supervisor.windows import FilePins
    from supervisor import fixture
    from types import MethodType
    package=read(O/'physical-plan.json');plan=package['plan']
    out=O/('predevice-'+str(uuid.uuid4()));out.mkdir();sb=out/'sandbox';sb.mkdir();stream=sb/'trace.bin'
    cap=construct(out,plan,stream,lambda tag:None);retained=cap.hit
    def hit(self,tag,ctx,tid):
        if tag!='environment_gate':return retained(tag,ctx,tid)
        capture_entry(self,ctx,out,plan)
        self.log('predevice_stop',native_CreateDevice_executed=False);self.stop_requested=True
    cap.hit=MethodType(hit,cap);exe=Path(plan['executable'])
    with FilePins() as pins:
        pins.pin(exe,plan['sha256']);pins.pin(exe.with_suffix('.pdb'),plan['pdb_sha256'])
        env=fixture.environment(sb);env['XRT_MONITOR_STREAM']=str(stream)
        with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
            cap.run([str(exe),'--owned-predevice'],cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=60)
    core.require(cap.cleanup['passed'] and cap.terminated_while_stopped,'predevice containment')
    core.require(not any('d3d8.dll' in r.get('path','').lower() or 'd3d9.dll' in r.get('path','').lower() for r in cap.rows),'predevice loaded graphics backend')
    save(O/'predevice.json',dict(passed=True,root=str(out),cleanup=cap.cleanup,actual_runtime_CreateDevice_entry_hit=True,native_device_created=False,backend_loaded=False,integrity=read(out/'environment_gate-graphics-trace/result.json')))

def environment():
    from supervisor.environment import Desktop
    out=O/('environment-'+str(uuid.uuid4()));out.mkdir()
    try:Desktop().check(out,'review');result=dict(passed=True,root=str(out),processes_launched=0)
    except BaseException as e:result=dict(passed=False,root=str(out),rejection=repr(e),processes_launched=0)
    save(O/'environment-review.json',result)
    print('Physical desktop gate '+('PASS' if result['passed'] else 'REJECTED; zero processes launched'),flush=True)
    if not result['passed']:raise SystemExit(2)

def owned_checks():
    configure();verify()
    # Legacy imports mutate module bindings. Each suite needs its own interpreter.
    out=O/('checks-'+str(uuid.uuid4()));out.mkdir();h=C.helper(out)
    for name in ('composed_live','prepare_candidate','qualify'):
        h.run([W/'.venv/Scripts/python.exe','-B','-I',H/'review.py',name],name,timeout=180)
    save(O/'owned-checks.json',dict(passed=True,receipts={n:core.sha(O/n) for n in ('composition.json','candidate-observer-preparation.json','containment.json','debugger-validation.json')},genuine_launches=0))

def physical():
    configure();verify()
    from supervisor.environment import Desktop
    from supervisor.windows import FilePins, Exclusive
    from supervisor import fixture
    from composition import construct
    from types import MethodType
    import ctypes as ct
    package=read(O/'physical-plan.json');plan=package['plan'];exe=Path(plan['executable'])
    seal=read(O/'review-seal.json')
    core.require(core.sha(O/'physical-plan.json')==seal['files']['physical-plan.json'],'sealed physical plan changed')
    out=O/('owner-graphics-'+str(uuid.uuid4()));out.mkdir();desktop=Desktop()
    # Fails on sandbox desktop before reservation or process creation.
    desktop.check(out,'owner-preflight')
    core.require(not (O/'physical-consumed.json').exists(),'physical fixture already attempted; review required, no retry')
    with FilePins() as pins:
        for p,d in {**package['inputs'],**package['dependencies'],str(exe):plan['sha256'],str(exe.with_suffix('.pdb')):plan['pdb_sha256']}.items():pins.pin(Path(p),d)
        with Exclusive(W/'out/desktop-fixtures/supervisor.lock'), C.legacy().V.R.CaseLock('level'), C.legacy().V.R.CaseLock('graphics-client-session'):
            # Requires the fixture service to be stopped; never changes it.
            sb=out/'sandbox';sb.mkdir();stream=sb/'trace.bin'
            protected=C.A.verify();save(out/'protected-before.json',protected)
            def environment(tag):return desktop.check(out,tag)
            cap=construct(out,plan,stream,environment);cap.allowed_modules=[str(exe),*package['dependencies']]
            retained=cap.hit
            def hit(self,tag,ctx,tid):
                if tag=='environment_gate':
                    capture_entry(self,ctx,out,plan)
                    return retained(tag,ctx,tid)
                if tag=='init_return':
                    from observer import collect_stopped
                    collect_stopped(self,stream,plan['symbols'],out/(tag+'-graphics-trace'))
                    raw=self.mem(ctx.get('rdi'),416)
                    (out/(tag+'-cpu.bin')).write_bytes(raw)
                    self.log('graphics_state_raw',tag=tag,host=ctx.snapshot(),cpu=raw.hex())
                    device=self.mem(self.sym('d8_device'),280);(out/'device-registry.bin').write_bytes(device)
                    token,refs=int.from_bytes(device[:4],'little'),int.from_bytes(device[4:8],'little')
                    host=int.from_bytes(device[24:32],'little')
                    core.require(token and refs==1 and host,'native device registry identity')
                    vt=int.from_bytes(self.mem(host,8),'little');(out/'native-device-vtable.bin').write_bytes(self.mem(vt,97*8))
                    lines=[json.loads(s) for s in (out/'stdout.txt').read_text().splitlines() if s.startswith('{')]
                    gpu=next(r for r in lines if r['kind']=='backend-adapter')
                    child=next(r for r in lines if r['kind']=='owned-context')
                    envraw=read(out/'before-CreateDevice-environment.json')
                    core.require(child['pid']==self.process_obj.pid and child['session']==envraw['session'] and child['station']=='WinSta0' and child['desktop']=='Default','child desktop/session mismatch')
                    luid=f"{gpu['luid_high']&0xffffffff:08x}:{gpu['luid_low']:08x}"
                    adapters={p['source']['adapter'] for p in envraw['query_display_config']['active']['paths']}
                    core.require(gpu['vendor']==0x10de and gpu['device']==0x2b85 and luid in adapters,'native backend/physical display adapter mismatch')
                    core.require(any('nvoglv64.dll' in r.get('path','').lower() for r in self.rows if r['kind']=='module_identity'),'actual NVIDIA Vulkan ICD not observed')
                return retained(tag,ctx,tid)
            cap.hit=MethodType(hit,cap)
            env=fixture.environment(sb);env['XRT_MONITOR_STREAM']=str(stream)
            deps=[Path(p) for p in package['dependencies'] if Path(p).name.lower()=='d3d8.dll']
            core.require(len(deps)==1,'one pinned backend');env['XRT_D3D8_DIR']=str(deps[0].parent)
            save(out/'command.json',dict(command=[str(exe),'--owned-graphics'],cwd=str(sb),environment=env))
            save(O/'physical-consumed.json',dict(evidence=str(out),fixture_sha256=plan['sha256'],genuine_candidate_consumed=False))
            error=None
            try:
                with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
                    cap.run([str(exe),'--owned-graphics'],cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=60)
            except BaseException as e:error=repr(e)
            finally:
                save(out/'result.json',dict(error=error,cleanup=cap.cleanup,terminated_while_stopped=getattr(cap,'terminated_while_stopped',False),candidate_executed=False,policy_activated=False,physical_qualification='PENDING_SAVED_EVIDENCE_REVIEW'))
                save(out/'protected-after.json',C.A.verify())
                core.require(C.A.verify()==protected,'protected asset change')
                desktop.check(out,'after-cleanup')
            core.require(error is None and cap.cleanup['passed'] and cap.terminated_while_stopped,'owner physical qualification failed '+str(error))
            core.require((out/'init_return-trace/result.json').exists(),'independent trace capture missing')
            print('Physical owned runtime gate captured. Saved-evidence review required; no genuine authorization.',out,flush=True)

if __name__=='__main__':
    O.mkdir(exist_ok=True)
    if sys.argv[1] in ('composed_live','prepare_candidate','qualify'):
        configure();runpy.run_path(str(P/(sys.argv[1]+'.py')),run_name='__main__')
    else:{'build':build,'protocol':protocol,'predevice':predevice,'environment':environment,'owned-checks':owned_checks,'physical':physical}[sys.argv[1]]()
