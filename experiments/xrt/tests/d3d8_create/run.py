"""Fresh serial builds and one native attempt per disposable process."""
import argparse,json,os,sys,subprocess,time,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3];RT=W/'experiments/xrt/runtime'
sys.path.insert(0,str(W/'tools/xrt'))
import graphics_backend as G
from asset_boundary import sha
VC=r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat'
def save(p,v):p.write_text(json.dumps(v,indent=2))
def execute(cmd,out,name,env=None,timeout=180):
    start=time.monotonic();r=subprocess.run([str(x)for x in cmd],cwd=W,env=env,capture_output=True,text=True,timeout=timeout)
    (out/(name+'.stdout.txt')).write_text(r.stdout);(out/(name+'.stderr.txt')).write_text(r.stderr)
    save(out/(name+'.json'),dict(command=[str(x)for x in cmd],exit=r.returncode,seconds=time.monotonic()-start))
    print(name,r.returncode,(' '.join(r.stdout.split())[:160] if r.returncode==0 else r.stderr.splitlines()[1:2]),flush=True);return r
def script(out,name,arch,body):
    p=out/(name+'.cmd');p.write_text(f'@echo off\ncall "{VC}" {arch} >nul || exit /b 1\n'+body+'\n')
    r=execute(['cmd','/d','/c',p],out,name);assert r.returncode==0,(name,r.stdout,r.stderr)
