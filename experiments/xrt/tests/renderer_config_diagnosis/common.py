"""Isolated renderer-configuration investigation. No genuine launch entry point."""
import pathlib
import sys
W=pathlib.Path(__file__).resolve().parents[4]
H=pathlib.Path(__file__).resolve().parent
O=W/'out/recovery/renderer-config-diagnosis-20261029-01'
LAST=W/'out/recovery/setres-initial-completion-20261029-01'
ATTEMPT=LAST/'owner-bfa1bae0-044b-42bc-aa73-30d1894c2a33'
PRIOR=W/'out/recovery/attachthread-setres-20261029-01'
RT=O/'runtime'
GUEST=0x11104bf8
SCOPE='initial-setres-before-11104bf8'
sys.dont_write_bytecode=True
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core
from supervisor.environment import load
def read(p):return core.read_large(p)
def save(p,v):core.atomic(p,v)
def identity():
    b=read(O/'build.json' if (O/'build.json').exists() else LAST/'build.json')
    return pathlib.Path(b['root'])/'xrt_ucc.exe',b['binary_sha256'],b['pdb_sha256']
EXE,SHA,PDB=identity()
PHRASE='AUTHORIZE ONE PROFILE-FIXED INITIAL SETRES '+SHA[:16].upper()+' BEFORE 11104BF8 FOR 60 SECONDS'
STOP_PHRASE='AUTHORIZE EXISTING INITIAL SETRES STOP BEFORE 11104BF8 FOR '+SHA[:16].upper()+' ONLY'
RVA=read(O/'stop-mapping.json')['stop_rva'] if (O/'stop-mapping.json').exists() else None
def legacy():
    m=load('renderer_configuration_retained_observer',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE,m.V.EXPECTED,_=identity();return m
