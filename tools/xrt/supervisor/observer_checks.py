"""Actual retained observer on fixed disposable non-game executables only."""
import ctypes as C
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import MethodType

from . import core, fixture
from .environment import load
from .observer import construct

STREAM_EXE = core.ROOT / "experiments/xrt/build/queryclass-20261029-01/translated-stream/translated.exe"


def prepare(out, exe=STREAM_EXE, *, stop_symbol="xrt_report_write", integrated=True):
    """Use the same factory, symbol/type queries, on_create and update as production.

    The fixture plan identifies a non-game sentinel, never a guest renderer stop.
    The real candidate's guest 0x0696f292 mapping is separately verified offline.
    """
    import pefile
    legacy = load("supervisor_non_game_observer", core.ROOT / "out/recovery/viewport-getobject-20261028-01/bounded_genuine.py")
    legacy.V.EXE, legacy.V.EXPECTED = exe, core.sha(exe)
    d = C.WinDLL("dbghelp", use_last_error=True)
    api, k = legacy.D.api, legacy.D.K
    handle = api(k, "GetCurrentProcess", [], T.HANDLE)()
    api(d, "SymSetOptions", [T.DWORD], T.DWORD)(0x81202)
    core.require(api(d, "SymInitializeW", [T.HANDLE, C.c_wchar_p, T.BOOL])(handle, str(exe.parent), False), "fixture symbols init")
    symbols = {}
    try:
        base = api(d, "SymLoadModuleExW", [T.HANDLE, T.HANDLE, C.c_wchar_p, C.c_wchar_p, C.c_ulonglong, T.DWORD, C.c_void_p, T.DWORD], C.c_ulonglong)(handle, None, str(exe), None, 0x140000000, 0, None, 0)
        core.require(base, "fixture symbols load")
        names = ["events", "event_seq", stop_symbol]
        if stop_symbol == "supervisor_fixture_stop": names.append("supervisor_sentinel")
        for name in names:
            s = legacy.D.Symbol(); s.SizeOfStruct = 88; s.MaxNameLen = 1023
            core.require(api(d, "SymFromName", [T.HANDLE, C.c_char_p, C.POINTER(legacy.D.Symbol)])(handle, name.encode(), C.byref(s)), "fixture symbol: " + name)
            symbols[name] = dict(rva=s.Address-base, size=s.Size)
    finally:
        core.require(api(d, "SymCleanup", [T.HANDLE])(handle), "fixture symbols cleanup")
    with pefile.PE(str(exe), fast_load=True) as pe:
        stop_rva = symbols[stop_symbol]["rva"]
        stop_bytes = pe.get_data(stop_rva, 8).hex()
    plan = dict(symbols=symbols, stop_rva=stop_rva, stop_bytes=stop_bytes,
                qualification_sentinel_only=True, executable=str(exe), sha256=core.sha(exe), pdb_sha256=core.sha(exe.with_suffix('.pdb')))
    core.atomic(out / "fixture-plan.json", plan)
    checks = []
    if integrated:
        observer = construct(legacy, out, plan, checks.append, [exe])
    else:
        observer = legacy.observer(out, plan, checks.append)
    return observer, plan, checks


def execute(observer, out, cmd, setup=None):
    sandbox = out / "sandbox"; sandbox.mkdir()
    if setup: setup(sandbox)
    env = fixture.environment(sandbox); env["XRT_EVENT_STREAM"] = str(out / "stream.raw.bin")
    with (out / "stdout.bin").open("xb") as stdout, (out / "stderr.bin").open("xb") as stderr:
        return observer.run(cmd, cwd=sandbox, env=env, stdout=stdout, stderr=stderr, timeout=15)


def build(out):
    target = out / "observer-build"; target.mkdir()
    recipe = core.read_large(core.ROOT / "out/recovery/queryclass-20261029-01/stream-test/build.json")["command"]
    source = core.ROOT / "tools/xrt/supervisor/observer_fixture.c"
    cmd = [str(source) if Path(s).name == "host.c" else s.replace(str(STREAM_EXE.parent), str(target)) for s in recipe]
    helper = load("supervisor_observer_fixture_compiler", core.ROOT / "experiments/xrt/tests/getobject_boundary/phase.py")
    helper.O = out
    p = subprocess.run(cmd, cwd=target, env=helper.env(), capture_output=True, timeout=60)
    (out / "observer-build.stdout.bin").write_bytes(p.stdout)
    (out / "observer-build.stderr.bin").write_bytes(p.stderr)
    core.require(p.returncode == 0 and b"C1001" not in p.stdout and b"D8040" not in p.stdout, "observer fixture build failed")
    core.atomic(out / "observer-build.json", dict(command=cmd, exit=p.returncode, source_sha256=core.sha(source), outputs=core.tree(target)))
    return target / "translated.exe"


