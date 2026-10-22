"""Run the ORIGINAL UCC.exe for each X1 test case in a fresh sandbox copy, optionally under uctrace.

Usage: python -I tools/xrt/trace_original.py [--trace] [--case NAME ...]

For each case: fresh copy of singleplayer/System -> sandbox_ref/<case>/System, run, capture
stdout (UCC's console output), UCC.log and exit code into experiments/xrt/references/<case>.*
(UCC.log contains machine-specific lines and is kept git-ignored under results/raw).
With --trace the run goes through experiments/xrt/build/tracer/uctrace.exe and the dependency
trace is written to experiments/xrt/traces/<case>.json.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CASES = {
    "hello": ["HelloWorld", "a", "b", "c"],
    "hellofull": ["Core.HelloWorldCommandlet", "a", "b", "c"],
    "simple": ["Core.SimpleCommandlet"],
    "arraytest": ["Core.ArrayTest"],
    "vmprobe": ["VMProbe.VMProbe"],
    "vmprobe_ini": ["VMProbe.VMProbe", "-ini=VMProbe.ini"],
    # error path: unknown commandlet class -> LOAD_NoFail -> appErrorf -> C++ throw -> UCC's catch
    "badclass": ["NoSuchCommandletXYZ"],
}


def main():
    trace = "--trace" in sys.argv
    sel = [a for a in sys.argv[1:] if not a.startswith("--")] or list(CASES)
    refdir = os.path.join(WS, "experiments", "xrt", "references")
    rawdir = os.path.join(WS, "experiments", "xrt", "results", "raw", "original")
    os.makedirs(refdir, exist_ok=True)
    os.makedirs(rawdir, exist_ok=True)
    summary = {}
    for case in sel:
        args = CASES[case]
        sb = os.path.join(WS, "sandbox_ref", case)
        subprocess.run([sys.executable, "-I", os.path.join(WS, "tools", "xrt", "make_sandbox.py"), sb, "--probe"],
                       check=True, capture_output=True)
        exe = os.path.join(sb, "System", "UCC.exe")
        stdout_file = os.path.join(refdir, f"{case}.stdout")
        if trace:
            tr = os.path.join(WS, "experiments", "xrt", "build", "tracer", "uctrace.exe")
            out_json = os.path.join(WS, "experiments", "xrt", "traces", f"{case}.json")
            p = subprocess.run([tr, os.path.join(WS, "experiments", "xrt", "traces", "entries"), out_json, stdout_file, exe] + args,
                               capture_output=True, text=True)
            code = json.load(open(out_json))["exit_code"]
            print(f"[{case}] {p.stdout.strip()}")
        else:
            with open(stdout_file, "wb") as f:
                p = subprocess.run([exe] + args, cwd=os.path.dirname(exe), stdout=f, stderr=subprocess.STDOUT)
            code = p.returncode
            print(f"[{case}] exit={code}")
        log = os.path.join(sb, "System", "UCC.log")
        if os.path.exists(log):
            shutil.copy2(log, os.path.join(rawdir, f"{case}{'.traced' if trace else ''}.UCC.log"))
        with open(stdout_file, "rb") as f:
            data = f.read()
        summary[case] = {"args": args, "exit_code": code, "stdout_sha256": hashlib.sha256(data).hexdigest(),
                         "stdout_lines": data.decode("latin-1").count("\n")}
    with open(os.path.join(refdir, "summary.json" if not trace else "summary.traced.json"), "w") as f:
        json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
