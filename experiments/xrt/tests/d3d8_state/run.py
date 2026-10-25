"""Fresh serial native and production/observed translated state fixtures."""
import argparse,importlib.util,json,os,shutil,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3];RT=W/'experiments/xrt/runtime'
sys.path.insert(0,str(HERE.parent/'d3d8_render'));import run as R
def native_build(out):
 assert not out.exists();out.mkdir(parents=True)
 for arch in ['x86','x64']:
  R.G.verified_pair(arch);d=out/arch;d.mkdir();s=(HERE.parent/'d3d8_device'/('abi32.asm'if arch=='x86'else'abi64.asm')).read_text().replace('device_abi','state_abi').replace('cwseed WORD 077fh','cwseed WORD 027fh')
  start=s.index('    push DWORD PTR [eax+28]'if arch=='x86'else'    mov rcx,[r10+8]');end=s.index('    mov edx,[esp+516]'if arch=='x86'else'    mov r10,[rsp+72]',start)
  call='    push DWORD PTR [eax+12]\n    push DWORD PTR [eax+8]\n    push DWORD PTR [eax+4]\n    call DWORD PTR [eax]\n'if arch=='x86'else'    mov rcx,[r10+8]\n    mov edx,[r10+16]\n    mov r8d,[r10+20]\n    call QWORD PTR [r10]\n'
  (d/'abi.asm').write_text(s[:start]+call+s[end:]);R.script(out,'native-build-'+arch,arch,f'{"ml"if arch=="x86"else"ml64"} /nologo /c /Fo"{d}/abi.obj" "{d}/abi.asm" || exit /b 1\n'+f'cl /nologo /O2 /W4 /Zi /Fo"{d}/native.obj" /Fd"{d}/compile.pdb" /Fe"{d}/native.exe" "{HERE}/native.c" "{d}/abi.obj" user32.lib /link /DEBUG /PDB:"{d}/native.pdb" || exit /b 1')
def native_run(out,state,value):
 rows=[]
 for arch in ['x86','x64']:
  for st,val,prime,seed in [(state,value,0,18),(state,value,1,18),(state,value,0,0),(state,value,0,0x13572468),(state,value,0,0xffffffff),(state,value^1,0,18),(state,0xffffffff,0,18),(0,1,0,18),(255,1,0,18)]:
   d=out/f'native-{arch}-{st}-{val}-{prime}-{seed}';d.mkdir();env=os.environ.copy();R.G.environment(env,d);r=R.execute([out/arch/'native.exe',R.G.verified_pair(arch),st,val,seed,prime],d,'run',env,60,d);rows.append(dict(arch=arch,state=st,value=val,prime=prime,seed=seed,rows=[json.loads(x)for x in r.stdout.splitlines()if x.startswith('{')]));R.save(out/'native-results.json',rows)
