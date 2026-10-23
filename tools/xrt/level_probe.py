"""Bounded REAL client startup, in one isolated content tree shared by reference and candidate.

prepare copies System, selected map/package dependencies, and external runtime resources, never Save.
reference uses uctrace's controlled deadline (a deadline is NOT a completed tick). candidate runs the same
client command through the translated loader. Each invocation records inputs, commands, writes and identities.
No PASS is inferred from an exit status or map-open message. Raw evidence remains git-ignored.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_xrt as R
import asset_boundary as A

WS = Path(R.WS)
SB = WS / "sandbox_cmp/first-world"
SOURCE = A.source()
RAW = WS / "experiments/xrt/results/raw/level"
ARGS = ["CS_Intro.un2", "-windowed", "-nosound", "-NOMMX", "-NOSSE"]
MODULES = ["Unreal2.exe", "Core.dll", "Engine.dll", "GlmLib.dll", "Window.dll", "WinDrv.dll", "D3DDrv.dll",
           "ALAudio.dll", "Legend.dll", "UI.dll", "U2.dll", "U2AI.dll", "U2Dialog.dll", "ParticleSystems.dll", "IpDrv.dll"]
POINTS = [("Engine.dll", 0x8f460, "UGameEngine.Init"), ("Engine.dll", 0x90f00, "UGameEngine.LoadMap"),
          ("Unreal2.exe", 0x2ee0, "Launcher.Error.Serialize"),
          ("D3DDrv.dll", 0xd8a6, "D3D.Direct3DCreate8.return"),
          ("D3DDrv.dll", 0xd8d9, "D3D.GetAdapterCount.return"),
          ("D3DDrv.dll", 0xdab4, "D3D.GetDeviceCaps.call"),
          ("D3DDrv.dll", 0xdab7, "D3D.GetDeviceCaps.return"),
          ("Engine.dll", 0xb9160, "ULevel.PostLoad"), ("Engine.dll", 0x18a30, "AGameInfo.eventInitGame"),
          ("Engine.dll", 0x6630, "AActor.eventPreBeginPlay"), ("Engine.dll", 0x66a0, "AActor.eventBeginPlay"),
          ("Engine.dll", 0x6600, "AActor.eventPostBeginPlay"), ("Engine.dll", 0xb2300, "ULevel.SpawnPlayActor"),
          ("Engine.dll", 0x938f0, "UGameEngine.Tick"), ("Engine.dll", 0xb5be0, "ULevel.Tick"),
          ("WinDrv.dll", 0x17c0, "UWindowsClient.Init"), ("WinDrv.dll", 0x3390, "UWindowsViewport.OpenWindow"),
          ("WinDrv.dll", 0x184b, "DirectInput8Create.call"), ("WinDrv.dll", 0x1850, "DirectInput8Create.return"),
          ("WinDrv.dll", 0x1939, "UWindowsClient.Init.return"),
          ("WinDrv.dll", 0x49b0, "UWindowsViewport.TryRenderDevice")]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot():
    return A.inventory(SB)


def save(p, value):
    p.write_text(json.dumps(value, indent=2), encoding="utf-8")


def prepare():
    A.check_writable(SB)
    if SB.exists():
        raise RuntimeError(f"preserving existing {SB}; prepare refuses to replace it")
    shutil.copytree(SOURCE, SB)
    print("prepared verified independent run tree", SB, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["prepare", "reference", "candidate"])
    ap.add_argument("--timeout-ms", type=int, default=90000)
    ap.add_argument("--minimal", action="store_true", help="reference: milestone breakpoints only, no function/import census")
    ap.add_argument("--d3d8-backend", choices=["dxvk"], help="candidate: verified official x64 DXVK 3.1.1 D3D8/D3D9 pair")
    ap.add_argument("--package", action="append", default=[], help="stage a verified snapshot package into the sandbox (repeatable)")
    a = ap.parse_args()
    if a.d3d8_backend and a.mode!='candidate':ap.error('--d3d8-backend requires candidate mode')
    if not 1 <= a.timeout_ms <= 600000:
        ap.error("timeout must be 1..600000 ms")
    A.verify()
    if a.mode == "prepare":
        prepare()
        A.verify()
        return 0
    A.check_writable(SB)
    A.inventory(SB)  # Reject aliases before restoring writable configuration.
    ident = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    out = RAW / (ident + "-" + a.mode)
    out.mkdir(parents=True, exist_ok=False)
    exe = SB / "System/Unreal2.exe"
    staged = []
    for relative in a.package:
        source = (SOURCE / relative).resolve()
        relative = source.relative_to(SOURCE.resolve())
        if source.suffix.lower() not in {".utx", ".u", ".usx", ".uax", ".ugx"} or not source.is_file():
            raise RuntimeError("expected a verified snapshot package")
        dest = SB / relative
        if dest.exists() and sha(dest) != sha(source):
            raise RuntimeError(f"preserving different existing sandbox package: {dest}")
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        staged.append(dict(R.file_identity(str(source)), destination=relative.as_posix()))
    # Restore only the known mutable config files; preserve every run's written versions first.
    pristine = SOURCE / "System"
    for p in pristine.glob("*"):
        if p.suffix.lower() == '.ini' or p.name == 'Golem.u':
            shutil.copy2(p, SB / "System" / p.name)
    for name in ["Unreal2.log", "Running.ini"]:
        p = SB / "System" / name
        if p.exists():
            p.unlink()
    before = snapshot()
    meta = {"id": ident, "mode": a.mode, "git": R.git_identity(), "sandbox": str(SB), "args": ARGS,
            "staged_packages": staged,
            "probe_driver": R.file_identity(str(Path(__file__).resolve())),
            "before": before, "runtime_sources": R.tree_digest(str(WS / "experiments/xrt/runtime")),
            "generated_code": R.tree_digest(str(WS / "experiments/xrt/gen"))}
    env = R.tracer_env(ident)
    if a.mode == "reference":
        entries = RAW / ("milestone-only-entries" if a.minimal else "entries")
        entries.mkdir(exist_ok=True)
        for module in ([] if a.minimal else MODULES):
            dest = entries / (module.lower() + ".txt")
            if not dest.exists():
                # Existing entry sets are tied to unchanged sandbox binaries by staging/input hashes.
                cached = Path(R.ENTRIES) / dest.name
                if cached.exists():
                    shutil.copy2(cached, dest)
                else:
                    with (out / (module + ".discovery.log")).open("wb") as f:
                        subprocess.run([sys.executable, "-I", str(HERE / "discover.py"), str(SB / "System" / module),
                                        "--entries", str(dest)], stdout=f, stderr=subprocess.STDOUT, check=True)
        points = out / "points.txt"
        points.write_text("".join(f"{m} {r:x} {label}\n" for m, r, label in POINTS))
        env.update(UCTRACE_TIMEOUT_MS=str(a.timeout_ms), UCTRACE_EVENTS=str(points),
                   UCTRACE_STOP_LABEL="Launcher.Error.Serialize",
                   UCTRACE_SITES="MessageBox,Direct3DCreate8,DirectDrawCreate,CreateFile,GetModuleHandleA")
        cmd = [R.TRACER, str(entries), str(out / "trace.json"), str(out / "stdout.bin"), str(exe)] + ARGS
        meta["tracer"] = R.file_identity(R.TRACER)
        meta["trace_mode"] = "milestone_only" if a.minimal else "function_import_census"
        meta["tracer_environment"] = {k:v for k,v in env.items() if k.startswith("UCTRACE_")}
        meta["points_sha256"] = sha(points)
    else:
        if a.d3d8_backend:
            import graphics_backend as G
            backend=G.verified_pair('x64')
            env['XRT_D3D8_DIR']=str(backend)
            meta['graphics_environment']=G.environment(env,out)
            meta['graphics_environment']['XRT_D3D8_DIR']=str(backend)
            meta['graphics_backend']={'implementation':'DXVK 3.1.1 x64 D3D8 over DXVK D3D9/Vulkan',
                                      'files':[R.file_identity(str(backend/name)) for name in G.HASHES['x64']]}
        cmd = [R.XRT, "--guest", str(exe), "--log", str(out / "xrt.log"), "--report", str(out / "report.json"),
               "--run-id", ident, "--timeout-ms", str(a.timeout_ms), "--"] + ARGS
        meta["candidate"] = R.file_identity(R.XRT)
    meta.update(command=cmd, cwd=str(exe.parent))
    save(out / "meta.json", meta)
    with (out / "host-output.txt").open("wb") as f:
        p = subprocess.run(cmd, cwd=exe.parent, stdout=f, stderr=subprocess.STDOUT, env=env,
                           timeout=a.timeout_ms / 1000 + 45)
    meta["exit_code"] = p.returncode
    if a.mode == 'candidate' and R.file_identity(R.XRT) != meta['candidate']:
        raise RuntimeError('candidate executable changed during experiment')
    after = snapshot()
    A.check_run_inputs(before, after)
    changed = {p: h for p, h in after.items() if before.get(p) != h}
    meta.update(written=changed, deleted=sorted(before.keys() - after.keys()))
    for path in changed:
        dest = out / "written" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SB / path, dest)
    save(out / "meta.json", meta)
    A.verify()
    print(a.mode, p.returncode, out, flush=True)
    return p.returncode


if __name__ == "__main__":
    with R.CaseLock("level"), R.CaseLock("graphics-client-session"):
        sys.exit(main())
