"""Experimental monitoring only. No genuine launch/queue entry point."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W / 'out/recovery/runtime-monitoring-20261030-01'
RT = O / 'runtime'
PRIOR = W / 'out/recovery/surface-transfer-20261030-01'
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core
from supervisor.environment import load
import asset_boundary as A
read, save = core.read_large, core.atomic
GUEST = 0x1090ed5c
def helper(out):
    m = load('monitor_build_helper', H.parent/'getobject_boundary/phase.py'); m.O = out
    return m
def identity():
    b = read(O/'build.json')
    return Path(b['root'])/'xrt_ucc.exe', b['binary_sha256'], b['pdb_sha256']
def legacy():
    m = load('monitor_retained_debugger', W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE, m.V.EXPECTED, _ = identity()
    return m
