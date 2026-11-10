"""Prepare an owner non-game action and conditional genuine diagnostic; no launch."""
import ast, importlib.util, json, shutil, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('post_package_preservation',HERE/'preserve.py');P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
W=P.W;O=P.O;OLD=P.OLD
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    assert P.read(O/'observer-tests.json')['passed']
    diag=P.read(O/'diagnosis.json');assert diag['passed'] and not diag['string_bytes_retained']
    chars=P.read(O/'init-audio-characterization.json')['runs']
    assert len(chars)==3 and all(r['exit']==0 and 'InitAudio return 00000000 object=1' in r['stdout'] and 'cleanup passed' in r['stdout'] for r in chars)
    build=P.read(OLD/'build.json');P.check(P.B,build['outputs'])
    assert all(P.sha(W/rel)==h for rel,h in P.read(OLD/'current-sources.json').items())
    fixture=P.read(O/'fixture-build.json');fixture['root']=str(W/'experiments/xrt/build/postsplash-recovery-20261028-01')
    P.save(O/'owner-fixture-build.json',fixture)
    # Keep the original fixture build record unchanged. The owner script reads
    # the package's bound descriptor, including the explicit artifact root.
    owner=(HERE/'owner_fixture.py').read_text().replace("read(O/'fixture-build.json')","read(O/'owner-fixture-build.json')")
    (O/'owner_fixture.py').write_text(owner)
    (O/'owner-init-audio.cmd').write_text(f'@echo off\nsetlocal\ncd /d "{W}"\n"{W}/.venv/Scripts/python.exe" -B -I "{O}/owner_fixture.py" --execute-owner-fixture\nexit /b %errorlevel%\n')
    for n in ['candidate_plan.py','candidate-debugger-plan.json','build.json','pinned-inputs.json']:
        shutil.copy2(OLD/n,O/n)
    shutil.copy2(HERE/'observer_evidence.py',O/'observer_evidence.py')
    genuine=(OLD/'bounded_genuine.py').read_text()
    assert genuine.count("L.SB=W/'sandbox_cmp/getobject-recovery-20261028-01'")==1
    genuine=genuine.replace("L.SB=W/'sandbox_cmp/getobject-recovery-20261028-01'","L.SB=W/'sandbox_cmp/postsplash-recovery-20261028-01'")
    (O/'bounded_genuine.py').write_text(genuine)
    owner=(OLD/'bounded_owner.py').read_text()
    needle="inputs=verify();RUN.mkdir()"
    assert owner.count(needle)==1
    owner=owner.replace(needle,"assert (O/'owner-init-audio-run/result.json').exists(), 'Owner non-game InitAudio prerequisite is pending; no game launch'\n    assert read(O/'owner-init-audio-run/result.json')['passed'], 'Owner fixture must pass first'\n    inputs=verify();RUN.mkdir()")
    (O/'bounded_owner.py').write_text(owner)
    (O/'owner-genuine-diagnostic.cmd').write_text(f'@echo off\nsetlocal\ncd /d "{W}"\n"{W}/.venv/Scripts/python.exe" -B -I "{O}/bounded_owner.py" --execute-owner-authorized\nexit /b %errorlevel%\n')
    P.save(O/'readiness.json',dict(prepared=True,gui_acceptance_complete=True,observer_live_qualified=True,
        diagnostic_only=True,genuine_launch_ready=False,owner_fixture_prerequisite='owner-init-audio-run/result.json must pass on the owner Default desktop',
        maximum_genuine_sessions=1,watchdog_ms=60000,retry=False,guest_stop='0x0696f292',instruction_must_not_execute=True,
        genuine_game_launched=False,strict_x87='FAILED; preserved',strict_wndproc_equality='FAILED; preserved',
        runtime_fix=False,exact_consumed_error_string_recovered=False))
    entries=P.read(OLD/'current-sources.json')
    for root in [HERE,W/'experiments/xrt/runtime',W/'experiments/xrt/gen']:
        for f in P.files(root):entries[f.relative_to(W).as_posix()]=P.sha(f)
    P.save(O/'current-sources.json',entries)
    identities={f.relative_to(W).as_posix():P.sha(f) for f in P.files(Path(fixture['root']))}
    for n in ['owner_fixture.py','owner-init-audio.cmd','owner-fixture-build.json']:
        identities[(O/n).relative_to(W).as_posix()]=P.sha(O/n)
    for f in (W/'out/recovery/session-aware-136-20261026-01').glob('*.py'):identities[f.relative_to(W).as_posix()]=P.sha(f)
    P.save(O/'owner-fixture-identities.json',identities)
    names=['candidate_plan.py','candidate-debugger-plan.json','bounded_genuine.py','bounded_owner.py','observer_evidence.py','owner-genuine-diagnostic.cmd',
        'build.json','readiness.json','pinned-inputs.json','current-sources.json','preservation.json','observer-tests.json','owner-fixture-identities.json']
    P.save(O/'launcher-identities.json',{n:P.sha(O/n) for n in names})
    for f in O.glob('*.py'):ast.parse(f.read_text())
    sys.path.insert(0,str(O));import candidate_plan as plan
    resolved=plan.resolve();assert resolved==P.read(O/'candidate-debugger-plan.json')
    import bounded_genuine as genuine
    dest=O/'offline-observer-construction';dest.mkdir()
    capture=genuine.observer(dest,resolved,lambda tag:None)
    assert capture.created==0 and capture._fatal_evidence_installed
    capture.log('offline_post_splash_construction',game_launched=False)
    package=load('post_offline_owner_package',O/'bounded_owner.py');package.verify()
    load('post_offline_owner_fixture',O/'owner_fixture.py').verify()
    assert not (O/'genuine-owner-run').exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    assert not (O/'owner-init-audio-run').exists()
    P.save(O/'conditional-continuation.json',dict(prepared=True,owner_fixture_pending=True,genuine_launch_ready=False,
        executable_sha256=build['binary_sha256'],pdb_sha256=build['pdb_sha256'],rebuilt=False,
        reason='Only observer evidence capture changed. The genuine transport failure was not reproduced in local non-game fixtures.',
        static_stop_mapping_verified=True,final_observer_constructed_offline=True,parent_watchdog_seconds=60,maximum_genuine_sessions=1,
        game_launched=False,owner_fixture_command=str(O/'owner-init-audio.cmd')))
    print('OWNER NON-GAME ACTION READY; GENUINE DIAGNOSTIC PREPARED BUT GATED',flush=True)
if __name__=='__main__':main()
