"""Read-only investigation identities; no genuine launch entry point."""
import pathlib
import sys

W = pathlib.Path(__file__).resolve().parents[4]
H = pathlib.Path(__file__).resolve().parent
O = W / 'out/recovery/setres-argument-diagnosis-20261029-01'
OLD = W / 'out/recovery/setres-import-continuation-20261029-01'
ATTEMPT = OLD / 'owner-fa3b112f-189a-422b-ac3c-ea197a910de6'
SANDBOX = W / 'sandbox_cmp/setres-fa3b112f-189a-422b-ac3c-ea197a910de6'
EXE = W / 'experiments/xrt/build/attachthread-setres-20261029-01/bfdbf2b3-901c-408a-a08d-025c05a48cf4/xrt_ucc.exe'
SHA = 'fee6e1e9a3c3def98c90c7e6c44268ec1026ccbe9e24d1f34d70d36707dd9a51'
PRIMARY = 0x0696d2cd
INITIAL = 0x11104bf8
sys.dont_write_bytecode = True
sys.path.insert(0, str(W / 'tools/xrt'))
from supervisor import core


def read(path):
    return core.read_large(path)


def save(path, value):
    core.atomic(path, value)
