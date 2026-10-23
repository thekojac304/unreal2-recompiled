"""Run the msvcr70 differential test and compare (see README.md).

  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\crt_diff\\compare.py [--json results.json] [--seed N] [--i10 N]

Generates the corpus (gen_corpus.py), runs build\\crt_diff\\ref.exe (real msvcr70.dll from the read-only
sandbox copy) and build\\crt_diff\\cand.exe (runtime adapters), compares every case, prints a per-category
summary and the first mismatches, writes a reproducer for every mismatch, and optionally writes a JSON summary
with the provenance of the run.

E, X and F lines run one case per pair of processes:
- E lines are intentional error behaviour (NULL destination, NULL format).
- X lines are _set_se_translator, whose state is per thread.
- F lines are file-system sequences. Their processes run in a scratch tree (build\\crt_diff\\fs\\root) that is rebuilt
  before every process. The tree has fixed names, contents, attributes and creation/write times; its access times
  are the run's start time. Each F result is compared together with a snapshot of the tree after the process
  (names, attributes, sizes, contents). The reference runs every F line a second time, and a reference that does not
  reproduce itself fails the case.
The reference catches faults with SEH; the candidate has no handler, so a fault ends its process. A fault on both
sides is a match (codes recorded); a fault on one side only is a mismatch.

Exit status: 0 every case compared and matched; 1 mismatches; 3 no mismatch but cases PENDING (a function whose
runtime adapter does not exist yet: never counted as passed).
"""
import argparse
import collections
import ctypes
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
BUILD = os.environ.get("XRT_CRT_BUILD_DIR") or os.path.join(ROOT, "experiments", "xrt", "build", "crt_diff")
DLL = os.path.join(ROOT, "sandbox_ref", "hellofull", "System", "msvcr70.dll")
DLL_SANDBOX = os.path.dirname(os.path.dirname(DLL))   # cand.exe loads the same DLL's tables from <this>\System
REPRO = os.path.join(HERE, "repro")
FS_PARENT = os.path.join(BUILD, "fs")
FS_ROOT = os.path.join(FS_PARENT, "root")
# Every process (generator, both sides, the isolated runs) gets compare.py's environment without the variables msvcr70
# reads for behaviour under test: TZ (time zone of _findfirst's times) and __MSVCRT_HEAP_SELECT (heap selection,
# hence _msize).
ENV_REMOVED = ("TZ", "__MSVCRT_HEAP_SELECT")
ENV = {k: v for k, v in os.environ.items() if k.upper() not in ENV_REMOVED}
# provenance: every runtime file on cand.exe's link line, the generated translation it links, and the harness itself
RUNTIME_SOURCES = ["xrt_fmt.c", "hle_msvcr70.c", "xrt_mem.c", "hle_kernel32.c", "xrt_msvcr70img.c", "xrt.h",
                   "xrt_internal.h"]
GENERATED_SOURCES = [os.path.join("experiments", "xrt", "gen", "msvcr70", "pow_sse2.c")]   # git-ignored
HARNESS_SOURCES = ["crt_diff_core.h", "ref.c", "cand.c", "gen_corpus.py", "compare.py", "build.cmd",
                   os.path.join("..", "common", "xrt_test_stubs.c")]
