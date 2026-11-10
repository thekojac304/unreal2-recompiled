"""Prepare a fresh owner-only package. Genuine execution is deliberately absent."""
import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('continuation_checks', HERE / 'checks.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
W, PRIOR = C.W, C.PRIOR
O = W / 'out/recovery/renderer-continuation-20261028-01'
SB = W / 'sandbox_cmp/renderer-continuation-20261028-01'


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def archive(path, entries):
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as target:
        for rel, expected in sorted(entries.items()):
            assert C.sha(W / rel) == expected, rel
            target.write(W / rel, rel)
    with zipfile.ZipFile(path) as target:
        for rel, expected in entries.items():
            with target.open(rel) as stream:
                assert C.hashlib.file_digest(stream, 'sha256').hexdigest() == expected, rel
    return dict(path=str(path), sha256=C.sha(path), files=len(entries), readback_verified=True)


def main():
    assert not sys.flags.optimize
    assert not SB.exists()
    verified = C.inputs()
    O.mkdir()
    save(O / 'owner-evidence-audit.json', verified['owner_evidence'])
    save(O / 'input-verification.json', verified)
    print('OWNER RECORDS AND INPUTS VERIFIED', flush=True)
    # Bind all retained inputs, including the owner result added after the prior
    # package was sealed. Preserve the old package without updating its manifests.
    preserved = C.read(PRIOR / 'preservation.json')
    history = dict(preserved['consumed_evidence'])
    history.update({p.relative_to(W).as_posix(): C.sha(p) for p in C.files(PRIOR)})
    for marker in (W / 'out/recovery').rglob('GENUINE-ATTEMPT-CONSUMED.json'):
        history[marker.relative_to(W).as_posix()] = C.sha(marker)
    save(O / 'historical-identities.json', history)
    sources = C.read(PRIOR / 'current-sources.json')
    sources.update({p.relative_to(W).as_posix(): C.sha(p) for p in C.files(HERE)})
    save(O / 'current-sources.json', sources)
    git = {}
    for name, args in [('head', ['rev-parse', 'HEAD']),
                       ('status', ['status', '--porcelain=v1', '-uall']),
                       ('staged', ['diff', '--cached', '--binary']),
                       ('unstaged', ['diff', '--binary'])]:
        data = subprocess.check_output(['git', *args], cwd=W)
        (O / ('git-' + name + '.txt')).write_bytes(data)
        git[name] = C.sha(O / ('git-' + name + '.txt'))
    pending_archive = archive(O / 'pending-source-state.zip', sources)
    owner_files = {p.relative_to(W).as_posix(): C.sha(p)
                   for p in C.files(PRIOR / 'owner-init-audio-run')}
    owner_archive = archive(O / 'owner-probe-evidence.zip', owner_files)
    save(O / 'preservation.json', dict(passed=True, protected_assets=verified['assets'],
         consumed_evidence=history, inherited_archives=preserved['archives'],
         inherited_archive_root=str(PRIOR), source_archive=pending_archive,
         owner_archive=owner_archive, git=git, historical_paths_reused=False,
         genuine_sessions_launched=0))
    print('PENDING SOURCE AND OWNER EVIDENCE ARCHIVED / READBACK VERIFIED', flush=True)

    for name in ['candidate_plan.py', 'candidate-debugger-plan.json', 'build.json',
                 'observer_evidence.py', 'strict-failures-retained.json']:
        shutil.copy2(PRIOR / name, O / name)
    assert C.sha(O / 'observer_evidence.py') == C.sha(W / 'experiments/xrt/tests/postsplash_recovery/observer_evidence.py')
    pinned = C.read(PRIOR / 'pinned-inputs.json')
    # The inherited file describes an older experiment's executable. The fresh
    # descriptor identifies the exact GetObject candidate instead.
    pinned['inputs']['binary_sha256'] = verified['binary_sha256']
    pinned['inputs']['pdb_sha256'] = verified['pdb_sha256']
    pinned['active_gpu_driver_verified'] = True
    pinned['active_display_gate'] = 'saved owner evidence PASS; must reobserve at owner launch'
    pinned['owner_probe_baseline'] = verified['owner_evidence']['baseline']
    save(O / 'pinned-inputs.json', pinned)
    old_genuine = (PRIOR / 'bounded_genuine.py').read_text()
    old_path = "L.SB=W/'sandbox_cmp/postsplash-recovery-20261028-01'"
    new_path = "L.SB=W/'sandbox_cmp/renderer-continuation-20261028-01'"
    assert old_genuine.count(old_path) == 1
    genuine = old_genuine.replace(old_path, new_path)
    (O / 'bounded_genuine.py').write_text(genuine, encoding='utf-8')
    assert genuine.replace(new_path, old_path) == old_genuine
    save(O / 'observer-lineage.json', dict(passed=True,
         inherited_launcher=str(PRIOR / 'bounded_genuine.py'),
         inherited_launcher_sha256=C.sha(PRIOR / 'bounded_genuine.py'),
         sole_launcher_change='fresh sandbox destination',
         corrected_observer_sha256=C.sha(O / 'observer_evidence.py'),
         runtime_or_helper_changes=False, renderer_assertions_changed=False,
         permanent_hardware_stop_algorithm_changed=False, watchdog_ms=60000,
         production_transport_timeout_ms=10000, maximum_genuine_sessions=1, retry=False))
    owner = (PRIOR / 'bounded_owner.py').read_text()
    owner = owner.replace('Owner-launched, one-session WM_GETOBJECT recovery continuation.',
                          'Owner-launched, one-session renderer continuation after verified InitAudio probes.')
    needle = "    return dict(assets=assets,helper=helper)"
    assert owner.count(needle) == 1
    owner = owner.replace(needle, """    assert r['genuine_launch_ready'] and r['owner_probe_verified']
    checks=load('fresh_continuation_readonly_checks',W/'experiments/xrt/tests/renderer_continuation/checks.py')
    checks.owner_evidence()
    return dict(assets=assets,helper=helper)""")
    start = "    assert (O/'owner-init-audio-run/result.json').exists(), 'Owner non-game InitAudio prerequisite is pending; no game launch'\n    assert read(O/'owner-init-audio-run/result.json')['passed'], 'Owner fixture must pass first'\n"
    assert owner.count(start) == 1
    owner = owner.replace(start, '')
    needle = "        if baseline is None:baseline=f"
    assert owner.count(needle) == 1
    owner = owner.replace(needle, "        assert f==read(O/'owner-evidence-audit.json')['baseline'], ('owner probe environment changed; stop and preserve',tag)\n" + needle)
    (O / 'bounded_owner.py').write_text(owner, encoding='utf-8')
    (O / 'owner-genuine-continuation.cmd').write_text(
        f'@echo off\nsetlocal\ncd /d "{W}"\n"{W / ".venv/Scripts/python.exe"}" -B -I "{O / "bounded_owner.py"}" --execute-owner-authorized\nexit /b %errorlevel%\n')

    # Reuse the already verified non-game fixture EXE/PDB. Only debugger probes
    # run here; the native/IPC audio investigation is not repeated.
    fixture = C.load('fresh_continuation_observer_qualification', W / 'experiments/xrt/tests/postsplash_recovery/fixtures.py')
    fixture.P.O = O
    fixture.F.B = W / 'experiments/xrt/build/postsplash-recovery-20261028-01'
    fixture.debugger()
    cmd = [W / '.venv/Scripts/python.exe', '-B', '-I', '-m', 'unittest', 'discover',
           '-s', W / 'experiments/xrt/tests/postsplash_recovery', '-p', 'test_observer_evidence.py', '-v']
    unit = subprocess.run(list(map(str, cmd)), cwd=W, capture_output=True, timeout=20)
    (O / 'observer-unit.stdout.txt').write_bytes(unit.stdout)
    (O / 'observer-unit.stderr.txt').write_bytes(unit.stderr)
    assert unit.returncode == 0 and b'Ran 10 tests' in unit.stderr and b'\nOK' in unit.stderr
    save(O / 'observer-unit.json', dict(passed=True, tests=10, exit=unit.returncode,
         observer_sha256=C.sha(O / 'observer_evidence.py')))
    for path in O.glob('*.py'):
        ast.parse(path.read_text())
    sys.path.insert(0, str(O))
    import candidate_plan
    plan = candidate_plan.resolve()
    assert plan == C.read(O / 'candidate-debugger-plan.json')
    assert plan['static_mapping_verified'] and not plan['client_launched']
    import bounded_genuine
    construction = O / 'offline-observer-construction'
    construction.mkdir()
    capture = bounded_genuine.observer(construction, plan, lambda tag: None)
    assert capture.created == 0 and capture._fatal_evidence_installed
    assert Path(capture._fatal_evidence_directory) == construction.resolve()
    capture.log('offline_final_observer_construction', game_launched=False)
    save(O / 'readiness.json', dict(prepared=True, genuine_launch_ready=True,
         owner_probe_verified=True, gui_acceptance_complete=True, observer_live_qualified=True,
         maximum_genuine_sessions=1, watchdog_ms=60000, retry=False,
         guest_stop='0x0696f292', instruction_must_not_execute=True,
         genuine_game_launched=False, owner_launch_required=True, strict_compatibility='FAILED',
         strict_x87='FAILED; retained separately', strict_wndproc_equality='FAILED; retained separately',
         binary_rebuilt=False, runtime_or_helper_changes=False,
         fresh_sandbox=str(SB), owner_environment_rechecked_before_and_during_launch=True))
    names = [p.relative_to(O).as_posix() for p in C.files(O)]
    save(O / 'launcher-identities.json', {name: C.sha(O / name) for name in names})
    package = C.load('fresh_owner_package_verification', O / 'bounded_owner.py')
    package.verify()
    # Read-only final checks verify all previous files, sources, build outputs,
    # sandbox bytes/metadata, protected assets and the exact owner evidence again.
    C.inputs()
    C.check(W, history)
    C.check(W, sources)
    for name, args in [('head', ['rev-parse', 'HEAD']), ('status', ['status', '--porcelain=v1', '-uall']),
                       ('staged', ['diff', '--cached', '--binary']), ('unstaged', ['diff', '--binary'])]:
        assert subprocess.check_output(['git', *args], cwd=W) == (O / ('git-' + name + '.txt')).read_bytes()
    state = candidate_plan.V.state()
    assert not state['processes']
    with candidate_plan.V.R.CaseLock('level'), candidate_plan.V.R.CaseLock('graphics-client-session'):
        pass
    save(O / 'preparation-cleanup.json', dict(passed=True, state=state, locks_reacquired=True,
         genuine_sessions_launched=0))
    assert not SB.exists() and not (O / 'genuine-owner-run').exists()
    assert not (O / 'GENUINE-ATTEMPT-CONSUMED.json').exists()
    save(O / 'final-integrity.json', dict(passed=True, owner_probe_independently_verified=True,
         historical_files_verified=len(history), source_files_verified=len(sources),
         exact_279_object_build_verified=True, exact_PE_PDB_stop_mapping_verified=True,
         protected_assets_verified=True, pinned_DXVK_and_helper_verified=True,
         observer_unit_tests=10, live_non_game_fatal_cases=2, hardware_execute_stop_selftest=True,
         final_observer_constructed_offline=True, strict_failures_retained=True,
         original_pending_changes_preserved=True, fresh_sandbox_not_created=True,
         genuine_sessions_launched=0, ready_for_owner=True))
    report = f'''Unreal II genuine renderer continuation — October 28, 2026 (US Eastern)

READY for one owner-launched experimental continuation toward SetRenderState(136,1).
Preparation launched zero genuine sessions. No original installation or save was modified.

Owner InitAudio evidence independently verified from raw per-run records:
  unguarded native S_OK / real object / 265 ms / exit 0;
  guarded native S_OK / real object / 250 ms / exit 0;
  production IPC S_OK / real object / 250 ms / exit 0.
Sequence 4: op 6, id 2, status 0, result 00000000, out 3, type 3.
Release/shutdown replies, cleanup, initial/final settings and locks match; processes empty.
Three owner environment observations pass the retained physical NVIDIA DisplayPort,
driver 32.0.16.2101, WinSta0/Default and receiving-input gates and match one fingerprint.
The launcher rechecks that fingerprint; environment drift stops the attempt.
The production DirectMusic deadline remains 10000 ms. No helper/runtime changes.

Candidate reused, without rebuilding or relinking:
  {plan['executable']}
  EXE SHA-256 {plan['sha256']}
  PDB SHA-256 {plan['pdb_sha256']}
All 279 fresh-build objects and 284 output files match the validated GetObject build;
31 runtime and 299 generated source files match its lineage. Pinned x86/x64 DXVK
3.1.1, helper, driver files, protected input trees and consumed sandbox bytes/metadata pass.
Permanent stop: native RVA {plan['stop_rva']:#x}, bytes {plan['stop_bytes']}, before guest
0x0696f292 and its LEA effect. The original hardware-slot/readback, callback/stack,
CreateDevice, Clear/Present and eight ordered scalar-state assertions are unchanged.
SetMaterial and unsupported methods/arguments stay guarded. Any fatal stops execution;
the corrected observer copies bounded raw %s bytes while the debug event is pending.
Ten observer unit tests, two fresh non-game live fatal probes and a fresh independent
terminate-before-instruction hardware test pass. The final observer was constructed offline.

Strict compatibility is still FAILED. The known x87 and complete WNDPROC equality
failures are separately retained in strict-failures-retained.json without assertion waivers.
This preparation establishes no new engine/world tick, frame or renderer milestone.

Owner PowerShell command (one genuine session maximum, 60-second watchdog, no retry):
  & "{O / 'owner-genuine-continuation.cmd'}"

Fresh sandbox reserved: {SB}
It is created only by the owner's launch. The fresh run directory and exclusive consumed
marker prohibit reuse; all prior markers/sessions remain intact. No automatic launch follows
preparation or the saved audio probes. On any stop preserve this entire package and run.

Preservation: {len(history)} historical identities verified; {len(sources)} source identities
and the pending Git state archived/readback-verified. Existing complete sandbox, exact build
and consumed evidence archives are retained in their historical locations and hash-verified.
See owner-evidence-audit.json, input-verification.json, observer-lineage.json,
observer-tests.json, final-integrity.json and preparation-cleanup.json for the audit.
'''
    (O / 'REPORT.txt').write_text(report, encoding='utf-8')
    save(O / 'artifact-manifest.json', C.tree(O))
    print('READY: FRESH OWNER CONTINUATION PREPARED; NO GENUINE GAME LAUNCHED', flush=True)


if __name__ == '__main__':
    main()
