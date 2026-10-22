"""Regression tests for the acceptance runner (tools/xrt/run_xrt.py).

  python -I -m unittest discover -s tools/xrt/tests -p "test_run_xrt.py" -v

Layers:
  Logic       always run, no proprietary content: argument validation, normalisation, expectations, artifact
              collection, tracer validation, report schema validation, and the REAL evidence profiles applied to
              synthetic event timelines built from the documented event schema (plus mutations of them).
  Real data   mutations of the newest real PASS run (runner schema 3, untraced and traced variants) under
              experiments/xrt/results/raw/runs (git-ignored). Skipped when there is none - unless XRT_FULL=1,
              which turns a missing layer into a failure.
  End to end  XRT_E2E=1: the real runner against fresh original references, with the translated run sabotaged by
              tamper_candidate.py and the tracer replaced by fake_tracer.py (minutes in total).
"""
import copy
import glob
import json
import os
import re
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
FULL = os.environ.get("XRT_FULL") == "1"
TMP_ROOT = os.path.join(R.WS, "experiments", "xrt", "build", "test_tmp")   # git-ignored


def mkdtemp():
    os.makedirs(TMP_ROOT, exist_ok=True)
    return tempfile.mkdtemp(dir=TMP_ROOT)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(obj, path):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f)


def rbytes(path):
    with open(path, "rb") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ synthetic data
MARK_NAMES = {(m, e["name"]) for m, cfg in load(R.MARKS).items() if m != "comment" for e in cfg.get("marks", [])}
SYN_MARKS = {k: 0x10200000 + 16 * i for i, k in enumerate(sorted(MARK_NAMES))}
SYN_WATCH = {("Core.dll", "FFileStream::Destroyed"): 0x101edbe0}
SYN_DIGEST = "d" * 64
SYN_EXPECTED = (SYN_MARKS, SYN_WATCH, SYN_DIGEST)
HELLO_OUT = (b"=======================================\r\nucc.exe: UnrealOS execution environment\r\n"
             b"=======================================\r\n\r\nExecuting Class Core.HelloWorldCommandlet\r\n"
             b"Hello, world!\r\nCommand line parameters=a b c\r\n")
CMDLINE = r"E:\x\sandbox_cmp\hellofull\System\UCC.exe Core.HelloWorldCommandlet a b c"


def synth_report(case, run_id="c1", exit_code=0):
    """A complete, valid schema-2 report for `case` (core_commandlet or core_error), built from the event schema."""
    ev = []

    def add(kind, thread=0, **kw):
        ev.append(dict(seq=len(ev) + 1, thread=thread, kind=kind, **kw))

    def mark(name, thread=0, top="0x10100100", module="Core.dll", **kw):
        add("mark", thread, name=name, module=module, va=f"0x{SYN_MARKS[(module, name)]:08x}", occurrence=1,
            stack_top=top, **kw)
    UCC = "0x00407100"
    add("watch_initial", -1, name="FFileStream::Destroyed", addr="0x101edbe0", value=0)
    add("dll_attach", module="Core.dll")
    add("dll_attach_returned", module="Core.dll", result=1)
    add("exe_entry", module="UCC.exe")
    mark("UCC main", module="UCC.exe", top="0x00407cc8")
    mark("appInit", top=UCC)
    mark("UObject::StaticInit")
    mark("FFileStream::Init")
    add("thread_create", index=1, entry=R.WORKER_ENTRY, param="0x00000000")
    add("thread_start", 1, index=1, entry=R.WORKER_ENTRY)
    mark("FFileStream worker thread entry", 1, top="0x0033fff0")
    mark("UObject::StaticLoadClass", top=UCC)
    if case.profile == "core_commandlet":
        mark("UObject::StaticLoadObject")
        mark("UObject::GetPackageLinker")
        add("file_open", path="..\\System\\Core.u", resolved="<sandbox>\\System\\Core.u", access="0x80000000",
            disposition=3, ok=True)
        mark("UObject::StaticConstructObject", top=UCC)
        mark("UCommandlet::Main", top=UCC)
        mark("UCommandlet::eventMain")
        mark("UObject::FindFunctionChecked")
        mark("UObject::ProcessEvent")
        mark("UObject::ProcessInternal")
        for n in case.natives:
            mark(n)
    mark("appPreExit", top=UCC)
    mark("UObject::StaticExit")
    mark("appExit", top=UCC)
    mark("FFileStream::Destroy")
    add("watch_store", name="FFileStream::Destroyed", addr="0x101edbe0", old=0, new=1, site="0x1013dadb",
        where="1013dadb (Core.dll+3dadb, in f_1013dab0+2b ?Destroy@FFileStream@@SAXXZ)")
    add("watch_store", 1, name="FFileStream::Destroyed", addr="0x101edbe0", old=1, new=2, site="0x1015a5fd",
        where="1015a5fd (Core.dll+5a5fd, in f_1015a520+dd)")
    add("exit_thread", 1, code=0)
    add("thread_end", 1, index=1, code=0, via="ExitThread")
    mark("FFileStream::Destroy: shutdown wait finished")
    mark("UCC main returned", module="UCC.exe", top="0x00000005", captured=exit_code)
    add("crt_exit", code=exit_code, onexit_handlers=2)
    add("process_exit", code=exit_code)
    add("thread_at_exit", index=1, state="exited")
    add("dll_detach", module="Core.dll")
    add("dll_detach_returned", module="Core.dll", result=1)
    add("process_exit_complete", code=exit_code)
    counts = {}
    for e in ev:
        if e["kind"] == "mark":
            counts[(e["module"], e["name"])] = counts.get((e["module"], e["name"]), 0) + 1
    return {"schema": 2, "run_id": run_id, "exit_code": exit_code, "outcome": "exited", "guest_command_line": CMDLINE,
            "modules": [{"name": "UCC.exe", "sha256": "a", "marks_sha256": SYN_DIGEST},
                        {"name": "Core.dll", "sha256": "b", "marks_sha256": SYN_DIGEST}],
            "threads": [{"index": 0, "state": "running", "exit_via": "", "exit_code": 0},
                        {"index": 1, "state": "exited", "exit_via": "ExitThread", "exit_code": 0}],
            "marks": [{"module": m, "va": f"0x{va:08x}", "name": n, "count": counts.get((m, n), 0)}
                      for (m, n), va in sorted(SYN_MARKS.items())],
            "watches": [{"module": "Core.dll", "name": "FFileStream::Destroyed", "addr": "0x101edbe0", "armed": 1,
                         "final": 2, "stores": 2}],
            "watch_unattributed_changes": 0, "events_recorded": len(ev), "events_dropped": 0, "events": ev}


