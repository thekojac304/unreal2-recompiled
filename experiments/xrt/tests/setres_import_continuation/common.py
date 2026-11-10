"""Fixed identities for the preparation-only SetRes completion milestone."""
import pathlib
import sys

W = pathlib.Path(__file__).resolve().parents[4]
H = pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core
from supervisor.environment import load

PRIOR = W / 'out/recovery/attachthread-setres-20261029-01'
O = W / 'out/recovery/setres-import-continuation-20261029-01'
EXE = W / 'experiments/xrt/build/attachthread-setres-20261029-01/bfdbf2b3-901c-408a-a08d-025c05a48cf4/xrt_ucc.exe'
SHA = 'fee6e1e9a3c3def98c90c7e6c44268ec1026ccbe9e24d1f34d70d36707dd9a51'
PDB = '54eb7019d493620f316f9cc87ec8c405f2b7d0cc7e08d978df6fd0fbaa71ad0b'
GUEST = 0x0696d2cd
RVA = 0x5a7f813
SCOPE = 'setres-import-continuation-before-0696d2cd'
PHRASE = 'AUTHORIZE ONE IMPORT-FIXED SETRES FEE6E1E9A3C3DEF9 BEFORE 0696D2CD FOR 60 SECONDS'


def legacy():
    m = load('setres_retained_observer', W / 'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE, m.V.EXPECTED = EXE, SHA
    return m


def read(path):
    return core.read_large(path)


def save(path, value):
    core.atomic(path, value)

