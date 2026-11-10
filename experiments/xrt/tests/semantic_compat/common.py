"""Semantic compatibility development. No game launch or authorization entry point."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W / 'out/recovery/semantic-compat-20261029-01'
RT = O / 'runtime'
PRIOR = W / 'out/recovery/renderer-config-diagnosis-20261029-01'
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core
from supervisor.environment import load
import asset_boundary as A
def read(p): return core.read_large(p)
def save(p, v): core.atomic(p, v)
GUEST=0x11104bf8
def identity():
    b=read(O/'build.json');return Path(b['root'])/'xrt_ucc.exe',b['binary_sha256'],b['pdb_sha256']
def legacy():
    m=load('semantic_retained_debugger',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE,m.V.EXPECTED,_=identity();return m