def candidate_dir(base, case=None, run_id="c1", report="synth", stdout=HELLO_OUT, log="Log: x\r\n", xrtlog=None,
                  exit_code=0, written=None, extra_meta=None):
    case = case or CASES["hellofull"]
    d = os.path.join(base, "xrt")
    written = {"UCC.log": log.encode("latin-1")} if written is None and log is not None else (written or {})
    meta = {"run_id": run_id, "inputs": {"UCC.exe": "a", "Core.dll": "b"}, "sandbox": "sandbox_cmp/x/System",
            "process_exit_code": exit_code, "written": {k: R.sha256_bytes(v) for k, v in written.items()}, "deleted": []}
    meta.update(extra_meta or {})
    write(os.path.join(d, "meta.json"), json.dumps(meta))
    write(os.path.join(d, "stdout.bin"), stdout)
    write(os.path.join(d, "stderr.txt"), b"")
    for k, v in written.items():
        write(os.path.join(d, "written", k), v)
    if log is not None:
        write(os.path.join(d, "UCC.log"), log.encode("latin-1"))
    if report == "synth":
        report = synth_report(case, run_id, exit_code)
    if report is not None:
        write(os.path.join(d, "report.json"), json.dumps(report))
    write(os.path.join(d, "xrt.log"), f"[t-1] run id: {run_id if xrtlog is None else xrtlog}\n")
    return d


def original_dir(base, run_id="r1", exit_code=0, stdout=HELLO_OUT, log="Log: x\r\n", trace=None, tracer_exit=0,
                 written=None, extra_meta=None, cmdline=CMDLINE):
    d = os.path.join(base, "original")
    written = {"UCC.log": log.encode("latin-1")} if written is None and log is not None else (written or {})
    meta = {"run_id": run_id, "inputs": {"UCC.exe": "a", "Core.dll": "b"}, "sandbox": "sandbox_cmp/x/System",
            "trace": trace is not None, "written": {k: R.sha256_bytes(v) for k, v in written.items()}, "deleted": []}
    if trace is None:
        meta.update(process_exit_code=exit_code, command_line=cmdline)
    else:
        meta["tracer_exit_code"] = tracer_exit
        if trace != "missing":
            write(os.path.join(d, "trace.json"), json.dumps(trace))
    meta.update(extra_meta or {})
    write(os.path.join(d, "meta.json"), json.dumps(meta))
    write(os.path.join(d, "stdout.bin"), stdout)
    for k, v in written.items():
        write(os.path.join(d, "written", k), v)
    if log is not None:
        write(os.path.join(d, "UCC.log"), log.encode("latin-1"))
    return d


def good_trace(run_id="r1", exit_code=0, hits=True):
    rvas = {"core.dll": [], "ucc.exe": []}
    if hits:
        for (m, n), va in SYN_MARKS.items():
            rvas[m.lower()].append(hex(va - (R.UCC_BASE if m == "UCC.exe" else R.CORE_BASE))[2:])
    return {"run_id": run_id, "complete": True, "exit_code": exit_code, "command": CMDLINE,
            "modules": [{"name": "Core.dll", "instrumented": 1, "hit_rvas": rvas["core.dll"]},
                        {"name": "UCC.exe", "instrumented": 1, "hit_rvas": rvas["ucc.exe"]}]}


# ------------------------------------------------------------------------------------------------ logic: arguments
class Arguments(unittest.TestCase):
    def bad(self, *argv):
        with self.assertRaises(R.UsageError):
            R.parse_args(list(argv))

    def test_repeat_must_be_positive_integer(self):
        for v in ("0", "-1", "1.5", "x", "", " ", "101", "1e2", "0x2"):
            self.bad("hellofull", "--repeat", v)
        self.assertEqual(R.parse_args(["hellofull", "--repeat", "3"]).repeat, 3)

    def test_timeout_must_be_finite_and_at_least_one_second(self):
        for v in ("0", "-5", "nan", "inf", "-inf", "x", "3601", "0.0004", "1e-9", "0.5"):
            self.bad("hellofull", "--timeout", v)
        self.assertEqual(R.parse_args(["hellofull", "--timeout", "2.5"]).timeout, 2.5)

    def test_case_ids_constrained_to_registry(self):
        for c in ("../hellofull", "..", "hellofull/..", "C:\\x", "HelloFull", "hellofull ", "sandbox", "x" * 50, ""):
            self.bad(c)
        self.bad()
        self.bad("hellofull", "hellofull")

    def test_args_after_dashdash_must_equal_registered(self):
        self.bad("hellofull", "--", "Core.HelloWorldCommandlet", "a", "b")
        self.bad("hellofull", "simple", "--", "Core.SimpleCommandlet")
        self.assertEqual(R.parse_args(["hellofull", "--", "Core.HelloWorldCommandlet", "a", "b", "c"]).cases, ["hellofull"])

    def test_trace_requires_reference(self):
        self.bad("hellofull", "--trace", "--no-original")

    def test_cli_exit_status_2_and_nothing_created(self):
        before = set(os.listdir(R.RUNS_ROOT)) if os.path.isdir(R.RUNS_ROOT) else set()
        for argv in (["hellofull", "--repeat", "0"], ["../x"], ["hellofull", "--timeout", "nan"],
                     ["--reevaluate", "C:\\nowhere"], ["--reevaluate"], ["--reevaluate", R.WS]):
            self.assertEqual(R.main(argv), 2, argv)
        after = set(os.listdir(R.RUNS_ROOT)) if os.path.isdir(R.RUNS_ROOT) else set()
        self.assertEqual(before, after, "a rejected invocation must not create a result location")

    def test_run_invocation_rejects_zero_runs_and_bad_timeouts(self):
        for repeat, timeout in ((0, 10.0), (1, 0.0), (1, float("nan")), (1, 0.5)):
            with self.assertRaises(R.UsageError):
                R.run_invocation(["hellofull"], repeat, timeout)

    def test_paths(self):
        with self.assertRaises(R.UsageError):
            R.fresh_sandbox("../escape")
        self.assertFalse(R.inside("C:\\x", R.WS))          # different drive: no crash
        self.assertFalse(R.inside(R.WS, R.WS))
        self.assertTrue(R.inside(os.path.join(R.WS, "a"), R.WS))

    def test_registry_rules(self):
        with self.assertRaises(ValueError):
            Expect(exit_code=1)
        Expect(exit_code=1, negative=True)
        with self.assertRaises(ValueError):
            Case("Bad Name", (), Expect(), "core_commandlet")
        for c in CASES.values():
            self.assertIn(c.profile, R.PROFILES)
            for n in c.natives:
                self.assertIn(("Core.dll", n), MARK_NAMES, n)


