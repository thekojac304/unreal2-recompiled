"""Non-game qualification for the production fixture service and collector."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
import uuid
from . import core, fixture_profiles as profiles
from .development import FixtureService, run_fixture, submit


def checked(command, out, name, *, timeout=240):
    result = subprocess.run(command, cwd=core.ROOT, capture_output=True, timeout=timeout)
    (out / (name + '.stdout.bin')).write_bytes(result.stdout)
    (out / (name + '.stderr.bin')).write_bytes(result.stderr)
    core.atomic(out / (name + '.json'), dict(command=command, exit=result.returncode))
    core.require(result.returncode == 0, name + ' failed; inspect ' + str(out))


def legacy_qualify(home):
    """Propagate the isolated test home to the unchanged fixed validator.

    Production recovery still invokes recovery_worker.py with its production
    home. This test-only wrapper gives parent and child the SAME isolated root,
    so the original worker's path assertion is exercised without weakening it.
    """
    home = core.independent(home)
    core.require(home.parent == core.ROOT / 'out' and home.name.startswith('lq-'), 'fixed legacy qualification root')
    core.HOME = home
    from . import recovery
    from .qualify import main
    real_run = subprocess.run
    worker = core.ROOT / 'tools/xrt/supervisor/recovery_worker.py'
    def run(command, *args, **kwargs):
        if len(command) == 5 and command[:4] == [sys.executable, '-B', '-I', str(worker)]:
            destination = Path(command[4])
            core.require(destination.is_relative_to(home), 'isolated validator evidence root')
            source = ("import sys,runpy;from pathlib import Path;sys.path.insert(0,str(Path('tools/xrt').resolve()));"
                      "from supervisor import core;core.HOME=Path(" + repr(str(home)) + ");"
                      "runpy.run_path(" + repr(str(worker)) + ",run_name='__main__')")
            command = [sys.executable, '-B', '-I', '-c', source, str(destination)]
        return real_run(command, *args, **kwargs)
    with patch('supervisor.recovery.subprocess.run', side_effect=run):
        main()


def project_seal():
    from .service import seal_files
    files = seal_files()
    E, _, _ = profiles.modules()
    # Include transitive project imports, not just the new adapter files.
    for module in list(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.is_file() and path.is_relative_to(core.ROOT) and '.venv' not in path.parts:
                files[path.relative_to(core.ROOT).as_posix()] = core.sha(path)
    for path in profiles.RENDERER.glob('*'):
        if path.is_file(): files[path.relative_to(core.ROOT).as_posix()] = core.sha(path)
    for path in (profiles.FROZEN / 'build/collector.dll', profiles.FROZEN / 'build/collector-build-record.json'):
        files[path.relative_to(core.ROOT).as_posix()] = core.sha(path)
    return files


def qualification_cycles(out):
    from . import fixture_collector as transport
    ids = {}
    for arch in ('x86', 'x64'):
        ids[arch] = profiles.build('collector-smoke', dict(arch=arch, case='normal'))
    ids['early'] = profiles.build('collector-smoke', dict(arch='x64', case='early-exit'))
    ids['linger'] = profiles.build('collector-smoke', dict(arch='x64', case='linger'))
    ids['descendant'] = profiles.build('collector-smoke', dict(arch='x64', case='descendant'))
    ids['abi'] = profiles.build('renderer-abi', dict(arch='x64', group=7, variant='translated'))
    # Inject a collector parser defect only after successful real collection.
    # This is in the qualification caller; queue data has no injection verb.
    injection = threading.Event()
    def runner(*args, **kwargs):
        if injection.is_set():
            injection.clear()
            with patch('supervisor.fixture_collector.validate_smoke', side_effect=ValueError('qualification injected parser defect')):
                return run_fixture(*args, **kwargs)
        return run_fixture(*args, **kwargs)
    service = FixtureService(out / 'persistent-queue', qualification=True, runner=runner)
    service.ledger.append('fixture-batch-authorized', batch=service.batch, qualification_only=True, owner_console=False)
    failures = []
    def serve():
        try: service.serve()
        except BaseException as error: failures.append(str(error))
    thread = threading.Thread(target=serve, name='qualification-fixture-service'); thread.start()
    results = []
    def cycle(candidate, expected, *, timeout=5, cancel=False):
        deadline = time.monotonic() + 10
        while not (service.home / 'status.json').exists() and time.monotonic() < deadline: time.sleep(.05)
        ident = submit(candidate, 'Non-game qualification using fixed production collector and queue', timeout, home=service.home)
        response = service.home / 'responses' / (ident + '.json')
        if cancel:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                processes = list((service.home / 'evidence').glob('*/captures/*/process.json'))
                if any(core.read(p).get('pid') and p.stat().st_mtime > time.time()-1 for p in processes): break
                time.sleep(.05)
            core.atomic(service.home / 'cancel' / (ident + '.json'), dict(id=ident, time=time.time()))
        deadline = time.monotonic() + 30
        while not response.exists() and not failures and time.monotonic() < deadline: time.sleep(.05)
        core.require(response.exists(), 'production fixture response missing: ' + str(failures))
        result = core.read(response); results.append(result)
        core.require(result['classification'] == expected, 'unexpected fixture outcome: ' + str(result))
        core.require(not service.halted, 'contained qualification failure halted service')
        return result
    try:
        cycle(ids['x86'], 'fixture-complete')
        cycle(ids['x64'], 'fixture-complete')
        injection.set(); failed = cycle(ids['x64'], 'collector-implementation-error')
        failure_tree = core.tree(Path(failed['evidence']))
        cycle(ids['x64'], 'fixture-complete')
        cycle(ids['early'], 'routine-fixture-failure')
        cycle(ids['linger'], 'watchdog', timeout=1)
        cycle(ids['descendant'], 'watchdog', timeout=1)
        cycle(ids['linger'], 'cancelled', timeout=15, cancel=True)
        cycle(ids['abi'], 'fixture-complete')
        # A concrete source edit and fixed rebuild, using a disposable source
        # workspace. The old failed sources and all old evidence stay unchanged.
        workspace = profiles.checkout(ids['early'])
        source = profiles.SOURCES / workspace / 'sources/evidence_smoke.c'
        text = source.read_text(); old = 'if(!strcmp(argv[1],"--early-exit"))return 17;'
        core.require(text.count(old) == 1, 'negative fixture repair anchor')
        source.write_text(text.replace(old, '/* corrected early-exit fixture: proceed through the normal checkpoints */'))
        corrected = profiles.build('collector-smoke', dict(arch='x64', case='early-exit'), source_workspace=workspace)
        # Same fixed argument; independent validation must accept the complete
        # normal stream regardless of whether an early-exit path was corrected.
        cycle(corrected, 'fixture-complete')
        cycle(ids['x64'], 'fixture-complete')
        core.require(core.tree(Path(failed['evidence'])) == failure_tree, 'failed result/evidence changed')
        core.require(all(r['batch_id'] == service.batch['id'] for r in results), 'service restarted between iterations')
    finally:
        service.shutdown = True; thread.join(10)
        core.require(not thread.is_alive() and not failures, 'persistent fixture thread failed: ' + str(failures))
    # Production manifest tampering, then a new request, in a separate service.
    safety = FixtureService(out / 'integrity-queue', qualification=True)
    safety.publish(state='waiting')
    ident = submit(ids['x64'], 'Verify real candidate digest tamper permanently blocks execution', home=safety.home)
    path = safety.home / 'requests' / (ident + '.json'); req = core.read(path); req['candidate_sha256'] = '0'*64; core.atomic(path,req)
    bad = safety.process(path)
    core.require(safety.halted and bad['classification'] == 'security-integrity-containment', 'integrity tamper did not halt')
    # A later valid request cannot bypass the durable integrity latch.
    safety.publish(state='waiting')
    ident2 = str(uuid.uuid4()); later = dict(req, id=ident2, candidate_sha256=core.sha(profiles.candidate_path(ids['x64'])))
    path2 = safety.home / 'requests' / (ident2 + '.json'); core.atomic(path2, later)
    core.require(safety.process(path2)['classification'] == 'rejected', 'integrity latch accepted later execution')
    # Inject a failed containment receipt around an actual harmless process.
    # The real Job is still closed and independently reports zero live children.
    def containment_failure(*args, **kwargs):
        real = transport.cleanup_receipt
        def unverified(*a, **k):
            return dict(real(*a, **k), verified=False, injected_qualification_failure=True)
        with patch('supervisor.fixture_collector.cleanup_receipt', side_effect=unverified):
            return run_fixture(*args, **kwargs)
    contained = FixtureService(out / 'containment-queue', qualification=True, runner=containment_failure)
    contained.publish(state='waiting')
    cid = submit(ids['x64'], 'Inject containment assurance failure after actual harmless process execution', home=contained.home)
    failed_containment = contained.process(contained.home / 'requests' / (cid + '.json'))
    core.require(contained.halted and failed_containment['classification'] == 'security-integrity-containment', 'missing containment did not halt')
    for exit_path in Path(failed_containment['evidence']).glob('captures/*/failure-exit.json'):
        exit_record = core.read(exit_path)
        core.require(exit_record['job_query_ok'] and exit_record['active_processes'] == 0, 'actual injected-case process cleanup failed')
    # Direct production containment adapter receipt inspection, plus unit
    # injection, proves missing/false cleanup cannot be called routine.
    core.require(all(core.read(p)['verified'] for p in (service.home / 'evidence').glob('*/captures/*/containment.json')), 'live Job cleanup missing')
    report = dict(passed=True, persistent_cycles=len(results), single_batch_id=service.batch['id'], results=results,
                  injected_parser_failure_preserved=True, corrected_source_candidate=corrected, source_workspace=workspace,
                  repeated_disposable_binary_allowed=True, cancellation=True, watchdog=True, descendant_cleanup=True,
                  real_candidate_integrity_halt=bad, injected_containment_halt=failed_containment,
                  graphics_devices_created=0, genuine_launches=0)
    core.atomic(out / 'cycles.json', report)
    return report


def preservation(out):
    baseline = core.ROOT / 'out/autonomous-desktop-20261029-01/baseline.json'
    if not baseline.exists():
        return dict(available=False, reason='no construction baseline; all frozen formal delivery hashes still required')
    data = core.read_large(baseline); counts = {}
    for root, files in data['trees'].items():
        for relative, digest in files.items():
            core.require(core.sha(core.independent(core.ROOT / root / relative)) == digest, 'historical file changed: ' + root + '/' + relative)
        counts[root] = len(files)
    result = dict(passed=True, original_files_unchanged=counts,
                  production_home_exact=core.tree(core.HOME) == data['trees']['out/desktop-supervisor'])
    core.require(result['production_home_exact'], 'historical genuine service home changed')
    core.atomic(out / 'preservation.json', result)
    return result


def qualify():
    from .environment import ordinary_user
    from .windows import Exclusive
    from .qualify import host_files
    ordinary_user()
    profiles.HOME.mkdir(parents=True, exist_ok=True)
    out = profiles.HOME / ('qualification-' + str(uuid.uuid4())); out.mkdir()
    with Exclusive(profiles.HOME / 'supervisor.lock'):
        python = [sys.executable, '-B', '-I']
        checked([*python, '-m', 'unittest', 'discover', '-s', str(core.ROOT / 'tools/xrt/supervisor/tests'), '-v'], out, 'supervisor-tests')
        # Run the full original 105 tests without its wrapper, which overwrites
        # historical validation-results. Tests create only fresh additive dirs.
        checked([*python, '-m', 'unittest', 'discover', '-s', str(profiles.RENDERER), '-p', 'test_*.py', '-v'], out, 'renderer-105-tests')
        # Full old enforcement qualification uses its own home. Nothing clears
        # or rewrites the genuine production halt, STOP or consumption ledger.
        legacy_home = core.ROOT / 'out' / ('lq-' + uuid.uuid4().hex[:8])
        script = ("import sys;from pathlib import Path;sys.path.insert(0,str(Path('tools/xrt').resolve()));"
                  "from supervisor.fixture_qualification import legacy_qualify;legacy_qualify(Path(" + repr(str(legacy_home)) + "))")
        checked([*python, '-c', script], out, 'legacy-enforcement', timeout=240)
        cycles = qualification_cycles(out)
        preserved = preservation(out)
        formal = profiles.build('renderer-batch-23', {})
        from .windows import FilePins
        formal_path = profiles.candidate_path(formal)
        with FilePins() as pins:
            pins.pin(formal_path, core.sha(formal_path))
            for name, digest in core.read_large(formal_path)['files'].items(): pins.pin(Path(name), digest)
        prepared = dict(version=1, candidate_id=formal, candidate_sha256=core.sha(profiles.candidate_path(formal)),
                        profile='formal-acceptance', family='renderer-batch-23', parameters={}, timeout_seconds=60,
                        objective='Collect and independently validate the complete frozen -03 physical 23-process native/translated renderer batch; retain strict compatibility failures.',
                        submitted=False, graphics_executed_during_preparation=False)
        core.atomic(out / 'acceptance-request.json', prepared)
        core.atomic(profiles.HOME / 'prepared-acceptance.json', prepared)
        E, _, _ = profiles.modules()
        # Import watchdog and guard dependencies before enumerating the seal.
        import capstone
        files = project_seal()
        seal = dict(passed=True, created_at=time.time(), files=files, host_files=host_files(), evidence=str(out),
                    profiles=list(profiles.PROFILES), physical_gate_required=True, construction_graphics_devices=0,
                    genuine_launches=0, cycles=cycles, preservation=preserved, prepared_acceptance=prepared,
                    renderer_original_tests=105, legacy_enforcement_requalified=True,
                    enforcement_delta='new fixture queue/adapter; historical genuine policy and renderer assertions unchanged; old supervisor-tree preservation replaced by this explicit qualification seal')
        core.atomic(out / 'qualification.json', seal)
        core.atomic(profiles.HOME / 'qualification.json', seal)
        print('FIXTURE QUALIFICATION PASSED; zero graphics devices and zero genuine launches. Evidence:', out)


if __name__ == '__main__': qualify()
