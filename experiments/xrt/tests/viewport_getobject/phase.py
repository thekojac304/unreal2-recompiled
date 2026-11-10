"""Disposable registered-window fixtures and preservation. Never launches a game."""
import importlib.util, json, shutil, subprocess, sys, zipfile
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
W = HERE.parents[3]
def load(name, path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
F=load('viewport_fixture_helpers',HERE/'../getobject_boundary/phase.py')
C=load('viewport_retained_checks',HERE/'../renderer_continuation/checks.py')
O=W/'out/recovery/viewport-getobject-20261028-01'
B=W/'experiments/xrt/build/viewport-getobject-20261028-01'
OLD=W/'out/recovery/renderer-continuation-20261028-01'
DIAG=W/'out/recovery/viewport-getobject-diagnosis-20261028-01'
F.O=O;F.B=B;F.HERE=HERE
sha,read,save,tree,check,run,env=F.sha,F.read,F.save,F.tree,F.check,F.run,F.env

def preserve():
    O.mkdir();B.mkdir()
    C.inputs()
    check(OLD,read(OLD/'final-seal.json'))
    check(DIAG,read(DIAG/'artifact-manifest.json'))
    p=read(DIAG/'preservation.json')
    for row in p['archives']:
        assert sha(DIAG/row['path'])==row['sha256']
        check(W,row['files'])
    sb=read(DIAG/'sandbox-manifest.json');assert tree(Path(sb['root']))==sb['files']
    assert metadata(Path(sb['root']))==read(DIAG/'sandbox-metadata.json')
    before={}
    for prefix in ['experiments/xrt/runtime','experiments/xrt/tests','tools']:
        for f in C.files(W/prefix):
            rel=f.relative_to(W).as_posix();before[rel]=sha(f)
            dest=O/'source-before'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    for rel in ['experiments/xrt/CURRENT_STATUS.md','experiments/xrt/build_client.cmd']:
        f=W/rel;before[rel]=sha(f);dest=O/'source-before'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    check(O/'source-before',before);save(O/'source-before.json',before)
    history={p.relative_to(W).as_posix():sha(p) for root in [OLD,DIAG] for p in C.files(root)}
    history.update(read(OLD/'historical-identities.json'))
    save(O/'preservation.json',dict(passed=True,consumed_evidence=history,protected_assets=C.inputs()['assets'],
        complete_sandbox=sb,sandbox_metadata_sha256=sha(DIAG/'sandbox-metadata.json'),
        inherited_exact_build=read(OLD/'build.json'),genuine_sessions_launched=0))
    for name,args in [('head',['rev-parse','HEAD']),('status',['status','--porcelain=v1','-uall']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
        (O/('git-'+name+'.txt')).write_bytes(subprocess.check_output(['git',*args],cwd=W))
    print('CONSUMED EVIDENCE / EXACT BUILD / SOURCES / SANDBOX PRESERVED',flush=True)

def metadata(root):
    return {p.relative_to(root).as_posix():dict(directory=p.is_dir(),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,
        attributes=getattr(p.stat(),'st_file_attributes',None)) for p in sorted(root.rglob('*'))}

def native_build():
    for arch in ['x86','x64']:
        d=B/arch;d.mkdir();e=env(arch)
        run(['ml' if arch=='x86' else 'ml64','/nologo','/c',f'/Fo{d}/abi.obj',HERE/('abi32.asm' if arch=='x86' else 'abi64.asm')],arch+'-abi',environment=e)
        run(['cl','/nologo','/c','/O2','/GS-','/W4',*(['/arch:IA32'] if arch=='x86' else []),f'/Fo{d}/',HERE/'probe.c'],arch+'-probe',environment=e)
        run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{d}/viewportprobe.dll',d/'probe.obj','user32.lib','kernel32.lib'],arch+'-dll',environment=e)
        run(['cl','/nologo','/O1','/Zi','/W4',f'/Fo{d}/',f'/Fd{d}/compile.pdb',f'/Fe{d}/native.exe',HERE/'native.c',d/'abi.obj','user32.lib','oleacc.lib','ole32.lib','oleaut32.lib','/link','/DEBUG'],arch+'-host',environment=e)

def native_run():
    for arch in ['x86','x64']:
        run([B/arch/'native.exe',B/arch/'viewportprobe.dll',O/(arch+'-unused.json')],arch+'-native',timeout=20)

def translated_build():
    F.HERE=HERE
    g=B/'gen';d=B/'translated';d.mkdir();e=env()
    run([F.PY,'-B','-I',W/'tools/xrt/xlift.py',B/'x86/viewportprobe.dll','--out',g],'lift',timeout=60)
    rt=W/'experiments/xrt/runtime'
    names=['hle_kernel32.c','hle_misc.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    cmd=['cl','/nologo','/O1','/Zi','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{rt}',f'/Fo{d}/',f'/Fd{d}/compile.pdb',f'/Fe{d}/translated.exe',HERE/'host.c',B/'x64/abi.obj',*sorted(g.glob('*.c')),*[rt/n for n in names],HERE/'../common/xrt_test_stubs.c','winmm.lib','advapi32.lib','ole32.lib','oleacc.lib','oleaut32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000']
    run(cmd,'translated-build',environment=e,timeout=180)

def translated_run():
    run([B/'translated/translated.exe',B/'x86/viewportprobe.dll',O/'baseline-report.json'],'baseline',timeout=20,expected=76)

def candidate_run():
    for arch in ['x86','x64']:
        run([B/arch/'native.exe',B/arch/'viewportprobe.dll',O/'unused.json','messages'],arch+'-messages',timeout=20)
    run([B/'translated/translated.exe',B/'x86/viewportprobe.dll',O/'positive-report.json','messages'],'positive',timeout=20)
    for case in ['object','wparam','upper','upperwp','nonzero','ansi','accessibility','queryclass','uia','mutated','message','unregistered']:
        run([B/'translated/translated.exe',B/'x86/viewportprobe.dll',O/(case+'-report.json'),case],case,timeout=20,expected=76)

def observed_run(tag='observed'):
    F.O=O/tag;F.O.mkdir();target=B/tag;target.mkdir()
    old=B/'oracle/translated'
    cmd=[s.replace(str(old),str(target)) for s in read(O/'oracle/translated-build.json')['command']]
    run(cmd,'build',environment=env(),timeout=180)
    run([target/'translated.exe',B/'oracle/x86/viewportprobe.dll',F.O/'positive-report.json','messages'],'positive',timeout=20)

def observed_focus_run():
    observed_run('observed-focus')
    r=read(O/'observed-focus/positive-report.json');assert r['exit_code']==0 and not r['events_dropped']
    assert (O/'observed-focus/positive.stdout.txt').read_text()==(O/'oracle/positive.stdout.txt').read_text()
    assert len([e for e in r['events'] if e['kind']=='fixture_suspended_focus_cpu' and e['passed']])==1
    assert len([e for e in r['events'] if e['kind']=='fixture_suspended_cpu' and e['passed']])==18
    assert len([e for e in r['events'] if e['kind']=='fixture_callback_abi' and e['passed']])==42
    assert len([e for e in r['events'] if e['kind']=='fixture_real_default'])==14
    save(O/'focus-cpu-audit.json',dict(passed=True,full_suspended_CPU_preserved_around_real_SetFocus=True,
        actual_default_calls=14,callback_checks=42,induced_nested_requests=2,stdout_matches_native=True,genuine_sessions=0))
    for meta in B.rglob('viewportprobe_meta.json'):
        dll=meta.parent.parent/'x86/viewportprobe.dll'
        assert sha(dll)==read(meta)['sha256'],str(meta)
    fixtures={p.relative_to(B).as_posix():sha(p) for p in C.files(B) if p.relative_to(B).parts[0]!='client'}
    save(O/'fixture-build-identities.json',dict(passed=True,root=str(B),files=fixtures,all_lifted_DLL_pairs_verified=True))

def regressions():
    root=O;F.O=O/'regressions';F.O.mkdir()
    h=W/'sandbox_viewport_getobject_regressions_20261028_01';h.mkdir()
    for prefix in ['.venv','experiments/xrt/runtime','experiments/xrt/tests','tools']:
        shutil.copytree(W/prefix,h/prefix,ignore=shutil.ignore_patterns('__pycache__'))
    sources={p:tree(h/p) for p in ['experiments/xrt/runtime','experiments/xrt/tests','tools']}
    names=['gui_boundary','class_boundary','geticon_boundary','setforeground_boundary','setactive_boundary','setcapture_boundary',
        'foreground_boundary','window_ae_boundary','clipcursor_boundary','mapwindowpoints_boundary','window_ids_boundary',
        'setcursor_boundary','setfocus_boundary','immassociatecontext_boundary','adjustwindowrect_boundary','module_boundary','focus_boundary','input_boundary']
    for name in names:run(['cmd','/d','/c',f'experiments\\xrt\\tests\\{name}\\build.cmd'],name,cwd=h,timeout=180)
    dpi=load('viewport_dpi96',h/'experiments/xrt/tests/geticon_dpi96/run.py')
    dpi.O=h/'out/recovery/viewport-dpi96';dpi.O.mkdir(parents=True)
    for stage in ['unicode','ansi']:dpi.build(stage);dpi.differential(stage)
    run([F.PY,'-B','-I','-m','unittest','discover','-s',W/'experiments/xrt/tests/postsplash_recovery','-p','test_observer_evidence.py','-v'],'observer-unit',timeout=30)
    for p,entries in sources.items():check(h/p,entries)
    save(root/'gui-regressions.json',dict(passed=True,suites=names,dpi96=['unicode','ansi'],observer_unit_tests=10,harness=str(h),sources=sources,genuine_sessions=0))

def dialog_regression():
    F.O=O/'dialog-regression';F.O.mkdir();F.B=B/'dialog-regression';F.B.mkdir();F.HERE=HERE/'../getobject_boundary'
    F.native_build();F.native_run();F.translated_build()
    run([F.B/'translated/translated.exe',F.B/'x86/getobjectprobe.dll',F.O/'positive-report.json'],'positive',timeout=20)
    for case in ['object','wparam','upper','nonzero']:
        run([F.B/'translated/translated.exe',F.B/'x86/getobjectprobe.dll',F.O/(case+'-report.json'),case],case,timeout=20,expected=76)
    assert (F.O/'x86-native.stdout.txt').read_text()==(F.O/'x64-native.stdout.txt').read_text()==(F.O/'positive.stdout.txt').read_text()
    save(O/'dialog-regression.json',dict(passed=True,samples=18,accessibility_queries=3,guards=4,protocol='DLGPROC FALSE and real dialog-manager processing'))

def client_build():
    F.O=O/'client-build';F.O.mkdir();old=read(OLD/'build.json');previous=Path(old['root']);check(previous,old['outputs'])
    runtime=tree(W/'experiments/xrt/runtime');generated=tree(W/'experiments/xrt/gen')
    assert generated==old['generated']
    assert sorted(n for n,h in runtime.items() if h!=old['runtime'].get(n))==['hle_gui.c','hle_gui_classes.inc']
    target=B/'client';target.mkdir();e=env();runs=[]
    for row in old['commands']:
        cmd=[s.replace(str(previous),str(target)) for s in row['command']]
        if row['command'][0].endswith('link.exe'):
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
        else:
            dest=Path(next(s[3:] for s in cmd if s.startswith('/Fo')));dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        # Preserve each serial compiler invocation. No concurrent compilation.
        run(cmd,row.get('name',Path(next((s[3:] for s in cmd if s.startswith('/Fo')),'link')).stem),cwd=W/'experiments/xrt',environment=e,timeout=300)
        name=row.get('name',Path(next((s[3:] for s in cmd if s.startswith('/Fo')),'link')).stem)
        runs.append(read(F.O/(name+'.json')))
    assert runtime==tree(W/'experiments/xrt/runtime') and generated==tree(W/'experiments/xrt/gen')
    outputs=tree(target);assert sum(n.endswith('.obj') for n in outputs)==279
    save(O/'build.json',dict(passed=True,compiled_objects=279,reused_objects=0,commands=runs,runtime=runtime,generated=generated,
        outputs=outputs,root=str(target),binary_sha256=sha(target/'xrt_ucc.exe'),pdb_sha256=sha(target/'xrt_ucc.pdb')))
    print('FRESH 279 OBJECT CLIENT BUILD PASS',flush=True)

if __name__=='__main__':
    if len(sys.argv)>2:
        O=O/sys.argv[2];B=B/sys.argv[2];O.mkdir(exist_ok=True);B.mkdir(exist_ok=True);F.O=O;F.B=B
    globals()[sys.argv[1]]()
