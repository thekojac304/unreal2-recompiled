"""Validate reused checkpoint objects/headers, and bind a client build to its actual source and lift inputs."""
import argparse
import json
import re
from pathlib import Path
import sys
import pefile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_xrt as R
from fresh_checkpoint import hashes

WS = Path(R.WS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()
    base, out = a.base.resolve(), a.out.resolve()
    base.relative_to(WS / "experiments/xrt/build")
    out.relative_to(WS / "experiments/xrt/build")
    checkpoint = json.loads((base / "identity.json").read_text())
    if checkpoint.get("result") != "PASS":
        raise RuntimeError("base is not a successful full checkpoint")
    for path, digest in checkpoint["generated_after"].items():
        if R.sha256_file(WS / "experiments/xrt/gen" / path) != digest:
            raise RuntimeError(f"baseline generated input changed: {path}")
    if R.sha256_file(WS / "experiments/xrt/runtime/xrt.h") != checkpoint["sources"]["experiments/xrt/runtime"]["xrt.h"]:
        raise RuntimeError("generated-code runtime header changed: a full rebuild is required")
    for path, digest in checkpoint["build_outputs"].items():
        if path.startswith("gen/") and R.sha256_file(base / "obj" / path) != digest:
            raise RuntimeError(f"baseline generated object changed: {path}")
    expected_objects = {p[4:]:h for p,h in checkpoint["build_outputs"].items() if p.startswith("gen/")}
    if hashes(base / "obj/gen") != expected_objects:
        raise RuntimeError("unexpected/missing baseline objects; wildcard linking refused")
    lifts = []
    ranges = []
    for stem, name, expected_base in [("unreal2", "Unreal2.exe", "0x10900000"),
                                      ("windrv", "WinDrv.dll", "0x11100000"),
                                      ("d3ddrv", "D3DDrv.dll", "0x6960000"),
                                      ("particlesystems", "ParticleSystems.dll", "0x0fe00000"),
                                      ("legend", "Legend.dll", "0x0ff40000"),
                                      ("ui", "UI.dll", "0x19120000"),
                                      ("u2", "U2.dll", "0x10060000"),
                                      ("u2dialog", "U2Dialog.dll", "0x19630000"),
                                      ("u2ai", "U2AI.dll", "0x1c6d0000")]:
        meta = json.loads((WS / "experiments/xrt/gen" / stem / (name.split('.')[0] + "_meta.json")).read_text())
        if int(meta["base"],16) != int(expected_base,16) or meta["sha256"] != R.sha256_file(WS / "sandbox_cmp/level/System" / name):
            raise RuntimeError(f"client lift/input/base mismatch: {name}")
        expected = set(meta["files"]) | {name.split('.')[0] + "_meta.json"}
        if set(hashes(WS / "experiments/xrt/gen" / stem)) != expected:
            raise RuntimeError(f"unexpected/missing generated client files: {name}")
        image = pefile.PE(str(WS / "sandbox_cmp/level/System" / name), fast_load=True)
        lo = int(meta["base"], 16)
        hi = lo + image.OPTIONAL_HEADER.SizeOfImage
        image.close()
        for other_lo, other_hi, other_name in ranges:
            if lo < other_hi and other_lo < hi:
                raise RuntimeError(f"overlapping client lift ranges: {name} and {other_name}")
        ranges.append((lo, hi, name))
        lifts.append(meta)
    observed_engine = [p for p in sorted((WS / 'experiments/xrt/gen/engine').glob('*.c'))
                       if p.name != 'Engine_table.c' and re.search(r'f_103(?:06630|066a0|06600|8f460|938f0|b5be0)\b',p.read_text())]
    observed_objects = {p.stem + '.obj' for p in observed_engine}
    client_sources = [p for stem in ["unreal2","windrv","d3ddrv","particlesystems","legend","ui","u2","u2dialog","u2ai"]
                      for p in (WS / 'experiments/xrt/gen' / stem).glob('*.c')]
    identity = {"git": R.git_identity(), "world_observer_units": [p.name for p in observed_engine], "base_identity": R.file_identity(str(base / "identity.json")),
                "baseline_binary": checkpoint["binary_sha256"], "runtime": R.tree_digest(str(WS / "experiments/xrt/runtime")),
                "generated": R.tree_digest(str(WS / "experiments/xrt/gen")), "lifter": R.file_identity(str(WS / "tools/xrt/xlift.py")),
                "client_lifts": lifts, "build_script": R.file_identity(str(WS / "experiments/xrt/build_client.cmd")),
                "identity_driver": R.file_identity(str(Path(__file__).resolve()))}
    out.mkdir(parents=True, exist_ok=True)
    # Recompile the exact unchanged Engine lift with read-only direct-call observers.
    # Other baseline generated objects remain hash-verified and are linked verbatim.
    (out / 'base-objects.rsp').write_text('\n'.join('"' + str(base / 'obj' / p) + '"'
        for p in checkpoint['build_outputs'] if p.startswith('gen/') and Path(p).name not in observed_objects))
    (out / 'engine-sources.rsp').write_text('\n'.join('"' + str(p) + '"'
        for p in observed_engine))
    (out / 'client-sources.rsp').write_text('\n'.join('"' + str(p) + '"'
        for p in client_sources if p.name != 'ParticleSystems_001.c'))
    if a.record:
        plan = json.loads((out / "client-plan.json").read_text())
        if any(plan[k] != identity[k] for k in ["runtime", "generated", "lifter", "base_identity", "build_script", "identity_driver"]):
            raise RuntimeError("source/lifts/base changed during client build")
        runtime_sources = list((WS / "experiments/xrt/runtime").glob("*.c"))
        for folder, sources in [("client",client_sources),("rt",runtime_sources),
                                ("engine",observed_engine)]:
            if {p.name for p in (out / "obj" / folder).glob("*.obj")} != {p.stem+".obj" for p in sources}:
                raise RuntimeError(f"unexpected/missing {folder} objects; wildcard linking refused")
        identity["binary"] = R.file_identity(str(out / "xrt_ucc.exe"))
        identity["objects"] = hashes(out / "obj")
        dest = out / "client-identity.json"
    else:
        dest = out / "client-plan.json"
    dest.write_text(json.dumps(identity, indent=2))
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