class Normalisation(unittest.TestCase):
    W = b"ArrayTest Transient.ArrayTest0 (Function Core.ArrayTest.NestedTests:000F) 0.661 Attempt to assign variable through None (line 0)\r\n"

    def test_elapsed_seconds_only(self):
        n = R.normalise_stdout
        self.assertEqual(n(self.W), n(self.W.replace(b"0.661", b"0.999")))
        for a, b in ((b":000F", b":0010"), (b"through None", b"through Nothing"), (b"(line 0)", b"(line 1)"),
                     (b"\r\n", b"\n")):
            self.assertNotEqual(n(self.W), n(self.W.replace(a, b)))
        other = b"Foo (Function A.B:0001) 0.500 Something else\r\n"
        self.assertNotEqual(n(other), n(other.replace(b"0.500", b"0.600")))

    def test_log_rules(self):
        a = ("Log: Log file open, 10/22/26 10:00:00\r\nInit: CPU Speed=3000.1 MHz\r\nLog: 12.5ms Purging garbage\r\n"
             "Init: CPU Features: CMOV FPU MMX SSE\r\nX\r\n")
        b = ("Log: Log file open, 10/23/26 11:11:11\r\nInit: CPU Speed=2999.9 MHz\r\nLog: 99ms Purging garbage\r\n"
             "Init: CPU Features: CMOV FPU\r\nX\r\n")
        self.assertEqual(R.normalise_log(a, True), R.normalise_log(b, True))
        self.assertNotEqual(R.normalise_log(a, False), R.normalise_log(b, False))     # -NOMMX -NOSSE: must match
        self.assertNotEqual(R.normalise_log(a, True), R.normalise_log(b.replace("X", "Y"), True))
        self.assertNotEqual(R.normalise_log(a, True), R.normalise_log(b.replace("\r\n", "\n"), True), "line endings")
        self.assertNotEqual(R.normalise_log(a, True), R.normalise_log(a.replace("X\r\n", "X\n"), True))
        self.assertTrue(R.policy_line_differs(["Core.HelloWorldCommandlet"]))
        self.assertFalse(R.policy_line_differs(["x", "-nommx", "-NOSSE"]))


class Expectations(unittest.TestCase):
    def test_normal_case_requires_exit_0(self):
        e = CASES["hellofull"].expect
        self.assertTrue(R.check_expectation(e, 3, b"anything"))
        self.assertEqual(R.check_expectation(e, 0, HELLO_OUT), [])
        self.assertTrue(R.check_expectation(e, 0, HELLO_OUT.replace(b"Hello, world!", b"Hello, world?")))
        self.assertTrue(R.check_expectation(e, 0, HELLO_OUT + b"Commandlet X not found\r\n"))


