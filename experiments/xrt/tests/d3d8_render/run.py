"""Serial disposable fixture driver. Never launches a game executable."""
import argparse,importlib.util,json,os,shutil,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3];RT=W/'experiments/xrt/runtime';O=W/'out/recovery/d3d8-clear-present-20261025-01'
sys.path.insert(0,str(W/'tools/xrt'));import graphics_backend as G
from asset_boundary import sha
VC=r'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat'
def save(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
def execute(cmd,d,name,env=None,timeout=180,cwd=None):
 start=time.monotonic();r=subprocess.run([str(x) for x in cmd],cwd=cwd or W,env=env,capture_output=True,text=True,timeout=timeout)
 (d/(name+'.stdout.txt')).write_text(r.stdout);(d/(name+'.stderr.txt')).write_text(r.stderr)
 save(d/(name+'.json'),dict(command=[str(x)for x in cmd],cwd=str(cwd or W),exit=r.returncode,seconds=time.monotonic()-start))
 print(name,r.returncode,round(time.monotonic()-start,2),flush=True)
 assert r.returncode==0,(cmd,r.stdout[-4000:],r.stderr[-4000:])
 assert 'C1001' not in r.stdout and 'D8040' not in r.stdout
 return r
def script(out,name,arch,body):
 p=out/(name+'.cmd');p.write_text(f'@echo off\ncall "{VC}" {arch} >nul || exit /b 1\n'+body+'\n');return execute(['cmd','/d','/c',p],out,name)
def native_build(out):
 assert (O/'preflight-integrity.json').exists();assert not out.exists();out.mkdir(parents=True)
 for arch in ['x86','x64']:
  G.verified_pair(arch);d=out/arch;d.mkdir();src=HERE.parent/'d3d8_device'/('abi32.asm'if arch=='x86'else'abi64.asm');s=src.read_text().replace('device_abi','render_abi').replace('cwseed WORD 077fh','cwseed WORD 027fh')
  if arch=='x86':
   start=s.index('    push DWORD PTR [eax+28]');end=s.index('    mov edx,[esp+516]',start)
   s=s[:start]+'''    cmp DWORD PTR [eax+48],0
    jne present_call
    push DWORD PTR [eax+28]
    push DWORD PTR [eax+24]
    push DWORD PTR [eax+20]
    push DWORD PTR [eax+16]
    push DWORD PTR [eax+12]
    push DWORD PTR [eax+8]
    push DWORD PTR [eax+4]
    jmp dispatch_call
present_call:
    push DWORD PTR [eax+44]
    push DWORD PTR [eax+40]
    push DWORD PTR [eax+36]
    push DWORD PTR [eax+32]
    push DWORD PTR [eax+4]
dispatch_call:
    call DWORD PTR [eax]
'''+s[end:]
  else:
   start=s.index('    mov rcx,[r10+8]');end=s.index('    mov r10,[rsp+72]',start)
   s=s[:start]+'''    mov rcx,[r10+8]
    cmp DWORD PTR [r10+80],0
    jne present_call
    mov edx,[r10+16]
    mov r8,[r10+24]
    mov r9d,[r10+32]
    mov eax,[r10+36]
    mov [rsp+32],eax
    mov eax,[r10+40]
    mov [rsp+40],eax
    mov eax,[r10+44]
    mov [rsp+48],eax
    jmp dispatch_call
present_call:
    mov rdx,[r10+48]
    mov r8,[r10+56]
    mov r9,[r10+64]
    mov rax,[r10+72]
    mov [rsp+32],rax
dispatch_call:
    call QWORD PTR [r10]
'''+s[end:]
  asm=d/'abi.asm';asm.write_text(s)
  script(out,'native-build-'+arch,arch,f'{"ml"if arch=="x86"else"ml64"} /nologo /c /Fo"{d}/abi.obj" "{asm}" || exit /b 1\n'+f'cl /nologo /O2 /W4 /Zi /Fo"{d}/native.obj" /Fd"{d}/compile.pdb" /Fe"{d}/native.exe" "{HERE}/native.c" "{d}/abi.obj" user32.lib gdi32.lib /link /DEBUG /PDB:"{d}/native.pdb" || exit /b 1')
 save(out/'native-sources.json',{str(p.relative_to(W)):sha(p)for p in [HERE/'native.c',HERE/'native_support.h',RT/'d3d8_abi.h']})
def native_one(out,arch,case,seed=18):
 d=out/f'native-{arch}-{case}-{seed}';assert not d.exists();d.mkdir();env=os.environ.copy();G.environment(env,d)
 r=execute([out/arch/'native.exe',G.verified_pair(arch),case,seed],d,'run',env,60,d)
 rows=[json.loads(s)for s in r.stdout.splitlines() if s.startswith('{')]
 save(d/'observations.json',rows)
 return dict(arch=arch,case=case,seed=seed,exit=r.returncode,rows=rows,directory=str(d))
def native_run(out):
 runs=[]
 for arch in ['x86','x64']:
  for case in [0,1,2,3,4,5,6,7,8,10,11,12,13,14]:
   runs.append(native_one(out,arch,case));save(out/'native-results.json',runs)
  for seed in [0,0x13572468,0xffffffff]:
   runs.append(native_one(out,arch,0,seed));save(out/'native-results.json',runs)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action');a.add_argument('--out',type=Path,required=True);v=a.parse_args();globals()[v.action.replace('-','_')](v.out.resolve())
