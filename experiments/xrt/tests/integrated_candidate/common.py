"""Isolated resource/first-frame work; no genuine execution entry point."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
W=H.parents[3]
O=W/'out/recovery/integrated-candidate-20261030-01'
SEALED=W/'out/recovery/surface-transfer-20261030-01'
RT=SEALED/'runtime'
PRIOR=W/'out/recovery/resource-frame-20261030-01'
EVIDENCE=W/'out/recovery/semantic-physical-20261030-01/continuation-proposal/owner-e5aa874c-8581-4dc0-9ba0-b7ba87cc475a'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core
from supervisor.environment import load
import asset_boundary as A
read=core.read_large
save=core.atomic
GUEST=0x1090ed5c
def identity():
    b=read(O/'build.json');return Path(b['root'])/'xrt_ucc.exe',b['binary_sha256'],b['pdb_sha256']
def legacy():
    m=load('resource_retained_debugger',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE,m.V.EXPECTED,_=identity();return m
def helper(out):
    m=load('resource_build_helper',H.parent/'getobject_boundary/phase.py');m.O=out;return m
