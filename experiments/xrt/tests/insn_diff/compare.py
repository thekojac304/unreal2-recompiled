"""Compares the native and lifted outputs of the differential instruction test (see README.md).

Only architecturally defined outputs are compared (Intel SDM): EFLAGS through the per-case mask that
gen.py computed (undefined flags masked, AF never compared), x87 C0/C2/C3 only where the instruction
defines them, ST(i) only for registers that are not empty on the hardware. Outputs the model
deliberately does not represent are counted separately as "model" categories, never as failures:
  x87-not-a-double     the hardware register holds a value outside double precision/range (80-bit model limit)
  x87-transcendental   fsin/fcos/fptan/fpatan/fyl2x/f2xm1 differ (host libm; ULP distance recorded)
  x87-nan-payload      both results are NaN, with different sign/payload bits
  x87-c1               FSW.C1 (the model never sets it)
  x87-exception-flags  FSW exception/summary bits (not modelled; all exceptions are masked)
  fnstsw-unmodelled    the same bits seen through fnstsw ax (AL, C1, and C0/C2/C3 where undefined)

Writes experiments/xrt/tests/insn_diff/results.json and build/insn_diff/mismatches.txt.
Usage: python -I compare.py
"""
import collections
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BUILD = os.path.join(WS, "experiments", "xrt", "build", "insn_diff")

OUT_FMT = struct.Struct("<II8IIHHHHI8dQQHH" + "HBB" * 24)
IN_FMT = struct.Struct("<II8IIIHHI8d" + "IB3x8s" * 4)
EXP_FMT = struct.Struct("<HHB")
STATUS = {0: "ok", 1: "#DE", 2: "exception", 3: "trap", 4: "fatal", 5: "other"}
FAIL = ("status", "gpr", "eflags", "memory", "x87-top", "x87-cc", "x87-fcw", "x87-value", "oracle")
MODEL = ("x87-not-a-double", "x87-transcendental", "x87-nan-payload", "x87-c1", "x87-exception-flags",
         "fnstsw-unmodelled", "fatal-by-design")
# Failures whose cause was traced outside the lifter (reported, not fixed here: runtime/*.c is not edited
# by this test). Keyed by form; the text is copied into results.json.
ATTRIBUTION = {
    "fsin": "runtime xrt_cpu.c trig_out_of_range(): NaN/inf operands take the |x|>=2^63 path (C2=1, operand "
            "unchanged); hardware returns a QNaN with C2=0",
    "fcos": "runtime xrt_cpu.c trig_out_of_range(): NaN/inf operands take the |x|>=2^63 path (C2=1, operand "
            "unchanged); hardware returns a QNaN with C2=0",
    "fptan": "runtime xrt_cpu.c trig_out_of_range(): NaN/inf operands take the |x|>=2^63 path (C2=1, nothing "
             "pushed); hardware stores QNaN, pushes, C2=0",
}
REGS = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"]


class Out:
    __slots__ = ("status", "excode", "r", "eflags", "fcw", "fsw", "valid", "exact", "hfs", "st", "hdata",
                 "hstack", "nchg", "chg")

    def __init__(self, t):
        self.status, self.excode = t[0], t[1]
        self.r = t[2:10]
        self.eflags, self.fcw, self.fsw, self.valid, self.exact, self.hfs = t[10], t[11], t[12], t[13], t[14], t[15]
        self.st = t[16:24]
        self.hdata, self.hstack, self.nchg = t[24], t[25], t[26]
        self.chg = [(t[28 + 3 * i], t[29 + 3 * i]) for i in range(min(self.nchg, 24))]


def bits(d):
    return struct.unpack("<Q", struct.pack("<d", d))[0]


def ordered(d):
    b = struct.unpack("<q", struct.pack("<d", d))[0]
    return b if b >= 0 else -(b & 0x7FFFFFFFFFFFFFFF)


def isnan(d):
    return d != d


def read_cases(path):
    with open(path, "rb") as f:
        hdr = f.read(16)
        nsnip, ncase = struct.unpack("<II", hdr[8:16])
        f.seek(16 + 8 * nsnip)
        bl = struct.unpack("<I", f.read(4))[0]
        f.seek(16 + 8 * nsnip + 4 + bl)
        data = f.read(IN_FMT.size * ncase)
    return [IN_FMT.unpack_from(data, i * IN_FMT.size) for i in range(ncase)]


