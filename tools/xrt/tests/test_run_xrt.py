"""Regression tests for the acceptance runner (tools/xrt/run_xrt.py).

  python -I -m unittest discover -s tools/xrt/tests -p "test_run_xrt.py" -v

Three layers:
  Logic       argument validation, normalisation, expectations, artifact collection and tracer validation on
              synthetic artifacts (no proprietary content; always run).
  Real data   mutations of the newest real PASS run of hellofull / arraytest found under
              experiments/xrt/results/raw/runs (git-ignored); skipped when there is none.
  End to end  XRT_E2E=1: the real runner against fresh original references, with the translated run sabotaged by
              tests/tamper_candidate.py (each test executes the original and the translated UCC; minutes in total).
"""
import copy
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import run_xrt as R  # noqa: E402
from cases import CASES, Case, Expect  # noqa: E402

E2E = os.environ.get("XRT_E2E") == "1"
# scratch copies of real artifacts stay inside the workspace's git-ignored build tree
TMP_ROOT = os.path.join(R.WS, "experiments", "xrt", "build", "test_tmp")


def mkdtemp():
    os.makedirs(TMP_ROOT, exist_ok=True)
    return tempfile.mkdtemp(dir=TMP_ROOT)


# ------------------------------------------------------------------------------------------------ helpers
def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"newline": "\n"})) as f:
        f.write(data)


def synth_original(d, run_id="r1", exit_code=0, stdout=b"hello\r\n", log="Log: x\n", trace=None, tracer_exit=0):
    meta = {"run_id": run_id, "inputs": {"UCC.exe": "a", "Core.dll": "b"}, "trace": trace is not None}
    if trace is None:
        meta["process_exit_code"] = exit_code
    else:
        meta["tracer_exit_code"] = tracer_exit
        if trace != "missing":
            write(os.path.join(d, "trace.json"), json.dumps(trace))
    write(os.path.join(d, "meta.json"), json.dumps(meta))
    write(os.path.join(d, "stdout.bin"), stdout)
    if log is not None:
        write(os.path.join(d, "UCC.log"), log.encode("latin-1"))
    return d


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(obj, path):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f)


def rbytes(path):
    with open(path, "rb") as f:
        return f.read()


def wbytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def newest_real_run(case):
    """(invocation summary, run dir) of the newest PASSing real run of `case`, or None."""
    for s in sorted(glob.glob(os.path.join(R.RUNS_ROOT, "*", f"{case}.summary.json")), reverse=True):
        d = load(s)
        if d.get("identity", {}).get("candidate", {}).get("substitute"):
            continue
        for r in d["runs"]:
            if r["verdict"] == "PASS":
                return d, os.path.join(R.WS, r["dir"])
    return None


