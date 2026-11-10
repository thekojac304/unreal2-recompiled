"""Focused disposable evidence; never invokes owner phases or a game."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parents[3]
RT = W / 'experiments/xrt/runtime'
OLD = HERE.parent / 'geticon_boundary'
O = W / 'out/recovery/geticon-dpi96-20261027-01'
VC = r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat'
SOURCES = ['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def execute(cmd,d,name,expected=0,env=None,cwd=None,timeout=180):
    start=time.monotonic()
    r=subprocess.run([str(x) for x in cmd],cwd=cwd or W,env=env,capture_output=True,text=True,timeout=timeout)
    (d/(name+'.stdout.txt')).write_text(r.stdout);(d/(name+'.stderr.txt')).write_text(r.stderr)
    save(d/(name+'.json'),dict(command=[str(x) for x in cmd],exit=r.returncode,seconds=time.monotonic()-start))
    print(name,r.returncode,round(time.monotonic()-start,2),flush=True)
    assert r.returncode==expected,(name,r.stdout[-3000:],r.stderr[-3000:])
    assert 'C1001' not in r.stdout and 'D8040' not in r.stdout
    return r
def script(d,name,arch,body):
    p=d/(name+'.cmd');p.write_text(f'@echo off\ncall "{VC}" {arch} >nul || exit /b 1\n'+body+'\n')
    return execute(['cmd','/d','/c',p],d,name)

def preserve():
    assert not O.exists();O.mkdir(parents=True)
    status=subprocess.check_output(['git','status','--porcelain'],cwd=W,text=True)
    (O/'initial-git-status.txt').write_text(status)
    paths=set()
    for directory in [RT,HERE.parent,W/'out/recovery/render-regression-assessment-20261027-01',W/'sandbox_render_missing_20261027_01/out/recovery/render-missing']:
        paths.update(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for line in status.splitlines():
        p=W/line[3:]
        if p.is_file():paths.add(p)
    for name in ['geticon_boundary_02','gui_boundary','class_boundary','setfocus_boundary']:
        paths.update(p for p in (W/'experiments/xrt/build'/name).rglob('*') if p.is_file())
    manifest={str(p.relative_to(W)):dict(size=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)}
    save(O/'initial-manifest.json',manifest)
    for p in paths:
        if p.suffix.lower() in ['.c','.h','.inc','.py','.md','.cmd','.asm'] and 'build' not in p.parts and 'out' not in p.parts:
            dest=O/'source-before'/p.relative_to(W);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    print('preserved',len(manifest),'existing files',flush=True)

def candidate(text):
    a='if(wp>ICON_SMALL2 || lp)'
    assert text.count(a)==1
    text=text.replace(a,'if(wp>ICON_SMALL2 || (lp && !(wp==ICON_BIG && lp==96)))')
    a='if(wp>ICON_SMALL2 || ARG(3))';assert text.count(a)==1
    text=text.replace(a,'if(wp>ICON_SMALL2 || (ARG(3) && !(wp==ICON_BIG && ARG(3)==96)))')
    a='result=wide?SendMessageW(window_host(ARG(0)),msg,wp,0):SendMessageA(window_host(ARG(0)),msg,wp,0);'
    assert text.count(a)==1
    return text.replace(a,'result=wide?SendMessageW(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3)):SendMessageA(window_host(ARG(0)),msg,wp,(LPARAM)(int32_t)ARG(3));')

DRIVER = r'''
static int failures;
static void expect(int ok){if(!ok)failures++;}
static unsigned id(DWORD v){unsigned i;if(!v)return 0;for(i=0;i<3;i++)if(v==get(icons,i))return i+1;failures++;return 99;}
int main(int argc,char**argv){
 unsigned m,n,s,i,j;DWORD seeds[]={0,0x5555,0xdeadbeef};DWORD want[]={0,0x12345678,0x23456789,0x3456789a,0x456789ab};uintptr_t h,r;
 if(argc!=5)return 2;init(argv[1],0,argv[4]);h=call(make_fn);expect(h!=0);put(window,(DWORD)h);put(selector,1);put(dpi,96);
 if(strcmp(argv[2],"positive")){
   put(mode,2);
   if(!strcmp(argv[2],"selector"))put(selector,3);
   if(!strcmp(argv[2],"small120")){put(selector,0);put(dpi,120);}
   if(!strcmp(argv[2],"small2-120")){put(selector,2);put(dpi,120);}
   if(!strcmp(argv[2],"dpi120"))put(dpi,120);
   if(!strcmp(argv[2],"dpi192"))put(dpi,192);
   if(!strcmp(argv[2],"negative-dpi"))put(dpi,0xffffffff);
   if(!strcmp(argv[2],"wrong-type"))put(mode,4);
   if(!strcmp(argv[2],"host-small120")){host_send(h,0,120);return 1;}
   if(!strcmp(argv[2],"host-dpi120")){host_send(h,1,120);return 1;}
   call(run_fn);finish();return 1;
 }
 for(m=0;m<4;m++)for(n=0;n<2;n++)for(s=0;s<3;s++){
   put(mode,m);put(nested,n);put(seed,seeds[s]);put(log_n,0);r=call(run_fn);
   for(i=0;i<5;i++)expect(get(abi,i)==want[i]);
   expect(id((DWORD)r)==(m<2?0:m-1));expect(get(error,0)==(m==3?0x6a01:seeds[s]));
   printf("send mode=%u nested=%u seed=%08lx result=%u error=%08lx abi=1\n",m,n,seeds[s],id((DWORD)r),get(error,0));
   for(j=0;j<get(log_n,0);j+=6){expect(get(log_data,j+2)==1);expect(get(log_data,j+3)==96);printf("cb %lu %lu %lu %lu %u %08lx\n",get(log_data,j),get(log_data,j+1),get(log_data,j+2),get(log_data,j+3),id(get(log_data,j+4)),get(log_data,j+5));}
   put(log_n,0);SetLastError(seeds[s]);r=host_send(h,1,96);expect(host_icon_id(r)==(m<2?0:m-1));expect(GetLastError()==(m==3?0x6a01:seeds[s]));
   printf("host mode=%u nested=%u result=%u error=%08lx suspended-abi=1\n",m,n,host_icon_id(r),GetLastError());
   for(j=0;j<get(log_n,0);j+=6){expect(get(log_data,j+2)==1);expect(get(log_data,j+3)==96);printf("cb %lu %lu %lu %lu %u %08lx\n",get(log_data,j),get(log_data,j+1),get(log_data,j+2),get(log_data,j+3),id(get(log_data,j+4)),get(log_data,j+5));}
 }
 expect(call(destroy_fn)!=0);finish();printf("failures=%d\n",failures);return failures?1:0;
}
'''
def build(stage):
    d=O/stage;assert not d.exists();d.mkdir()
    for n in ['x86','x64','gen']: (d/n).mkdir()
    src=(OLD/'geticonprobe.c').read_text().replace('(w+1)%3,0','w,l').replace('record(1,(w+1)%3,0,','record(1,w,(DWORD)l,')
    src=src.replace('depth--;return r;','if(probe_mode==3)SetLastError(0x6a00+depth);depth--;return r;')
    if stage.endswith('ansi'):src=src.replace('SendMessageW','SendMessageA')
    (d/'geticonprobe.c').write_text(src)
    (d/'driver.h').write_text(DRIVER)
    native=(OLD/'native.c').read_text().replace('#include "driver.h"',r'''
static unsigned host_icon_id(uintptr_t r){unsigned i;if(!r)return 0;for(i=0;i<3;i++)if(r==get(icons,i))return i+1;return 99;}
static uintptr_t host_send(uintptr_t h,WPARAM w,LPARAM l){return SendMessageW((HWND)h,WM_GETICON,w,l);}
#include "driver.h"
''')
    (d/'native.c').write_text(native)
    host=(OLD/'host.c').read_text().replace('#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"','#include "'+str(W/'tools/xrt/tests/ehprobe/xrt_probe_host.c').replace('\\','/')+'"')
    host=host.replace('#include "driver.h"',r'''
static unsigned host_icon_id(uintptr_t r){unsigned i;if(!r)return 0;for(i=0;i<3;i++)if(r==(uintptr_t)icon_host(get(icons,i)))return i+1;return 99;}
static uintptr_t host_send(uintptr_t h,WPARAM w,LPARAM l){
 CPU saved=*cpu;BYTE frame[16];CPU* previous=xrt_gui_callback_enter(cpu);uintptr_t result;DWORD error;
 memcpy(frame,G2H(cpu->r[ESP]),16);result=SendMessageW(window_host(h),WM_GETICON,w,l);error=GetLastError();
 xrt_gui_callback_leave(previous);
 if(memcmp(&saved,cpu,sizeof saved)||memcmp(frame,G2H(cpu->r[ESP]),16))ExitProcess(77);
 SetLastError(error);return result;
}
#include "driver.h"
''')
    (d/'host.c').write_text(host)
    if stage.endswith('ansi'):
        for p in [d/'native.c',d/'host.c']:p.write_text(p.read_text().replace('SendMessageW','SendMessageA'))
    script(d,'build-x86','x86',f'cl /nologo /c /O2 /GS- /W4 /Fo"{d}/x86/probe.obj" "{d}/geticonprobe.c" || exit /b 1\nlink /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:0x12000000 /DYNAMICBASE:NO /OUT:"{d}/geticonprobe.dll" "{d}/x86/probe.obj" user32.lib kernel32.lib || exit /b 1\ncl /nologo /O2 /W4 /Fo"{d}/x86/native.obj" /Fe"{d}/native.exe" "{d}/native.c" user32.lib gdi32.lib || exit /b 1')
    execute([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',d/'geticonprobe.dll','--out',d/'gen'],d,'lift')
    gui=RT/'hle_gui.c'
    if stage.startswith('candidate'):gui=d/'hle_gui.c';gui.write_text(candidate((RT/'hle_gui.c').read_text()))
    inputs=[d/'host.c',*(gui if n=='hle_gui.c' else RT/n for n in SOURCES),HERE.parent/'common/xrt_test_stubs.c']
    script(d,'build-x64','x64',f'cl /nologo /O1 /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"{RT}" /Fo"{d}/x64/" /Fe"{d}/translated.exe" '+ ' '.join('"'+str(p)+'"' for p in inputs)+f' "{d}/gen/*.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /STACK:0x10000000 || exit /b 1')
    save(d/'identities.json',{str(p.relative_to(W)):sha(p) for p in [*inputs,d/'geticonprobe.c',d/'driver.h',d/'geticonprobe.dll',d/'native.exe',d/'translated.exe']})

def differential(stage):
    d=O/stage;rows=[]
    for side in ['native','translated']:
        r=execute([d/(side+'.exe'),d/'geticonprobe.dll','positive','0',d/'positive-report.json'],d,side+'-positive',timeout=30)
        rows.append(r.stdout)
    assert rows[0]==rows[1] and rows[0].endswith('failures=0\n')
    ev=json.loads((d/'positive-report.json').read_text());assert ev['events_dropped']==0
    cb=[e for e in ev['events'] if e['kind']=='gui_get_icon_callback_return'];assert len(cb)==72
    assert all(e['selector']==1 and e['dpi']==96 for e in cb)
    assert any(e['icon']==0 for e in cb) and any(0xfb000000<=e['icon']<0xfb001000 for e in cb)
    for mode in ['selector','small120','small2-120','dpi120','dpi192','negative-dpi','wrong-type','host-small120','host-dpi120']:
        r=execute([d/'translated.exe',d/'geticonprobe.dll',mode,'0',d/(mode+'-report.json')],d,'negative-'+mode,expected=76,timeout=30)
        assert ('unknown class object' if mode=='wrong-type' else 'unmeasured selector/DPI') in r.stderr
    save(d/'differential.json',dict(passed=True,native_x86_translated_exact=True,sends=24,host_sends=24,callback_returns=len(cb),null_and_two_typed_icons=True,nested_depth=2,seeded_last_error=True,send_abi=True,suspended_cpu_and_frame=True,negative_cases=9))

def implement():
    assert json.loads((O/'candidate02/differential.json').read_text())['passed']
    p=RT/'hle_gui.c';before=O/'source-before'/p.relative_to(W)
    p.write_bytes(candidate(before.read_bytes().decode()).encode())
    save(O/'implementation.json',dict(before=sha(before),after=sha(p),original_line_endings_preserved=True))

def regressions():
    d=O/'regressions02';assert not d.exists();d.mkdir()
    for suite in ['geticon_boundary','gui_boundary','class_boundary','setfocus_boundary']:
        src=HERE.parent/suite;target=d/suite;relative=target.relative_to(W)
        original=(src/'build.cmd').read_text()
        build=re.sub(r'cd /d .*',f'cd /d "{W}"'.replace('\\','/'),original,count=1)
        build=re.sub(r'set OUT=.*','set OUT='+str(relative).replace('\\','/'),build,count=1)
        build=build.replace('.venv\\Scripts\\python -I "%HERE%\\compare.py"','rem comparison runs separately with isolated paths')
        p=d/(suite+'.cmd');p.write_text(build)
        execute(['cmd','/d','/c',p],d,suite+'-build')
        compare=(src/'compare.py').read_text()
        compare=re.sub(r'Path\(__file__\)\.resolve\(\)\.parents\[4\]', lambda m:'Path('+repr(W.as_posix())+')',compare)
        compare=re.sub(r"(?:ws|W)\s*/\s*'experiments/xrt/build/[^']+'",lambda m:'Path('+repr(target.as_posix())+')',compare)
        p=d/(suite+'-compare.py');p.write_text(compare)
        execute([W/'.venv/Scripts/python.exe','-B','-I',p],d,suite+'-compare',timeout=90)
    save(d/'summary.json',dict(passed=True,suites=['geticon_boundary','gui_boundary','class_boundary','setfocus_boundary']))

def wndproc():
    sys.path.insert(0,str(W/'tools/xrt'));import graphics_backend as G
    d=O/'wndproc02';assert not d.exists();d.mkdir();runs=[]
    for arch in ['x86','x64']:
        dest=d/arch;dest.mkdir()
        script(d,'build-'+arch,arch,f'cl /nologo /O2 /Zi /W4 /Fo"{dest}/wndproc.obj" /Fd"{dest}/compile.pdb" /Fe"{dest}/wndproc.exe" "{HERE}/wndproc.c" user32.lib /link /DEBUG /PDB:"{dest}/wndproc.pdb" || exit /b 1')
        for order in [0,1]:
            client=d/f'{arch}-order{order}';client.mkdir();env=os.environ.copy();G.environment(env,client)
            r=execute([dest/'wndproc.exe',G.verified_pair(arch),order],client,'run',env=env,cwd=client,timeout=45)
            rows=[json.loads(s) for s in r.stdout.splitlines() if s.startswith('{')];save(client/'observations.json',rows)
            runs.append(dict(arch=arch,window_first=bool(order),rows=rows,directory=str(client)))
    save(d/'results.json',runs)
    save(d/'identities.json',{str(p.relative_to(W)):sha(p) for p in [HERE/'wndproc.c',RT/'d3d8_abi.h',*(p for p in d.rglob('*') if p.suffix in ['.exe','.pdb','.obj'])]})

def smoke(forced=False):
    sys.path.insert(0,str(W/'tools/xrt'));import graphics_backend as G
    old=W/'sandbox_render_missing_20261027_01';fixture=old/'out/recovery/render-missing/fixture';observed=fixture/'observed'
    d=O/('render-smoke-forced' if forced else 'render-smoke');assert not d.exists();d.mkdir()
    checks={n:sha(RT/n)==sha(old/'experiments/xrt/runtime'/n) for n in SOURCES if n!='hle_gui.c'}
    assert all(checks.values()),checks
    assert (O/'source-before/experiments/xrt/runtime/hle_gui.c').read_bytes()==(old/'experiments/xrt/runtime/hle_gui.c').read_bytes()
    objects=[p for p in observed.glob('*.obj') if p.name not in (['hle_gui.obj','hle_misc.obj'] if forced else ['hle_gui.obj'])]
    extra=''
    if forced:
        device=(observed/'hle_d3d8_device.inc').read_text()
        line=next(s for s in device.splitlines() if 'test_native_leave' in s and '\\"Present\\"' in s)
        device=device.replace(line,line+'\n xrt_event("test_exact_icon_enter","\\"selector\\":1,\\"dpi\\":96");\n SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,ICON_BIG,96);\n xrt_event("test_exact_icon_leave","\\"selector\\":1,\\"dpi\\":96");')
        (d/'hle_d3d8_device.inc').write_text(device)
        for name,child in [('hle_d3d8.inc','hle_d3d8_device.inc'),('hle_misc.c','hle_d3d8.inc')]:
            text=(observed/name).read_text();text=text.replace((observed/child).as_posix(),(d/child).as_posix());(d/name).write_text(text)
        extra=f'cl /nologo /c /O1 /Zi /fp:strict /W3 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"{RT}" /Fo"{d}/hle_misc.obj" /Fd"{d}/misc-compile.pdb" "{d}/hle_misc.c" || exit /b 1\n'
        objects.append(d/'hle_misc.obj')
    save(d/'reused-inputs.json',dict(unchanged_runtime=checks,objects={str(p.relative_to(W)):sha(p) for p in objects if p.exists()},dll_sha256=sha(fixture/'x86/d3dprobe.dll'),gui_sha256=sha(RT/'hle_gui.c'),only_production_runtime_change='hle_gui.c',forced_observation=forced))
    script(d,'build','x64',extra+f'cl /nologo /c /O1 /Zi /fp:strict /W3 /D_CRT_SECURE_NO_WARNINGS /I"{RT}" /Fo"{d}/hle_gui.obj" /Fd"{d}/compile.pdb" "{RT}/hle_gui.c" || exit /b 1\ncl /nologo /Fe"{d}/translated.exe" "{d}/hle_gui.obj" '+ ' '.join('"'+str(p)+'"' for p in objects)+f' winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /DEBUG /PDB:"{d}/translated.pdb" /STACK:0x10000000 || exit /b 1')
    client=d/'client';client.mkdir();env=os.environ.copy();G.environment(env,client);env['XRT_D3D8_DIR']=str(G.verified_pair('x64'));env.pop('XRT_RENDER_CALLBACKS',None)
    r=execute([d/'translated.exe',fixture/'x86/d3dprobe.dll',client/'report.json',0,0,18,0],client,'run',env=env,cwd=client,timeout=45)
    data=json.loads((client/'report.json').read_text());assert data['events_dropped']==0
    events=data['events'];assert not any(e['kind']=='fatal' for e in events)
    icons=[e for e in events if e['kind']=='gui_get_icon_callback_return' and e['selector']==1 and e['dpi']==96];assert icons
    returns=[e for e in events if e['kind']=='d3d8_render_return'];assert [e['method'] for e in returns]==['Clear','Present']
    save(d/'summary.json',dict(passed=True,scope='one observed case-0 fixture only; no full render acceptance',actual_dpi96_callbacks=len(icons),render_methods=[e['method'] for e in returns],exit=0,strict_x87_waived=False))

def smoke_forced():smoke(True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['preserve','build','differential','implement','regressions','wndproc','smoke','smoke_forced']);a.add_argument('--stage',default='candidate');args=a.parse_args()
    globals()[args.action](args.stage) if args.action in ['build','differential'] else globals()[args.action]()