# ------------------------------------------------------------------------------------------------ logic: evaluation
class Synthetic(unittest.TestCase):
    """The real evaluation and evidence profiles on synthetic artifacts."""

    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.case = CASES["hellofull"]

    def judge(self, ref=None, cand=None, case=None, expected=SYN_EXPECTED):
        case = case or self.case
        r = R.collect_original(ref) if ref else None
        c = R.collect_candidate(cand or candidate_dir(os.path.join(self.tmp, "c"), case))
        return R.evaluate(case, r, c, expected)

    def failed_groups(self, v):
        return {g["group"] for g in v["evidence"] if not g["ok"]}

    def test_valid_pair_passes(self):
        v = self.judge(original_dir(os.path.join(self.tmp, "o")))
        self.assertEqual(v["verdict"], "PASS", v["failures"])
        self.assertTrue(all(g["ok"] for g in v["evidence"]))
        self.assertGreaterEqual(len(v["evidence"]), 8)

    def test_core_error_profile(self):
        # the profile itself; badclass additionally requires exception evidence (ExceptionEvidence tests)
        case = Case("synth_error", CASES["badclass"].args, CASES["badclass"].expect, "core_error")
        out = HELLO_OUT.replace(b"Executing Class Core.HelloWorldCommandlet\r\nHello, world!\r\nCommand line parameters=a b c\r\n",
                                b"Commandlet NoSuchCommandletXYZ not found\r\n")
        cand = candidate_dir(os.path.join(self.tmp, "c"), case, stdout=out)
        v = self.judge(original_dir(os.path.join(self.tmp, "o"), stdout=out), cand, case)
        self.assertEqual(v["verdict"], "PASS", v["failures"])
        rep = synth_report(CASES["hellofull"])            # a commandlet ran: not a lookup failure
        cand2 = candidate_dir(os.path.join(self.tmp, "c2"), case, stdout=out, report=rep)
        self.assertIn("lookup_failure", self.failed_groups(self.judge(None, cand2, case)))

    def mutate(self, fn, groups=(), text=None, case=None):
        rep = synth_report(case or self.case)
        fn(rep)
        v = self.judge(original_dir(os.path.join(self.tmp, "o")),
                       candidate_dir(os.path.join(self.tmp, "c"), case or self.case, report=rep), case)
        self.assertEqual(v["verdict"], "FAIL")
        for g in groups:
            self.assertIn(g, self.failed_groups(v), v["failures"])
        if text:
            self.assertTrue(any(text in f for f in v["failures"]), v["failures"])
        shutil.rmtree(self.tmp)
        os.makedirs(self.tmp)
        return v

    @staticmethod
    def drop(rep, pred):
        rep["events"] = [e for e in rep["events"] if not pred(e)]
        for i, e in enumerate(rep["events"]):
            e["seq"] = i + 1
        rep["events_recorded"] = len(rep["events"])

    def test_every_profile_event_is_required(self):
        base = synth_report(self.case)
        for i, e in enumerate(base["events"]):
            if e["kind"] in ("dll_attach", "dll_detach"):      # informational: the *_returned events are required
                continue
            key = (e["kind"], e.get("name"), e.get("thread"))
            self.mutate(lambda r, k=key: self.drop(r, lambda x: (x["kind"], x.get("name"), x.get("thread")) == k))

    def test_misattributed_and_patched_flag_stores(self):
        def store(r, new):
            return next(e for e in r["events"] if e["kind"] == "watch_store" and e["new"] == new)
        self.mutate(lambda r: store(r, 2).update(thread=0), ["shutdown_flag_transition"])
        self.mutate(lambda r: store(r, 2).update(where=store(r, 1)["where"]), ["shutdown_flag_transition"])
        self.mutate(lambda r: store(r, 1).update(where="10101000 (Core.dll+1000, in f_10101000+0)"), ["shutdown_flag_transition"])
        self.mutate(lambda r: store(r, 1).update(new=2), ["shutdown_flag_transition"])
        self.mutate(lambda r: r.update(watch_unattributed_changes=1), ["shutdown_flag_transition"])
        self.mutate(lambda r: r["watches"][0].update(final=1), ["shutdown_flag_transition"])

        def swap(r):
            a, b = store(r, 1), store(r, 2)
            ia, ib = r["events"].index(a), r["events"].index(b)
            r["events"][ia], r["events"][ib] = b, a
            for i, e in enumerate(r["events"]):
                e["seq"] = i + 1
        self.mutate(swap, ["shutdown_flag_transition"])

    def test_wrong_callers_values_and_threads(self):
        def m(r, name):
            return next(e for e in r["events"] if e.get("name") == name)
        self.mutate(lambda r: m(r, "appInit").update(stack_top="0x10140aa3"), ["engine_initialization"])
        self.mutate(lambda r: m(r, "UObject::StaticConstructObject").update(stack_top="0x1013894a"),
                    ["package_load_and_commandlet_construction"])
        self.mutate(lambda r: m(r, "UCC main returned").update(captured=1), ["engine_cleanup_and_exit"])
        self.mutate(lambda r: m(r, "FFileStream worker thread entry").update(thread=0), ["worker_creation_and_execution"])
        def extra_thread(r):
            r["events"].insert(10, {"seq": 0, "thread": 0, "kind": "thread_create", "index": 2, "entry": "0x10101000",
                                    "param": "0x0"})
            for i, e in enumerate(r["events"]):
                e["seq"] = i + 1
            r["events_recorded"] = len(r["events"])
        self.mutate(extra_thread, ["worker_creation_and_execution"])
        self.mutate(lambda r: r["threads"][1].update(state="running"), ["worker_termination_and_wait_completion"])
        self.mutate(lambda r: next(e for e in r["events"] if e["kind"] == "thread_at_exit").update(state="alive"),
                    ["worker_termination_and_wait_completion"])
        self.mutate(lambda r: r.update(events_dropped=3, events_recorded=r["events_recorded"] + 3),
                    ["engine_cleanup_and_exit"])

    def test_case_natives_required_and_ordered(self):
        for n in self.case.natives:
            self.mutate(lambda r, n=n: self.drop(r, lambda e: e.get("name") == n), ["commandlet_execution"])

        def late(r):
            e = next(x for x in r["events"] if x.get("name") == "UObject::execLog")
            r["events"].remove(e)
            r["events"].append(e)
            for i, x in enumerate(r["events"]):
                x["seq"] = i + 1
        self.mutate(late, ["commandlet_execution"])

    def test_instrumentation_binding(self):
        self.mutate(lambda r: [m.update(marks_sha256="e" * 64) for m in r["modules"]], ["instrumentation_binding"])
        self.mutate(lambda r: r["marks"][0].update(va="0x00000001"), ["instrumentation_binding"])
        self.mutate(lambda r: r["marks"].pop(), ["instrumentation_binding"])
        self.mutate(lambda r: next(e for e in r["events"] if e["kind"] == "mark").update(va="0x00000002"),
                    ["instrumentation_binding"])
        self.mutate(lambda r: r["watches"][0].update(addr="0x101edbe4"), ["instrumentation_binding"])
        v = self.judge(original_dir(os.path.join(self.tmp, "o")), expected=None)
        self.assertEqual(v["verdict"], "FAIL")

    def test_malformed_reports_fail_without_crashing(self):
        breakers = [lambda r: r.update(modules=None), lambda r: r.update(events=[1, 2]),
                    lambda r: r["events"][3].pop("seq"), lambda r: r["events"][3].update(seq="4"),
                    lambda r: r["events"][3].update(thread=False), lambda r: r["events"][5].update(seq=1),
                    lambda r: next(e for e in r["events"] if e["kind"] == "watch_store").update(where=None),
                    lambda r: r["events"].append({"kind": "incomplete"}), lambda r: r["events"][2].update(truncated=True),
                    lambda r: r.update(events_recorded=1), lambda r: r.update(exit_code="0"),
                    lambda r: r.update(threads=[{"index": "1"}]), lambda r: r.update(outcome=None)]
        for fn in breakers:
            rep = synth_report(self.case)
            fn(rep)
            v = self.judge(None, candidate_dir(os.path.join(self.tmp, "c"), report=rep))
            self.assertEqual(v["verdict"], "FAIL")
            self.assertTrue(any("malformed runtime report" in f for f in v["failures"]), v["failures"])
            shutil.rmtree(self.tmp)
            os.makedirs(self.tmp)

    def test_missing_and_stale_artifacts(self):
        o = original_dir(os.path.join(self.tmp, "o"))
        for kw, text in (({"report": None}, "runtime report missing"),
                         ({"report": dict(synth_report(self.case), run_id="old")}, "stale or foreign runtime report"),
                         ({"xrtlog": "0" * 32}, "runtime log does not carry this run's id"),
                         ({"xrtlog": ""}, "runtime log does not carry this run's id"),
                         ({"log": None}, "UCC.log missing")):
            v = self.judge(o, candidate_dir(os.path.join(self.tmp, "c"), **kw))
            self.assertEqual(v["verdict"], "FAIL", kw)
            self.assertTrue(any(text in f for f in v["failures"]), (kw, v["failures"]))
            shutil.rmtree(os.path.join(self.tmp, "c"))
        c = candidate_dir(os.path.join(self.tmp, "c"))
        os.remove(os.path.join(c, "xrt.log"))
        self.assertTrue(any("runtime log missing" in f for f in self.judge(o, c)["failures"]))
        shutil.rmtree(os.path.join(self.tmp, "c"))
        c = candidate_dir(os.path.join(self.tmp, "c"))
        write(os.path.join(c, "report.json"), '{"schema": 2, "run_id": "c1", "events": [')
        self.assertEqual(self.judge(o, c)["verdict"], "FAIL")

    def test_old_artifacts_elsewhere_are_never_consumed(self):
        old = candidate_dir(os.path.join(self.tmp, "old_invocation"))           # a complete, valid older run
        self.assertTrue(os.path.exists(os.path.join(old, "UCC.log")))
        v = self.judge(original_dir(os.path.join(self.tmp, "o")), candidate_dir(os.path.join(self.tmp, "new"), log=None))
        self.assertEqual(v["verdict"], "FAIL")

    def test_exit_codes(self):
        rep = synth_report(self.case, exit_code=3)
        ref = original_dir(os.path.join(self.tmp, "o"), exit_code=3)
        cand = candidate_dir(os.path.join(self.tmp, "c"), report=rep, exit_code=3)
        v = self.judge(ref, cand)
        self.assertEqual(v["verdict"], "FAIL")                 # equal nonzero exits: not a success case
        self.assertFalse(v["expected_result"])
        neg = Case("synthneg", self.case.args, Expect(3, self.case.expect.stdout_contains, negative=True),
                   "core_commandlet", self.case.natives)
        self.assertEqual(self.judge(ref, cand, neg)["verdict"], "PASS")
        v = self.judge(None, candidate_dir(os.path.join(self.tmp, "c2"), report=dict(synth_report(self.case), exit_code=1)))
        self.assertTrue(any("differs from the process exit code" in f for f in v["failures"]))

    def test_no_reference_is_unverified(self):
        v = self.judge(None)
        self.assertEqual(v["verdict"], "UNVERIFIED")
        self.assertIsNone(v["output_matches_reference"])

    def test_timeouts_and_diagnostics(self):
        o = original_dir(os.path.join(self.tmp, "o"), extra_meta={"timed_out": True, "process_exit_code": None})
        v = self.judge(o)
        self.assertTrue(any("original timed out" in f for f in v["failures"]), v["failures"])
        c = candidate_dir(os.path.join(self.tmp, "c1"), extra_meta={"timed_out": True, "process_exit_code": None})
        self.assertTrue(any("did not exit" in f for f in self.judge(None, c)["failures"]))
        c = candidate_dir(os.path.join(self.tmp, "c2"), report=dict(synth_report(self.case), outcome="timeout", exit_code=78),
                          exit_code=78)
        self.assertEqual(self.judge(None, c)["verdict"], "FAIL")
        c = candidate_dir(os.path.join(self.tmp, "c3"))
        write(os.path.join(c, "stderr.txt"), b"\nXRT FATAL (exit 76): something\n")
        v = self.judge(None, c)
        self.assertFalse(v["candidate_execution_completed"])

    def test_input_sandbox_and_command_line_identity(self):
        for kw, text in (({"extra_meta": {"inputs": {"UCC.exe": "a", "Core.dll": "b", "Core.u": "z"}}}, "different input files"),
                         ({"extra_meta": {"sandbox": "sandbox_cmp/y/System"}}, "different sandbox paths"),
                         ({"cmdline": CMDLINE + " d"}, "different guest command lines")):
            v = self.judge(original_dir(os.path.join(self.tmp, "o"), **kw))
            self.assertEqual(v["verdict"], "FAIL", kw)
            self.assertTrue(any(text in f for f in v["failures"]), v["failures"])
            shutil.rmtree(os.path.join(self.tmp, "o"))
        rep = dict(synth_report(self.case), modules=[{"name": "UCC.exe", "sha256": "a", "marks_sha256": SYN_DIGEST},
                                                     {"name": "Core.dll", "sha256": "OTHER", "marks_sha256": SYN_DIGEST}])
        self.assertEqual(self.judge(None, candidate_dir(os.path.join(self.tmp, "c"), report=rep))["verdict"], "FAIL")

    def test_written_files(self):
        o = original_dir(os.path.join(self.tmp, "o"), written={"UCC.log": b"Log: x\r\n", "User.ini": b"[A]\r\nx=1\r\n"})
        for written, want in (({"UCC.log": b"Log: x\r\n", "User.ini": b"[A]\r\nx=1\r\n"}, "PASS"),
                              ({"UCC.log": b"Log: x\r\n", "User.ini": b"[A]\r\nx=2\r\n"}, "FAIL"),
                              ({"UCC.log": b"Log: x\r\n"}, "FAIL"),
                              ({"UCC.log": b"Log: x\r\n", "User.ini": b"[A]\r\nx=1\r\n", "Extra.ini": b""}, "FAIL")):
            self.assertEqual(self.judge(o, candidate_dir(os.path.join(self.tmp, "c"), written=written))["verdict"], want)
            shutil.rmtree(os.path.join(self.tmp, "c"))
        c = candidate_dir(os.path.join(self.tmp, "c"))
        write(os.path.join(c, "written", "UCC.log"), b"tampered")             # copy no longer matches its hash
        self.assertEqual(self.judge(o, c)["verdict"], "FAIL")

    def test_tracer_failure_distinguished_from_guest_exit(self):
        o = R.collect_original(original_dir(os.path.join(self.tmp, "a"), trace=good_trace()))
        self.assertTrue(o["ok"], o["errors"])
        o = R.collect_original(original_dir(os.path.join(self.tmp, "b"), trace=good_trace(exit_code=5)))
        self.assertTrue(o["ok"])
        self.assertEqual(o["exit_code"], 5)
        v = R.evaluate(self.case, o, R.collect_candidate(candidate_dir(os.path.join(self.tmp, "bc"))), SYN_EXPECTED)
        self.assertTrue(any("reference does not produce" in f for f in v["failures"]))
        self.assertFalse(any("tracer failure" in f for f in v["failures"]))
        g = good_trace()
        for name, kw in (("tool_exit", {"trace": g, "tracer_exit": 4}), ("stale", {"trace": dict(g, run_id="x")}),
                         ("incomplete", {"trace": dict(g, complete=False)}), ("missing", {"trace": "missing"}),
                         ("no_code", {"trace": {k: v for k, v in g.items() if k != "exit_code"}}),
                         ("no_command", {"trace": {k: v for k, v in g.items() if k != "command"}})):
            o = R.collect_original(original_dir(os.path.join(self.tmp, name), **kw))
            self.assertFalse(o["ok"], name)
            self.assertTrue(any("tracer failure" in e for e in o["errors"]), (name, o["errors"]))
        o = R.collect_original(original_dir(os.path.join(self.tmp, "to"), trace=g, extra_meta={"timed_out": True}))
        self.assertEqual(o["errors"][0][:len("original timed out under the tracer")], "original timed out under the tracer")
        self.assertFalse(any("tracer failure" in e for e in o["errors"]), o["errors"])

    def test_trace_cross_check(self):
        v = self.judge(original_dir(os.path.join(self.tmp, "o"), trace=good_trace()))
        self.assertEqual(v["verdict"], "PASS", v["failures"])
        self.assertTrue(any(g["group"] == "original_trace_cross_check" and g["ok"] and len(g["checks"]) >= 20
                            for g in v["evidence"]))
        tr = good_trace()
        tr["modules"][0]["hit_rvas"] = [x for x in tr["modules"][0]["hit_rvas"]
                                        if int(x, 16) != SYN_MARKS[("Core.dll", "FFileStream worker thread entry")] - R.CORE_BASE]
        v = self.judge(original_dir(os.path.join(self.tmp, "o2"), trace=tr))
        self.assertIn("original_trace_cross_check", self.failed_groups(v))
        tr = good_trace()
        tr["modules"][1]["hit_rvas"] = []                         # UCC.exe main not executed by the original
        self.assertIn("original_trace_cross_check", self.failed_groups(self.judge(original_dir(os.path.join(self.tmp, "o3"), trace=tr))))
        tr = good_trace(hits=False)
        self.assertIn("original_trace_cross_check", self.failed_groups(self.judge(original_dir(os.path.join(self.tmp, "o4"), trace=tr))))

    def test_reference_without_log_is_invalid(self):
        v = self.judge(original_dir(os.path.join(self.tmp, "o"), log=None))
        self.assertEqual(v["verdict"], "FAIL")
        self.assertFalse(v["output_matches_reference"])


