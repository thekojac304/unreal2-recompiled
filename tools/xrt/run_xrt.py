"""Acceptance runner for the translated runtime: run the ORIGINAL UCC.exe and the translated one (xrt_ucc.exe)
on a registered case (tools/xrt/cases.py) and decide, separately for every run:

  candidate_execution_completed  the translated process ran to its own exit: report written by this run (run id),
                                 outcome "exited", report and process exit codes agree, no fatal diagnostic/timeout
  output_matches_reference       stdout, exit code, UCC.log and every other file the run wrote in its sandbox
                                 equal a FRESH original run made by this invocation with the same guest command
                                 line (null when there is no reference: equivalence is never claimed without one)
  expected_result                the case's own expectation (exit code, required/forbidden stdout lines) holds for
                                 the translated run - and for the reference, which is otherwise not a valid one
  milestone_evidence_valid       the case's evidence profile holds on the translated run's event timeline (runtime
                                 report "events", recorded by the marks/watches of tools/xrt/marks.json, which the
                                 build must have been lifted with: names, addresses and the file's SHA-256 are checked)

A run PASSes only if all four hold. Without a reference (--no-original) a run is at best UNVERIFIED: execution,
expected result and evidence can be confirmed, equivalence cannot. A failure of the harness itself (sandbox,
tool, unexpected exception) is recorded as a FAIL with "harness error" and gives exit status 4.

Isolation and freshness: both executables run in the SAME guest-visible sandbox path, sandbox_cmp/<case>/System,
recreated from manifest-verified snapshot inputs before every single execution (the engine hashes paths into its config maps,
so equal paths are needed for comparable internal behaviour) while holding an exclusive per-case lock. Results go
to a directory created exclusively by this invocation, experiments/xrt/results/raw/runs/<invocation-id>/<case>/
run<k>/{original,xrt}/ (git-ignored); nothing is read from any other location. The runtime report and log and the
tracer's JSON must carry the run id this invocation gave them; UCC.log must be absent from the fresh sandbox before
a run and present after it. Every file a run creates or changes in its sandbox is copied to <run dir>/written/.

Comparison rules (documented presentation/measurement differences; everything else must be byte-identical,
line endings included):
  stdout       identical after normalising only the elapsed-seconds field the VM prints in script warnings
               ("...:000F) 0.666 Attempt to assign variable through None": wall-clock seconds since start, it
               varies between runs of the original too); the raw byte comparison is reported as well
  exit code    identical
  UCC.log      identical after normalising: the two timestamp lines, "CPU Speed=" (measured), the elapsed
               "<n>ms Purging garbage", the same script-warning seconds, and "CPU Features:" only when the
               arguments do not contain -NOMMX -NOSSE (the translated runtime's CPU policy hides MMX/SSE; with
               those switches the original takes the same scalar paths and the line must match exactly)
  other files  the set of files written in the sandbox and their contents identical (no normalisation)

Usage:
  python -I tools/xrt/run_xrt.py <case> [<case> ...] [--repeat N] [--timeout S] [--trace] [--no-original]
                                 [-- <commandlet args: must equal the case's registered arguments>]
  python -I tools/xrt/run_xrt.py --list
  python -I tools/xrt/run_xrt.py --reevaluate experiments/xrt/results/raw/runs/<invocation-id>
      Re-judges the preserved raw artifacts of that invocation with the current evaluation code (nothing is
      executed); verdicts are labelled REEVALUATED_* and never count as a fresh PASS.
Writes <invocation dir>/summary.json, <invocation dir>/<case>.summary.json (full evidence) and
experiments/xrt/results/compare/<case>.json (latest summary of the case, with its invocation id; the directory can
be redirected with XRT_COMPARE_DIR, e.g. by the runner's own tests).
Exit status: 0 every run PASS; 1 any run FAIL; 2 usage error; 3 no failure, but some run UNVERIFIED;
4 harness error; 5 re-evaluation without failures (not a fresh result).
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
import traceback
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import CASE_ID, CASES  # noqa: E402

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PY = sys.executable
XRT = os.environ.get("XRT_BINARY") or os.path.join(WS, "experiments", "xrt", "build", "xrt_ucc.exe")
TRACER = os.path.join(WS, "experiments", "xrt", "build", "tracer", "uctrace.exe")
ENTRIES = os.path.join(WS, "experiments", "xrt", "traces", "entries")
RUNS_ROOT = os.path.join(WS, "experiments", "xrt", "results", "raw", "runs")
COMPARE_DIR = os.environ.get("XRT_COMPARE_DIR") or os.path.join(WS, "experiments", "xrt", "results", "compare")
SANDBOX_ROOT = os.path.join(WS, "sandbox_cmp")
MARKS = os.path.join(WS, "tools", "xrt", "marks.json")
MAX_REPEAT = 100
MIN_TIMEOUT, MAX_TIMEOUT = 1.0, 3600.0
TRACE_SLOWDOWN = 15          # the debugger-traced original runs ~10x slower than a direct run
UCC_BASE, UCC_SIZE = 0x400000, 0xF000
CORE_BASE, CORE_SIZE = 0x10100000, 0x191000
ENGINE_BASE = 0x10300000
GLMLIB_BASE = 0x02F40000      # lifted for an address the original loader rebased it to (preferred 0x10000000; the
                              # original's choice varies: 0x02df0000, 0x02dd0000 in vmprobe runs, 0x02f40000 in ucc make
                              # after Editor.dll at 0x02de0000 - the layout these lifts reproduce)
WORKER_ENTRY = "0x1015a520"
EXIT_STATUS = {"PASS": 0, "FAIL": 1, "UNVERIFIED": 3}
EXIT_HARNESS, EXIT_REEVALUATED = 4, 5


class UsageError(Exception):
    pass


class HarnessError(Exception):
    pass


# ------------------------------------------------------------------------------------------------ normalisation
ELAPSED_IN_WARNING = re.compile(r"(\(Function [^)]*\)) [0-9]+\.[0-9]{3} (Attempt to assign variable through None)")


def normalise_stdout(data):
    return ELAPSED_IN_WARNING.sub(r"\1 <elapsed> \2", data.decode("latin-1"))


def normalise_log(text, policy_line_differs):
    """Line-by-line normalisation; each line keeps its own terminator ('\\r' before the split point), so a
    difference in line endings is never normalised away."""
    out = []
    for line in text.split("\n"):
        end = "\r" if line.endswith("\r") else ""
        body = line[:-1] if end else line
        body = ELAPSED_IN_WARNING.sub(r"\1 <elapsed> \2", body)
        body = re.sub(r"^(Log: Log file open, |Uninitialized: Log file closed, ).*$", r"\1<timestamp>", body)
        body = re.sub(r"^Init: CPU Speed=.*$", "Init: CPU Speed=<measured>", body)
        body = re.sub(r"^Log: [0-9.]+ms Purging garbage$", "Log: <elapsed>ms Purging garbage", body)
        if policy_line_differs:
            body = re.sub(r"^Init: CPU Features:.*$", "Init: CPU Features: <policy>", body)
        out.append(body + end)
    return "\n".join(out)


def policy_line_differs(args):
    return not ({"-NOMMX", "-NOSSE"} <= {a.upper() for a in args})


# ------------------------------------------------------------------------------------------------ helpers
def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inside(path, root):
    try:
        path, root = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
        return path != root and os.path.commonpath([path, root]) == root
    except ValueError:              # different drives
        return False


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


def tree_digest(root, patterns=(".c", ".h", ".inc", ".py", ".json", ".cmd")):
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
class CaseLock:
    """Exclusive lock on sandbox_cmp/<case> for one execution (another invocation of the same case fails fast
    instead of deleting a running sandbox). Released by the OS if the process dies."""

    def __init__(self, case_name):
        import msvcrt
        self.msvcrt = msvcrt
        os.makedirs(SANDBOX_ROOT, exist_ok=True)
        self.path = os.path.join(SANDBOX_ROOT, f"{case_name}.lock")

    def __enter__(self):
        self.f = open(self.path, "a+b")
        try:
            self.f.seek(0)
            self.msvcrt.locking(self.f.fileno(), self.msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self.f.close()
            raise HarnessError(f"sandbox {self.path} is locked by another invocation") from exc
        return self

    def __exit__(self, *exc):
        self.f.seek(0)
        self.msvcrt.locking(self.f.fileno(), self.msvcrt.LK_UNLCK, 1)
        self.f.close()


def fresh_sandbox(case_name):
    """Recreate sandbox_cmp/<case>/System from verified snapshot inputs; returns (system dir, {file: sha256})."""
    if not CASE_ID.match(case_name):
        raise UsageError(f"bad case id {case_name!r}")
    sb = os.path.join(SANDBOX_ROOT, case_name)
    if not inside(sb, SANDBOX_ROOT):
        raise UsageError(f"sandbox path escapes {SANDBOX_ROOT}: {sb}")
    p = subprocess.run([PY, "-I", os.path.join(WS, "tools", "xrt", "make_sandbox.py"), sb, "--probe"],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise HarnessError(f"make_sandbox failed ({p.returncode}): {p.stderr.strip()[-500:]}")
    hashes = dict(line.split() for line in p.stdout.splitlines() if line.strip())
    sysdir = os.path.join(sb, "System")
    if os.path.exists(os.path.join(sysdir, "UCC.log")):
        raise HarnessError("fresh sandbox already contains UCC.log (verified source must not contain one)")
    return sysdir, hashes


def snapshot(sysdir):
    out = {}
    for dirpath, _, files in os.walk(sysdir):
        for f in files:
            p = os.path.join(dirpath, f)
            st = os.stat(p)
            out[os.path.relpath(p, sysdir).replace("\\", "/")] = (st.st_size, st.st_mtime_ns)
    return out


def capture_writes(sysdir, before, outdir):
    """Copy every file the run created or changed in the sandbox to outdir/written/; {rel: sha256}, [deleted]."""
    after = snapshot(sysdir)
    written = {}
    for relp, st in sorted(after.items()):
        if before.get(relp) != st:
            src = os.path.join(sysdir, relp)
            dst = os.path.join(outdir, "written", relp)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            written[relp] = sha256_file(dst)
    return written, sorted(set(before) - set(after))


# ------------------------------------------------------------------------------------------------ executions
def write_meta(outdir, meta):
    with open(os.path.join(outdir, "meta.json"), "w", newline="\n") as f:
        json.dump(meta, f, indent=1)


def tracer_env(run_id):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("UCTRACE_")}
    env["UCTRACE_RUN_ID"] = run_id
    return env


EH_POINTS_CACHE = {}


def eh_points_file(sysdir, hashes, outdir):
    """uctrace event points for every C++ EH funclet/continuation of UCC.exe and Core.dll (tools/xrt/eh_points.py),
    generated from the sandbox inputs (cached per input identity) and copied into the run directory."""
    key = (hashes.get("UCC.exe"), hashes.get("Core.dll"))
    if key not in EH_POINTS_CACHE:
        tmp = os.path.join(outdir, "eh_points.gen.txt")
        p = subprocess.run([PY, "-I", os.path.join(WS, "tools", "xrt", "eh_points.py"), os.path.join(sysdir, "Core.dll"),
                            os.path.join(sysdir, "UCC.exe"), "--out", tmp], capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise HarnessError(f"eh_points.py failed: {p.stderr.strip()[-300:]}")
        EH_POINTS_CACHE[key] = read_bytes(tmp)
        os.remove(tmp)
    dst = os.path.join(outdir, "eh_points.txt")
    with open(dst, "wb") as f:
        f.write(EH_POINTS_CACHE[key])
    return dst


def execute_original(case, outdir, timeout, trace):
    """Run the original UCC.exe in the fresh sandbox; artifacts go to outdir (created here: must not exist)."""
    os.makedirs(outdir)
    with CaseLock(case.name):
        sysdir, hashes = fresh_sandbox(case.name)
        before = snapshot(sysdir)
        run_id = uuid.uuid4().hex
        exe = os.path.join(sysdir, "UCC.exe")
        stdout_path = os.path.join(outdir, "stdout.bin")
        meta = {"run_id": run_id, "sandbox": rel(sysdir), "inputs": hashes, "trace": trace}
        t0 = time.time()
        if trace:
            cmd = [TRACER, ENTRIES, os.path.join(outdir, "trace.json"), stdout_path, exe] + list(case.args)
            meta["command"] = cmd
            meta["timeout_s"] = timeout * TRACE_SLOWDOWN
            env = tracer_env(run_id)
            if case.cxx_exceptions:
                points = eh_points_file(sysdir, hashes, outdir)
                env["UCTRACE_EVENTS"] = points
                meta["eh_points_sha256"] = sha256_file(points)
            try:
                p = subprocess.run(cmd, cwd=sysdir, capture_output=True, timeout=meta["timeout_s"], env=env)
                meta["tracer_exit_code"] = p.returncode
                meta["tracer_output"] = (p.stdout + p.stderr).decode("utf-8", "replace")[-2000:]
            except subprocess.TimeoutExpired:
                meta["timed_out"] = True
        else:
            cmd = [exe] + list(case.args)
            meta["command"] = cmd
            meta["command_line"] = subprocess.list2cmdline(cmd)
            meta["timeout_s"] = timeout
            try:
                with open(stdout_path, "wb") as f:
                    p = subprocess.run(cmd, cwd=sysdir, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
                meta["process_exit_code"] = p.returncode
            except subprocess.TimeoutExpired:
                meta["timed_out"] = True
        meta["seconds"] = round(time.time() - t0, 3)
        if os.path.exists(os.path.join(sysdir, "UCC.log")):
            shutil.copy2(os.path.join(sysdir, "UCC.log"), os.path.join(outdir, "UCC.log"))
        meta["written"], meta["deleted"] = capture_writes(sysdir, before, outdir)
    write_meta(outdir, meta)
    return outdir


def execute_candidate(case, outdir, timeout, command_prefix=None):
    """Run the translated UCC (or, only for the runner's self-tests, a substitute command) in the fresh sandbox."""
    os.makedirs(outdir)
    with CaseLock(case.name):
        sysdir, hashes = fresh_sandbox(case.name)
        before = snapshot(sysdir)
        run_id = uuid.uuid4().hex
        cmd = list(command_prefix or [XRT]) + [
            "--guest", os.path.join(sysdir, "UCC.exe"), "--log", os.path.join(outdir, "xrt.log"),
            "--report", os.path.join(outdir, "report.json"), "--run-id", run_id,
            "--timeout-ms", str(int(math.ceil(timeout * 1000))), "--"] + list(case.args)
        meta = {"run_id": run_id, "sandbox": rel(sysdir), "inputs": hashes, "command": cmd,
                "substitute_candidate": command_prefix is not None, "timeout_s": timeout + 30}
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
        meta["written"], meta["deleted"] = capture_writes(sysdir, before, outdir)
    write_meta(outdir, meta)
    return outdir


# ------------------------------------------------------------------------------------------------ collection
META_KEYS = ("run_id", "command", "command_line", "seconds", "trace", "inputs", "sandbox", "process_exit_code",
             "tracer_exit_code", "timed_out", "substitute_candidate", "written", "deleted", "timeout_s",
             "eh_points_sha256")


def _meta(outdir, r):
    try:
        meta = load_json(os.path.join(outdir, "meta.json"))
        if not isinstance(meta, dict) or not isinstance(meta.get("run_id"), str) or not meta["run_id"]:
            raise ValueError("no run id")
    except (OSError, ValueError) as exc:
        r["errors"].append(f"meta.json missing or malformed: {exc}")
        return None
    r["meta"] = {k: meta.get(k) for k in META_KEYS if k in meta}
    return meta


def _written_files(outdir, meta, r):
    """{rel: bytes} of the files this run wrote (from outdir/written, verified against meta's hashes)."""
    out = {}
    written = meta.get("written")
    if not isinstance(written, dict):
        r["errors"].append("no record of the files written in the sandbox")
        return out
    for relp, digest in written.items():
        p = os.path.join(outdir, "written", relp)
        if not inside(p, os.path.join(outdir, "written")):
            r["errors"].append(f"written-file path escapes the run directory: {relp}")
            continue
        try:
            data = read_bytes(p)
        except OSError:
            r["errors"].append(f"written file {relp} missing from the run directory")
            continue
        if sha256_bytes(data) != digest:
            r["errors"].append(f"written file {relp} does not match its recorded hash")
        out[relp] = data
    return out


def collect_original(outdir):
    """Validated artifacts of an original run. Reads only from outdir. r['ok'] is False on any problem."""
    r = {"dir": rel(outdir), "errors": []}
    err = r["errors"].append
    meta = _meta(outdir, r)
    if meta is None:
        r["ok"] = False
        return r
    if meta.get("trace"):
        r["tool"] = "uctrace"
        if meta.get("timed_out"):
            err(f"original timed out under the tracer (limit {meta.get('timeout_s')} s)")
        else:
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
                    err("tracer failure: trace incomplete (no EXIT_PROCESS event, or the debuggee did not terminate)")
                elif not isinstance(tr.get("exit_code"), int) or isinstance(tr.get("exit_code"), bool):
                    err("tracer failure: trace has no guest exit code")
                elif not isinstance(tr.get("command"), str):
                    err("tracer failure: trace has no debuggee command line")
                else:
                    r["exit_code"] = tr["exit_code"]    # the GUEST's exit code, whatever it is (not a tool failure)
                    r["command_line"] = tr["command"]
                    r["trace"] = tr
            if meta.get("eh_points_sha256"):
                try:
                    pts = read_bytes(os.path.join(outdir, "eh_points.txt"))
                    if sha256_bytes(pts) != meta["eh_points_sha256"]:
                        raise ValueError("hash mismatch")
                    r["eh_points"] = pts.decode("ascii").splitlines()
                except (OSError, ValueError, UnicodeDecodeError) as exc:
                    err(f"exception event points of this run missing or altered: {exc}")
    else:
        r["tool"] = "direct"
        if meta.get("timed_out"):
            err(f"original timed out (limit {meta.get('timeout_s')} s)")
        elif isinstance(meta.get("process_exit_code"), int):
            r["exit_code"] = meta["process_exit_code"]
            r["command_line"] = meta.get("command_line")
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
    r["written"] = _written_files(outdir, meta, r)
    r["ok"] = not r["errors"]
    return r


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_report(rep):
    """Schema problems of a runtime report (schema 2), [] when well formed."""
    p = []
    for key, typ in (("events", list), ("threads", list), ("modules", list), ("marks", list), ("watches", list)):
        if not isinstance(rep.get(key), typ) or not all(isinstance(x, dict) for x in rep.get(key) or []):
            p.append(f"'{key}' is not a list of objects")
    for key in ("exit_code", "events_recorded", "events_dropped", "watch_unattributed_changes"):
        if not _is_int(rep.get(key)):
            p.append(f"'{key}' is not an integer")
    if not isinstance(rep.get("outcome"), str) or not isinstance(rep.get("guest_command_line"), str):
        p.append("'outcome' or 'guest_command_line' is not a string")
    if p:
        return p
    last = 0
    for e in rep["events"]:
        if not _is_int(e.get("seq")) or not _is_int(e.get("thread")) or not isinstance(e.get("kind"), str):
            p.append(f"malformed event {str(e)[:120]}")
            break
        if e["seq"] <= last:
            p.append(f"event sequence not strictly increasing at seq {e['seq']}")
            break
        last = e["seq"]
        if e["kind"] == "incomplete" or e.get("truncated"):
            p.append(f"incomplete or truncated event at seq {e['seq']}")
            break
        for k, v in e.items():
            if k in ("name", "module", "where", "path", "resolved", "va", "stack_top", "entry", "via", "state", "addr") \
                    and not isinstance(v, str):
                p.append(f"event seq {e['seq']}: field '{k}' is not a string")
                break
    if rep["events_recorded"] != len(rep["events"]) + rep["events_dropped"]:
        p.append("events_recorded does not equal stored + dropped events")
    for m in rep["modules"]:
        if not isinstance(m.get("name"), str) or not isinstance(m.get("sha256"), str):
            p.append("module entry without name/sha256")
    for t in rep["threads"]:
        if not _is_int(t.get("index")) or not isinstance(t.get("state"), str):
            p.append("thread entry without index/state")
    return p


def collect_candidate(outdir):
    """Validated artifacts of a translated run. Reads only from outdir. r['ok'] is False on any problem."""
    r = {"dir": rel(outdir), "errors": []}
    err = r["errors"].append
    meta = _meta(outdir, r)
    if meta is None:
        r["ok"] = False
        return r
    if meta.get("timed_out"):
        err(f"translated process did not exit (harness limit {meta.get('timeout_s')} s)")
    elif _is_int(meta.get("process_exit_code")):
        r["exit_code"] = meta["process_exit_code"]
    else:
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
        else:
            problems = validate_report(rep)
            if problems:
                err("malformed runtime report: " + "; ".join(problems[:5]))
            else:
                r["report"] = rep
                r["command_line"] = rep["guest_command_line"]
    try:
        with open(os.path.join(outdir, "xrt.log"), encoding="utf-8", errors="replace") as f:
            first = f.readline()
        if first.rstrip("\n").split("] ", 1)[-1] != f"run id: {meta['run_id']}":
            err("runtime log does not carry this run's id")
    except OSError:
        err("runtime log missing")
    r["written"] = _written_files(outdir, meta, r)
    r["ok"] = not r["errors"]
    return r


# ------------------------------------------------------------------------------------------------ evidence
def in_ucc(addr_text):
    try:
        return UCC_BASE <= int(addr_text, 16) < UCC_BASE + UCC_SIZE
    except (TypeError, ValueError):
        return False


class Timeline:
    """Query helpers over the runtime report's ordered event list (validated by validate_report)."""

    def __init__(self, report):
        self.ev = report["events"]
        self.report = report

    def find(self, kind, **kw):
        return [e for e in self.ev if e.get("kind") == kind and all(e.get(k) == v for k, v in kw.items())]

    def first(self, kind, **kw):
        hits = self.find(kind, **kw)
        return hits[0] if hits else None

    def mark(self, name, **kw):
        return self.first("mark", name=name, **kw)

    def marks(self, name):
        return self.find("mark", name=name)

    def mark_from_ucc(self, name):
        """first occurrence of an entry mark whose return address ([esp] at entry) is in UCC.exe, on thread 0"""
        return next((e for e in self.find("mark", name=name, thread=0) if in_ucc(e.get("stack_top"))), None)

    def mark_count(self, name):
        return next((m.get("count") for m in self.report["marks"] if m.get("name") == name), None)


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


def expected_instrumentation(sysdir):
    """{(module, name): va} for every mark, {(module, name): addr} for every watch, as marks.json resolves against
    the input modules, and the SHA-256 of marks.json."""
    cfg_raw = read_bytes(MARKS)
    cfg = json.loads(cfg_raw)
    marks, watches = {}, {}
    for module, base in (("UCC.exe", UCC_BASE), ("Core.dll", CORE_BASE)):
        exports = export_rvas(os.path.join(sysdir, module))
        for e in cfg.get(module, {}).get("marks", []):
            marks[(module, e["name"])] = base + exports[e["export"]] if "export" in e else int(e["va"], 16)
        for e in cfg.get(module, {}).get("watches", []):
            watches[(module, e["name"])] = base + exports[e["export"]] if "export" in e else int(e["va"], 16)
    return marks, watches, sha256_bytes(cfg_raw)


def ev_instrumentation(t, expected):
    """The build was lifted with the current marks.json and every mark/watch sits where marks.json says."""
    c = Checks("instrumentation_binding")
    marks, watches, digest = expected
    for m in t.report["modules"]:
        c.check(f"{m['name']} was lifted with the current tools/xrt/marks.json", m.get("marks_sha256") == digest,
                f"{m.get('marks_sha256')} vs {digest}")
    got = {}
    for m in t.report["marks"]:
        try:
            got[(m.get("module"), m.get("name"))] = int(m.get("va"), 16)
        except (TypeError, ValueError):
            got[(m.get("module"), m.get("name"))] = None
    c.check("report marks are exactly the marks.json marks at the resolved addresses", got == marks,
            f"{len(got)} reported, {len(marks)} expected; differing: "
            f"{sorted(str(k) for k in set(got) ^ set(marks) | {k for k in got if k in marks and got[k] != marks[k]})[:5]}")
    bad = [e["seq"] for e in t.find("mark") if marks.get((e.get("module"), e.get("name"))) != _hex(e.get("va"))]
    c.check("every mark event carries its resolved address", not bad, f"seq {bad[:5]}")
    gotw = {(w.get("module"), w.get("name")): _hex(w.get("addr")) for w in t.report["watches"]}
    c.check("report watches are exactly the marks.json watches at the resolved addresses", gotw == watches, str(gotw))
    return c.result()


def _hex(v):
    try:
        return int(v, 16)
    except (TypeError, ValueError):
        return None


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
                             if e.get("resolved", "").lower() == "<sandbox>\\system\\core.u"), None))
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
    we = c.require("mark 'FFileStream worker thread entry' on thread 1: the worker function executes",
                   t.mark("FFileStream worker thread entry", thread=1))
    c.order("order: FFileStream::Init < thread created < thread started < worker entry", fs, cr, st, we)
    other = [e for e in t.find("thread_create") if e.get("index") != 1]
    c.check("no other guest threads created", not other, f"{len(other)} other thread_create events")
    # loader notification (none of the modules calls DisableThreadLibraryCalls): DLL_THREAD_ATTACH on the new thread
    # for every DLL initialised when it starts, in initialisation order, before its start routine
    want = [e.get("module") for e in initialised_dlls(t, st)]
    ta = t.find("dll_thread_attach", thread=1)
    c.check("DLL_THREAD_ATTACH on thread 1 for each DLL initialised before it started, in initialisation order",
            [e.get("module") for e in ta] == want, f"{[e.get('module') for e in ta]} vs {want}")
    if ta:
        c.order("order: thread started < DLL_THREAD_ATTACH notifications < worker entry", st, *ta, we)
    return c.result()


