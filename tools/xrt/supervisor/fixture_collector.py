"""Bounded adapter around the repaired production evidence collector.

The original snapshot/module-identity implementation and independent assertions
are reused unchanged. Only lifecycle control and trusted environment construction
are added here. No queue-selected command reaches this module.
"""
import ctypes as C
import os
import subprocess
import threading
import time
import uuid
from . import core, fixture_profiles as profiles


class Cancelled(RuntimeError):
    pass


class WatchdogExpired(TimeoutError):
    pass


def cleanup_receipt(directory, *, launched):
    """Cleanup is independent of parsing, ABI assertions and fixture success."""
    if not launched:
        return dict(verified=True, launched=False)
    for name in ('failure-exit.json', 'exit.json'):
        path = directory / name
        if path.exists():
            exit = core.read(path)
            safe = (exit.get('job_query_ok') is True and exit.get('active_processes') == 0
                    and exit.get('wait') == 0 and exit.get('exit') != 259
                    and exit.get('assigned_before_resume') is True and exit.get('kill_on_close') is True)
            return dict(verified=safe, launched=True, receipt=name, **exit)
    return dict(verified=False, launched=True, reason='no final Job/process receipt')


def capture(exe, args, directory, *, build_record, backend, timeout, stop, physical, extra_env=None):
    E, A, original = profiles.modules()
    from .fixture import environment
    collector = original.Collector()  # exact repaired production DLL/snapshot code
    lib = collector.lib
    directory.mkdir()
    command = [str(exe), *map(str, args)]
    env = environment(directory)
    effective = E.P.G.environment(env, directory)
    token = uuid.uuid4().hex
    env.update(XRT_EVIDENCE_DIR=str(directory), XRT_EVIDENCE_READY='Local\\XrtEvidenceReady-' + token,
               XRT_EVIDENCE_GATE='Local\\XrtEvidenceGate-' + token)
    env.update(extra_env or {})  # only sealed profile code supplies these values
    block = C.create_unicode_buffer('\0'.join(k + '=' + v for k, v in sorted(env.items(), key=lambda kv: kv[0].upper())) + '\0\0')
    child = None; worker = None; done = threading.Event(); interrupted = []; abort_errors = []
    record = dict(schema=2, command=command, command_line=subprocess.list2cmdline(command), cwd=str(directory),
                  executable_sha256=core.sha(exe), build_record=str(build_record), build_record_sha256=core.sha(build_record),
                  backend={str(p): core.sha(p) for p in backend}, dxvk_environment=effective,
                  owner_pid=os.getpid(), physical=physical, forced_cleanup=False,
                  fixture_stdout='stdout.txt', runtime_events='runtime-events.jsonl',
                  runtime_stream_origin='instrumented fixture services; not full production runtime telemetry',
                  event_loss_policy='synchronous writes counted; no queue-drop instrumentation; dropped_event_count must remain null')
    try:
        owner = collector.snapshot(os.getpid(), directory / 'owner-before.json')
        A.environment(owner, physical=physical)
        record.update(owner_sid=owner['owner_sid'], start_filetime=original.now())
        core.atomic(directory / 'process.json', record)
        (directory / 'runtime-events.jsonl').touch()
        if stop():
            raise Cancelled('cancelled before process creation')
        child = lib.ev_spawn(record['command_line'], str(directory), C.cast(block, C.c_void_p),
                             str(directory / 'stdout.txt'), str(directory / 'stderr.txt'),
                             env['XRT_EVIDENCE_READY'], env['XRT_EVIDENCE_GATE'])
        if not child:
            # Native ev_spawn terminates an unassigned suspended child on failure.
            # It provides no final receipt, so missing containment stays a halt.
            raise core.IntegrityFailure('CreateProcess/Job assignment failed; no verified launch receipt')
        deadline = time.monotonic() + timeout
        def watchdog():
            while not done.wait(.05):
                try:
                    reason = 'cancelled' if stop() else 'watchdog' if time.monotonic() >= deadline else None
                    if reason:
                        interrupted.append(reason)
                        if not lib.ev_abort(child):
                            abort_errors.append('TerminateJobObject failed')
                        return
                except BaseException as error:
                    abort_errors.append(str(error)); lib.ev_abort(child); return
        worker = threading.Thread(target=watchdog, name='fixture-process-watchdog', daemon=True); worker.start()
        pid = lib.ev_pid(child); record['pid'] = pid; core.atomic(directory / 'process.json', record)
        collector.snapshot(pid, directory / 'suspended.json', pre_resume=True)
        if lib.ev_job(child, str(directory / 'suspended-job.json')) != 0:
            raise core.IntegrityFailure('suspended Job membership unverified')
        if lib.ev_resume(child) == 0xffffffff:
            raise core.IntegrityFailure('ResumeThread failed')
        for phase in ('loaded', 'cleaned'):
            status = lib.ev_wait(child, max(1, int((deadline - time.monotonic()) * 1000)))
            if status != 0:
                raise RuntimeError(f'missing child checkpoint: {phase}, wait={status}')
            receipt = core.read(directory / (phase + '-self.json'))
            if receipt['phase'] != phase or receipt['pid'] != pid:
                raise core.IntegrityFailure('checkpoint PID/phase identity')
            snapshot = collector.snapshot(pid, directory / (phase + '-environment.json'))
            A.environment(snapshot, physical=physical)
            if lib.ev_job(child, str(directory / (phase + '-job.json'))) != 0:
                raise core.IntegrityFailure('checkpoint Job membership unverified')
            if not lib.ev_release(child):
                raise core.IntegrityFailure('checkpoint release failed')
        if lib.ev_finish(child, str(directory / 'exit.json'), max(1, int((deadline - time.monotonic()) * 1000))) != 0:
            raise core.IntegrityFailure('final Job receipt unavailable')
        done.set(); worker.join(2)
        exit = core.read(directory / 'exit.json')
        if not cleanup_receipt(directory, launched=True)['verified']:
            raise core.IntegrityFailure('process/descendant cleanup unverified')
        record['finish_filetime'] = original.now(); core.atomic(directory / 'process.json', record)
        collector.snapshot(os.getpid(), directory / 'owner-after.json')
        if exit['exit'] != 0:
            raise RuntimeError('fixture exit failure: ' + str(exit['exit']))
        if interrupted:
            raise Cancelled('request cancelled') if interrupted[0] == 'cancelled' else WatchdogExpired('per-process watchdog')
    except BaseException as error:
        if child:
            lib.ev_abort(child)
            lib.ev_finish(child, str(directory / 'failure-exit.json'), 5000)
        record.update(forced_cleanup=True, failure=str(error), finish_filetime=original.now())
        core.atomic(directory / 'process.json', record)
        if interrupted and not isinstance(error, core.IntegrityFailure):
            raise Cancelled('request cancelled') if interrupted[0] == 'cancelled' else WatchdogExpired('per-process watchdog') from error
        if isinstance(error, RuntimeError) and time.monotonic() >= locals().get('deadline', float('inf')):
            raise WatchdogExpired('per-process watchdog') from error
        raise
    finally:
        done.set()
        if worker:
            worker.join(2)
        try:
            receipt = cleanup_receipt(directory, launched=bool(child))
            if abort_errors or (worker and worker.is_alive()):
                receipt.update(verified=False, watchdog_errors=abort_errors or ['watchdog did not stop'])
            core.atomic(directory / 'containment.json', receipt)
        finally:
            # Evidence I/O failures must still close the kill-on-close Job.
            if child:
                lib.ev_close(child)
        if not receipt['verified']:
            raise core.IntegrityFailure('collector containment unverified: ' + str(receipt))


