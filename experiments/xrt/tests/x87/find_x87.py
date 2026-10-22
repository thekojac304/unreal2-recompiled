"""Locate x87 transcendental / rounding / sqrt instructions in a translated module.

Runs tools/xrt/discover.py's Module over the module (sandbox copy, read as data only), lists every
discovered function that contains one of the instructions of interest, marks which of them executed in
a traced run of the original (traces/<case>.json "hit_rvas"), and writes the disassembly of those
functions to a git-ignored build directory for manual analysis.

Usage: python -I experiments/xrt/tests/x87/find_x87.py <module.dll> <trace.json> <out_dir>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "xrt"))
from discover import Module  # noqa: E402

INTEREST = {"fsin", "fcos", "fsincos", "fptan", "fpatan", "fyl2x", "fyl2xp1", "f2xm1", "fscale", "frndint",
            "fsqrt", "fprem", "fprem1", "fxtract", "fninit", "fldcw", "fistp", "fist", "fild", "fisttp"}
PRIMARY = {"fsin", "fcos", "fsincos", "fptan", "fpatan", "fyl2x", "fyl2xp1", "f2xm1", "fscale", "frndint", "fsqrt",
           "fprem", "fprem1", "fxtract", "fninit"}


def main():
    path, trace_path, out_dir = sys.argv[1:4]
    os.makedirs(out_dir, exist_ok=True)
    mod = Module(path).run()
    name = mod.img.name
    hit = set()
    with open(trace_path) as f:
        tr = json.load(f)
    for m in tr["modules"]:
        if m["name"].lower() == name.lower():
            hit = {int(r, 16) if isinstance(r, str) else r for r in m["hit_rvas"]}
    base = mod.img.base
    found = []
    census = {}
    for e, fn in sorted(mod.functions.items()):
        mn = [fn.insns[va].mnemonic for va in sorted(fn.insns)]
        for x in mn:
            if x in INTEREST:
                census[x] = census.get(x, 0) + 1
        prim = sorted({x for x in mn if x in PRIMARY})
        if not prim:
            continue
        found.append({"rva": hex(e - base), "va": hex(e), "insns": len(fn.insns), "ops": prim,
                      "counts": {x: mn.count(x) for x in sorted(set(mn) & INTEREST)},
                      "executed_in_trace": (e - base) in hit})
        with open(os.path.join(out_dir, f"fn_{e - base:06x}.asm"), "w") as f:
            for va in sorted(fn.insns):
                ins = fn.insns[va]
                f.write(f"{va:08x}  {ins.mnemonic} {ins.op_str}\n")
    # also: all fninit / fldcw sites (state changes the runtime treats specially)
    report = {"module": name, "base": hex(base), "functions_discovered": len(mod.functions),
              "instruction_census": census, "functions": found}
    with open(os.path.join(out_dir, "x87_functions.json"), "w") as f:
        json.dump(report, f, indent=1)
    for r in found:
        print(r["rva"], r["insns"], r["ops"], r["counts"], "EXECUTED" if r["executed_in_trace"] else "-")
    print(json.dumps(census))


if __name__ == "__main__":
    main()
