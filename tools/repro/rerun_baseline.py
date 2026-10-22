"""Rebuild and rerun the Phase 0 baseline tests (E5 uvm, E6 lifted routines) with provenance.

Usage: python -I tools/repro/rerun_baseline.py [--skip-linux]

Writes experiments/xrt/results/baseline_rerun.json (commands, tool versions, input
hashes, seeds, exit codes, output hashes, verdicts). Raw stdout/stderr go to
experiments/xrt/results/raw/baseline/ (git-ignored: they can contain engine output).
ARM64 runs use Docker --platform linux/arm64, i.e. QEMU user-mode EMULATION on x86-64.
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(WS, "experiments", "xrt", "results", "raw", "baseline")
VCVARS = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(name, cmd, shell=False, cwd=WS):
    t0 = datetime.datetime.now()
    p = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True)
    dt = (datetime.datetime.now() - t0).total_seconds()
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, name + ".out"), "wb") as f:
        f.write(p.stdout)
    with open(os.path.join(RAW, name + ".err"), "wb") as f:
        f.write(p.stderr)
    text = p.stdout.decode("utf-8", "replace")
    print(f"[{name}] exit={p.returncode} ({dt:.1f}s)")
    return {"name": name, "command": cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd),
            "exit_code": p.returncode, "seconds": round(dt, 2),
            "stdout_sha256": hashlib.sha256(p.stdout).hexdigest(), "stdout_tail": text.strip().splitlines()[-12:]}


def tool_versions():
    v = {"python": sys.version.split()[0]}
    try:
        import capstone
        import pefile
        v["pefile"], v["capstone"] = pefile.__version__, capstone.__version__
    except ImportError:
        pass
    out = subprocess.run(f'call "{VCVARS}" x64 >nul && cl 2>&1', shell=True, capture_output=True).stdout.decode(errors="replace")
    v["msvc_x64"] = out.strip().splitlines()[0] if out.strip() else "?"
    out = subprocess.run(f'call "{VCVARS}" x86 >nul && cl 2>&1', shell=True, capture_output=True).stdout.decode(errors="replace")
    v["msvc_x86"] = out.strip().splitlines()[0] if out.strip() else "?"
    v["docker"] = subprocess.run(["docker", "--version"], capture_output=True).stdout.decode().strip()
    for img in ("gcc:13", "alpine:3.20"):
        r = subprocess.run(["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", img], capture_output=True)
        v["image " + img] = r.stdout.decode().strip()
    return v


def main():
    skip_linux = "--skip-linux" in sys.argv
    sysdir = os.path.join(WS, "sandbox", "System")
    inputs = {}
    for rel in ["sandbox/System/Core.dll", "sandbox/System/Core.u", "sandbox/System/VMProbe.u", "sandbox/System/UCC.exe",
                "experiments/vmprobe/VMProbe.reference.txt", "experiments/vmprobe/Core.HelloWorldCommandlet.reference.txt",
                "experiments/vmprobe/Core.SimpleCommandlet.reference.txt", "experiments/vmprobe/Core.ArrayTest.reference.txt",
                "experiments/lift/lifted_core.c", "experiments/lift/harness_lifted.c", "experiments/lift/harness_original.c",
                "experiments/lift/testvec.h", "experiments/lift/x86rt.h", "tools/lift/lift_x86.py"]:
        p = os.path.join(WS, rel)
        inputs[rel] = sha(p) if os.path.exists(p) else "MISSING"
    for f in sorted(os.listdir(os.path.join(WS, "experiments", "uvm", "src"))):
        inputs["experiments/uvm/src/" + f] = sha(os.path.join(WS, "experiments", "uvm", "src", f))
    results = []
    # E5: uvm on Windows x64 (native)
    results.append(run("uvm_build_msvc_x64", r"experiments\uvm\build_msvc.cmd x64", shell=True))
    uvm = os.path.join(WS, "experiments", "uvm", "build", "x64", "uvm.exe")
    ref = os.path.join(WS, "experiments", "vmprobe")
    for c in ("HelloWorldCommandlet", "SimpleCommandlet", "ArrayTest"):
        results.append(run(f"uvm_x64_Core.{c}", [uvm, sysdir, f"Core.{c}", "--parms", "a b c", "--quiet", "--compare",
                                                 os.path.join(ref, f"Core.{c}.reference.txt")]))
    results.append(run("uvm_x64_VMProbe", [uvm, sysdir, "VMProbe.VMProbe", "--quiet", "--compare",
                                           os.path.join(ref, "VMProbe.reference.txt")]))
    # E6: original Core.dll (x86, native) vs lifted C (x64, native)
    results.append(run("lift_build_and_test_win", r"experiments\lift\build_and_test.cmd", shell=True))
    lift_dir = os.path.join(WS, "experiments", "lift", "build")
    for f in ("original_x86.txt", "lifted_x64.txt"):
        p = os.path.join(lift_dir, f)
        if os.path.exists(p):
            inputs["generated:" + f] = sha(p)
    if not skip_linux:
        vol = f"{WS}:/work".replace("\\", "/")
        results.append(run("uvm_linux_x64_gcc13", ["docker", "run", "--rm", "-v", vol, "gcc:13", "sh",
                                                   "/work/experiments/uvm/run_linux_tests.sh", "linux-x64"]))
        results.append(run("uvm_linux_arm64_QEMU", ["docker", "run", "--rm", "--platform", "linux/arm64", "-v", vol, "alpine:3.20", "sh", "-c",
                                                    "apk add --no-cache g++ >/dev/null && sh /work/experiments/uvm/run_linux_tests.sh linux-arm64"]))
        results.append(run("lift_linux_x64_gcc13", ["docker", "run", "--rm", "-v", vol, "gcc:13", "sh",
                                                    "/work/experiments/lift/run_linux_lift.sh", "linux-x64"]))
        results.append(run("lift_linux_arm64_QEMU", ["docker", "run", "--rm", "--platform", "linux/arm64", "-v", vol, "alpine:3.20", "sh", "-c",
                                                     "apk add --no-cache gcc musl-dev >/dev/null && sh /work/experiments/lift/run_linux_lift.sh linux-arm64"]))
    record = {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "host": "Windows 11 x64 (i7-14700K); ARM64 rows run under QEMU user-mode emulation via Docker",
        "seeds": {"lift testvec.h xorshift32 g_rng": "0x12345678", "N_CASES": 20000, "appSRandInit seed": 12345},
        "tools": tool_versions(), "inputs_sha256": inputs, "runs": results,
    }
    out = os.path.join(WS, "experiments", "xrt", "results", "baseline_rerun.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1)
    print("wrote", out)
    sys.exit(1 if any(r["exit_code"] for r in results) else 0)


if __name__ == "__main__":
    main()
