"""Run the translated UCC (xrt_ucc.exe) and the ORIGINAL UCC.exe on the same commandlet and compare.

Both run in the same sandbox path, sandbox_cmp/<case>/System, recreated from the read-only install before
every single run (the engine hashes paths into its config maps, so equal paths are needed for comparable
internal behaviour, and every run must start from pristine files).

Usage:
  python -I tools/xrt/run_xrt.py <case> [--repeat N] [--trace] [--no-original] [--timeout S] -- <commandlet args>

Writes raw outputs (git-ignored) to experiments/xrt/results/raw/{original,xrt}/<case>[.<k>].*, and a summary to
experiments/xrt/results/compare/<case>.json. Exit status 0 only if every translated run matches its reference.

Comparison rules (documented presentation/measurement differences; everything else must be byte-identical):
  stdout       identical after normalising only the elapsed-seconds field the VM prints in script warnings
               ("...:000F) 0.666 Attempt to assign variable through None": wall-clock seconds since start, it
               varies between runs of the original too); the raw byte comparison is reported as well
  exit code    identical
  UCC.log      identical after normalising: the two timestamp lines, "CPU Speed=" (measured), the elapsed
               "<n>ms Purging garbage", the same script-warning seconds, and "CPU Features:" only when the
               arguments do not contain -NOMMX -NOSSE (the translated runtime's CPU policy hides MMX/SSE; with
               those switches the original takes the same scalar paths and the line must match exactly)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PY = sys.executable
XRT = os.path.join(WS, "experiments", "xrt", "build", "xrt_ucc.exe")
TRACER = os.path.join(WS, "experiments", "xrt", "build", "tracer", "uctrace.exe")
FSTREAM_DESTROYED = "101edbe0"   # FFileStream::Destroyed (Core.dll export ?Destroyed@FFileStream@@2HA)


def fresh_sandbox(case):
    sb = os.path.join(WS, "sandbox_cmp", case)
    subprocess.run([PY, "-I", os.path.join(WS, "tools", "xrt", "make_sandbox.py"), sb, "--probe"], check=True,
                   capture_output=True)
    return os.path.join(sb, "System")


ELAPSED_IN_WARNING = re.compile(r"(\(Function [^)]*\)) [0-9]+\.[0-9]{3} (Attempt to assign variable through None)")


def normalise_stdout(data):
    return ELAPSED_IN_WARNING.sub(r"\1 <elapsed> \2", data.decode("latin-1"))


def normalise_log(text, policy_line_differs):
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = ELAPSED_IN_WARNING.sub(r"\1 <elapsed> \2", line)
        line = re.sub(r"^(Log: Log file open, |Uninitialized: Log file closed, ).*$", r"\1<timestamp>", line)
        line = re.sub(r"^Init: CPU Speed=.*$", "Init: CPU Speed=<measured>", line)
        line = re.sub(r"^Log: [0-9.]+ms Purging garbage$", "Log: <elapsed>ms Purging garbage", line)
        if policy_line_differs:
            line = re.sub(r"^Init: CPU Features:.*$", "Init: CPU Features: <policy>", line)
        out.append(line)
    return "\n".join(out)


def run_original(case, args, tag, trace, timeout):
    sysdir = fresh_sandbox(case)
    raw = os.path.join(WS, "experiments", "xrt", "results", "raw", "original")
    os.makedirs(raw, exist_ok=True)
    exe = os.path.join(sysdir, "UCC.exe")
    out = os.path.join(raw, f"{tag}.stdout")
    t0 = time.time()
    if trace:
        tj = os.path.join(raw, f"{tag}.trace.json")
        subprocess.run([TRACER, os.path.join(WS, "experiments", "xrt", "traces", "entries"), tj, out, exe] + args,
                       cwd=sysdir, capture_output=True, timeout=timeout)
        code = json.load(open(tj))["exit_code"]
    else:
        with open(out, "wb") as f:
            p = subprocess.run([exe] + args, cwd=sysdir, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        code = p.returncode
    secs = time.time() - t0
    shutil.copy2(os.path.join(sysdir, "UCC.log"), os.path.join(raw, f"{tag}.UCC.log"))
    return {"exit_code": code, "seconds": round(secs, 3), "stdout": out, "log": os.path.join(raw, f"{tag}.UCC.log")}


def run_xrt(case, args, tag, timeout):
    sysdir = fresh_sandbox(case)
    raw = os.path.join(WS, "experiments", "xrt", "results", "raw", "xrt")
    os.makedirs(raw, exist_ok=True)
    out, err = os.path.join(raw, f"{tag}.stdout"), os.path.join(raw, f"{tag}.stderr")
    rep, log = os.path.join(raw, f"{tag}.report.json"), os.path.join(raw, f"{tag}.xrt.log")
    cmd = [XRT, "--guest", os.path.join(sysdir, "UCC.exe"), "--log", log, "--report", rep, "--watch", FSTREAM_DESTROYED,
           "--timeout-ms", str(int(timeout * 1000)), "--"] + args
    t0 = time.time()
    with open(out, "wb") as fo, open(err, "wb") as fe:
        p = subprocess.run(cmd, cwd=sysdir, stdout=fo, stderr=fe, timeout=timeout + 30)
    secs = time.time() - t0
    shutil.copy2(os.path.join(sysdir, "UCC.log"), os.path.join(raw, f"{tag}.UCC.log")) \
        if os.path.exists(os.path.join(sysdir, "UCC.log")) else None
    return {"exit_code": p.returncode, "seconds": round(secs, 3), "stdout": out, "stderr": err, "report": rep,
            "xrt_log": log, "log": os.path.join(raw, f"{tag}.UCC.log")}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def worker_evidence(r):
    """Facts about the file-streaming worker from the translated run's report and runtime log."""
    ev = {}
    try:
        rep = json.load(open(r["report"]))
    except (OSError, ValueError):
        return {"error": "no report"}
    for t in rep["threads"]:
        if t["index"] == 1:
            ev["worker"] = {k: t[k] for k in ("entry", "state", "exit_via", "exit_code", "sleeps", "contended_cs",
                                               "preemptions")}
        if t["index"] == 0:
            ev["main"] = {k: t[k] for k in ("sleeps", "contended_cs", "preemptions")}
    ev["destroyed_flag_timeline"] = [ln.split("] ", 1)[1].strip() for ln in open(r["xrt_log"], encoding="utf-8", errors="replace")
                                     if f"watch {FSTREAM_DESTROYED}" in ln]
    ev["thread_events"] = [ln.split("] ", 1)[1].strip() for ln in open(r["xrt_log"], encoding="utf-8", errors="replace")
                           if re.search(r"thread \d+ (created|running|exited)|ExitThread|at process exit", ln)]
    return ev


