"""Fresh owner-only package with unchanged permanent-stop and renderer assertions."""
import ast,importlib.util,json,shutil,subprocess,sys,zipfile
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('viewport_preparation_phase_isolated',H/'phase.py')
P=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(P)
W,O,B,OLD=P.W,P.O,P.B,P.OLD
SB=W/'sandbox_cmp/viewport-getobject-20261028-01'
def archive(name,entries):
    path=O/name
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for rel,h in sorted(entries.items()):
            assert P.sha(W/rel)==h;z.write(W/rel,rel)
    with zipfile.ZipFile(path) as z:
        for rel,h in entries.items():
            with z.open(rel) as f:assert P.C.hashlib.file_digest(f,'sha256').hexdigest()==h
    return dict(path=name,sha256=P.sha(path),files=len(entries),readback_verified=True)

def integrity():
    preserved=P.read(O/'preservation.json');P.check(W,preserved['consumed_evidence'])
    prior=preserved['inherited_exact_build'];P.check(Path(prior['root']),prior['outputs'])
    sb=preserved['complete_sandbox'];assert P.tree(Path(sb['root']))==sb['files']
    assert P.metadata(Path(sb['root']))==P.read(P.DIAG/'sandbox-metadata.json')
    before=P.read(O/'source-before.json')
    allowed=['experiments/xrt/runtime/hle_gui.c','experiments/xrt/runtime/hle_gui_classes.inc','experiments/xrt/tests/viewport_getobject/phase.py','experiments/xrt/CURRENT_STATUS.md']
    P.check(W,{k:h for k,h in before.items() if k not in allowed})
    changed=[k for k,h in before.items() if P.sha(W/k)!=h]
    assert set(changed)<=set(allowed),changed
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W)==(O/'git-head.txt').read_bytes()
    assert subprocess.check_output(['git','diff','--cached','--binary'],cwd=W)==(O/'git-staged.txt').read_bytes()
    build=P.read(O/'build.json');P.check(Path(build['root']),build['outputs'])
    fixtures=P.read(O/'fixture-build-identities.json');assert fixtures['passed'] and fixtures['all_lifted_DLL_pairs_verified']
    P.check(Path(fixtures['root']),fixtures['files'])
    assert P.tree(W/'experiments/xrt/runtime')==build['runtime'] and P.tree(W/'experiments/xrt/gen')==build['generated']
    assert build['compiled_objects']==279 and build['reused_objects']==0
    rsp=Path(build['root'])/'link-objects.rsp';objects=[Path(s.strip('"')) for s in rsp.read_text().splitlines() if s.strip()]
    assert len(objects)==len(set(objects))==279 and all(p.is_file() and p.is_relative_to(Path(build['root'])/'obj') for p in objects)
    sys.path.insert(0,str(W/'tools/xrt'));import asset_boundary as A,graphics_backend as G
    assert A.verify()==preserved['protected_assets']
    pinned=P.read(OLD/'pinned-inputs.json')
    for path,h in pinned['pinned_driver_files'].items():assert P.sha(path)==h
    for arch in ['x86','x64']:G.verified_pair(arch)
    helper=pinned['inputs']['helper'];assert P.sha(helper['path'])==helper['sha256']
    strict=P.read(OLD/'strict-failures-retained.json')
    assert strict['x87']==strict['wndproc_equality']=='FAILED' and strict['original_assertions_unchanged']
    assert P.sha(strict['source'])==strict['sha256']
    for path,h in strict['findings']['preserved_sources'].items():assert P.sha(path)==h
    for marker in ['renderer-continuation-20261028-01','getobject-recovery-20261028-01','renderer-init-preparation-20261027-01']:
        assert (W/'out/recovery'/marker/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    return dict(passed=True,historical_files=len(preserved['consumed_evidence']),source_files=len(before),protected_assets_verified=True,
        exact_old_build_preserved=True,complete_consumed_sandbox_bytes_and_metadata_verified=True,pinned_dependencies_verified=True,strict_failures_retained=True)

def dependencies():
    source=W/'out/recovery/d3d8-clear-present-20261025-01/dependency-identities.json';d=P.read(source)
    for key in ['toolchain','system_inputs','libraries']:
        for path,h in d[key].items():assert P.sha(path)==h,(key,path)
    for path,entries in d['headers'].items():assert P.tree(Path(path))==entries,path
    P.save(O/'dependency-verification.json',dict(passed=True,source=str(source),sha256=P.sha(source),
        toolchain=len(d['toolchain']),system_inputs=len(d['system_inputs']),libraries=len(d['libraries']),headers=sum(len(v) for v in d['headers'].values())))

def main():
    assert not sys.flags.optimize and not SB.exists()
    verified=integrity();dependencies()
    for name in ['fixture-audit.json','focus-cpu-audit.json','gui-regressions.json','dialog-regression.json']:assert P.read(O/name)['passed']
    build=P.read(O/'build.json');prior=P.read(OLD/'build.json');exe=Path(build['root'])/'xrt_ucc.exe'
    plan=(OLD/'candidate_plan.py').read_text()
    replacements=[(str(Path(prior['root'])/'xrt_ucc.exe').replace('\\','\\\\'),str(exe).replace('\\','\\\\')),
        (prior['binary_sha256'],build['binary_sha256']),(prior['pdb_sha256'],build['pdb_sha256'])]
    for before,after in replacements:assert plan.count(before)==1;plan=plan.replace(before,after)
    (O/'candidate_plan.py').write_text(plan)
    genuine=(OLD/'bounded_genuine.py').read_text()
    before="L.SB=W/'sandbox_cmp/renderer-continuation-20261028-01'";after="L.SB=W/'sandbox_cmp/viewport-getobject-20261028-01'"
    assert genuine.count(before)==1;genuine=genuine.replace(before,after)
    (O/'bounded_genuine.py').write_text(genuine)
    for name in ['observer_evidence.py','strict-failures-retained.json','owner-evidence-audit.json']:
        shutil.copy2(OLD/name,O/name)
    pinned=P.read(OLD/'pinned-inputs.json');pinned['inputs']['binary_sha256']=build['binary_sha256'];pinned['inputs']['pdb_sha256']=build['pdb_sha256']
    P.save(O/'pinned-inputs.json',pinned)
    owner=(OLD/'bounded_owner.py').read_text().replace('renderer continuation after verified InitAudio probes','registered-window WM_GETOBJECT continuation')
    # Verification is extended; launch count, environment checks and cleanup are inherited.
    needle="    return dict(assets=assets,helper=helper)"
    assert owner.count(needle)==1
    owner=owner.replace(needle,"    extra=load('viewport_owner_readonly_integrity',W/'experiments/xrt/tests/viewport_getobject/prepare.py')\n    extra.integrity()\n"+needle)
    (O/'bounded_owner.py').write_text(owner)
    (O/'owner-genuine-viewport.cmd').write_text(f'@echo off\nsetlocal\ncd /d "{W}"\n"{P.F.PY}" -B -I "{O / "bounded_owner.py"}" --execute-owner-authorized\nexit /b %errorlevel%\n')
    sys.path.insert(0,str(O));import candidate_plan
    resolved=candidate_plan.resolve();assert resolved['static_mapping_verified'] and resolved['guest_stop']==0x696f292
    P.save(O/'candidate-debugger-plan.json',resolved)
    # Fresh live non-game fatal probes and independent execute-stop selftest.
    fixture=P.load('viewport_observer_qualification',W/'experiments/xrt/tests/postsplash_recovery/fixtures.py')
    fixture.P.O=O;fixture.F.B=W/'experiments/xrt/build/postsplash-recovery-20261028-01';fixture.debugger()
    import bounded_genuine
    construction=O/'offline-observer-construction';construction.mkdir()
    capture=bounded_genuine.observer(construction,resolved,lambda tag:None)
    assert capture.created==0 and capture._fatal_evidence_installed
    assert Path(capture._fatal_evidence_directory)==construction.resolve()
    capture.log('offline_final_observer_construction',game_launched=False)
    P.save(O/'observer-lineage.json',dict(passed=True,sole_genuine_launcher_change='fresh sandbox path',
        renderer_assertions_unchanged=True,permanent_hardware_stop_algorithm_unchanged=True,watchdog_ms=60000,maximum_sessions=1,retry=False,
        strict_x87='FAILED; retained separately',strict_wndproc_equality='FAILED; retained separately',genuine_sessions_launched=0))
    sources={rel:P.sha(W/rel) for rel in P.read(OLD/'current-sources.json')}
    for prefix in ['experiments/xrt/runtime','experiments/xrt/tests','tools']:
        sources.update({p.relative_to(W).as_posix():P.sha(p) for p in P.C.files(W/prefix)})
    sources['experiments/xrt/CURRENT_STATUS.md']=P.sha(W/'experiments/xrt/CURRENT_STATUS.md')
    P.save(O/'current-sources.json',sources)
    P.save(O/'pending-source-archive.json',archive('pending-source-state.zip',sources))
    for path in O.glob('*.py'):ast.parse(path.read_text())
    P.save(O/'readiness.json',dict(prepared=True,genuine_launch_ready=True,owner_probe_verified=True,gui_acceptance_complete=True,observer_live_qualified=True,
        maximum_genuine_sessions=1,watchdog_ms=60000,retry=False,guest_stop='0x0696f292',instruction_must_not_execute=True,
        genuine_game_launched=False,owner_launch_required=True,fresh_sandbox=str(SB),strict_compatibility='FAILED',
        strict_x87='FAILED; retained separately',strict_wndproc_equality='FAILED; retained separately',
        retained_accessibility_boundary='OBJID_QUERYCLASSNAMEIDX, wp=0 remains unsupported; any occurrence stops the attempt'))
    P.save(O/'launcher-identities.json',{p.relative_to(O).as_posix():P.sha(p) for p in P.C.files(O) if 'source-before' not in p.parts})
    package=P.load('viewport_fresh_owner_verification',O/'bounded_owner.py');package.verify()
    state=candidate_plan.V.state();assert not state['processes']
    with candidate_plan.V.R.CaseLock('level'),candidate_plan.V.R.CaseLock('graphics-client-session'):pass
    assert not SB.exists() and not (O/'genuine-owner-run').exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    verified=integrity();P.check(W,sources)
    P.save(O/'final-integrity.json',dict(**verified,ready_for_owner=True,fresh_compiled_objects=279,reused_objects=0,
        PE_PDB_stop_mapping_verified=True,observer_qualified=True,processes_empty=True,locks_reacquired=True,fresh_sandbox_not_created=True,genuine_sessions_launched=0))
    print('FRESH OWNER PACKAGE READY; ZERO GENUINE LAUNCHES',flush=True)
def recover_preparation():
    """Preserve the unconsumed first preparation and repair only its namespace binding."""
    assert not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists() and not (O/'genuine-owner-run').exists()
    assert not (O/'final-integrity.json').exists()
    backup=O/'preparation-v1';backup.mkdir()
    names=['candidate_plan.py','candidate-debugger-plan.json','bounded_genuine.py','bounded_owner.py','observer_evidence.py',
        'strict-failures-retained.json','owner-evidence-audit.json','pinned-inputs.json','owner-genuine-viewport.cmd',
        'observer-tests.json','observer-lineage.json','current-sources.json','pending-source-archive.json','readiness.json','launcher-identities.json']
    for name in names:shutil.copy2(O/name,backup/name)
    shutil.copy2(O/'source-before/experiments/xrt/tests/viewport_getobject/phase.py',backup/'initial-phase.py')
    (backup/'DIAGNOSIS.txt').write_text('Offline preparation only; zero genuine sessions. FileNotFoundError for offline-observer-construction/preservation.json arose because a generic import named phase was shared with inherited observer dependencies. No hash mismatch or data corruption occurred. The original partial package records are retained here; its pending-source-state.zip remains untouched at the phase root. Isolated spec imports remove that namespace collision.\n')
    integrity()
    assert str(H) not in sys.path
    sys.path.insert(0,str(O));import candidate_plan
    resolved=candidate_plan.resolve();assert resolved==P.read(O/'candidate-debugger-plan.json')
    qualification=O/'observer-qualification-v2';qualification.mkdir()
    fixture=P.load('viewport_observer_namespace_requalification',W/'experiments/xrt/tests/postsplash_recovery/fixtures.py')
    fixture.P.O=qualification;fixture.F.B=W/'experiments/xrt/build/postsplash-recovery-20261028-01';fixture.debugger()
    (O/'observer-tests.json').write_text(json.dumps(P.read(qualification/'observer-tests.json'),indent=2))
    import bounded_genuine
    construction=O/'offline-observer-construction-v2';construction.mkdir()
    capture=bounded_genuine.observer(construction,resolved,lambda tag:None)
    assert capture.created==0 and capture._fatal_evidence_installed
    assert Path(capture._fatal_evidence_directory)==construction.resolve()
    assert P.O==O and Path(candidate_plan.S.A.__file__).resolve()!=H/'phase.py'
    capture.log('offline_final_observer_construction',game_launched=False)
    P.save(O/'observer-namespace-audit.json',dict(passed=True,phase_helper=str(Path(P.__file__).resolve()),
        inherited_observer_dependency=str(Path(candidate_plan.S.A.__file__).resolve()),
        helper_output_directory_unchanged=True,output_directory=str(construction),genuine_sessions_launched=0))
    lineage=P.read(O/'observer-lineage.json');lineage['namespace_isolated']=True
    (O/'observer-lineage.json').write_text(json.dumps(lineage,indent=2))
    sources={rel:P.sha(W/rel) for rel in P.read(OLD/'current-sources.json')}
    for prefix in ['experiments/xrt/runtime','experiments/xrt/tests','tools']:
        sources.update({p.relative_to(W).as_posix():P.sha(p) for p in P.C.files(W/prefix)})
    sources['experiments/xrt/CURRENT_STATUS.md']=P.sha(W/'experiments/xrt/CURRENT_STATUS.md')
    (O/'current-sources.json').write_text(json.dumps(sources,indent=2))
    archived=archive('pending-source-state-v2.zip',sources)
    (O/'pending-source-archive.json').write_text(json.dumps(archived,indent=2))
    ready=P.read(O/'readiness.json');ready['observer_namespace_isolated']=True
    (O/'readiness.json').write_text(json.dumps(ready,indent=2))
    entries={p.relative_to(O).as_posix():P.sha(p) for p in P.C.files(O)
        if 'source-before' not in p.parts and p.name!='launcher-identities.json'}
    (O/'launcher-identities.json').write_text(json.dumps(entries,indent=2))
    package=P.load('viewport_requalified_owner_verification',O/'bounded_owner.py');package.verify()
    state=candidate_plan.V.state();assert not state['processes']
    with candidate_plan.V.R.CaseLock('level'),candidate_plan.V.R.CaseLock('graphics-client-session'):pass
    assert not SB.exists() and not (O/'genuine-owner-run').exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    verified=integrity();P.check(W,sources)
    P.save(O/'final-integrity.json',dict(**verified,ready_for_owner=True,fresh_compiled_objects=279,reused_objects=0,
        PE_PDB_stop_mapping_verified=True,observer_qualified=True,observer_namespace_isolated=True,
        first_preparation_preserved=True,processes_empty=True,locks_reacquired=True,fresh_sandbox_not_created=True,genuine_sessions_launched=0))
    print('NAMESPACE-ISOLATED OWNER PACKAGE READY; ZERO GENUINE LAUNCHES',flush=True)
if __name__=='__main__':
    (recover_preparation if sys.argv[1:]==['recover-preparation'] else main)()
