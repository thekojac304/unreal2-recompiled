"""Production fixture plus separately labelled native observation/callback hooks."""
import argparse,json,os,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run as R
W,RT,O=R.W,R.RT,R.O
def observed_source(dest):
 code=(RT/'hle_d3d8_device.inc').read_text();code=code.replace('#include <xmmintrin.h>','#include <xmmintrin.h>\n#include "'+str(HERE/'native_support.h').replace('\\','/')+'"')
 for method,size,call in [('Clear',32,'hr=o->host->vt->Clear(o->host,count,nrect,flags,color,z,stencil);error=GetLastError();after=_mm_getcsr();'),('Present',24,'hr=o->host->vt->Present(o->host,NULL,NULL,NULL,NULL);error=GetLastError();after=_mm_getcsr();')]:
  # Every observation and forced callback is outside the actual native call.
  hook='''{
 CPU saved=*c;BYTE frame[FRAME_BYTES];DWORD saved_error=GetLastError(),saved_mx=_mm_getcsr();char mode[8]={0},tag[80];static unsigned ordinal;
 memcpy(frame,G2H(esp),FRAME_BYTES);GetEnvironmentVariableA("XRT_RENDER_CALLBACKS",mode,sizeof mode);
 snprintf(tag,sizeof tag,"METHOD-before-%u",ordinal);state(o->host,(HWND)xrt_gui_device_window(c,o->window),tag);snapshot(o->host,tag,0);
 if(mode[0]=='1')SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,0,0);
 if(memcmp(&saved,c,sizeof saved)||memcmp(frame,G2H(esp),FRAME_BYTES))xrt_fatal(c,77,"test pre-native suspended CPU/frame changed");
 xrt_event("test_native_enter","\\"method\\":\\"METHOD\\",\\"this\\":%u,\\"host\\":%llu",o->guest,(unsigned long long)(uintptr_t)o->host);
 _mm_setcsr(saved_mx);SetLastError(saved_error);
 NATIVE_CALL
 xrt_event("test_native_leave","\\"method\\":\\"METHOD\\",\\"this\\":%u,\\"result\\":%lu,\\"last_error\\":%lu",o->guest,(DWORD)hr,error);
 if(mode[0]=='1')SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,0,0);
 if(memcmp(&saved,c,sizeof saved)||memcmp(frame,G2H(esp),FRAME_BYTES))xrt_fatal(c,77,"test post-native suspended CPU/frame changed");
 snprintf(tag,sizeof tag,"METHOD-after-%u",ordinal);snapshot(o->host,tag,ordinal==0);state(o->host,(HWND)xrt_gui_device_window(c,o->window),tag);
 CAPTURE
 xrt_event("test_suspended_render_cpu","\\"method\\":\\"METHOD\\",\\"all_cpu_bytes\\":true,\\"frame_bytes\\":FRAME_BYTES,\\"ordinal\\":%u",ordinal++);
 _mm_setcsr(after);SetLastError(error);
 }'''.replace('FRAME_BYTES',str(size)).replace('METHOD',method).replace('NATIVE_CALL',call).replace('CAPTURE','capture_window((HWND)xrt_gui_device_window(c,o->window),tag,ordinal==0);'if method=='Present'else'')
  assert code.count(call)==1;code=code.replace(call,hook)
 (dest/'hle_d3d8_device.inc').write_text(code)
 code=(RT/'hle_d3d8.inc').read_text().replace('#include "hle_d3d8_device.inc"','#include "'+str(dest/'hle_d3d8_device.inc').replace('\\','/')+'"');(dest/'hle_d3d8.inc').write_text(code)
 code=(RT/'hle_misc.c').read_text().replace('#include "hle_d3d8.inc"','#include "'+str(dest/'hle_d3d8.inc').replace('\\','/')+'"');p=dest/'hle_misc.c';p.write_text(code);return p
