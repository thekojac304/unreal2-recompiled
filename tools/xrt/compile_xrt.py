"""Compiler-milestone driver: the ORIGINAL UnrealScript compiler (UCC.exe make, run from a sandbox copy) and the
TRANSLATED one (xrt_ucc.exe running the same UCC.exe) compile project-owned probe sources; the packages they write
are compared byte for byte and structurally, and executed by both engines.

Probe variants (project-owned test code, never game code): experiments/xrt/compile_probe/<variant>/XrtCompileProbe/
Classes/*.uc
  v1, v2   one commandlet class; v2 changes only the ProbeTag constant and the default Greeting (source-change proof)
  v3       several classes: inheritance, overrides, super, statics, defaults, arrays, out parameters, control flow
  invalid  uses an undeclared identifier: must fail to compile, and behave identically in both compilers
Each runnable variant has experiments/xrt/compile_probe/<variant>/expected.txt: the exact 'XCP ' lines its commandlet
prints, one per line, derived by hand from the sources. The original engine running the original compiler's package
(combination A) is the ground-truth check of that fixture: a disagreement is reported as a fixture failure, and the
fixture is never rewritten from run output.

Configuration rule: every execution uses a fresh sandbox at the SAME guest-visible path sandbox_cmp/xcp (the whole
directory removed, then recreated by tools/xrt/make_sandbox.py from the read-only install, while holding the
exclusive lock sandbox_cmp/xcp.lock). For a compile, the sources are staged to sandbox_cmp/xcp/XrtCompileProbe/
Classes/ and System/XrtCompileProbe.ini is derived from System/Unreal2.ini byte for byte (latin-1, line endings
kept), except that in [Editor.EditorEngine] all EditPackages= lines are replaced, at the position of the first one,
by exactly EditPackages=Core and EditPackages=XrtCompileProbe: make then builds only the probe package and never
rebuilds a shipped one. Before a run System/XrtCompileProbe.u must be absent and no XrtCompileProbe.* may exist
anywhere in the sandbox except the staged sources and that ini (otherwise: harness error).
  compile   UCC.exe make -ini=XrtCompileProbe.ini                      (cwd System; original: stdout+stderr merged)
            xrt_ucc.exe --guest <sandbox>\\System\\UCC.exe --log .. --report .. --run-id .. --timeout-ms .. -- make
            -ini=XrtCompileProbe.ini                                   (the run_xrt.execute_candidate shape)
  execute   UCC.exe XrtCompileProbe.XrtCompileProbe                    (no sources staged; the package is copied from
            this invocation's raw results and verified by SHA-256)

Compile classification (never by the exit code or by the package's existence alone):
  SUCCESS       exit code 0 AND a stdout line starting 'Success - 0 error(s)' AND no error reported AND System/
                XrtCompileProbe.u created by THIS run (absent before, present after, in the run's written set)
  FAILURE       stdout reports errors (an 'N error(s)' summary with N > 0, or another line containing 'Error' or
                'error') AND no success line AND no XrtCompileProbe.u written or present after the run; the exit code
                is recorded and compared between the compilers, never assumed
  INCONSISTENT  anything else (exit 0 without a package, a package together with error text, a stale package,
                timeout, fatal runtime diagnostic, ...): FAIL
Write policy (SHA-256 of every sandbox file before and after each run): a compile may change only System/Golem.u
(GlmLib's editor-mode start re-saves this 64-byte header-only package with a fresh GUID - the original does too; the
re-save must differ from the shipped file only in the GUID), System/XrtCompileProbe.ini (the engine saves its config)
and create only System/UCC.log and System/XrtCompileProbe.u; an execution may only create System/UCC.log. Anything
else - including a deletion - is an 'unexpected write' (FAIL).

Translated-run evidence (runtime report of the run, tools/xrt/run_xrt.py validate_report/Timeline), named checks:
report run id = the run's id, outcome 'exited', report exit code = process exit code, no 'fatal'/'timeout' event and
no XRT FATAL/TIMEOUT diagnostic, events_dropped == 0, process_exit_complete, every mapped module lifted from the
sandbox file of the same name, guest command line = the original's; compile: file_open ok of <sandbox>\\XrtCompile
Probe\\Classes\\<file> for every staged .uc, Editor.dll executed translated code including rva 68290
(UEditorEngine::InitEditor) and 85a50 (UEditorEngine::MakeScripts), a Golem.u re-save's GUID equal to the
create_guid preceding it, and for a successful compile UnrImp.gpi unloaded and a MoveFile to <sandbox>\\System\\
XrtCompileProbe.u (ok) whose preceding create_guid event's 'bytes' (the 16 GUID bytes in memory order) equal the
package's header bytes [36, 52); for the invalid source no such MoveFile (the error path leaves through appErrorf and
the original does not shut GlmLib down there - no 'Library shutting down' in its UCC.log - so the UnrImp.gpi unload is
only recorded, and the shutdown sequence is compared through UCC.log); execution:
file_open ok of <sandbox>\\System\\XrtCompileProbe.u, UCommandlet::Main called from UCC.exe, script executed
(ProcessInternal) and UObject::execLog called at least once per expected line.

Comparison classes for two packages (bytes): identical / guid_only (every differing byte inside the package GUID,
header bytes [36, 52), same size) / other. Differing offsets are reported as half-open ranges; ranges outside the
GUID field are 'unresolved' (a difference is never explained without evidence). Both packages are also parsed
(tools/pkgreader/upkg.py) and compared by header field, name/import/export table entry and each export's serialized
bytes. GUID rule: header bytes [36, 52) in Windows GUID memory layout (Data1..Data3 little-endian); RFC 4122 version 4
<=> (data[43] >> 4) == 4 and (data[44] & 0xC0) == 0x80. Within a variant every pair of packages must be identical or
guid_only (with distinct GUIDs: every compile created its own); v1 and v2 packages must differ outside the GUID.
Run comparisons (every compile run against the variant's first original run): exit code, stdout after
run_xrt.normalise_stdout, error/diagnostic lines, UCC.log after run_xrt.normalise_log, the set of written files,
XrtCompileProbe.ini contents, Golem.u (guid_only), System input hashes.

Execution cross-check (variants that compile, i.e. not 'invalid'): four combinations, each in a fresh sandbox:
  A  original package, original engine        B  original package, translated engine
  C  translated package, original engine      D  translated package, translated engine
(P_original = compile_original1's package, P_xrt = compile_xrt1's). Required: every combination exits 0 and prints
exactly expected.txt, leaves the package bytes unchanged, stdout of A..D identical after normalise_stdout, UCC.log
identical after normalise_log for A~C and B~D (same engine) and A~B, C~D (CPU-feature line normalised).
Source-change proof (v1 and v2 requested): the v1 and v2 packages of each compiler differ (hash, outside the GUID),
and the combinations print each variant's own tag/greeting (D: translated compiler -> translated engine), every v2
compile having started from a fresh sandbox without any XrtCompileProbe.u.

Results: experiments/xrt/results/raw/compile/<invocation-id>/ (created exclusively; git-ignored): plan.json,
<variant>/compile_<compiler><k>/ and <variant>/exec_<A..D>/ (meta.json with command, cwd, inputs, sandbox hashes
before/after, timings, exit code; stdout.bin, UCC.log, written/<files>, XrtCompileProbe.input.ini; report.json,
xrt.log, stderr.txt for translated runs), summary.json (everything) and compile_milestone.public.json; the public
compact summary also goes to experiments/xrt/results/compare/compile_milestone.json (XRT_COMPARE_DIR redirects it)
when the invocation used the complete configuration (all four variants, both compilers, --repeat >= 2, executions).

Usage:
  python -I tools/xrt/compile_xrt.py [--variants v1,v2,v3,invalid] [--compilers original,xrt] [--repeat N]
                                     [--timeout S] [--skip-exec]
  python -I tools/xrt/compile_xrt.py --reevaluate experiments/xrt/results/raw/compile/<invocation-id>
      re-judges the preserved raw artifacts with the current evaluation code and fixtures (nothing is executed);
      writes summary.reevaluated.json, verdicts are labelled REEVALUATED_* and never count as a fresh PASS.
Exit status: 0 PASS; 1 FAIL; 2 usage error; 3 no failure but INCOMPLETE (a subset of variants/compilers/runs was
requested, which cannot establish the milestone); 4 harness error; 5 re-evaluation without failures.
"""
import argparse
import importlib.util
import itertools
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_xrt as R  # noqa: E402
from make_sandbox import remove_tree  # noqa: E402

WS, PY, XRT, SANDBOX_ROOT = R.WS, R.PY, R.XRT, R.SANDBOX_ROOT
PROBE_ROOT = os.path.join(WS, "experiments", "xrt", "compile_probe")
COMPILE_ROOT = os.path.join(WS, "experiments", "xrt", "results", "raw", "compile")
MAKE_SANDBOX = os.path.join(HERE, "make_sandbox.py")
UPKG_PATH = os.path.join(WS, "tools", "pkgreader", "upkg.py")
PUBLIC_NAME = "compile_milestone.json"


