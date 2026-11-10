"""Fixed identities for the preparation-only SetRes completion milestone."""
import pathlib
import sys

W = pathlib.Path(__file__).resolve().parents[4]
H = pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core
from supervisor.environment import load

PRIOR = W / 'out/recovery/renderer-gamma-integration-20261029-01'
O = W / 'out/recovery/setres-completion-20261029-01'
EXE = W / 'experiments/xrt/build/renderer-prerequisites-20261029-01/ba218809-88d7-40a6-b069-2125cbecd53c/xrt_ucc.exe'
SHA = 'd6071f6563300dc4ae04b77d35943625f5b4274bb58db4a04ed6aee22b58d158'
PDB = '9e571a4c30354a36e261f4263cd414e578c6d046ead554ae7f741f79891ced8b'
GUEST = 0x0696d2cd
RVA = 0x05a7f813
SCOPE = 'setres-completion-before-0696d2cd'
PHRASE = 'AUTHORIZE ONE SETRES COMPLETION D6071F6563300DC4 BEFORE 0696D2CD FOR 60 SECONDS'


def legacy():
    m = load('setres_retained_observer', W / 'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE, m.V.EXPECTED = EXE, SHA
    return m


def read(path):
    return core.read_large(path)


def save(path, value):
    core.atomic(path, value)