def qualify(out):
    directory = out / "production-observer-live"; directory.mkdir()
    exe = build(directory)
    results = []
    for case in ("dispatch", "fatal", "import-fatal", "guest-fatal", "module-denied"):
        dest = directory / case; dest.mkdir()
        case_exe = STREAM_EXE if case == "guest-fatal" else exe
        stop_symbol = "xrt_report_write" if case == "guest-fatal" else "supervisor_fixture_stop"
        observer, plan, checks = prepare(dest, case_exe, stop_symbol=stop_symbol)
        original_hit = observer.hit

        def hit(self, tag, ctx, tid):
            if tag != "hard_stop_0696f292": return original_hit(tag, ctx, tid)
            core.require(case == "dispatch" and ctx.get("rip") == self.base + plan["stop_rva"], "unexpected fixture sentinel")
            core.require(self.u32(self.sym("supervisor_sentinel")) == 0x55555555, "fixture sentinel instruction executed")
            self.snapshot_events()
            self.log("fixture_permanent_stop", instruction_executed=False, sentinel_unchanged=True,
                     production_renderer_hit_assertions_exercised=False)
            self.stop_requested = True

        observer.hit = MethodType(hit, observer)
        setup = None
        if case == "module-denied":
            def setup(sandbox):
                shutil.copy2(Path(os.environ['SystemRoot']) / 'System32/version.dll', sandbox / 'observer-policy.dll')
        error = None
        cmd = [str(case_exe), case]
        if case == "guest-fatal":
            cmd = [str(case_exe), str(core.ROOT / 'experiments/xrt/build/queryclass-20261029-01/x86/viewportprobe.dll'),
                   str(dest / 'FORBIDDEN-report.json'), 'nonzero']
        try:
            execute(observer, dest, cmd, setup)
            core.require(case == "dispatch", "expected fixture rejection absent")
        except RuntimeError as exc:
            error = str(exc)
            if case in ("fatal", "import-fatal", "guest-fatal"):
                core.require(core.expected_fatal(observer.rows, dict(kind="first-unsupported-or-permanent")), "production fatal evidence invalid")
            else:
                core.require(case == "module-denied" and "outside approved dependency profile" in error, "unexpected observer failure: " + error)
        core.require(checks == ["target-created-before-first-resume"], "production on_create was not exercised")
        core.require(observer.cleanup['passed'] and observer.cleanup['remaining_job_processes'] == 0, "observer cleanup")
        core.require(not (dest / 'sandbox/FORBIDDEN.txt').exists(), "fixture sentinel executed")
        core.require(not (dest / 'FORBIDDEN-report.json').exists(), "runtime fatal body executed")
        core.require(any(r['kind'] == 'terminated_before_continue' for r in observer.rows), "live observation resumed")
        core.require(any(r['kind'] == 'module_identity' and not r['system_dependency'] for r in observer.rows), "executable module identity absent")
        core.require(any(r['kind'] == 'module_identity' and r['system_dependency'] for r in observer.rows), "DLL module identities absent")
        readbacks = [r for r in observer.rows if r['kind'] == 'breakpoints_readback']
        core.require(readbacks and all(r['permanent_stop_present'] for r in readbacks), "permanent sentinel readback absent")
        codes = {r['code'] for r in observer.rows if r['kind'] == 'debug_event'}
        expected_codes = {1, 3, 6} if case == 'guest-fatal' else {1, 2, 3, 4, 6, 8}
        core.require(expected_codes <= codes, "debug event dispatch coverage incomplete")
        if case == 'dispatch': core.require(5 in codes and observer.terminated_while_stopped, "stop dispatch incomplete")
        if (dest / 'runtime-events.raw.bin').exists():
            core.require((dest / 'runtime-events.raw.bin').read_bytes() == (dest / 'stream.raw.bin').read_bytes(), "production snapshot/stream mismatch")
        row = dict(case=case, passed=True, error=error, cleanup=observer.cleanup, debug_event_codes=sorted(codes),
                   production_construction_on_create_update=True, breakpoint_readbacks=len(readbacks),
                   terminate_before_continue=True, genuine_sessions=0)
        core.atomic(dest / 'result.json', row); results.append(row)
    core.atomic(directory / 'result.json', dict(passed=True, cases=results, genuine_sessions=0,
                sentinel_scope='Real production initialization/update; fixture-only stop instruction, real guest mapping verified offline.'))
    return dict(passed=True, evidence=str(directory), cases=results, executable_sha256=core.sha(exe), genuine_sessions=0)
