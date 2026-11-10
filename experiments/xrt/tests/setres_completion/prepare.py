"""Preparation and non-game validation only. No owner launcher is imported here."""
import os
import pathlib
import subprocess
import sys
import time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def preservation():
    core.require(not O.exists(),'preserve the existing preparation; do not reset it')
    O.mkdir()
    roots=[p for p in (W/'out/recovery').iterdir() if p.is_dir() and p!=O]
    roots += [core.HOME,W/'tools/xrt/supervisor',W/'experiments/xrt/runtime',W/'experiments/xrt/gen',EXE.parent]
    # Preserve the complete prior recovery history, not only its summaries.
    data=dict(trees={},strict_failure_files={},genuine_launches=0,production_breakpoint_changes=0)
    for root in roots:
        data['trees'][str(root)]=core.tree(root)
    for p in [W/'experiments/xrt/tests/x87/results.json',W/'debug-symbols.json']:
        if p.exists():data['strict_failure_files'][str(p)]=core.sha(p)
    l=legacy();data['protected']=l.D.Assets.verify()
    save(O/'preservation.json',data)
    print('Complete prior recovery/source/supervisor history sealed',flush=True)


def verify():
    from identity import verify as check
    from mapping import resolve,sequence
    save(O/'candidate-identity.json',check())
    plan=resolve();save(O/'stop-mapping.json',plan)
    save(O/'call-scope.json',dict(configured_calls=238,operations=sequence(),extra='CreateDevice, Clear, Present, first eight states, SetMaterial, ResizeViewport',
        strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained'))
    from observer import construct
    dest=O/'offline-construction';dest.mkdir()
    cap,l=construct(dest,plan,lambda _:None,[pathlib.Path(p) for p in read(O/'candidate-identity.json')['dependencies']])
    core.require(cap.created==0 and cap.cpu is None,'offline observer executed')
    save(O/'observer-construction.json',dict(passed=True,created=cap.created,operations=len(cap.profile),game_started=False))
    print('Independent candidate lineage, PE/PDB, original instructions and observer construction PASS',flush=True)


def final_preservation():
    p=read(O/'preservation.json');checks={}
    for root,expected in p['trees'].items():
        checks[root]=core.tree(pathlib.Path(root))==expected
        core.require(checks[root],'previous evidence/source tree changed: '+root)
    for name,digest in p['strict_failure_files'].items():core.require(core.sha(name)==digest,'strict evidence changed')
    l=legacy();core.require(l.D.Assets.verify()==p['protected'],'protected installation/saves/snapshot changed')
    save(O/'preservation-after.json',dict(passed=True,trees=checks,protected_equal=True,genuine_launches=0,production_breakpoint_changes=0))
    print('All previous recovery, production supervisor, source identities and protected assets unchanged',flush=True)


if __name__=='__main__':
    core.require(len(sys.argv)==2 and sys.argv[1] in ('preserve','verify','final-preservation'),'preparation subcommand')
    {'preserve':preservation,'verify':verify,'final-preservation':final_preservation}[sys.argv[1]]()
