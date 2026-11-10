"""Isolated engine bring-up development. No genuine launch entry point."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W / 'out/recovery/engine-bringup-20261030-01'
RT = O / 'runtime'
PRIOR = W / 'out/recovery/semantic-compat-20261029-01'
EVIDENCE = W / 'out/recovery/semantic-physical-20261030-01/continuation-proposal/owner-e5aa874c-8581-4dc0-9ba0-b7ba87cc475a'
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core
from supervisor.environment import load
import asset_boundary as A
read = core.read_large
save = core.atomic
GUEST=0x1090ed5c
def identity():
    b=read(O/'build.json');return Path(b['root'])/'xrt_ucc.exe',b['binary_sha256'],b['pdb_sha256']
def legacy():
    m=load('bringup_retained_debugger',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE,m.V.EXPECTED,_=identity();return m

def helper(out):
    m = load('bringup_build_helper', H.parent / 'getobject_boundary/phase.py')
    m.O = out
    return m
