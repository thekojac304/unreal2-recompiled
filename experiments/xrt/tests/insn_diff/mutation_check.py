"""Sensitivity check for the differential instruction test: injects known bugs into the lifted C.

Each mutation edits the generated build/insn_diff/id_lifted.c the way a plausible lifter bug would,
rebuilds only the lifted harness, reruns it on the same cases and requires compare.py to report
failures. A mutation that survives (no failure reported) means the vectors cannot see that bug.

Usage: python -I mutation_check.py      (after run.py; prints a table, exit 1 if a mutant survives)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BUILD = os.path.join(WS, "experiments", "xrt", "build", "insn_diff")
PY = sys.executable

# (name, old text in the generated C, replacement): each one is a single plausible lifter defect
MUTATIONS = [
    ("adc ignores carry-in", "a_ + b_ + c->cf", "a_ + b_"),
    ("sbb carry-out ignores carry-in", "c->cf = a_ < b_ + c->cf", "c->cf = a_ < b_"),
    ("shr CF taken from the wrong bit", "(uint64_t)a_ >> (n_ - 1u)) & 1u); r_ = (uint32_t)((uint64_t)a_ >> n_)",
     "(uint64_t)a_ >> n_) & 1u); r_ = (uint32_t)((uint64_t)a_ >> n_)"),
    ("setl condition inverted", "(c->sf != c->of)) ? 1u", "(c->sf == c->of)) ? 1u"),
    ("high-byte register write clobbers the low byte", "0xFFFF00FFu) | (((uint32_t)(", "0xFFFF0000u) | (((uint32_t)("),
    ("8-bit compare flags computed at 32 bits", "fl_sub(c, a_, b_, r_, 8)", "fl_sub(c, a_, b_, r_, 32)"),
    ("idiv quotient overflow not detected", "if (q_ > 2147483647LL || q_ < -2147483648LL) xrt_div0",
     "if (0) xrt_div0"),
    ("string ops ignore DF", "(c->df ? (uint32_t)-4 : 4u)", "4u"),
    ("fsub/fsubp ST(i),ST(0) operand order swapped", "*ST(c, 1) = *ST(c, 1) - *ST(c, 0);",
     "*ST(c, 1) = *ST(c, 0) - *ST(c, 1);"),
    ("sar shifts logically", "int64_t s_ = (int64_t)(int32_t)(a_ << (32 - 32)) >> (32 - 32);",
     "int64_t s_ = (int64_t)a_;"),
    ("movsx from 16 bits treated as 8 bits", "(uint32_t)(int32_t)(int16_t)(", "(uint32_t)(int32_t)(int8_t)("),
    ("x87 fild m64 read as m32", "(double)(int64_t)rd64(", "(double)(int32_t)rd32("),
    ("fs: operands off by 4 bytes", "c->fs_base + ", "c->fs_base + 4u + "),
]


def failed_count(text):
    for ln in text.splitlines():
        if ln.startswith("failed cases: "):
            return int(ln.split(":")[1].split(";")[0])
    raise RuntimeError("compare.py output without a failure count: " + text[-300:])


def main():
    with open(os.path.join(BUILD, "id_lifted.c"), encoding="utf-8") as f:
        src = f.read()
    r = subprocess.run([PY, "-I", os.path.join(HERE, "compare.py"), "--no-write"], capture_output=True, text=True)
    baseline = failed_count(r.stdout)
    print(f"baseline: {baseline} failed cases")
    mdir = os.path.join(BUILD, "mutants")
    os.makedirs(mdir, exist_ok=True)
    rows = []
    for i, (name, old, new) in enumerate(MUTATIONS):
        n = src.count(old)
        if n == 0:
            rows.append((name, 0, None, "pattern not in the generated code"))
            continue
        c_path = os.path.join(mdir, f"mut{i:02d}.c")
        exe = os.path.join(mdir, f"mut{i:02d}.exe")
        out = os.path.join(mdir, f"mut{i:02d}.bin")
        with open(c_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(src.replace(old, new))
        r = subprocess.run(["cmd", "/c", os.path.join(HERE, "build_lifted.cmd"), c_path, exe],
                           capture_output=True, text=True)
        if r.returncode:
            rows.append((name, n, None, "build failed: " + (r.stdout + r.stderr)[-300:]))
            continue
        subprocess.run([exe, os.path.join(BUILD, "cases.bin"), out, os.path.join(BUILD, "teb.bin")], check=True,
                       capture_output=True)
        r = subprocess.run([PY, "-I", os.path.join(HERE, "compare.py"), "--lifted", out, "--no-write"],
                           capture_output=True, text=True)
        line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
        rows.append((name, n, failed_count(r.stdout) > baseline, line))
    survived = 0
    result = []
    for name, n, killed, line in rows:
        state = "killed" if killed else "SURVIVED" if killed is False else "n/a"
        survived += killed is False
        print(f"{state:8}  {name}  [{n} sites]  {line}")
        result.append({"mutation": name, "sites": n, "result": state, "detail": line})
    with open(os.path.join(BUILD, "mutation_check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
