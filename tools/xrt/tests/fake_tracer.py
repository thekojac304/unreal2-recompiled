"""Runner self-test helper: a stand-in for uctrace.exe (run_xrt.TRACER = python, ENTRIES = this file).

Called as: python fake_tracer.py <trace.json> <stdout file> <exe> [args...] with UCTRACE_RUN_ID set.
FAKE_TRACER_MODE selects the behaviour; every mode except tool failures really runs the original <exe> so the
reference artifacts (stdout, UCC.log) exist:
  ok              faithful trace JSON (no function hits), exit 0
  guest_exit5     faithful, but report the guest exit code as 5 (a guest result, not a tool failure)
  tool_exit4      write a faithful JSON but exit 4 (tool failure)
  stale           JSON with another run id
  incomplete      JSON with complete=false
  no_json         exit 0 without writing JSON
  garbage         write invalid JSON
"""
import json
import os
import subprocess
import sys


def main():
    mode = os.environ.get("FAKE_TRACER_MODE", "ok")
    out_json, out_stdout, exe, args = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    with open(out_stdout, "wb") as f:
        p = subprocess.run([exe] + args, cwd=os.path.dirname(exe), stdout=f, stderr=subprocess.STDOUT)
    trace = {"run_id": os.environ.get("UCTRACE_RUN_ID", ""), "complete": True, "debuggee_terminated": True,
             "command": subprocess.list2cmdline([exe] + args), "exit_code": p.returncode, "threads": 2, "modules": [],
             "imports": [], "exceptions": [], "events": []}
    if mode == "guest_exit5":
        trace["exit_code"] = 5
    elif mode == "stale":
        trace["run_id"] = "0" * 32
    elif mode == "incomplete":
        trace["complete"] = False
    if mode == "no_json":
        return 0
    with open(out_json, "w", encoding="utf-8") as f:
        f.write("{ not json" if mode == "garbage" else json.dumps(trace))
    return 4 if mode == "tool_exit4" else 0


if __name__ == "__main__":
    sys.exit(main())
