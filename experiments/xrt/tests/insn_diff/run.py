"""Runs the whole differential instruction test (see README.md):
census -> snippets/vectors/lifting -> build both harnesses -> native run -> lifted run -> compare.

Usage (from anywhere):
  .venv\\Scripts\\python.exe -I experiments\\xrt\\tests\\insn_diff\\run.py [--seed N] [--scale F] [--mutation-check]
Exit status: 0 when no unattributed failure is left, 1 otherwise.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BUILD = os.path.join(WS, "experiments", "xrt", "build", "insn_diff")
PY = sys.executable


def step(name, cmd):
    t = time.time()
    print(f"== {name}", flush=True)
    r = subprocess.run(cmd, cwd=WS)
    print(f"   ({time.time() - t:.1f} s, exit {r.returncode})", flush=True)
    return r.returncode


def main():
    args = sys.argv[1:]
    gen_args = []
    for opt in ("--seed", "--scale"):
        if opt in args:
            gen_args += [opt, args[args.index(opt) + 1]]
    # --live-random: snippets lifted as under xlift --opt flags with a random live-flag set each; only live flags
    # are compared (results.live-random.json, the committed results.json stays the default-lift evidence)
    results = "results.live-random.json" if "--live-random" in args else "results.json"
    if "--live-random" in args:
        gen_args.append("--live-random")
    os.makedirs(BUILD, exist_ok=True)
    if step("census", [PY, "-I", os.path.join(HERE, "census.py")]):
        return 2
    if step("generate snippets, vectors, lifted C", [PY, "-I", os.path.join(HERE, "gen.py")] + gen_args):
        return 2
    if step("build harnesses", ["cmd", "/c", os.path.join(HERE, "build.cmd")]):
        return 2
    cases = os.path.join(BUILD, "cases.bin")
    teb = os.path.join(BUILD, "teb.bin")
    if step("native x86 run", [os.path.join(BUILD, "native_x86.exe"), cases, os.path.join(BUILD, "out_native.bin"),
                               teb]):
        return 2
    if step("lifted x64 run", [os.path.join(BUILD, "lifted_x64.exe"), cases, os.path.join(BUILD, "out_lifted.bin"),
                               teb]):
        return 2
    if step("compare", [PY, "-I", os.path.join(HERE, "compare.py"), "--quiet", "--results", results]):
        return 1
    if "--mutation-check" in args:
        if step("mutation check", [PY, "-I", os.path.join(HERE, "mutation_check.py")]):
            return 1
    with open(os.path.join(HERE, results), encoding="utf-8") as f:
        s = json.load(f)["summary"]
    print(f"cases {s['cases']}, failed {s['failed_cases']} (unattributed {s['failed_cases_unattributed']})")
    return 1 if s["failed_cases_unattributed"] else 0


if __name__ == "__main__":
    sys.exit(main())