def build(out):
    assert not out.exists();out.mkdir(parents=True)
    for arch in ['x86','x64']:
        d=out/arch;d.mkdir();asm=''
        if arch=='x86':
            asm=f'ml /nologo /c /Fo"{d}/abi.obj" "{HERE}/abi32.asm" || exit /b 1\n'
        script(out,'build-'+arch,arch,
            f'lib /nologo /def:"{HERE.parent}/d3d8_boundary/d3d8.def" /machine:{"X86"if arch=="x86"else"X64"} /out:"{d}/d3d8.lib" || exit /b 1\n'+asm+
            f'cl /nologo /c /O2 '+('/arch:IA32 'if arch=='x86'else'')+f'/GS- /W4 /Fo"{d}/probe.obj" "{HERE}/probe.c" || exit /b 1\n'+
            f'link /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:{"0x12000000"if arch=="x86"else"0x180000000"} /DYNAMICBASE:NO /OUT:"{d}/d3dprobe.dll" "{d}/probe.obj" '+(f'"{d}/abi.obj" /alternatename:__imp__Direct3DCreate8@4=__imp__Direct3DCreate8 'if arch=='x86'else'')+
            f'"{d}/d3d8.lib" kernel32.lib user32.lib gdi32.lib || exit /b 1\n'+
            f'cl /nologo /O2 /W4 /Fo"{d}/native.obj" /Fe"{d}/native.exe" "{HERE}/native.c" || exit /b 1')
        script(out,'build-abi-'+arch,arch,
            f'{"ml"if arch=="x86"else"ml64"} /nologo /c /Fo"{d}/native_abi_asm.obj" "{HERE.parent}/d3d8_device/abi{"32"if arch=="x86"else"64"}.asm" || exit /b 1\n'+
            f'cl /nologo /O2 /W4 /Fo"{d}/native_abi.obj" /Fe"{d}/native_abi.exe" "{HERE}/native_abi.c" "{d}/native_abi_asm.obj" user32.lib kernel32.lib || exit /b 1')
    assert execute([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',out/'x86/d3dprobe.dll','--out',out/'gen'],out,'lift').returncode==0
    sources=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    base='cl /nologo /O1 /Zi /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW '+f'/I"{RT}" '
    for variant in ['production','injected']:
        dest=out/variant;dest.mkdir();misc=RT/'hle_misc.c'
        if variant=='injected':
            # Only this separate executable has fault/callback injection. The
            # real backend still supplies HRESULT, output, mutations and error.
            code=(RT/'hle_d3d8_device.inc').read_text()
            code=code.replace('if(SUCCEEDED(hr)) {\n        if(q!=o->host', '''{char mode[16]={0};GetEnvironmentVariableA("XRT_CREATE_TEST",mode,sizeof mode);
            if(mode[0]=='5' && SUCCEEDED(hr)) {iid.Data1^=1;xrt_event("test_unmodelled_qi","\\"real_acquired_reference\\":true");}}
    if(SUCCEEDED(hr)) {
        if(q!=o->host''')
            code=code.replace('if(q!=o->parent->host)', '''if(q!=o->parent->host || GetEnvironmentVariableA("XRT_CREATE_TEST_PARENT",NULL,0))''')
            code=code.replace('mxcsr_before=_mm_getcsr();','''{
            char mode[16]={0};GetEnvironmentVariableA("XRT_CREATE_TEST",mode,sizeof mode);
            if(mode[0]=='1') {
                CPU saved=*c;BYTE frame[32];memcpy(frame,G2H(c->r[ESP]),32);
                _mm_setcsr(0x3f80);SendMessageW(focus_host,WM_GETICON,0,0);
                if(memcmp(&saved,c,sizeof saved) || memcmp(frame,G2H(c->r[ESP]),32))xrt_fatal(c,77,"test callback corrupted suspended CPU/frame");
                xrt_event("test_suspended_cpu","\\"all_registers_x87_flags\\":true,\\"frame_bytes\\":32,\\"device_unpublished\\":true");
                SetLastError(xrt_get_last_error(c));
            }
            if(mode[0]=='4') {_mm_setcsr(0x3f80);SetLastError(xrt_get_last_error(c));}
            if(mode[0]=='2') {n.depthformat=71;xrt_event("test_backend_injection","\\"depth\\":71,\\"real_backend\\":true");SetLastError(xrt_get_last_error(c));}
            }
            mxcsr_before=_mm_getcsr();''')
            code=code.replace('xrt_gui_callback_leave(previous);\n    }','''{
            char mode[16]={0};GetEnvironmentVariableA("XRT_CREATE_TEST",mode,sizeof mode);
            if(mode[0]=='1') {
                CPU saved=*c;BYTE frame[32];memcpy(frame,G2H(c->r[ESP]),32);
                SendMessageW(focus_host,WM_GETICON,0,0);
                if(memcmp(&saved,c,sizeof saved) || memcmp(frame,G2H(c->r[ESP]),32))xrt_fatal(c,77,"test post-create callback corrupted suspended CPU/frame");
                xrt_event("test_suspended_cpu_after_native","\\"all_registers_x87_flags\\":true,\\"frame_bytes\\":32,\\"device_unpublished\\":true,\\"native_output_ready\\":true");
            }
            if(mode[0]=='3') {
                n.width=101;n.height=102;n.format=103;n.count=104;n.multisample=105;n.swap=106;n.window=NULL;
                n.windowed=108;n.depth=109;n.depthformat=110;n.flags=111;n.refresh=112;n.interval=113;
                xrt_event("test_mutation_injection","\\"all_fields\\":true");
            }
            }
            xrt_gui_callback_leave(previous);
    }''')
            (dest/'hle_d3d8_device.inc').write_text(code)
            code=(RT/'hle_d3d8.inc').read_text().replace('#include "hle_d3d8_device.inc"','#include "'+str(dest/'hle_d3d8_device.inc').replace('\\','/')+'"')
            (dest/'hle_d3d8.inc').write_text(code)
            code=(RT/'hle_misc.c').read_text().replace('#include "hle_d3d8.inc"','#include "'+str(dest/'hle_d3d8.inc').replace('\\','/')+'"')
            misc=dest/'hle_misc.c';misc.write_text(code)
        inputs=[HERE/'host.c',*(RT/s if s!='hle_misc.c'else misc for s in sources),HERE.parent/'common/xrt_test_stubs.c']
        script(out,'build-'+variant,'x64',base+f'/Fo"{dest}\\\\" /Fd"{dest}/compile.pdb" /Fe"{dest}/translated.exe" '+
            ' '.join('"'+str(p)+'"'for p in inputs)+f' "{out}/gen/*.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /DEBUG /PDB:"{dest}/translated.pdb" /STACK:0x10000000 || exit /b 1')
    snapshot=out/'source-snapshot';snapshot.mkdir()
    files=[*RT.glob('*'),*HERE.glob('*')]
    for p in files:
        if p.is_file():
            dest=snapshot/('runtime'if p.parent==RT else'fixture')/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
    save(out/'sources.json',{str(p.relative_to(W)):sha(p)for p in files if p.is_file()})
    save(out/'outputs.json',{str(p.relative_to(out)):sha(p)for p in out.rglob('*')if p.is_file()and p.suffix in ['.obj','.pdb','.exe','.dll']})
def one(out,arch,case,arg=0,seed=18,inject=0,variant='production',tag=''):
    name=f'{arch}-{variant}-{case}-{arg}-{seed}-{inject}{tag}';d=out/name;assert not d.exists();d.mkdir()
    env=os.environ.copy();G.environment(env,d);env['XRT_D3D8_DIR']=str(G.verified_pair('x64'));env.pop('XRT_CREATE_TEST',None)
    if inject==6:env['XRT_CREATE_TEST_PARENT']='1'
    else:env.pop('XRT_CREATE_TEST_PARENT',None)
    if arch=='translated':cmd=[out/variant/'translated.exe',out/'x86/d3dprobe.dll',d/'report.json',case,arg,seed,inject]
    else:cmd=[out/arch/'native.exe',G.verified_pair(arch)/'d3d8.dll',out/arch/'d3dprobe.dll',case,arg,seed,inject]
    r=execute(cmd,d,'run',env,60)
    rec=dict(arch=arch,case=case,arg=arg,seed=seed,inject=inject,variant=variant,exit=r.returncode,stdout=r.stdout,stderr=r.stderr,directory=str(d))
    if arch=='translated':
        report=json.loads((d/'report.json').read_text());ev=report['events'];rec['events']=ev
        assert report['events_dropped']==0 and [e['seq']for e in ev]==list(range(1,len(ev)+1))
    save(d/'result.json',rec);return rec
def run(out):
    runs=[]
    for arch in ['x86','x64','translated']:
        for case in [0,1,2,3,4,5,6,9]:
            runs.append(one(out,arch,case));assert runs[-1]['exit']==0
        for seed in [0,0x13572468,0xffffffff]:
            runs.append(one(out,arch,0,seed=seed));assert runs[-1]['exit']==0
    for case in [7,8,10,11,21,22,23,24,31,35]:
        runs.append(one(out,'translated',case));assert runs[-1]['exit']==76
    for arg in [0,1,0xffffffff,0xffffffd0]:
        for case in [25,26]:runs.append(one(out,'translated',case,arg));assert runs[-1]['exit']==76
    for arg in [1,2,0x104]:
        for case in [27,29]:runs.append(one(out,'translated',case,arg));assert runs[-1]['exit']==76
    for case in [32,33,34]:
        for arg in [1,0xffffffff]:runs.append(one(out,'translated',case,arg));assert runs[-1]['exit']==76
    for arg in [*range(6),*range(7,16)]:
        runs.append(one(out,'translated',20,arg));assert runs[-1]['exit']==76
    for case,inject in [(6,1),(13,1),(12,1),(0,2),(0,3),(6,4),(0,5),(0,6)]:
        runs.append(one(out,'translated',case,inject=inject,variant='injected'));assert runs[-1]['exit']==(76 if case==12 or inject in [2,5,6] else 0)
    save(out/'results.json',dict(runs=runs))
    abi=[]
    for arch in ['x86','x64']:
        for depth in [77,71]:
            d=out/f'native-abi-{arch}-{depth}';d.mkdir();env=os.environ.copy();G.environment(env,d)
            r=execute([out/arch/'native_abi.exe',G.verified_pair(arch),depth],d,'run',env,60);assert r.returncode==0
            abi.append(dict(arch=arch,depth=depth,data=json.loads(r.stdout),directory=str(d)))
    save(out/'native-abi.json',abi)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();globals()[a.action](a.out.resolve())
