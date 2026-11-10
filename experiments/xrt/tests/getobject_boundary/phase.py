"""WM_GETOBJECT recovery: isolated artifacts, no game execution entry point."""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[4]
O = W / 'out/recovery/getobject-recovery-20261028-01'
B = W / 'experiments/xrt/build/getobject-recovery-20261028-01'
HERE = Path(__file__).resolve().parent
OLD = W / 'out/recovery/genuine-fatal-diagnosis-20261028-01'
PREP = W / 'out/recovery/renderer-init-preparation-20261027-01'
PY = W / '.venv/Scripts/python.exe'

def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p, v):
    with Path(p).open('x', encoding='utf-8') as f: json.dump(v, f, indent=2)
def tree(p): return {f.relative_to(p).as_posix(): sha(f) for f in sorted(p.rglob('*')) if f.is_file() and '__pycache__' not in f.parts}
def check(root, entries):
    for rel, h in entries.items(): assert sha(root / rel) == h, ('integrity', str(root), rel)
def load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def env(arch='x64'):
    vc = r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat'
    script = O / ('environment-' + arch + '.cmd')
    script.write_text(f'@echo off\ncall "{vc}" {arch} >nul || exit /b 1\nset\n')
    p = subprocess.run(['cmd', '/d', '/c', str(script)], capture_output=True, text=True, check=True)
    e = dict(line.split('=', 1) for line in p.stdout.splitlines() if '=' in line and not line.startswith('='))
    for k in list(e):
        if k.startswith(('XRT_', 'DXVK_', 'VK_')) or k in ['CL', '_CL_', 'LINK', '_LINK_']: del e[k]
    e['PYTHONDONTWRITEBYTECODE'] = '1'
    return e
def run(cmd, name, cwd=W, environment=None, timeout=60, expected=0):
    assert not any((O/(name+s)).exists() for s in ['.json','.stdout.txt','.stderr.txt']), ('preserve prior run',name)
    start = time.monotonic()
    cmd=list(map(str,cmd))
    if environment and not Path(cmd[0]).is_file():
        cmd[0]=shutil.which(cmd[0],path=environment.get('Path',environment.get('PATH')))
        assert cmd[0], 'tool missing'
    p = subprocess.run(list(map(str, cmd)), cwd=cwd, env=environment, capture_output=True, timeout=timeout)
    (O / (name + '.stdout.txt')).write_bytes(p.stdout); (O / (name + '.stderr.txt')).write_bytes(p.stderr)
    row = dict(command=list(map(str, cmd)), exit=p.returncode, seconds=time.monotonic()-start)
    save(O / (name + '.json'), row)
    assert p.returncode == expected, (name, row, p.stdout[-5000:], p.stderr[-3000:])
    assert b'C1001' not in p.stdout + p.stderr and b'D8040' not in p.stdout + p.stderr
    print(name, p.returncode, round(row['seconds'], 2), flush=True)
    return p
def preserve():
    O.mkdir(); B.mkdir()
    check(OLD, read(OLD / 'artifact-manifest.json'))
    p = read(OLD / 'preservation.json')
    check(W, p['original_evidence_sha256'])
    check(W, read(PREP / 'preserved-manifest.json'))
    check(W / 'experiments/xrt/build/renderer-init-preparation-20261027-01', read(PREP / 'build.json')['outputs'])
    sb = read(OLD / 'consumed-sandbox-manifest.json'); assert tree(Path(sb['root'])) == sb['files']
    sys.path.insert(0, str(W / 'tools/xrt')); import asset_boundary
    assert asset_boundary.verify() == p['protected_assets']
    before = {}
    for root in [W/'experiments/xrt/runtime', W/'experiments/xrt/tests', W/'tools']:
        for f in root.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts:
                rel = f.relative_to(W); before[rel.as_posix()] = sha(f)
                q = O/'source-before'/rel; q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, q); assert sha(q) == before[rel.as_posix()]
    save(O/'source-before.json', before)
    save(O/'preservation.json', dict(passed=True, consumed_evidence=p['original_evidence_sha256'], diagnosis_artifacts=read(OLD/'artifact-manifest.json'), protected_assets=p['protected_assets'], consumed_sandbox=sb, genuine_sessions=0))
    print('PRESERVATION PASS', flush=True)