def observed_source(d,state,value):
 code=(RT/'hle_d3d8_device.inc').read_text();call='hr=o->host->vt->SetRenderState(o->host,state,value);error=GetLastError();after=_mm_getcsr();'
 hook='''{
 CPU saved=*c;BYTE frame[16];DWORD saved_error=GetLastError(),saved_mx=_mm_getcsr(),v;unsigned i;static unsigned ordinal;HRESULT sh;typedef HRESULT(WINAPI*GetFn)(D8Device*,DWORD,DWORD*);GetFn get=(GetFn)(*(void***)o->host)[51];char mode[8]={0};
 memcpy(frame,G2H(esp),16);GetEnvironmentVariableA("XRT_STATE_CALLBACKS",mode,sizeof mode);
 if(!ordinal){sh=o->host->vt->SetRenderState(o->host,state,value^1);printf("{\\"kind\\":\\"prime\\",\\"hr\\":%lu,\\"value\\":%u}\\n",(DWORD)sh,value^1);}
 printf("{\\"kind\\":\\"state\\",\\"ordinal\\":%u,\\"values\\":[",ordinal);for(i=0;i<256;i++){v=0xa5a5a5a5;sh=get(o->host,i,&v);printf("%s[%lu,%lu]",i?",":"",(DWORD)sh,v);}puts("]}");
 if(mode[0]=='1')SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,0,0);
 if(memcmp(&saved,c,sizeof saved)||memcmp(frame,G2H(esp),16))xrt_fatal(c,77,"test pre-native CPU/frame changed");
 xrt_event("test_native_enter","\\"method\\":\\"SetRenderState\\",\\"ordinal\\":%u",ordinal);
 _mm_setcsr(saved_mx);SetLastError(saved_error);
 NATIVE_CALL
 xrt_event("test_native_leave","\\"method\\":\\"SetRenderState\\",\\"ordinal\\":%u,\\"result\\":%lu,\\"last_error\\":%lu",ordinal,(DWORD)hr,error);
 if(mode[0]=='1')SendMessageW((HWND)xrt_gui_device_window(c,o->window),WM_GETICON,0,0);
 if(memcmp(&saved,c,sizeof saved)||memcmp(frame,G2H(esp),16))xrt_fatal(c,77,"test post-native CPU/frame changed");
 printf("{\\"kind\\":\\"state\\",\\"ordinal\\":%u,\\"values\\":[",++ordinal);for(i=0;i<256;i++){v=0xa5a5a5a5;sh=get(o->host,i,&v);printf("%s[%lu,%lu]",i?",":"",(DWORD)sh,v);}puts("]}");
 xrt_event("test_suspended_state_cpu","\\"all_cpu_bytes\\":true,\\"frame_bytes\\":16,\\"ordinal\\":%u",ordinal);
 _mm_setcsr(after);SetLastError(error);
 }'''.replace('NATIVE_CALL',call)
 assert code.count(call)==1;code=code.replace(call,hook)
 # Fixture-only observation of adapter entry, including identity guards that
 # deliberately stop before the normal production call event/native interval.
 entry='static void d8_device_SetRenderState(CPU*c) {'
 assert code.count(entry)==1
 code=code.replace(entry,entry+'\n    xrt_event("test_state_adapter_entry","\\"this\\":%u,\\"state\\":%u,\\"value\\":%u",ARG(0),ARG(1),ARG(2));')
 code=code.replace('#include <xmmintrin.h>','#include <xmmintrin.h>\n#include <stdio.h>');(d/'hle_d3d8_device.inc').write_text(code)
 code=(RT/'hle_d3d8.inc').read_text().replace('#include "hle_d3d8_device.inc"','#include "'+str(d/'hle_d3d8_device.inc').replace('\\','/')+'"');(d/'hle_d3d8.inc').write_text(code)
 code=(RT/'hle_misc.c').read_text().replace('#include "hle_d3d8.inc"','#include "'+str(d/'hle_d3d8.inc').replace('\\','/')+'"');p=d/'hle_misc.c';p.write_text(code);return p