class ExceptionEvidence(unittest.TestCase):
    """cxx_exception_path (report only) and cxx_exception_path_matches_original (vs the traced original)."""

    @staticmethod
    def report_with(cxx):
        rep = synth_report(CASES["hello"])
        ev = rep["events"]
        cut = next(i for i, e in enumerate(ev) if e.get("name") == "UCommandlet::Main")
        for k, (kind, fields) in enumerate(cxx):
            ev.insert(cut + k, dict(seq=0, thread=0, kind=kind, **fields))
        for i, e in enumerate(ev):
            e["seq"] = i + 1
        rep["events_recorded"] = len(ev)
        throws = sum(1 for k, f in cxx if k == "cxx_throw" and not f.get("rethrow"))
        rep["cxx_exceptions"] = {"throws": throws, "catches": sum(1 for k, _ in cxx if k == "cxx_catch"),
                                 "unwind_actions": sum(1 for k, _ in cxx if k == "cxx_unwind"),
                                 "rethrows_leaving_catch": 0, "objects_destroyed": 0}
        return rep

    GOOD = [("cxx_throw", {"site": "0x1013c89f", "type": ".PAG", "object": "0x1", "rethrow": False}),
            ("cxx_catch", {"node": "0x2", "funcinfo": "0x3", "try": 0, "eh_state": 1, "depth": 0, "funclet": "0x1014f209", "type": ".PAG"}),
            ("cxx_unwind", {"node": "0x2", "eh_state": 1, "action": "0x10101000"}),
            ("cxx_catch_end", {"node": "0x2", "funclet": "0x1014f209", "how": "completed"}),
            ("cxx_resume", {"node": "0x2", "continuation": "0x1014f294", "in": "function"})]
    POINTS = ["core.dll 4f209 catch 0x1014f209 .PAG frame 0x1014f140 cont 0x1014f294",
              "core.dll 1000 unwind 0x10101000 frame 0x1014f140", "core.dll 4f294 continue 0x1014f294 frame 0x1014f140"]

    def trace(self, extra_continue=False):
        ev = [{"kind": "exception", "index": 0, "code": "0xe06d7363", "caller": "0x1013c89f"},
              {"kind": "point", "label": "catch 0x1014f209 .PAG frame 0x1014f140 cont 0x1014f294"},
              {"kind": "point", "label": "unwind 0x10101000 frame 0x1014f140"},
              {"kind": "point", "label": "continue 0x1014f294 frame 0x1014f140"}]
        if extra_continue:            # a normal-flow pass over a continuation point is not a resumption
            ev.insert(0, {"kind": "point", "label": "continue 0x1014f294 frame 0x1014f140"})
        return {"events": ev, "exceptions": [{"code": "0xe06d7363", "type": ".PAG"}], "event_points": 3, "events_dropped": 0}

    def group(self, groups, name):
        return next(g for g in groups if g["group"] == name)

    def test_report_only_group(self):
        g = self.group(R.PROFILES["core_commandlet"](CASES["hello"], self.report_with(self.GOOD)), "cxx_exception_path")
        self.assertTrue(g["ok"], g)
        for drop in ("cxx_catch", "cxx_catch_end", "cxx_resume"):
            bad = [x for x in self.GOOD if x[0] != drop]
            g = self.group(R.PROFILES["core_commandlet"](CASES["hello"], self.report_with(bad)), "cxx_exception_path")
            self.assertFalse(g["ok"], drop)
        g = self.group(R.PROFILES["core_commandlet"](CASES["hello"], self.report_with([])), "cxx_exception_path")
        self.assertFalse(g["ok"], "the measured path throws: no exception at all is not evidence")

    def test_sequence_matches_original(self):
        rep = self.report_with(self.GOOD)
        ref = {"trace": self.trace(extra_continue=True), "eh_points": self.POINTS}
        self.assertTrue(R.ev_cxx_original(rep, ref)["ok"])
        for i, field, value in ((0, "site", "0x1013c8a0"), (1, "funclet", "0x1014ed86"), (2, "action", "0x10101010"),
                                (4, "continuation", "0x1014f295")):
            cxx = [(k, dict(f)) for k, f in self.GOOD]
            cxx[i][1][field] = value
            self.assertFalse(R.ev_cxx_original(self.report_with(cxx), ref)["ok"], field)
        cxx = [(k, dict(f)) for k, f in self.GOOD]
        cxx[0][1]["rethrow"] = True
        self.assertFalse(R.ev_cxx_original(self.report_with(cxx), ref)["ok"], "rethrow flag")
        self.assertFalse(R.ev_cxx_original(rep, {"trace": self.trace(), "eh_points": None})["ok"], "no event points")
        tr = self.trace()
        tr["events_dropped"] = 1
        self.assertFalse(R.ev_cxx_original(rep, {"trace": tr, "eh_points": self.POINTS})["ok"], "dropped events")

    def test_exception_case_requires_traced_reference(self):
        out = HELLO_OUT
        v = R.evaluate(CASES["hello"], R.collect_original(original_dir(mkdtemp(), stdout=out)),
                       R.collect_candidate(candidate_dir(mkdtemp(), CASES["hello"], report=self.report_with(self.GOOD))),
                       SYN_EXPECTED)
        g = self.group(v["evidence"], "cxx_exception_path_matches_original")
        self.assertFalse(g["ok"])
        self.assertEqual(v["verdict"], "FAIL")


