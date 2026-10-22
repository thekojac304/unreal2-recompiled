"""Supporting analyses for results.json (run by run_x87.py after the comparisons):

  pi66_validation    hardware fsin/fcos/fptan results on random large arguments against exact sin/cos/tan
                     computed with the true pi and with the x87's 66-bit pi (big-integer reference)
  sine_table         every FGlobalMath sine-table entry whose float32 value differs, with exact values
  double_rounding    hx-model float mismatches (exhaustive lists, |x| < 2^20): the bits of the hardware's
                     64-bit significand below the float's 24 bits
  gmath_readers      Core.dll code that reads the GMath tables, and whether it executed in any trace

Usage: python -I analyze_extra.py <build_dir> <Core.dll> <out.json>
"""
import json
import os
import struct
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "tools", "xrt"))
from x87data import (OPS, OUT, P66_FIX, REC, SETS, d, f, frac80, frac_d, load, sin_cos_exact, ulps_double,  # noqa: E402
                     ulps_float)

XRT = os.path.abspath(os.path.join(HERE, "..", ".."))


def trig(kind, x, p=None):
    s, c = sin_cos_exact(x, p)
    return s if kind == "sin" else c if kind == "cos" else s / c


def pi66_validation(recs, hw, rt):
    out = {}
    kinds = {1: "sin", 2: "cos", 3: "tan"}
    for sname in ("rand_small", "rand_medium", "rand_large", "pi_multiples"):
        sid = SETS.index(sname)
        for op, kind in kinds.items():
            n, worst_true, worst_66, worst_rt_true = 0, 0.0, 0.0, 0.0
            for r, h, m in zip(recs, hw, rt):
                if r[2] != sid or r[0] != op or r[3] % 50:
                    continue
                x = d(r[4])
                hv, mv = frac80(h[0]), frac_d(m[3])
                if hv is None or mv is None:
                    continue
                t, t66 = trig(kind, Fraction(x)), trig(kind, Fraction(x), P66_FIX)
                if t == 0 or t66 == 0:
                    continue
                n += 1
                worst_true = max(worst_true, ulps_double(hv - t, t))
                worst_66 = max(worst_66, ulps_double(hv - t66, t66))
                worst_rt_true = max(worst_rt_true, ulps_double(mv - t, t))
            out[f"{sname}/{kind}"] = {"samples": n, "hw80_max_err_double_ulps_vs_true_pi": worst_true,
                                      "hw80_max_err_double_ulps_vs_pi66": worst_66,
                                      "runtime_max_err_double_ulps_vs_true_pi": worst_rt_true}
    return out


def sine_table(recs, hw, rts):
    sid, op = SETS.index("engine_sintab"), 40
    rows = []
    for k, (r, h) in enumerate(zip(recs, hw)):
        if r[2] != sid or r[0] != op:
            continue
        diff = {m: rt[k][2] for m, rt in rts.items() if rt[k][2] != h[2]}
        if not diff:
            continue
        x = d(h[5])
        t = trig("sin", Fraction(x))
        rows.append({"index": r[3], "argument": x, "argument_bits": f"{h[5]:016x}", "hw_float": f"{h[2]:08x}",
                     "hw_float_value": f(h[2]), "exact_sin": float(t),
                     "models_differing": {m: {"float": f"{v:08x}", "value": f(v), "float_ulps_from_hw": abs(v - h[2])}
                                          for m, v in diff.items()},
                     "hw_err_float_ulps_vs_exact": ulps_float(Fraction(f(h[2])) - t, t)})
    n_double = {m: sum(1 for k, (r, h) in enumerate(zip(recs, hw)) if r[2] == sid and r[0] == op and rt[k][3] != h[3])
                for m, rt in rts.items()}
    return {"entries": 16384, "float_mismatches": rows, "double_level_mismatches": n_double}


