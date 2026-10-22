"""Acceptance runner for the translated runtime: run the ORIGINAL UCC.exe and the translated one (xrt_ucc.exe)
on a registered case (tools/xrt/cases.py) and decide, separately for every run:

  candidate_execution_completed  the translated process ran to its own exit: report written by this run (run id),
                                 outcome "exited", report and process exit codes agree, no fatal diagnostic/timeout
  output_matches_reference       stdout, exit code and UCC.log equal a FRESH original run made by this invocation
                                 (null when there is no reference: equivalence is never claimed without one)
  expected_result                the case's own expectation (exit code, required/forbidden stdout lines) holds for
                                 the translated run - and for the reference, which is otherwise not a valid one
  milestone_evidence_valid       the case's evidence profile holds on the translated run's event timeline (runtime
                                 report "events", recorded by the marks/watches of tools/xrt/marks.json)

A run PASSes only if all four hold. Without a reference (--no-original) a run is at best UNVERIFIED: execution,
expected result and evidence can be confirmed, equivalence cannot.

Isolation and freshness: both executables run in the SAME guest-visible sandbox path, sandbox_cmp/<case>/System,
recreated from the read-only install before every single execution (the engine hashes paths into its config maps,
so equal paths are needed for comparable internal behaviour). Results go to a directory created exclusively by
this invocation, experiments/xrt/results/raw/runs/<invocation-id>/<case>/run<k>/{original,xrt}/ (git-ignored);
nothing is read from any other location. The runtime report and log and the tracer's JSON must carry the run id
this invocation gave them; UCC.log must be absent from the fresh sandbox before a run and present after it.

Comparison rules (documented presentation/measurement differences; everything else must be byte-identical):
  stdout       identical after normalising only the elapsed-seconds field the VM prints in script warnings
               ("...:000F) 0.666 Attempt to assign variable through None": wall-clock seconds since start, it
               varies between runs of the original too); the raw byte comparison is reported as well
  exit code    identical
  UCC.log      identical after normalising: the two timestamp lines, "CPU Speed=" (measured), the elapsed
               "<n>ms Purging garbage", the same script-warning seconds, and "CPU Features:" only when the
               arguments do not contain -NOMMX -NOSSE (the translated runtime's CPU policy hides MMX/SSE; with
               those switches the original takes the same scalar paths and the line must match exactly)

Usage:
  python -I tools/xrt/run_xrt.py <case> [<case> ...] [--repeat N] [--timeout S] [--trace] [--no-original]
                                 [-- <commandlet args: must equal the case's registered arguments>]
  python -I tools/xrt/run_xrt.py --list
  python -I tools/xrt/run_xrt.py --reevaluate experiments/xrt/results/raw/runs/<invocation-id>
      (re-judge preserved raw artifacts with the current evaluation code; executes nothing)
Writes <invocation dir>/summary.json, <invocation dir>/<case>.summary.json (full evidence) and
experiments/xrt/results/compare/<case>.json (latest summary of the case, with its invocation id).
Exit status: 0 every run PASS; 1 any run FAIL; 2 usage error; 3 no failure, but some run UNVERIFIED.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import CASE_ID, CASES  # noqa: E402

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PY = sys.executable
XRT = os.path.join(WS, "experiments", "xrt", "build", "xrt_ucc.exe")
TRACER = os.path.join(WS, "experiments", "xrt", "build", "tracer", "uctrace.exe")
ENTRIES = os.path.join(WS, "experiments", "xrt", "traces", "entries")
RUNS_ROOT = os.path.join(WS, "experiments", "xrt", "results", "raw", "runs")
COMPARE_DIR = os.path.join(WS, "experiments", "xrt", "results", "compare")
SANDBOX_ROOT = os.path.join(WS, "sandbox_cmp")
MARKS = os.path.join(WS, "tools", "xrt", "marks.json")
MAX_REPEAT = 100
MAX_TIMEOUT = 3600.0
UCC_BASE, UCC_SIZE = 0x400000, 0xF000
WORKER_ENTRY = "0x1015a520"
EXIT_STATUS = {"PASS": 0, "FAIL": 1, "UNVERIFIED": 3}


class UsageError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ normalisation
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


def policy_line_differs(args):
    return not ({"-NOMMX", "-NOSSE"} <= {a.upper() for a in args})


# ------------------------------------------------------------------------------------------------ helpers
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inside(path, root):
    path, root = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    return path != root and os.path.commonpath([path, root]) == root


def rel(path):
    """workspace-relative path for summaries (absolute when outside the workspace)"""
    path = os.path.abspath(path)
    return os.path.relpath(path, WS).replace("\\", "/") if inside(path, WS) else path


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def git_identity():
    try:
        head = subprocess.run(["git", "-C", WS, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip()
        dirty = subprocess.run(["git", "-C", WS, "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                               text=True, timeout=30).stdout.strip()
        return {"head": head, "tracked_files_modified": bool(dirty), "modified": dirty.splitlines()[:50]}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": str(exc)}


def file_identity(path):
    return {"path": rel(path), "sha256": sha256_file(path)} if os.path.isfile(path) else {"path": rel(path), "missing": True}


def tree_digest(root, patterns=(".c", ".h", ".py", ".json", ".cmd")):
    """SHA-256 over (relative name, content) of the source files below root: identifies an exact source state
    even when it is not committed (generated code in gen/ is never committed)."""
    h, n = hashlib.sha256(), 0
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for f in sorted(files):
            if f.endswith(patterns):
                p = os.path.join(dirpath, f)
                h.update(os.path.relpath(p, root).replace("\\", "/").encode() + b"\0" + read_bytes(p) + b"\0")
                n += 1
    return {"path": rel(root), "files": n, "sha256": h.hexdigest()}


# ------------------------------------------------------------------------------------------------ sandbox
def fresh_sandbox(case_name):
    """Recreate sandbox_cmp/<case>/System from the install; returns (system dir, {file: sha256})."""
    if not CASE_ID.match(case_name):
        raise UsageError(f"bad case id {case_name!r}")
    sb = os.path.join(SANDBOX_ROOT, case_name)
    if not inside(sb, SANDBOX_ROOT):
        raise UsageError(f"sandbox path escapes {SANDBOX_ROOT}: {sb}")
    p = subprocess.run([PY, "-I", os.path.join(WS, "tools", "xrt", "make_sandbox.py"), sb, "--probe"],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"make_sandbox failed ({p.returncode}): {p.stderr.strip()[:500]}")
    hashes = dict(line.split() for line in p.stdout.splitlines() if line.strip())
    sysdir = os.path.join(sb, "System")
    if os.path.exists(os.path.join(sysdir, "UCC.log")):
        raise RuntimeError("fresh sandbox already contains UCC.log (the install is expected not to have one)")
    return sysdir, hashes


# ------------------------------------------------------------------------------------------------ executions
def write_meta(outdir, meta):
    with open(os.path.join(outdir, "meta.json"), "w", newline="\n") as f:
        json.dump(meta, f, indent=1)


def execute_original(case, outdir, timeout, trace):
    """Run the original UCC.exe in the fresh sandbox; artifacts go to outdir (created here: must not exist)."""
    os.makedirs(outdir)
    sysdir, hashes = fresh_sandbox(case.name)
    run_id = uuid.uuid4().hex
    exe = os.path.join(sysdir, "UCC.exe")
    stdout_path = os.path.join(outdir, "stdout.bin")
    meta = {"run_id": run_id, "sandbox": rel(sysdir), "inputs": hashes, "trace": trace}
    t0 = time.time()
    if trace:
        cmd = [TRACER, ENTRIES, os.path.join(outdir, "trace.json"), stdout_path, exe] + list(case.args)
        meta["command"] = cmd
        try:
            p = subprocess.run(cmd, cwd=sysdir, capture_output=True, timeout=timeout,
                               env=dict(os.environ, UCTRACE_RUN_ID=run_id))
            meta["tracer_exit_code"] = p.returncode
            meta["tracer_output"] = (p.stdout + p.stderr).decode("utf-8", "replace")[-2000:]
        except subprocess.TimeoutExpired:
            meta["timed_out"] = True
    else:
        cmd = [exe] + list(case.args)
        meta["command"] = cmd
        try:
            with open(stdout_path, "wb") as f:
                p = subprocess.run(cmd, cwd=sysdir, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
            meta["process_exit_code"] = p.returncode
        except subprocess.TimeoutExpired:
            meta["timed_out"] = True
    meta["seconds"] = round(time.time() - t0, 3)
    if os.path.exists(os.path.join(sysdir, "UCC.log")):
        shutil.copy2(os.path.join(sysdir, "UCC.log"), os.path.join(outdir, "UCC.log"))
    write_meta(outdir, meta)
    return outdir


def execute_candidate(case, outdir, timeout, command_prefix=None):
    """Run the translated UCC (or, only for the runner's self-tests, a substitute command) in the fresh sandbox."""
    os.makedirs(outdir)
    sysdir, hashes = fresh_sandbox(case.name)
    run_id = uuid.uuid4().hex
    cmd = list(command_prefix or [XRT]) + [
        "--guest", os.path.join(sysdir, "UCC.exe"), "--log", os.path.join(outdir, "xrt.log"),
        "--report", os.path.join(outdir, "report.json"), "--run-id", run_id,
        "--timeout-ms", str(int(timeout * 1000)), "--"] + list(case.args)
    meta = {"run_id": run_id, "sandbox": rel(sysdir), "inputs": hashes, "command": cmd,
            "substitute_candidate": command_prefix is not None}
    t0 = time.time()
    try:
        with open(os.path.join(outdir, "stdout.bin"), "wb") as fo, open(os.path.join(outdir, "stderr.txt"), "wb") as fe:
            p = subprocess.run(cmd, cwd=sysdir, stdout=fo, stderr=fe, timeout=timeout + 30)
        meta["process_exit_code"] = p.returncode
    except subprocess.TimeoutExpired:
        meta["timed_out"] = True
    meta["seconds"] = round(time.time() - t0, 3)
    if os.path.exists(os.path.join(sysdir, "UCC.log")):
        shutil.copy2(os.path.join(sysdir, "UCC.log"), os.path.join(outdir, "UCC.log"))
    write_meta(outdir, meta)
    return outdir


# ------------------------------------------------------------------------------------------------ collection
META_KEYS = ("run_id", "command", "seconds", "trace", "inputs", "process_exit_code", "tracer_exit_code", "timed_out",
             "substitute_candidate")


def _meta(outdir, r):
    try:
        meta = load_json(os.path.join(outdir, "meta.json"))
        if not isinstance(meta, dict) or not meta.get("run_id"):
            raise ValueError("no run id")
    except (OSError, ValueError) as exc:
        r["errors"].append(f"meta.json missing or malformed: {exc}")
        return None
    r["meta"] = {k: meta.get(k) for k in META_KEYS if k in meta}
    return meta


def collect_original(outdir):
    """Validated artifacts of an original run. Reads only from outdir. r['ok'] is False on any problem."""
    r = {"dir": rel(outdir), "errors": []}
    err = r["errors"].append
    meta = _meta(outdir, r)
    if meta is None:
        r["ok"] = False
        return r
    if meta.get("timed_out"):
        err("original run timed out")
    if meta.get("trace"):
        r["tool"] = "uctrace"
        if meta.get("tracer_exit_code") != 0:
            err(f"tracer failure: uctrace exit status {meta.get('tracer_exit_code')}: "
                f"{(meta.get('tracer_output') or '').strip()[-300:]}")
        try:
            tr = load_json(os.path.join(outdir, "trace.json"))
            if not isinstance(tr, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as exc:
            err(f"tracer failure: trace.json missing or malformed: {exc}")
            tr = None
        if tr is not None:
            if tr.get("run_id") != meta["run_id"]:
                err(f"tracer failure: stale or foreign trace (run id {tr.get('run_id')!r}, expected {meta['run_id']!r})")
            elif tr.get("complete") is not True:
                err("tracer failure: trace incomplete (no EXIT_PROCESS event)")
            elif not isinstance(tr.get("exit_code"), int):
                err("tracer failure: trace has no guest exit code")
            else:
                r["exit_code"] = tr["exit_code"]    # the GUEST's exit code, whatever it is (not a tool failure)
                r["trace"] = tr
    else:
        r["tool"] = "direct"
        if isinstance(meta.get("process_exit_code"), int):
            r["exit_code"] = meta["process_exit_code"]
    if "exit_code" not in r and not r["errors"]:
        err("no guest exit code recorded")
    try:
        r["stdout"] = read_bytes(os.path.join(outdir, "stdout.bin"))
    except OSError:
        err("stdout missing")
    try:
        r["log"] = read_bytes(os.path.join(outdir, "UCC.log")).decode("latin-1")
    except OSError:
        err("UCC.log missing (the original did not write one in the fresh sandbox)")
    r["ok"] = not r["errors"]
    return r


def collect_candidate(outdir):
    """Validated artifacts of a translated run. Reads only from outdir. r['ok'] is False on any problem."""
    r = {"dir": rel(outdir), "errors": []}
    err = r["errors"].append
    meta = _meta(outdir, r)
    if meta is None:
        r["ok"] = False
        return r
    if meta.get("timed_out"):
        err("translated process did not exit (harness timeout)")
    if isinstance(meta.get("process_exit_code"), int):
        r["exit_code"] = meta["process_exit_code"]
    elif not meta.get("timed_out"):
        err("no process exit code recorded")
    try:
        r["stdout"] = read_bytes(os.path.join(outdir, "stdout.bin"))
    except OSError:
        err("stdout missing")
    try:
        r["stderr"] = read_bytes(os.path.join(outdir, "stderr.txt")).decode("utf-8", "replace")
    except OSError:
        err("stderr missing")
    try:
        r["log"] = read_bytes(os.path.join(outdir, "UCC.log")).decode("latin-1")
    except OSError:
        err("UCC.log missing (the translated run did not write one in the fresh sandbox)")
    try:
        rep = load_json(os.path.join(outdir, "report.json"))
        if not isinstance(rep, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as exc:
        err(f"runtime report missing or malformed: {exc}")
        rep = None
    if rep is not None:
        if rep.get("run_id") != meta["run_id"]:
            err(f"stale or foreign runtime report (run id {rep.get('run_id')!r}, expected {meta['run_id']!r})")
        elif rep.get("schema") != 2:
            err(f"runtime report schema {rep.get('schema')!r}, expected 2")
        elif not isinstance(rep.get("events"), list) or not isinstance(rep.get("threads"), list):
            err("runtime report lacks the event timeline or the thread list")
        else:
            r["report"] = rep
    try:
        with open(os.path.join(outdir, "xrt.log"), encoding="utf-8", errors="replace") as f:
            first = f.readline()
        if first.rstrip("\n").split("] ", 1)[-1] != f"run id: {meta['run_id']}":
            err("runtime log does not carry this run's id")
    except OSError:
        err("runtime log missing")
    r["ok"] = not r["errors"]
    return r


# ------------------------------------------------------------------------------------------------ evidence
def in_ucc(addr_text):
    try:
        return UCC_BASE <= int(addr_text, 16) < UCC_BASE + UCC_SIZE
    except (TypeError, ValueError):
        return False


class Timeline:
    """Query helpers over the runtime report's ordered event list."""

    def __init__(self, report):
        self.ev = [e for e in report.get("events") or [] if isinstance(e, dict)]
        self.report = report

    def find(self, kind, **kw):
        return [e for e in self.ev if e.get("kind") == kind and all(e.get(k) == v for k, v in kw.items())]

    def first(self, kind, **kw):
        hits = self.find(kind, **kw)
        return hits[0] if hits else None

    def mark(self, name, **kw):
        return self.first("mark", name=name, **kw)

    def mark_from_ucc(self, name):
        """first occurrence of an entry mark whose return address ([esp] at entry) is in UCC.exe, on thread 0"""
        return next((e for e in self.find("mark", name=name, thread=0) if in_ucc(e.get("stack_top"))), None)

    def mark_count(self, name):
        return next((m.get("count") for m in self.report.get("marks") or [] if m.get("name") == name), None)


class Checks:
    def __init__(self, group):
        self.group, self.items = group, []

    def check(self, name, ok, detail=""):
        self.items.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    def require(self, name, event, detail=None):
        self.check(name, event is not None, "" if event is None or detail is None else detail(event))
        return event

    def order(self, name, *events):
        if any(e is None for e in events):
            return self.check(name, False, "an event is missing")
        seqs = [e["seq"] for e in events]
        return self.check(name, all(a < b for a, b in zip(seqs, seqs[1:])), f"seq {seqs}")

    def result(self):
        return {"group": self.group, "ok": bool(self.items) and all(i["ok"] for i in self.items), "checks": self.items}


def ev_init(t):
    c = Checks("engine_initialization")
    att = c.require("Core.dll DllMain(DLL_PROCESS_ATTACH) ran and returned TRUE",
                    t.first("dll_attach_returned", module="Core.dll", result=1))
    entry = c.require("UCC.exe entry point entered", t.first("exe_entry", module="UCC.exe"))
    main = c.require("UCC main entered (thread 0)", t.mark("UCC main", thread=0))
    init = c.require("appInit called from UCC.exe (thread 0)", t.mark_from_ucc("appInit"))
    si = c.require("UObject::StaticInit entered (thread 0)", t.mark("UObject::StaticInit", thread=0))
    fs = c.require("FFileStream::Init entered (thread 0)", t.mark("FFileStream::Init", thread=0))
    c.order("order: DllMain attach < UCC entry < UCC main < appInit < StaticInit < FFileStream::Init",
            att, entry, main, init, si, fs)
    return c.result()


def ev_load(t):
    c = Checks("package_load_and_commandlet_construction")
    si = t.mark("UObject::StaticInit", thread=0)
    lc = c.require("UObject::StaticLoadClass called from UCC.exe (thread 0)", t.mark_from_ucc("UObject::StaticLoadClass"))
    lo = c.require("UObject::StaticLoadObject entered (thread 0)", t.mark("UObject::StaticLoadObject", thread=0))
    pl = c.require("UObject::GetPackageLinker entered (thread 0)", t.mark("UObject::GetPackageLinker", thread=0))
    core_u = c.require("Core.u opened from the sandbox (CreateFile succeeded)",
                       next((e for e in t.find("file_open", ok=True, thread=0)
                             if str(e.get("resolved", "")).lower() == "<sandbox>\\system\\core.u"), None))
    cons = c.require("commandlet object constructed: UObject::StaticConstructObject called from UCC.exe",
                     t.mark_from_ucc("UObject::StaticConstructObject"), lambda e: f"caller {e.get('stack_top')}")
    c.order("order: StaticInit < StaticLoadClass < StaticLoadObject < GetPackageLinker < Core.u opened",
            si, lc, lo, pl, core_u)
    c.order("order: Core.u opened < commandlet construction", core_u, cons)
    return c.result()


def ev_commandlet(t, case):
    c = Checks("commandlet_execution")
    cons = t.mark_from_ucc("UObject::StaticConstructObject")
    main = c.require("UCommandlet::Main called from UCC.exe (thread 0)", t.mark_from_ucc("UCommandlet::Main"))
    em = c.require("UCommandlet::eventMain entered", t.mark("UCommandlet::eventMain", thread=0))
    ff = c.require("UObject::FindFunctionChecked entered", t.mark("UObject::FindFunctionChecked", thread=0))
    pe = c.require("UObject::ProcessEvent entered", t.mark("UObject::ProcessEvent", thread=0))
    pi = c.require("UObject::ProcessInternal entered (script bytecode executes)", t.mark("UObject::ProcessInternal", thread=0))
    c.order("order: construction < Main < eventMain < FindFunctionChecked < ProcessEvent < ProcessInternal",
            cons, main, em, ff, pe, pi)
    pre = t.mark("appPreExit", thread=0)
    for n in case.natives:
        e = c.require(f"case native {n} executed (thread 0)", t.mark(n, thread=0), lambda e, n=n: f"count {t.mark_count(n)}")
        c.order(f"order: ProcessInternal < first {n} < appPreExit", pi, e, pre)
    return c.result()


def ev_worker(t):
    c = Checks("worker_creation_and_execution")
    fs = t.mark("FFileStream::Init", thread=0)
    cr = c.require("thread 1 created by thread 0 at the FFileStream worker entry (Core.dll+5a520)",
                   t.first("thread_create", thread=0, index=1, entry=WORKER_ENTRY))
    st = c.require("thread 1 started", t.first("thread_start", thread=1, index=1))
    we = c.require("worker entry function executes on thread 1", t.mark("FFileStream worker thread entry", thread=1))
    c.order("order: FFileStream::Init < thread created < thread started < worker entry", fs, cr, st, we)
    other = [e for e in t.find("thread_create") if e.get("index") != 1]
    c.check("no other guest threads created", not other, f"{len(other)} other thread_create events")
    return c.result()


def ev_flag(t):
    c = Checks("shutdown_flag_transition")
    c.require("FFileStream::Destroyed is 0 when the watches are armed",
              t.first("watch_initial", name="FFileStream::Destroyed", value=0))
    stores = t.find("watch_store", name="FFileStream::Destroyed")
    shape = [(e.get("old"), e.get("new"), e.get("thread")) for e in stores]
    c.check("exactly the documented stores: 0->1 by the main thread, then 1->2 by the worker",
            shape == [(0, 1, 0), (1, 2, 1)], f"stores {shape}")
    destroy = t.mark("FFileStream::Destroy", thread=0)
    if len(stores) == 2:
        c.check("0->1 stored inside FFileStream::Destroy", "?Destroy@FFileStream@@SAXXZ" in stores[0].get("where", ""),
                stores[0].get("where", ""))
        c.check("1->2 stored inside the worker function", "in f_1015a520+" in stores[1].get("where", ""),
                stores[1].get("where", ""))
        c.order("order: FFileStream::Destroy < store 1 (main) < store 2 (worker)", destroy, stores[0], stores[1])
    else:
        c.check("order: FFileStream::Destroy < store 1 (main) < store 2 (worker)", False, "stores missing")
    un = t.find("watch_unattributed", name="FFileStream::Destroyed")
    c.check("no change of FFileStream::Destroyed that no recorded store explains",
            not un and t.report.get("watch_unattributed_changes") == 0, f"{len(un)} unattributed change events")
    w = next((w for w in t.report.get("watches") or [] if w.get("name") == "FFileStream::Destroyed"), None)
    c.check("watch armed; final value 2", w is not None and w.get("armed") == 1 and w.get("final") == 2, str(w))
    return c.result()


def ev_termination(t):
    c = Checks("worker_termination_and_wait_completion")
    stores = t.find("watch_store", name="FFileStream::Destroyed")
    s2 = stores[1] if len(stores) == 2 else None
    xt = c.require("worker called ExitThread(0)", t.first("exit_thread", thread=1, code=0))
    te = c.require("thread 1 ended via ExitThread with code 0", t.first("thread_end", thread=1, index=1, code=0, via="ExitThread"))
    c.order("order: store 2 < ExitThread < thread end", s2, xt, te)
    wf = c.require("main thread left the shutdown wait loop", t.mark("FFileStream::Destroy: shutdown wait finished", thread=0))
    c.order("order: store 2 (worker) < wait loop left (main)", s2, wf)
    ae = c.require("thread 1 had exited when the process exited", t.first("thread_at_exit", index=1, state="exited"))
    c.order("order: thread end < process exit", te, ae)
    th = next((x for x in t.report.get("threads") or [] if x.get("index") == 1), None)
    c.check("report: thread 1 exited via ExitThread with code 0",
            th is not None and th.get("state") == "exited" and th.get("exit_via") == "ExitThread" and th.get("exit_code") == 0,
            str(th))
    return c.result()


def ev_exit(t, expected_exit, before):
    c = Checks("engine_cleanup_and_exit")
    pre = c.require("appPreExit called from UCC.exe", t.mark_from_ucc("appPreExit"))
    se = c.require("UObject::StaticExit entered", t.mark("UObject::StaticExit", thread=0))
    ax = c.require("appExit called from UCC.exe", t.mark_from_ucc("appExit"))
    de = c.require("FFileStream::Destroy entered", t.mark("FFileStream::Destroy", thread=0))
    wf = t.mark("FFileStream::Destroy: shutdown wait finished", thread=0)
    mr = c.require("UCC main returned", t.mark("UCC main returned", thread=0), lambda e: f"returned {e.get('captured')}")
    if mr is not None:
        c.check(f"UCC main returned {expected_exit}", mr.get("captured") == expected_exit, f"{mr.get('captured')}")
    ce = c.require(f"CRT exit({expected_exit}) on thread 0", t.first("crt_exit", thread=0, code=expected_exit))
    pe = c.require(f"ExitProcess({expected_exit})", t.first("process_exit", code=expected_exit))
    dd = c.require("Core.dll DllMain(DLL_PROCESS_DETACH) ran", t.first("dll_detach_returned", module="Core.dll"))
    pc = c.require("process exit completed", t.first("process_exit_complete", code=expected_exit))
    c.order("order: [preceding milestone] < appPreExit < StaticExit < appExit < Destroy < wait left < main returned "
            "< exit() < ExitProcess < DLL detach < exit complete", before, pre, se, ax, de, wf, mr, ce, pe, dd, pc)
    rep = t.report
    c.check(f"report outcome 'exited' with exit code {expected_exit}",
            rep.get("outcome") == "exited" and rep.get("exit_code") == expected_exit, f"{rep.get('outcome')} {rep.get('exit_code')}")
    c.check("no fatal or timeout event", not t.find("fatal") and not t.find("timeout"))
    c.check("event timeline complete (nothing dropped)", rep.get("events_dropped") == 0, f"dropped {rep.get('events_dropped')}")
    return c.result()


def profile_core_commandlet(case, report):
    t = Timeline(report)
    return [ev_init(t), ev_load(t), ev_commandlet(t, case), ev_worker(t), ev_flag(t), ev_termination(t),
            ev_exit(t, case.expect.exit_code, t.mark("UObject::ProcessInternal", thread=0))]


def profile_core_error(case, report):
    t = Timeline(report)
    c = Checks("lookup_failure")
    lc = c.require("UObject::StaticLoadClass called from UCC.exe", t.mark_from_ucc("UObject::StaticLoadClass"))
    c.check("no commandlet executed (UCommandlet::Main never entered)", t.mark_count("UCommandlet::Main") == 0,
            f"count {t.mark_count('UCommandlet::Main')}")
    return [ev_init(t), c.result(), ev_worker(t), ev_flag(t), ev_termination(t), ev_exit(t, case.expect.exit_code, lc)]


PROFILES = {"core_commandlet": profile_core_commandlet, "core_error": profile_core_error}
# function-entry marks each profile relies on; with --trace each must also have executed in the ORIGINAL
PROFILE_ENTRY_MARKS = {
    "core_commandlet": ("appInit", "UObject::StaticInit", "FFileStream::Init", "UObject::StaticLoadClass",
                        "UObject::StaticLoadObject", "UObject::GetPackageLinker", "UObject::StaticConstructObject",
                        "UCommandlet::Main", "UCommandlet::eventMain", "UObject::FindFunctionChecked", "UObject::ProcessEvent",
                        "UObject::ProcessInternal", "appPreExit", "UObject::StaticExit", "appExit", "FFileStream::Destroy"),
    "core_error": ("appInit", "UObject::StaticInit", "FFileStream::Init", "UObject::StaticLoadClass", "appPreExit",
                   "UObject::StaticExit", "appExit", "FFileStream::Destroy"),
}


def export_rvas(path):
    """{export name: rva}, parsed from an in-memory copy (a memory-mapped file would keep the sandbox locked)."""
    import pefile
    pe = pefile.PE(data=read_bytes(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    out = {e.name.decode(): e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    pe.close()
    return out


def original_cross_check(case, trace, core_exports):
    """--trace: the original must also have executed every function-entry mark the evidence relies on."""
    cfg = load_json(MARKS)["Core.dll"]["marks"]
    by_name = {e["name"]: e for e in cfg}
    hits = next(({int(x, 16) for x in m.get("hit_rvas", [])} for m in trace.get("modules", [])
                 if m.get("instrumented") and str(m.get("name", "")).lower() == "core.dll"), set())
    out = []
    for n in PROFILE_ENTRY_MARKS.get(case.profile, ()) + tuple(case.natives):
        e = by_name.get(n)
        rva = core_exports.get(e["export"]) if e and "export" in e else (int(e["va"], 16) - 0x10100000 if e else None)
        out.append({"check": f"original executed {n}", "ok": rva is not None and rva in hits,
                    "detail": f"rva {rva:#x}" if rva is not None else "unknown mark"})
    return out


# ------------------------------------------------------------------------------------------------ evaluation
def check_expectation(expect, exit_code, stdout):
    problems = []
    if exit_code != expect.exit_code:
        problems.append(f"exit code {exit_code}, expected {expect.exit_code}")
    text = stdout.decode("latin-1") if stdout is not None else ""
    problems += [f"stdout lacks {s!r}" for s in expect.stdout_contains if s not in text]
    problems += [f"stdout contains forbidden {s!r}" for s in expect.stdout_excludes if s in text]
    return problems


def compare(case, ref, cand):
    a, b = ref["stdout"], cand["stdout"]
    out = {"stdout_byte_identical": a == b,
           "stdout_identical_after_normalisation": normalise_stdout(a) == normalise_stdout(b),
           "exit_code_identical": ref.get("exit_code") == cand.get("exit_code")}
    la = normalise_log(ref["log"], policy_line_differs(case.args)).split("\n")
    lb = normalise_log(cand["log"], policy_line_differs(case.args)).split("\n")
    diff = [f"line {i + 1}: - {x} | + {y}" for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    if len(la) != len(lb):
        diff.append(f"line count {len(la)} vs {len(lb)}")
    out["ucc_log_identical_after_normalisation"] = not diff
    out["ucc_log_diff"] = diff[:20]
    if not out["stdout_identical_after_normalisation"]:
        sa, sb = normalise_stdout(a).splitlines(), normalise_stdout(b).splitlines()
        sd = [f"line {i + 1}: - {x} | + {y}" for i, (x, y) in enumerate(zip(sa, sb)) if x != y]
        if len(sa) != len(sb):
            sd.append(f"line count {len(sa)} vs {len(sb)}")
        out["stdout_diff"] = sd[:20]
    out["match"] = out["stdout_identical_after_normalisation"] and out["exit_code_identical"] and not diff
    return out


def evaluate(case, ref, cand, core_exports=None):
    """Verdict for one run from collected artifacts (ref is None when there is no reference)."""
    v = {"failures": []}
    fail = v["failures"].append
    # 1. candidate execution
    rep = cand.get("report")
    completed = bool(cand.get("ok")) and rep is not None
    for e in cand["errors"]:
        fail(f"translated run: {e}")
    if rep is not None:
        if rep.get("outcome") != "exited":
            completed = False
            fail(f"translated run did not exit normally: outcome {rep.get('outcome')!r}")
        if rep.get("exit_code") != cand.get("exit_code"):
            completed = False
            fail(f"report exit code {rep.get('exit_code')} differs from the process exit code {cand.get('exit_code')}")
    diag = [ln for ln in cand.get("stderr", "").splitlines() if ln.startswith(("XRT FATAL", "XRT TIMEOUT"))]
    if diag:
        completed = False
        fail(f"translated run stopped with a diagnostic: {diag[0][:300]}")
    v["candidate_execution_completed"] = completed
    # 2. expected result of the case
    problems = check_expectation(case.expect, cand.get("exit_code"), cand.get("stdout")) if "stdout" in cand else ["no stdout"]
    for p in problems:
        fail(f"expected result (translated run): {p}")
    v["expected_result"] = completed and not problems
    # 3. reference comparison
    if ref is None:
        v["reference"] = "none"
        v["output_matches_reference"] = None
    else:
        v["reference"] = "fresh-original"
        for e in ref["errors"]:
            fail(f"reference: {e}")
        ref_problems = check_expectation(case.expect, ref.get("exit_code"), ref.get("stdout")) if ref["ok"] else []
        for p in ref_problems:
            fail(f"reference does not produce the case's expected result: {p}")
        v["output_matches_reference"] = False
        if ref["ok"] and not ref_problems:
            if "stdout" in cand and "log" in cand:
                cmp = compare(case, ref, cand)
                v["comparison"] = cmp
                v["output_matches_reference"] = cmp["match"]
                if not cmp["match"]:
                    fail("output differs from the reference: " + ", ".join(
                        k for k in ("stdout_identical_after_normalisation", "exit_code_identical",
                                    "ucc_log_identical_after_normalisation") if not cmp[k]))
            else:
                fail("no comparable translated output (stdout or UCC.log missing)")
    # 4. milestone evidence
    if rep is None:
        v["evidence"] = []
        v["milestone_evidence_valid"] = False
        fail("milestone evidence: no valid runtime report from this run")
    else:
        groups = PROFILES[case.profile](case, rep)
        if ref is not None and ref.get("trace") is not None:
            cc = original_cross_check(case, ref["trace"], core_exports or {})
            groups.append({"group": "original_trace_cross_check", "ok": all(i["ok"] for i in cc), "checks": cc})
        v["evidence"] = groups
        v["milestone_evidence_valid"] = all(g["ok"] for g in groups)
        for g in groups:
            for i in g["checks"]:
                if not i["ok"]:
                    fail(f"milestone evidence [{g['group']}]: {i['check']} ({i['detail']})")
    # 5. identical inputs for both runs; translated code lifted from exactly these inputs
    cin = (cand.get("meta") or {}).get("inputs")
    if ref is not None and (ref.get("meta") or {}).get("inputs") != cin:
        fail("the original and translated runs used different input files")
    if rep is not None:
        mods = {m.get("name"): m.get("sha256") for m in rep.get("modules", [])}
        for f in ("UCC.exe", "Core.dll"):
            if not cin or mods.get(f) != cin.get(f):
                fail(f"translated {f} was not lifted from the sandbox input {f}")
    ok = not v["failures"] and completed and v["expected_result"] and v["milestone_evidence_valid"]
    v["verdict"] = ("PASS" if v["output_matches_reference"] is True else "UNVERIFIED") if ok else "FAIL"
    return v


# ------------------------------------------------------------------------------------------------ CLI
def parse_args(argv):
    if "--" in argv:
        k = argv.index("--")
        opts, extra = argv[:k], argv[k + 1:]
    else:
        opts, extra = argv, None

    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise UsageError(message)

    ap = Parser(prog="run_xrt.py", add_help=False)
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--repeat", default="1")
    ap.add_argument("--timeout", default="120")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--no-original", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(opts)
    if a.list:
        return a
    if not a.cases:
        raise UsageError("no case given (--list shows the registered cases)")
    for c in a.cases:
        if not CASE_ID.match(c) or c not in CASES:
            raise UsageError(f"unknown case {c!r}; registered: {', '.join(sorted(CASES))}")
    if len(set(a.cases)) != len(a.cases):
        raise UsageError("a case is listed twice")
    if not re.fullmatch(r"[0-9]+", a.repeat.strip()):
        raise UsageError(f"--repeat must be a positive integer, got {a.repeat!r}")
    a.repeat = int(a.repeat)
    if not 1 <= a.repeat <= MAX_REPEAT:
        raise UsageError(f"--repeat must be between 1 and {MAX_REPEAT}, got {a.repeat}")
    try:
        a.timeout = float(a.timeout)
    except ValueError as exc:
        raise UsageError(f"--timeout must be a number of seconds, got {a.timeout!r}") from exc
    if not math.isfinite(a.timeout) or not 0 < a.timeout <= MAX_TIMEOUT:
        raise UsageError(f"--timeout must be finite, positive and at most {MAX_TIMEOUT:g} s, got {a.timeout}")
    if a.trace and a.no_original:
        raise UsageError("--trace traces the original; it cannot be combined with --no-original")
    if extra is not None:
        if len(a.cases) != 1:
            raise UsageError("commandlet arguments after -- are only accepted with a single case")
        if tuple(extra) != CASES[a.cases[0]].args:
            raise UsageError(f"arguments {extra} differ from the registered arguments of {a.cases[0]}: "
                             f"{list(CASES[a.cases[0]].args)}")
    return a


def new_invocation_dir(root=RUNS_ROOT):
    inv = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    d = os.path.join(root, inv)
    os.makedirs(d)          # exclusive: a result location is never reused
    return inv, d


def run_invocation(case_names, repeat, timeout, trace=False, no_original=False, candidate_prefix=None, echo=print):
    if not case_names or not 1 <= repeat <= MAX_REPEAT or not (math.isfinite(timeout) and 0 < timeout <= MAX_TIMEOUT):
        raise UsageError("invalid case list, repeat count or timeout")
    inv, invdir = new_invocation_dir()
    identity = {
        "git": git_identity(),
        "runner": file_identity(os.path.abspath(__file__)),
        "cases_registry": file_identity(os.path.join(WS, "tools", "xrt", "cases.py")),
        "marks": file_identity(MARKS),
        "lifter": file_identity(os.path.join(WS, "tools", "xrt", "xlift.py")),
        "runtime_sources": tree_digest(os.path.join(WS, "experiments", "xrt", "runtime")),
        "generated_code": tree_digest(os.path.join(WS, "experiments", "xrt", "gen")),
        "candidate": file_identity(XRT) if candidate_prefix is None else {"substitute": list(candidate_prefix)},
        "tracer": file_identity(TRACER) if trace else None,
        "python": sys.version.split()[0], "host": platform.platform(),
    }
    core_exports = {}       # Core.dll export RVAs for the --trace cross-check (read from the first fresh sandbox)
    summaries = {}
    for name in case_names:
        case = CASES[name]
        s = {"runner_schema": 2, "invocation_id": inv, "invocation_dir": rel(invdir), "case": name, "args": list(case.args),
             "expect": {"exit_code": case.expect.exit_code, "negative": case.expect.negative,
                        "stdout_contains": list(case.expect.stdout_contains),
                        "stdout_excludes": list(case.expect.stdout_excludes)},
             "profile": case.profile, "natives": list(case.natives), "repeat": repeat, "timeout_s": timeout,
             "trace": trace, "reference": "none" if no_original else "fresh-original", "identity": identity, "runs": []}
        for k in range(repeat):
            rundir = os.path.join(invdir, name, f"run{k}")
            ref = None
            if not no_original:
                ref = collect_original(execute_original(case, os.path.join(rundir, "original"), timeout, trace))
                if trace and not core_exports:
                    core_exports = export_rvas(os.path.join(SANDBOX_ROOT, name, "System", "Core.dll"))
            cand = collect_candidate(execute_candidate(case, os.path.join(rundir, "xrt"), timeout, candidate_prefix))
            v = evaluate(case, ref, cand, core_exports)
            entry = {"run": k, "dir": rel(rundir), "verdict": v["verdict"],
                     "candidate": {"exit_code": cand.get("exit_code"), "seconds": (cand.get("meta") or {}).get("seconds"),
                                   "stdout_sha256": hashlib.sha256(cand["stdout"]).hexdigest() if "stdout" in cand else None,
                                   "inputs": (cand.get("meta") or {}).get("inputs")}}
            if ref is not None:
                entry["original"] = {"tool": ref.get("tool"), "exit_code": ref.get("exit_code"),
                                     "seconds": (ref.get("meta") or {}).get("seconds"),
                                     "stdout_sha256": hashlib.sha256(ref["stdout"]).hexdigest() if "stdout" in ref else None}
            entry.update(v)
            s["runs"].append(entry)
            echo(f"[{name} run {k}] {v['verdict']}: executed={v['candidate_execution_completed']} "
                 f"matches_reference={v['output_matches_reference']} expected_result={v['expected_result']} "
                 f"evidence={v['milestone_evidence_valid']} (translated exit {cand.get('exit_code')}"
                 + (f", original exit {ref.get('exit_code')} via {ref.get('tool')})" if ref is not None else ", no reference)"))
            for f in v["failures"][:8]:
                echo(f"    - {f}")
            if len(v["failures"]) > 8:
                echo(f"    ... {len(v['failures']) - 8} more (see the summary)")
        counts = {x: sum(1 for r in s["runs"] if r["verdict"] == x) for x in ("PASS", "FAIL", "UNVERIFIED")}
        s["counts"] = counts
        s["verdict"] = "FAIL" if counts["FAIL"] else "UNVERIFIED" if counts["UNVERIFIED"] else "PASS"
        summaries[name] = s
        with open(os.path.join(invdir, f"{name}.summary.json"), "w", newline="\n") as f:
            json.dump(s, f, indent=1)
    verdicts = [s["verdict"] for s in summaries.values()]
    overall = {"invocation_id": inv, "verdict": "FAIL" if "FAIL" in verdicts else "UNVERIFIED" if "UNVERIFIED" in verdicts else "PASS",
               "cases": {n: {"verdict": s["verdict"], "counts": s["counts"]} for n, s in summaries.items()}}
    with open(os.path.join(invdir, "summary.json"), "w", newline="\n") as f:
        json.dump(overall, f, indent=1)
    return inv, invdir, summaries, overall


def reevaluate(invdir, echo=print):
    """Re-judge the raw artifacts of an earlier invocation with the current evaluation code (nothing is executed;
    each run is still judged only on its own artifacts). Writes <invdir>/<case>.reevaluated.json."""
    out = {}
    for sp in sorted(f for f in os.listdir(invdir) if f.endswith(".summary.json")):
        s = load_json(os.path.join(invdir, sp))
        case = CASES[s["case"]]
        if list(case.args) != s["args"]:
            raise UsageError(f"{sp}: registered arguments changed since that invocation")
        core_exports = {}
        runs = []
        for r in s["runs"]:
            rundir = os.path.join(WS, r["dir"])
            ref = None if s["reference"] == "none" else collect_original(os.path.join(rundir, "original"))
            if ref is not None and ref.get("trace") is not None and not core_exports:
                core_exports = export_rvas(os.path.join(SANDBOX_ROOT, case.name, "System", "Core.dll"))
            v = evaluate(case, ref, collect_candidate(os.path.join(rundir, "xrt")), core_exports)
            runs.append({"run": r["run"], "dir": r["dir"], "original_verdict": r["verdict"]} | v)
            echo(f"[{case.name} run {r['run']}] {r['verdict']} -> {v['verdict']}")
            for f in v["failures"][:8]:
                echo(f"    - {f}")
        counts = {x: sum(1 for r in runs if r["verdict"] == x) for x in ("PASS", "FAIL", "UNVERIFIED")}
        res = {"reevaluated_invocation": s["invocation_id"], "case": case.name, "runner": file_identity(os.path.abspath(__file__)),
               "counts": counts, "verdict": "FAIL" if counts["FAIL"] else "UNVERIFIED" if counts["UNVERIFIED"] else "PASS",
               "runs": runs}
        with open(os.path.join(invdir, f"{case.name}.reevaluated.json"), "w", newline="\n") as f:
            json.dump(res, f, indent=1)
        out[case.name] = res
    return out


def public_summary(s):
    """The per-case summary kept in git: everything except the full per-check evidence (kept in the raw dir)."""
    out = dict(s)
    out["runs"] = []
    for r in s["runs"]:
        r2 = {k: v for k, v in r.items() if k != "evidence"}
        r2["evidence"] = [{"group": g["group"], "ok": g["ok"], "checks_passed": sum(1 for i in g["checks"] if i["ok"]),
                           "failed_checks": [i for i in g["checks"] if not i["ok"]]} for g in r.get("evidence", [])]
        out["runs"].append(r2)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--reevaluate"]:
        d = os.path.abspath(argv[1]) if len(argv) == 2 else ""
        if not d or not inside(d, RUNS_ROOT) or not os.path.isdir(d):
            print(f"run_xrt.py: --reevaluate needs one invocation directory below {rel(RUNS_ROOT)}", file=sys.stderr)
            return 2
        res = reevaluate(d)
        verdicts = [r["verdict"] for r in res.values()]
        overall = "FAIL" if "FAIL" in verdicts or not verdicts else "UNVERIFIED" if "UNVERIFIED" in verdicts else "PASS"
        print(f"re-evaluated {rel(d)}: {overall}; " + "; ".join(f"{n} {r['verdict']} {r['counts']}" for n, r in res.items()))
        return EXIT_STATUS[overall]
    try:
        a = parse_args(argv)
    except UsageError as exc:
        print(f"run_xrt.py: {exc}", file=sys.stderr)
        return 2
    if a.list:
        for n, c in sorted(CASES.items()):
            print(f"{n:16} {c.profile:16} {' '.join(c.args)}")
        return 0
    for exe, needed in ((XRT, True), (TRACER, a.trace)):
        if needed and not os.path.isfile(exe):
            print(f"run_xrt.py: {rel(exe)} is not built", file=sys.stderr)
            return 2
    inv, invdir, summaries, overall = run_invocation(a.cases, a.repeat, a.timeout, a.trace, a.no_original)
    os.makedirs(COMPARE_DIR, exist_ok=True)
    for n, s in summaries.items():
        with open(os.path.join(COMPARE_DIR, f"{n}.json"), "w", newline="\n") as f:
            json.dump(public_summary(s), f, indent=1)
    print(f"invocation {inv}: {overall['verdict']}; "
          + "; ".join(f"{n} {c['verdict']} {c['counts']}" for n, c in overall["cases"].items()))
    print(f"raw evidence: {rel(invdir)}")
    return EXIT_STATUS[overall["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
