"""Run the C++ exception probe natively (x86, the game's msvcr70.dll) and translated (x64 runtime), and compare.

Usage: python -I run_probe.py   (after build_and_run.cmd built experiments/xrt/build/ehprobe/)
Positive probes: the event logs (constructors, destructors, catches, continuations, exception-object destruction, in
order) must be identical, and the translated run must have exercised the dispatcher paths each probe is meant to
cover (unwind actions, rethrow out of a catch block, resumption inside a catch block, object destruction).
Negative probes: unsupported exception behaviour must stop the translated run with an explicit diagnostic (exit 76);
the native outcome is recorded. Writes experiments/xrt/build/ehprobe/results.json; exit status 0 when all hold.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
# EHPROBE_OUT: another build directory (build_and_run_dev.cmd: the developer runtime and option set, round 4)
OUT = os.environ.get("EHPROBE_OUT") or os.path.join(WS, "experiments", "xrt", "build", "ehprobe")
SB = os.path.join(WS, "sandbox_cmp", "ehprobe")
POSITIVE = ["probe_cleanup", "probe_rethrow", "probe_nested", "probe_enclosing", "probe_loop", "probe_rethrow_callee",
            "probe_deep", "probe_caller_state", "probe_guard_calls"]
NEGATIVE = {"probe_neg_unhandled": "is not caught by any handler",
            "probe_neg_catch_by_value": "needs its copy constructor"}


def run(cmd, timeout):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "timeout", "", ""


def logs(text):
    out = {}
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 4 and f[1] == "returned" and f[3] == "log":
            out[f[0]] = {"returned": int(f[2]), "log": [int(x) for x in f[4:]]}
    return out


def main():
    p = subprocess.run([sys.executable, "-I", os.path.join(WS, "tools", "xrt", "make_sandbox.py"), SB],
                       capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"make_sandbox failed: {p.stderr}")
    sysdir = os.path.join(SB, "System")
    dll = os.path.join(OUT, "ehprobe.dll")
    native, xrt = os.path.join(OUT, "native_host.exe"), os.path.join(OUT, "xrt_probe_host.exe")
    res = {"positive": {}, "negative": {}, "dispatcher_paths": {}}
    ok = True
    nrc, nout, nerr = run([native, sysdir, dll] + POSITIVE, 120)
    report = os.path.join(OUT, "report.json")
    if os.path.exists(report):
        os.remove(report)
    xrc, xout, xerr = run([xrt, dll, report] + POSITIVE, 300)
    nl, xl = logs(nout), logs(xout)
    res["native_exit"], res["translated_exit"] = nrc, xrc
    if xrc != 0:
        res["translated_stderr"] = xerr[-3000:]
        ok = False
    for name in POSITIVE:
        a, b = nl.get(name), xl.get(name)
        same = a is not None and a == b
        res["positive"][name] = {"native": a, "translated": b, "identical": same}
        ok &= same
        print(f"{name:22} {'identical' if same else 'DIFFERENT'}  native {a and a['log']}" + ("" if same else f"  translated {b and b['log']}"))
    try:
        rep = json.load(open(report))
        ev = [e for e in rep.get("events", []) if e.get("kind", "").startswith("cxx_")]
    except (OSError, ValueError):
        rep, ev = {}, []
    paths = {
        "unwind actions (destructors through unwind funclets)": sum(1 for e in ev if e["kind"] == "cxx_unwind"),
        "rethrows leaving a catch block": sum(1 for e in ev if e["kind"] == "cxx_rethrow_leaves_catch"),
        "resumptions inside an active catch block": sum(1 for e in ev if e["kind"] == "cxx_resume" and e.get("in") == "catch block"),
        "resumptions in the owning function": sum(1 for e in ev if e["kind"] == "cxx_resume" and e.get("in") == "function"),
        "abandoned catch blocks": sum(1 for e in ev if e["kind"] == "cxx_catch_end" and e.get("how") == "abandoned"),
        "exception objects destroyed": sum(1 for e in ev if e["kind"] == "cxx_destroy"),
        "catches at catch depth > 0": sum(1 for e in ev if e["kind"] == "cxx_catch" and e.get("depth", 0) > 0),
    }
    res["dispatcher_paths"] = paths
    for k, v in paths.items():
        print(f"  translated dispatcher: {k}: {v}")
        ok &= v > 0
    for name, expect in NEGATIVE.items():
        nrc2, nout2, nerr2 = run([native, sysdir, dll, name], 60)
        xrc2, xout2, xerr2 = run([xrt, dll, os.path.join(OUT, f"report_{name}.json"), name], 120)
        explicit = xrc2 == 76 and expect in xerr2 and "XRT FATAL" in xerr2
        res["negative"][name] = {"native_exit": nrc2 if isinstance(nrc2, str) else f"{nrc2 & 0xFFFFFFFF:#x}",
                                 "native_output": nout2.strip()[-300:], "translated_exit": xrc2,
                                 "translated_diagnostic": next((ln for ln in xerr2.splitlines() if "XRT FATAL" in ln), ""),
                                 "fails_explicitly": explicit}
        ok &= explicit
        print(f"{name:26} native exit {res['negative'][name]['native_exit']}; translated exit {xrc2}: "
              f"{res['negative'][name]['translated_diagnostic'][:140]}")
    res["ok"] = ok
    with open(os.path.join(OUT, "results.json"), "w", newline="\n") as f:
        json.dump(res, f, indent=1)
    print("PROBE", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