EXCLUSIONS = {
    "_snwprintf": "not imported by UCC.exe, Core.dll, Engine.dll, GlmLib.dll or Editor.dll",
    "swscanf, swprintf, _snprintf, _vsnprintf on the ucc make path": "not reached by the original `ucc make` (main "
        "session's import trace); _snprintf/_vsnprintf keep their B/K/E cases (PENDING without an adapter)",
    "outputs of 16384 characters or more": "B lines: SKIP (the measuring call has a 16384-character capacity)",
    "F2 (ACP 932 command-line splitting)": "separate test experiments/xrt/tests/f2_mbcs_argv, open, not part of this "
                                           "formatter result",
    "DBCS code pages for the path and string functions": "T and F lines run under the system ANSI code page (recorded "
        "in fs.acp); behaviour under ACP 932 belongs to the open F2 work and is not claimed here",
    "TZ and __MSVCRT_HEAP_SELECT environment variables": "removed from the environment of every process (generator, "
        "both sides, isolated runs): F-line times use the system time zone (recorded in fs, with whether DST was in "
        "effect at the run), and msvcr70 selects its heap the default way (system heap on NT 5+)",
    "access times in F lines": "every access time in the tree is the run's start time T0: NTFS refreshes a last-access "
        "time that is more than an hour old when the file is opened, so historical access times would not stay fixed. "
        "Creation and write times are fixed historical values",
    "times in the tree snapshot": "the snapshot compares names, attributes, sizes and contents; times are compared "
        "through _findfirst/_findnext only",
    "files of 4 GB or more": "_finddata_t.size is 32-bit; not tested",
    "_set_se_translator invocation": "X lines check the recorded and returned translators only; whether a translator "
        "runs when a structured exception crosses a C++ try block belongs to exception dispatch (the runtime does "
        "not translate structured exceptions), not tested here",
    "qsort comparators": "harness comparators (int32, wrapping difference, descending, first-byte key, constant 0); "
        "the engine's own comparators run as translated code and are not reproduced",
    "heap addresses": "Z lines record success, content preservation and _msize, never addresses",
}

_spec = importlib.util.spec_from_file_location("gen_corpus", os.path.join(HERE, "gen_corpus.py"))
GEN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GEN)                       # FS_DIRS, FS_FILES, FS_ROOT_TIMES: the scratch tree

K32 = ctypes.WinDLL("kernel32", use_last_error=True)
K32.CreateFileW.restype = wintypes.HANDLE
K32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                            wintypes.DWORD, wintypes.HANDLE]
K32.SetFileTime.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 3
K32.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
K32.CloseHandle.argtypes = [wintypes.HANDLE]
INVALID_HANDLE = wintypes.HANDLE(-1).value


def long_path(p):
    return "\\\\?\\" + os.path.abspath(p)


def set_times(path, ctime, atime, wtime):
    h = K32.CreateFileW(long_path(path), 0x100, 7, None, 3, 0x02000000, None)   # FILE_WRITE_ATTRIBUTES, backup sem.
    if h in (None, INVALID_HANDLE):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fts = [wintypes.FILETIME(t & 0xFFFFFFFF, t >> 32) for t in (ctime, atime, wtime)]
        if not K32.SetFileTime(h, *[ctypes.byref(x) for x in fts]):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        K32.CloseHandle(h)


def set_attrs(path, attrs):
    if not K32.SetFileAttributesW(long_path(path), attrs or 0x80):
        raise ctypes.WinError(ctypes.get_last_error())


def fs_clear():
    if os.path.normcase(os.path.dirname(os.path.dirname(FS_ROOT))) != os.path.normcase(BUILD):
        raise SystemExit("refusing to clear %s" % FS_ROOT)
    top = long_path(FS_ROOT)
    if not os.path.lexists(top):
        return
    for dirpath, dirnames, filenames in os.walk(top):
        for n in dirnames + filenames:
            K32.SetFileAttributesW(os.path.join(dirpath, n), 0x80)
    shutil.rmtree(top)


def fs_build(t0):
    """the scratch tree of gen_corpus.FS_*: every access time t0, the root's and its parent's times fixed last"""
    fs_clear()
    os.makedirs(FS_ROOT)
    for rel, *_ in GEN.FS_DIRS:
        os.makedirs(os.path.join(FS_ROOT, rel), exist_ok=True)
    for rel, data, *_ in GEN.FS_FILES:
        with open(os.path.join(FS_ROOT, rel), "wb") as f:
            f.write(data)
    for rel, data, attrs, ct, wt in GEN.FS_FILES:
        set_times(os.path.join(FS_ROOT, rel), ct, t0, wt)
        set_attrs(os.path.join(FS_ROOT, rel), attrs)
    for rel, attrs, ct, wt in sorted(GEN.FS_DIRS, key=lambda d: -d[0].count("\\")):
        set_times(os.path.join(FS_ROOT, rel), ct, t0, wt)
        set_attrs(os.path.join(FS_ROOT, rel), attrs)
    for p in (FS_ROOT, FS_PARENT):
        set_times(p, GEN.FS_ROOT_TIMES[0], t0, GEN.FS_ROOT_TIMES[1])


