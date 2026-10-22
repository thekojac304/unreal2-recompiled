"""Run the msvcr70 differential test and compare (see README.md).

  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\crt_diff\\compare.py [--json results.json]

Generates the corpus (gen_corpus.py), runs build\\crt_diff\\ref.exe (real msvcr70.dll from the read-only
sandbox copy) and build\\crt_diff\\cand.exe (runtime adapters), compares every case, prints a per-category
summary and the first mismatches, and optionally writes a JSON summary.
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


def sh(cmd, out_path):
    with open(out_path, "wb") as out:
        p = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE)
    return p.returncode, p.stderr.decode("utf-8", "replace")


def load(path):
    d = {}
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
    kind = ref[0]
    info = {"id": cid, "case": corpus_line}
    if kind == "P" and "EXC" not in ref[1] + cand[1]:
        toks = corpus_line.split(" ")
        info["format"] = wtext(toks[2])
        for side, (_, rest) in (("ref", ref), ("cand", cand)):
            head = rest.split(" ; ")[0]
            info[side] = {"L": field(head, "L"), "text": wtext(field(head, "T") or "~"), "Z": field(head, "Z"),
                          "N": field(head, "N"), "trunc": rest.split(" ; ")[1:]}
    else:
        info["ref"] = ref[1]
        info["cand"] = cand[1]
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write a JSON summary here")
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--i10", type=int, default=6000)
    ap.add_argument("--show", type=int, default=3, help="mismatches shown per category")
    ap.add_argument("--no-run", action="store_true", help="compare existing result files only")
    a = ap.parse_args()
    corpus = os.path.join(BUILD, "corpus.txt")
    files = {s: (os.path.join(BUILD, s + "_results.txt"), os.path.join(BUILD, s + "_stdout.bin")) for s in ("ref", "cand")}
    if not a.no_run:
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "gen_corpus.py"), corpus, "--seed", str(a.seed),
                        "--i10", str(a.i10)], check=True)
        rc, err = sh([os.path.join(BUILD, "ref.exe"), DLL, corpus, files["ref"][0]], files["ref"][1])
        print("ref: exit %d %s" % (rc, err.strip().replace("\n", " | ")))
        if rc:
            sys.exit("reference run failed")
        rc, err = sh([os.path.join(BUILD, "cand.exe"), corpus, files["cand"][0]], files["cand"][1])
        print("cand: exit %d %s" % (rc, err.strip().replace("\n", " | ")[-2000:]))
        if rc:
            sys.exit("candidate run failed")
    lines = {}
    with open(corpus, encoding="ascii") as f:
        for line in f:
            t = line.split(" ", 2)
            if len(t) > 1:
                lines[t[1]] = line.rstrip("\n")
    ref, cand = load(files["ref"][0]), load(files["cand"][0])
    out = {s: open(files[s][1], "rb").read() for s in files}
    cats = collections.OrderedDict()
    mism = collections.defaultdict(list)
    ref_exc = []
    for cid in lines:
        cat = cid.split(".")[0]
        st = cats.setdefault(cat, {"cases": 0, "mismatches": 0})
        st["cases"] += 1
        r, c = ref.get(cid), cand.get(cid)
        if r is None or c is None:
            st["mismatches"] += 1
            mism[cat].append({"id": cid, "case": lines[cid], "ref": r, "cand": c, "why": "missing result"})
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
    total = sum(s["cases"] for s in cats.values())
    bad = sum(s["mismatches"] for s in cats.values())
    for cat, st in cats.items():
        print("%-10s %7d cases %6d mismatches" % (cat, st["cases"], st["mismatches"]))
    print("TOTAL      %7d cases %6d mismatches; reference faults: %d" % (total, bad, len(ref_exc)))
    for cat, lst in mism.items():
        for m in lst[:a.show]:
            print(json.dumps(m, ensure_ascii=True)[:1500])
    if a.json:
        h = hashlib.sha256(open(DLL, "rb").read()).hexdigest()
        summary = {
            "date": datetime.date.today().isoformat(),
            "reference": {"dll": os.path.relpath(DLL, ROOT).replace("\\", "/"), "sha256": h},
            "corpus": {"seed": a.seed, "i10_cases": a.i10, "cases": total},
            "categories": cats,
            "total_mismatches": bad,
            "reference_faults": ref_exc,
            "mismatch_examples": {k: v[:5] for k, v in mism.items()},
        }
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(summary, f, indent=1, ensure_ascii=True)
            f.write("\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
