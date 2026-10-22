"""Runner self-test helper: a deliberately broken "candidate" for tools/xrt/run_xrt.py regression tests.

Usage (as the candidate command prefix): python -I tamper_candidate.py <mode> <xrt_ucc.exe arguments...>
Runs the real experiments/xrt/build/xrt_ucc.exe with the given arguments in the current directory (the run's fresh
sandbox), then sabotages the result according to <mode>. The runner must notice every sabotage except the
documented, normalised timing differences. A mode whose pattern matches nothing does NOT silently pass: it prints
an "XRT FATAL tamper" diagnostic and exits 99, so a test expecting PASS fails loudly.

  none                         pass everything through unchanged
  drop_report                  delete the runtime report
  stale_report                 rewrite the report's run id (a report from another run)
  stale_xrtlog                 rewrite the runtime log's run id
  drop_worker                  remove the worker thread and every worker event from the report
  worker_incomplete            the worker never acknowledges: drop its 1->2 store, ExitThread and end events, and
                               the main thread's 'shutdown wait finished' mark; thread 1 'running' at exit
  flag_skips_ack               drop the worker's 1->2 store of FFileStream::Destroyed from the timeline
  flag_by_main                 attribute the 1->2 store to the main thread (a patched flag)
  drop_ucclog                  delete the UCC.log the run wrote in the sandbox
  drop_xrtlog                  delete the runtime log
  fatal_stderr                 append an "XRT FATAL" diagnostic to stderr (report untouched)
  hang                         sleep past the harness limit after the run
  extra_write                  create an additional file in the sandbox
  ucclog_lf                    convert the sandbox UCC.log's CRLF line endings to LF
  stdout:<old>=><new>          replace text in the candidate's stdout
  stdoutre:<regex>=><new>      regex-replace in the candidate's stdout (bytes, latin-1)
  ucclog:<regex>=><new>        regex-replace lines in the sandbox UCC.log
"""
import json
import os
import re
import subprocess
import sys
import time

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
XRT = os.path.join(WS, "experiments", "xrt", "build", "xrt_ucc.exe")


def arg(args, name):
    return args[args.index(name) + 1] if name in args else None


def noop(what):
    sys.stderr.write(f"XRT FATAL tamper: {what} matched nothing\n")
    sys.exit(99)


def edit_report(path, fn):
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    fn(rep)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, indent=1)


def drop_worker(rep):
    rep["threads"] = [t for t in rep["threads"] if t.get("index") != 1]
    rep["events"] = [e for e in rep["events"] if e.get("thread") != 1 and e.get("index") != 1]
    rep["events_recorded"] = len(rep["events"])


def worker_incomplete(rep):
    for t in rep["threads"]:
        if t.get("index") == 1:
            t.update(state="running", exit_via="", exit_code=0)
    rep["events"] = [e for e in rep["events"] if not (
        (e.get("kind") in ("exit_thread", "thread_end") and e.get("thread") == 1)
        or (e.get("kind") == "watch_store" and e.get("new") == 2)
        or (e.get("kind") == "mark" and e.get("name") == "FFileStream::Destroy: shutdown wait finished"))]
    for e in rep["events"]:
        if e.get("kind") == "thread_at_exit" and e.get("index") == 1:
            e["state"] = "alive"
    rep["events_recorded"] = len(rep["events"])


def flag_skips_ack(rep):
    rep["events"] = [e for e in rep["events"] if not (e.get("kind") == "watch_store" and e.get("new") == 2)]
    rep["events_recorded"] = len(rep["events"])


def flag_by_main(rep):
    st = [e for e in rep["events"] if e.get("kind") == "watch_store" and e.get("new") == 2]
    if not st:
        noop("flag_by_main")
    st[0]["thread"] = 0


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    p = subprocess.run([XRT] + args, stdout=subprocess.PIPE)
    out = p.stdout
    if mode.startswith("stdout:"):
        old, new = mode[len("stdout:"):].split("=>", 1)
        if old.encode("latin-1") not in out:
            noop(mode)
        out = out.replace(old.encode("latin-1"), new.encode("latin-1"))
    elif mode.startswith("stdoutre:"):
        rx, new = mode[len("stdoutre:"):].split("=>", 1)
        out2 = re.sub(rx.encode("latin-1"), new.encode("latin-1"), out)
        if out2 == out:
            noop(mode)
        out = out2
    sys.stdout.buffer.write(out)
    sys.stdout.flush()
    rep, log = arg(args, "--report"), arg(args, "--log")
    if mode == "drop_report":
        os.remove(rep)
    elif mode == "stale_report":
        edit_report(rep, lambda r: r.update(run_id="0" * 32))
    elif mode == "stale_xrtlog":
        with open(log, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if not lines or "run id: " not in lines[0]:
            noop(mode)
        lines[0] = lines[0].split("run id: ")[0] + "run id: " + "0" * 32 + "\n"
        with open(log, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)
    elif mode == "drop_worker":
        edit_report(rep, drop_worker)
    elif mode == "worker_incomplete":
        edit_report(rep, worker_incomplete)
    elif mode == "flag_skips_ack":
        edit_report(rep, flag_skips_ack)
    elif mode == "flag_by_main":
        edit_report(rep, flag_by_main)
    elif mode == "drop_ucclog":
        os.remove("UCC.log")
    elif mode == "drop_xrtlog":
        os.remove(log)
    elif mode == "fatal_stderr":
        sys.stderr.write("\nXRT FATAL (exit 76): injected by tamper_candidate\n")
    elif mode == "hang":
        time.sleep(3600)
    elif mode == "extra_write":
        with open("Tamper.ini", "w") as f:
            f.write("[Tamper]\nx=1\n")
    elif mode == "ucclog_lf":
        with open("UCC.log", "rb") as f:
            data = f.read()
        if b"\r\n" not in data:
            noop(mode)
        with open("UCC.log", "wb") as f:
            f.write(data.replace(b"\r\n", b"\n"))
    elif mode.startswith("ucclog:"):
        rx, new = mode[len("ucclog:"):].split("=>", 1)
        with open("UCC.log", "rb") as f:
            text = f.read().decode("latin-1")
        text2 = re.sub(rx, new, text, flags=re.M)
        if text2 == text:
            noop(mode)
        with open("UCC.log", "wb") as f:
            f.write(text2.encode("latin-1"))
    elif mode != "none" and not mode.startswith(("stdout:", "stdoutre:")):
        sys.exit(f"tamper: unknown mode {mode}")
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