def read_out(path, n):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) != n * OUT_FMT.size:
        sys.exit(f"{path}: {len(data)} bytes, expected {n} records of {OUT_FMT.size}")
    return [Out(t) for t in OUT_FMT.iter_unpack(data)]


def fmt_in(k):
    r = " ".join(f"{REGS[i]}={k[2 + i]:08x}" for i in range(8))
    s = f"{r} efl={k[10]:03x}"
    if k[11]:
        s += " st=[" + ", ".join(repr(k[15 + i]) for i in range(k[11])) + "]"
    pt = [(k[23 + 3 * j], k[24 + 3 * j], k[25 + 3 * j]) for j in range(4)]
    pts = [f"{a:08x}:{b[:ln].hex()}" for a, ln, b in pt if ln]
    if pts:
        s += " mem " + " ".join(pts)
    return s


def fmt_out(o):
    if o.status:
        return f"status={STATUS.get(o.status, o.status)} code={o.excode:08x}"
    r = " ".join(f"{REGS[i]}={o.r[i]:08x}" for i in range(8))
    s = f"{r} efl={o.eflags & 0xCD5:03x} fsw={o.fsw:04x} fcw={o.fcw:04x}"
    nv = bin(o.valid).count("1")
    if o.valid != 0xFF or o.exact != 0xFF:
        s += f" valid={o.valid:02x} exact={o.exact:02x}"
    s += " st=[" + ", ".join(f"{o.st[i]!r}" for i in range(min(nv, 8))) + "]"
    s += f" chg={o.nchg}:" + ",".join(f"{off:x}={v:02x}" for off, v in o.chg)
    return s


def compare_case(sn, k, e, n, l, ulps):
    """List of (category, detail) for one case."""
    fmask, ccmask, eflags = e
    issues = []
    if n.status != l.status:
        if (eflags & 2) and n.status == 0 and l.status == 4:
            return [("fatal-by-design", "lifted runtime refuses this x87 control word (xrt_fldcw)")]
        return [("status", f"native {STATUS.get(n.status)} lifted {STATUS.get(l.status)}")]
    if (eflags & 1) and n.status != 1:
        issues.append(("oracle", "gen.py predicted #DE, hardware did not"))
    if n.status != 0:
        return issues
    texts = sn["text"]
    gmask = [0xFFFFFFFF] * 8
    unmod = [0] * 8
    if "fnstsw ax" in texts:
        cc = 0x4500 if sn["family"] == "x87seq" else 0
        gmask[0] = 0xFFFF0000 | 0x3800 | cc
        unmod[0] = 0xFFFF & ~gmask[0]
    for i in range(8):
        d = (n.r[i] ^ l.r[i])
        if d & gmask[i]:
            issues.append(("gpr", f"{REGS[i]} native {n.r[i]:08x} lifted {l.r[i]:08x}"))
        elif d & unmod[i]:
            issues.append(("fnstsw-unmodelled", f"{REGS[i]} bits {d & unmod[i]:04x}"))
    d = (n.eflags ^ l.eflags) & fmask
    if d:
        names = [nm for b, nm in ((1, "CF"), (4, "PF"), (0x40, "ZF"), (0x80, "SF"), (0x400, "DF"), (0x800, "OF")) if d & b]
        issues.append(("eflags", f"{'/'.join(names)} native {n.eflags & 0xCD5:03x} lifted {l.eflags & 0xCD5:03x}"))
    if n.hdata != l.hdata or n.hstack != l.hstack:
        issues.append(("memory", f"native {n.nchg} changed {n.chg[:8]} lifted {l.nchg} changed {l.chg[:8]}"))
    if n.hfs != l.hfs:
        issues.append(("memory", f"TEB ExceptionList/ArbitraryUserPointer differ (fs: writes)"))
    if (n.fsw ^ l.fsw) & 0x3800:
        issues.append(("x87-top", f"native TOP {n.fsw >> 11 & 7} lifted {l.fsw >> 11 & 7}"))
    if (n.fsw ^ l.fsw) & ccmask:
        issues.append(("x87-cc", f"native fsw {n.fsw:04x} lifted {l.fsw:04x} (defined {ccmask:04x})"))
    if (n.fsw ^ l.fsw) & 0x200:
        issues.append(("x87-c1", f"native C1={n.fsw >> 9 & 1}"))
    if (n.fsw ^ l.fsw) & 0x80FF:
        issues.append(("x87-exception-flags", f"native {n.fsw & 0x80FF:04x} lifted {l.fsw & 0x80FF:04x}"))
    if n.fcw != l.fcw:
        issues.append(("x87-fcw", f"native {n.fcw:04x} lifted {l.fcw:04x}"))
    mode = sn.get("x87", {}).get("mode", "exact")
    for i in range(8):
        if not (n.valid >> i & 1):
            continue
        a, b = n.st[i], l.st[i]
        if mode != "ulp" and not (n.exact >> i & 1):
            # the hardware register holds a value that is not a double (64-bit significand or exponent
            # beyond double range): a model limitation even when its rounding equals the lifted value
            same = "equals" if bits(a) == bits(b) else "differs from"
            issues.append(("x87-not-a-double", f"ST({i}) native ~{a!r} (not a double; rounded {same} lifted) "
                                               f"lifted {b!r}"))
            continue
        if bits(a) == bits(b):
            if mode == "ulp":
                ulps[0] += 1
            continue
        if isnan(a) and isnan(b):
            issues.append(("x87-nan-payload", f"ST({i}) native {bits(a):016x} lifted {bits(b):016x}"))
        elif mode == "ulp":
            u = abs(ordered(a) - ordered(b)) if not (isnan(a) or isnan(b) or math.isinf(a) or math.isinf(b)) else -1
            ulps[min(u, 3) if u >= 0 else 4] += 1
            issues.append(("x87-transcendental", f"ST({i}) native {a!r} lifted {b!r} ulp={u}"))
        elif not (n.exact >> i & 1):
            issues.append(("x87-not-a-double", f"ST({i}) native ~{a!r} (not a double) lifted {b!r}"))
        else:
            issues.append(("x87-value", f"ST({i}) native {a!r} lifted {b!r}"))
    return issues