def native_build():
    for arch in ['x86', 'x64']:
        d = B/arch; d.mkdir(exist_ok=True); e = env(arch)
        run(['cl','/nologo','/c','/O2','/GS-','/W4',f'/Fo{d}/',HERE/'probe.c'], arch+'-probe', environment=e)
        run(['rc','/nologo','/fo',d/'probe.res',HERE/'probe.rc'], arch+'-resource', environment=e)
        run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{d}/getobjectprobe.dll',d/'probe.obj',d/'probe.res','user32.lib','kernel32.lib'],arch+'-dll',environment=e)
        run(['cl','/nologo','/O1','/Zi','/W4',f'/Fo{d}/',f'/Fd{d}/compile.pdb',f'/Fe{d}/native.exe',HERE/'native.c','user32.lib','oleacc.lib','ole32.lib','oleaut32.lib','/link','/DEBUG'],arch+'-host',environment=e)
def translated_build():
    g=B/'gen'; d=B/'translated'; d.mkdir(exist_ok=True); e=env()
    run([PY,'-B','-I',W/'tools/xrt/xlift.py',B/'x86/getobjectprobe.dll','--out',g],'lift',timeout=60)
    rt=W/'experiments/xrt/runtime'
    names=['hle_kernel32.c','hle_misc.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    cmd=['cl','/nologo','/O1','/Zi','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{rt}',f'/Fo{d}/',f'/Fd{d}/compile.pdb',f'/Fe{d}/translated.exe',HERE/'host.c',*sorted(g.glob('*.c')),*[rt/n for n in names],HERE/'../common/xrt_test_stubs.c','winmm.lib','advapi32.lib','ole32.lib','oleacc.lib','oleaut32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000']
    run(cmd,'translated-build',environment=e,timeout=180)
def native_run():
    for arch in ['x86','x64']:
        run([B/arch/'native.exe',B/arch/'getobjectprobe.dll',O/(arch+'-unused.json')],arch+'-native',timeout=20)
def client_build():
    global O
    root=O; O=O/'client-build'; O.mkdir()
    previous=W/'experiments/xrt/build/renderer-init-preparation-20261027-01'
    old=read(PREP/'build.json');check(previous,old['outputs'])
    runtime=tree(W/'experiments/xrt/runtime');generated=tree(W/'experiments/xrt/gen')
    assert generated==old['generated']
    assert [n for n,h in runtime.items() if h!=old['sources'].get(n)]==['hle_gui.c']
    target=B/'client';target.mkdir();e=env();runs=[]
    for row in old['commands']:
        cmd=[s.replace(str(previous),str(target)) for s in row['command']]
        if row['name']=='link':
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
        else:
            dest=Path(next(s[3:] for s in cmd if s.startswith('/Fo')));dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        run(cmd,row['name'],cwd=W/'experiments/xrt',environment=e,timeout=300)
        runs.append(read(O/(row['name']+'.json')))
    assert runtime==tree(W/'experiments/xrt/runtime') and generated==tree(W/'experiments/xrt/gen')
    outputs=tree(target);assert sum(n.endswith('.obj') for n in outputs)==279
    save(root/'build.json',dict(passed=True,compiled_objects=279,reused_objects=0,commands=runs,runtime=runtime,generated=generated,
        outputs=outputs,root=str(target),binary_sha256=sha(target/'xrt_ucc.exe'),pdb_sha256=sha(target/'xrt_ucc.pdb')))
    print('FRESH CLIENT BUILD PASS',flush=True)
def gui_regressions():
    global O
    root=O;O=O/'gui-regressions';O.mkdir()
    h=W/'sandbox_getobject_regressions_20261028_01';h.mkdir()
    # All suites resolve their own root; a fresh workspace keeps historical
    # output directories and consumed markers untouched.
    for prefix in ['.venv','experiments/xrt/runtime','experiments/xrt/tests','tools']:
        shutil.copytree(W/prefix,h/prefix,ignore=shutil.ignore_patterns('__pycache__'))
    sources={prefix:tree(h/prefix) for prefix in ['experiments/xrt/runtime','experiments/xrt/tests','tools']}
    names=['gui_boundary','class_boundary','geticon_boundary','setforeground_boundary','setactive_boundary','setcapture_boundary',
        'foreground_boundary','window_ae_boundary','clipcursor_boundary','mapwindowpoints_boundary','window_ids_boundary',
        'setcursor_boundary','setfocus_boundary','immassociatecontext_boundary','adjustwindowrect_boundary','module_boundary','focus_boundary','input_boundary']
    for name in names:
        run(['cmd','/d','/c',f'experiments\\xrt\\tests\\{name}\\build.cmd'],name,cwd=h,timeout=180)
    # Reuse the established DPI96 fixture builder without its historical phase,
    # implementation, renderer or preservation entry points.
    dpi=load('wm_dpi96_regressions',h/'experiments/xrt/tests/geticon_dpi96/run.py')
    dpi.O=h/'out/recovery/getobject-dpi96';dpi.O.mkdir(parents=True)
    for stage in ['unicode','ansi']:dpi.build(stage);dpi.differential(stage)
    run([h/'.venv/Scripts/python.exe','-B','-I','-m','unittest','discover','-s','experiments/xrt/tests/getobject_boundary','-p','test_observer_evidence.py','-v'],'observer-unit',cwd=h,timeout=30)
    for prefix,entries in sources.items():check(h/prefix,entries)
    save(root/'gui-regressions.json',dict(passed=True,suites=names,dpi96=['unicode','ansi'],observer_unit_tests=7,
        harness=str(h),sources=sources,genuine_sessions=0))
def gui_complete():
    global O
    root=O;O=O/'gui-regressions-completion';O.mkdir()
    h=W/'sandbox_getobject_regressions_20261028_01'
    names=['gui_boundary','class_boundary','geticon_boundary','setforeground_boundary','setactive_boundary','setcapture_boundary',
        'foreground_boundary','window_ae_boundary','clipcursor_boundary','mapwindowpoints_boundary','window_ids_boundary',
        'setcursor_boundary','setfocus_boundary','immassociatecontext_boundary','adjustwindowrect_boundary','module_boundary','focus_boundary','input_boundary']
    assert tree(h/'experiments/xrt/runtime')==tree(W/'experiments/xrt/runtime')
    before=read(root/'source-before.json')
    check(h,{rel:v for rel,v in before.items() if rel.startswith(('tools/','experiments/xrt/tests/')) and '/getobject_boundary/' not in rel})
    for name in names:assert read(root/'gui-regressions'/(name+'.json'))['exit']==0
    sources={prefix:tree(h/prefix) for prefix in ['experiments/xrt/runtime','experiments/xrt/tests','tools']}
    dpi=load('wm_dpi96_completion',h/'experiments/xrt/tests/geticon_dpi96/run.py')
    dpi.O=h/'out/recovery/getobject-dpi96';dpi.O.mkdir(parents=True)
    for stage in ['unicode','ansi']:dpi.build(stage);dpi.differential(stage)
    run([h/'.venv/Scripts/python.exe','-B','-I','-m','unittest','discover','-s','experiments/xrt/tests/getobject_boundary','-p','test_observer_evidence.py','-v'],'observer-unit',cwd=h,timeout=30)
    for prefix,entries in sources.items():check(h/prefix,entries)
    save(root/'gui-regressions.json',dict(passed=True,suites=names,dpi96=['unicode','ansi'],dpi96_directory=str(dpi.O),observer_unit_tests=7,
        harness=str(h),sources=sources,genuine_sessions=0,initial_dpi_output_path_error_preserved=True))
if __name__ == '__main__': globals()[sys.argv[1]]()