def fs_snapshot():
    """the tree after a process: names, attributes, sizes and content hashes (not times)"""
    rows = []
    top = long_path(FS_ROOT)
    for dirpath, dirnames, filenames in os.walk(top):
        for n in dirnames + filenames:
            p = os.path.join(dirpath, n)
            st = os.stat(p)
            rel = os.path.relpath(p, top)
            if n in dirnames:
                rows.append("D %s %X" % (rel, st.st_file_attributes))
            else:
                rows.append("F %s %X %d %s" % (rel, st.st_file_attributes, st.st_size, sha(p)[:16]))
    return sorted(rows)


def sh(cmd, out_path):
    with open(out_path, "wb") as out:
        p = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, env=ENV)
    return p.returncode, p.stderr.decode("utf-8", "replace")


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, wintypes.WORD) for n in ("wYear", "wMonth", "wDayOfWeek", "wDay", "wHour", "wMinute", "wSecond",
                                             "wMilliseconds")]


class TIME_ZONE_INFORMATION(ctypes.Structure):
    _fields_ = [("Bias", wintypes.LONG), ("StandardName", wintypes.WCHAR * 32), ("StandardDate", SYSTEMTIME),
                ("StandardBias", wintypes.LONG), ("DaylightName", wintypes.WCHAR * 32), ("DaylightDate", SYSTEMTIME),
                ("DaylightBias", wintypes.LONG)]


def system_time_zone():
    """the system time zone as the TZ-less processes see it (GetTimeZoneInformation, independent of this process's TZ)"""
    tzi = TIME_ZONE_INFORMATION()
    rc = K32.GetTimeZoneInformation(ctypes.byref(tzi))
    return {"standard_name": tzi.StandardName, "daylight_name": tzi.DaylightName, "bias_minutes": tzi.Bias,
            "daylight_bias_minutes": tzi.DaylightBias, "dst_in_effect": rc == 2}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git(*args):
    p = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True)
    return p.stdout.strip()


def load(path):
    d = {}
    if not os.path.exists(path):
        return d
    with open(path, encoding="ascii") as f:
        for line in f:
            kind, cid, rest = (line.rstrip("\n").split(" ", 2) + [""])[:3]
            d[cid] = (kind, rest)
    return d


def wtext(h):
    if h in ("~", ""):
        return ""
    return "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h), 4))


def field(rest, key):
    for tok in rest.split(" "):
        if tok.startswith(key + "="):
            return tok[len(key) + 1:]
    return None


def canon_w(rest, stdout):
    if "EXC=" in rest:
        return rest
    r, o, n = field(rest, "R"), field(rest, "O"), field(rest, "N")
    a, b = (int(x) for x in o.split(","))
    return "R=%s OUT=%s N=%s" % (r, stdout[a:b].hex(), n)


def describe(cid, corpus_line, ref, cand):
    """human-readable view of a mismatch"""
    kind = ref[0] if ref else cand[0]
    info = {"id": cid, "case": corpus_line}
    if kind == "P" and ref and cand and "EXC" not in ref[1] + cand[1]:
        toks = corpus_line.split(" ")
        info["format"] = wtext(toks[2])
        for side, (_, rest) in (("ref", ref), ("cand", cand)):
            head = rest.split(" ; ")[0]
            info[side] = {"L": field(head, "L"), "text": wtext(field(head, "T") or "~"), "Z": field(head, "Z"),
                          "N": field(head, "N"), "trunc": rest.split(" ; ")[1:]}
    else:
        info["case"] = corpus_line[:300]
        info["ref"] = short(ref[1]) if ref else None
        info["cand"] = short(cand[1]) if cand else None
    return info


