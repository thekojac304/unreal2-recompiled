"""Native x86 child/x64 host feasibility and independent missing-routine comparison."""
from pathlib import Path
import hashlib,json,subprocess,uuid,pefile,sys,struct
sys.path.insert(0,str(Path(__file__).resolve().parent))
from script_names import scripts,call_missing,UnsupportedScript
WS=Path(__file__).resolve().parents[4];B=WS/'experiments/xrt/build/directmusic_boundary'
SB=WS/'sandbox_cmp/level';OUT=WS/'experiments/xrt/results/raw/directmusic'/('session-'+uuid.uuid4().hex[:12]);OUT.mkdir(parents=True)
image=SB/'System/Engine.dll';pe=pefile.PE(str(image))
rvas=[0x240010,0x23ffb0,0x240020,0x23ffa0,0x23ffe0,0x23ffd0,0x23fff0,0x23ff80,0x240000,0x23ff90,0x240040,0x23ffc0,0x240030]
(OUT/'guids.bin').write_bytes(b''.join(pe.get_data(r,16) for r in rvas))
runs=[]
for arch in ['x86','x64']:
    machine=pefile.PE(str(B/arch/'session.exe'),fast_load=True).FILE_HEADER.Machine
    if machine!=({'x86':0x14c,'x64':0x8664}[arch]):raise RuntimeError('native session architecture mismatch')
    cmd=[str(B/arch/'session.exe'),str(OUT/'guids.bin'),str(SB/'Music')]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    runs.append(dict(architecture=arch,pe_machine=hex(machine),command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr,binary_sha256=hashlib.sha256((B/arch/'session.exe').read_bytes()).hexdigest()))
    (OUT/(arch+'.txt')).write_text(r.stdout+r.stderr);print(arch,r.returncode,r.stdout)
data=(SB/'Music/Intro.con').read_bytes();items=scripts(data)
if len(items)!=1 or items[0]['name']!='Script1':raise RuntimeError('unsupported container/script selection')
script=items[0];native_names=[line[8:] for line in runs[0]['stdout'].splitlines() if line.startswith('routine ')]
missing={n:call_missing(script,n) for n in ['', '__xrt_missing_routine__']}
blocked=[]
for n in script['routines']:
    try:call_missing(script,n)
    except UnsupportedScript:blocked.append(n)
ok=(runs[0]['exit']==0 and set(native_names)==set(script['routines']) and len(blocked)==len(native_names)
    and all(f'CallRoutine.{suffix} {missing[name]:08x}' in runs[0]['stdout'] for name,suffix in [('', 'empty'),('__xrt_missing_routine__','missing')])
    and runs[1]['exit']==4 and 'Performance8 80040154' in runs[1]['stdout'])
record={'pass':ok,'parent_pointer_bits':struct.calcsize('P')*8,
        'scope':'native child-process feasibility plus independent missing-name failure only; no translated Performance8, script initialization or playback implementation',
        'runs':runs,'engine_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'container_sha256':hashlib.sha256(data).hexdigest(),
        'script':script,'native_routines':native_names,'independent_missing_results':missing,'present_routines_explicitly_unsupported':blocked,
        'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('script_names.py'),Path(__file__).with_name('session.c')]}}
(OUT/'result.json').write_text(json.dumps(record,indent=2));(B/'session-latest.json').write_text(json.dumps({'evidence':str(OUT.relative_to(WS))}))
print(OUT,'PASS' if ok else 'FAIL');raise SystemExit(0 if ok else 1)
