"""Run the msvcr70 differential test and compare (see README.md).

  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\crt_diff\\compare.py [--json results.json] [--seed N] [--i10 N]

Generates the corpus (gen_corpus.py), runs build\\crt_diff\\ref.exe (real msvcr70.dll from the read-only
sandbox copy) and build\\crt_diff\\cand.exe (runtime adapters), compares every case, prints a per-category
summary and the first mismatches, writes a reproducer for every mismatch, and optionally writes a JSON summary
with the provenance of the run.

E lines (intentional error behaviour: NULL destination, NULL format) run one case per pair of processes: the
reference catches faults with SEH, the candidate has no handler, so a fault ends its process. A fault on both
sides is a match (codes recorded); a fault on one side only is a mismatch.

Exit status: 0 every case compared and matched; 1 mismatches; 3 no mismatch but cases PENDING (a bounded
function whose runtime adapter does not exist yet: never counted as passed).
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
BUILD = os.path.join(ROOT, "experiments", "xrt", "build", "crt_diff")
DLL = os.path.join(ROOT, "sandbox_ref", "hellofull", "System", "msvcr70.dll")
REPRO = os.path.join(HERE, "repro")
RUNTIME_SOURCES = ["xrt_fmt.c", "hle_msvcr70.c", "xrt_mem.c", "xrt.h", "xrt_internal.h"]
EXCLUSIONS = {
    "_snwprintf": "not imported by UCC.exe, Core.dll, Engine.dll, GlmLib.dll or Editor.dll",
    "vsprintf, swprintf": "unbounded variants imported by Engine.dll/GlmLib.dll; no runtime adapter; outside the "
                          "bounded-printf target (sprintf itself is covered by the A lines)",
    "outputs of 16384 characters or more": "B lines: SKIP (the measuring call has a 16384-character capacity)",
    "F2 (ACP 932 command-line splitting)": "separate test experiments/xrt/tests/f2_mbcs_argv, open, not part of this "
                                           "formatter result",
}


def sh(cmd, out_path):
    with open(out_path, "wb") as out:
        p = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE)
    return p.returncode, p.stderr.decode("utf-8", "replace")


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
        info["ref"] = ref[1] if ref else None
        info["cand"] = cand[1] if cand else None
    return info


def write_repro(cid, corpus_line, ref_text, cand_text, commit, isolated):
    """one-line corpus (rerunnable as is: the drivers skip '#' lines) with both results as comments"""
    os.makedirs(REPRO, exist_ok=True)
    with open(os.path.join(REPRO, cid + ".txt"), "w", encoding="ascii", newline="\n") as f:
        f.write("# crt_diff reproducer for %s (%s, runtime %s)%s\n" % (
            cid, datetime.date.today().isoformat(), commit, "; error case: run it in its own processes" if isolated else ""))
        f.write("#   experiments\\xrt\\build\\crt_diff\\ref.exe sandbox_ref\\hellofull\\System\\msvcr70.dll <this file> ref_out.txt\n")
        f.write("#   experiments\\xrt\\build\\crt_diff\\cand.exe <this file> cand_out.txt\n")
        f.write("# ref:  %s\n# cand: %s\n" % (ref_text, cand_text))
        f.write(corpus_line + "\n")


def run_isolated(lines):
    """E lines: each in its own reference and candidate process; returns {id: (ref_outcome, cand_outcome)}"""
    out = {}
    one = os.path.join(BUILD, "err_one.txt")
    for line in lines:
        cid = line.split(" ")[1]
        with open(one, "w", encoding="ascii", newline="\n") as f:
            f.write(line + "\n")
        rr, cr = os.path.join(BUILD, "err_ref.txt"), os.path.join(BUILD, "err_cand.txt")
        for p in (rr, cr):
            if os.path.exists(p):
                os.remove(p)
        rc_ref, _ = sh([os.path.join(BUILD, "ref.exe"), DLL, one, rr], os.path.join(BUILD, "err_ref_stdout.bin"))
        rc_cand, _ = sh([os.path.join(BUILD, "cand.exe"), one, cr], os.path.join(BUILD, "err_cand_stdout.bin"))
        ref, cand = load(rr).get(cid), load(cr).get(cid)
        if ref is None:
            ref_o = ("harness-error", "reference process exit %d without a result" % rc_ref)
        elif "EXC=" in ref[1]:
            ref_o = ("fault", ref[1])
        else:
            ref_o = ("ret", ref[1])
        if cand is not None and cand[1] == "PENDING":
            cand_o = ("pending", "")
        elif cand is not None:
            cand_o = ("ret", cand[1])
        elif rc_cand != 0:
            cand_o = ("fault", "process exit 0x%08X" % (rc_cand & 0xFFFFFFFF))
        else:
            cand_o = ("harness-error", "candidate exit 0 without a result")
        out[cid] = (ref_o, cand_o)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write a JSON summary here")
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--i10", type=int, default=6000)
    ap.add_argument("--show", type=int, default=3, help="mismatches shown per category")
    ap.add_argument("--no-run", action="store_true", help="compare existing result files only")
    a = ap.parse_args()
    corpus = os.path.join(BUILD, "corpus.txt")
    errors = os.path.join(BUILD, "errors.txt")
    files = {s: (os.path.join(BUILD, s + "_results.txt"), os.path.join(BUILD, s + "_stdout.bin")) for s in ("ref", "cand")}
    commit = git("rev-parse", "HEAD")
    gen_cmd = [sys.executable, "-I", os.path.join(HERE, "gen_corpus.py"), corpus, "--seed", str(a.seed), "--i10",
               str(a.i10), "--errors-out", errors]
    cand_err = ""
    if not a.no_run:
        subprocess.run(gen_cmd, check=True)
        rc, err = sh([os.path.join(BUILD, "ref.exe"), DLL, corpus, files["ref"][0]], files["ref"][1])
        print("ref: exit %d %s" % (rc, err.strip().replace("\n", " | ")))
        if rc:
            sys.exit("reference run failed")
        rc, cand_err = sh([os.path.join(BUILD, "cand.exe"), corpus, files["cand"][0]], files["cand"][1])
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
    isolated = run_isolated(err_lines) if err_lines and not a.no_run else {}
    for line in err_lines:
        cid = line.split(" ")[1]
        if cid not in isolated:
            continue
        cat = cid.split(".")[0]
        st = cats.setdefault(cat, {"cases": 0, "mismatches": 0, "pending": 0})
        st.setdefault("outcomes", {})
        st["cases"] += 1
        (rk, rt), (ck, ct) = isolated[cid]
        st["outcomes"][cid] = {"ref": [rk, rt], "cand": [ck, ct]}
        if ck == "pending" and rk != "harness-error":
            st["pending"] += 1
            continue
        if not ((rk == ck == "fault") or (rk == ck == "ret" and rt == ct)):
            st["mismatches"] += 1
            mism[cat].append({"id": cid, "case": line, "ref": [rk, rt], "cand": [ck, ct]})
            write_repro(cid, line, "%s %s" % (rk, rt), "%s %s" % (ck, ct), commit, True)
    total = sum(s["cases"] for s in cats.values())
    bad = sum(s["mismatches"] for s in cats.values())
    pending = sum(s["pending"] for s in cats.values())
    for cat, st in cats.items():
        print("%-12s %7d cases %6d mismatches%s" % (cat, st["cases"], st["mismatches"],
                                                    " %6d PENDING" % st["pending"] if st["pending"] else ""))
    print("TOTAL        %7d cases %6d mismatches %6d PENDING (not compared: no runtime adapter); reference faults: %d"
          % (total, bad, pending, len(ref_exc)))
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
                "runtime_sources_sha256": {s: sha(os.path.join(rt, s)) for s in RUNTIME_SOURCES},
                "ref_exe_sha256": sha(os.path.join(BUILD, "ref.exe")),
                "cand_exe_sha256": sha(os.path.join(BUILD, "cand.exe")),
                "candidate_adapters": [l.strip() for l in cand_err.splitlines() if l.startswith("bounded ")],
                "commands": [" ".join(os.path.relpath(x, ROOT) if os.path.isabs(x) else x for x in gen_cmd),
                             "build\\crt_diff\\ref.exe <dll> corpus.txt ref_results.txt",
                             "build\\crt_diff\\cand.exe corpus.txt cand_results.txt",
                             "per E line: ref.exe and cand.exe on a one-line corpus"],
            },
            "reference": {"dll": os.path.relpath(DLL, ROOT).replace("\\", "/"), "sha256": sha(DLL)},
            "corpus": {"seed": a.seed, "i10_cases": a.i10, "cases": total, "isolated_error_cases": len(err_lines)},
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
    return 1 if bad else 3 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