# ------------------------------------------------------------------------------------------------ logic
class Arguments(unittest.TestCase):
    def bad(self, *argv):
        with self.assertRaises(R.UsageError):
            R.parse_args(list(argv))

    def test_repeat_must_be_positive_integer(self):
        for v in ("0", "-1", "1.5", "x", "", " ", "101", "1e2"):
            self.bad("hellofull", "--repeat", v)
        self.assertEqual(R.parse_args(["hellofull", "--repeat", "3"]).repeat, 3)

    def test_timeout_must_be_positive_finite(self):
        for v in ("0", "-5", "nan", "inf", "-inf", "x", "3601"):
            self.bad("hellofull", "--timeout", v)
        self.assertEqual(R.parse_args(["hellofull", "--timeout", "2.5"]).timeout, 2.5)

    def test_case_ids_constrained_to_registry(self):
        for c in ("../hellofull", "..", "hellofull/..", "C:\\x", "HelloFull", "hellofull ", "sandbox", "x" * 50, ""):
            self.bad(c)
        self.bad()                        # no case
        self.bad("hellofull", "hellofull")

    def test_args_after_dashdash_must_equal_registered(self):
        self.bad("hellofull", "--", "Core.HelloWorldCommandlet", "a", "b")
        self.bad("hellofull", "simple", "--", "Core.SimpleCommandlet")
        a = R.parse_args(["hellofull", "--", "Core.HelloWorldCommandlet", "a", "b", "c"])
        self.assertEqual(a.cases, ["hellofull"])

    def test_trace_requires_reference(self):
        self.bad("hellofull", "--trace", "--no-original")

    def test_cli_exit_status_2_on_usage_errors_and_nothing_created(self):
        before = set(os.listdir(R.RUNS_ROOT)) if os.path.isdir(R.RUNS_ROOT) else set()
        for argv in (["hellofull", "--repeat", "0"], ["../x"], ["hellofull", "--timeout", "nan"]):
            self.assertEqual(R.main(argv), 2)
        after = set(os.listdir(R.RUNS_ROOT)) if os.path.isdir(R.RUNS_ROOT) else set()
        self.assertEqual(before, after, "a rejected invocation must not create a result location")

    def test_run_invocation_rejects_zero_runs(self):
        with self.assertRaises(R.UsageError):
            R.run_invocation(["hellofull"], 0, 10.0)

    def test_sandbox_path_constrained(self):
        with self.assertRaises(R.UsageError):
            R.fresh_sandbox("../escape")

    def test_registry_negative_rule(self):
        with self.assertRaises(ValueError):
            Expect(exit_code=1)                      # nonzero only for an explicit negative test
        Expect(exit_code=1, negative=True)
        with self.assertRaises(ValueError):
            Case("Bad Name", (), Expect(), "core_commandlet")


class Normalisation(unittest.TestCase):
    W = b"ArrayTest Transient.ArrayTest0 (Function Core.ArrayTest.NestedTests:000F) 0.661 Attempt to assign variable through None (line 0)\r\n"

    def test_elapsed_seconds_only(self):
        self.assertEqual(R.normalise_stdout(self.W), R.normalise_stdout(self.W.replace(b"0.661", b"0.999")))
        self.assertNotEqual(R.normalise_stdout(self.W), R.normalise_stdout(self.W.replace(b":000F", b":0010")))
        self.assertNotEqual(R.normalise_stdout(self.W), R.normalise_stdout(self.W.replace(b"through None", b"through Nothing")))
        self.assertNotEqual(R.normalise_stdout(self.W), R.normalise_stdout(self.W.replace(b"(line 0)", b"(line 1)")))
        other = b"Foo (Function A.B:0001) 0.500 Something else\r\n"
        self.assertNotEqual(R.normalise_stdout(other), R.normalise_stdout(other.replace(b"0.500", b"0.600")))

    def test_log_rules(self):
        a = "Log: Log file open, 10/22/26 10:00:00\nInit: CPU Speed=3000.1 MHz\nLog: 12.5ms Purging garbage\nInit: CPU Features: CMOV FPU MMX SSE\nX\n"
        b = "Log: Log file open, 10/23/26 11:11:11\nInit: CPU Speed=2999.9 MHz\nLog: 99ms Purging garbage\nInit: CPU Features: CMOV FPU\nX\n"
        self.assertEqual(R.normalise_log(a, True), R.normalise_log(b, True))
        self.assertNotEqual(R.normalise_log(a, False), R.normalise_log(b, False))     # -NOMMX -NOSSE: must match
        self.assertNotEqual(R.normalise_log(a, True), R.normalise_log(b.replace("X", "Y"), True))
        self.assertTrue(R.policy_line_differs(["Core.HelloWorldCommandlet"]))
        self.assertFalse(R.policy_line_differs(["x", "-nommx", "-NOSSE"]))


class Expectations(unittest.TestCase):
    def test_normal_case_requires_exit_0(self):
        e = CASES["hellofull"].expect
        self.assertTrue(R.check_expectation(e, 3, b"anything"))
        out = ("ucc.exe: UnrealOS execution environment\r\nExecuting Class Core.HelloWorldCommandlet\r\nHello, world!\r\n"
               "Command line parameters=a b c\r\n").encode()
        self.assertEqual(R.check_expectation(e, 0, out), [])
        self.assertTrue(R.check_expectation(e, 0, out.replace(b"Hello, world!", b"Hello, world?")))
        self.assertTrue(R.check_expectation(e, 0, out + b"Commandlet X not found\r\n"))


