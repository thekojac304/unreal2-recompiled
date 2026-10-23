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
    parser.add_argument("configuration", choices=["system", "d3d8to9", "dgvoodoo", "dxvk"])
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--package", action="append", default=[],
                        help="installed singleplayer package, relative to its root (repeatable)")
    parser.add_argument("--stop-after-present", type=int, default=0,
                        help="controlled stop after N normal game Present returns")
    parser.add_argument("--capture-client", action="store_true",
                        help="capture this debuggee's client DC at the controlled Present stop")
    parser.add_argument("--stop-after-floor", type=int, default=0,
                        help="focused CRT observation: stop after N appRound floor returns, recording x87 state")
    parser.add_argument("--stop-after-ceil", type=int, default=0,
                        help="focused CRT observation: stop after N appCeil returns, recording x87 state")
    parser.add_argument("--stop-after-music-factory", action="store_true",
                        help="observe the original DirectMusic factories and stop after the second return")
    parser.add_argument("--music-trace", action="store_true", help="read-only DirectMusic argument/memory observation")
    parser.add_argument("--sound", action="store_true", help="omit -nosound for a controlled original comparison")
    parser.add_argument("--close-after-present", action="store_true", help="post WM_CLOSE at the bounded Present stop and trace normal cleanup")
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
    elif args.configuration=='dxvk':
        import graphics_backend as G
        backend=G.verified_pair('x86')
        dll=backend/'d3d8.dll'
        wrapper={'implementation':'DXVK 3.1.1 x86 D3D8 over DXVK D3D9/Vulkan',
                 'files':[R.file_identity(str(backend/name)) for name in G.HASHES['x86']]}

    ident = uuid.uuid4().hex[:12] + "-" + args.configuration
    root = L.WS / "sandbox_cmp/graphics-client" / ident
    out = L.WS / "experiments/xrt/results/raw/graphics-startup" / ident
    out.mkdir(parents=True, exist_ok=False)
    shutil.copytree(L.SB, root)
    staged = []
    for relative in args.package:
        source = (L.SOURCE / relative).resolve()
        relative = source.relative_to(L.SOURCE.resolve())
        if source.suffix.lower() not in {".utx", ".u", ".usx", ".uax", ".ugx"} or not source.is_file():
            raise RuntimeError("expected an installed game package")
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        staged.append(dict(R.file_identity(str(source)), destination=relative.as_posix()))
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
        if args.configuration=='dxvk':shutil.copy2(backend/'d3d9.dll',root/'System/d3d9.dll')
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
    # Instruction offsets verified against the staged game DLLs. RET points retain EAX;
    # a nonzero LoadMap result is still paired with actor/tick evidence before a world claim.
    extra += [("Engine.dll", 0x936a0, "UGameEngine.LoadMap.return"),
              ("Engine.dll", 0x9389a, "UGameEngine.LoadMap.failure.return"),
              ("Engine.dll", 0x6c00, "AActor.eventTick"),
              ("Engine.dll", 0xb63eb, "ULevel.Tick.return"),
              ("D3DDrv.dll", 0xef95, "D3D.CreateDevice.call.1"),
              ("D3DDrv.dll", 0xef98, "D3D.CreateDevice.return.1"),
              ("D3DDrv.dll", 0xf0ce, "D3D.CreateDevice.call.2"),
              ("D3DDrv.dll", 0xf0d1, "D3D.CreateDevice.return.2"),
              ("D3DDrv.dll", 0xf17f, "D3D.InitialPresent.call"),
              ("D3DDrv.dll", 0xf182, "D3D.InitialPresent.return"),
              ("Engine.dll", 0x93c1e, "UGameEngine.WorldTick.return"),
              ("Engine.dll", 0x93ca5, "UGameEngine.EntryTick.return"),
              ("D3DDrv.dll", 0xb2d0, "UD3DRenderDevice.Present"),
              ("D3DDrv.dll", 0xb387, "D3D.Present.call.1"),
              ("D3DDrv.dll", 0xb38a, "D3D.Present.return.1"),
              ("D3DDrv.dll", 0xb3c8, "D3D.Present.call.2"),
              ("D3DDrv.dll", 0xb3cb, "D3D.Present.return.2")]
    extra += [("D3DDrv.dll",0xd8a1,"D3D.Direct3DCreate8.call"),
              ("D3DDrv.dll",0xd96b,"D3D.GetAdapterIdentifier.call"),
              ("D3DDrv.dll",0xd96e,"D3D.GetAdapterIdentifier.return"),
              ("D3DDrv.dll",0xdd94,"D3D.CheckDeviceFormat.call.1"),
              ("D3DDrv.dll",0xdd97,"D3D.CheckDeviceFormat.return.1"),
              ("D3DDrv.dll",0xddc0,"D3D.CheckDeviceFormat.call.2"),
              ("D3DDrv.dll",0xddc3,"D3D.CheckDeviceFormat.return.2"),
              ("D3DDrv.dll",0xddec,"D3D.CheckDeviceFormat.call.3"),
              ("D3DDrv.dll",0xddef,"D3D.CheckDeviceFormat.return.3")]
    extra += [("Engine.dll",0x18177f,"DirectMusic.CoInitialize.call"),
              ("Engine.dll",0x181785,"DirectMusic.CoInitialize.return"),
              ("Engine.dll",0x18182c,"DirectMusic.Loader8.call"),
              ("Engine.dll",0x18182e,"DirectMusic.Loader8.return"),
              ("Engine.dll",0x181845,"DirectMusic.Performance8.call"),
              ("Engine.dll",0x181847,"DirectMusic.Performance8.return")]
    if args.stop_after_music_factory and (args.stop_after_present or args.stop_after_floor or args.stop_after_ceil):
        parser.error("stop-after-music-factory cannot combine with other stop options")
    if args.stop_after_floor:
        if not 1 <= args.stop_after_floor <= 1000 or args.stop_after_present:
            parser.error("stop-after-floor must be 1..1000 and cannot combine with stop-after-present")
        extra += [("msvcr70.dll",0x98db,"CRT.floor.entry"),
                  ("msvcr70.dll",0x9919,"CRT.floor.SSE2"),
                  ("msvcr70.dll",0x363b7,"CRT.floor.x87"),
                  ("Core.dll",0x17226,"Core.appRound.floor.return")]
    if args.stop_after_ceil:
        if not 1 <= args.stop_after_ceil <= 1000 or args.stop_after_present or args.stop_after_floor:
            parser.error("stop-after-ceil must be 1..1000 and cannot combine with other stop options")
        extra += [("msvcr70.dll",0x97c0,"CRT.ceil.entry"),
                  ("msvcr70.dll",0x97fe,"CRT.ceil.SSE2"),
                  ("msvcr70.dll",0x362e6,"CRT.ceil.x87"),
                  ("Core.dll",0x17200,"Core.appCeil.return")]
    points.write_text("".join(f"{module} {rva:x} {label}\n" for module, rva, label in L.POINTS + extra))
    exe = root / "System/Unreal2.exe"
    env = R.tracer_env(ident)
    graphics_environment=G.environment(env,out) if args.configuration=='dxvk' else None
    env.update(UCTRACE_TIMEOUT_MS=str(args.timeout_ms), UCTRACE_EVENTS=str(points),
               UCTRACE_STOP_LABEL="Launcher.Error.Serialize")
    if args.stop_after_music_factory:
        env["UCTRACE_STOP_LABEL"] = "DirectMusic.Performance8.return"
    if args.stop_after_floor:
        env.update(UCTRACE_FPU="1", UCTRACE_STOP_LABEL="Core.appRound.floor.return",
                   UCTRACE_STOP_AFTER=str(args.stop_after_floor))
    if args.stop_after_ceil:
        env.update(UCTRACE_FPU="1", UCTRACE_STOP_LABEL="Core.appCeil.return",
                   UCTRACE_STOP_AFTER=str(args.stop_after_ceil))
    if args.stop_after_present:
        if not 1 <= args.stop_after_present <= 100:
            parser.error("stop-after-present must be 1..100")
        env.update(UCTRACE_STOP_LABEL="D3D.Present.return.1", UCTRACE_STOP_AFTER=str(args.stop_after_present))
    if args.music_trace:
        from music_points import POINTS as MUSIC_POINTS
        # Replace duplicate music points so each address has one unambiguous label.
        all_points = [p for p in L.POINTS + extra if not p[2].startswith('DirectMusic.')]
        import pefile
        api_points=[]
        for dll,names in [('ole32',['CoInitialize']),('combase',['CoInitializeEx','CoUninitialize','CoCreateInstance']),
                          ('dsound',['DirectSoundCreate','DirectSoundCreate8'])]:
            image=pefile.PE('C:/Windows/SysWOW64/'+dll+'.dll')
            for e in image.DIRECTORY_ENTRY_EXPORT.symbols:
                if e.name and e.name.decode() in names and not e.forwarder:
                    api_points.append((dll+'.dll',e.address,'DirectMusic.API.'+e.name.decode()+'.entry'))
        points.write_text("".join(f"{m} {r:x} {label}\n" for m,r,label in all_points + MUSIC_POINTS + api_points))
        env['UCTRACE_MUSIC_LOG'] = str(out / 'music.jsonl')
    if args.close_after_present:
        if not args.stop_after_present:parser.error('--close-after-present requires --stop-after-present')
        env['UCTRACE_CLOSE_ON_STOP']='1'
    if args.capture_client:
        if not args.stop_after_present:
            parser.error("capture-client requires a bounded Present stop")
        env["UCTRACE_CAPTURE_CLIENT"] = str(out / "client.bmp")
    game_args = [a for a in L.ARGS if not (args.sound and a == '-nosound')]
    command = [R.TRACER, str(entries), str(out / "trace.json"), str(out / "stdout.bin"), str(exe)] + game_args
    before = {f.relative_to(root).as_posix(): L.sha(f) for f in root.rglob("*") if f.is_file()}
    meta = {"id": ident, "configuration": args.configuration, "sandbox": str(root), "command": command,
            "args": game_args, "git": R.git_identity(), "driver": R.file_identity(str(Path(__file__).resolve())),
            "before": before, "tracer": R.file_identity(R.TRACER), "wrapper": wrapper, "staged_packages": staged,
            "environment": {k: v for k, v in env.items() if k.startswith("UCTRACE_")},
            "graphics_environment": graphics_environment,
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
    if not (out / "trace.json").exists():
        print(out)
        print("incomplete observer run; no world/frame verdict; see host-output.txt")
        return 1
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