def validate_smoke(directory, exe, build, *, physical, args=None):
    _, A, _ = profiles.modules()
    rows, _, events = A.process(directory, physical=physical, expected_exe=exe, expected_args=args or ['--smoke'],
                                expected_build=build, expected_backend=[exe.parent / 'disposable.dll'])
    A.need(rows == [dict(kind='smoke-cleanup', destroyed=True, window_valid=False, unloaded=True, module_loaded=False)], 'smoke cleanup assertion')
    A.need([e['event'] for e in events] == ['smoke-observation'], 'smoke runtime event')


def validate_abi(directory, item, build, *, physical=False):
    E, A, _ = profiles.modules()
    rows, _, events = A.process(directory, physical=physical, expected_exe=item['exe'], expected_args=['--abi-evidence'], expected_build=build)
    expected = [(c, seed) for c in A.read(E.P.O / 'cases.json')['cases'] if c['group'] == item['group']
                for seed in (18,0,0x13572468,0xffffffff) for _ in range(2)]
    A.need(len(rows) == len(expected) + 1, 'complete ABI call sequence')
    for row, (case, seed) in zip(rows[:-1], expected):
        A.abi(row, item['arch'])
        A.need(row['kind'] == 'call' and all(row[k] == case[k] for k in ('group','site','config','slot','a','b','c'))
               and row['hr'] == 0 and row['seed'] == row['error'] == seed and row['fpu_preserved'] is True, 'ABI result and measured call identity')
    A.need(rows[-1] == dict(kind='abi-only-summary', passed=True, calls=len(expected), graphics=False, double_only=True), 'ABI summary')
    wanted = [(kind, c['site'], c['slot']) for c, _ in expected for kind in ('adapter-enter','adapter-leave')] if item['variant'] == 'translated' else []
    A.need([(e['event'], e['payload']['site'], e['payload']['slot']) for e in events] == wanted, 'ABI event sequence')