def initialised_dlls(t, before):
    """DLL_PROCESS_ATTACH completions (TRUE) before event `before`, in order, without DLLs a FreeLibrary unloaded
    again (dll_unloaded) before `before`: those got their DLL_PROCESS_DETACH then, not at process exit"""
    if before is None:
        return []
    unloads = t.find("dll_unloaded")
    return [e for e in t.find("dll_attach_returned") if e.get("result") == 1 and e["seq"] < before["seq"]
            and not any(u.get("module") == e.get("module") and e["seq"] < u["seq"] < before["seq"] for u in unloads)]


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
    w = next((w for w in t.report["watches"] if w.get("name") == "FFileStream::Destroyed"), None)
    c.check("watch armed; final value 2", w is not None and w.get("armed") == 1 and w.get("final") == 2, str(w))
    return c.result()


def ev_termination(t):
    c = Checks("worker_termination_and_wait_completion")
    stores = t.find("watch_store", name="FFileStream::Destroyed")
    s2 = stores[1] if len(stores) == 2 else None
    xt = c.require("worker called ExitThread(0)", t.first("exit_thread", thread=1, code=0))
    te = c.require("thread 1 ended via ExitThread with code 0", t.first("thread_end", thread=1, index=1, code=0, via="ExitThread"))
    c.order("order: store 2 < ExitThread < thread end", s2, xt, te)
    want = [e.get("module") for e in reversed(initialised_dlls(t, te))]
    td = t.find("dll_thread_detach", thread=1)
    c.check("DLL_THREAD_DETACH on thread 1 for each DLL initialised before it ended, in reverse initialisation order",
            [e.get("module") for e in td] == want, f"{[e.get('module') for e in td]} vs {want}")
    if td:
        c.order("order: ExitThread < DLL_THREAD_DETACH notifications < thread end", xt, *td, te)
    wf = c.require("mark 'FFileStream::Destroy: shutdown wait finished' on thread 0: main left the wait loop",
                   t.mark("FFileStream::Destroy: shutdown wait finished", thread=0))
    c.order("order: store 2 (worker) < wait loop left (main)", s2, wf)
    ae = c.require("thread 1 had exited when the process exited", t.first("thread_at_exit", index=1, state="exited"))
    c.order("order: thread end < process exit", te, ae)
    th = next((x for x in t.report["threads"] if x.get("index") == 1), None)
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
    want = [e.get("module") for e in reversed(initialised_dlls(t, pe))]
    got = [e.get("module") for e in t.find("dll_detach_returned") if pe is not None and pc is not None
           and pe["seq"] < e["seq"] < pc["seq"]]
    c.check("DLL_PROCESS_DETACH for every initialised DLL, in reverse initialisation order", got == want,
            f"{got} vs {want}")
    rep = t.report
    c.check(f"report outcome 'exited' with exit code {expected_exit}",
            rep.get("outcome") == "exited" and rep.get("exit_code") == expected_exit, f"{rep.get('outcome')} {rep.get('exit_code')}")
    c.check("no fatal or timeout event", not t.find("fatal") and not t.find("timeout"))
    c.check("event timeline complete (nothing dropped)", rep.get("events_dropped") == 0, f"dropped {rep.get('events_dropped')}")
    return c.result()


