"""Fixed renderer initialization profile. Invoked only after owner batch gates."""
import os
import shutil
import sys
import time
from . import core
from .environment import load
from .fixture import environment
from .plan import resolve
from .observer import construct


def run(m, request, out, sandbox, stop, desktop, seal):
    input_before=dict(state=desktop.owner.V.state(),physical_clip=desktop.expected['clip'])
    input_cleanup=out/'input-cleanup';input_cleanup.mkdir()
    # The inherited observer and its transitive dependencies are sealed before import.
    legacy = load("desktop_supervisor_retained_observer", core.ROOT / "out/recovery/viewport-getobject-20261028-01/bounded_genuine.py")
    legacy.V.EXE = core.ROOT / m["executable"]
    legacy.V.EXPECTED = m["sha256"]
    plan = resolve(legacy.S, legacy.E, legacy.V, m["pdb_sha256"])
    core.require(plan["static_mapping_verified"] and plan["guest_stop"] == 0x696f292, "permanent mapping gate")
    core.atomic(out / "debugger-plan.json", plan)
    # Keep all strict x87, WNDPROC and renderer parameter assertions in the observer.
    capture = construct(legacy, out, plan, lambda tag: desktop.check(out, tag),
                        [core.ROOT / m["executable"], *[core.ROOT / rel for rel in m["dependencies"]]])
    A, R = legacy.D.Assets, legacy.D.R
    sys.path.insert(0, str(core.ROOT / "tools/xrt"))
    import graphics_backend as G
    helper = core.ROOT / seal["helper"]["path"]
    protected = A.verify()
    A.check_writable(sandbox)
    # sandbox is an exclusively created empty directory owned by this attempt.
    shutil.copytree(A.source(), sandbox, dirs_exist_ok=True)
    before = A.inventory(sandbox)
    env = environment(sandbox)
    G.environment(env, out)
    env.update(XRT_BINARY=str(legacy.V.EXE), XRT_DMUSIC_BACKEND="ipc", XRT_DMUSIC_HELPER=str(helper),
               XRT_ASSET_MANIFEST=str(A.DEFAULT_MANIFEST), XRT_STOP_FIRST_LEVEL_TICK="1",
               XRT_EVENT_STREAM=str(out / "runtime-stream.raw.bin"),
               XRT_D3D8_DIR=str(G.verified_pair("x64")))
    cmd = [str(legacy.V.EXE), "--guest", str(sandbox / "System/Unreal2.exe"),
           "--log", str(out / "xrt.log"), "--report", str(out / "runtime-report.json"),
           "--run-id", request["id"], "--timeout-ms", str(request["timeout_seconds"] * 1000),
           "--", "CS_Intro.un2", "-windowed", "-nosound", "-NOMMX", "-NOSSE"]
    core.atomic(out / "launch-profile.json", dict(command=cmd, cwd=str(sandbox / "System"), environment=env,
                                                protected=protected, sandbox_before=before))
    classification = "unclassified-discrepancy"
    error = None
    try:
        with R.CaseLock("level"), R.CaseLock("graphics-client-session"):
            core.require(not legacy.V.P.processes(), "another game/helper process exists")
            desktop.check(out, "before-launch")
            with (out / "stdout.bin").open("xb") as stdout, (out / "stderr.bin").open("xb") as stderr:
                try:
                    core.require(time.time()<request['expires_at'] and not stop(), 'authorization expired/stopped before launch')
                    capture.run(cmd, cwd=sandbox / "System", env=env, stdout=stdout, stderr=stderr,
                                timeout=request["timeout_seconds"], stop=stop)
                except TimeoutError:
                    classification = "timeout"
                except RuntimeError as exc:
                    error = str(exc)
                    if core.expected_fatal(capture.rows,request["expected_stop"]):
                        classification = "expected-unsupported-method"
                    else:
                        raise
        if (out / "hard-stop.json").exists():
            core.require(capture.terminated_while_stopped, "stop resumed")
            # Preserve complete renderer validation when the expected permanent stop is reached.
            legacy.audit(out)
            (out / "result.json").rename(out / "renderer-audit.json")
            classification = "permanent-stop" if request["expected_stop"]["kind"] in ("permanent-stop","first-unsupported-or-permanent") else "unexpected-stop"
        return dict(classification=classification, passed=classification in ("expected-unsupported-method", "permanent-stop"),
                    error=error, cleanup=capture.cleanup, gameplay_verified=False,
                    strict_x87="FAILED; historical failure retained", strict_wndproc_equality="FAILED; historical failure retained")
    finally:
        # Eligibility is written only after every independent post-run check.
        core.atomic(out / "cleanup.json", getattr(capture, "cleanup", dict(passed=False, launch_started=False)))
        # Restore only the captured cursor/StickyKeys baseline if the child
        # changed it, retaining the existing owner cleanup safeguard. No display
        # setting is changed. The final physical observation still must match.
        desktop.owner.RUN=input_cleanup
        desktop.owner.restore_and_check(input_before)
        core.require(A.verify() == protected, "protected assets changed")
        after = A.inventory(sandbox)
        A.check_run_inputs(before, after)
        core.atomic(out / "sandbox-after.json", after)
        stream=out / "runtime-stream.raw.bin"
        if stream.exists():
            import json
            raw=stream.read_bytes()
            core.require(len(raw)%448==0,"partial runtime stream record")
            rows=[json.loads(raw[i:i+448].split(b'\0',1)[0]) for i in range(0,len(raw),448)]
            rows.sort(key=lambda r:r['seq'])
            core.require([r['seq'] for r in rows]==list(range(1,len(rows)+1)),"runtime stream gaps")
            core.require(not any(r.get('truncated') for r in rows),"truncated runtime events")
            snapshot=out / "runtime-events.json"
            if snapshot.exists():
                core.require(rows==core.read_large(snapshot)['events'],"stream/stopped-memory discrepancy")
            core.atomic(out / "runtime-stream-summary.json",dict(records=len(rows),contiguous=True,
                        stopped_memory_equal=snapshot.exists(),complete_committed_records=True))
        desktop.check(out, "after-cleanup")
        stderr_text = (out/'stderr.bin').read_text(errors='replace') if (out/'stderr.bin').exists() else ''
        guard_closed = ('DirectMusic helper fatal: cannot install isolated disk-open guard' in stderr_text
                        and 'DirectMusic IPC seq' not in stderr_text
                        and any(r['kind']=='terminated_before_continue' for r in capture.rows))
        sta_closed = ('DirectMusic helper fatal: cannot initialize STA' in stderr_text
                      and 'DirectMusic IPC seq' not in stderr_text)
        core.atomic(out/'assurance.json', dict(cleanup_verified=capture.cleanup.get('passed') is True,
                    integrity_verified=True, guard_failed_closed=guard_closed,
                    helper_startup_failed=sta_closed,
                    unexpected_host_crash=('DirectMusic child exited' in (error or '') and not guard_closed and not sta_closed)))

