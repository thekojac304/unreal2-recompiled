"""Read-only adoption of the sealed candidate; all new receipts are isolated."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W / 'out/recovery/init-monitoring-20261030-01'
SEALED = W / 'out/recovery/integrated-candidate-20261030-01'
RT = W / 'out/recovery/surface-transfer-20261030-01/runtime'
PRIOR = W / 'out/recovery/resource-frame-20261030-01'
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core
from supervisor.environment import load
import asset_boundary as A
read, save = core.read_large, core.atomic
GUEST = 0x1090ed5c
def identity():
    b = read(SEALED / 'build.json')
    return Path(b['root']) / 'xrt_ucc.exe', b['binary_sha256'], b['pdb_sha256']
def legacy():
    m = load('init_monitoring_retained', W / 'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE, m.V.EXPECTED, _ = identity()
    return m
def helper(out):
    m = load('init_monitoring_build', H.parent / 'getobject_boundary/phase.py')
    m.O = out
    return m
