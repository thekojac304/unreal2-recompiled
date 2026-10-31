"""Owned native monitor regression tests, using the existing Job launcher."""
import ctypes as C
import json
import os
from pathlib import Path
from trace_reader import Record, Snapshot, snapshot, records, _layout


def run(dev):
    from trace_profile import install
    dev.setup()
    install(dev.RT)
    env = dev.compiler_environment()
    obj = dev.BUILD / 'trace-fixture'
    obj.mkdir(exist_ok=True)
    for source, name in [(dev.RT / 'monitor.asm', 'probe'),
                         (dev.WS / 'experiments/xrt/tests/practical_init/fpu_oracle.asm', 'oracle')]:
        dev.command(['ml64', '/nologo', '/c', '/Zi', f'/Fo{obj / (name + ".obj")}', source], env, 'trace-' + name)
    dev.compile_one(dev.HERE / 'trace_fixture.c', obj / 'fixture.obj', env, [dev.RT, dev.HERE], ['/Od', '/std:c11'])
    dev.compile_one(dev.HERE / 'trace_fixture.c', obj / 'fixture-test.obj', env, [dev.RT, dev.HERE], ['/Od', '/std:c11', '/DXRT_DEV_TRACE_TEST'])
    for name, source in [('dev', dev.RT / 'monitor.c'), ('baseline', dev.BASE / 'runtime/monitor.c')]:
        # The dev monitor is tested at the optimisation the developer executable links (/O2).
        dev.compile_one(source, obj / (name + '.obj'), env, [source.parent, dev.HERE], ['/O2' if name == 'dev' else '/Od', '/std:c11', '/DXRT_DEV_TRACE_TEST'])
        dev.command(['link', '/nologo', '/DEBUG', f'/OUT:{obj / (name + ".exe")}',
                     obj / ('fixture-test.obj' if name == 'dev' else 'fixture.obj'), obj / (name + '.obj'), obj / 'probe.obj', obj / 'oracle.obj'], env, 'trace-link-' + name)
    out = dev.fresh_run()
    results = []
    def case(name, mode, profile='development', full='', address='', exe='dev', expected=0):
        folder = out / name
        folder.mkdir()
        path = folder / 'monitor.bin'
        child_env = dict(os.environ, XRT_MONITOR_PROFILE=profile, XRT_DEV_TRACE_FULL=full, XRT_DEV_TRACE_ADDRESS=address)
        child_env.pop('XRT_DEV_GAME', None)
        actual = dev.launch(obj / (exe + '.exe'), [path, mode], folder, obj, child_env, 60)
        process = dev.read(folder / 'process.json')
        assert actual == expected and process['remaining_processes'] == 0, (name, actual, process)
        rows = list(records(path))
        side = snapshot(str(path) + '.routine') if profile == 'development' else None
        if side:
            assert C.sizeof(Snapshot) == Path(str(path) + '.routine').stat().st_size
        else:
            assert not Path(str(path) + '.routine').exists()
        # Validate parent/return accounting for the filtered critical stream.
        stacks = {}
        for r in rows:
            stack = stacks.setdefault(r.thread, [])
            if r.event == 2:
                assert r.parent == (stack[-1][0] if stack else 0)
                stack.append((r.invocation, r.domain, r.name))
            if r.event in (3, 9):
                assert stack.pop() == (r.invocation, r.domain, r.name)
        if mode not in ('fatal', 'unsupported'):
            assert not any(stacks.values())
        results.append(dict(case=name, exit=actual, critical_records=len(rows),
                            routine_events=side.routine_events if side else 0,
                            sidecar_bytes=C.sizeof(Snapshot) if side else 0))
        print('PASS trace', name, flush=True)
        return rows, side

    def imp(value, name):
        return next(s for s in value.imports if s.name.decode() == name)
    rows, value = case('large', 'large')
    s = imp(value, 'msvcr70.dll!wcslen')
    assert (s.begins, s.ends, s.failures, s.minimum, s.maximum, s.changes) == (200003, 200003, 0, 0, 16, 200002)
    assert s.first_begin.sequence < s.first_end.sequence < s.last_begin.sequence < s.last_end.sequence
    assert s.last_end.result == 200002 % 17
    assert len(rows) < 20 and value.overwritten == value.observed - 512
    recent = list(value.recent[value.recent_next:]) + list(value.recent[:value.recent_next])
    assert [r.sequence for r in recent] == list(range(value.observed - 511, value.observed + 1))
    assert recent[-1].event == 6 and value.terminal == 1
    for mode in ('checkpoint', 'threads', 'nested', 'failure', 'failure-exit'):
        rows, value = case(mode, mode)
        s = imp(value, 'msvcr70.dll!wcslen')
        assert s.begins == s.ends == (3009 if mode == 'threads' else 38 if mode == 'nested' else 37)
        if mode.startswith('failure'):
            failure = imp(value, 'msvcr70.dll!malloc')
            assert failure.failures == 1 and failure.ends == 1
            assert any(r.name == failure.name and r.event == 3 and r.result == 0 and r.error == 8 for r in rows)
            assert failure.first_failure.error == 8
        if mode == 'nested':
            aborted = imp(value, 'msvcr70.dll!wcscpy')
            assert aborted.aborts == aborted.failures == 1
    rows, value = case('fatal', 'fatal', expected=76)
    assert rows[-1].event == 5 and rows[-2].event == 2 and value.terminal == 3
    assert imp(value, 'msvcr70.dll!wcslen').ends == 200003
    assert value.recent[(value.recent_next-1)%512].event == 5
    rows, value = case('unsupported', 'unsupported', expected=78)
    assert rows[-1].event == 5 and rows[-2].name == b'unknown.dll!Unsupported'
    rows, value = case('selected', 'small', full='msvcr70.dll!wcslen')
    assert value.selected_records == 74 and sum(r.name == b'msvcr70.dll!wcslen' for r in rows) == 74
    rows, value = case('selected-address', 'small', address='0x12340003')
    assert value.selected_records == 2 and sum(r.name == b'msvcr70.dll!wcslen' for r in rows) == 2
    rows, value = case('selected-subtree', 'selected-nested', address='0xfeed1234')
    assert value.selected_records == 6 and any(r.blob_size == 20 for r in rows)
    assert not any(r.event == 11 for r in rows)
    rows, value = case('seek-status', 'seek-status')
    s = imp(value, 'kernel32.dll!SetFilePointer')
    assert s.ends == 2 and s.failures == 1 and s.first_failure.guest_error == 6
    rows, value = case('io-failure', 'io-failure', expected=0xe04d0019)
    assert rows[-1].event == 10
    rows, value = case('rolled-data', 'exhaust')
    assert len(rows) == 2 and value.observed == 140005 and value.overwritten == 139493
    rows, value = case('selected-beyond-old-limit', 'exhaust', full='owned.detail')
    assert len(rows) == 140005 and value.selected_records == 140003
    rows, value = case('abrupt', 'abrupt', expected=77)
    assert value.terminal == 0 and value.observed < 140004 and value.observed >= 131072
    assert rows[-1].event == 1  # no invented close or endpoint
    rows, value = case('unknown', 'unknown')
    s = imp(value, 'owned.unclassified')
    assert s.unclassified == 70003 and s.suspects == 70002 and s.failures == 0
    assert any(r.result == 0x80001234 and r.flags & 0x400 for r in rows)
    assert len(rows) < 10  # novelty preserved; repetition counted and rolled
    rows, value = case('table-overflow', 'overflow')
    assert value.table_overflow == 89 and value.imports[-1].begins == 89
    rows, value = case('fileio-endpoint', 'fileio', expected=10)
    read = imp(value, 'kernel32.dll!ReadFile')
    write = imp(value, 'kernel32.dll!WriteFile')
    seek = imp(value, 'kernel32.dll!SetFilePointer')
    assert read.begins == read.ends == 70007 and read.failures == 3
    assert read.bytes == write.bytes == write.ends == seek.ends == 70003
    assert read.short_io == 1 and read.metadata_missing == 0
    assert seek.failures == write.failures == 0 and read.first_failure.guest_error == 6
    assert any(r.name == b'kernel32.dll!ReadFile' and r.flags & 0x100 and r.guest_error == 6 for r in rows)
    assert value.terminal == 2 and rows[-1].name == b'dev.Init.return'
    assert value.observed > 420000 and len(rows) < 20
    assert not any(r.blob_size for r in value.recent)
    endpoint = out / 'fileio-endpoint'
    assert not dev.endpoint_proven(endpoint, 10)  # checkpoint but no matching report
    dev.write(endpoint / 'runtime-report.json', {'events': [{'kind': 'dev_init_return', 'guest_next': '0x1090ed5c'}]})
    assert dev.endpoint_proven(endpoint, 10) and not dev.endpoint_proven(endpoint, 0)
    dev.write(out / 'large/runtime-report.json', {'events': [{'kind': 'dev_init_return', 'guest_next': '0x1090ed5c'}]})
    assert not dev.endpoint_proven(out / 'large', 10)  # report and exit alone cannot prove it
    # Corrupt/truncated snapshots are explicitly rejected, never called complete.
    raw = (out / 'fileio-endpoint/monitor.bin.routine').read_bytes()
    for label, data in [('torn', raw[:100] + bytes([raw[100]^1]) + raw[101:]), ('truncated', raw[:-1])]:
        path = out / (label + '.routine');path.write_bytes(data)
        try:
            snapshot(path)
        except ValueError:
            pass
        else:
            raise AssertionError(label + ' accepted')
    strict, _ = case('forensic', 'small', profile='forensic', full='msvcr70.dll!wcslen')
    baseline, _ = case('baseline-forensic', 'small', profile='forensic', exe='baseline')
    # Existing strict decoder accepts both; compare stable event semantics.
    for name in ('forensic', 'baseline-forensic'):
        _layout.decode(out / name / 'monitor.bin')
    fields = ('version', 'event', 'sequence', 'invocation', 'parent', 'depth', 'domain', 'name', 'result', 'error', 'guest_error', 'cpu', 'stack')
    def semantic(r):
        return tuple(bytes(getattr(r, f)) if f in ('cpu', 'stack') else getattr(r, f) for f in fields)
    assert [semantic(r) for r in strict] == [semantic(r) for r in baseline]
    dev.write(out / 'trace-results.json', dict(passed=True, cases=results, game_executions=0,
              assertions='native call counts/results, LastError, CPU bytes, exact FXSAVE and DF at every probe; bounded history, file I/O, overflow, selected tracing beyond old capacity, first failure/fatal/unsupported preservation, endpoint, abrupt/torn snapshot limitations, strict baseline equality'))
    print('Trace results:', out)
    return out