def decode_fs(text):
    """readable view of an F result, one line per op: buffers as strings, every _finddata_t decoded"""
    lines, cur = [], []

    def flush():
        if cur:
            lines.append(" ".join(cur))
            cur.clear()

    for tok in text.split(" "):
        if tok in ("cwd", "full", "cd", "ff", "find", "open"):
            flush()
            cur.append(tok)
        elif tok.startswith("D=") and len(tok) == 2 + 2 * (16 + 280 + 16):
            b = bytes.fromhex(tok[2:])[16:16 + 280]
            attrib, tc, ta, tw, size = struct.unpack("<IiiiI", b[:20])
            flush()
            lines.append("  fd: attrib=%X create=%d access=%d write=%d size=%d name=%r"
                         % (attrib, tc, ta, tw, size, b[20:].split(b"\0")[0]))
        elif tok.startswith("B=") and len(tok) > 66:
            flush()
            lines.append("  buffer: %r" % bytes.fromhex(tok[2:])[16:-16].split(b"\0")[0])
        elif tok.startswith("S=") and tok != "S=~":
            cur.append("S=%r" % bytes.fromhex(tok[2:]))
        elif tok[:2] in ("R=", "e=", "F=", "N=", "C=", "M=", "S=", "I=") or tok[:3] == "le=" or tok.startswith("EXC="):
            cur.append(tok)
    flush()
    return lines


def write_repro(cid, corpus_line, ref_text, cand_text, commit, isolated, notes=(), t0=None):
    """one-line corpus (rerunnable as is: the drivers skip '#' lines) with both results as comments"""
    os.makedirs(REPRO, exist_ok=True)
    with open(os.path.join(REPRO, cid + ".txt"), "w", encoding="ascii", newline="\n") as f:
        f.write("# crt_diff reproducer for %s (%s, commit %s)%s\n" % (
            cid, datetime.date.today().isoformat(), commit, "; one process per side" if isolated else ""))
        f.write("# rerun (both sides, the same way compare.py ran it): .venv\\Scripts\\python.exe -I "
                "experiments\\xrt\\tests\\crt_diff\\compare.py --repro experiments\\xrt\\tests\\crt_diff\\repro\\%s.txt\n"
                % cid)
        if t0 is not None:
            f.write("# t0 %d  (FILETIME of every access time in the scratch tree; --repro rebuilds the tree with it)\n" % t0)
        else:
            f.write("#   %s %s <this file> ref_out.txt\n#   %s <this file> cand_out.txt %s\n"
                    % (os.path.join(BUILD, "ref.exe"), DLL, os.path.join(BUILD, "cand.exe"), DLL_SANDBOX))
        f.write("# ref:  %s\n# cand: %s\n" % (ref_text, cand_text))
        for n in notes:
            f.write("# %s\n" % n.encode("ascii", "backslashreplace").decode())
        f.write(corpus_line + "\n")


def split_exc(rest):
    """a reference line that ends in a fault: (code, the text before it)"""
    i = rest.rfind("EXC=")
    return rest[i:i + 12], rest[:i].rstrip(" ")


def run_one(side, line, cid, cwd):
    """one corpus line in a fresh process of `side` with current directory cwd; returns the outcome
    (kind, text, prefix, info). kind: ret / pending / fault (an exception; text EXC=<code>, prefix the line written
    before it, flushed by the drivers before every call) / fatal (the candidate's xrt_fatal: text its message) /
    harness-error (never a match). info (exit status, stderr) is not compared."""
    one = os.path.join(BUILD, "iso_one.txt")
    with open(one, "w", encoding="ascii", newline="\n") as f:
        f.write(line + "\n")
    res = os.path.join(BUILD, "iso_%s.txt" % side)
    if os.path.exists(res):
        os.remove(res)
    if side == "ref":
        cmd = [os.path.join(BUILD, "ref.exe"), DLL, one, res]
    else:
        cmd = [os.path.join(BUILD, "cand.exe"), one, res, DLL_SANDBOX]
    with open(os.path.join(BUILD, "iso_%s_stdout.bin" % side), "wb") as out:
        p = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, cwd=cwd, env=ENV)
    r = load(res).get(cid)
    rc = p.returncode & 0xFFFFFFFF
    err = p.stderr.decode("utf-8", "replace").strip().replace("\n", " | ")
    info = "exit 0x%08X: %s" % (rc, err[-300:])
    partial = r[1] if r is not None else ""
    if side == "ref":
        if r is None or rc:
            return ("harness-error", "reference process without a complete result", partial, info)
        if "EXC=" in r[1]:
            code, prefix = split_exc(r[1])
            return ("fault", code, prefix, info)
        return ("ret", r[1], "", info)
    if rc >= 0xC0000000:
        return ("fault", "EXC=%08X" % rc, partial, info)
    if rc:
        fatal = [l for l in p.stderr.decode("utf-8", "replace").splitlines() if l.startswith("xrt_fatal (")]
        if fatal and "test harness" not in fatal[-1]:
            return ("fatal", fatal[-1], partial, info)
        return ("harness-error", "candidate exit 0x%08X" % rc, partial, info)
    if r is not None:
        return ("pending", "", "", info) if r[1] == "PENDING" else ("ret", r[1], "", info)
    return ("harness-error", "candidate exit 0 without a result", "", info)


