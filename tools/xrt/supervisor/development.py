"""Persistent owner-authorized disposable-fixture service. Genuine code is absent.

Shares durable queue/state/ledger primitives with Service, in a separate home.
Fast development continues through contained failures. Formal acceptance uses the
unchanged renderer evidence assertions and an independent saved-evidence audit.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import uuid
from . import core, fixture_profiles as profiles
from .policy import State
from .service import Service, seal_files, verify_seal


class DesktopUnavailable(RuntimeError):
    pass


def read_status(home=profiles.HOME):
    """Read the replaceable status projection across Windows sharing races."""
    deadline = time.monotonic() + 2
    while True:
        try:
            return core.read(home / 'status.json')
        except PermissionError:
            if time.monotonic() >= deadline: raise
            time.sleep(.01)


class FixtureService(Service):
    def __init__(self, home=profiles.HOME, *, qualification=False, runner=None, gate=None):
        super().__init__(home, 0, qualification=qualification)
        (self.home / 'cancel').mkdir(exist_ok=True)
        self.runner = runner or run_fixture
        self.gate = gate or physical_gate
        self.batch.update(profiles=list(profiles.PROFILES), scope='disposable-fixtures-only', genuine_limit=0)
        reviewed = {ident for r in self.ledger.rows if r['kind'] == 'fixture-owner-review' for ident in r['resolved_requests']}
        self.unresolved = [r['request_id'] for r in self.ledger.rows if r['kind'] == 'fixture-unclassified' and r['request_id'] not in reviewed]

    def publish(self, **values):
        # Windows readers may briefly open status.json without delete sharing.
        # Status replacement is retryable; evidence/ledger/identity failures are
        # never covered by this narrow retry. Failed temp images are retained.
        deadline = time.monotonic() + 2
        while True:
            try:
                super().publish(service='disposable-fixtures', updated_at=time.time(), unresolved=self.unresolved, **values)
                return
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.01)

    def cancelled(self, ident):
        return self.stop() or time.time() >= self.batch['expires_at'] or (self.home / 'cancel' / (ident + '.json')).exists()

    def execution_check(self):
        if (self.home / 'HALTED.json').exists():
            self.operational_state = State.SAFETY_HALT
        if self.seal:
            verify_seal(self.seal)
        core.require(not self.stop(), 'fixture service stopping')
        core.require(not (self.home / 'HALTED.json').exists() and self.operational_state != State.SAFETY_HALT,
                     'SAFETY HALT; owner review and requalification required')

    def process(self, path):
        # Validate before claiming so an unavailable desktop leaves the original
        # request in place. No child exists while paused.
        try:
            request = profiles.parse(core.read(path), self.batch)
            core.require(path.name == request['id'] + '.json', 'filename/UUID binding')
            self.execution_check()
            core.require(not any(r.get('request_id') == request['id'] for r in self.ledger.rows), 'replay request')
            core.require(request['profile'] != 'formal-acceptance' or not self.unresolved,
                         'unclassified correctness remains unresolved; investigate before formal acceptance')
            if not self.cancelled(request['id']):
                self.gate(self.home, request, qualification=self.qualification)
        except DesktopUnavailable as error:
            self.publish(state='paused', request=path.name, reason=str(error))
            return None
        except core.IntegrityFailure as error:
            self.halt(str(error))
            return self.reject(path, str(error))
        except (core.Rejected, OSError, ValueError) as error:
            return self.reject(path, str(error))
        except BaseException as error:
            self.halt('fixture preflight failed without classification: ' + str(error))
            return self.reject(path, str(error))
        claimed = self.home / 'processing' / path.name
        core.independent(claimed); core.require(not claimed.exists(), 'duplicate claim')
        os.rename(path, claimed)
        out = self.home / 'evidence' / str(uuid.uuid4()); out.mkdir()
        core.atomic(out / 'request.json', request)
        result = dict(version=2, id=request['id'], batch_id=self.batch['id'], profile=request['profile'],
                      family=request['family'], evidence=str(out), started_at=time.time(), passed=False,
                      genuine_launches=0, graphics_devices_created=None if request['family'] in ('renderer-group','renderer-batch-23') else 0,
                      production_accepted=False,
                      strict_x87='FAILED', strict_wndproc='FAILED', strict_native_x86='FAILED')
        candidate = None
        try:
            if core.read(claimed) != request:
                raise core.IntegrityFailure('queue request changed during preflight')
            candidate = profiles.validate_candidate(request)
            core.atomic(out / 'candidate.json', candidate)
            # Unlike genuine launches, a disposable executable is reusable across
            # distinct request IDs. Claim every ID durably before dispatch.
            profiles.parse(request, self.batch)
            self.ledger.append('fixture-request-claimed', request_id=request['id'], batch_id=self.batch['id'],
                               candidate_id=request['candidate_id'], candidate_sha256=request['candidate_sha256'])
            self.execution_check()
            if self.cancelled(request['id']):
                result.update(classification='cancelled', reason='cancelled before launch')
            else:
                from .windows import FilePins
                with ExitStack() as stack:
                    pins = stack.enter_context(FilePins())
                    pins.pin(profiles.candidate_path(candidate['id']), request['candidate_sha256'])
                    for name, digest in candidate['files'].items():
                        pins.pin(Path(name), digest)
                    result.update(self.runner(request, candidate, out, lambda: self.cancelled(request['id']),
                                              lambda: self.progress(request, out), qualification=self.qualification))
            profiles.validate_candidate(request)
            self.execution_check_after_run()
        except core.IntegrityFailure as error:
            result.update(classification='security-integrity-containment', reason=str(error))
            self.halt(str(error))
        except BaseException as error:
            # An adapter supplies independent final cleanup even when parsing fails.
            # Without that assurance a host exception must close execution.
            (out / 'exception.txt').write_text(traceback.format_exc(), encoding='utf-8')
            assurance = core.read(out / 'assurance.json') if (out / 'assurance.json').exists() else {}
            safe = assurance.get('cleanup_verified') is True and assurance.get('integrity_verified') is True
            result.update(classification='collector-implementation-error' if safe else 'security-integrity-containment', reason=str(error))
            if not safe:
                self.halt('unverified fixture exception: ' + str(error))
        # Failed handlers cannot skip integrity or qualification checks.
        if candidate:
            try:
                profiles.validate_candidate(request); self.execution_check_after_run()
            except Exception as error:
                result.update(passed=False, classification='security-integrity-containment', reason=str(error))
                self.halt(str(error))
        if result.get('classification') == 'unclassified-correctness':
            self.unresolved.append(request['id'])
            self.ledger.append('fixture-unclassified', request_id=request['id'], evidence=str(out))
        if self.operational_state == State.SAFETY_HALT:
            result['passed'] = False
        result.update(finished_at=time.time(), operational_state=self.operational_state)
        core.atomic(out / 'result.json', result)
        core.atomic(out / 'evidence-index.json', core.tree(out))
        self.ledger.append('fixture-result', request_id=request['id'], classification=result['classification'],
                           passed=result['passed'], evidence=str(out), result_sha256=core.sha(out / 'result.json'))
        self.response(path.name, result)
        os.rename(claimed, self.home / 'archive' / (out.name + '.json'))
        return result

    def execution_check_after_run(self):
        if self.seal:
            verify_seal(self.seal)
        if (self.home / 'HALTED.json').exists() and self.operational_state != State.SAFETY_HALT:
            raise core.IntegrityFailure('external safety latch appeared during execution')
        # STOP is ordinary cancellation, not an integrity failure.

    def progress(self, request, out):
        self.execution_check_after_run()
        self.publish(state='processing', request=request['id'], evidence=str(out))

    def response(self, name, result):
        path = self.home / 'responses' / name
        if path.exists():
            path = path.with_name(path.stem + '-rejected-' + uuid.uuid4().hex + '.json')
        core.atomic(path, result)

    def reject(self, path, reason):
        result = dict(version=2, id=path.stem, classification='rejected', passed=False, reason=reason,
                      genuine_launches=0, finished_at=time.time(), operational_state=self.operational_state)
        # Rejected queue data is evidence too; never delete or overwrite it.
        try:
            core.independent(path)
        except core.Rejected as error:
            # Never follow, rename or delete a reparse/hardlinked queue object.
            self.halt('unsafe queue object: ' + str(error))
            result.update(operational_state=self.operational_state, unsafe_request_retained=str(path))
            self.response(path.name, result)
            return result
        archive = self.home / 'archive' / (str(uuid.uuid4()) + '.json')
        os.rename(path, archive); result['request_file'] = str(archive)
        self.response(path.name, result)
        self.ledger.append('fixture-rejected', request_id=path.stem, reason=reason)
        return result

    def serve(self):
        self.publish(state='waiting')
        while not self.stop() and time.time() < self.batch['expires_at']:
            if self.operational_state == State.SAFETY_HALT:
                self.publish(state='halted'); return
            if not list((self.home / 'requests').glob('*.json')):
                self.publish(state='halted' if self.halted else 'waiting')
            for path in sorted((self.home / 'requests').glob('*.json')):
                if self.stop(): break
                result = self.process(path)
                if result is None: break
                self.publish(state='halted' if self.halted else 'waiting', last_result=result)
            time.sleep(.2 if not list((self.home / 'requests').glob('*.json')) else 1)
        self.publish(state='stopped')


def physical_gate(home, request, *, qualification=False):
    # Qualification never bypasses the graphics gate, even with a test service.
    graphical = request['family'] in ('renderer-group', 'renderer-batch-23')
    if qualification and not graphical:
        return
    from .environment import ordinary_user
    ordinary_user()
    _, A, original = profiles.modules()
    directory = home / 'evidence' / ('gate-' + str(uuid.uuid4())); directory.mkdir()
    try:
        snapshot = original.Collector().snapshot(os.getpid(), directory / 'owner.json')
        A.environment(snapshot, physical=True)
    except A.Incomplete as error:
        raise DesktopUnavailable('physical desktop unavailable; queue retained: ' + str(error)) from error


def run_fixture(request, candidate, out, stop, progress, *, qualification=False):
    from . import fixture_collector as transport
    E, A, original = profiles.modules()
    family = request['family']; values = request['parameters']
    root = profiles.candidate_path(candidate['id']).parent
    formal = family == 'renderer-batch-23'
    if formal:
        profiles.verify_formal()
    physical = family in ('renderer-group', 'renderer-batch-23') or not qualification
    captures = out / 'captures'; captures.mkdir()
    reports = []; observations = {}; classification = 'fixture-complete'; reason = None
    devices = 0
    try:
        for item in profiles.plan(family, values, root):
            if stop(): raise transport.Cancelled('request cancelled between processes')
            progress()
            if physical:
                # Recheck before each process of a long acceptance batch.
                physical_gate(out, request, qualification=qualification)
            exe = item['exe']; directory = captures / item['name']
            backend = []; extra = None
            build = Path(candidate['build_record']) if candidate['build_record'] else exe.parent / 'build-record.json'
            if family == 'collector-smoke':
                args = [dict(normal='--smoke', **{'early-exit':'--early-exit', 'linger':'--linger', 'descendant':'--spawn-descendant'})[values['case']]]
                backend = [exe.parent / 'disposable.dll']; extra = {'XRT_SMOKE_DLL': str(backend[0])}
            elif family == 'renderer-abi':
                args = ['--abi-evidence']
            else:
                pair = E.P.G.verified_pair(item['arch']); backend = [pair / 'd3d8.dll', pair / 'd3d9.dll']
                args = [pair,148,1,18,0] if item['group'] == 0 else ['--physical', pair]
                devices += 1
            try:
                transport.capture(exe, args, directory, build_record=build, backend=backend,
                                  timeout=request['timeout_seconds'], stop=stop, physical=physical, extra_env=extra)
            except (transport.Cancelled, transport.WatchdogExpired):
                raise
            except core.IntegrityFailure:
                raise
            except original.IdentityIncomplete as error:
                raise core.IntegrityFailure('loaded-module integrity unverified: ' + str(error)) from error
            except A.Incomplete as error:
                # The transport calls this validator only for environment
                # observations; numerical/ABI validation happens below.
                classification = 'environment-unavailable'; reason = str(error); break
            except Exception as error:
                # A checkpoint/transport error does not describe compatibility.
                classification = 'routine-fixture-failure' if family == 'collector-smoke' and values['case'] != 'normal' else 'collector-implementation-error'
                reason = str(error); break
            try:
                if family == 'collector-smoke':
                    transport.validate_smoke(directory, exe, build, physical=physical, args=args)
                elif family == 'renderer-abi':
                    transport.validate_abi(directory, item, build, physical=physical)
                elif formal:
                    if item['group'] == 0: A.preflight(directory, item['arch'])
                    else:
                        observed, report = A.group(directory, item['group'], item['arch'], item['variant'] == 'translated')
                        observations.setdefault(item['group'], []).append(observed); reports.append(report)
                        if len(observations[item['group']]) == 3:
                            A.need(observations[item['group']][0] == observations[item['group']][1] == observations[item['group']][2], 'native/translated differential discrepancy')
                else:
                    rows, snapshot, events = A.process(directory, physical=True, expected_exe=exe, expected_args=args,
                                                       expected_build=build, expected_backend=backend)
                    A.adapter(rows, snapshot, directory, item['arch'])
                    A.group_observations(rows, item['group'], item['arch'], item['variant'] == 'translated', events)
            except A.Incomplete as error:
                classification = 'unclassified-correctness'; reason = str(error); break
            except Exception as error:
                classification = 'collector-implementation-error'; reason = str(error); break
            core.atomic(out / 'progress.json', dict(completed=len(list(captures.iterdir())), total=23 if formal else 1,
                        last=item['name'], reports=reports)); progress()
        if classification == 'fixture-complete' and formal:
            # Separate interpreter rereads ALL saved raw evidence. No execution.
            command = [sys.executable, '-B', '-I', str(core.ROOT / 'tools/xrt/desktop_supervisor.py'), 'audit-fixtures', '--evidence', str(out)]
            audit = subprocess.run(command, cwd=core.ROOT, capture_output=True, timeout=120)
            (out / 'audit.stdout.bin').write_bytes(audit.stdout); (out / 'audit.stderr.bin').write_bytes(audit.stderr)
            if audit.returncode or not (out / 'assessment.json').exists():
                classification = 'unclassified-correctness'; reason = 'independent evidence audit rejected; see audit logs'
    except transport.Cancelled as error:
        classification = 'cancelled'; reason = str(error)
    except transport.WatchdogExpired as error:
        classification = 'watchdog'; reason = str(error)
    except DesktopUnavailable as error:
        classification = 'environment-unavailable'; reason = str(error)
    finally:
        receipts = [core.read(p) for p in captures.glob('*/containment.json')]
        dirs = list(captures.iterdir())
        cleanup = len(receipts) == len(dirs) and all(r['verified'] is True for r in receipts)
        profiles.verify_identities(candidate['files'])
        core.atomic(out / 'assurance.json', dict(cleanup_verified=cleanup, integrity_verified=True))
        if not cleanup:
            raise core.IntegrityFailure('missing/failed per-process containment receipt')
    graphical = family in ('renderer-group', 'renderer-batch-23')
    return dict(classification=classification, passed=classification == 'fixture-complete', reason=reason,
                graphics_devices_created=(devices if classification == 'fixture-complete' else None) if graphical else 0,
                graphics_fixture_attempts=devices, process_count=sum(r.get('launched') is True for r in receipts),
                functional_verdict='PASSED' if classification == 'fixture-complete' else 'NOT_PASSED',
                strict_compatibility_verdict='FAILED; historical x87/WNDPROC/native-x86 retained')


def submit(ident, objective, timeout=60, *, home=profiles.HOME):
    status = read_status(home)
    core.require(status.get('service') == 'disposable-fixtures' and status['state'] in ('waiting','processing','paused') and not status['halted'], 'live fixture service required')
    core.require(time.time() - status['updated_at'] < 180, 'stale fixture service status')
    path = profiles.candidate_path(ident); candidate = core.read_large(path); batch = status['batch']
    stamp = time.time(); request_id = str(uuid.uuid4())
    request = dict(version=2, id=request_id, batch_id=batch['id'], created_at=stamp,
                   expires_at=min(stamp + 300, batch['expires_at']), objective=objective,
                   profile='formal-acceptance' if candidate['family'] == 'renderer-batch-23' else 'fast-development',
                   family=candidate['family'], parameters=candidate['parameters'], candidate_id=ident,
                   candidate_sha256=core.sha(path), timeout_seconds=timeout)
    profiles.parse(request, batch); profiles.validate_candidate(request)
    core.atomic(home / 'requests' / (request_id + '.json'), request)
    return request_id


def serve():
    from .environment import ordinary_user
    from .windows import Exclusive, FilePins
    ordinary_user()
    core.require(not sys.flags.optimize and sys.stdin.isatty(), 'owner local interactive console with assertions required')
    profiles.HOME.mkdir(parents=True, exist_ok=True)
    with Exclusive(profiles.HOME / 'supervisor.lock'):
        service = FixtureService(profiles.HOME)
        core.require(not service.halted and not service.stop(), 'fixture safety latch/STOP requires owner investigation; preserved history cannot be cleared by queue')
        seal = core.read_large(profiles.HOME / 'qualification.json')
        core.require(seal.get('passed') is True, 'qualify-fixtures must pass')
        verify_seal(seal)
        with FilePins() as pins:
            for name, digest in {**{str(core.ROOT / k):v for k,v in seal['files'].items()}, **seal['host_files']}.items():
                pins.pin(Path(name), digest)
            service.bind_seal(seal)
            gate_request = dict(family='renderer-batch-23')
            physical_gate(service.home, gate_request)
            print('Fixed disposable fixtures only. Four hours; 60 seconds/process; formal batch 23 processes.')
            print('Type exactly: AUTHORIZE DISPOSABLE FIXTURES FAST AND FORMAL')
            core.require(input().strip() == 'AUTHORIZE DISPOSABLE FIXTURES FAST AND FORMAL', 'fixture service not authorized')
            verify_seal(seal)
            service.ledger.append('fixture-batch-authorized', batch=service.batch, owner_console=True, qualification_sha256=core.digest(seal))
            def shutdown(*_): service.shutdown = True
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK): signal.signal(sig, shutdown)
            print('Fixture service waiting. Use fixture-status / stop-fixtures.', flush=True)
            service.serve()


def review():
    """Owner-only review; never reachable through a queued fixture request."""
    from .environment import ordinary_user
    from .windows import Exclusive
    ordinary_user()
    core.require(sys.stdin.isatty(), 'fixture review requires the local owner console')
    with Exclusive(profiles.HOME / 'supervisor.lock'):
        service = FixtureService(profiles.HOME)
        core.require(not list((service.home / 'processing').glob('*.json')), 'investigate interrupted claims before review')
        core.require(service.halted or service.unresolved, 'no fixture safety/correctness hold to review')
        seal = core.read_large(service.home / 'qualification.json')
        core.require(seal.get('passed') is True, 'current non-game qualification required')
        verify_seal(seal)
        print('Review the original failure evidence, diagnosis, code repair and regressions.')
        print('This authorizes a fresh test batch. All original acceptance assertions still apply.')
        print('Hold:', service.hold, 'Unclassified request IDs:', service.unresolved)
        print('Qualification evidence:', seal['evidence'])
        phrase = 'REVIEW FIXTURE HOLD ' + core.digest(seal)[:16]
        print('Type exactly:', phrase)
        core.require(input().strip() == phrase, 'owner fixture review not accepted')
        verify_seal(seal)
        dest = service.home / 'owner-reviews' / str(uuid.uuid4()); dest.mkdir(parents=True)
        core.atomic(dest / 'review.json', dict(time=time.time(), hold=service.hold, unresolved=service.unresolved,
                    qualification_sha256=core.digest(seal), fresh_authorization_required=True))
        service.ledger.append('fixture-owner-review', resolved_requests=service.unresolved,
                              evidence=str(dest), qualification_sha256=core.digest(seal))
        latch = service.home / 'HALTED.json'
        if latch.exists(): core.independent(latch); os.rename(latch, dest / 'HALTED.json')
        service.transition(State.RUNNING, None)
        print('Review recorded; old failures retained. STOP is unchanged. Start a fresh authorized fixture batch.')


def audit(out):
    E, A, _ = profiles.modules()
    request = core.read(out / 'request.json')
    core.require(request['family'] == 'renderer-batch-23' and request['profile'] == 'formal-acceptance', 'formal audit scope')
    profiles.validate_candidate(request); profiles.verify_formal()
    result = A.batch(out / 'captures')
    core.atomic(out / 'assessment.json', result)


def cli(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('serve-fixtures'); sub.add_parser('fixture-status'); sub.add_parser('stop-fixtures'); sub.add_parser('qualify-fixtures'); sub.add_parser('submit-acceptance'); sub.add_parser('review-fixtures')
    build = sub.add_parser('build-test'); build.add_argument('family', choices=profiles.FAMILIES)
    build.add_argument('--arch', choices=('x86','x64'), default='x64'); build.add_argument('--group', type=int, default=1)
    build.add_argument('--variant', choices=('native','translated'), default='native')
    build.add_argument('--case', choices=('normal','early-exit','linger','descendant'), default='normal')
    build.add_argument('--source-workspace', help='UUID from checkout-test; rebuild edited sources using the same fixed recipe')
    edit = sub.add_parser('checkout-test'); edit.add_argument('--candidate', required=True)
    send = sub.add_parser('submit-test'); send.add_argument('--candidate', required=True); send.add_argument('--objective', required=True)
    send.add_argument('--timeout', type=int, default=60)
    cancel = sub.add_parser('cancel-test'); cancel.add_argument('id')
    read = sub.add_parser('test-result'); read.add_argument('id')
    check = sub.add_parser('audit-fixtures'); check.add_argument('--evidence', type=Path, required=True)
    args = ap.parse_args(argv)
    if args.command == 'serve-fixtures': serve()
    elif args.command == 'review-fixtures': review()
    elif args.command == 'qualify-fixtures':
        from .fixture_qualification import qualify
        qualify()
    elif args.command == 'build-test':
        values = {} if args.family == 'renderer-batch-23' else (dict(arch=args.arch, case=args.case) if args.family == 'collector-smoke' else dict(arch=args.arch, group=args.group, variant=args.variant))
        core.require(args.family != 'renderer-batch-23' or not args.source_workspace, 'formal acceptance uses frozen -03 delivery only')
        print(profiles.build(args.family, values, source_workspace=args.source_workspace))
    elif args.command == 'checkout-test': print(profiles.checkout(args.candidate))
    elif args.command == 'submit-test': print(submit(args.candidate, args.objective, args.timeout))
    elif args.command == 'submit-acceptance':
        prepared = core.read(profiles.HOME / 'prepared-acceptance.json')
        core.require(core.sha(profiles.candidate_path(prepared['candidate_id'])) == prepared['candidate_sha256'], 'prepared acceptance candidate changed')
        print(submit(prepared['candidate_id'], prepared['objective'], prepared['timeout_seconds']))
    elif args.command == 'fixture-status': print(json.dumps(read_status(profiles.HOME), indent=2))
    elif args.command == 'stop-fixtures':
        core.independent(profiles.HOME / 'STOP'); (profiles.HOME / 'STOP').touch(exist_ok=True); print('Fixture stop requested.')
    elif args.command == 'cancel-test':
        core.uuid_text(args.id); core.atomic(profiles.HOME / 'cancel' / (args.id + '.json'), dict(id=args.id, time=time.time()))
    elif args.command == 'test-result':
        core.uuid_text(args.id); print(json.dumps(core.read(profiles.HOME / 'responses' / (args.id + '.json')), indent=2))
    else:
        core.require(args.evidence.resolve().is_relative_to(profiles.HOME) or args.evidence.resolve().is_relative_to(core.ROOT / 'out'), 'workspace evidence required')
        audit(core.independent(args.evidence))
