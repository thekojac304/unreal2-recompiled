"""Gate-F CRT differential test: the runtime's msvcr70 adapters for qsort, atof, _CIpow, _CIfmod, _isnan, toupper,
strchr, _stricmp and atoi against the real msvcr70.dll (x86, sandbox copy).

Usage (workspace root, after build.cmd):
  .venv\\Scripts\\python -I tools\\xrt\\tests\\crt_gatef\\compare.py [--seed N] [--scale K] [--inputs FILE] [--json OUT]
--inputs adds operand lines recorded by the runtime (XRT_MATH_LOG, see hle_msvcr70.c) from a real run.
Exit status 0 only when every case matches. The corpus and raw results stay in experiments/xrt/build/crt_gatef/.
"""
import argparse
import json
import math
import os
import random
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(WS, "experiments", "xrt", "build", "crt_gatef")
SB = os.path.join(WS, "sandbox_cmp", "crt_gatef")


def dbits(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def hexs(b):
    return b.hex() if b else "-"


SPECIAL = [0.0, -0.0, 1.0, -1.0, 2.0, 0.5, -0.5, 3.0, 10.0, 1e-300, 1e300, 5e-324, 2.2250738585072014e-308,
           1.7976931348623157e308, math.inf, -math.inf, math.nan, math.pi, math.e, 0.1, 255.0, 1.0 / 255.0]
NAN_BITS = [0x7FF8000000000000, 0xFFF8000000000000, 0x7FF0000000000001, 0x7FF4000000000000, 0x7FFFFFFFFFFFFFFF,
            0xFFF0000000000001, 0x7FF8000000000001, 0x7FF0000000080000, 0x7FF0000100000000]


# Inputs that once failed, kept as regression cases: host pow() is 1 ulp off msvcr70's SSE2 pow on these (the last
# two are among VMProbe's real inputs: Engine's 3072-entry table of x^-0.5), pow(NaN, 0) goes through the DLL's math
# error handler, and msvcr70's fmod departs from C99 on zero/infinite operands.
REGRESSIONS = [
    "pow 3ff3900000000000 bfe0000000000000", "pow 3ffa380000000000 bfe0000000000000",
    "pow 401c000000000000 4033000000000000", "pow 4024000000000000 4037000000000000",
    "pow 4022000000000000 4031000000000000", "pow c034000000000000 4037000000000000",
    "pow 3fdb100000000000 3ff9ce6c091f3279", "pow 3fb8181818181818 4009d651b7d539e6",
    "pow 400bfbfbfbfbfbfc 3fe0000000000000", "pow 3fc8ead65b7a3284 4008000000000000",
    "pow 4021630a5a8f49d1 c01c000000000000", "pow 7fefffffffffffff 3fe0000000000000",
    "pow 7ff8000000000000 0000000000000000", "pow 7ff8000000000000 8000000000000000",
    "pow 3ff0000000000000 7ff0000000000000", "pow bff0000000000000 fff0000000000000",
    "fmod 8000000000000000 3ff0000000000000", "fmod 3ff0000000000000 7ff0000000000000",
    "fmod 7ff0000000000000 3ff0000000000000", "fmod 3ff0000000000000 0000000000000000",
    "fmod 7ff0000000000001 4000000000000000",
]


def gen_pow(rnd, scale, lines):
    lines.extend(REGRESSIONS)
    for x in SPECIAL:
        for y in SPECIAL:
            lines.append(f"pow {dbits(x):016x} {dbits(y):016x}")
            lines.append(f"fmod {dbits(x):016x} {dbits(y):016x}")
    for b in NAN_BITS:
        lines.append(f"pow {b:016x} {dbits(2.0):016x}")
        lines.append(f"pow {dbits(2.0):016x} {b:016x}")
        lines.append(f"fmod {b:016x} {dbits(2.0):016x}")
    for xi in range(-20, 21):              # integer powers, as UnrealScript ** and table builders use them
        for yi in range(-12, 25):
            lines.append(f"pow {dbits(float(xi)):016x} {dbits(float(yi)):016x}")
    for _ in range(4000 * scale):          # gamma-table-like arguments: base in [0, 1], exponents 0.1 .. 4
        x = rnd.randint(0, 1023) / rnd.choice([255.0, 1023.0, 1024.0, 1.0 * rnd.randint(1, 4096)])
        y = rnd.choice([1 / 2.2, 2.2, 1 / 1.7, 0.5, 1.5, 2.0, 3.0]) if rnd.random() < 0.5 else rnd.uniform(0.05, 4.0)
        lines.append(f"pow {dbits(x):016x} {dbits(y):016x}")
    for _ in range(6000 * scale):
        x = rnd.choice([rnd.uniform(0, 10), rnd.uniform(0, 1e3), math.exp(rnd.uniform(-700, 700)), -rnd.uniform(0, 10)])
        y = rnd.choice([rnd.uniform(-10, 10), float(rnd.randint(-30, 30)), rnd.uniform(-300, 300), rnd.uniform(-1, 1)])
        lines.append(f"pow {dbits(x):016x} {dbits(y):016x}")
    for _ in range(6000 * scale):
        x = rnd.choice([rnd.uniform(-1e6, 1e6), rnd.uniform(-10, 10), math.ldexp(rnd.random(), rnd.randint(-1074, 1023))])
        y = rnd.choice([rnd.uniform(-10, 10), rnd.uniform(-1e-3, 1e-3), math.ldexp(rnd.random(), rnd.randint(-1074, 1023)),
                        float(rnd.randint(-100, 100))])
        lines.append(f"fmod {dbits(x):016x} {dbits(y):016x}")


def gen_isnan(rnd, scale, lines):
    for x in SPECIAL:
        lines.append(f"isnan {dbits(x):016x}")
    for b in NAN_BITS:
        lines.append(f"isnan {b:016x}")
    for _ in range(3000 * scale):
        e = rnd.choice([0, 0x7FF, 0x7FE, 1, rnd.randint(0, 0x7FF)])
        m = rnd.choice([0, 1, 1 << 51, (1 << 52) - 1, 1 << 19, rnd.getrandbits(52)])
        lines.append(f"isnan {(rnd.getrandbits(1) << 63) | (e << 52) | m:016x}")


def atof_strings(rnd, scale):
    s = ["0", "-0", "+0", "1", "-1", "1.5", ".5", "5.", ".", "-", "+", "", " ", "abc", "1e", "1e+", "1e-", "1E5", "1d5",
         "1D5", "1e5x", "  \t\n\v\f\r12.25", "1e309", "-1e309", "1e-400", "1e5201", "1e-5201", "1e99999999999", "0e99999",
         "0.000000000000000000000000000000001e40", "1.7976931348623157e308", "1.7976931348623158e308",
         "1.7976931348623159e308", "2.2250738585072014e-308", "2.2250738585072011e-308", "4.9e-324", "2.4703282292062328e-324",
         "2.4703282292062327e-324", "9007199254740993", "9007199254740995", "9007199254740997", "0.1", "0.2", "0.3",
         "123456789012345678901234567890", "1234567890123456789012345", "123456789012345678901234", "99999999999999999999999999",
         "0.1000000000000000055511151231257827021181583404541015625", "inf", "nan", "INF", "0x10", "1,5", "1 5", "--1",
         "+-1", "1e+-5", "12+3", "12-3", "3.25", "-17", "42", "1.0", "0.5", "2.25", "1024", "0.333333", "1e10",
         "00000123.4500000", "000.000", "1.e5", ".e5", "+.5", "-.5e-3", "1e0005", "1e-0005", "\xa01", "1\xa0"]
    out = [x.encode("latin-1") for x in s]
    for k in range(20, 30):                # the 24/25-digit quirk: the 24th digit 0..9 followed by more digits
        for d in range(10):
            out.append(("1" * 23 + str(d) + "7" * (k - 24)).encode())
            out.append(("0." + "3" * 23 + str(d) + "5" * (k - 24)).encode())
    for _ in range(20000 * scale):
        kind = rnd.random()
        if kind < 0.3:
            x = math.ldexp(rnd.random() + 0.5, rnd.randint(-1080, 1023))
            out.append(("%.*g" % (rnd.randint(1, 30), x)).encode())
        elif kind < 0.5:
            out.append(("%.*fe%d" % (rnd.randint(0, 25), rnd.uniform(-10, 10), rnd.randint(-330, 310))).encode())
        elif kind < 0.7:
            digits = "".join(rnd.choice("0123456789") for _ in range(rnd.randint(1, 40)))
            point = rnd.randint(0, len(digits))
            exp = rnd.choice(["", "e%d" % rnd.randint(-350, 350), "E+%d" % rnd.randint(0, 40), "d-%d" % rnd.randint(0, 40)])
            out.append((rnd.choice(["", "-", "+", " "]) + digits[:point] + "." + digits[point:] + exp).encode())
        elif kind < 0.85:                  # near-halfway doubles: the exact decimal of a midpoint, truncated
            x = math.ldexp(rnd.getrandbits(53) | (1 << 52), rnd.randint(-1074, 970))
            mid = x + math.ulp(x) / 2
            out.append(("%.*e" % (rnd.randint(15, 40), mid)).encode())
        else:
            out.append(bytes(rnd.choice(b"0123456789.eEdD+- \tx") for _ in range(rnd.randint(0, 12))))
    return out


def gen_strings(rnd, scale, lines):
    for s in atof_strings(rnd, scale):
        lines.append(f"atof {hexs(s)}")
    for c in list(range(-300, 300)) + [-1, 0x7FFFFFFF, -0x80000000, 0x1FF61, 0xFF, 0x100, 0x161]:
        lines.append(f"toupper {c}")
    alpha = b"abcXYZ_[]`{}@AZaz09 \x80\xe9\xff"
    for _ in range(3000 * scale):
        s = bytes(rnd.choice(alpha) for _ in range(rnd.randint(0, 12)))
        lines.append(f"strchr {hexs(s)} {rnd.choice([0, 0x41, 0x61, 0x5F, 0xE9, -23, 0x161, ord('Z'), ord('[')])}")
        t = bytes((ch ^ 0x20) if rnd.random() < 0.3 and chr(ch).isalpha() else ch for ch in s)
        if rnd.random() < 0.3:
            t = t[:rnd.randint(0, len(t))] + bytes(rnd.choice(alpha) for _ in range(rnd.randint(0, 3)))
        lines.append(f"stricmp {hexs(s)} {hexs(t)}")
    for s in [b"", b"0", b"-0", b"42", b"-17", b"+5", b"  \t\n\v\f\r 12x", b"2147483647", b"2147483648", b"-2147483648",
              b"4294967296", b"99999999999999", b"--1", b"+-1", b"1 2", b"\xa012", b"0x10", b"007"]:
        lines.append(f"atoi {hexs(s)}")
    for _ in range(2000 * scale):
        s = (rnd.choice(["", " ", "\t", "-", "+", "--"]) + "".join(rnd.choice("0123456789") for _ in range(rnd.randint(0, 14)))
             + rnd.choice(["", "x", " 5", "."])).encode()
        lines.append(f"atoi {hexs(s)}")


def gen_qsort(rnd, scale, lines):
    for n in [0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 16, 17, 31, 50, 64, 100, 257, 1000]:
        for width in [4, 8, 12]:
            if width < 8 and n > 1:
                continue                   # the id must fit: 4-byte elements only for the trivial sizes
            for keys in sorted({1, 2, 3, 10, max(n, 1)}):
                for mode in [0, 1, 2]:
                    for seed in range(1 + scale):
                        lines.append(f"qsort {n} {width} {keys} {mode} {rnd.getrandbits(31) + seed}")


def build_corpus(args):
    rnd = random.Random(args.seed)
    lines = []
    gen_pow(rnd, args.scale, lines)
    gen_isnan(rnd, args.scale, lines)
    gen_strings(rnd, args.scale, lines)
    gen_qsort(rnd, args.scale, lines)
    if args.inputs:
        with open(args.inputs, encoding="ascii") as f:
            for ln in f:
                p = ln.split()
                if p and p[0] in ("pow", "fmod") and len(p) >= 3:
                    lines.append(f"{p[0]} {p[1]} {p[2]}")
                elif p and p[0] in ("isnan",) and len(p) >= 2:
                    lines.append(f"isnan {p[1]}")
                elif p and p[0] == "atof" and len(p) >= 2:
                    lines.append(f"atof {p[1]}")
    return lines


def category(line):
    return line.split(" ", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--inputs")
    ap.add_argument("--json")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    p = subprocess.run([sys.executable, "-I", os.path.join(WS, "tools", "xrt", "make_sandbox.py"), SB],
                       capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"make_sandbox failed: {p.stderr}")
    lines = build_corpus(args)
    corpus = os.path.join(OUT, "corpus.txt")
    with open(corpus, "w", newline="\n", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")
    ref_out, cand_out = os.path.join(OUT, "ref.txt"), os.path.join(OUT, "cand.txt")
    for f in (ref_out, cand_out):
        if os.path.exists(f):
            os.remove(f)
    r1 = subprocess.run([os.path.join(OUT, "ref.exe"), os.path.join(SB, "System"), corpus, ref_out],
                        capture_output=True, text=True, timeout=1800)
    r2 = subprocess.run([os.path.join(OUT, "cand.exe"), SB, corpus, cand_out], capture_output=True, text=True,
                        timeout=1800)
    if r1.returncode or r2.returncode or not os.path.exists(ref_out) or not os.path.exists(cand_out):
        sys.exit(f"a side failed: ref {r1.returncode} {r1.stderr[-500:]} cand {r2.returncode} {r2.stderr[-500:]}")
    ref = open(ref_out).read().splitlines()
    cand = open(cand_out).read().splitlines()
    if len(ref) != len(lines) or len(cand) != len(lines):
        sys.exit(f"result counts differ: corpus {len(lines)} ref {len(ref)} cand {len(cand)}")
    summary, mism = {}, []
    for ln, a, b in zip(lines, ref, cand):
        cat = category(ln)
        s = summary.setdefault(cat, {"cases": 0, "mismatches": 0})
        s["cases"] += 1
        if a != b:
            s["mismatches"] += 1
            mism.append({"case": ln[:300], "ref": a.split(" ", 1)[1], "cand": b.split(" ", 1)[1]})
    total = sum(s["mismatches"] for s in summary.values())
    for cat, s in sorted(summary.items()):
        print(f"{cat:8} {s['cases']:7} cases {s['mismatches']:6} mismatches")
    for m in mism[:40]:
        print("  MISMATCH", m["case"][:160], "| ref", m["ref"][:80], "| cand", m["cand"][:80])
    print("TOTAL", sum(s["cases"] for s in summary.values()), "cases,", total, "mismatches")
    if args.json:
        with open(args.json, "w", newline="\n") as f:
            json.dump({"seed": args.seed, "scale": args.scale, "inputs": bool(args.inputs), "summary": summary,
                       "mismatches_first_200": mism[:200]}, f, indent=1)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
