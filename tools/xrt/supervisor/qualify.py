"""Non-game qualification only; production observer construction, no game launch."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid
from . import core
from . import fixture
from .environment import load, ordinary_user, Desktop
from .service import Service, seal_files
from .windows import Exclusive, FilePins


def build(out):
    build_dir = core.ROOT / "experiments/xrt/build/desktop-supervisor"
    build_dir.mkdir(exist_ok=True)
    # Serial build with the repository's existing compiler environment collector.
    helper = load("supervisor_compiler_environment", core.ROOT / "experiments/xrt/tests/getobject_boundary/phase.py")
    helper.O = out
    env = helper.env()
    cmd = [shutil.which("cl", path=env.get("Path", env.get("PATH"))), "/nologo", "/O1", "/W4", "/MT",
           "/Fe" + str(build_dir / "fixture.exe"), "/Fo" + str(build_dir / "fixture.obj"),
           str(core.ROOT / "tools/xrt/supervisor/fixture.c"), "/link", "/DYNAMICBASE"]
    p = subprocess.run(cmd, cwd=build_dir, env=env, capture_output=True, timeout=60)
    (out / "build.stdout.bin").write_bytes(p.stdout);(out / "build.stderr.bin").write_bytes(p.stderr)
    core.require(p.returncode == 0 and b"C1001" not in p.stdout and b"D8040" not in p.stdout, "fixture build failed")
    return build_dir / "fixture.exe"


def request(service, exe, case):
    ident = str(uuid.uuid4())
    manifest = dict(version=1, kind="fixture", executable=exe.relative_to(core.ROOT).as_posix(), sha256=core.sha(exe),
                    pdb_sha256=None, build_record=None, build_record_sha256=None,
                    sources={"tools/xrt/supervisor/fixture.c": core.sha(core.ROOT / "tools/xrt/supervisor/fixture.c")},
                    dependencies={}, fixture_case=case)
    candidate = service.home / "candidates" / (ident + ".json")
    core.atomic(candidate, manifest)
    req = dict(version=1, id=ident, batch_id=service.batch["id"], created_at=time.time(), expires_at=time.time() + 240,
               objective="Non-game persistent queue qualification: " + case,
               candidate='out/desktop-supervisor/candidates/'+ident+'.json', manifest_sha256=core.sha(candidate),
               expected_stop=dict(kind="fixture-breakpoint" if case == "hard-stop" else "fixture-complete"),
               scope=core.FIXTURE_SCOPE, timeout_seconds=15)
    path = service.home / "requests" / (ident + ".json")
    core.atomic(path, req)
    return path


def direct(exe, out, case, *, cancel=False):
    directory=out / case;directory.mkdir();sandbox=directory / "sandbox";sandbox.mkdir()
    probe=fixture.Probe(directory,sandbox,case)
    stop=threading.Event()
    if cancel:
        timer=threading.Timer(.8,stop.set);timer.start()
    try:
        with (directory / "stdout.bin").open("wb") as stdout,(directory / "stderr.bin").open("wb") as stderr:
            try:
                probe.run([str(exe),case],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,
                          timeout=10 if cancel else 2,stop=stop.is_set)
                raise AssertionError("qualification should have stopped")
            except TimeoutError:
                core.require(case in ("hang","tree"),"unexpected timeout")
            except RuntimeError as e:
                core.require(case=="fatal-stop" and "injected fatal" in str(e),"unexpected observation failure")
        core.require(probe.cleanup["passed"] and not (sandbox / "FORBIDDEN.txt").exists(),"cleanup/stop failure")
        if case == "tree":
            pid=core.read(sandbox / "child.json")["pid"]
            from .windows import api,K,Close
            import ctypes as C
            from ctypes import wintypes as T
            handle=api(K,"OpenProcess",[T.DWORD,T.BOOL,T.DWORD],T.HANDLE)(0x1000,False,pid)
            if handle:
                code=T.DWORD();api(K,"GetExitCodeProcess",[T.HANDLE,C.POINTER(T.DWORD)])(handle,C.byref(code));Close(handle)
                core.require(code.value!=259,"descendant still running")
        if case=="fatal-stop":
            core.require(any(r["kind"]=="terminated_before_continue" and r.get("observation_failed") for r in probe.rows),"fatal continued")
        core.atomic(directory / "result.json",dict(passed=True,case=case,cleanup=probe.cleanup,cancel=cancel))
        return dict(case=case,passed=True,cleanup=probe.cleanup,cancel=cancel)
    finally:
        if cancel:timer.cancel()


def runtime_stream_stop(out, D):
    """Stop an actual translated non-game runtime before xrt_fatal executes."""
    import ctypes as C
    from ctypes import wintypes as T
    directory=out/'live-runtime-stream';directory.mkdir();sandbox=directory/'sandbox';sandbox.mkdir()
    exe=core.ROOT/'experiments/xrt/build/queryclass-20261029-01/translated-stream/translated.exe'
    dll=core.ROOT/'experiments/xrt/build/queryclass-20261029-01/x86/viewportprobe.dll'
    dbg=C.WinDLL('dbghelp',use_last_error=True);api=D.api
    handle=api(D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(dbg,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    core.require(api(dbg,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(handle,str(exe.parent),False),'symbols init')
    symbols={}
    try:
        base=api(dbg,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(handle,None,str(exe),None,0x140000000,0,None,0)
        core.require(base,'symbols load')
        for name in ('xrt_fatal','events','event_seq'):
            s=D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            core.require(api(dbg,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(D.Symbol)])(handle,name.encode(),C.byref(s)),'symbol '+name)
            symbols[name]=s.Address-base
    finally:api(dbg,'SymCleanup',[T.HANDLE])(handle)
    class RuntimeProbe(fixture.Probe):
        def on_create(self,ev):self.breakpoints={self.base+symbols['xrt_fatal']:'fatal'}
        def hit(self,tag,ctx,tid):
            core.require(tag=='fatal' and ctx.get('rdx')&0xffffffff==76,'unexpected runtime stop')
            count=int.from_bytes(self.mem(self.base+symbols['event_seq'],8),'little')
            pointer=int.from_bytes(self.mem(self.base+symbols['events'],8),'little')
            raw=self.mem(pointer,count*448)
            (directory/'stopped-memory.raw.bin').write_bytes(raw)
            core.require(raw==(directory/'stream.raw.bin').read_bytes(),'stream/stopped memory mismatch')
            core.require(count>0,'empty runtime stream')
            self.log('runtime_stream_verified',records=count,fatal_body_executed=False)
            self.stop_requested=True
    probe=RuntimeProbe(directory,sandbox,'runtime-stream')
    env=fixture.environment(sandbox);env['XRT_EVENT_STREAM']=str(directory/'stream.raw.bin')
    with (directory/'stdout.bin').open('wb') as stdout,(directory/'stderr.bin').open('wb') as stderr:
        probe.run([str(exe),str(dll),str(directory/'FORBIDDEN-report.json'),'nonzero'],cwd=sandbox,env=env,stdout=stdout,stderr=stderr,timeout=15)
    core.require(probe.terminated_while_stopped and probe.cleanup['passed'] and not (directory/'FORBIDDEN-report.json').exists(),'runtime termination failed')
    result=dict(passed=True,terminated_before_fatal_body=True,complete_stream_equal_stopped_memory=True,
                cleanup=probe.cleanup,executable_sha256=core.sha(exe),genuine_sessions=0)
    core.atomic(directory/'result.json',result)
    return result


def host_files():
    paths={Path(sys.executable),Path(sys._base_executable)}
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if not file:continue
        path=Path(file)
        if path.is_file() and (path.is_relative_to(Path(sys.base_prefix)) or path.is_relative_to(core.ROOT/'.venv')):
            paths.add(path)
    paths.update(Path(sys.base_prefix).glob('python*.dll'))
    import capstone
    paths.update(Path(capstone.__file__).parent.rglob('*.dll'))
    return {str(p.resolve()):core.sha(p) for p in sorted(paths)}


def main():
    ordinary_user()
    core.HOME.mkdir(parents=True,exist_ok=True)
    out=core.HOME / ("qualification-"+str(uuid.uuid4()));out.mkdir()
    with Exclusive(core.HOME / "supervisor.lock"):
        command=[sys.executable,"-B","-I","-m","unittest","discover","-s",str(core.ROOT / "tools/xrt/supervisor/tests"),"-v"]
        unit_env=dict(os.environ,SUPERVISOR_TEST_OUTPUT=str(out))
        p=subprocess.run(command,cwd=core.ROOT,env=unit_env,capture_output=True,timeout=60)
        (out / "unit.stdout.bin").write_bytes(p.stdout);(out / "unit.stderr.bin").write_bytes(p.stderr)
        core.require(p.returncode==0,"unit safety tests failed")
        exe=build(out)
        # Qualification has its own queue/status/ledger, including when the
        # production batch is halted. Never rewrite or clear production history.
        service=Service(out / "queue",0,qualification=True)
        core.require(not service.halted,"qualification queue halted")
        results=[]
        failures=[]
        def serve():
            try:service.serve()
            except BaseException as error:failures.append(str(error))
        worker=threading.Thread(target=serve,name="qualification-queue")
        worker.start()
        try:
            for case in ("ok-a","ok-b","hard-stop"):
                path=request(service,exe,case)
                response=service.home / "responses" / path.name
                deadline=time.monotonic()+25
                while not response.exists() and not failures and time.monotonic()<deadline:time.sleep(.05)
                core.require(response.exists(),"persistent queue response missing: "+str(failures))
                result=core.read(response);results.append(result)
                core.require(result.get("passed"),"request/result cycle failed: "+str(result))
        finally:
            service.shutdown=True;worker.join(timeout=10)
            core.require(not worker.is_alive() and not failures,"queue thread shutdown failed")
            service.shutdown=False
        # Replay the exact archived request, preserving the original response.
        first=core.read(Path(results[0]["evidence"]) / "request.json")
        replay=service.home / "requests" / (first["id"]+".json");core.atomic(replay,first)
        core.require(service.process(replay)["classification"]=="rejected","replay accepted")
        live=[direct(exe,out,"hang"),direct(exe,out,"tree"),direct(exe,out,"fatal-stop")]
        cancel_out=out / "local-stop";cancel_out.mkdir();live.append(direct(exe,cancel_out,"tree",cancel=True))
        with FilePins() as pins:
            pins.pin(exe,core.sha(exe))
            blocked=False
            try:
                with exe.open("r+b") as f:f.write(b"MZ")
            except PermissionError:blocked=True
            core.require(blocked,"pinned executable writable")
        # Observe actual construction context; genuine physical acceptance is
        # deferred to the owner process if this automation context is isolated.
        desktop=Desktop();data=desktop.owner.observe();core.atomic(out / "construction-environment.json",data)
        measured=next(r for r in data['cursor_observer']['rows'] if r['tag']=='per-monitor-v2')
        input_before=dict(state=desktop.owner.V.state(),physical_clip=measured['clip'])
        desktop.owner.RUN=out/'input-cleanup';desktop.owner.RUN.mkdir()
        desktop.owner.restore_and_check(input_before)
        try:
            desktop.check(out,"construction-gate");desktop_pass=True
        except Exception as e:
            desktop_pass=False;core.atomic(out / "construction-gate-rejection.json",dict(reason=str(e),rejected=True))
        strict=core.read_large(core.ROOT / "out/recovery/viewport-getobject-20261028-01/strict-failures-retained.json")
        core.require(strict["x87"]==strict["wndproc_equality"]=="FAILED","strict failures lost")
        pinned=core.read_large(core.ROOT / "out/recovery/viewport-getobject-20261028-01/pinned-inputs.json")
        helper_path=Path(pinned["inputs"]["helper"]["path"])
        helper=dict(path=helper_path.relative_to(core.ROOT).as_posix(),sha256=core.sha(helper_path))
        dependencies={helper["path"]:helper["sha256"]}
        sys.path.insert(0,str(core.ROOT / "tools/xrt"));import graphics_backend as G
        for name in G.HASHES['x64']:
            dependency=G.verified_pair('x64') / name
            dependencies[dependency.relative_to(core.ROOT).as_posix()]=core.sha(dependency)
        # Non-game stop mapping is resolved for the new candidate without launching it.
        from .plan import resolve
        retained=load('supervisor_offline_candidate_mapping',core.ROOT / 'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
        build_record=core.ROOT / 'out/recovery/queryclass-20261029-01/build.json'
        built=core.read_large(build_record);retained.V.EXE=Path(built['root'])/'xrt_ucc.exe';retained.V.EXPECTED=built['binary_sha256']
        plan=resolve(retained.S,retained.E,retained.V,built['pdb_sha256'])
        core.require(plan['static_mapping_verified'] and plan['guest_stop']==0x696f292,'candidate permanent mapping failed')
        core.atomic(out/'candidate-debugger-plan.json',plan)
        offline=out/'offline-production-observer';offline.mkdir()
        from .observer import construct
        observer=construct(retained,offline,plan,lambda _:None,[retained.V.EXE])
        core.require(observer.created==0 and observer._fatal_evidence_installed,'production observer construction failed')
        observer.log('offline_construction_verified',genuine_sessions=0)
        stream_test=runtime_stream_stop(out,retained.D)
        from .observer_checks import qualify as qualify_observer
        observer_test=qualify_observer(out)
        from .helper_checks import qualify as qualify_helper
        helper_guard=qualify_helper(out,helper=helper_path)
        from .autonomy_checks import qualify as qualify_autonomy
        autonomy=qualify_autonomy(out,exe,helper)
        desktop.owner.restore_and_check(input_before)
        seal=dict(passed=True,created_at=time.time(),files=seal_files(),host_files=host_files(),fixture_sha256=core.sha(exe),
                  genuine_sessions_launched=0,persistent_requests=results,live_safety=live,
                  physical_gate_passed_in_construction_context=desktop_pass,
                  owner_physical_gate_required=True,helper=helper,candidate_dependencies=dependencies,
                  permanent_mapping_verified_without_launch=True,live_runtime_stream=stream_test,
                  production_observer_integration=observer_test,strict_x87="FAILED; retained separately",
                  helper_guard=helper_guard,
                  operational_state_qualification=autonomy,
                  strict_wndproc_equality="FAILED; retained separately",evidence=str(out))
        core.atomic(core.HOME / "qualification.json",seal)
        core.atomic(out / "qualification.json",seal)
        service.publish(state="qualified-stopped")
        print("NON-GAME QUALIFICATION PASS; zero genuine launches. Evidence:",out)


if __name__=="__main__":main()