def ev_cxx(t):
    """the exception path completed inside the translated runtime: every throw was handled and execution resumed"""
    c = Checks("cxx_exception_path")
    ev = [e for e in t.ev if e["kind"].startswith("cxx_")]
    throws = [e for e in ev if e["kind"] == "cxx_throw"]
    c.check("C++ exceptions were thrown (the measured path throws)", throws, f"{len(throws)} throws")
    unhandled = []
    for i, e in enumerate(ev):
        if e["kind"] == "cxx_throw" and not e.get("rethrow"):
            nxt = next((x for x in ev[i + 1:] if x["kind"] in ("cxx_throw", "cxx_catch")), None)
            if nxt is None or nxt["kind"] != "cxx_catch":
                unhandled.append(e["seq"])
    c.check("every throw selected a handler before the next throw", not unhandled, f"throws without a catch: {unhandled[:5]}")
    catches = [e for e in ev if e["kind"] == "cxx_catch"]
    ends = [e for e in ev if e["kind"] == "cxx_catch_end"]
    c.check("every catch block ended (completed, abandoned or rethrown)", len(ends) == len(catches),
            f"{len(catches)} catches, {len(ends)} ends")
    done = [e for e in ends if e.get("how") == "completed"]
    resumes = [e for e in ev if e["kind"] == "cxx_resume"]
    c.check("execution resumed at a continuation after each completed catch", done and len(resumes) == len(done),
            f"{len(done)} completed, {len(resumes)} resumes")
    st = t.report.get("cxx_exceptions") or {}
    c.check("report statistics agree with the event timeline",
            st.get("throws") == sum(1 for e in throws if not e.get("rethrow")) and st.get("catches") == len(catches)
            and st.get("unwind_actions") == sum(1 for e in ev if e["kind"] == "cxx_unwind"), str(st))
    return c.result()


