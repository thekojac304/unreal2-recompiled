"""Measure initial COM dependencies, without claiming translated/audio compatibility."""
from pathlib import Path
import hashlib
import json
import subprocess
import uuid
import pefile

WS=Path(__file__).resolve().parents[4]
BUILD=WS/'experiments/xrt/build/directmusic_boundary'
image=WS/'sandbox_cmp/level/System/Engine.dll'
pe=pefile.PE(str(image))
rvas=[0x240010,0x23ffb0,0x240020,0x23ffa0]
operands=[pe.get_data(rva,16) for rva in rvas]
out=WS/'experiments/xrt/results/raw/directmusic'/uuid.uuid4().hex[:12]
out.mkdir(parents=True,exist_ok=False)
runs={}
for arch,machine in [('x86',0x14c),('x64',0x8664)]:
    exe=BUILD/arch/'native.exe'
    assert pefile.PE(str(exe),fast_load=True).FILE_HEADER.Machine==machine
    cmd=[str(exe),*(b.hex() for b in operands)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    runs[arch]={'command':cmd,'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
                'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
    (out/(arch+'.txt')).write_text(result.stdout+result.stderr)
record={'scope':'native dependency observation only; no translated COM adapter, audio initialization or playback',
        'engine_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
        'operands':[{'rva':hex(r),'bytes':b.hex(),'guid':str(uuid.UUID(bytes_le=b))} for r,b in zip(rvas,operands)],
        'runs':runs,'oracle_completed':all(r['exit']==0 for r in runs.values()),
        'initial_factory_results_identical':runs['x86']['stdout']==runs['x64']['stdout']}
(out/'result.json').write_text(json.dumps(record,indent=2))
(BUILD/'latest.json').write_text(json.dumps({'evidence':str(out.relative_to(WS))},indent=2))
print(out)
for arch,r in runs.items():print(arch,r['stdout'].strip())
if not record['oracle_completed']:raise SystemExit(1)
print('INITIAL DEPENDENCY MATCH' if record['initial_factory_results_identical'] else 'MEASURED ARCHITECTURE DIFFERENCE (not a compatibility pass)')
