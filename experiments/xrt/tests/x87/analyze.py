"""Inspect record mismatches: hardware vs a runtime model, with an exact reference for trig functions.

Usage: python -I analyze.py <build_dir> <set> <op> [model=rt] [--limit N] [--all]
  build_dir holds inputs.bin, hw32.bin and rt_<model>.bin (x87_rt64 run ...).
For fsin/fcos/fptan/appSin/appCos/appTan/FGlobalMath_sine_table, prints the exact value, the value
with the x87's 66-bit pi, and the hardware's / model's errors against both (in double ulps).
"""
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x87data import (OPS, OUT, P66_FIX, REC, SETS, d, f, frac80, frac_d, load, sin_cos_exact,  # noqa: E402
                     ulps_double)

TRIG = {"fsin": "sin", "appSin": "sin", "FGlobalMath_sine_table": "sin", "fcos": "cos", "appCos": "cos",
        "fptan": "tan", "appTan": "tan"}


def ref(kind, x, p=None):
    s, c = sin_cos_exact(x, p)
    if kind == "sin":
        return s
    if kind == "cos":
        return c
    return s / c if c else None


def main():
    bd, setn, opn = sys.argv[1:4]
    model = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else "rt"
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 20
    show_all = "--all" in sys.argv
    recs = load(os.path.join(bd, "inputs.bin"), REC)
    hw = load(os.path.join(bd, "hw32.bin"), OUT)
    rt = load(os.path.join(bd, f"rt_{model}.bin"), OUT)
    sid = SETS.index(setn)
    opid = [k for k, v in OPS.items() if v == opn][0]
    shown = 0
    for r, h, m in zip(recs, hw, rt):
        if r[2] != sid or r[0] != opid:
            continue
        same = (h[2] == m[2] and h[3] == m[3] and h[4] == m[4])
        if same and not show_all:
            continue
        a, b = r[4], r[5]
        x = d(a)
        if opn == "FGlobalMath_sine_table":
            x = d(h[5])
        line = (f"idx={r[3]:5d} aux={r[1]} a={a:016x} ({x!r}) b={b:016x} hw80={h[0][::-1].hex()} fsw={h[1]:04x}/{m[1]:04x} "
                f"hw64={h[3]:016x} rt64={m[3]:016x} hw32={h[2]:08x} rt32={m[2]:08x} ({f(h[2])!r} / {f(m[2])!r}) "
                f"i64={h[4]:x}/{m[4]:x}")
        print(line)
        kind = TRIG.get(opn)
        if kind and abs(x) < 2 ** 63:
            xf = Fraction(x)
            t = ref(kind, xf)
            t66 = ref(kind, xf, P66_FIX)
            hv = frac80(h[0])
            mv = frac_d(m[3])
            if t is not None and hv is not None and mv is not None:
                print(f"    exact={float(t)!r} pi66={float(t66)!r} | hw80 err: {ulps_double(hv - t, t):.3g} ulp vs exact, "
                      f"{ulps_double(hv - t66, t66):.3g} vs pi66 | model err: {ulps_double(mv - t, t):.3g} vs exact, "
                      f"{ulps_double(mv - t66, t66):.3g} vs pi66")
        shown += 1
        if shown >= limit:
            break


if __name__ == "__main__":
    main()
