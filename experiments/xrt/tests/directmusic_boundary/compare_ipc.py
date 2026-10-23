"""Serialized native/IPC session and failure acceptance. Preserve tested executables."""
from pathlib import Path
import ctypes, hashlib, json, shutil, struct, subprocess, time, uuid
import pefile

WS=Path(__file__).resolve().parents[4]
B=WS/'experiments/xrt/build/dmusic-ipc'
OUT=WS/'experiments/xrt/results/raw/directmusic'/('ipc-'+uuid.uuid4().hex[:12])
OUT.mkdir(parents=True)
SB=WS/'sandbox_cmp/level'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
images={name:B/name for name in ['dmusic_helper.exe','ipc_session.exe']}
images['native_session.exe']=WS/'experiments/xrt/build/directmusic_boundary/x86/session.exe'
for name,p in images.items(): shutil.copy2(p,OUT/name)
pe=pefile.PE(str(SB/'System/Engine.dll'))
rvas=[0x240010,0x23ffb0,0x240020,0x23ffa0,0x23ffe0,0x23ffd0,0x23fff0,0x23ff80,0x240000,0x23ff90,0x240040,0x23ffc0,0x240030]
(OUT/'guids.bin').write_bytes(b''.join(pe.get_data(r,16) for r in rvas))
commands=[('native',[str(OUT/'native_session.exe'),str(OUT/'guids.bin'),str(SB/'Music')])]
base=[str(OUT/'ipc_session.exe'),str(OUT/'dmusic_helper.exe'),str(SB),'1',str(OUT/'guids.bin')]
commands += [(mode,base+[mode]) for mode in ['session','lifetime','malformed','badsize','badsequence','badkind','truncated','invalid','unsupported','crash','timeout','disconnect','host-exit','guard','routine-block','processpmsg','callback']]
runs=[]
for mode,cmd in commands:
    start=time.monotonic()
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
    run=dict(mode=mode,command=cmd,exit=r.returncode,elapsed=time.monotonic()-start,stdout=r.stdout,stderr=r.stderr)
    if mode=='host-exit':
        child=int(r.stdout.strip().split()[-1])
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.restype=ctypes.c_void_p
        handle=k.OpenProcess(0x100000,False,child)
        if handle:
            k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
            run['child_terminated']=k.WaitForSingleObject(handle,2000)==0
            k.CloseHandle.argtypes=[ctypes.c_void_p];k.CloseHandle(handle)
        else: run['child_terminated']=True
    (OUT/(mode+'.stdout')).write_text(r.stdout)
    (OUT/(mode+'.stderr')).write_text(r.stderr)
    runs.append(run);print(mode,r.returncode,round(run['elapsed'],3),flush=True)
native=runs[0]['stdout'];ipc=runs[1]['stdout']
same=native==ipc
if not same:
    import difflib
    print(''.join(difflib.unified_diff(native.splitlines(True),ipc.splitlines(True))))
expected={'lifetime':'stale handle rejected','malformed':'malformed rejected','badsize':'malformed rejected',
          'badsequence':'malformed rejected','badkind':'malformed rejected','truncated':'disconnect bounded',
          'invalid':'status 2','unsupported':'status 3','crash':'child exited','timeout':'deadline exceeded',
          'disconnect':'disconnect exit 0','guard':'disk guard verified','routine-block':'status 3',
          'processpmsg':'unsupported Tool.ProcessPMsg','callback':'unsupported callback'}
faults=all(message in next(r for r in runs if r['mode']==mode)['stdout']+next(r for r in runs if r['mode']==mode)['stderr'] for mode,message in expected.items())
ok=(all(r['exit']==0 for r in runs) and same and faults and next(r for r in runs if r['mode']=='host-exit')['child_terminated']
    and 'sandbox denied' not in runs[1]['stderr']
    and struct.calcsize('P')==8
    and pefile.PE(str(OUT/'dmusic_helper.exe')).FILE_HEADER.Machine==0x14c
    and pefile.PE(str(OUT/'ipc_session.exe')).FILE_HEADER.Machine==0x8664)
sources=[WS/'experiments/xrt/runtime/dmusic_backend.h',WS/'experiments/xrt/runtime/dmusic_pipe.h',WS/'experiments/xrt/dmusic_helper/main.c',WS/'experiments/xrt/dmusic_helper/file_guard.h',Path(__file__),Path(__file__).with_name('ipc_session.c')]
record=dict(passed=ok,fault_diagnostics_match=faults,protocol=dict(magic='31424d44',version=1,frame_bytes=2000,sha256=sha(sources[0])),
            native_stdout_exactly_matches_ipc=same,runs=runs,
            binaries={n:dict(sha256=sha(OUT/n),path=str((OUT/n).relative_to(WS))) for n in images},
            inputs={str(p.relative_to(WS)):sha(p) for p in [SB/'System/Engine.dll',SB/'Music/Intro.con']},
            sources={str(p.relative_to(WS)):sha(p) for p in sources})
(OUT/'result.json').write_text(json.dumps(record,indent=2))
(B/'latest.json').write_text(json.dumps(dict(evidence=str(OUT.relative_to(WS)))))
print(OUT,'PASS' if ok else 'FAIL')
raise SystemExit(0 if ok else 1)