def build(out,state,value):
 for arch in ['x86','x64']:
  d=out/arch;asm=''
  if arch=='x86':
   s=(HERE.parent/'d3d8_render/abi32.asm').read_text();start=s.index('    cmp DWORD PTR [ecx+24],0');end=s.index('done:',start);s=s[:start]+'''    push DWORD PTR [ecx+28]
    push DWORD PTR [ecx+24]
    push eax
    mov edx,[eax]
    call DWORD PTR [edx+200]
'''+s[end:];(d/'guestabi.asm').write_text(s);asm=f'ml /nologo /c /Fo"{d}/guestabi.obj" "{d}/guestabi.asm" || exit /b 1\n'
  R.script(out,'client-build-'+arch,arch,f'lib /nologo /def:"{HERE.parent}/d3d8_boundary/d3d8.def" /machine:{"X86"if arch=="x86"else"X64"} /out:"{d}/d3d8.lib" || exit /b 1\n'+asm+f'cl /nologo /c /O2 '+('/arch:IA32 'if arch=='x86'else'')+f'/GS- /W4 /Fo"{d}/probe.obj" "{HERE}/probe.c" || exit /b 1\n'+f'link /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:{"0x12000000"if arch=="x86"else"0x180000000"} /DYNAMICBASE:NO /OUT:"{d}/d3dprobe.dll" "{d}/probe.obj" '+(f'"{d}/guestabi.obj" /alternatename:__imp__Direct3DCreate8@4=__imp__Direct3DCreate8 'if arch=='x86'else'')+f'"{d}/d3d8.lib" kernel32.lib user32.lib || exit /b 1\n'+f'cl /nologo /O2 /W4 /Fo"{d}/native_client.obj" /Fe"{d}/native_client.exe" "{HERE.parent}/d3d8_render/native_client.c" || exit /b 1')
 R.execute([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',out/'x86/d3dprobe.dll','--out',out/'gen'],out,'lift-state')
 sources=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
 for variant in ['production','observed']:
  d=out/variant;d.mkdir();misc=RT/'hle_misc.c'if variant=='production'else observed_source(d,state,value);inputs=[HERE.parent/'d3d8_render/host.c',*(RT/p if p!='hle_misc.c'else misc for p in sources),HERE.parent/'common/xrt_test_stubs.c']
  R.script(out,'translated-build-'+variant,'x64',f'cl /nologo /O1 /Zi /fp:strict /W3 /wd4102 /wd4146 /wd4100 /D_CRT_SECURE_NO_WARNINGS /DSTUB_LOADLIB /DSTUB_POW /I"{RT}" /Fo"{d}\\\\" /Fd"{d}/compile.pdb" /Fe"{d}/translated.exe" '+' '.join('"'+str(p)+'"'for p in inputs)+f' "{out}/gen/*.c" winmm.lib advapi32.lib ole32.lib bcrypt.lib user32.lib gdi32.lib /link /DEBUG /PDB:"{d}/translated.pdb" /STACK:0x10000000 || exit /b 1')
 snapshot=out/'source-snapshot';snapshot.mkdir();shutil.copytree(RT,snapshot/'runtime');shutil.copytree(HERE,snapshot/'fixture',ignore=shutil.ignore_patterns('__pycache__'))
 R.save(out/'sources.json',{str(p.relative_to(W)):R.sha(p)for root in [RT,HERE]for p in root.rglob('*')if p.is_file()and '__pycache__'not in p.parts})
def one(out,arch,state,value,seed=18,variant='production',inject=0,expected=0):
 d=out/f'client-{arch}-{variant}-{state}-{value}-{seed}-{inject}';d.mkdir();env=os.environ.copy();R.G.environment(env,d);env['XRT_D3D8_DIR']=str(R.G.verified_pair('x64'));env['XRT_STATE_CALLBACKS']=str(inject)
 cmd=[out/variant/'translated.exe',out/'x86/d3dprobe.dll',d/'report.json',state,value,seed,0]if arch=='translated'else[out/arch/'native_client.exe',R.G.verified_pair(arch)/'d3d8.dll',out/arch/'d3dprobe.dll',state,value,seed,0]
 import subprocess
 r=subprocess.run([str(v)for v in cmd],cwd=d,env=env,capture_output=True,text=True,timeout=60);(d/'stdout.txt').write_text(r.stdout);(d/'stderr.txt').write_text(r.stderr)
 rec=dict(arch=arch,state=state,value=value,seed=seed,variant=variant,inject=inject,exit=r.returncode,stdout=r.stdout,stderr=r.stderr,observations=[json.loads(s)for s in r.stdout.splitlines()if s.startswith('{')])
 if arch=='translated':
  report=json.loads((d/'report.json').read_text());assert report['events_dropped']==0;rec['events']=report['events']
 R.save(d/'result.json',rec);print('client',arch,variant,state,value,seed,inject,r.returncode,flush=True);assert r.returncode==expected,(rec,r.stderr[-3000:]);return rec
def run(out,state,value):
 rows=[]
 def add(*a,**kw):rows.append(one(out,*a,**kw));R.save(out/'translated-results.json',rows)
 for arch in ['x86','x64','translated']:
  for seed in [18,0,0x13572468,0xffffffff]:add(arch,state,value,seed)
 add('translated',state,value,variant='observed');add('translated',state,value,variant='observed',inject=1)
 for st,val in [(state,value^1),(state,0xffffffff),(0,1),(255,1),(250,0),(251,0),(252,0),(254,0),(256,0)]:add('translated',st,val,expected=76)
 for st in [250,251,254,256]:add('translated',st,0,variant='observed',expected=76)
 add('translated',253,0)
 for st in [70,71,72]:add('translated',st,1,variant='observed',inject=1,expected=76)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action');a.add_argument('--out',type=Path,required=True);a.add_argument('--state',type=int,default=7);a.add_argument('--value',type=int,default=1);v=a.parse_args();fn=globals()[v.action.replace('-','_')];fn(v.out.resolve())if v.action=='native-build'else fn(v.out.resolve(),v.state,v.value)