class Reevaluation(unittest.TestCase):
    def setUp(self):
        self.root = mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.inv = os.path.join(R.RUNS_ROOT, "test-reeval-" + os.path.basename(self.root))
        os.makedirs(self.inv)
        self.addCleanup(shutil.rmtree, self.inv, True)

    def make(self, runs=1, repeat=None, dirs=None, substitute=False):
        dump({"invocation_id": "x", "cases": {"hellofull": {}}}, os.path.join(self.inv, "summary.json"))
        rs = []
        for k in range(runs):
            rd = os.path.join(self.inv, "hellofull", f"run{k}")
            candidate_dir(rd)
            original_dir(rd)
            rs.append({"run": k, "dir": (dirs or {}).get(k, R.rel(rd)), "verdict": "PASS"})
        dump({"case": "hellofull", "args": list(CASES["hellofull"].args), "repeat": runs if repeat is None else repeat,
              "reference": "fresh-original", "invocation_id": "x", "runs": rs,
              "identity": {"candidate": {"substitute": ["x"]} if substitute else {"path": "x"}}},
             os.path.join(self.inv, "hellofull.summary.json"))

    def test_rejections(self):
        for kw in ({"runs": 0}, {"runs": 1, "repeat": 2}, {"dirs": {0: "../elsewhere/run0"}}, {"substitute": True}):
            shutil.rmtree(self.inv)
            os.makedirs(self.inv)
            self.make(**kw)
            self.assertEqual(R.main(["--reevaluate", self.inv]), 2, kw)

    def test_labels_never_fresh(self):
        self.make()
        lines = []
        res = R.reevaluate(self.inv, echo=lines.append)
        self.assertTrue(res["hellofull"]["verdict"].startswith("REEVALUATED_"))
        self.assertNotEqual(R.main(["--reevaluate", self.inv]), 0)
        self.assertEqual(res["hellofull"]["runs"][0]["reference"], "preserved-original")


class SandboxAndLock(unittest.TestCase):
    def test_fresh_sandbox_removes_planted_files(self):
        sysdir = os.path.join(R.SANDBOX_ROOT, "selftest_sandbox", "System")
        os.makedirs(sysdir, exist_ok=True)
        write(os.path.join(sysdir, "UCC.log"), b"stale")
        write(os.path.join(sysdir, "planted.txt"), b"x")
        self.addCleanup(shutil.rmtree, os.path.join(R.SANDBOX_ROOT, "selftest_sandbox"), True)
        d, hashes = R.fresh_sandbox("selftest_sandbox")
        self.assertFalse(os.path.exists(os.path.join(d, "planted.txt")))
        self.assertFalse(os.path.exists(os.path.join(d, "UCC.log")))
        self.assertIn("UCC.exe", hashes)

    def test_lock_is_exclusive_and_becomes_a_harness_error(self):
        with R.CaseLock("selftest_lock"):
            with self.assertRaises(R.HarnessError):
                with R.CaseLock("selftest_lock"):
                    pass
            ref, cand, v = R.run_one(CASES["hellofull"].__class__("selftest_lock", ("x",), Expect(), "core_commandlet"),
                                     os.path.join(mkdtemp(), "run0"), 10.0, False, True, None, {})
            self.assertEqual(v["verdict"], "FAIL")
            self.assertTrue(v["harness_error"])
        with R.CaseLock("selftest_lock"):
            pass

    def test_capture_writes(self):
        d = mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        sysdir = os.path.join(d, "System")
        write(os.path.join(sysdir, "a.ini"), b"1")
        write(os.path.join(sysdir, "b.ini"), b"2")
        before = R.snapshot(sysdir)
        write(os.path.join(sysdir, "a.ini"), b"changed")
        write(os.path.join(sysdir, "c.ini"), b"new")
        os.remove(os.path.join(sysdir, "b.ini"))
        written, deleted = R.capture_writes(sysdir, before, os.path.join(d, "out"))
        self.assertEqual(sorted(written), ["a.ini", "c.ini"])
        self.assertEqual(deleted, ["b.ini"])