def eh_sequence_translated(report):
    out = []
    for e in report["events"]:
        k = e["kind"]
        if k == "cxx_throw":
            out.append(("throw", e.get("site"), bool(e.get("rethrow"))))
        elif k == "cxx_catch":
            out.append(("catch", e.get("funclet")))
        elif k == "cxx_unwind":
            out.append(("unwind", e.get("action")))
        elif k == "cxx_resume":
            out.append(("resume", e.get("continuation")))
    return out


def eh_sequence_original(trace, points):
    """the same sequence from the traced original: C++ exceptions (caller; no ThrowInfo type = rethrow), catch and
    unwind funclet entries, and the continuation a completed catch resumed at (the 'continue' point that follows
    the catch funclet and equals its static continuation)"""
    conts = {}
    for line in points or []:
        f = line.split()
        if len(f) >= 7 and f[2] == "catch" and f[-2] == "cont" and f[-1] != "none":
            conts[f[3]] = f[-1]
    excs = trace.get("exceptions") or []
    out, pending = [], None
    for e in trace.get("events") or []:
        if e.get("kind") == "exception":
            x = excs[e["index"]] if isinstance(e.get("index"), int) and 0 <= e["index"] < len(excs) else {}
            if e.get("code") == "0xe06d7363":
                out.append(("throw", e.get("caller"), not x.get("type")))
                pending = None
        elif e.get("kind") == "point":
            f = str(e.get("label", "")).split()
            if f[:1] == ["catch"]:
                out.append(("catch", f[1]))
                pending = conts.get(f[1])
            elif f[:1] == ["unwind"]:
                out.append(("unwind", f[1]))
            elif f[:1] == ["continue"] and pending and f[1] == pending:
                out.append(("resume", f[1]))
                pending = None
    return out


