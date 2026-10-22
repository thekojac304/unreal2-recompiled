"""Print a table of the record comparison (x87_rt64 cmp output).

Usage: python -I summarize_records.py <cmp_records.json> [model] [--all]
"""
import json
import sys


def main():
    d = json.load(open(sys.argv[1]))
    want = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    show_all = "--all" in sys.argv
    for m in d["models"]:
        if want and m["model"] != want:
            continue
        print("== model", m["model"])
        for g in m["groups"]:
            bad = any(g[k] for k in ("mismatch_double", "mismatch_float", "c2_mismatch", "int_mismatch",
                                     "arg_mismatch", "fptan_push_mismatch", "fptan_pushed_value_mismatch", "nan_payload_only"))
            if not bad and not show_all:
                continue
            print(f"{g['set']:26s} {g['op']:24s} n={g['n']:7d} dbl={g['mismatch_double']:6d} flt={g['mismatch_float']:6d} "
                  f"zs={g['float_zero_sign_only']} nanp={g['nan_payload_only']:4d} c2={g['c2_mismatch']:4d} "
                  f"int={g['int_mismatch']:5d} arg={g['arg_mismatch']} push={g['fptan_push_mismatch']}/{g['fptan_pushed_value_mismatch']} "
                  f"ulp80={g['max_ulp_double_vs_hw80']:.3g} ulpd={g['max_ulp_double_vs_hw_double']} "
                  f"ulpf={g['max_ulp_float']}" + ("" if bad else "  OK"))


if __name__ == "__main__":
    main()