# ------------------------------------------------------------------------------------------------ real data
def newest_real_run(case, trace):
    """run dir of the newest PASSing real run of `case` (runner schema >= 3, real candidate, given trace mode)."""
    for s in sorted(glob.glob(os.path.join(R.RUNS_ROOT, "*", f"{case}.summary.json")), reverse=True):
        d = load(s)
        if d.get("runner_schema", 0) < 3 or d.get("trace") != trace or (d.get("identity") or {}).get("candidate", {}).get("substitute"):
            continue
        if ((d.get("identity") or {}).get("marks") or {}).get("sha256") != R.sha256_file(R.MARKS):
            continue
        for r in d["runs"]:
            if r["verdict"] == "PASS":
                return os.path.join(R.WS, r["dir"])
    return None


class RealArtifactMutations(unittest.TestCase):
    """Mutations of the newest real PASS run; the unmodified copy must PASS first."""

    def load_run(self, case, trace=False):
        rundir = newest_real_run(case, trace)
        if rundir is None:
            if FULL:
                self.fail(f"no real PASS run of {case} (trace={trace}) under {R.RUNS_ROOT}")
            self.skipTest(f"no real PASS run of {case} (trace={trace})")
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(rundir, os.path.join(self.tmp, "run"))
        self.o = os.path.join(self.tmp, "run", "original")
        self.x = os.path.join(self.tmp, "run", "xrt")
        self.case = CASES[case]
        self.expected = R.expected_instrumentation(os.path.join(R.SANDBOX_ROOT, case, "System"))
        self.assertEqual(self.verdict()["verdict"], "PASS", "baseline copy must pass")

    def verdict(self):
        return R.evaluate(self.case, R.collect_original(self.o), R.collect_candidate(self.x), self.expected)

    def edit(self, fn):
        p = os.path.join(self.x, "report.json")
        rep = load(p)
        fn(rep)
        dump(rep, p)

    def test_traced_baseline(self):
        self.load_run("hellofull", trace=True)
        v = self.verdict()
        self.assertTrue(any(g["group"] == "original_trace_cross_check" and g["ok"] for g in v["evidence"]))

    def test_each_milestone_is_required(self):
        """Removing every event of one mark name, or one process/thread/watch event, must fail the run, and a
        failed check must name what was removed."""
        self.load_run("hellofull")
        rep = load(os.path.join(self.x, "report.json"))
        names = sorted({e["name"] for e in rep["events"] if e["kind"] == "mark"})
        for n in names:
            trial = copy.deepcopy(rep)
            trial["events"] = [e for e in trial["events"] if e.get("name") != n]
            trial["events_recorded"] = len(trial["events"])
            dump(trial, os.path.join(self.x, "report.json"))
            v = self.verdict()
            self.assertEqual(v["verdict"], "FAIL", n)
            self.assertTrue(any(n in f for f in v["failures"]), (n, v["failures"][:4]))
        kinds = ("dll_attach_returned", "exe_entry", "thread_create", "thread_start", "exit_thread", "thread_end",
                 "watch_initial", "watch_store", "thread_at_exit", "crt_exit", "process_exit", "dll_detach_returned",
                 "process_exit_complete")
        for i, e in enumerate(rep["events"]):
            if e["kind"] in kinds:
                trial = copy.deepcopy(rep)
                del trial["events"][i]
                trial["events_recorded"] -= 1
                dump(trial, os.path.join(self.x, "report.json"))
                self.assertEqual(self.verdict()["verdict"], "FAIL", e["kind"])
        dump(rep, os.path.join(self.x, "report.json"))
        self.assertEqual(self.verdict()["verdict"], "PASS")

    def test_no_worker(self):
        self.load_run("hellofull")

        def f(r):
            r["threads"] = [t for t in r["threads"] if t["index"] != 1]
            r["events"] = [e for e in r["events"] if e.get("thread") != 1 and e.get("index") != 1]
            r["events_recorded"] = len(r["events"])
        self.edit(f)
        bad = {g["group"] for g in self.verdict()["evidence"] if not g["ok"]}
        self.assertTrue({"worker_creation_and_execution", "worker_termination_and_wait_completion"} <= bad, bad)

    def test_real_output_alterations(self):
        self.load_run("hellofull")
        p = os.path.join(self.x, "stdout.bin")
        data = rbytes(p)
        for altered in (data.replace(b"Hello, world!", b"Hello, world?"), data + b"\r\n", data.replace(b"\r\n", b"\n")):
            write(p, altered)
            v = self.verdict()
            self.assertEqual(v["verdict"], "FAIL")
            self.assertFalse(v["comparison"]["stdout_identical_after_normalisation"])
        write(p, data)
        self.assertEqual(self.verdict()["verdict"], "PASS")

    def test_ucc_log_alterations(self):
        self.load_run("hellofull")
        p = os.path.join(self.x, "UCC.log")
        text = rbytes(p).decode("latin-1")
        stamped = re.sub(r"^(Log: Log file open, )[^\r\n]*", r"\g<1>01/01/99 00:00:00", text, flags=re.M)
        self.assertNotEqual(stamped, text)
        for altered, want in ((stamped, "PASS"), (text.replace("Hello, world!", "Hello, world?"), "FAIL"),
                              (text.replace("\r\n", "\n"), "FAIL"), ("\n".join(text.split("\n")[:-3]), "FAIL")):
            write(p, altered.encode("latin-1"))
            v = self.verdict()
            self.assertEqual(v["verdict"], want)
            if want == "FAIL":
                self.assertFalse(v["comparison"]["ucc_log_identical_after_normalisation"])

    def test_arraytest_warning_text_offsets_and_timing(self):
        self.load_run("arraytest")
        p = os.path.join(self.x, "stdout.bin")
        data = rbytes(p)
        self.assertIn(b"Attempt to assign variable through None", data)
        timing = re.sub(rb"(\(Function [^)]*\)) [0-9]+\.[0-9]{3} ", rb"\1 9.999 ", data)
        self.assertNotEqual(timing, data)
        for altered, want in ((timing, "PASS"), (data.replace(b"through None", b"through Nothing"), "FAIL"),
                              (data.replace(b"NestedTests:000F", b"NestedTests:0010"), "FAIL"),
                              (data.replace(b"RegularTests:0090", b"RegularTests:0091"), "FAIL"),
                              (data.replace(b"out of bounds (5/2)", b"out of bounds (5/3)"), "FAIL")):
            self.assertNotEqual(altered, data)
            write(p, altered)
            self.assertEqual(self.verdict()["verdict"], want)
        write(p, data)
        lp = os.path.join(self.x, "UCC.log")
        log = rbytes(lp)
        if b"through None" in log:
            write(lp, re.sub(rb"(\(Function [^)]*\)) [0-9]+\.[0-9]{3} ", rb"\1 7.777 ", log))
            self.assertEqual(self.verdict()["verdict"], "PASS")
            write(lp, log.replace(b"NestedTests:000F", b"NestedTests:000E"))
            self.assertEqual(self.verdict()["verdict"], "FAIL")