def main():
    argv = sys.argv[1:]
    if "--" not in argv:
        sys.exit(__doc__)
    k = argv.index("--")
    opts, args = argv[:k], argv[k + 1:]
    case = opts[0]
    repeat = int(opts[opts.index("--repeat") + 1]) if "--repeat" in opts else 1
    timeout = float(opts[opts.index("--timeout") + 1]) if "--timeout" in opts else 120.0
    trace = "--trace" in opts
    policy_differs = not ({"-NOMMX", "-NOSSE"} <= {a.upper() for a in args})
    summary = {"case": case, "args": args, "repeat": repeat, "runs": [], "all_match": True}
    for i in range(repeat):
        tag = case if repeat == 1 else f"{case}.{i}"
        ref = None if "--no-original" in opts else run_original(case, args, tag, trace, timeout)
        xr = run_xrt(case, args, tag, timeout)
        entry = {"run": i, "xrt": {"exit_code": xr["exit_code"], "seconds": xr["seconds"], "stdout_sha256": sha(xr["stdout"])}}
        try:
            entry["xrt"]["stderr"] = open(xr["stderr"], encoding="utf-8", errors="replace").read()[:2000]
        except OSError:
            pass
        entry["worker"] = worker_evidence(xr)
        if ref:
            entry["original"] = {"exit_code": ref["exit_code"], "seconds": ref["seconds"], "stdout_sha256": sha(ref["stdout"])}
            a, b = open(ref["stdout"], "rb").read(), open(xr["stdout"], "rb").read()
            entry["stdout_byte_identical"] = a == b
            same_out = normalise_stdout(a) == normalise_stdout(b)
            la = normalise_log(open(ref["log"], encoding="latin-1").read(), policy_differs)
            lb = normalise_log(open(xr["log"], encoding="latin-1").read(), policy_differs) if os.path.exists(xr["log"]) else ""
            diff = [f"- {a}\n+ {b}" for a, b in zip(la.split("\n"), lb.split("\n")) if a != b]
            if len(la.split("\n")) != len(lb.split("\n")):
                diff.append(f"line count {len(la.split(chr(10)))} vs {len(lb.split(chr(10)))}")
            entry["stdout_identical_after_normalisation"] = same_out
            entry["exit_code_identical"] = ref["exit_code"] == xr["exit_code"]
            entry["ucc_log_identical_after_normalisation"] = not diff
            entry["ucc_log_diff"] = diff[:20]
            ok = same_out and entry["exit_code_identical"] and not diff
        else:
            ok = xr["exit_code"] == 0
        entry["match"] = ok
        summary["all_match"] &= ok
        summary["runs"].append(entry)
        print(f"[{case} run {i}] xrt exit={xr['exit_code']} ({xr['seconds']}s)"
              + (f" original exit={ref['exit_code']} ({ref['seconds']}s) stdout_identical={entry['stdout_identical_after_normalisation']} (raw bytes {entry['stdout_byte_identical']})"
                 f" log_identical={entry['ucc_log_identical_after_normalisation']}" if ref else "")
              + f" worker sleeps={entry['worker'].get('worker', {}).get('sleeps')} -> {'MATCH' if ok else 'MISMATCH'}")
    outdir = os.path.join(WS, "experiments", "xrt", "results", "compare")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{case}.json"), "w", newline="\n") as f:
        json.dump(summary, f, indent=1)
    sys.exit(0 if summary["all_match"] else 1)


if __name__ == "__main__":
    main()
