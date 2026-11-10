"""Prepare a new owner-only bounded continuation. Never invokes its launcher."""
import ast, importlib.util, json, shutil, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('wm_preparation_phase',HERE/'phase.py');F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
O=F.O;W=F.W

def main():
    build=F.read(O/'build.json');assert build['passed'] and build['compiled_objects']==279 and build['reused_objects']==0
    F.check(Path(build['root']),build['outputs'])
    assert F.tree(W/'experiments/xrt/runtime')==build['runtime'] and F.tree(W/'experiments/xrt/gen')==build['generated']
    assert F.read(O/'gui-regressions.json')['passed'] and F.read(O/'fixture-results.json')['passed'] and F.read(O/'observer-qualified.json')['passed']
    exe=Path(build['root'])/'xrt_ucc.exe'
    previous=F.PREP
    # Keep every PE/PDB mapping assertion, thunk check, register check and stop
    # instruction assertion; replace only the identities and file locations.
    plan=(previous/'candidate_plan.py').read_text()
    plan=plan.replace(str(W/'experiments/xrt/build/renderer-init-preparation-20261027-01/xrt_ucc.exe').replace('\\','\\\\'),str(exe).replace('\\','\\\\'))
    plan=plan.replace('43fcf4f1f58043561619cdee969c2822f8bfe57fcaa9b2605d379f43cb921001',build['binary_sha256'])
    plan=plan.replace('261e44108f215fb4895c4722e017e72abcd9d9f36beb378393be988c164113d6',build['pdb_sha256'])
    assert str(exe).replace('\\','\\\\') in plan
    (O/'candidate_plan.py').write_text(plan)
    genuine=(previous/'bounded_genuine.py').read_text()
    genuine=genuine.replace("L.SB=W/'sandbox_cmp/renderer-init-preparation-20261027-01'","L.SB=W/'sandbox_cmp/getobject-recovery-20261028-01'")
    assert genuine.count('return Observe(symbols)')==1
    genuine=genuine.replace('return Observe(symbols)',"capture=Observe(symbols)\n    from observer_evidence import install\n    return install(capture,out)")
    assert genuine.count('return capture.run(cmd,**kw)')==1
    genuine=genuine.replace('return capture.run(cmd,**kw)',"kw['timeout']=min(float(kw.get('timeout',60)),60.0)\n            return capture.run(cmd,**kw)")
    (O/'bounded_genuine.py').write_text(genuine)
    shutil.copy2(HERE/'observer_evidence.py',O/'observer_evidence.py')
    shutil.copy2(HERE/'owner.py',O/'bounded_owner.py')
    command=f'@echo off\nsetlocal\ncd /d "{W}"\n"{F.PY}" -B -I "{O}/bounded_owner.py" --execute-owner-authorized\nexit /b %errorlevel%\n'
    (O/'owner-genuine-getobject.cmd').write_text(command)
    # Import resolution occurs in this separate preparation interpreter, without
    # putting the project fixture's phase.py under the inherited module name.
    sys.path.insert(0,str(O));import candidate_plan as P
    resolved=P.resolve()
    assert resolved['static_mapping_verified'] and resolved['guest_stop']==0x696f292
    assert resolved['sha256']==build['binary_sha256'] and resolved['pdb_sha256']==build['pdb_sha256']
    F.save(O/'candidate-debugger-plan.json',resolved)
    # Construct the exact final observer, but do not create a process. Its strict
    # assertion body and permanent hardware-slot algorithm remain byte-identical.
    import bounded_genuine as G
    checkdir=O/'observer-construction-test';checkdir.mkdir()
    capture=G.observer(checkdir,resolved,lambda tag:None)
    assert capture.created==0 and capture._fatal_evidence_installed
    assert Path(capture._fatal_evidence_directory)==checkdir.resolve()
    capture.log('offline_construction',game_launched=False)
    assert F.read(checkdir/'debug-observations.jsonl')['output_directory']==str(checkdir.resolve())
    baseline=F.read(previous/'preservation.json')
    # Bind all inherited observer, owner and launcher dependencies in their
    # existing locations, including the consumed sources, without editing them.
    entries=F.read(previous/'preserved-manifest.json')
    entries={rel:F.sha(W/rel) for rel in entries}
    for directory in [HERE,W/'experiments/xrt/runtime',W/'experiments/xrt/gen',W/'tools']:
        for f in directory.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts:entries[f.relative_to(W).as_posix()]=F.sha(f)
    for rel in ['session-aware-136-20261026-01','d3d8-scalar-init-20261025-01','d3d8-genuine-20261025-03','current-display-d3d8-20261025-01']:
        for f in (W/'out/recovery'/rel).glob('*.py'):entries[f.relative_to(W).as_posix()]=F.sha(f)
    F.save(O/'current-sources.json',entries)
    F.save(O/'pinned-inputs.json',baseline['pinned'])
    F.save(O/'readiness.json',dict(prepared=True,gui_acceptance_complete=True,observer_live_qualified=True,
        maximum_genuine_sessions=1,watchdog_ms=60000,retry=False,guest_stop='0x0696f292',instruction_must_not_execute=True,
        genuine_game_launched=False,consumed_session_reused=False,owner_launch_required=True,
        strict_x87='FAILED; retained separately',strict_wndproc_equality='FAILED; retained separately',
        renderer_evidence='previous owner acceptance preserved; no new renderer execution or method implementation'))
    names=['candidate_plan.py','candidate-debugger-plan.json','bounded_genuine.py','bounded_owner.py','observer_evidence.py','owner-genuine-getobject.cmd',
        'build.json','readiness.json','pinned-inputs.json','current-sources.json','fixture-results.json','gui-regressions.json','observer-qualified.json','preservation.json','dependency-verification.json']
    F.save(O/'launcher-identities.json',{n:F.sha(O/n) for n in names})
    for f in O.glob('*.py'):ast.parse(f.read_text())
    owner=F.load('wm_owner_offline_validation',O/'bounded_owner.py')
    inputs=owner.verify();assert inputs['assets']==F.read(O/'preservation.json')['protected_assets']
    assert not (O/'genuine-owner-run').exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    F.save(O/'continuation-prepared.json',dict(passed=True,plan=resolved,offline_final_observer_constructed=True,owner_inputs_verified=True,
        live_non_game_debugger_qualification=F.read(O/'observer-qualified.json'),maximum_genuine_sessions=1,watchdog_ms=60000,retry=False,genuine_game_launched=False))
    print('OWNER CONTINUATION PREPARED; NO GAME LAUNCHED',flush=True)
if __name__=='__main__':main()