# ------------------------------------------------------------------------------------------------ end to end
@unittest.skipUnless(E2E, "set XRT_E2E=1 to run end-to-end runner tests (executes the original and translated UCC)")
class EndToEnd(unittest.TestCase):
    TAMPER = [sys.executable, "-I", os.path.join(HERE, "tamper_candidate.py")]

    def run_case(self, case, mode, no_original=False, trace=False, timeout=120.0):
        lines = []
        inv, invdir, summaries, overall = R.run_invocation([case], 1, timeout, trace=trace, no_original=no_original,
                                                            candidate_prefix=self.TAMPER + [mode], echo=lines.append)
        return summaries[case]["runs"][0], lines

    def expect(self, case, mode, verdict, groups=(), text=None, **kw):
        run, lines = self.run_case(case, mode, **kw)
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
        self.assertFalse(r["milestone_evidence_valid"] or r["candidate_execution_completed"])

    def test_stale_report_and_log(self):
        self.expect("hellofull", "stale_report", "FAIL", text="stale or foreign runtime report")
        self.expect("hellofull", "stale_xrtlog", "FAIL", text="runtime log does not carry this run's id")

    def test_worker_evidence_removed(self):
        self.expect("hellofull", "drop_worker", "FAIL", ["worker_creation_and_execution", "worker_termination_and_wait_completion"])

    def test_worker_incomplete(self):
        self.expect("hellofull", "worker_incomplete", "FAIL", ["shutdown_flag_transition", "worker_termination_and_wait_completion"])

    def test_flag_acknowledgement_missing_or_patched(self):
        self.expect("hellofull", "flag_skips_ack", "FAIL", ["shutdown_flag_transition"])
        self.expect("hellofull", "flag_by_main", "FAIL", ["shutdown_flag_transition"])

    def test_current_logs_omitted_while_old_artifacts_exist(self):
        old = os.path.join(R.WS, "experiments", "xrt", "results", "raw", "xrt")
        os.makedirs(old, exist_ok=True)
        for name in ("hellofull.UCC.log", "hellofull.report.json", "hellofull.xrt.log"):
            p = os.path.join(old, name)
            if not os.path.exists(p):
                write(p, b"stale\n")
                self.addCleanup(os.remove, p)
        self.expect("hellofull", "drop_ucclog", "FAIL", text="UCC.log missing")
        self.expect("hellofull", "drop_xrtlog", "FAIL", text="runtime log missing")

    def test_no_reference_is_unverified(self):
        run = self.expect("hellofull", "none", "UNVERIFIED", no_original=True)
        self.assertIsNone(run["output_matches_reference"])
        self.assertTrue(run["candidate_execution_completed"] and run["expected_result"] and run["milestone_evidence_valid"])
        out = mkdtemp()
        p = subprocess.run([sys.executable, "-I", os.path.join(R.WS, "tools", "xrt", "run_xrt.py"), "hellofull",
                            "--no-original"], capture_output=True, text=True, timeout=600,
                           env=dict(os.environ, XRT_COMPARE_DIR=out))
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn("matches_reference=None", p.stdout)
        self.assertEqual(load(os.path.join(out, "hellofull.json"))["verdict"], "UNVERIFIED")

    def test_zero_runs_cli(self):
        p = subprocess.run([sys.executable, "-I", os.path.join(R.WS, "tools", "xrt", "run_xrt.py"), "hellofull",
                            "--repeat", "0"], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)
        self.assertNotIn("PASS", p.stdout + p.stderr)

    def test_altered_output(self):
        self.expect("hellofull", "stdout:Hello, world!=>Hello, world?", "FAIL", text="output differs")

    def test_altered_warning_text_and_offset(self):
        self.expect("arraytest", "stdout:through None=>through Nothing", "FAIL", text="output differs")
        self.expect("arraytest", "stdout:NestedTests:000F=>NestedTests:0010", "FAIL", text="output differs")

    def test_documented_timing_differences_accepted(self):
        self.expect("arraytest", r"stdoutre:(\(Function [^)]*\)) [0-9]+\.[0-9]{3} =>\1 9.999 ", "PASS")
        self.expect("arraytest", r"ucclog:^(Log: Log file open, )[^\r\n]*=>\g<1>01/01/99 00:00:00", "PASS")
        self.expect("hellofull", r"ucclog:^Init: CPU Speed=[^\r\n]*=>Init: CPU Speed=1.000000 MHz", "PASS")

    def test_altered_ucc_log_content_and_line_endings(self):
        self.expect("hellofull", r"ucclog:^Log: Executing Class ([^\r\n]*)=>Log: Executing Klass \g<1>", "FAIL",
                    text="output differs")
        self.expect("hellofull", "ucclog_lf", "FAIL", text="output differs")

    def test_extra_written_file(self):
        self.expect("hellofull", "extra_write", "FAIL", text="written_files_identical")

    def test_fatal_diagnostic(self):
        r = self.expect("hellofull", "fatal_stderr", "FAIL", text="stopped with a diagnostic")
        self.assertFalse(r["candidate_execution_completed"])

    def test_hang_is_a_timeout(self):
        r = self.expect("hellofull", "hang", "FAIL", text="did not exit", no_original=True, timeout=1.0)
        self.assertFalse(r["candidate_execution_completed"])

    def test_tracer_failures_end_to_end(self):
        saved = R.TRACER, R.ENTRIES
        R.TRACER, R.ENTRIES = sys.executable, os.path.join(HERE, "fake_tracer.py")
        self.addCleanup(lambda: setattr(R, "TRACER", saved[0]) or setattr(R, "ENTRIES", saved[1]))
        for mode, text in (("tool_exit4", "tracer failure: uctrace exit status 4"), ("stale", "stale or foreign trace"),
                           ("incomplete", "trace incomplete"), ("no_json", "trace.json missing"),
                           ("garbage", "trace.json missing or malformed"),
                           ("guest_exit5", "reference does not produce the case's expected result")):
            os.environ["FAKE_TRACER_MODE"] = mode
            try:
                r = self.expect("hellofull", "none", "FAIL", text=text, trace=True)
            finally:
                del os.environ["FAKE_TRACER_MODE"]
            if mode == "guest_exit5":
                self.assertFalse(any("tracer failure" in f for f in r["failures"]))


if __name__ == "__main__":
    unittest.main()