def outcome_text(o):
    return "%s %s%s" % (o[0], o[1], " | before it: %s" % o[2] if o[2] else "")


def run_isolated(lines, t0):
    """E, X and F lines, each in its own reference and candidate process (F: in a freshly built scratch tree, with
    a snapshot of the tree afterwards, and a second reference run once every line has run); returns
    {id: {"ref": outcome, "cand": outcome[, "ref_tree", "cand_tree", "ref2", "ref2_tree"]}}"""
    out = {}
    for line in lines:
        cid = line.split(" ")[1]
        r = out[cid] = {}
        for side in ("ref", "cand"):
            if line.startswith("F "):
                fs_build(t0)
                r[side] = run_one(side, line, cid, FS_ROOT)
                r[side + "_tree"] = fs_snapshot()
            else:
                r[side] = run_one(side, line, cid, BUILD)
    for line in lines:
        if line.startswith("F "):
            cid = line.split(" ")[1]
            fs_build(t0)
            out[cid]["ref2"] = run_one("ref", line, cid, FS_ROOT)
            out[cid]["ref2_tree"] = fs_snapshot()
    if any(l.startswith("F ") for l in lines):
        fs_clear()
    return out


def repro(arg):
    """--repro: rerun one case on both sides as the full run does (F lines: the tree rebuilt with the reproducer's t0
    before each process, the reference twice), print the outcomes, decoded F results and tree differences"""
    path = arg if os.path.exists(arg) else os.path.join(REPRO, arg + ".txt")
    t0, line = None, None
    if os.path.exists(path):
        for l in open(path, encoding="ascii").read().splitlines():
            if l.startswith("# t0 "):
                t0 = int(l.split()[2])
            elif l and not l.startswith("#"):
                line = l
    else:                                       # an id: look it up in the generated corpus files
        for fn in ("corpus.txt", "errors.txt"):
            p = os.path.join(BUILD, fn)
            for l in (open(p, encoding="ascii") if os.path.exists(p) else []):
                if l.split(" ", 2)[1:2] == [arg]:
                    line = l.rstrip("\n")
    if not line:
        sys.exit("no corpus line in %s" % arg)
    cid = line.split(" ")[1]
    fs = line.startswith("F ")
    if fs and t0 is None:
        t0 = int(time.time()) * 10 ** 7 + 116444736000000000
    runs = {}
    for side in ("ref", "cand", "ref2"):
        if fs:
            fs_build(t0)
        runs[side] = run_one("cand" if side == "cand" else "ref", line, cid, FS_ROOT if fs else BUILD)
        if fs:
            runs[side + "_tree"] = fs_snapshot()
    if fs:
        fs_clear()
    print("case: %s" % line[:300])
    for side in ("ref", "cand", "ref2"):
        o = runs[side]
        print("%-5s %s\n      %s" % (side, outcome_text(o)[:2000], o[3][-300:]))
        if fs:
            for d in decode_fs(o[2] + " " + o[1] if o[0] != "ret" else o[1]):
                print("      " + d)
    if fs:
        for n in tree_notes(runs["ref_tree"], runs["cand_tree"], "reference tree", "candidate tree"):
            print(n)
    same_ref = runs["ref"][:3] == runs["ref2"][:3] and (not fs or runs["ref_tree"] == runs["ref2_tree"])
    same = runs["ref"][:3] == runs["cand"][:3] and runs["ref"][0] in ("ret", "fault") and \
        (not fs or runs["ref_tree"] == runs["cand_tree"])
    print("reference reproducible: %s; candidate %s" % (same_ref, "MATCHES" if same else "DIFFERS"))
    return 0 if same and same_ref else 1


