"""Owner-launched, one-session WM_GETOBJECT recovery continuation. No auto retry."""
import argparse, hashlib, importlib.util, json, os, sys, traceback
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;W=O.parents[2];RUN=O/'genuine-owner-run'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def verify():
    r=read(O/'readiness.json');assert r['prepared'] and r['gui_acceptance_complete'] and r['observer_live_qualified']
    assert r['maximum_genuine_sessions']==1 and r['watchdog_ms']==60000 and not r['retry']
    for rel,h in read(O/'launcher-identities.json').items():assert sha(O/rel)==h,rel
    for rel,h in read(O/'current-sources.json').items():assert sha(W/rel)==h,rel
    build=read(O/'build.json');assert build['passed']
    for rel,h in build['outputs'].items():assert sha(Path(build['root'])/rel)==h,rel
    sys.path.insert(0,str(W/'tools/xrt'));import asset_boundary as A,graphics_backend as G
    assets=A.verify();assert assets==read(O/'preservation.json')['protected_assets']
    pinned=read(O/'pinned-inputs.json')
    for p,h in pinned['pinned_driver_files'].items():assert sha(p)==h,p
    for arch in ['x86','x64']:G.verified_pair(arch)
    helper=pinned['inputs']['helper'];assert sha(helper['path'])==helper['sha256']
    # The prior session remains consumed. Never call its launcher or reuse its tree.
    consumed=W/'out/recovery/renderer-init-preparation-20261027-01'
    assert (consumed/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    for rel,h in read(O/'preservation.json')['consumed_evidence'].items():assert sha(W/rel)==h,rel
    return dict(assets=assets,helper=helper)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-owner-authorized',action='store_true');args=parser.parse_args()
    if not args.execute_owner_authorized:parser.error('Run only when the owner chooses the prepared continuation; no game launched.')
    assert not sys.flags.optimize
    assert not RUN.exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists(),'one attempt only; preserve any failure'
    inputs=verify();RUN.mkdir()
    sys.path.insert(0,str(O));import bounded_genuine as genuine
    m=load('wm_owner_environment',W/'out/recovery/session-aware-136-20261026-01/owner.py');m.RUN=RUN
    baseline=None;before=None
    def check(tag):
        nonlocal baseline
        d=m.observe();save(RUN/(tag+'-environment.json'),d);f=m.environment_gate(d)
        if baseline is None:baseline=f
        else:assert f==baseline,('environment changed',tag)
    try:
        check('initial');check('second')
        before=dict(state=m.V.state(),physical_clip=baseline['clip']);assert not before['state']['processes']
        save(RUN/'initial-state.json',before)
        plan=genuine.resolve();assert plan==read(O/'candidate-debugger-plan.json')
        save(RUN/'preflight.json',dict(passed=True,inputs=inputs,baseline=baseline,maximum_sessions=1,
            hard_stop='0x0696f292',watchdog_ms=60000,strict_x87='FAILED; retained',strict_wndproc_equality='FAILED; retained'))
        check('before-genuine');genuine.run(RUN/'session',check,inputs)
        save(RUN/'completed.json',dict(passed=True,genuine_sessions=1,continued_after_guest_0696f292=False))
    except BaseException:
        (RUN/'STOP.txt').write_text(traceback.format_exc());raise
    finally:
        if before is not None:m.restore_and_check(before)
        verify();check('final')
if __name__=='__main__':main()
