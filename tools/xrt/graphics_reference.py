"""Run the original client in a fresh copy with one pinned x86 D3D8 wrapper.

The wrapper releases must already be downloaded from their official GitHub releases
into ignored third_party/graphics. This driver never downloads or changes the install.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import level_probe as L
import run_xrt as R

WRAPPERS = {
    "d3d8to9": ("d3d8to9-v1.16.0/d3d8.dll", "1.16.0",
                 "122928cfe225c25d30decf7184a5d37e490cecf3b58256ba3206c7e1853f8ab8"),
    "dgvoodoo": ("dgVoodoo2-v2.87.5/extracted/MS/x86/D3D8.dll", "2.87.5",
                  "d03e2562178db1fcf3493fc0a0b23a465e35c55d73adb3ec095be866cd662704"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configuration", choices=["system", "d3d8to9", "dgvoodoo"])
    parser.add_argument("--timeout-ms", type=int, default=60000)
    args = parser.parse_args()
    if not 1 <= args.timeout_ms <= 120000:
        parser.error("timeout must be 1..120000 ms")
    dll, wrapper = None, None
    if args.configuration in WRAPPERS:
        relative, version, digest = WRAPPERS[args.configuration]
        dll = L.WS / "third_party/graphics" / relative
        if L.sha(dll) != digest:
            raise RuntimeError("wrapper hash differs from the verified official release")
        import pefile
        if pefile.PE(str(dll), fast_load=True).FILE_HEADER.Machine != 0x14c:
            raise RuntimeError("wrapper must be x86; it cannot be loaded into the translated x64 host")
        wrapper = dict(R.file_identity(str(dll)), version=version, architecture="x86")

    ident = uuid.uuid4().hex[:12] + "-" + args.configuration
    root = L.WS / "sandbox_cmp/graphics-client" / ident
    out = L.WS / "experiments/xrt/results/raw/graphics-startup" / ident
    out.mkdir(parents=True, exist_ok=False)
    shutil.copytree(L.SB, root)
    for source in (L.RAW / "pristine-config").glob("*"):
        shutil.copy2(source, root / "System" / source.name)
    for name in ["Unreal2.log", "Running.ini"]:
        (root / "System" / name).unlink(missing_ok=True)
    if args.configuration == "dgvoodoo":
        source = L.WS / "third_party/graphics/dgVoodoo2-v2.87.5/extracted/dgVoodoo.conf"
        config = source.read_text()
        for name, value in [("OutputAPI", "d3d11_fl11_0"), ("FullScreenMode", "false"), ("CaptureMouse", "false")]:
            config, count = re.subn(r"(?m)^" + name + r"\s*=.*$", name + " = " + value, config)
            if count != 1:
                raise RuntimeError("unexpected official configuration format")
        (root / "System/dgVoodoo.conf").write_text(config)
    if dll:
        shutil.copy2(dll, root / "System/d3d8.dll")
    elif (root / "System/d3d8.dll").exists():
        raise RuntimeError("system reference contains a local d3d8.dll")

    entries = out / "entries"
    entries.mkdir()  # Milestone breakpoints only. Broad launcher import instrumentation perturbs this client.
    points = out / "points.txt"
    extra = [("Unreal2.exe", 0x6250, "FileReader.open"),
             ("Unreal2.exe", 0x62ba, "FileReader.CreateFileW.return"),
             ("Window.dll", 0x20e27, "Splash.GetDC.return"),
             ("Window.dll", 0x20e5a, "Splash.CreateDIBitmap.return"),
             ("Unreal2.exe", 0x4191, "Splash.LoadFileToBitmap.return"),
             ("Unreal2.exe", 0x43a5, "Splash.CreateDialog.return")]
    points.write_text("".join(f"{module} {rva:x} {label}\n" for module, rva, label in L.POINTS + extra))
    exe = root / "System/Unreal2.exe"
    env = R.tracer_env(ident)
    env.update(UCTRACE_TIMEOUT_MS=str(args.timeout_ms), UCTRACE_EVENTS=str(points),
               UCTRACE_STOP_LABEL="Launcher.Error.Serialize")
    command = [R.TRACER, str(entries), str(out / "trace.json"), str(out / "stdout.bin"), str(exe)] + L.ARGS
    before = {f.relative_to(root).as_posix(): L.sha(f) for f in root.rglob("*") if f.is_file()}
    meta = {"id": ident, "configuration": args.configuration, "sandbox": str(root), "command": command,
            "args": L.ARGS, "git": R.git_identity(), "driver": R.file_identity(str(Path(__file__).resolve())),
            "before": before, "tracer": R.file_identity(R.TRACER), "wrapper": wrapper,
            "environment": {k: v for k, v in env.items() if k.startswith("UCTRACE_")},
            "points_sha256": L.sha(points)}
    L.save(out / "meta.json", meta)
    with (out / "host-output.txt").open("wb") as output:
        result = subprocess.run(command, cwd=exe.parent, env=env, stdout=output, stderr=subprocess.STDOUT,
                                timeout=args.timeout_ms / 1000 + 45)
    meta["exit_code"] = result.returncode
    after = {f.relative_to(root).as_posix(): L.sha(f) for f in root.rglob("*") if f.is_file()}
    meta["written"] = {name: digest for name, digest in after.items() if before.get(name) != digest}
    for name in meta["written"]:
        dest = out / "written" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, dest)
    meta["deleted"] = sorted(before.keys() - after.keys())
    L.save(out / "meta.json", meta)
    trace = json.loads((out / "trace.json").read_text())
    print(out)
    print("loaded graphics modules:", [(m["name"], m["path"]) for m in trace["modules"]
          if m["name"].lower() in ["d3d8.dll", "d3d9.dll", "d3d11.dll", "d3d12.dll"]])
    print("trace status:", {k: trace.get(k) for k in ["exit_code", "complete", "termination_reason"]})
    print("events:", json.dumps([(e.get("label"), e.get("eax"), e.get("diagnostic_arg0_wide"))
          for e in trace.get("events", []) if e.get("label") in
          ["D3D.GetDeviceCaps.return", "UGameEngine.LoadMap", "Launcher.Error.Serialize"]], ensure_ascii=True))
    if result.returncode or not trace.get("complete") or trace.get("run_id") != ident:
        return 1
    return 0  # Completed investigation, NOT a game-success verdict.


if __name__ == "__main__":
    with R.CaseLock("graphics-client-session"):
        sys.exit(main())