def build(out):
 assert (O/'native-audit.json').exists()
 for arch in ['x86','x64']:
  d=out/arch;asm=''
  if arch=='x86':asm=f'ml /nologo /c /Fo"{d}/guestabi.obj" "{HERE}/abi32.asm" || exit /b 1\n'
  R.script(out,'client-build-'+arch,arch,f'lib /nologo /def:"{HERE.parent}/d3d8_boundary/d3d8.def" /machine:{"X86"if arch=="x86"else"X64"} /out:"{d}/d3d8.lib" || exit /b 1\n'+asm+f'cl /nologo /c /O2 '+('/arch:IA32 'if arch=='x86'else'')+f'/GS- /W4 /Fo"{d}/probe.obj" "{HERE}/probe.c" || exit /b 1\n'+f'link /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:{"0x12000000"if arch=="x86"else"0x180000000"} /DYNAMICBASE:NO /OUT:"{d}/d3dprobe.dll" "{d}/probe.obj" '+(f'"{d}/guestabi.obj" /alternatename:__imp__Direct3DCreate8@4=__imp__Direct3DCreate8 'if arch=='x86'else'')+f'"{d}/d3d8.lib" kernel32.lib user32.lib gdi32.lib || exit /b 1\n'+f'cl /nologo /O2 /W4 /Fo"{d}/native_client.obj" /Fe"{d}/native_client.exe" "{HERE}/native_client.c" || exit /b 1')
 R.execute([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',out/'x86/d3dprobe.dll','--out',out/'gen'],out,'lift-render')
 sources=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
 for variant in ['production','observed']:
  d=out/variant;d.mkdir();misc=RT/'hle_misc.c'if variant=='production'else observed_source(d)
  inputs=[HERE/'host.c',*(RT/p if p!='hle_misc.c'else misc for p in sources),HERE.parent/'common/xrt_test_stubs.c']
  R.script(out,'translated-build-'+variant,'x64',f'cl /nologo /O1 /Zi /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"{RT}" /Fo"{d}\\\\" /Fd"{d}/compile.pdb" /Fe"{d}/translated.exe" '+' '.join('"'+str(p)+'"'for p in inputs)+f' "{out}/gen/*.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /DEBUG /PDB:"{d}/translated.pdb" /STACK:0x10000000 || exit /b 1')
 snapshot=out/'source-snapshot';snapshot.mkdir()
 files=[*RT.glob('*'),*HERE.glob('*')]
 for p in files:
  if p.is_file():d=snapshot/('runtime'if p.parent==RT else'fixture')/p.name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
 R.save(out/'sources.json',{str(p.relative_to(W)):R.sha(p)for p in files if p.is_file()})
 R.save(out/'outputs.json',{str(p.relative_to(out)):R.sha(p)for p in out.rglob('*')if p.is_file()and p.suffix in ['.obj','.exe','.dll','.pdb']})
def one(out,arch,case,arg=0,seed=18,variant='production',inject=0,expected=0):
 d=out/f'client-{arch}-{variant}-{case}-{arg}-{seed}-{inject}';assert not d.exists();d.mkdir();env=os.environ.copy();R.G.environment(env,d);env['XRT_D3D8_DIR']=str(R.G.verified_pair('x64'));env.pop('XRT_RENDER_CALLBACKS',None)
 cmd=[out/variant/'translated.exe',out/'x86/d3dprobe.dll',d/'report.json',case,arg,seed,inject]if arch=='translated'else[out/arch/'native_client.exe',R.G.verified_pair(arch)/'d3d8.dll',out/arch/'d3dprobe.dll',case,arg,seed,inject]
 start=__import__('time').monotonic();r=__import__('subprocess').run([str(v)for v in cmd],cwd=d,env=env,capture_output=True,text=True,timeout=60)
 (d/'stdout.txt').write_text(r.stdout);(d/'stderr.txt').write_text(r.stderr);rec=dict(arch=arch,case=case,arg=arg,seed=seed,variant=variant,inject=inject,exit=r.returncode,command=[str(v)for v in cmd],stdout=r.stdout,stderr=r.stderr,directory=str(d))
 if arch=='translated':
  report=json.loads((d/'report.json').read_text());ev=report['events'];assert report['events_dropped']==0 and [e['seq']for e in ev]==list(range(1,len(ev)+1));rec['events']=ev
 rec['observations']=[json.loads(s)for s in r.stdout.splitlines()if s.startswith('{')];R.save(d/'result.json',rec);print(arch,variant,case,arg,seed,inject,r.returncode,flush=True);assert r.returncode==expected,(rec,r.stderr[-3000:]);return rec
def run(out):
 runs=[]
 def add(*a,**kw):runs.append(one(out,*a,**kw));R.save(out/'translated-results.json',runs)
 for arch in ['x86','x64','translated']:
  for case in range(8):add(arch,case)
  for seed in [0,0x13572468,0xffffffff]:add(arch,0,seed=seed)
 for case in range(8):add('translated',case,variant='observed')
 add('translated',30,arg=2);add('translated',6,variant='observed',inject=1)
 for case,arg in [(20,0),(20,3),(20,8),(20,0x80000000),(21,1),(21,2),(21,0xffffffff),(22,0),(22,1),(22,0xfffffff8),(23,1),(24,1),(25,0),(26,1),(27,0),(28,0),(29,0),(31,0x80000000),(31,0x3f800000),(31,0x7fc00000),(32,1),(33,0),(33,1),(33,2),(33,3),(34,1),(30,1),(30,0x104)]:add('translated',case,arg,expected=76)
 for slot in [3,14,16,20,25,31,37,50,70,75,96]:add('translated',40,slot,expected=76)
 for case in range(50,58):add('translated',case,expected=76)
 for case in [70,71,72]:add('translated',case,variant='observed',inject=1,expected=76)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['build','run']);p.add_argument('--out',type=Path,required=True);a=p.parse_args();globals()[a.action](a.out.resolve())