def main():
    args = sys.argv[1:]
    lifted_path = args[args.index("--lifted") + 1] if "--lifted" in args else os.path.join(BUILD, "out_lifted.bin")
    write = "--no-write" not in args
    quiet = "--quiet" in args
    with open(os.path.join(BUILD, "snippets.json"), encoding="utf-8") as f:
        sj = json.load(f)
        snips = sj["snippets"]
    with open(os.path.join(BUILD, "census.json"), encoding="utf-8") as f:
        census = json.load(f)
    cases = read_cases(os.path.join(BUILD, "cases.bin"))
    with open(os.path.join(BUILD, "expect.bin"), "rb") as f:
        exps = list(EXP_FMT.iter_unpack(f.read()))
    nat = read_out(os.path.join(BUILD, "out_native.bin"), len(cases))
    lif = read_out(lifted_path, len(cases))
    per_form = collections.OrderedDict()
    per_family = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)
    ulps = collections.Counter()
    status_pairs = collections.Counter()
    de_kinds = collections.defaultdict(collections.Counter)
    for idx in range(len(cases)):
        k, e, n, l = cases[idx], exps[idx], nat[idx], lif[idx]
        sn = snips[k[0]]
        u = [0] * 5
        issues = compare_case(sn, k, e, n, l, u)
        for j, v in enumerate(u):
            if v:
                ulps[["0", "1", "2", ">=3", "inf/nan"][j]] += v
        status_pairs[(STATUS.get(n.status), STATUS.get(l.status))] += 1
        form = sn["form"]
        pf = per_form.setdefault(form, {"cases": 0, "snippets": set(), "encodings": set(), "variants": set(),
                                        "failed_cases": 0, "categories": collections.Counter(), "de_cases": 0,
                                        "family": sn["family"]})
        pf["cases"] += 1
        pf["snippets"].add(k[0])
        pf["encodings"].add(sn["enc"])
        pf["variants"].add(sn["variant"].split(" imm=")[0])
        if n.status == 1 and l.status == 1:
            pf["de_cases"] += 1
            de_kinds[form]["divide-by-zero" if n.excode == 0xC0000094 else "quotient-overflow"
                           if n.excode == 0xC0000095 else f"{n.excode:08x}"] += 1
        cats = {c for c, _ in issues}
        if cats & set(FAIL):
            pf["failed_cases"] += 1
        for c in cats:
            pf["categories"][c] += 1
            per_family[sn["family"]][c] += 1
        per_family[sn["family"]]["cases"] += 1
        for c, detail in issues:
            key = (form, c)
            if len(examples[key]) < 4:
                examples[key].append((idx, sn, k, n, l, detail))
    total_fail = sum(p["failed_cases"] for p in per_form.values())
    forms_out = {}
    for form, p in per_form.items():
        cen = census["forms"].get(form)
        forms_out[form] = {
            "family": p["family"], "census_count": cen["count"] if cen else 0, "in_census": bool(cen),
            "encodings": len(p["encodings"]), "census_encodings": len(cen["encodings"]) if cen else 0,
            "snippets": len(p["snippets"]), "variants": sorted(p["variants"]), "cases": p["cases"],
            "de_cases": p["de_cases"], "failed_cases": p["failed_cases"],
            "categories": dict(p["categories"]),
        }
        if form in de_kinds:
            forms_out[form]["de_kinds"] = dict(de_kinds[form])
        if p["failed_cases"] and form in ATTRIBUTION:
            forms_out[form]["attribution"] = ATTRIBUTION[form]
    summary = {
        "snippets": len(snips), "cases": len(cases), "forms": len(per_form),
        "census_forms": len(census["forms"]),
        "census_forms_covered": sum(1 for f in census["forms"] if f in per_form),
        "census_encodings": sum(len(f["encodings"]) for f in census["forms"].values()),
        "census_encodings_covered": sum(1 for f, fd in census["forms"].items() for ek in fd["encodings"]
                                        if f in per_form and ek in per_form[f]["encodings"]),
        "failed_cases": total_fail,
        "failed_cases_census_forms": sum(p["failed_cases"] for fm, p in per_form.items() if fm in census["forms"]),
        "failed_cases_extended_forms": sum(p["failed_cases"] for fm, p in per_form.items()
                                           if fm not in census["forms"]),
        "failed_cases_unattributed": sum(p["failed_cases"] for fm, p in per_form.items() if fm not in ATTRIBUTION),
        "failure_categories": {c: sum(p["categories"].get(c, 0) for p in per_form.values()) for c in FAIL},
        "model_categories": {c: sum(p["categories"].get(c, 0) for p in per_form.values()) for c in MODEL},
        "status_pairs": {f"{a}/{b}": v for (a, b), v in status_pairs.items()},
        "transcendental_ulp_histogram": dict(ulps),
        "families": {f: dict(c) for f, c in sorted(per_family.items())},
    }
    summary["seed"], summary["scale"] = sj.get("seed"), sj.get("scale")
    res = {"summary": summary,
           "census": {"instructions_decoded": census["modules"], "excluded": census["excluded"],
                      "addressing_modes": census["addr_modes"], "fnstsw_ax_consumers": census["fnstsw_ax_consumers"]},
           "extended_not_implemented": sj.get("extended_unsupported", []),
           "forms": forms_out}
    mc = os.path.join(BUILD, "mutation_check.json")
    if os.path.exists(mc):
        with open(mc, encoding="utf-8") as f:
            res["mutation_check"] = json.load(f)
    if not write:
        bad = sorted(((p["failed_cases"], form) for form, p in per_form.items() if p["failed_cases"]), reverse=True)
        print(f"failed cases: {total_fail}; forms: " + ", ".join(f"{fm} ({cnt})" for cnt, fm in bad[:12]))
        return 1 if total_fail else 0
    name = args[args.index("--results") + 1] if "--results" in args else "results.json"
    with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(BUILD, "mismatches.txt"), "w", encoding="utf-8", newline="\n") as f:
        for (form, c), exs in sorted(examples.items(), key=lambda kv: (kv[0][1] not in FAIL, kv[0])):
            f.write(f"=== {form} :: {c} ({per_form[form]['categories'][c]} cases)\n")
            for idx, sn, k, n, l, detail in exs:
                f.write(f"  case {idx} snippet {k[0]} [{sn['variant']}] {sn['text']}  ({sn['bytes']})\n")
                f.write(f"    {detail}\n    in:     {fmt_in(k)}\n    native: {fmt_out(n)}\n    lifted: {fmt_out(l)}\n")
    if not quiet:
        print(json.dumps(summary, indent=1))
    bad = sorted(((p["failed_cases"], form) for form, p in per_form.items() if p["failed_cases"]), reverse=True)
    for cnt, form in bad[:40]:
        print(f"  FAIL {cnt:6}  {form}  {dict(per_form[form]['categories'])}")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
