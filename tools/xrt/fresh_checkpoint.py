"""Reproduce the declared lifts, then compile ALL TUs in an exclusively new build directory.

Uses an existing isolated System copy; never copies game assets. A scratch lift is compared byte for byte
including metadata, one module at a time. A mismatch is preserved and stops before compilation; no generated
input is overwritten. Logs, exact commands, source/input/output hashes and build identity stay local.
Usage: python -I tools/xrt/fresh_checkpoint.py --system sandbox/System
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone

WS = Path(__file__).resolve().parents[2]
GEN = WS / "experiments/xrt/gen"
MODULES = [("ucc", "UCC.exe", None), ("core", "Core.dll", None),
           ("engine", "Engine.dll", None), ("glmlib", "GlmLib.dll", "0x02f40000"),
           ("editor", "Editor.dll", "0x02de0000"), ("window", "Window.dll", None),
           ("unrimp", "plugins/UnrImp.gpi", "0x036d0000"), ("fire", "Fire.dll", "0x03710000")]


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system", type=Path, required=True)
    a = ap.parse_args()
    system = a.system.resolve()
    rel = system.relative_to(WS)
    if not rel.parts[0].startswith("sandbox"):
        ap.error("input must be an existing workspace sandbox")
    ident = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    root = WS / "experiments/xrt/build" / ("fresh-" + ident)
    root.mkdir(parents=True, exist_ok=False)
    record = {"id": ident, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WS, text=True).strip(),
              "source_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=WS, text=True),
              "sources": {p: hashes(WS / p) for p in ("tools/xrt", "experiments/xrt/runtime")},
              "build_script_sha256": hashlib.sha256((WS / "experiments/xrt/build_xrt.cmd").read_bytes()).hexdigest(),
              "generated_before": hashes(GEN), "commands": [], "verified": []}
    def save():
        (root / "identity.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    def run(cmd, name, env=None):
        record["commands"].append(cmd)
        save()
        with (root / (name + ".log")).open("wb") as f:
            rc = subprocess.call(cmd, cwd=WS, stdout=f, stderr=subprocess.STDOUT, env=env)
        if rc:
            raise RuntimeError(f"{name} failed ({rc}); see {root}")
    try:
        for stem, module, base in MODULES:
            scratch = root / "verify" / stem
            cmd = [sys.executable, "-I", "tools/xrt/xlift.py", str(system / module), "--out", str(scratch)]
            if base:
                cmd += ["--base", base]
            run(cmd, "lift-" + stem)
            before, after = hashes(GEN / stem), hashes(scratch)
            diffs = [p for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
            if diffs:
                record["discrepancy"] = {"module": module, "files": diffs, "existing": before, "regenerated": after}
                raise RuntimeError(f"generated discrepancy {module}: {diffs}; both versions preserved")
            record["verified"].append({"module": module, "base": base, "files": after})
            scratch.resolve().relative_to(root.resolve())
            shutil.rmtree(scratch)  # checked workspace path; exact equality established; keep only the hashes
            save()
            print(f"verified {module}", flush=True)
        scratch = root / "verify" / "pow_sse2.c"
        run([sys.executable, "-I", "tools/xrt/lift_sse2.py", str(system / "msvcr70.dll"), "0x7c00ae08",
             "xrt_msvcr70_pow_sse2", "--error-handler", "0x7c036052", "--out", str(scratch)], "lift-pow")
        # Its sole input-path comment is intentionally provenance-sensitive; compare with that line canonicalized.
        def pow_body(p):
            return "\n".join(line for line in p.read_text().splitlines() if not line.startswith(" * source:"))
        if pow_body(scratch) != pow_body(GEN / "msvcr70/pow_sse2.c"):
            raise RuntimeError("pow_sse2.c differs beyond its input-path comment; both versions preserved")
        record["pow_verified"] = True
        scratch.unlink()
        record["generated_after"] = hashes(GEN)
        if record["generated_after"] != record["generated_before"]:
            raise RuntimeError("shared generated code changed during verification")
        env = dict(os.environ, XRT_BUILD_DIR=str(root))
        run(["cmd.exe", "/d", "/c", "experiments\\xrt\\build_xrt.cmd"], "build-all", env)
        record["build_outputs"] = hashes(root / "obj")
        record["binary_sha256"] = hashlib.sha256((root / "xrt_ucc.exe").read_bytes()).hexdigest()
        record["result"] = "PASS"
        print(f"PASS {root}", flush=True)
    except Exception as exc:
        record["result"] = "FAIL"
        record["error"] = str(exc)
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
