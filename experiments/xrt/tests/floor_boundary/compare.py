"""Bit/state differential against native x86 msvcr70; failures are never waived."""
from pathlib import Path
import hashlib
import json
import random
import struct
import subprocess
import sys
import uuid
import argparse

WS=Path(__file__).resolve().parents[4]
OUT=WS/'experiments/xrt/build/floor_boundary'

def corpus():
    values={0,1,0xfffffffffffff,0x10000000000000,0x7fefffffffffffff,
            0x7ff0000000000000,0x7ff8000000000000,0x7ff0000000000001,
            0x7ff8123456789abc,0x7ff0123456789abc,
            0x3faa000000000000,0x3fefe00000000000,
            0x409001a400000000,0x4090025c00000000,0x409fa40000000000}
    for x in [0.5,1.,1.5,2.,3.,255.,256.,65536.,2.**31,2.**32,2.**51,2.**52,2.**53]:
        b=struct.unpack('<Q',struct.pack('<d',x))[0]
        values.update(b+d for d in [-2,-1,0,1,2])
    rng=random.Random(20261023)
    values.update(rng.getrandbits(63) for _ in range(3000))
    values|={v|1<<63 for v in values}
    # Exact observed state plus clean and seeded condition/sticky flags; deeper values must survive.
    for v in sorted(values):
        for sw,depth in [(0,0),(0x100,0),(0x120,0),(0x472f,2),(0x4000,4),(0x4025,0)]:
            for cw in [0x027f,0x023f]:
                yield f'{v:016x} {cw:04x} {sw:04x} {depth}\n'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--function',choices=['floor','ceil'],default='floor')
    ap.add_argument('--native-only',action='store_true')
    args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    evidence=WS/'experiments/xrt/results/raw'/args.function/uuid.uuid4().hex[:12]
    evidence.mkdir(parents=True,exist_ok=False)
    inp=evidence/'corpus.txt'; inp.write_text(''.join(corpus()))
    ref=evidence/'native.txt'; cand=evidence/'cand.txt'
    subprocess.run([str(OUT/'native.exe'),str(WS/'sandbox_cmp/level/System/msvcr70.dll'),str(inp),str(ref),args.function],check=True)
    if args.native_only:
        print(ref); return 0
    subprocess.run([str(OUT/'cand.exe'),str(inp),str(cand),args.function],check=True)
    a,b=ref.read_text().splitlines(),cand.read_text().splitlines()
    differences=[{'case':i,'reference':x,'candidate':y} for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    negative=evidence/'unsupported-cw.txt'; negative.write_text('3ff8000000000000 037f 0000 0\n')
    neg=subprocess.run([str(OUT/'cand.exe'),str(negative),str(evidence/'unsupported-cw-output.txt'),args.function],capture_output=True,text=True)
    rejected=neg.returncode==76 and 'leaves the modelled x87 state' in neg.stderr
    result={'function':args.function,'cases':len(a),'candidate_cases':len(b),'differences':differences,
            'unsupported_control_word':{'exit':neg.returncode,'stderr':neg.stderr,'explicitly_rejected':rejected},
            'hashes':{str(p.relative_to(WS)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [inp,ref,cand,OUT/'native.exe',OUT/'cand.exe',WS/'sandbox_cmp/level/System/msvcr70.dll']}}
    (evidence/'result.json').write_text(json.dumps(result,indent=2))
    (OUT/'latest.json').write_text(json.dumps({'evidence':str(evidence.relative_to(WS))},indent=2))
    print(f'{len(a)} cases, {len(differences)} differences, candidate {len(b)}')
    print(evidence)
    for d in differences[:8]: print(d)
    return int(bool(differences) or len(a)!=len(b) or len(a)!=len(inp.read_text().splitlines()) or not a or not rejected)

if __name__=='__main__':sys.exit(main())