def candidate_dir(base, run_id="c1", report=None, stdout=b"hello\r\n", log="Log: x\n", xrtlog=True, exit_code=0):
    d = os.path.join(base, "xrt")
    write(os.path.join(d, "meta.json"), json.dumps({"run_id": run_id, "inputs": {"UCC.exe": "a", "Core.dll": "b"},
                                                    "process_exit_code": exit_code}))
    write(os.path.join(d, "stdout.bin"), stdout)
    write(os.path.join(d, "stderr.txt"), b"")
    if log is not None:
        write(os.path.join(d, "UCC.log"), log.encode("latin-1"))
    if report is not None:
        write(os.path.join(d, "report.json"), json.dumps(report))
    if xrtlog:
        write(os.path.join(d, "xrt.log"), f"[t-1] run id: {run_id}\n")
    return d


MINIMAL_REPORT = {"schema": 2, "run_id": "c1", "outcome": "exited", "exit_code": 0, "events": [], "threads": [],
                  "modules": [{"name": "UCC.exe", "sha256": "a"}, {"name": "Core.dll", "sha256": "b"}]}


class Collection(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        R.PROFILES["test_minimal"] = lambda case, rep: [{"group": "g", "ok": True, "checks": [{"check": "c", "ok": True, "detail": ""}]}]
        self.case = Case("synth", ("X",), Expect(0, ("hello",)), "test_minimal")

    def tearDown(self):
        shutil.rmtree(self.tmp)
        del R.PROFILES["test_minimal"]

    def test_valid_synthetic_pair_passes(self):
        ref = R.collect_original(synth_original(os.path.join(self.tmp, "o")))
        cand = R.collect_candidate(candidate_dir(self.tmp, report=MINIMAL_REPORT))
        self.assertEqual(R.evaluate(self.case, ref, cand)["verdict"], "PASS")

    def test_missing_report(self):
        cand = R.collect_candidate(candidate_dir(self.tmp, report=None))
        v = R.evaluate(self.case, R.collect_original(synth_original(os.path.join(self.tmp, "o"))), cand)
        self.assertEqual(v["verdict"], "FAIL")
        self.assertFalse(v["candidate_execution_completed"])
        self.assertFalse(v["milestone_evidence_valid"])

    def test_stale_report_and_log(self):
        rep = dict(MINIMAL_REPORT, run_id="old")
        v = R.evaluate(self.case, None, R.collect_candidate(candidate_dir(self.tmp, report=rep)))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertTrue(any("stale" in f for f in v["failures"]))
        shutil.rmtree(self.tmp)
        cand = R.collect_candidate(candidate_dir(self.tmp, report=MINIMAL_REPORT, xrtlog=False))
        self.assertEqual(R.evaluate(self.case, None, cand)["verdict"], "FAIL")

    def test_malformed_report(self):
        d = candidate_dir(self.tmp, report=MINIMAL_REPORT)
        write(os.path.join(d, "report.json"), '{"schema": 2, "run_id": "c1", "events": [')
        self.assertEqual(R.evaluate(self.case, None, R.collect_candidate(d))["verdict"], "FAIL")

    def test_report_exit_code_must_match_process(self):
        cand = R.collect_candidate(candidate_dir(self.tmp, report=dict(MINIMAL_REPORT, exit_code=1)))
        self.assertEqual(R.evaluate(self.case, None, cand)["verdict"], "FAIL")

    def test_no_reference_is_unverified_never_match(self):
        v = R.evaluate(self.case, None, R.collect_candidate(candidate_dir(self.tmp, report=MINIMAL_REPORT)))
        self.assertEqual(v["verdict"], "UNVERIFIED")
        self.assertIsNone(v["output_matches_reference"])

    def test_missing_current_ucc_log(self):
        old = os.path.join(self.tmp, "old_invocation", "xrt")
        write(os.path.join(old, "UCC.log"), b"Log: x\n")           # an old, valid-looking artifact elsewhere
        cand = R.collect_candidate(candidate_dir(os.path.join(self.tmp, "new"), report=MINIMAL_REPORT, log=None))
        v = R.evaluate(self.case, R.collect_original(synth_original(os.path.join(self.tmp, "o"))), cand)
        self.assertEqual(v["verdict"], "FAIL")
        self.assertTrue(any("UCC.log missing" in f for f in v["failures"]))

    def test_equal_nonzero_exit_fails_normal_case_but_passes_negative(self):
        rep = dict(MINIMAL_REPORT, exit_code=3)
        ref = R.collect_original(synth_original(os.path.join(self.tmp, "o"), exit_code=3))
        cand = R.collect_candidate(candidate_dir(self.tmp, report=rep, exit_code=3))
        v = R.evaluate(self.case, ref, cand)
        self.assertEqual(v["verdict"], "FAIL")
        self.assertFalse(v["expected_result"])
        self.assertTrue(any("reference does not produce" in f for f in v["failures"]))
        neg = Case("synthneg", ("X",), Expect(3, ("hello",), negative=True), "test_minimal")
        self.assertEqual(R.evaluate(neg, ref, cand)["verdict"], "PASS")

    def test_tracer_failure_distinguished_from_guest_exit(self):
        good = {"run_id": "r1", "complete": True, "exit_code": 0, "modules": []}
        o = R.collect_original(synth_original(os.path.join(self.tmp, "a"), trace=good))
        self.assertTrue(o["ok"])
        # the guest exits 5, the tracer worked: a guest result, not a tool failure
        o = R.collect_original(synth_original(os.path.join(self.tmp, "b"), trace=dict(good, exit_code=5)))
        self.assertTrue(o["ok"])
        self.assertEqual(o["exit_code"], 5)
        v = R.evaluate(self.case, o, R.collect_candidate(candidate_dir(os.path.join(self.tmp, "bc"), report=MINIMAL_REPORT)))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertTrue(any("reference does not produce" in f for f in v["failures"]))
        self.assertFalse(any("tracer failure" in f for f in v["failures"]))
        for name, kw in (("tool_exit", {"trace": good, "tracer_exit": 4}), ("stale", {"trace": dict(good, run_id="x")}),
                         ("incomplete", {"trace": dict(good, complete=False)}), ("missing", {"trace": "missing"}),
                         ("no_code", {"trace": {"run_id": "r1", "complete": True}})):
            o = R.collect_original(synth_original(os.path.join(self.tmp, name), **kw))
            self.assertFalse(o["ok"], name)
            self.assertTrue(any("tracer failure" in e for e in o["errors"]), (name, o["errors"]))

    def test_reference_without_log_is_invalid(self):
        o = R.collect_original(synth_original(os.path.join(self.tmp, "o"), log=None))
        v = R.evaluate(self.case, o, R.collect_candidate(candidate_dir(self.tmp, report=MINIMAL_REPORT)))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertFalse(v["output_matches_reference"])

    def test_input_identity_mismatch(self):
        rep = dict(MINIMAL_REPORT, modules=[{"name": "UCC.exe", "sha256": "a"}, {"name": "Core.dll", "sha256": "OTHER"}])
        v = R.evaluate(self.case, None, R.collect_candidate(candidate_dir(self.tmp, report=rep)))
        self.assertEqual(v["verdict"], "FAIL")


# ------------------------------------------------------------------------------------------------ real data
class RealArtifactMutations(unittest.TestCase):
    """Mutations of the newest real PASS run; evaluate() must reject them (or accept documented differences)."""

    def load(self, case):
        got = newest_real_run(case)
        if got is None:
            self.skipTest(f"no real PASS run of {case} under {R.RUNS_ROOT}")
        _, rundir = got
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copytree(rundir, os.path.join(self.tmp, "run"))
        self.o = os.path.join(self.tmp, "run", "original")
        self.x = os.path.join(self.tmp, "run", "xrt")
        self.case = CASES[case]

    def verdict(self):
        ref = R.collect_original(self.o)
        exports = R.export_rvas(os.path.join(R.SANDBOX_ROOT, self.case.name, "System", "Core.dll")) \
            if ref.get("trace") is not None else {}
        return R.evaluate(self.case, ref, R.collect_candidate(self.x), exports)

    def edit(self, fn):
        p = os.path.join(self.x, "report.json")
        rep = load(p)
        fn(rep)
        dump(rep, p)

    def test_unchanged_copy_passes(self):
        self.load("hellofull")
        self.assertEqual(self.verdict()["verdict"], "PASS")

    def test_each_milestone_event_is_required(self):
        """Removing any single process/thread/mark/watch event the profile names must fail the run."""
        self.load("hellofull")
        rep = load(os.path.join(self.x, "report.json"))
        kinds = {"dll_attach_returned", "exe_entry", "mark", "thread_create", "thread_start", "exit_thread", "thread_end",
                 "watch_initial", "watch_store", "thread_at_exit", "crt_exit", "process_exit", "dll_detach_returned",
                 "process_exit_complete"}
        needed = []
        for i, e in enumerate(rep["events"]):
            if e["kind"] not in kinds:
                continue
            trial = copy.deepcopy(rep)
            del trial["events"][i]
            dump(trial, os.path.join(self.x, "report.json"))
            if R.evaluate(self.case, R.collect_original(self.o), R.collect_candidate(self.x))["verdict"] == "FAIL":
                needed.append((e["kind"], e.get("name")))
        dump(rep, os.path.join(self.x, "report.json"))
        names = {n for k, n in needed if k == "mark"}
        for n in ("UCC main", "appInit", "UObject::StaticInit", "FFileStream::Init", "UObject::StaticLoadClass",
                  "UObject::GetPackageLinker", "UCommandlet::Main", "UObject::ProcessEvent", "UObject::execLog",
                  "FFileStream worker thread entry", "appPreExit", "appExit", "FFileStream::Destroy",
                  "FFileStream::Destroy: shutdown wait finished", "UCC main returned"):
            self.assertIn(n, names, f"removing the first '{n}' mark went unnoticed")
        for k in ("thread_create", "thread_start", "exit_thread", "thread_end", "watch_store", "crt_exit", "process_exit",
                  "dll_detach_returned", "process_exit_complete", "thread_at_exit", "dll_attach_returned", "exe_entry"):
            self.assertIn(k, {k2 for k2, _ in needed}, f"removing the {k} event went unnoticed")

    def test_no_worker(self):
        self.load("hellofull")
        self.edit(lambda r: (r.__setitem__("threads", [t for t in r["threads"] if t["index"] != 1]),
                             r.__setitem__("events", [e for e in r["events"] if e.get("thread") != 1 and e.get("index") != 1])))
        v = self.verdict()
        self.assertEqual(v["verdict"], "FAIL")
        bad = {g["group"] for g in v["evidence"] if not g["ok"]}
        self.assertTrue({"worker_creation_and_execution", "worker_termination_and_wait_completion"} <= bad, bad)

    def test_worker_incomplete(self):
        self.load("hellofull")

        def f(r):
            for t in r["threads"]:
                if t["index"] == 1:
                    t.update(state="running", exit_via="")
            r["events"] = [e for e in r["events"] if not (e["kind"] in ("exit_thread", "thread_end") and e["thread"] == 1)]
        self.edit(f)
        v = self.verdict()
        self.assertEqual(v["verdict"], "FAIL")
        self.assertIn("worker_termination_and_wait_completion", {g["group"] for g in v["evidence"] if not g["ok"]})

    def test_flag_order_and_extra_store(self):
        self.load("hellofull")

        def swap(r):
            st = [e for e in r["events"] if e["kind"] == "watch_store"]
            st[0]["seq"], st[1]["seq"] = st[1]["seq"], st[0]["seq"]
        self.edit(swap)
        self.assertEqual(self.verdict()["verdict"], "FAIL")
        self.load("hellofull")

        def extra(r):
            r["events"].append({"seq": 10 ** 6, "thread": 0, "kind": "watch_store", "name": "FFileStream::Destroyed",
                                "old": 2, "new": 1, "where": "x"})
        self.edit(extra)
        self.assertEqual(self.verdict()["verdict"], "FAIL")

    def test_unattributed_change(self):
        self.load("hellofull")
        self.edit(lambda r: r.__setitem__("watch_unattributed_changes", 1))
        self.assertEqual(self.verdict()["verdict"], "FAIL")

    def test_dropped_events(self):
        self.load("hellofull")
        self.edit(lambda r: r.__setitem__("events_dropped", 5))
        self.assertEqual(self.verdict()["verdict"], "FAIL")

    def test_fatal_outcome(self):
        self.load("hellofull")
        self.edit(lambda r: r.update(outcome="C++ exception thrown", exit_code=76))
        self.assertEqual(self.verdict()["verdict"], "FAIL")

    def test_real_output_alterations(self):
        self.load("hellofull")
        p = os.path.join(self.x, "stdout.bin")
        data = rbytes(p)
        wbytes(p, data.replace(b"Hello, world!", b"Hello, world?"))
        self.assertEqual(self.verdict()["verdict"], "FAIL")
        wbytes(p, data + b"\r\n")
        self.assertEqual(self.verdict()["verdict"], "FAIL")
        wbytes(p, data)
        self.assertEqual(self.verdict()["verdict"], "PASS")

    def test_ucc_log_alterations(self):
        self.load("hellofull")
        p = os.path.join(self.x, "UCC.log")
        text = rbytes(p).decode("latin-1")
        import re
        wbytes(p, re.sub(r"^(Log: Log file open, ).*$", r"\g<1>01/01/99 00:00:00", text, flags=re.M).encode("latin-1"))
        self.assertEqual(self.verdict()["verdict"], "PASS", "the timestamp line is a documented difference")
        wbytes(p, text.replace("Hello, world!", "Hello, world?").encode("latin-1"))
        self.assertEqual(self.verdict()["verdict"], "FAIL")
        lines = text.split("\n")
        wbytes(p, "\n".join(lines[:-3] + lines[-2:]).encode("latin-1"))
        self.assertEqual(self.verdict()["verdict"], "FAIL")

    def test_arraytest_warning_text_offsets_and_timing(self):
        self.load("arraytest")
        p = os.path.join(self.x, "stdout.bin")
        data = rbytes(p)
        self.assertIn(b"Attempt to assign variable through None", data)
        import re
        timing = re.sub(rb"(\(Function [^)]*\)) [0-9]+\.[0-9]{3} ", rb"\1 9.999 ", data)
        self.assertNotEqual(timing, data)
        for altered, want in ((timing, "PASS"),
                              (data.replace(b"through None", b"through Nothing"), "FAIL"),
                              (data.replace(b"NestedTests:000F", b"NestedTests:0010"), "FAIL"),
                              (data.replace(b"RegularTests:0090", b"RegularTests:0091"), "FAIL"),
                              (data.replace(b"out of bounds (5/2)", b"out of bounds (5/3)"), "FAIL")):
            wbytes(p, altered)
            self.assertEqual(self.verdict()["verdict"], want)
        wbytes(p, data)
        lp = os.path.join(self.x, "UCC.log")
        log = rbytes(lp)
        if b"through None" in log:
            wbytes(lp, re.sub(rb"(\(Function [^)]*\)) [0-9]+\.[0-9]{3} ", rb"\1 7.777 ", log))
            self.assertEqual(self.verdict()["verdict"], "PASS")
            wbytes(lp, log.replace(b"NestedTests:000F", b"NestedTests:000E"))
            self.assertEqual(self.verdict()["verdict"], "FAIL")


# ------------------------------------------------------------------------------------------------ end to end
@unittest.skipUnless(E2E, "set XRT_E2E=1 to run end-to-end runner tests (executes the original and translated UCC)")
class EndToEnd(unittest.TestCase):
    TAMPER = [sys.executable, "-I", os.path.join(HERE, "tamper_candidate.py")]

    def run_case(self, case, mode, no_original=False):
        lines = []
        inv, invdir, summaries, overall = R.run_invocation([case], 1, 120.0, no_original=no_original,
                                                            candidate_prefix=self.TAMPER + [mode], echo=lines.append)
        self.addCleanup(lambda: None)
        return summaries[case]["runs"][0], overall, lines

    def expect(self, case, mode, verdict, groups=(), text=None, no_original=False):
        run, overall, lines = self.run_case(case, mode, no_original)
        self.assertEqual(run["verdict"], verdict, "\n".join(lines))
        bad = {g["group"] for g in run.get("evidence", []) if not g["ok"]}
        for g in groups:
            self.assertIn(g, bad, "\n".join(lines))
        if text:
            self.assertTrue(any(text in f for f in run["failures"]), "\n".join(lines))
        return run

    def test_control_unmodified_candidate_passes(self):
        self.expect("hellofull", "none", "PASS")

    def test_report_removed(self):
        r = self.expect("hellofull", "drop_report", "FAIL", text="runtime report missing")
        self.assertFalse(r["milestone_evidence_valid"])
        self.assertFalse(r["candidate_execution_completed"])

    def test_stale_report(self):
        self.expect("hellofull", "stale_report", "FAIL", text="stale or foreign runtime report")

    def test_worker_evidence_removed(self):
        self.expect("hellofull", "drop_worker", "FAIL", ["worker_creation_and_execution", "worker_termination_and_wait_completion"])

    def test_worker_incomplete(self):
        self.expect("hellofull", "worker_incomplete", "FAIL", ["worker_termination_and_wait_completion"])

    def test_flag_acknowledgement_missing(self):
        self.expect("hellofull", "flag_skips_ack", "FAIL", ["shutdown_flag_transition"])

    def test_current_logs_omitted_while_old_artifacts_exist(self):
        # old-runner artifact names and a previous invocation's files exist; neither may be consumed
        old = os.path.join(R.WS, "experiments", "xrt", "results", "raw", "xrt")
        os.makedirs(old, exist_ok=True)
        planted = [os.path.join(old, "hellofull.UCC.log"), os.path.join(old, "hellofull.report.json"),
                   os.path.join(old, "hellofull.xrt.log")]
        for p in planted:
            if not os.path.exists(p):
                write(p, b"stale\n")
                self.addCleanup(os.remove, p)
        self.expect("hellofull", "drop_ucclog", "FAIL", text="UCC.log missing")
        self.expect("hellofull", "drop_xrtlog", "FAIL", text="runtime log missing")

    def test_no_reference_is_unverified(self):
        run = self.expect("hellofull", "none", "UNVERIFIED", no_original=True)
        self.assertIsNone(run["output_matches_reference"])
        self.assertTrue(run["candidate_execution_completed"] and run["expected_result"] and run["milestone_evidence_valid"])
        p = subprocess.run([sys.executable, "-I", os.path.join(R.WS, "tools", "xrt", "run_xrt.py"), "hellofull",
                            "--no-original"], capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertNotIn("PASS", p.stdout.split("invocation")[-1].split(";")[0])

    def test_zero_runs_cli(self):
        p = subprocess.run([sys.executable, "-I", os.path.join(R.WS, "tools", "xrt", "run_xrt.py"), "hellofull",
                            "--repeat", "0"], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("MATCH", p.stdout + p.stderr)

    def test_altered_output(self):
        self.expect("hellofull", "stdout:Hello, world!=>Hello, world?", "FAIL", text="output differs")

    def test_altered_warning_text_and_offset(self):
        self.expect("arraytest", "stdout:through None=>through Nothing", "FAIL", text="output differs")
        self.expect("arraytest", "stdout:NestedTests:000F=>NestedTests:0010", "FAIL", text="output differs")

    def test_documented_timing_differences_accepted(self):
        self.expect("arraytest", r"ucclog:^(Log: Log file open, ).*$=>\g<1>01/01/99 00:00:00", "PASS")
        self.expect("hellofull", r"ucclog:^Init: CPU Speed=.*$=>Init: CPU Speed=1.000000 MHz", "PASS")

    def test_altered_ucc_log_content(self):
        self.expect("hellofull", r"ucclog:^Log: Executing Class (.*)$=>Log: Executing Klass \g<1>", "FAIL",
                    text="output differs")


if __name__ == "__main__":
    unittest.main()
