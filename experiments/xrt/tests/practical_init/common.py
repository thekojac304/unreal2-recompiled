"""Experimental monitoring only. No genuine launch/queue entry point."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
BASELINE = W / 'out/recovery/runtime-monitoring-20261030-01'
O = W / 'out/recovery/practical-init-20261031-01'
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
    original=m.run
    def pinned_run(command,name,**kwargs):
        before=core.tree(RT)
        inputs={str(p):core.sha(p) for arg in command if (p:=Path(str(arg))).is_file()}
        result=original(command,name,**kwargs)
        core.require(core.tree(RT)==before,'runtime changed during qualification command '+name)
        receipt=read(out/(name+'.json'));receipt.update(runtime_at_command=before,explicit_file_inputs=inputs)
        save(out/(name+'.json'),receipt)
        return result
    m.run=pinned_run
    return m
def identity():
    b = read(O/'build.json')
    return Path(b['root'])/'xrt_ucc.exe', b['binary_sha256'], b['pdb_sha256']
def legacy():
    m = load('monitor_retained_debugger', W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE, m.V.EXPECTED, _ = identity()
    return m

FINISHED = W/'out/recovery/init-runtime-finish-20261030-01'
from supervisor import fixture
from debugger_handles import install
install()
_environment=fixture.environment
def development_environment(sandbox):
    e=_environment(sandbox);e['XRT_MONITOR_PROFILE']='development';return e
fixture.environment=development_environment