def short(text):
    return text if len(text) <= 240 else "sha256:%s (%d chars)" % (hashlib.sha256(text.encode()).hexdigest()[:16], len(text))


def tree_notes(a, b, la, lb):
    """the rows in which two tree snapshots differ"""
    sa, sb = set(a or []), set(b or [])
    return ["%s only: %s" % (la, x) for x in sorted(sa - sb)] + ["%s only: %s" % (lb, x) for x in sorted(sb - sa)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write a JSON summary here")
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--i10", type=int, default=6000)
    ap.add_argument("--show", type=int, default=3, help="mismatches shown per category")
    ap.add_argument("--no-run", action="store_true", help="compare existing result files only (the isolated E/X/F "
                                                                 "lines are then not compared)")
    ap.add_argument("--repro", help="rerun one reproducer file from repro/ (or a corpus line's id) on both sides, the "
                                    "way the full run ran it, and print both results")
    a = ap.parse_args()
    if a.repro:
        return repro(a.repro)
    if a.no_run and a.json:
        sys.exit("--json needs a full run: with --no-run the isolated E/X/F lines are not compared")
    corpus = os.path.join(BUILD, "corpus.txt")
    errors = os.path.join(BUILD, "errors.txt")
    files = {s: (os.path.join(BUILD, s + "_results.txt"), os.path.join(BUILD, s + "_stdout.bin")) for s in ("ref", "cand")}
    commit = git("rev-parse", "HEAD")
    gen_cmd = [sys.executable, "-I", os.path.join(HERE, "gen_corpus.py"), corpus, "--seed", str(a.seed), "--i10",
               str(a.i10), "--errors-out", errors]
    cand_err = ""
    if not a.no_run:
        subprocess.run(gen_cmd, check=True, env=ENV)
        rc, err = sh([os.path.join(BUILD, "ref.exe"), DLL, corpus, files["ref"][0]], files["ref"][1])
        print("ref: exit %d %s" % (rc, err.strip().replace("\n", " | ")))
        if rc:
            sys.exit("reference run failed")
        rc, cand_err = sh([os.path.join(BUILD, "cand.exe"), corpus, files["cand"][0], DLL_SANDBOX], files["cand"][1])
        print("cand: exit %d %s" % (rc, cand_err.strip().replace("\n", " | ")[-2000:]))
        if rc:
            sys.exit("candidate run failed")
    lines = {}
    with open(corpus, encoding="ascii") as f:
        for line in f:
            t = line.split(" ", 2)
            if len(t) > 1:
                lines[t[1]] = line.rstrip("\n")
    err_lines = []
    if os.path.exists(errors):
        with open(errors, encoding="ascii") as f:
            err_lines = [l.rstrip("\n") for l in f if l.strip()]
    ref, cand = load(files["ref"][0]), load(files["cand"][0])
    out = {s: open(files[s][1], "rb").read() for s in files}
    cats = collections.OrderedDict()
    mism = collections.defaultdict(list)
    ref_exc = []
    if os.path.isdir(REPRO) and not a.no_run:
        for fn in os.listdir(REPRO):
            if fn.endswith(".txt"):
                os.remove(os.path.join(REPRO, fn))   # reproducers always describe the latest run
    for cid in lines:
        cat = cid.split(".")[0]
        st = cats.setdefault(cat, {"cases": 0, "mismatches": 0, "pending": 0})
        st["cases"] += 1
        r, c = ref.get(cid), cand.get(cid)
        if r is not None and c is not None and c[1] == "PENDING":
            st["pending"] += 1
            continue
        if r is None or c is None:
            st["mismatches"] += 1
            mism[cat].append({"id": cid, "case": lines[cid], "ref": r, "cand": c, "why": "missing result"})
            write_repro(cid, lines[cid], r, c, commit, False)
            continue
        if "EXC" in r[1]:
            ref_exc.append(cid)
        if r[0] == "W":
            same = canon_w(r[1], out["ref"]) == canon_w(c[1], out["cand"])
        else:
            same = r[1] == c[1]
        if not same:
            st["mismatches"] += 1
            mism[cat].append(describe(cid, lines[cid], r, c))
            write_repro(cid, lines[cid], r[1], c[1], commit, False)
    t0 = int(time.time()) * 10 ** 7 + 116444736000000000      # FILETIME of the run's start: the tree's access times
    tz_start = system_time_zone()
    isolated = run_isolated(err_lines, t0) if err_lines and not a.no_run else {}
    tz_end = system_time_zone()
    selfcheck = {"f_lines": 0, "reproducible": 0}
    not_run = 0
    for line in err_lines:
        cid = line.split(" ")[1]
        cat = cid.split(".")[0]
        st = cats.setdefault(cat, {"cases": 0, "mismatches": 0, "pending": 0})
        st["cases"] += 1
        if cid not in isolated:                 # --no-run: isolated lines only run with the processes
            st["not_run"] = st.get("not_run", 0) + 1
            not_run += 1
            continue
        st.setdefault("outcomes", {})
        res = isolated[cid]
        (rk, rt, rp, _), (ck, ct, cp, cinfo) = res["ref"], res["cand"]
        st["outcomes"][cid] = {"ref": [rk, short(rt), short(rp)], "cand": [ck, short(ct), short(cp)]}
        fs = line.startswith("F ")
        if fs:
            selfcheck["f_lines"] += 1
            same_ref = res["ref2"][:3] == res["ref"][:3] and res["ref2_tree"] == res["ref_tree"]
            st["outcomes"][cid]["reference_reproducible"] = same_ref
            if not same_ref:
                st["mismatches"] += 1
                mism[cat].append({"id": cid, "case": line[:300], "why": "reference not reproducible"})
                write_repro(cid, line, "run 1: " + outcome_text(res["ref"]), "(reference run 2) "
                            + outcome_text(res["ref2"]), commit, True,
                            ["reference run 1:"] + decode_fs(res["ref"][1] + " " + res["ref"][2]) + ["reference run 2:"]
                            + decode_fs(res["ref2"][1] + " " + res["ref2"][2])
                            + tree_notes(res["ref_tree"], res["ref2_tree"], "run 1", "run 2"), t0)
                continue
            selfcheck["reproducible"] += 1
        if ck == "pending" and rk != "harness-error":
            st["pending"] += 1
            continue
        # a fault matches only the same exception after the same output (and, for F lines, the same tree)
        same = rk == ck and rk in ("ret", "fault") and rt == ct and rp == cp and \
            (not fs or res["ref_tree"] == res["cand_tree"])
        if not same:
            st["mismatches"] += 1
            mism[cat].append({"id": cid, "case": line[:300], "ref": [rk, short(rt), short(rp)],
                              "cand": [ck, short(ct), short(cp), cinfo[-300:]]})
            notes = ["candidate process: " + cinfo]
            if fs:
                notes += (["reference:"] + decode_fs(rp + " " + rt if rk == "fault" else rt) + ["candidate:"]
                          + decode_fs(cp + " " + ct if ck != "ret" else ct)
                          + tree_notes(res["ref_tree"], res["cand_tree"], "reference tree", "candidate tree"))
            write_repro(cid, line, outcome_text(res["ref"]), outcome_text(res["cand"]), commit, True, notes,
                        t0 if fs else None)
    total = sum(s["cases"] for s in cats.values())
    bad = sum(s["mismatches"] for s in cats.values())
    pending = sum(s["pending"] for s in cats.values())
    for cat, st in cats.items():
        print("%-12s %7d cases %6d mismatches%s" % (cat, st["cases"], st["mismatches"],
                                                    " %6d PENDING" % st["pending"] if st["pending"] else ""))
    print("TOTAL        %7d cases %6d mismatches %6d PENDING (not compared: no runtime adapter); reference faults: %d"
          % (total, bad, pending, len(ref_exc)))
    if selfcheck["f_lines"]:
        print("F lines: the reference reproduced itself in %d of %d" % (selfcheck["reproducible"], selfcheck["f_lines"]))
    if not_run:
        print("%d isolated E/X/F cases NOT compared (--no-run: they run only with their processes)" % not_run)
    if tz_start != tz_end:
        print("WARNING: the system time zone state changed during the run: %s -> %s" % (tz_start, tz_end))
    for cat, lst in mism.items():
        for m in lst[:a.show]:
            print(json.dumps(m, ensure_ascii=True)[:1500])
    if bad:
        print("reproducers: %s" % os.path.relpath(REPRO, ROOT))
    if a.json:
        rt = os.path.join(ROOT, "experiments", "xrt", "runtime")
        summary = {
            "date": datetime.date.today().isoformat(),
            "provenance": {
                "commit": commit,
                "runtime_dirty": git("status", "--porcelain", "--", "experiments/xrt/runtime", "tools/xrt") or None,
                "harness_dirty": git("status", "--porcelain", "--", "experiments/xrt/tests") or None,
                "runtime_sources_sha256": {s: sha(os.path.join(rt, s)) for s in RUNTIME_SOURCES},
                "generated_sources_sha256 (git-ignored)": {s.replace("\\", "/"): sha(os.path.join(ROOT, s))
                                                           for s in GENERATED_SOURCES},
                "harness_sources_sha256": {s.replace("\\", "/"): sha(os.path.join(HERE, s)) for s in HARNESS_SOURCES},
                "corpus_sha256": {"corpus.txt": sha(corpus), "errors.txt": sha(errors)},
                "environment_removed": list(ENV_REMOVED),
                "environment_removed_were_set": sorted(k for k in os.environ if k.upper() in ENV_REMOVED),
                "ref_exe_sha256": sha(os.path.join(BUILD, "ref.exe")),
                "cand_exe_sha256": sha(os.path.join(BUILD, "cand.exe")),
                "candidate_adapters": [l.strip() for l in cand_err.splitlines()
                                       if l.startswith("bounded ") or l.startswith("dependencies ")],
                "commands": [" ".join(os.path.relpath(x, ROOT) if os.path.isabs(x) else x for x in gen_cmd),
                             "build\\crt_diff\\ref.exe <dll> corpus.txt ref_results.txt",
                             "build\\crt_diff\\cand.exe corpus.txt cand_results.txt sandbox_ref\\hellofull",
                             "per E/X/F line: ref.exe and cand.exe on a one-line corpus (F: current directory "
                             "build\\crt_diff\\fs\\root, rebuilt before each process; reference run twice)",
                             "environment of every process: compare.py's without %s" % " and ".join(ENV_REMOVED)],
            },
            "reference": {"dll": os.path.relpath(DLL, ROOT).replace("\\", "/"), "sha256": sha(DLL)},
            "corpus": {"seed": a.seed, "i10_cases": a.i10, "cases": total,
                       "isolated_cases": dict(collections.Counter(l[0] for l in err_lines)),
                       "isolated_error_cases": sum(1 for l in err_lines if l.startswith("E "))},
            "fs": {
                "root": os.path.relpath(FS_ROOT, ROOT).replace("\\", "/"),
                "tree_spec_sha256": hashlib.sha256(repr((GEN.FS_ROOT_TIMES, GEN.FS_DIRS, GEN.FS_FILES)).encode())
                                           .hexdigest(),
                "access_time_t0_filetime": t0,
                "system_time_zone_at_start": tz_start,
                "system_time_zone_changed_during_run": tz_start != tz_end,
                "acp": K32.GetACP(),
                "reference_self_check": selfcheck,
            },
            "categories": cats,
            "total_mismatches": bad,
            "pending": pending,
            "reference_faults": ref_exc,
            "mismatch_examples": {k: v[:5] for k, v in mism.items()},
            "exclusions": EXCLUSIONS,
        }
        prev = {}
        if os.path.exists(a.json):
            with open(a.json, encoding="utf-8") as f:
                prev = json.load(f)
        for k in ("extended_run", "extended_run_wide_only", "narrow_sprintf", "before_fix"):
            if k in prev:
                summary[k] = prev[k]                # hand-merged sections of one-off runs are kept
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(summary, f, indent=1, ensure_ascii=True)
            f.write("\n")
    return 1 if bad else 3 if pending or not_run else 0


if __name__ == "__main__":
    sys.exit(main())