def _load_upkg():
    spec = importlib.util.spec_from_file_location("xcp_upkg", UPKG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


upkg = _load_upkg()

CASE = "xcp"                                  # sandbox_cmp/xcp, lock sandbox_cmp/xcp.lock
PKG = "XrtCompileProbe"
PKG_FILE = "XrtCompileProbe.u"
INI_FILE = "XrtCompileProbe.ini"
PKG_REL, INI_REL, GOLEM_REL, LOG_REL = "System/XrtCompileProbe.u", "System/XrtCompileProbe.ini", "System/Golem.u", "System/UCC.log"
INPUT_INI_COPY = "XrtCompileProbe.input.ini"
MAKE_ARGS = ("make", "-ini=XrtCompileProbe.ini")
EXEC_ARGS = ("XrtCompileProbe.XrtCompileProbe",)
EDIT_PACKAGES = ("Core", "XrtCompileProbe")
VARIANTS = ("v1", "v2", "v3", "invalid")
NEGATIVE = frozenset({"invalid"})
COMPILERS = ("original", "xrt")
DEFAULT_REPEAT, DEFAULT_TIMEOUT = 2, 900.0
GUID_START, GUID_END = 36, 52
EDITOR_RVAS = (("68290", "UEditorEngine::InitEditor"), ("85a50", "UEditorEngine::MakeScripts"))
COMBOS = (("A", "original", "original"), ("B", "original", "xrt"), ("C", "xrt", "original"), ("D", "xrt", "xrt"))
COMPILE_ALLOWED_MODIFIED, COMPILE_ALLOWED_CREATED = (GOLEM_REL, INI_REL), (LOG_REL, PKG_REL)
EXEC_ALLOWED_MODIFIED, EXEC_ALLOWED_CREATED = (), (LOG_REL,)
EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_INCOMPLETE, EXIT_HARNESS, EXIT_REEVALUATED = 0, 1, 2, 3, 4, 5
GUID_RULE = ("GUID = package header bytes [36, 52) in Windows GUID memory layout (Data1, Data2, Data3 little-endian, "
             "Data4 bytes); RFC 4122 version 4 <=> (data[43] >> 4) == 4 (version nibble: high nibble of Data3's high "
             "byte, GUID byte 7) and (data[44] & 0xC0) == 0x80 (variant bits of Data4[0], GUID byte 8)")
SOURCE_CHANGE_LINES = {"v1": "XCP tag=alpha-1 greeting=from-defaults", "v2": "XCP tag=bravo-2 greeting=changed-default"}


# ------------------------------------------------------------------------------------------------ configuration (ini)
def split_lines(data):
    """bytes -> lines, each keeping its own terminator; b''.join(split_lines(d)) == d"""
    out, pos = [], 0
    while pos < len(data):
        k = data.find(b"\n", pos)
        end = len(data) if k < 0 else k + 1
        out.append(data[pos:end])
        pos = end
    return out


def _body(line):
    if line.endswith(b"\r\n"):
        return line[:-2], b"\r\n"
    if line.endswith(b"\n"):
        return line[:-1], b"\n"
    return line, b""


def _section(body):
    s = body.strip()
    return s[1:-1].strip().lower() if s.startswith(b"[") and s.endswith(b"]") else None


def _key(body):
    return body.split(b"=", 1)[0].strip().lower() if b"=" in body else None


EDITOR_SECTION = b"editor.editorengine"


def _edit_package_lines(lines):
    """indices of the EditPackages lines of [Editor.EditorEngine]; number of such sections"""
    section, seen, idx = None, 0, []
    for i, line in enumerate(lines):
        body = _body(line)[0]
        name = _section(body)
        if name is not None:
            section = name
            seen += name == EDITOR_SECTION
        elif section == EDITOR_SECTION and _key(body) == b"editpackages":
            idx.append(i)
    return idx, seen


def edit_packages(data):
    """the effective EditPackages list of [Editor.EditorEngine] (values stripped, latin-1)"""
    lines = split_lines(data)
    idx, _ = _edit_package_lines(lines)
    return [_body(lines[i])[0].split(b"=", 1)[1].strip().decode("latin-1") for i in idx]


def derive_ini(data, packages=EDIT_PACKAGES):
    """XrtCompileProbe.ini from Unreal2.ini: in [Editor.EditorEngine] every EditPackages= line is removed and
    EditPackages=<p> for each of `packages` inserted at the position of the first one (the first inserted line takes
    that line's terminator, the last one the terminator of the last removed line); every other byte is unchanged.
    Returns (bytes, info). Raises HarnessError when the section is missing or ambiguous or has no EditPackages."""
    lines = split_lines(data)
    idx, seen = _edit_package_lines(lines)
    if seen != 1:
        raise R.HarnessError(f"Unreal2.ini has {seen} [Editor.EditorEngine] sections (exactly one expected)")
    if not idx:
        raise R.HarnessError("Unreal2.ini [Editor.EditorEngine] has no EditPackages line")
    first_eol, last_eol = _body(lines[idx[0]])[1], _body(lines[idx[-1]])[1]
    if not first_eol:                      # the only EditPackages line ends the file without a terminator
        first_eol = b"\r\n" if b"\r\n" in data else b"\n"
    new = []
    for j, p in enumerate(packages):
        eol = last_eol if j == len(packages) - 1 else first_eol
        new.append(b"EditPackages=" + p.encode("latin-1") + eol)
    removed = set(idx)
    out = []
    for i, line in enumerate(lines):
        if i == idx[0]:
            out.extend(new)
        if i not in removed:
            out.append(line)
    derived = b"".join(out)
    info = {"replaced_edit_packages": [_body(lines[i])[0].split(b"=", 1)[1].strip().decode("latin-1") for i in idx],
            "first_edit_packages_line": idx[0] + 1, "inserted": [n.rstrip(b"\r\n").decode("latin-1") for n in new]}
    return derived, info


# ------------------------------------------------------------------------------------------------ stdout analysis
SUMMARY_RE = re.compile(r"\b(Success|Failure) - (\d+) error\(s\)")
SUCCESS_PREFIX = "Success - 0 error(s)"


def text_lines(data):
    return [ln.rstrip("\r") for ln in data.decode("latin-1").split("\n")]


def compile_messages(stdout):
    """compiler result signals in stdout: the success line, error summaries, diagnostic lines ('Error'/'error')"""
    lines = text_lines(stdout or b"")
    summaries = []
    for ln in lines:
        m = SUMMARY_RE.search(ln)
        if m:
            summaries.append((m.group(1), int(m.group(2)), ln))
    diagnostics = [ln for ln in lines if "Error" in ln or "error" in ln]
    zero_summaries = {ln for _, n, ln in summaries if n == 0}
    error_lines = [ln for ln in diagnostics if ln not in zero_summaries]
    return {"success_line": any(ln.startswith(SUCCESS_PREFIX) for ln in lines),
            "summaries": [ln for _, _, ln in summaries], "diagnostics": diagnostics, "error_lines": error_lines,
            "errors_reported": bool(error_lines) or any(n > 0 for _, n, _ in summaries)}


def classify_compile(exit_code, timed_out, stdout, pkg_before, pkg_written, pkg_after, aborted=None):
    """SUCCESS / FAILURE / INCONSISTENT (see the module docstring) with the facts it was decided on"""
    m = compile_messages(stdout)
    facts = {"exit_code": exit_code, "timed_out": bool(timed_out), "success_line": m["success_line"],
             "errors_reported": m["errors_reported"], "package_before": bool(pkg_before),
             "package_written_by_run": bool(pkg_written), "package_after": bool(pkg_after), "aborted": aborted}
    reasons = []
    if timed_out:
        reasons.append("the run timed out")
    if exit_code is None:
        reasons.append("no exit code")
    if stdout is None:
        reasons.append("no stdout")
    if aborted:
        reasons.append(f"the run was aborted: {aborted}")
    if pkg_before:
        reasons.append("XrtCompileProbe.u existed before the run (stale package)")
    if not reasons:
        if m["success_line"] and not m["errors_reported"] and exit_code == 0 and pkg_written and pkg_after:
            return {"classification": "SUCCESS", "reasons": [], "facts": facts, "messages": m}
        if m["errors_reported"] and not m["success_line"] and not pkg_written and not pkg_after:
            return {"classification": "FAILURE", "reasons": [], "facts": facts, "messages": m}
        if m["success_line"] and m["errors_reported"]:
            reasons.append("stdout has both a success line and error text")
        if m["success_line"] and not (pkg_written and pkg_after):
            reasons.append("success reported but no XrtCompileProbe.u written by this run")
        if m["success_line"] and exit_code != 0:
            reasons.append(f"success reported with exit code {exit_code}")
        if m["errors_reported"] and (pkg_written or pkg_after):
            reasons.append("errors reported but XrtCompileProbe.u " + ("written by this run" if pkg_written else "present"))
        if not m["success_line"] and not m["errors_reported"]:
            reasons.append("stdout reports neither success nor errors")
        if pkg_written and not pkg_after:
            reasons.append("XrtCompileProbe.u written but absent after the run")
        if not reasons:
            reasons.append("signals disagree")
    return {"classification": "INCONSISTENT", "reasons": reasons, "facts": facts, "messages": m}


def xcp_lines(stdout):
    """(lines from 'XCP ' on, raw lines): every stdout line containing 'XCP ' (trailing CR/LF stripped, nothing else)"""
    got, raw = [], []
    for ln in (stdout or b"").decode("latin-1").split("\n"):
        ln = ln.rstrip("\r\n")
        k = ln.find("XCP ")
        if k >= 0:
            raw.append(ln)
            got.append(ln[k:])
    return got, raw


def read_expected(path):
    """expected.txt: one exact line per expected XCP line (LF or CRLF; trailing spaces are significant)"""
    text = R.read_bytes(path).decode("utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in lines]


def compare_expected(got, expected):
    if got == expected:
        return {"ok": True, "detail": f"{len(got)} lines equal"}
    first = next((i for i, (a, b) in enumerate(zip(got, expected)) if a != b), None)
    if first is not None:
        detail = f"line {first + 1}: got {got[first]!r}, expected {expected[first]!r}"
    else:
        detail = f"{len(got)} lines, expected {len(expected)}; extra {(got[len(expected):] or expected[len(got):])[:2]!r}"
    return {"ok": False, "detail": detail, "first_difference": first}


def combo_matrix(compilers):
    """the execution combinations runnable with the requested compilers (each compiler is also an engine)"""
    return [{"combo": n, "package": p, "engine": e} for n, p, e in COMBOS if p in compilers and e in compilers]


# ------------------------------------------------------------------------------------------------ packages
def byte_ranges(a, b):
    """differing offsets as merged half-open ranges [start, end); a size difference extends to the longer length"""
    n, out, start = min(len(a), len(b)), [], None
    for i in range(n):
        if a[i] != b[i]:
            if start is None:
                start = i
        elif start is not None:
            out.append([start, i])
            start = None
    if start is not None:
        out.append([start, n])
    if len(a) != len(b):
        if out and out[-1][1] == n:
            out[-1][1] = max(len(a), len(b))
        else:
            out.append([n, max(len(a), len(b))])
    return out


def in_guid(r):
    return GUID_START <= r[0] and r[1] <= GUID_END


def diff_class(a, b, ranges=None):
    if a == b:
        return "identical"
    ranges = byte_ranges(a, b) if ranges is None else ranges
    return "guid_only" if len(a) == len(b) and all(in_guid(r) for r in ranges) else "other"


def guid_info(data):
    if data is None or len(data) < GUID_END:
        return {"present": False}
    g = data[GUID_START:GUID_END]
    version, variant = g[7] >> 4, g[8] & 0xC0
    return {"present": True, "hex": g.hex(), "version_nibble": version, "variant_bits": f"0x{variant:02x}",
            "rfc4122_v4": version == 4 and variant == 0x80}


HEADER_FIELDS = ("version", "licensee", "flags", "name_count", "name_offset", "export_count", "export_offset",
                 "import_count", "import_offset", "generations", "header_end")


def parse_package(data, name=PKG_FILE):
    try:
        return upkg.Package(name, data), None
    except Exception as exc:  # noqa: BLE001 - a package the reader cannot parse is a reported difference, never a crash
        return None, f"{type(exc).__name__}: {exc}"


def _exp_name(p, e):
    try:
        return p.objpath(e)
    except Exception:  # noqa: BLE001
        return e.name


def structural_diff(a, b, name=PKG_FILE):
    """table-level comparison (header fields, names, imports, exports, export payloads); the GUID is reported
    separately (guid_equal), never as a structural difference"""
    pa, ea = parse_package(a, name)
    pb, eb = parse_package(b, name)
    if ea or eb:
        return {"parsed": False, "errors": [e for e in (ea, eb) if e], "differences": [], "guid_equal": None}
    d = []
    for f in HEADER_FIELDS:
        va, vb = getattr(pa, f), getattr(pb, f)
        if va != vb:
            d.append({"table": "header", "object": f, "a": va, "b": vb})
    for i in range(max(len(pa.names), len(pb.names))):
        na = (pa.names[i], pa.name_flags[i]) if i < len(pa.names) else None
        nb = (pb.names[i], pb.name_flags[i]) if i < len(pb.names) else None
        if na != nb:
            d.append({"table": "names", "object": f"#{i} {(na or nb)[0]}", "a": na, "b": nb})
    for i in range(max(len(pa.imports), len(pb.imports))):
        ia = (pa.imports[i].class_package, pa.imports[i].class_name, pa.imports[i].outer, pa.imports[i].name) \
            if i < len(pa.imports) else None
        ib = (pb.imports[i].class_package, pb.imports[i].class_name, pb.imports[i].outer, pb.imports[i].name) \
            if i < len(pb.imports) else None
        if ia != ib:
            d.append({"table": "imports", "object": f"#{i} {(ia or ib)[3]}", "a": ia, "b": ib})
    for i in range(max(len(pa.exports), len(pb.exports))):
        xa = pa.exports[i] if i < len(pa.exports) else None
        xb = pb.exports[i] if i < len(pb.exports) else None
        label = f"#{i + 1} {_exp_name(pa, xa) if xa is not None else _exp_name(pb, xb)}"
        if xa is None or xb is None:
            d.append({"table": "exports", "object": label, "a": xa is not None, "b": xb is not None})
            continue
        ta = (xa.class_ref, xa.super_ref, xa.outer, xa.name, xa.flags, xa.size, xa.offset)
        tb = (xb.class_ref, xb.super_ref, xb.outer, xb.name, xb.flags, xb.size, xb.offset)
        if ta != tb:
            d.append({"table": "exports", "object": label, "field": "entry", "a": ta, "b": tb})
        pla, plb = pa.payload(xa), pb.payload(xb)
        if pla != plb:
            d.append({"table": "exports", "object": label, "field": "serialized bytes",
                      "ranges": byte_ranges(pla, plb)[:20]})
    return {"parsed": True, "errors": [], "differences": d[:50], "difference_count": len(d), "guid_equal": pa.guid == pb.guid}


def compare_packages(a, b, label_a, label_b, name=PKG_FILE):
    ranges = byte_ranges(a, b)
    cls = diff_class(a, b, ranges)
    st = structural_diff(a, b, name)
    return {"a": label_a, "b": label_b, "sha256": [R.sha256_bytes(a), R.sha256_bytes(b)], "size": [len(a), len(b)],
            "classification": cls, "differing_ranges": ranges[:100], "differing_range_count": len(ranges),
            "differing_bytes": sum(e - s for s, e in ranges),
            "unresolved_ranges": [r for r in ranges if not in_guid(r)][:100],
            "guid": [guid_info(a).get("hex"), guid_info(b).get("hex")], "structure": st,
            "at_most_guid": cls in ("identical", "guid_only") and st["parsed"] and not st["differences"]}


def saved_guid_check(events, target, data):
    """(ok, detail): the last successful MoveFile to `target` ('<sandbox>\\...') and the create_guid event preceding
    it (after any earlier MoveFile): its 'bytes' (16 bytes, memory order) must equal the header bytes [36, 52)"""
    t = target.lower()
    moves = [e for e in events if e.get("kind") == "move_file" and str(e.get("to", "")).lower() == t and e.get("ok") is True]
    if not moves:
        return False, f"no successful MoveFile to {target}"
    mv = moves[-1]
    earlier = [e["seq"] for e in events if e.get("kind") == "move_file" and e["seq"] < mv["seq"]]
    floor = earlier[-1] if earlier else 0
    cgs = [e for e in events if e.get("kind") == "create_guid" and floor < e["seq"] < mv["seq"]]
    if not cgs:
        return False, f"no create_guid event between the previous MoveFile (seq {floor}) and the save (seq {mv['seq']})"
    cg = cgs[-1]
    if cg.get("result") != "0x00000000":
        return False, f"create_guid seq {cg['seq']} failed: result {cg.get('result')!r}"
    b = cg.get("bytes")
    if not isinstance(b, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", b):
        return False, f"create_guid seq {cg['seq']} has no 'bytes' field of 32 hex digits ({sorted(cg)})"
    g = guid_info(data)
    if not g["present"]:
        return False, "no package bytes to compare"
    return b.lower() == g["hex"], f"create_guid seq {cg['seq']} bytes {b.lower()}, header {g['hex']} (save seq {mv['seq']})"


# ------------------------------------------------------------------------------------------------ write policy
def write_policy(before, after, allowed_modified, allowed_created):
    """before/after: {sandbox-relative path: sha256}; paths compared case-insensitively"""
    am, ac = {p.lower() for p in allowed_modified}, {p.lower() for p in allowed_created}
    modified = sorted(k for k in before if k in after and before[k] != after[k])
    created = sorted(k for k in after if k not in before)
    deleted = sorted(k for k in before if k not in after)
    unexpected = ([f"modified {k}" for k in modified if k.lower() not in am]
                  + [f"created {k}" for k in created if k.lower() not in ac] + [f"deleted {k}" for k in deleted])
    return {"modified": modified, "created": created, "deleted": deleted, "unexpected": unexpected, "ok": not unexpected}


def has(m, relp):
    return any(k.lower() == relp.lower() for k in (m or {}))


def get(m, relp):
    return next((v for k, v in (m or {}).items() if k.lower() == relp.lower()), None)


def input_digest(before):
    """SHA-256 over the System files before a run, without the probe configuration and package (run-specific)"""
    items = sorted((k, v) for k, v in before.items()
                   if k.lower().startswith("system/") and k.lower() not in (INI_REL.lower(), PKG_REL.lower()))
    return R.sha256_bytes("\n".join(f"{k} {v}" for k, v in items).encode())


# ------------------------------------------------------------------------------------------------ sandbox
def source_dir(variant):
    return os.path.join(PROBE_ROOT, variant, PKG, "Classes")


def expected_path(variant):
    return os.path.join(PROBE_ROOT, variant, "expected.txt")


def source_hashes(variant):
    d = source_dir(variant)
    return {f: R.sha256_file(os.path.join(d, f)) for f in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, f))}


def _no_links(path):
    if os.path.islink(path) or (hasattr(os.path, "isjunction") and os.path.isjunction(path)):
        raise R.HarnessError(f"link or junction in the sandbox: {path}")


def hash_tree(root):
    out = {}
    for dirpath, dirnames, files in os.walk(root):
        for d in dirnames:
            _no_links(os.path.join(dirpath, d))
        dirnames.sort()
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            _no_links(p)
            out[os.path.relpath(p, root).replace("\\", "/")] = R.sha256_file(p)
    return out


def find_probe_files(root):
    """sandbox-relative paths of every file or directory named XrtCompileProbe.* (case-insensitive)"""
    out = []
    for dirpath, dirnames, files in os.walk(root):
        for n in dirnames + files:
            if n.lower().startswith(PKG.lower() + "."):
                out.append(os.path.relpath(os.path.join(dirpath, n), root).replace("\\", "/"))
    return sorted(out)


def fresh_sandbox():
    """Remove sandbox_cmp/xcp entirely and recreate it (System only) with make_sandbox.py (without --probe)."""
    sb = os.path.join(SANDBOX_ROOT, CASE)
    if not R.inside(sb, SANDBOX_ROOT):
        raise R.HarnessError(f"sandbox path escapes {SANDBOX_ROOT}: {sb}")
    if os.path.lexists(sb):
        remove_tree(sb)
    if os.path.lexists(sb):
        raise R.HarnessError(f"could not remove {sb}")
    p = subprocess.run([PY, "-I", MAKE_SANDBOX, sb], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise R.HarnessError(f"make_sandbox failed ({p.returncode}): {p.stderr.strip()[-500:]}")
    inputs = {}
    for line in p.stdout.splitlines():
        if line.strip():
            name, digest = line.split()
            inputs[name] = digest
    sysdir = os.path.join(sb, "System")
    if sorted(os.listdir(sb)) != ["System"]:
        raise R.HarnessError(f"fresh sandbox contains more than System: {sorted(os.listdir(sb))}")
    if os.path.exists(os.path.join(sysdir, "UCC.log")):
        raise R.HarnessError("fresh sandbox already contains UCC.log (the install is expected not to have one)")
    return sb, sysdir, inputs


def stage_sources(variant, sb):
    src = source_dir(variant)
    dst = os.path.join(sb, PKG, "Classes")
    os.makedirs(dst)
    staged = {}
    for f in sorted(os.listdir(src)):
        p = os.path.join(src, f)
        if not os.path.isfile(p):
            raise R.HarnessError(f"unexpected entry in {R.rel(src)}: {f}")
        shutil.copyfile(p, os.path.join(dst, f))
        staged[f] = R.sha256_file(os.path.join(dst, f))
        if staged[f] != R.sha256_file(p):
            raise R.HarnessError(f"staged copy of {f} differs from its source")
    if not any(f.lower().endswith(".uc") for f in staged):
        raise R.HarnessError(f"no .uc source in {R.rel(src)}")
    return staged


def record_writes(sb, before, after, snap_before, outdir):
    """copy every created/changed file (by content hash) to outdir/written/<rel>; ({rel: sha256}, touched, deleted)"""
    written = {}
    for relp, digest in sorted(after.items()):
        if before.get(relp) != digest:
            dst = os.path.join(outdir, "written", relp)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(sb, relp), dst)
            if R.sha256_file(dst) != digest:
                raise R.HarnessError(f"{relp} changed after the run had ended")
            written[relp] = digest
    snap_after = R.snapshot(sb)
    touched = sorted(k for k in snap_after if k in snap_before and snap_after[k] != snap_before[k] and k not in written)
    return written, touched, sorted(set(before) - set(after))


def _process(meta, cmd, cwd, outdir, limit, merge_stderr):
    meta["command"] = cmd
    meta["command_line"] = subprocess.list2cmdline(cmd)
    meta["cwd"] = R.rel(cwd)
    meta["timeout_s"] = limit
    meta["started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    try:
        with open(os.path.join(outdir, "stdout.bin"), "wb") as fo:
            if merge_stderr:
                p = subprocess.run(cmd, cwd=cwd, stdout=fo, stderr=subprocess.STDOUT, timeout=limit)
            else:
                with open(os.path.join(outdir, "stderr.txt"), "wb") as fe:
                    p = subprocess.run(cmd, cwd=cwd, stdout=fo, stderr=fe, timeout=limit)
        meta["process_exit_code"] = p.returncode
    except subprocess.TimeoutExpired:
        meta["timed_out"] = True
    meta["seconds"] = round(time.time() - t0, 3)


def _command(engine, sysdir, outdir, run_id, timeout, args):
    exe = os.path.join(sysdir, "UCC.exe")
    if engine == "original":
        return [exe] + list(args), timeout, True
    return [XRT, "--guest", exe, "--log", os.path.join(outdir, "xrt.log"), "--report", os.path.join(outdir, "report.json"),
            "--run-id", run_id, "--timeout-ms", str(int(math.ceil(timeout * 1000))), "--"] + list(args), timeout + 30, False


def _finish_run(meta, sb, sysdir, outdir, before, snap):
    after = hash_tree(sb)
    meta["sandbox_after"] = after
    if os.path.exists(os.path.join(sysdir, "UCC.log")):
        shutil.copyfile(os.path.join(sysdir, "UCC.log"), os.path.join(outdir, "UCC.log"))
    meta["written"], meta["touched_unchanged"], meta["deleted"] = record_writes(sb, before, after, snap, outdir)


def execute_compile(variant, compiler, outdir, timeout):
    """One compile in a fresh sandbox; every artifact goes to outdir (created here: must not exist)."""
    os.makedirs(outdir)
    meta = {"kind": "compile", "variant": variant, "compiler": compiler, "run_id": uuid.uuid4().hex, "trace": False,
            "args": list(MAKE_ARGS)}
    try:
        with R.CaseLock(CASE):
            sb, sysdir, inputs = fresh_sandbox()
            meta.update(sandbox=R.rel(sysdir), sandbox_root=R.rel(sb), inputs=inputs,
                        guest_exe=os.path.join(sysdir, "UCC.exe"))
            meta["probe_files_before_staging"] = find_probe_files(sb)
            if meta["probe_files_before_staging"]:
                raise R.HarnessError(f"XrtCompileProbe.* in the fresh sandbox: {meta['probe_files_before_staging']}")
            meta["staged"] = stage_sources(variant, sb)
            base = R.read_bytes(os.path.join(sysdir, "Unreal2.ini"))
            derived, info = derive_ini(base)
            with open(os.path.join(sysdir, INI_FILE), "xb") as f:
                f.write(derived)
            with open(os.path.join(outdir, INPUT_INI_COPY), "xb") as f:
                f.write(derived)
            meta["ini"] = dict(info, base_sha256=R.sha256_bytes(base), sha256=R.sha256_bytes(derived),
                               edit_packages=edit_packages(derived))
            if meta["ini"]["edit_packages"] != list(EDIT_PACKAGES):
                raise R.HarnessError(f"derived EditPackages {meta['ini']['edit_packages']}")
            allowed = {f"{PKG}/Classes/{f}".lower() for f in meta["staged"]} | {INI_REL.lower()}
            meta["probe_files_before_run"] = find_probe_files(sb)
            extra = [p for p in meta["probe_files_before_run"] if p.lower() not in allowed]
            if os.path.lexists(os.path.join(sysdir, PKG_FILE)) or extra:
                raise R.HarnessError(f"target package or other probe files present before the run: {extra}")
            if os.path.isfile(os.path.join(sysdir, "Golem.u")):
                os.makedirs(os.path.join(outdir, "before", "System"))
                shutil.copyfile(os.path.join(sysdir, "Golem.u"), os.path.join(outdir, "before", "System", "Golem.u"))
            before = hash_tree(sb)
            snap = R.snapshot(sb)
            meta["sandbox_before"] = before
            cmd, limit, merge = _command(compiler, sysdir, outdir, meta["run_id"], timeout, MAKE_ARGS)
            _process(meta, cmd, sysdir, outdir, limit, merge)
            _finish_run(meta, sb, sysdir, outdir, before, snap)
    except Exception as exc:
        meta["harness_error"] = f"{type(exc).__name__}: {exc}"
        R.write_meta(outdir, meta)
        raise
    R.write_meta(outdir, meta)
    return meta


def execute_exec(variant, combo, pkg_compiler, engine, package_path, package_sha, outdir, timeout):
    """Run the commandlet of a package from this invocation's raw results in a fresh sandbox (no sources)."""
    os.makedirs(outdir)
    meta = {"kind": "exec", "variant": variant, "combo": combo, "package_compiler": pkg_compiler, "engine": engine,
            "run_id": uuid.uuid4().hex, "trace": False, "args": list(EXEC_ARGS), "source_package": R.rel(package_path),
            "source_package_sha256": package_sha}
    try:
        if not R.inside(package_path, COMPILE_ROOT):
            raise R.HarnessError(f"package {package_path} is not in the raw compile results")
        data = R.read_bytes(package_path)
        if R.sha256_bytes(data) != package_sha:
            raise R.HarnessError(f"{R.rel(package_path)} does not match its recorded SHA-256")
        os.makedirs(os.path.join(outdir, "package"))
        with open(os.path.join(outdir, "package", PKG_FILE), "xb") as f:
            f.write(data)
        with R.CaseLock(CASE):
            sb, sysdir, inputs = fresh_sandbox()
            meta.update(sandbox=R.rel(sysdir), sandbox_root=R.rel(sb), inputs=inputs,
                        guest_exe=os.path.join(sysdir, "UCC.exe"))
            meta["probe_files_before_staging"] = find_probe_files(sb)
            if meta["probe_files_before_staging"] or os.path.lexists(os.path.join(sb, PKG)):
                raise R.HarnessError(f"probe files in the fresh sandbox: {meta['probe_files_before_staging']}")
            with open(os.path.join(sysdir, PKG_FILE), "xb") as f:
                f.write(data)
            meta["loaded_package_sha256"] = R.sha256_file(os.path.join(sysdir, PKG_FILE))
            if meta["loaded_package_sha256"] != package_sha:
                raise R.HarnessError("the package copied into the sandbox does not match its recorded SHA-256")
            meta["probe_files_before_run"] = find_probe_files(sb)
            if [p.lower() for p in meta["probe_files_before_run"]] != [PKG_REL.lower()]:
                raise R.HarnessError(f"unexpected probe files before the run: {meta['probe_files_before_run']}")
            before = hash_tree(sb)
            snap = R.snapshot(sb)
            meta["sandbox_before"] = before
            cmd, limit, merge = _command(engine, sysdir, outdir, meta["run_id"], timeout, EXEC_ARGS)
            _process(meta, cmd, sysdir, outdir, limit, merge)
            _finish_run(meta, sb, sysdir, outdir, before, snap)
    except Exception as exc:
        meta["harness_error"] = f"{type(exc).__name__}: {exc}"
        R.write_meta(outdir, meta)
        raise
    R.write_meta(outdir, meta)
    return meta


# ------------------------------------------------------------------------------------------------ judging (raw only)
def load_meta(outdir):
    try:
        m = R.load_json(os.path.join(outdir, "meta.json"))
        return m if isinstance(m, dict) else None
    except (OSError, ValueError):
        return None


def collect(outdir, engine):
    return R.collect_original(outdir) if engine == "original" else R.collect_candidate(outdir)


def runtime_diagnostics(r):
    return [ln for ln in (r.get("stderr") or "").splitlines() if ln.startswith(("XRT FATAL", "XRT TIMEOUT"))]


def aborted_reason(r, engine):
    if engine == "original":
        return None
    rep = r.get("report")
    if rep is None:
        return "no valid runtime report"
    if rep.get("outcome") != "exited":
        return f"runtime outcome {rep.get('outcome')!r}"
    t = R.Timeline(rep)
    if t.find("fatal") or t.find("timeout"):
        return "fatal or timeout event in the runtime report"
    diag = runtime_diagnostics(r)
    return diag[0][:200] if diag else None


def module_entry(rep, name):
    return next((m for m in rep.get("modules", []) if str(m.get("name", "")).lower() == name.lower()), None)


def hit_rvas(m):
    out = set()
    for x in (m or {}).get("hit_rvas") or []:
        try:
            out.add(int(str(x), 16))
        except ValueError:
            pass
    return out


def report_integrity(c, r, meta):
    """named checks every translated run must satisfy (c: run_xrt.Checks); returns the Timeline or None"""
    rep = r.get("report")
    c.check("runtime report of this run present and well formed (run id, schema 2)", rep is not None,
            "; ".join(r.get("errors") or [])[:300])
    if rep is None:
        return None
    t = R.Timeline(rep)
    c.check("report run id equals the run's id", rep.get("run_id") == meta.get("run_id"), str(rep.get("run_id")))
    c.check("report outcome 'exited'", rep.get("outcome") == "exited", str(rep.get("outcome")))
    c.check("report exit code equals the process exit code",
            r.get("exit_code") is not None and rep.get("exit_code") == r.get("exit_code"),
            f"report {rep.get('exit_code')}, process {r.get('exit_code')}")
    c.check("no fatal or timeout event", not t.find("fatal") and not t.find("timeout"),
            str((t.find("fatal") + t.find("timeout"))[:1])[:300])
    diag = runtime_diagnostics(r)
    c.check("no XRT FATAL / XRT TIMEOUT diagnostic on stderr", not diag, diag[0][:300] if diag else "")
    c.check("event timeline complete (events_dropped == 0)", rep.get("events_dropped") == 0, f"{rep.get('events_dropped')}")
    c.require("process exit completed (process_exit_complete with the exit code)",
              t.first("process_exit_complete", code=r.get("exit_code")), lambda e: f"seq {e['seq']}")
    files = {}
    for k, v in (meta.get("sandbox_before") or {}).items():
        if k.lower().startswith("system/"):
            files.setdefault(k.rsplit("/", 1)[-1].lower(), set()).add(v)
    bad = [m.get("name") for m in rep.get("modules", []) if files.get(str(m.get("name", "")).lower()) != {m.get("sha256")}]
    c.check("every mapped module was lifted from the sandbox file of the same name (SHA-256)", not bad and rep.get("modules"),
            f"mismatched: {bad[:5]}")
    want = subprocess.list2cmdline([meta.get("guest_exe") or ""] + list(meta.get("args") or []))
    c.check("guest command line equals the original's (sandbox UCC.exe and the same arguments)",
            rep.get("guest_command_line") == want, f"{rep.get('guest_command_line')!r} vs {want!r}")
    return t


def compile_evidence(r, meta, variant, pkg_data, golem_data):
    c = R.Checks("translated_compile_evidence")
    t = report_integrity(c, r, meta)
    if t is None:
        return c.result()
    opened = {str(e.get("resolved", "")).lower() for e in t.find("file_open", ok=True)}
    for f in sorted(meta.get("staged") or {}):
        if f.lower().endswith(".uc"):
            target = f"<sandbox>\\{PKG}\\Classes\\{f}"
            c.check(f"staged source read: file_open ok of {target}", target.lower() in opened)
    ed = module_entry(t.report, "Editor.dll")
    c.check("Editor.dll mapped and translated code executed (functions_executed > 0)",
            ed is not None and isinstance(ed.get("functions_executed"), int) and ed["functions_executed"] > 0,
            f"{(ed or {}).get('functions_executed')} functions")
    hits = hit_rvas(ed)
    for rva, fn in EDITOR_RVAS:
        c.check(f"Editor.dll executed {fn} (hit rva {rva})", int(rva, 16) in hits, f"{len(hits)} hit rvas")
    target = f"<sandbox>\\System\\{PKG_FILE}"
    saves = [e for e in t.find("move_file") if str(e.get("to", "")).lower() == target.lower() and e.get("ok") is True]
    if variant in NEGATIVE:
        c.check(f"nothing saved: no successful MoveFile to {target}", not saves, f"{len(saves)} saves")
    else:
        c.check(f"package saved by this run: MoveFile to {target} ok", bool(saves), f"{len(saves)} saves")
        ok, detail = saved_guid_check(t.ev, target, pkg_data)
        c.check("package GUID (header bytes 36..51) equals the create_guid bytes preceding the save", ok, detail)
    if golem_data is not None:
        ok, detail = saved_guid_check(t.ev, "<sandbox>\\System\\Golem.u", golem_data)
        c.check("Golem.u re-save: GUID equals the create_guid bytes preceding its save", ok, detail)
    unloaded = t.first("dll_unloaded", module="UnrImp.gpi")
    if variant in NEGATIVE:
        # compile errors leave through appErrorf: the original's UCC.log then has no 'Golem: [Log] Library shutting
        # down' (GlmLib, which unloads UnrImp.gpi, is not shut down), so the unload is not required on this path; the
        # shutdown sequence is compared with the original's through UCC.log instead
        res = c.result()
        res["info"] = {"unrimp_unloaded": unloaded is not None}
        return res
    c.require("UnrImp.gpi unloaded (dll_unloaded)", unloaded, lambda e: f"seq {e['seq']}")
    return c.result()


def exec_evidence(r, meta, n_expected):
    c = R.Checks("translated_execution_evidence")
    t = report_integrity(c, r, meta)
    if t is None:
        return c.result()
    target = f"<sandbox>\\System\\{PKG_FILE}"
    c.require(f"package opened: file_open ok of {target}",
              next((e for e in t.find("file_open", ok=True) if str(e.get("resolved", "")).lower() == target.lower()), None),
              lambda e: f"seq {e['seq']}")
    c.require("UCommandlet::Main called from UCC.exe", t.mark_from_ucc("UCommandlet::Main"))
    c.require("script bytecode executed (UObject::ProcessInternal)", t.mark("UObject::ProcessInternal", thread=0))
    n = t.mark_count("UObject::execLog")
    c.check("UObject::execLog called at least once per expected line", isinstance(n, int) and n >= n_expected,
            f"{n} calls, {n_expected} expected lines")
    return c.result()


def _pkg_record(data):
    if data is None:
        return None
    return {"sha256": R.sha256_bytes(data), "size": len(data), "guid": guid_info(data)}


def judge_compile(outdir, variant, compiler, k, sources):
    """(result, artifacts) for one compile run, from its raw directory only"""
    name = f"compile_{compiler}{k}"
    res = {"run": name, "compiler": compiler, "k": k, "dir": R.rel(outdir)}
    c = R.Checks(name)
    meta = load_meta(outdir)
    if meta is None or meta.get("harness_error"):
        c.check("run executed (meta.json present, no harness error)", False,
                "meta.json missing or malformed" if meta is None else meta["harness_error"])
        res.update(classification="INCONSISTENT", ok=False, harness_error=(meta or {}).get("harness_error") or "no meta",
                   checks=c.result(), groups=[c.result()])
        return res, None
    r = collect(outdir, compiler)
    before, after, written = meta.get("sandbox_before") or {}, meta.get("sandbox_after") or {}, meta.get("written") or {}
    res["meta"] = {k2: meta.get(k2) for k2 in ("run_id", "command", "command_line", "cwd", "sandbox", "seconds",
                                                "process_exit_code", "timed_out", "timeout_s", "inputs", "staged", "ini",
                                                "started_utc", "touched_unchanged", "deleted")}
    c.check("artifacts of this run present and consistent (run id, exit code, stdout, UCC.log, written files)",
            r["ok"], "; ".join(r["errors"])[:400])
    c.check("XrtCompileProbe.u absent before the run (fresh sandbox, nothing from an earlier run)",
            meta.get("probe_files_before_staging") == [] and not has(before, PKG_REL),
            f"before staging {meta.get('probe_files_before_staging')}, before run {meta.get('probe_files_before_run')}")
    allowed = {f"{PKG}/Classes/{f}".lower() for f in meta.get("staged") or {}} | {INI_REL.lower()}
    c.check("no XrtCompileProbe.* in the sandbox before the run except the staged sources and the ini",
            all(p.lower() in allowed for p in meta.get("probe_files_before_run") or ["<missing>"]),
            str(meta.get("probe_files_before_run")))
    c.check("staged sources are exactly the variant's sources (SHA-256)", meta.get("staged") == sources,
            f"staged {meta.get('staged')}")
    ini = meta.get("ini") or {}
    c.check("configuration: [Editor.EditorEngine] EditPackages = Core, XrtCompileProbe",
            ini.get("edit_packages") == list(EDIT_PACKAGES), str(ini.get("edit_packages")))
    try:
        ini_copy = R.sha256_file(os.path.join(outdir, INPUT_INI_COPY))
    except OSError:
        ini_copy = None
    c.check("the sandbox ini before the run is the recorded derived ini (SHA-256)",
            ini.get("sha256") is not None and ini_copy == ini.get("sha256") == get(before, INI_REL),
            f"{ini_copy} / {ini.get('sha256')} / {get(before, INI_REL)}")
    pkg_data = get(r.get("written"), PKG_REL)
    golem_data = get(r.get("written"), GOLEM_REL)
    cls = classify_compile(r.get("exit_code"), meta.get("timed_out"), r.get("stdout"), has(before, PKG_REL),
                           has(written, PKG_REL), has(after, PKG_REL), aborted_reason(r, compiler))
    want = "FAILURE" if variant in NEGATIVE else "SUCCESS"
    c.check(f"compile classified {want}", cls["classification"] == want,
            f"{cls['classification']}: {'; '.join(cls['reasons'])}" if cls["reasons"] else cls["classification"])
    pol = write_policy(before, after, COMPILE_ALLOWED_MODIFIED, COMPILE_ALLOWED_CREATED)
    c.check("no unexpected write (only Golem.u and XrtCompileProbe.ini changed, UCC.log and XrtCompileProbe.u created)",
            pol["ok"] and before and after, "; ".join(pol["unexpected"][:10]) or ("" if before and after else "no hashes"))
    if variant in NEGATIVE:
        c.check("XrtCompileProbe.u absent after the run", not has(after, PKG_REL))
    golem_before = None
    if golem_data is not None:
        try:
            golem_before = R.read_bytes(os.path.join(outdir, "before", "System", "Golem.u"))
        except OSError:
            golem_before = None
        ok = golem_before is not None and R.sha256_bytes(golem_before) == get(before, GOLEM_REL)
        c.check("shipped Golem.u preserved from before the run (SHA-256 verified)", ok)
        if ok:
            gc = compare_packages(golem_before, golem_data, "shipped", name, "Golem.u")
            res["golem_vs_shipped"] = gc
            c.check("Golem.u re-save differs from the shipped Golem.u at most in the GUID (documented exception)",
                    gc["at_most_guid"], f"{gc['classification']} {gc['unresolved_ranges'][:5]} {gc['structure'].get('errors')}")
    groups = [c.result()]
    if compiler == "xrt":
        groups.append(compile_evidence(r, meta, variant, pkg_data, golem_data))
    res.update(classification=cls["classification"], classification_reasons=cls["reasons"], facts=cls["facts"],
               exit_code=r.get("exit_code"), timed_out=bool(meta.get("timed_out")),
               stdout_sha256=R.sha256_bytes(r["stdout"]) if "stdout" in r else None,
               success_line=cls["messages"]["success_line"], summaries=cls["messages"]["summaries"],
               diagnostics=cls["messages"]["diagnostics"], write_policy=pol, written=dict(sorted(written.items())),
               input_digest=input_digest(before), package=_pkg_record(pkg_data), golem=_pkg_record(golem_data),
               groups=groups, ok=all(g["ok"] for g in groups), harness_error=None)
    art = {"r": r, "meta": meta, "package": pkg_data, "golem": golem_data, "golem_before": golem_before,
           "classification": cls["classification"]}
    return res, art


def _line_diff(a, b, limit=20):
    la, lb = a.split("\n"), b.split("\n")
    d = [f"line {i + 1}: - {x!r} | + {y!r}" for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    if len(la) != len(lb):
        d.append(f"line count {len(la)} vs {len(lb)}")
    return d[:limit]


def compare_run_outputs(ra, rb, args):
    """stdout (normalise_stdout), exit code, UCC.log (normalise_log), written-file names of two collected runs"""
    out = {"exit_code": [ra.get("exit_code"), rb.get("exit_code")]}
    sa, sb = ra.get("stdout"), rb.get("stdout")
    out["stdout_byte_identical"] = sa is not None and sa == sb
    out["stdout_identical_after_normalisation"] = sa is not None and sb is not None and \
        R.normalise_stdout(sa) == R.normalise_stdout(sb)
    if not out["stdout_identical_after_normalisation"] and sa is not None and sb is not None:
        out["stdout_diff"] = _line_diff(R.normalise_stdout(sa), R.normalise_stdout(sb))
    la, lb = ra.get("log"), rb.get("log")
    if la is not None and lb is not None:
        pol = R.policy_line_differs(args)
        diff = _line_diff(R.normalise_log(la, pol), R.normalise_log(lb, pol))
        out["ucc_log_identical_after_normalisation"] = not diff
        out["ucc_log_diff"] = diff
    else:
        out["ucc_log_identical_after_normalisation"] = False
        out["ucc_log_diff"] = ["UCC.log missing"]
    wa, wb = sorted((ra.get("written") or {})), sorted((rb.get("written") or {}))
    out["written_names"] = [wa, wb]
    out["written_names_equal"] = [x.lower() for x in wa] == [x.lower() for x in wb]
    return out


def judge_variant(invdir, plan, variant, expected):
    vdir = os.path.join(invdir, variant)
    compilers, repeat = plan["compilers"], plan["repeat"]
    out = {"variant": variant, "negative": variant in NEGATIVE, "compiles": [], "run_comparisons": [],
           "package_pairs": [], "golem_pairs": [], "exec": None}
    arts = {}
    groups = []
    for comp in compilers:
        for k in range(1, repeat + 1):
            res, art = judge_compile(os.path.join(vdir, f"compile_{comp}{k}"), variant, comp, k, plan["sources"][variant])
            out["compiles"].append(res)
            groups.extend({**g, "group": f"{res['run']}/{g['group']}" if g["group"] != res["run"] else g["group"]}
                          for g in res["groups"])
            if art is not None:
                arts[f"{comp}{k}"] = art
    # ---- cross-run comparisons against the first original run (else the first run)
    c = R.Checks("compile_run_comparisons")
    names = [f"{comp}{k}" for comp in compilers for k in range(1, repeat + 1)]
    c.check("every compile run produced judgeable artifacts", all(n in arts for n in names),
            f"missing: {[n for n in names if n not in arts]}")
    ref = next((n for n in names if n in arts), None)
    for n in names:
        if n == ref or n not in arts or ref is None:
            continue
        a, b = arts[ref], arts[n]
        cmp = compare_run_outputs(a["r"], b["r"], MAKE_ARGS)
        cmp["runs"] = [ref, n]
        ma, mb = compile_messages(a["r"].get("stdout")), compile_messages(b["r"].get("stdout"))
        cmp["diagnostics_equal"] = ma["diagnostics"] == mb["diagnostics"]
        ia = get(a["meta"].get("written"), INI_REL)
        ib = get(b["meta"].get("written"), INI_REL)
        cmp["ini_written_equal"] = ia == ib
        cmp["input_digest_equal"] = input_digest(a["meta"].get("sandbox_before") or {}) == \
            input_digest(b["meta"].get("sandbox_before") or {})
        out["run_comparisons"].append(cmp)
        p = f"{ref} vs {n}: "
        c.check(p + "same exit code", cmp["exit_code"][0] is not None and cmp["exit_code"][0] == cmp["exit_code"][1],
                str(cmp["exit_code"]))
        c.check(p + "stdout identical after normalise_stdout", cmp["stdout_identical_after_normalisation"],
                "; ".join(cmp.get("stdout_diff", []))[:400])
        c.check(p + "same error/diagnostic lines", cmp["diagnostics_equal"], f"{ma['diagnostics'][:3]} vs {mb['diagnostics'][:3]}")
        c.check(p + "UCC.log identical after normalise_log", cmp["ucc_log_identical_after_normalisation"],
                "; ".join(cmp["ucc_log_diff"])[:400])
        c.check(p + "same set of written files", cmp["written_names_equal"], str(cmp["written_names"]))
        c.check(p + "XrtCompileProbe.ini saved with identical contents", cmp["ini_written_equal"], f"{ia} vs {ib}")
        c.check(p + "identical System inputs (SHA-256 of every input file)", cmp["input_digest_equal"])
    groups.append(c.result())
    # ---- packages
    pk = R.Checks("packages")
    pkgs = {n: a["package"] for n, a in arts.items() if a["package"] is not None}
    golems = {n: a["golem"] for n, a in arts.items() if a["golem"] is not None}
    out["packages"] = {n: _pkg_record(d) for n, d in pkgs.items()}
    out["golem"] = {n: _pkg_record(d) for n, d in golems.items()}
    if variant in NEGATIVE:
        pk.check("no compile wrote XrtCompileProbe.u", not pkgs, str(sorted(pkgs)))
    else:
        pk.check("every compile wrote XrtCompileProbe.u", sorted(pkgs) == sorted(names), str(sorted(pkgs)))
        for a, b in itertools.combinations(sorted(pkgs, key=names.index), 2):
            cp = compare_packages(pkgs[a], pkgs[b], a, b)
            out["package_pairs"].append(cp)
            pk.check(f"XrtCompileProbe.u {a} vs {b}: differs at most in the GUID (bytes and structure)", cp["at_most_guid"],
                     f"{cp['classification']}, unresolved {cp['unresolved_ranges'][:5]}, structure "
                     f"{[(x['table'], x['object']) for x in cp['structure']['differences'][:5]]} {cp['structure']['errors']}")
        guids = [guid_info(d).get("hex") for d in pkgs.values()]
        pk.check("every compile created its own package GUID (all distinct)", len(set(guids)) == len(guids), str(guids))
        kinds = {comp: {guid_info(d).get("rfc4122_v4") for n, d in pkgs.items() if n.startswith(comp)} for comp in compilers}
        if len(compilers) == 2 and all(kinds.values()):
            pk.check("translated packages' GUIDs have the original's RFC 4122 v4 classification",
                     kinds["original"] == kinds["xrt"], str(kinds))
    for a, b in itertools.combinations(sorted(golems, key=names.index), 2):
        gp = compare_packages(golems[a], golems[b], a, b, "Golem.u")
        out["golem_pairs"].append(gp)
        pk.check(f"Golem.u {a} vs {b}: differs at most in the GUID", gp["at_most_guid"],
                 f"{gp['classification']}, unresolved {gp['unresolved_ranges'][:5]}")
    groups.append(pk.result())
    # ---- execution cross-check
    if variant not in NEGATIVE and not plan.get("skip_exec"):
        ex, exec_groups = judge_exec_set(vdir, plan, variant, expected)
        out["exec"] = ex
        groups.extend(exec_groups)
    out["groups"] = groups
    out["harness_errors"] = [r["harness_error"] for r in out["compiles"] if r.get("harness_error")] + \
        [r["harness_error"] for r in (out["exec"] or {}).get("runs", []) if r.get("harness_error")]
    out["ok"] = all(g["ok"] for g in groups)
    return out


def judge_exec(outdir, variant, combo, pkg_compiler, engine, expected):
    res = {"combo": combo, "package": pkg_compiler, "engine": engine, "dir": R.rel(outdir)}
    c = R.Checks(f"exec_{combo}")
    meta = load_meta(outdir)
    if meta is None or meta.get("harness_error") or meta.get("skipped"):
        why = "meta.json missing" if meta is None else meta.get("harness_error") or f"not run: {meta.get('skipped')}"
        c.check("execution ran (meta.json present, no harness error, not skipped)", False, why)
        res.update(ok=False, groups=[c.result()], harness_error=(meta or {}).get("harness_error"), skipped=(meta or {}).get("skipped"))
        return res, None
    r = collect(outdir, engine)
    before, after = meta.get("sandbox_before") or {}, meta.get("sandbox_after") or {}
    res["meta"] = {k: meta.get(k) for k in ("run_id", "command", "command_line", "cwd", "sandbox", "seconds",
                                            "process_exit_code", "timed_out", "timeout_s", "inputs", "source_package",
                                            "source_package_sha256", "loaded_package_sha256", "started_utc")}
    c.check("artifacts of this run present and consistent (run id, exit code, stdout, UCC.log, written files)",
            r["ok"], "; ".join(r["errors"])[:400])
    loaded = meta.get("loaded_package_sha256")
    c.check("package loaded from this invocation's raw compile results (SHA-256 verified)",
            loaded is not None and loaded == meta.get("source_package_sha256") == get(before, PKG_REL),
            f"{loaded} / {meta.get('source_package_sha256')} / {get(before, PKG_REL)}")
    c.check("no sources and no other XrtCompileProbe.* in the sandbox (only the package)",
            meta.get("probe_files_before_staging") == [] and
            [p.lower() for p in meta.get("probe_files_before_run") or []] == [PKG_REL.lower()],
            str(meta.get("probe_files_before_run")))
    c.check("package bytes unchanged by the run", loaded is not None and get(after, PKG_REL) == loaded,
            f"after {get(after, PKG_REL)}")
    c.check("exit code 0", r.get("exit_code") == 0, str(r.get("exit_code")))
    got, raw = xcp_lines(r.get("stdout"))
    cmp = compare_expected(got, expected) if expected is not None else {"ok": False, "detail": "no expected.txt"}
    c.check("XCP lines equal expected.txt (exact, in order)", cmp["ok"], cmp["detail"])
    pol = write_policy(before, after, EXEC_ALLOWED_MODIFIED, EXEC_ALLOWED_CREATED)
    c.check("no unexpected write (only UCC.log created)", pol["ok"] and before and after, "; ".join(pol["unexpected"][:10]))
    groups = [c.result()]
    if engine == "xrt":
        groups.append(exec_evidence(r, meta, len(expected or [])))
    res.update(exit_code=r.get("exit_code"), xcp_lines=got, xcp_raw_lines=raw, matches_expected=cmp["ok"],
               expected_detail=cmp["detail"], stdout_sha256=R.sha256_bytes(r["stdout"]) if "stdout" in r else None,
               loaded_package_sha256=loaded, write_policy=pol, written=dict(sorted((meta.get("written") or {}).items())),
               groups=groups, ok=all(g["ok"] for g in groups), harness_error=None)
    return res, r


def judge_exec_set(vdir, plan, variant, expected):
    combos = combo_matrix(plan["compilers"])
    ex = {"combinations": [x["combo"] for x in combos], "runs": [], "comparisons": [], "fixture_failure": None}
    groups, rs = [], {}
    for x in combos:
        res, r = judge_exec(os.path.join(vdir, f"exec_{x['combo']}"), variant, x["combo"], x["package"], x["engine"], expected)
        ex["runs"].append(res)
        groups.extend({**g, "group": g["group"] if g["group"].startswith("exec_") else f"exec_{x['combo']}/{g['group']}"}
                      for g in res["groups"])
        if r is not None:
            rs[x["combo"]] = r
    a = next((x for x in ex["runs"] if x["combo"] == "A"), None)
    if a is not None and "xcp_lines" in a:
        ex["fixture_failure"] = not a["matches_expected"]
        if ex["fixture_failure"]:
            ex["fixture_failure_detail"] = (f"FIXTURE/EXPECTATION FAILURE: the original engine running the original "
                                            f"compiler's package disagrees with expected.txt: {a['expected_detail']}")
    c = R.Checks("execution_cross_check")
    c.check("every combination executed", sorted(rs) == sorted(ex["combinations"]),
            f"executed {sorted(rs)} of {ex['combinations']}")
    if a is not None:
        c.check("fixture ground truth: combination A (original package, original engine) prints expected.txt",
                a.get("matches_expected") is True, a.get("expected_detail", "A not executed"))
    pairs = [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]
    log_pairs = {("A", "C"), ("B", "D"), ("A", "B"), ("C", "D")}
    for p, q in pairs:
        if p in rs and q in rs:
            cmp = compare_run_outputs(rs[p], rs[q], EXEC_ARGS)
            cmp["combos"] = [p, q]
            ex["comparisons"].append(cmp)
            c.check(f"{p} vs {q}: stdout identical after normalise_stdout", cmp["stdout_identical_after_normalisation"],
                    "; ".join(cmp.get("stdout_diff", []))[:400])
            c.check(f"{p} vs {q}: same exit code", cmp["exit_code"][0] == cmp["exit_code"][1], str(cmp["exit_code"]))
            c.check(f"{p} vs {q}: same set of written files", cmp["written_names_equal"], str(cmp["written_names"]))
            if (p, q) in log_pairs:
                c.check(f"{p} vs {q}: UCC.log identical after normalise_log", cmp["ucc_log_identical_after_normalisation"],
                        "; ".join(cmp["ucc_log_diff"])[:400])
    groups.append(c.result())
    return ex, groups


def judge_source_change(variants_out, plan):
    if not {"v1", "v2"} <= set(plan["variants"]):
        return None
    c = R.Checks("source_change_proof")
    v1, v2 = variants_out["v1"], variants_out["v2"]
    proof = {"packages": {}, "exec": {}}
    for comp in plan["compilers"]:
        a = (v1["packages"] or {}).get(f"{comp}1")
        b = (v2["packages"] or {}).get(f"{comp}1")
        proof["packages"][comp] = {"v1_sha256": (a or {}).get("sha256"), "v2_sha256": (b or {}).get("sha256")}
        c.check(f"{comp} compiler: v1 and v2 packages differ (SHA-256)", a is not None and b is not None and a["sha256"] != b["sha256"],
                str(proof["packages"][comp]))
    for comp in plan["compilers"]:
        x1, x2 = v1.get("_pkg_bytes", {}).get(f"{comp}1"), v2.get("_pkg_bytes", {}).get(f"{comp}1")
        if x1 is not None and x2 is not None:
            cp = compare_packages(x1, x2, f"v1 {comp}1", f"v2 {comp}1")
            proof["packages"][comp].update(classification=cp["classification"], differing_ranges=cp["differing_ranges"][:20],
                                           structural_differences=[(d["table"], d["object"]) for d in cp["structure"]["differences"][:20]])
            c.check(f"{comp} compiler: v1 and v2 packages differ outside the GUID (the source change reached the package)",
                    cp["classification"] == "other", cp["classification"])
    for v, out in (("v1", v1), ("v2", v2)):
        for comp in plan["compilers"]:
            runs = [r for r in out["compiles"] if r["compiler"] == comp]
            c.check(f"{v} {comp} compiles started from a fresh sandbox without XrtCompileProbe.u",
                    bool(runs) and all(r.get("facts", {}).get("package_before") is False for r in runs),
                    str([r.get("facts", {}).get("package_before") for r in runs]))
    if not plan.get("skip_exec"):
        for combo in [x["combo"] for x in combo_matrix(plan["compilers"]) if x["combo"] in ("A", "D")]:
            got = {}
            for v, out in (("v1", v1), ("v2", v2)):
                run = next((x for x in (out["exec"] or {}).get("runs", []) if x["combo"] == combo), None)
                got[v] = (run or {}).get("xcp_lines")
                c.check(f"combination {combo} prints {v}'s own tag/greeting ({SOURCE_CHANGE_LINES[v]!r})",
                        bool(got[v]) and got[v][0] == SOURCE_CHANGE_LINES[v], str((got[v] or [None])[0]))
            proof["exec"][combo] = got
    res = c.result()
    res["proof"] = proof
    return res


def configuration_complete(plan):
    return (set(plan["variants"]) == set(VARIANTS) and set(plan["compilers"]) == set(COMPILERS)
            and plan["repeat"] >= 2 and not plan.get("skip_exec"))


def judge_invocation(invdir, plan, mode, harness=()):
    """Judge every run of an invocation from its raw directory (fresh and re-evaluation use the same code)."""
    variants_out = {}
    fixtures = {}
    for v in plan["variants"]:
        exp = None
        if v not in NEGATIVE:
            p = expected_path(v)
            if os.path.isfile(p):
                exp = read_expected(p)
                fixtures[v] = {"path": R.rel(p), "sha256": R.sha256_file(p), "lines": exp,
                               "recorded_sha256": (plan.get("expected") or {}).get(v, {}).get("sha256")}
            else:
                fixtures[v] = {"path": R.rel(p), "missing": True}
        out = judge_variant(invdir, plan, v, exp)
        # package bytes for the cross-variant comparison (not serialised)
        out["_pkg_bytes"] = {}
        for comp in plan["compilers"]:
            m = load_meta(os.path.join(invdir, v, f"compile_{comp}1"))
            dg = get((m or {}).get("written"), PKG_REL)
            if dg:
                try:
                    data = R.read_bytes(os.path.join(invdir, v, f"compile_{comp}1", "written", PKG_REL))
                    if R.sha256_bytes(data) == dg:
                        out["_pkg_bytes"][f"{comp}1"] = data
                except OSError:
                    pass
        variants_out[v] = out
    sc = judge_source_change(variants_out, plan)
    for out in variants_out.values():
        out.pop("_pkg_bytes", None)
    complete = configuration_complete(plan)
    # a fresh invocation sees every harness error itself (also those that left no meta.json); a re-evaluation only
    # the ones recorded in the run directories
    hcount = len(harness) if mode == "fresh" else sum(len(o["harness_errors"]) for o in variants_out.values())
    for v, out in variants_out.items():
        vcomplete = set(plan["compilers"]) == set(COMPILERS) and plan["repeat"] >= 2 and \
            (v in NEGATIVE or not plan.get("skip_exec"))
        out["verdict"] = "FAIL" if not out["ok"] or out["harness_errors"] else ("PASS" if vcomplete else "INCOMPLETE")
    verdicts = [o["verdict"] for o in variants_out.values()]
    failed = "FAIL" in verdicts or (sc is not None and not sc["ok"]) or bool(harness)
    verdict = "FAIL" if failed else ("PASS" if complete and "INCOMPLETE" not in verdicts else "INCOMPLETE")
    if mode == "reevaluated":
        verdict = "REEVALUATED_" + verdict
        for o in variants_out.values():
            o["verdict"] = "REEVALUATED_" + o["verdict"]
    fixture_failures = {v: o["exec"]["fixture_failure_detail"] for v, o in variants_out.items()
                        if (o.get("exec") or {}).get("fixture_failure")}
    return {"schema": 1, "tool": "compile_xrt", "mode": mode, "invocation_id": plan["invocation_id"],
            "invocation_dir": R.rel(invdir), "verdict": verdict, "configuration_complete": complete,
            "configuration": {k: plan[k] for k in ("variants", "compilers", "repeat", "timeout_s", "skip_exec")},
            "identity": plan.get("identity"), "identity_after": plan.get("identity_after"),
            "inputs": {"sources": plan["sources"], "expected": fixtures},
            "commands": {"compile": list(MAKE_ARGS), "execute": list(EXEC_ARGS)}, "guid_rule": GUID_RULE,
            "harness_errors": hcount, "harness_error_list": list(harness),
            "fixture_failures": fixture_failures, "variants": variants_out, "source_change_proof": sc}


# ------------------------------------------------------------------------------------------------ summaries
def public_summary(s):
    """compact, publishable: hashes, offsets, check names/verdicts, the probe's own output lines, relative paths"""
    def checks(groups):
        return [{"group": g["group"], "ok": g["ok"], "checks": [{"check": i["check"], "ok": i["ok"]} for i in g["checks"]]}
                for g in groups]

    def pair(p):
        return {"a": p["a"], "b": p["b"], "sha256": p["sha256"], "size": p["size"], "classification": p["classification"],
                "differing_ranges": p["differing_ranges"], "unresolved_ranges": p["unresolved_ranges"], "guid": p["guid"],
                "structure_parsed": p["structure"]["parsed"],
                "structural_differences": [{"table": d["table"], "object": d["object"], "field": d.get("field")}
                                           for d in p["structure"]["differences"]]}
    out = {k: s[k] for k in ("schema", "tool", "mode", "invocation_id", "invocation_dir", "verdict", "configuration_complete",
                             "configuration", "commands", "guid_rule", "harness_errors")}
    ident = s.get("identity") or {}
    out["identity"] = {"git_head": (ident.get("git") or {}).get("head"),
                       "git_tracked_files_modified": (ident.get("git") or {}).get("tracked_files_modified"),
                       "candidate": ident.get("candidate"), "runtime_sources": ident.get("runtime_sources"),
                       "driver": ident.get("driver")}
    out["inputs"] = {"sources": s["inputs"]["sources"],
                     "expected": {v: {k: f.get(k) for k in ("path", "sha256", "lines", "missing") if k in f}
                                  for v, f in s["inputs"]["expected"].items()}}
    out["fixture_failures"] = s["fixture_failures"]
    out["variants"] = {}
    for v, o in s["variants"].items():
        out["variants"][v] = {
            "verdict": o["verdict"],
            "compiles": [{"run": r["run"], "dir": r["dir"], "classification": r.get("classification"),
                          "exit_code": r.get("exit_code"), "stdout_sha256": r.get("stdout_sha256"),
                          "written": r.get("written"), "package": r.get("package"), "golem": r.get("golem"),
                          "input_digest": r.get("input_digest"), "seconds": (r.get("meta") or {}).get("seconds")}
                         for r in o["compiles"]],
            "package_pairs": [pair(p) for p in o["package_pairs"]],
            "golem_pairs": [pair(p) for p in o["golem_pairs"]],
            "golem_vs_shipped": [pair(r["golem_vs_shipped"]) for r in o["compiles"] if r.get("golem_vs_shipped")],
            "exec": None if o["exec"] is None else {
                "fixture_failure": o["exec"]["fixture_failure"],
                "runs": [{"combo": r["combo"], "package": r["package"], "engine": r["engine"], "dir": r["dir"],
                          "exit_code": r.get("exit_code"), "xcp_lines": r.get("xcp_lines"),
                          "matches_expected": r.get("matches_expected"), "stdout_sha256": r.get("stdout_sha256"),
                          "loaded_package_sha256": r.get("loaded_package_sha256")} for r in o["exec"]["runs"]]},
            "checks": checks(o["groups"])}
    sc = s.get("source_change_proof")
    out["source_change_proof"] = None if sc is None else {"ok": sc["ok"], "proof": sc["proof"],
                                                          "checks": [{"check": i["check"], "ok": i["ok"]} for i in sc["checks"]]}
    return out


def write_json(path, obj, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, default=str)


# ------------------------------------------------------------------------------------------------ invocation
def identity(compilers):
    return {"git": R.git_identity(), "driver": R.file_identity(os.path.abspath(__file__)),
            "run_xrt": R.file_identity(os.path.join(HERE, "run_xrt.py")), "make_sandbox": R.file_identity(MAKE_SANDBOX),
            "upkg": R.file_identity(UPKG_PATH),
            "candidate": R.file_identity(XRT) if "xrt" in compilers else None,
            "runtime_sources": R.tree_digest(os.path.join(WS, "experiments", "xrt", "runtime")),
            "generated_code": R.tree_digest(os.path.join(WS, "experiments", "xrt", "gen")) if "xrt" in compilers else None,
            "python": sys.version.split()[0], "host": platform.platform()}


def validate_request(variants, compilers, repeat, timeout, skip_exec):
    if not variants or len(set(variants)) != len(variants) or any(v not in VARIANTS for v in variants):
        raise R.UsageError(f"variants must be distinct names from {', '.join(VARIANTS)}, got {variants}")
    if not compilers or len(set(compilers)) != len(compilers) or any(c not in COMPILERS for c in compilers):
        raise R.UsageError(f"compilers must be distinct names from {', '.join(COMPILERS)}, got {compilers}")
    if not isinstance(repeat, int) or isinstance(repeat, bool) or not 1 <= repeat <= R.MAX_REPEAT:
        raise R.UsageError(f"--repeat must be between 1 and {R.MAX_REPEAT}, got {repeat}")
    if not isinstance(timeout, float) or not math.isfinite(timeout) or not R.MIN_TIMEOUT <= timeout <= R.MAX_TIMEOUT:
        raise R.UsageError(f"--timeout must be finite and between {R.MIN_TIMEOUT:g} and {R.MAX_TIMEOUT:g} s, got {timeout}")
    for v in variants:
        d = source_dir(v)
        if not os.path.isdir(d) or not any(f.lower().endswith(".uc") for f in os.listdir(d)):
            raise R.UsageError(f"no probe sources for variant {v} in {R.rel(d)}")
        if v not in NEGATIVE and not skip_exec and not os.path.isfile(expected_path(v)):
            raise R.UsageError(f"variant {v} has no {R.rel(expected_path(v))}")


def _skip(outdir, reason, meta_extra):
    os.makedirs(outdir)
    R.write_meta(outdir, dict(meta_extra, run_id=uuid.uuid4().hex, skipped=reason))


def run_invocation(variants, compilers, repeat, timeout, skip_exec=False, echo=print):
    variants, compilers = list(variants), list(compilers)
    validate_request(variants, compilers, repeat, timeout, skip_exec)
    compilers = [c for c in COMPILERS if c in compilers]
    if "xrt" in compilers and not os.path.isfile(XRT):
        raise R.UsageError(f"{R.rel(XRT)} is not built")
    inv, invdir = R.new_invocation_dir(COMPILE_ROOT)
    plan = {"schema": 1, "invocation_id": inv, "variants": variants, "compilers": compilers, "repeat": repeat,
            "timeout_s": timeout, "skip_exec": bool(skip_exec), "identity": identity(compilers),
            "sources": {v: source_hashes(v) for v in variants},
            "expected": {v: {"path": R.rel(expected_path(v)), "sha256": R.sha256_file(expected_path(v)),
                             "lines": read_expected(expected_path(v))}
                         for v in variants if v not in NEGATIVE and os.path.isfile(expected_path(v))}}
    write_json(os.path.join(invdir, "plan.json"), plan, exclusive=True)
    harness = []
    for v in variants:
        vdir = os.path.join(invdir, v)
        for comp in compilers:
            for k in range(1, repeat + 1):
                outdir = os.path.join(vdir, f"compile_{comp}{k}")
                try:
                    execute_compile(v, comp, outdir, timeout)
                except Exception as exc:  # noqa: BLE001 - recorded as a harness error of this run
                    harness.append(f"{v}/compile_{comp}{k}: {type(exc).__name__}: {exc}")
                    echo(f"[{v} compile_{comp}{k}] HARNESS ERROR: {type(exc).__name__}: {exc}")
                    continue
                res, _ = judge_compile(outdir, v, comp, k, plan["sources"][v])
                echo(f"[{v} compile_{comp}{k}] {res['classification']} exit {res.get('exit_code')} "
                     f"({(res.get('meta') or {}).get('seconds')} s) checks {'ok' if res['ok'] else 'FAILED'}")
                for g in res["groups"]:
                    for i in g["checks"]:
                        if not i["ok"]:
                            echo(f"    - [{g['group']}] {i['check']} ({i['detail'][:200]})")
        if v in NEGATIVE or skip_exec:
            continue
        for x in combo_matrix(compilers):
            outdir = os.path.join(vdir, f"exec_{x['combo']}")
            src_dir = os.path.join(vdir, f"compile_{x['package']}1")
            res, art = judge_compile(src_dir, v, x["package"], 1, plan["sources"][v])
            extra = {"kind": "exec", "variant": v, "combo": x["combo"], "package_compiler": x["package"], "engine": x["engine"]}
            if art is None or res["classification"] != "SUCCESS" or art["package"] is None:
                _skip(outdir, f"compile_{x['package']}1 did not compile successfully ({res['classification']})", extra)
                echo(f"[{v} exec_{x['combo']}] not run: compile_{x['package']}1 {res['classification']}")
                continue
            pkg_path = os.path.join(src_dir, "written", PKG_REL)
            try:
                execute_exec(v, x["combo"], x["package"], x["engine"], pkg_path, R.sha256_bytes(art["package"]), outdir, timeout)
            except Exception as exc:  # noqa: BLE001
                harness.append(f"{v}/exec_{x['combo']}: {type(exc).__name__}: {exc}")
                echo(f"[{v} exec_{x['combo']}] HARNESS ERROR: {type(exc).__name__}: {exc}")
                continue
            er, _ = judge_exec(outdir, v, x["combo"], x["package"], x["engine"], plan["expected"].get(v, {}).get("lines"))
            echo(f"[{v} exec_{x['combo']}] package {x['package']} engine {x['engine']}: exit {er.get('exit_code')} "
                 f"expected {'matched' if er.get('matches_expected') else 'NOT matched'} checks {'ok' if er['ok'] else 'FAILED'}")
            for ln in er.get("xcp_lines") or []:
                echo(f"    | {ln}")
            for g in er["groups"]:
                for i in g["checks"]:
                    if not i["ok"]:
                        echo(f"    - [{g['group']}] {i['check']} ({i['detail'][:200]})")
    plan["identity_after"] = {"candidate": R.file_identity(XRT) if "xrt" in compilers else None,
                              "runtime_sources": R.tree_digest(os.path.join(WS, "experiments", "xrt", "runtime"))}
    summary = judge_invocation(invdir, plan, "fresh", harness)
    if "xrt" in compilers:
        same = plan["identity_after"]["candidate"] == plan["identity"]["candidate"]
        summary["candidate_unchanged_during_invocation"] = same
        if not same:
            summary["verdict"] = "FAIL"
            summary["harness_error_list"].append("the translated build changed during the invocation")
    write_json(os.path.join(invdir, "summary.json"), summary, exclusive=True)
    pub = public_summary(summary)
    write_json(os.path.join(invdir, "compile_milestone.public.json"), pub, exclusive=True)
    if summary["configuration_complete"]:
        os.makedirs(R.COMPARE_DIR, exist_ok=True)
        write_json(os.path.join(R.COMPARE_DIR, PUBLIC_NAME), pub)
    return inv, invdir, summary


def reevaluate(invdir, echo=print):
    plan = R.load_json(os.path.join(invdir, "plan.json"))
    if not isinstance(plan, dict) or plan.get("schema") != 1:
        raise R.UsageError("plan.json missing or of an unknown schema")
    for key in ("invocation_id", "variants", "compilers", "repeat", "timeout_s", "sources"):
        if key not in plan:
            raise R.UsageError(f"plan.json lacks {key!r}")
    if os.path.basename(os.path.normpath(invdir)) != plan["invocation_id"]:
        raise R.UsageError("plan.json belongs to another invocation")
    plan.setdefault("skip_exec", False)
    try:
        prior = R.load_json(os.path.join(invdir, "summary.json"))
    except (OSError, ValueError):
        prior = {}
    summary = judge_invocation(invdir, plan, "reevaluated", ())
    summary["original_verdict"] = prior.get("verdict")
    summary["reevaluated_by"] = R.file_identity(os.path.abspath(__file__))
    write_json(os.path.join(invdir, "summary.reevaluated.json"), summary)
    write_json(os.path.join(invdir, "compile_milestone.reevaluated.public.json"), public_summary(summary))
    for v, o in summary["variants"].items():
        echo(f"[{v}] {o['verdict']}")
    return summary


# ------------------------------------------------------------------------------------------------ CLI
def parse_args(argv):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise R.UsageError(message)

    ap = Parser(prog="compile_xrt.py", add_help=False, allow_abbrev=False)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--compilers", default=",".join(COMPILERS))
    ap.add_argument("--repeat", default=str(DEFAULT_REPEAT))
    ap.add_argument("--timeout", default=str(DEFAULT_TIMEOUT))
    ap.add_argument("--skip-exec", action="store_true")
    a = ap.parse_args(argv)
    a.variants = [x.strip() for x in a.variants.split(",")]
    a.compilers = [x.strip() for x in a.compilers.split(",")]
    if not re.fullmatch(r"[0-9]+", a.repeat.strip()):
        raise R.UsageError(f"--repeat must be a positive integer, got {a.repeat!r}")
    a.repeat = int(a.repeat)
    try:
        a.timeout = float(a.timeout)
    except ValueError as exc:
        raise R.UsageError(f"--timeout must be a number of seconds, got {a.timeout!r}") from exc
    validate_request(a.variants, a.compilers, a.repeat, a.timeout, a.skip_exec)
    a.compilers = [c for c in COMPILERS if c in a.compilers]
    return a


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--reevaluate" in argv:
        d = os.path.abspath(argv[1]) if len(argv) == 2 and argv[0] == "--reevaluate" else ""
        if not d or not R.inside(d, COMPILE_ROOT) or not os.path.isdir(d):
            print(f"compile_xrt.py: --reevaluate needs exactly one invocation directory below {R.rel(COMPILE_ROOT)}",
                  file=sys.stderr)
            return EXIT_USAGE
        try:
            s = reevaluate(d)
        except (R.UsageError, OSError, ValueError, KeyError) as exc:
            print(f"compile_xrt.py: cannot re-evaluate {R.rel(d)}: {exc}", file=sys.stderr)
            return EXIT_USAGE
        print(f"re-evaluated {R.rel(d)} (preserved artifacts, not a fresh result): {s['verdict']}")
        return EXIT_FAIL if s["verdict"] == "REEVALUATED_FAIL" else EXIT_REEVALUATED
    try:
        a = parse_args(argv)
        if "xrt" in a.compilers and not os.path.isfile(XRT):
            raise R.UsageError(f"{R.rel(XRT)} is not built")
    except R.UsageError as exc:
        print(f"compile_xrt.py: {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        inv, invdir, s = run_invocation(a.variants, a.compilers, a.repeat, a.timeout, a.skip_exec)
    except R.UsageError as exc:
        print(f"compile_xrt.py: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception:  # noqa: BLE001 - a failure of the driver itself
        traceback.print_exc()
        return EXIT_HARNESS
    for v, o in s["variants"].items():
        print(f"[{v}] {o['verdict']}" + (f" (harness errors: {len(o['harness_errors'])})" if o["harness_errors"] else ""))
        for g in o["groups"]:
            for i in g["checks"]:
                if not i["ok"]:
                    print(f"    - [{g['group']}] {i['check']} ({i['detail'][:200]})")
    for v, msg in s["fixture_failures"].items():
        print(f"!!! {v}: {msg}")
    sc = s.get("source_change_proof")
    if sc is not None:
        print(f"[source change proof] {'ok' if sc['ok'] else 'FAILED'}")
        for i in sc["checks"]:
            if not i["ok"]:
                print(f"    - {i['check']} ({i['detail'][:200]})")
    print(f"invocation {inv}: {s['verdict']}" + ("" if s["configuration_complete"] else " (subset of the milestone configuration)"))
    print(f"raw evidence: {R.rel(invdir)}")
    if s["harness_errors"] or s["harness_error_list"]:
        return EXIT_HARNESS
    return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL, "INCOMPLETE": EXIT_INCOMPLETE}[s["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