def ev_cxx_original(report, ref):
    c = Checks("cxx_exception_path_matches_original")
    tr, points = ref.get("trace") or {}, ref.get("eh_points")
    c.check("the original was traced with the exception event points",
            bool(points) and (tr.get("event_points") or 0) > 0 and tr.get("events_dropped") == 0,
            f"{tr.get('event_points')} points, dropped {tr.get('events_dropped')}")
    a, b = eh_sequence_original(tr, points), eh_sequence_translated(report)
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    if a == b:
        detail = f"{len(a)} events"
    elif first is not None:
        detail = f"first difference at {first}: original {a[first]} translated {b[first]}"
    else:
        detail = f"original {len(a)} / translated {len(b)} events; extra {(a[len(b):] or b[len(a):])[:2]}"
    c.check("same sequence of throws (site, rethrow), selected catch funclets, unwind actions and resumptions",
            a == b, detail)
    n = sum(1 for e in tr.get("exceptions") or [] if e.get("code") == "0xe06d7363")
    c.check("the original raised exactly the C++ exceptions in the sequence",
            n == sum(1 for x in a if x[0] == "throw") and n == len(tr.get("exceptions") or []),
            f"{n} C++ exceptions, {len(tr.get('exceptions') or [])} exceptions in total")
    return c.result()


def in_core(addr_text):
    try:
        return CORE_BASE <= int(addr_text, 16) < CORE_BASE + CORE_SIZE
    except (TypeError, ValueError):
        return False


def ev_engine(t):
    """Engine.dll is a genuine requirement of the case: Core loads it dynamically, and its static import GlmLib.dll
    is mapped (rebased, as in the original) and initialised before it; both execute translated code."""
    c = Checks("engine_module_loading")
    ll = c.require("Core.dll loads Engine.dll dynamically: LoadLibraryW, called from Core.dll, returned 0x10300000",
                   next((e for e in t.find("load_library", name="Engine.dll")
                         if e.get("result") == f"0x{ENGINE_BASE:08x}" and in_core(e.get("site"))), None),
                   lambda e: f"site {e.get('site')}")
    me = c.require("Engine.dll mapped at its preferred base",
                   t.first("dll_mapped", module="Engine.dll", base=f"0x{ENGINE_BASE:08x}", preferred_base=f"0x{ENGINE_BASE:08x}"))
    mg = c.require("GlmLib.dll (a static import of Engine.dll) mapped, rebased from its preferred base 0x10000000",
                   t.first("dll_mapped", module="GlmLib.dll", base=f"0x{GLMLIB_BASE:08x}", preferred_base="0x10000000"))
    ag = c.require("GlmLib.dll DllMain(DLL_PROCESS_ATTACH) returned TRUE", t.first("dll_attach_returned", module="GlmLib.dll", result=1))
    ae = c.require("Engine.dll DllMain(DLL_PROCESS_ATTACH) returned TRUE", t.first("dll_attach_returned", module="Engine.dll", result=1))
    c.order("order: Engine mapped < GlmLib mapped < GlmLib initialised < Engine initialised < LoadLibraryW returned",
            me, mg, ag, ae, ll)
    c.order("order: appInit < Engine.dll loaded < UCommandlet::Main", t.mark_from_ucc("appInit"), ll,
            t.mark_from_ucc("UCommandlet::Main"))
    mapped = [e.get("module") for e in t.find("dll_mapped")]
    c.check("exactly Engine.dll and GlmLib.dll mapped after startup, once each", sorted(mapped) == ["Engine.dll", "GlmLib.dll"],
            str(mapped))
    loaded = sorted({e.get("name") for e in t.find("load_library") if e.get("result") != "0x00000000"})
    c.check("LoadLibraryW succeeded only for translated modules (Core.dll, Engine.dll)",
            set(loaded) <= {"Core.dll", "Engine.dll"}, str(loaded))
    for name in ("Engine.dll", "GlmLib.dll"):
        m = next((m for m in t.report["modules"] if m.get("name") == name), None)
        n = (m or {}).get("functions_executed") or 0
        c.check(f"{name}: translated functions executed", n > 0, f"{n} functions")
    return c.result()