def double_rounding(bd):
    rows = []
    for op in ("sin", "cos", "tan", "atan", "sqrt", "exp", "loge"):
        p = os.path.join(bd, "exh", f"mis_{op}_hx.bin")
        if not os.path.exists(p):
            continue
        data = open(p, "rb").read()
        for i in range(0, len(data), 32):
            arg, hw32, rt32, _ = struct.unpack_from("<IIII", data, i)
            mant = int.from_bytes(data[i + 16:i + 24], "little")
            rows.append({"op": op, "arg": f"{arg:08x}", "arg_value": f(arg), "hw_float": f"{hw32:08x}", "hx_float": f"{rt32:08x}",
                         "hw80_significand": f"{mant:016x}", "bits_below_float": format(mant & ((1 << 40) - 1), "040b")})
    return rows


def fma3_records(recs, hw, rt, rt_nofma):
    """runtime outputs with the UCRT FMA3 code paths enabled (default on this host) and disabled"""
    from collections import Counter
    n, d64, d32, hw_on, hw_off = Counter(), Counter(), Counter(), Counter(), Counter()
    for r, h, a, b in zip(recs, hw, rt, rt_nofma):
        k = OPS[r[0]]
        n[k] += 1
        d64[k] += a[3] != b[3]
        d32[k] += a[2] != b[2]
        hw_on[k] += a[3] != h[3]
        hw_off[k] += b[3] != h[3]
    return {k: {"records": n[k], "double_differs_on_off": d64[k], "float_differs_on_off": d32[k],
                "double_mismatch_vs_hw_fma3_on": hw_on[k], "double_mismatch_vs_hw_fma3_off": hw_off[k]}
            for k in n if d64[k] or d32[k]}


def gmath_readers(core):
    from discover import Module
    mod = Module(core).run()
    b = mod.img.base
    exp = {n: b + r for n, r in mod.img.exports.items()}
    names = {v: k for k, v in exp.items()}
    gm = exp["?GMath@@3VFGlobalMath@@A"]
    traces = {}
    for t in ("hellofull", "hello", "simple", "arraytest", "badclass", "vmprobe"):
        tr = json.load(open(os.path.join(XRT, "traces", f"{t}.json")))
        for m in tr["modules"]:
            if m["name"] == "Core.dll":
                traces[t] = {int(r, 16) if isinstance(r, str) else r for r in m["hit_rvas"]}
    out = []
    for e, fn in sorted(mod.functions.items()):
        n = sum(1 for ins in fn.insns.values() for op in ins.operands
                if op.type == 3 and gm + 0x8c <= (op.mem.disp & 0xFFFFFFFF) < gm + 0x2008c)
        if n:
            out.append({"rva": hex(e - b), "name": names.get(e), "table_operands": n,
                        "executed_in": [t for t, s in traces.items() if (e - b) in s]})
    return {"gmath_rva": hex(gm - b), "sine_table_rva": hex(gm + 0x8c - b), "sqrt_table_rva": hex(gm + 0x1008c - b),
            "readers": out}


def main():
    bd, core, outp = sys.argv[1:4]
    recs = load(os.path.join(bd, "inputs.bin"), REC)
    hw = load(os.path.join(bd, "hw32.bin"), OUT)
    rts = {m: load(os.path.join(bd, f"rt_{m}.bin"), OUT) for m in ("rt", "hx", "p66", "pfix")
           if os.path.exists(os.path.join(bd, f"rt_{m}.bin"))}
    res = {"pi66_validation": pi66_validation(recs, hw, rts["rt"]), "sine_table": sine_table(recs, hw, rts),
           "fma3_records": fma3_records(recs, hw, rts["rt"], load(os.path.join(bd, "rt_rt_nofma.bin"), OUT)),
           "double_rounding_hx": double_rounding(bd), "gmath_readers": gmath_readers(core)}
    json.dump(res, open(outp, "w"), indent=1)
    print("wrote", outp)


if __name__ == "__main__":
    main()
