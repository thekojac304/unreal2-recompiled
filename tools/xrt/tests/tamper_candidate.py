"""Runner self-test helper: a deliberately broken "candidate" for tools/xrt/run_xrt.py regression tests.

Usage (as the candidate command prefix): python -I tamper_candidate.py <mode> <xrt_ucc.exe arguments...>
Runs the real experiments/xrt/build/xrt_ucc.exe with the given arguments in the current directory (the run's fresh
sandbox), then sabotages the result according to <mode>. The runner must notice every sabotage except the
documented, normalised timing differences ("ok:*" modes).

  none                         pass everything through unchanged
  drop_report                  delete the runtime report
  stale_report                 rewrite the report's run id (a report from another run)
  drop_worker                  remove the worker thread and every worker event from the report
  worker_incomplete            the worker never ends: drop its ExitThread/end events, state 'running'
  flag_skips_ack               drop the worker's 1->2 store of FFileStream::Destroyed from the timeline
  drop_ucclog                  delete the UCC.log the run wrote in the sandbox
  drop_xrtlog                  delete the runtime log
  stdout:<old>=><new>          replace text in the candidate's stdout
  ucclog:<regex>=><new>        regex-replace lines in the sandbox UCC.log
"""
import json
import os
import re
import subprocess
import sys

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
XRT = os.path.join(WS, "experiments", "xrt", "build", "xrt_ucc.exe")


def arg(args, name):
    return args[args.index(name) + 1] if name in args else None


def edit_report(path, fn):
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    fn(rep)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, indent=1)


def drop_worker(rep):
    rep["threads"] = [t for t in rep["threads"] if t.get("index") != 1]
    rep["events"] = [e for e in rep["events"] if e.get("thread") != 1 and e.get("index") != 1]


def worker_incomplete(rep):
    for t in rep["threads"]:
        if t.get("index") == 1:
            t.update(state="running", exit_via="", exit_code=0)
    rep["events"] = [e for e in rep["events"] if not (e.get("kind") in ("exit_thread", "thread_end") and e.get("thread") == 1)]
    for e in rep["events"]:
        if e.get("kind") == "thread_at_exit" and e.get("index") == 1:
            e["state"] = "alive"


def flag_skips_ack(rep):
    rep["events"] = [e for e in rep["events"] if not (e.get("kind") == "watch_store" and e.get("new") == 2)]


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    p = subprocess.run([XRT] + args, stdout=subprocess.PIPE)
    out = p.stdout
    if mode.startswith("stdout:"):
        old, new = mode[len("stdout:"):].split("=>", 1)
        if old.encode("latin-1") not in out:
            sys.stderr.write(f"tamper: {old!r} not in stdout\n")
        out = out.replace(old.encode("latin-1"), new.encode("latin-1"))
    sys.stdout.buffer.write(out)
    sys.stdout.flush()
    rep, log = arg(args, "--report"), arg(args, "--log")
    if mode == "drop_report":
        os.remove(rep)
    elif mode == "stale_report":
        edit_report(rep, lambda r: r.update(run_id="0" * 32))
    elif mode == "drop_worker":
        edit_report(rep, drop_worker)
    elif mode == "worker_incomplete":
        edit_report(rep, worker_incomplete)
    elif mode == "flag_skips_ack":
        edit_report(rep, flag_skips_ack)
    elif mode == "drop_ucclog":
        os.remove("UCC.log")
    elif mode == "drop_xrtlog":
        os.remove(log)
    elif mode.startswith("ucclog:"):
        rx, new = mode[len("ucclog:"):].split("=>", 1)
        with open("UCC.log", "rb") as f:
            text = f.read().decode("latin-1")
        text2 = re.sub(rx, new, text, flags=re.M)
        if text2 == text:
            sys.stderr.write(f"tamper: {rx!r} matched nothing in UCC.log\n")
        with open("UCC.log", "wb") as f:
            f.write(text2.encode("latin-1"))
    elif mode != "none" and not mode.startswith("stdout:"):
        sys.exit(f"tamper: unknown mode {mode}")
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