def engine_cross_check(trace, report):
    """--trace: the translated Engine.dll and GlmLib.dll executed exactly the functions the original executed"""
    orig = {}
    for m in trace.get("modules", []):
        if isinstance(m, dict) and m.get("instrumented") and not m.get("unloaded"):
            try:
                orig[str(m.get("name", "")).lower()] = {int(x, 16) for x in m.get("hit_rvas", [])}
            except (TypeError, ValueError):
                orig[str(m.get("name", "")).lower()] = None
    out = []
    for name in ("Engine.dll", "GlmLib.dll"):
        rm = next((m for m in report["modules"] if m.get("name") == name), None)
        xs = {int(x, 16) for x in (rm or {}).get("hit_rvas", [])}
        os_ = orig.get(name.lower())
        ok = rm is not None and os_ is not None and bool(xs) and xs == os_
        detail = (f"translated {len(xs)}, original {len(os_) if os_ is not None else 'not traced'}; only translated "
                  f"{sorted(hex(x) for x in xs - (os_ or set()))[:5]}, only original {sorted(hex(x) for x in (os_ or set()) - xs)[:5]}")
        out.append({"check": f"{name}: the translated run executed exactly the functions the original executed",
                    "ok": ok, "detail": detail})
    return out


def profile_core_commandlet(case, report):
    t = Timeline(report)
    return [ev_init(t), ev_load(t), ev_commandlet(t, case), ev_worker(t), ev_flag(t), ev_termination(t),
            ev_exit(t, case.expect.exit_code, t.mark("UObject::ProcessInternal", thread=0))] + \
        ([ev_cxx(t)] if case.cxx_exceptions else [])


def profile_engine_commandlet(case, report):
    return profile_core_commandlet(case, report) + [ev_engine(Timeline(report))]


def profile_core_error(case, report):
    t = Timeline(report)
    c = Checks("lookup_failure")
    lc = c.require("UObject::StaticLoadClass called from UCC.exe", t.mark_from_ucc("UObject::StaticLoadClass"))
    c.check("no commandlet executed (UCommandlet::Main never entered)", t.mark_count("UCommandlet::Main") == 0,
            f"count {t.mark_count('UCommandlet::Main')}")
    return [ev_init(t), c.result(), ev_worker(t), ev_flag(t), ev_termination(t), ev_exit(t, case.expect.exit_code, lc)] + \
        ([ev_cxx(t)] if case.cxx_exceptions else [])


PROFILES = {"core_commandlet": profile_core_commandlet, "core_error": profile_core_error,
            "engine_commandlet": profile_engine_commandlet}
# function-entry marks each profile relies on; with --trace each must also have executed in the ORIGINAL
COMMON_ENTRY_MARKS = (("UCC.exe", "UCC main"), ("Core.dll", "appInit"), ("Core.dll", "UObject::StaticInit"),
                      ("Core.dll", "FFileStream::Init"), ("Core.dll", "FFileStream worker thread entry"),
                      ("Core.dll", "UObject::StaticLoadClass"), ("Core.dll", "appPreExit"), ("Core.dll", "UObject::StaticExit"),
                      ("Core.dll", "appExit"), ("Core.dll", "FFileStream::Destroy"))
PROFILE_ENTRY_MARKS = {
    "core_commandlet": COMMON_ENTRY_MARKS + (
        ("Core.dll", "UObject::StaticLoadObject"), ("Core.dll", "UObject::GetPackageLinker"),
        ("Core.dll", "UObject::StaticConstructObject"), ("Core.dll", "UCommandlet::Main"),
        ("Core.dll", "UCommandlet::eventMain"), ("Core.dll", "UObject::FindFunctionChecked"),
        ("Core.dll", "UObject::ProcessEvent"), ("Core.dll", "UObject::ProcessInternal")),
    "core_error": COMMON_ENTRY_MARKS,
}
PROFILE_ENTRY_MARKS["engine_commandlet"] = PROFILE_ENTRY_MARKS["core_commandlet"]


def original_cross_check(case, trace, expected):
    """--trace: the original must also have executed every function-entry mark the evidence relies on."""
    marks = expected[0]
    hits = {}
    for m in trace.get("modules", []):
        if isinstance(m, dict) and m.get("instrumented"):
            try:
                hits[str(m.get("name", "")).lower()] = {int(x, 16) for x in m.get("hit_rvas", [])}
            except (TypeError, ValueError):
                hits[str(m.get("name", "")).lower()] = set()
    out = []
    names = PROFILE_ENTRY_MARKS.get(case.profile, ()) + tuple(("Core.dll", n) for n in case.natives)
    for module, n in names:
        va = marks.get((module, n))
        base = UCC_BASE if module == "UCC.exe" else CORE_BASE
        ok = va is not None and (va - base) in hits.get(module.lower(), set())
        out.append({"check": f"original executed {module} {n}", "ok": ok,
                    "detail": f"rva {va - base:#x}" if va is not None else "unknown mark"})
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
    diff = [f"line {i + 1}: - {x!r} | + {y!r}" for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    if len(la) != len(lb):
        diff.append(f"line count {len(la)} vs {len(lb)}")
    out["ucc_log_identical_after_normalisation"] = not diff
    out["ucc_log_diff"] = diff[:20]
    if not out["stdout_identical_after_normalisation"]:
        sa, sb = normalise_stdout(a).split("\n"), normalise_stdout(b).split("\n")
        sd = [f"line {i + 1}: - {x!r} | + {y!r}" for i, (x, y) in enumerate(zip(sa, sb)) if x != y]
        if len(sa) != len(sb):
            sd.append(f"line count {len(sa)} vs {len(sb)}")
        out["stdout_diff"] = sd[:20]
    wa = {k: v for k, v in ref["written"].items() if k != "UCC.log"}
    wb = {k: v for k, v in cand["written"].items() if k != "UCC.log"}
    out["written_files"] = sorted(set(wa) | set(wb))
    out["written_files_identical"] = wa == wb
    if wa != wb:
        out["written_files_diff"] = sorted(k for k in set(wa) | set(wb) if wa.get(k) != wb.get(k))[:20]
    out["match"] = (out["stdout_identical_after_normalisation"] and out["exit_code_identical"] and not diff
                    and out["written_files_identical"])
    return out


def evaluate(case, ref, cand, expected=None):
    """Verdict for one run from collected artifacts (ref is None when there is no reference). `expected` is
    expected_instrumentation() for the case's sandbox inputs; without it the instrumentation binding fails."""
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
            if cand.get("ok") or ("stdout" in cand and "log" in cand):
                cmp = compare(case, ref, cand)
                v["comparison"] = cmp
                v["output_matches_reference"] = cmp["match"]
                if not cmp["match"]:
                    fail("output differs from the reference: " + ", ".join(
                        k for k in ("stdout_identical_after_normalisation", "exit_code_identical",
                                    "ucc_log_identical_after_normalisation", "written_files_identical") if not cmp[k]))
            else:
                fail("no comparable translated output (stdout or UCC.log missing)")
    # 4. milestone evidence
    if rep is None:
        v["evidence"] = []
        v["milestone_evidence_valid"] = False
        fail("milestone evidence: no valid runtime report from this run")
    else:
        try:
            groups = [ev_instrumentation(Timeline(rep), expected)] if expected else \
                [{"group": "instrumentation_binding", "ok": False,
                  "checks": [{"check": "expected instrumentation resolved", "ok": False, "detail": "not available"}]}]
            groups += PROFILES[case.profile](case, rep)
            if ref is not None and ref.get("trace") is not None:
                cc = original_cross_check(case, ref["trace"], expected) if expected else []
                if case.profile == "engine_commandlet":
                    cc += engine_cross_check(ref["trace"], rep)
                groups.append({"group": "original_trace_cross_check", "ok": bool(cc) and all(i["ok"] for i in cc),
                               "checks": cc})
            if case.cxx_exceptions and ref is not None:
                if ref.get("trace") is not None:
                    groups.append(ev_cxx_original(rep, ref))
                else:
                    groups.append({"group": "cxx_exception_path_matches_original", "ok": False, "checks": [
                        {"check": "traced original available for the exception comparison", "ok": False,
                         "detail": "the reference was not traced"}]})
        except Exception as exc:  # noqa: BLE001 - an unexpected report shape is a failed run, never a crash
            groups = [{"group": "evidence_evaluation", "ok": False,
                       "checks": [{"check": "evaluate the evidence profile", "ok": False, "detail": repr(exc)[:300]}]}]
        v["evidence"] = groups
        v["milestone_evidence_valid"] = all(g["ok"] for g in groups)
        for g in groups:
            for i in g["checks"]:
                if not i["ok"]:
                    fail(f"milestone evidence [{g['group']}]: {i['check']} ({i['detail']})")
    # 5. identical inputs and guest command line for both runs; translated code lifted from exactly these inputs
    cin = (cand.get("meta") or {}).get("inputs")
    if ref is not None and ref["ok"]:
        if (ref.get("meta") or {}).get("inputs") != cin:
            fail("the original and translated runs used different input files")
        if (ref.get("meta") or {}).get("sandbox") != (cand.get("meta") or {}).get("sandbox"):
            fail("the original and translated runs used different sandbox paths")
        if ref.get("command_line") != cand.get("command_line"):
            fail(f"different guest command lines: original {ref.get('command_line')!r}, "
                 f"translated {cand.get('command_line')!r}")
    if rep is not None:
        mods = {m.get("name"): m.get("sha256") for m in rep["modules"]}
        for f in sorted(set(mods) | {"UCC.exe", "Core.dll"}):   # every module the run mapped (Engine, GlmLib, ...)
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
    if not math.isfinite(a.timeout) or not MIN_TIMEOUT <= a.timeout <= MAX_TIMEOUT:
        raise UsageError(f"--timeout must be finite and between {MIN_TIMEOUT:g} and {MAX_TIMEOUT:g} s, got {a.timeout}")
    if a.trace and a.no_original:
        raise UsageError("--trace traces the original; it cannot be combined with --no-original")
    if extra is not None:
        if len(a.cases) != 1:
            raise UsageError("commandlet arguments after -- are only accepted with a single case")
        if tuple(extra) != CASES[a.cases[0]].args:
            raise UsageError(f"arguments {extra} differ from the registered arguments of {a.cases[0]}: "
                             f"{list(CASES[a.cases[0]].args)}")
    return a


def new_invocation_dir(root=None):
    inv = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    d = os.path.join(root or RUNS_ROOT, inv)
    os.makedirs(d)          # exclusive: a result location is never reused
    return inv, d


def run_one(case, rundir, timeout, trace, no_original, candidate_prefix, expected_cache):
    """Execute and judge one run; a harness failure becomes a FAIL verdict with the reason."""
    ref = cand = None
    try:
        if not no_original:
            ref = collect_original(execute_original(case, os.path.join(rundir, "original"), timeout, trace))
        cand = collect_candidate(execute_candidate(case, os.path.join(rundir, "xrt"), timeout, candidate_prefix))
        if "expected" not in expected_cache:
            expected_cache["expected"] = expected_instrumentation(os.path.join(SANDBOX_ROOT, case.name, "System"))
        v = evaluate(case, ref, cand, expected_cache["expected"])
        v["harness_error"] = None
    except Exception as exc:  # noqa: BLE001 - recorded as a failed run
        v = {"verdict": "FAIL", "harness_error": f"{type(exc).__name__}: {exc}",
             "failures": [f"harness error: {type(exc).__name__}: {exc}"], "traceback": traceback.format_exc()[-3000:],
             "candidate_execution_completed": False, "output_matches_reference": None if no_original else False,
             "expected_result": False, "milestone_evidence_valid": False, "evidence": []}
    return ref, cand, v


def run_invocation(case_names, repeat, timeout, trace=False, no_original=False, candidate_prefix=None, echo=print):
    if not case_names or not 1 <= repeat <= MAX_REPEAT or not (math.isfinite(timeout) and MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
        raise UsageError("invalid case list, repeat count or timeout")
    for n in case_names:
        if n not in CASES:
            raise UsageError(f"unknown case {n!r}")
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
        "tracer": file_identity(TRACER) if os.path.isfile(TRACER) else None,
        "tracer_source": file_identity(os.path.join(WS, "experiments", "xrt", "tracer", "uctrace.c")),
        "eh_points_tool": file_identity(os.path.join(WS, "tools", "xrt", "eh_points.py")),
        "python": sys.version.split()[0], "host": platform.platform(),
    }
    summaries = {}
    expected_cache = {}
    for name in case_names:
        case = CASES[name]
        case_trace = bool(trace or case.cxx_exceptions) and not no_original
        if case_trace and candidate_prefix is None and not os.path.isfile(TRACER):
            raise UsageError(f"{name} needs the traced original (exception evidence); {rel(TRACER)} is not built")
        s = {"runner_schema": 4, "invocation_id": inv, "invocation_dir": rel(invdir), "case": name, "args": list(case.args),
             "expect": {"exit_code": case.expect.exit_code, "negative": case.expect.negative,
                        "stdout_contains": list(case.expect.stdout_contains),
                        "stdout_excludes": list(case.expect.stdout_excludes)},
             "profile": case.profile, "natives": list(case.natives), "repeat": repeat, "timeout_s": timeout,
             "trace": case_trace, "trace_forced": case_trace and not trace,
             "reference": "none" if no_original else "fresh-original", "identity": identity, "runs": []}
        for k in range(repeat):
            rundir = os.path.join(invdir, name, f"run{k}")
            ref, cand, v = run_one(case, rundir, timeout, case_trace, no_original, candidate_prefix, expected_cache)
            entry = {"run": k, "dir": rel(rundir), "verdict": v["verdict"]}
            if cand is not None:
                entry["candidate"] = {"exit_code": cand.get("exit_code"), "seconds": (cand.get("meta") or {}).get("seconds"),
                                      "stdout_sha256": sha256_bytes(cand["stdout"]) if "stdout" in cand else None,
                                      "command_line": cand.get("command_line"), "inputs": (cand.get("meta") or {}).get("inputs"),
                                      "written": sorted((cand.get("meta") or {}).get("written") or {})}
            if ref is not None:
                entry["original"] = {"tool": ref.get("tool"), "exit_code": ref.get("exit_code"),
                                     "seconds": (ref.get("meta") or {}).get("seconds"),
                                     "stdout_sha256": sha256_bytes(ref["stdout"]) if "stdout" in ref else None,
                                     "command_line": ref.get("command_line"),
                                     "written": sorted((ref.get("meta") or {}).get("written") or {})}
            entry.update(v)
            s["runs"].append(entry)
            echo(f"[{name} run {k}] {v['verdict']}: executed={v['candidate_execution_completed']} "
                 f"matches_reference={v['output_matches_reference']} expected_result={v['expected_result']} "
                 f"evidence={v['milestone_evidence_valid']} (translated exit {cand.get('exit_code') if cand else None}"
                 + (f", original exit {ref.get('exit_code')} via {ref.get('tool')})" if ref is not None else ", no reference)"))
            for f in v["failures"][:8]:
                echo(f"    - {f}")
            if len(v["failures"]) > 8:
                echo(f"    ... {len(v['failures']) - 8} more (see the summary)")
        counts = {x: sum(1 for r in s["runs"] if r["verdict"] == x) for x in ("PASS", "FAIL", "UNVERIFIED")}
        s["counts"] = counts
        s["harness_errors"] = sum(1 for r in s["runs"] if r.get("harness_error"))
        s["verdict"] = "FAIL" if counts["FAIL"] or not s["runs"] else "UNVERIFIED" if counts["UNVERIFIED"] else "PASS"
        summaries[name] = s
        with open(os.path.join(invdir, f"{name}.summary.json"), "w", newline="\n") as f:
            json.dump(s, f, indent=1)
    verdicts = [s["verdict"] for s in summaries.values()]
    overall = {"invocation_id": inv, "verdict": "FAIL" if "FAIL" in verdicts else "UNVERIFIED" if "UNVERIFIED" in verdicts else "PASS",
               "harness_errors": sum(s["harness_errors"] for s in summaries.values()), "repeat": repeat,
               "cases": {n: {"verdict": s["verdict"], "counts": s["counts"]} for n, s in summaries.items()}}
    with open(os.path.join(invdir, "summary.json"), "w", newline="\n") as f:
        json.dump(overall, f, indent=1)
    return inv, invdir, summaries, overall


def reevaluate(invdir, echo=print):
    """Re-judge the raw artifacts of an earlier invocation with the current evaluation code. Nothing is executed;
    every run is judged only on its own artifacts, the reference is labelled 'preserved-original' and the verdicts
    REEVALUATED_* (never a fresh PASS). Writes <invdir>/<case>.reevaluated.json."""
    overall = load_json(os.path.join(invdir, "summary.json"))
    names = sorted(overall.get("cases") or {})
    files = sorted(f[:-len(".summary.json")] for f in os.listdir(invdir) if f.endswith(".summary.json"))
    if not names or names != files:
        raise UsageError(f"{invdir}: case summaries {files} do not match the invocation's cases {names}")
    out = {}
    for name in names:
        s = load_json(os.path.join(invdir, f"{name}.summary.json"))
        if name not in CASES or s.get("case") != name:
            raise UsageError(f"{name}: not a registered case or a mismatched summary")
        case = CASES[name]
        if list(case.args) != s.get("args"):
            raise UsageError(f"{name}: registered arguments changed since that invocation")
        if (s.get("identity") or {}).get("candidate", {}).get("substitute"):
            raise UsageError(f"{name}: that invocation used a substitute candidate (runner self-test)")
        runs = s.get("runs") or []
        if not _is_int(s.get("repeat")) or s["repeat"] < 1 or len(runs) != s["repeat"]:
            raise UsageError(f"{name}: {len(runs)} runs recorded, {s.get('repeat')} requested")
        expected = None
        results = []
        for k, r in enumerate(runs):
            rundir = os.path.join(invdir, name, f"run{k}")
            if r.get("dir") != rel(rundir):
                raise UsageError(f"{name} run {k}: recorded directory {r.get('dir')!r} is not {rel(rundir)!r}")
            if expected is None:
                expected = expected_instrumentation(os.path.join(SANDBOX_ROOT, name, "System")) \
                    if os.path.isdir(os.path.join(SANDBOX_ROOT, name, "System")) else None
            ref = None if s.get("reference") == "none" else collect_original(os.path.join(rundir, "original"))
            v = evaluate(case, ref, collect_candidate(os.path.join(rundir, "xrt")), expected)
            if ref is not None:
                v["reference"] = "preserved-original"
            v["verdict"] = "REEVALUATED_" + v["verdict"]
            results.append({"run": k, "dir": r["dir"], "original_verdict": r.get("verdict")} | v)
            echo(f"[{name} run {k}] {r.get('verdict')} -> {v['verdict']}")
            for f in v["failures"][:8]:
                echo(f"    - {f}")
        counts = {x: sum(1 for r in results if r["verdict"] == "REEVALUATED_" + x) for x in ("PASS", "FAIL", "UNVERIFIED")}
        res = {"reevaluated_invocation": s.get("invocation_id"), "case": name, "runner": file_identity(os.path.abspath(__file__)),
               "counts": counts, "verdict": "REEVALUATED_" + ("FAIL" if counts["FAIL"] or not results
                                                             else "UNVERIFIED" if counts["UNVERIFIED"] else "PASS"),
               "runs": results}
        with open(os.path.join(invdir, f"{name}.reevaluated.json"), "w", newline="\n") as f:
            json.dump(res, f, indent=1)
        out[name] = res
    return out


def public_summary(s):
    """The per-case summary kept in git: everything except the full per-check evidence (kept in the raw dir)."""
    out = dict(s)
    out["runs"] = []
    for r in s["runs"]:
        r2 = {k: v for k, v in r.items() if k not in ("evidence", "traceback")}
        r2["evidence"] = [{"group": g["group"], "ok": g["ok"], "checks_passed": sum(1 for i in g["checks"] if i["ok"]),
                           "failed_checks": [i for i in g["checks"] if not i["ok"]]} for g in r.get("evidence", [])]
        out["runs"].append(r2)
    return out


def publish(summaries, trace):
    """compare/<case>.json (direct references) or compare/<case>.traced.json (traced references): the latest
    summary of each mode, so a traced cross-check run never replaces the latest repeated acceptance run."""
    os.makedirs(COMPARE_DIR, exist_ok=True)
    for n, s in summaries.items():
        traced_name = trace and not CASES[n].cxx_exceptions     # exception cases are always traced
        with open(os.path.join(COMPARE_DIR, f"{n}{'.traced' if traced_name else ''}.json"), "w", newline="\n") as f:
            json.dump(public_summary(s), f, indent=1)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--reevaluate"]:
        d = os.path.abspath(argv[1]) if len(argv) == 2 else ""
        if not d or not inside(d, RUNS_ROOT) or not os.path.isdir(d):
            print(f"run_xrt.py: --reevaluate needs one invocation directory below {rel(RUNS_ROOT)}", file=sys.stderr)
            return 2
        try:
            res = reevaluate(d)
        except (UsageError, OSError, ValueError, KeyError) as exc:
            print(f"run_xrt.py: cannot re-evaluate {rel(d)}: {exc}", file=sys.stderr)
            return 2
        failed = any(r["verdict"] != "REEVALUATED_PASS" for r in res.values())
        print(f"re-evaluated {rel(d)} (preserved artifacts, not a fresh result): "
              + "; ".join(f"{n} {r['verdict']} {r['counts']}" for n, r in res.items()))
        return 1 if failed else EXIT_REEVALUATED
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
    publish(summaries, a.trace)
    print(f"invocation {inv}: {overall['verdict']}; "
          + "; ".join(f"{n} {c['verdict']} {c['counts']}" for n, c in overall["cases"].items()))
    if overall["harness_errors"]:
        print(f"harness errors: {overall['harness_errors']} (see the summaries)")
    print(f"raw evidence: {rel(invdir)}")
    return EXIT_HARNESS if overall["harness_errors"] else EXIT_STATUS[overall["verdict"]]


def export_rvas(path):
    """{export name: rva}, parsed from an in-memory copy (a memory-mapped file would keep the sandbox locked)."""
    import pefile
    pe = pefile.PE(data=read_bytes(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    exp = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    out = {e.name.decode(): e.address for e in exp.symbols if e.name} if exp else {}
    pe.close()
    return out


if __name__ == "__main__":
    sys.exit(main())
