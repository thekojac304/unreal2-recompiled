"""Run the x87 differential tests and write experiments/xrt/tests/x87/results.json.

Usage (workspace root):
  .venv\\Scripts\\python -I experiments\\xrt\\tests\\x87\\run_x87.py [--build] [--quick] [--skip-exhaustive]
    --build            lift the helpers (xlift --only) and build both harnesses first
    --quick            exhaustive runs only for sin (all other steps unchanged)
    --skip-exhaustive  reuse exhaustive results already in build/x87/exh

Build products and raw data stay in experiments/xrt/build/x87 (git-ignored).
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
XRT = os.path.join(ROOT, "experiments", "xrt")
B = os.path.join(XRT, "build", "x87")
EXH = os.path.join(B, "exh")
PY = sys.executable
CORE = os.path.join(ROOT, "sandbox_ref", "hellofull", "System", "Core.dll")
TRACES = ["hellofull", "hello", "simple", "arraytest", "badclass", "vmprobe"]
ONLY = "0x10116f60,0x10116f80,0x10116fa0,0x10116fc0,0x10116fe0,0x10116ff0,0x10117000,0x10117010,0x1015d510"
XOPS = ["sin", "cos", "tan", "atan", "sqrt", "exp", "loge"]


def run(args, **kw):
    t0 = time.time()
    print(">", " ".join(args), flush=True)
    p = subprocess.run(args, cwd=B, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        print(p.stdout, p.stderr)
        raise SystemExit(f"failed: {args}")
    print(f"  ({time.time() - t0:.1f} s) {p.stdout.strip()[-400:]}", flush=True)
    return p.stdout


def jlines(path):
    return [json.loads(x) for x in open(path) if x.strip()] if os.path.exists(path) else []


def main():
    os.makedirs(EXH, exist_ok=True)
    quick = "--quick" in sys.argv
    ops = ["sin"] if quick else XOPS
    # The runtime under test is runtime/xrt_cpu.c as committed (HEAD). A working-tree copy that differs
    # (another session may be changing the runtime) is validated separately ("working_tree").
    snap = os.path.join(B, "snap")
    os.makedirs(snap, exist_ok=True)
    head_c, wt_c = os.path.join(snap, "xrt_cpu_head.c"), os.path.join(snap, "xrt_cpu_wt.c")
    if "--build" in sys.argv:
        run([PY, "-I", os.path.join(ROOT, "tools", "xrt", "xlift.py"), CORE, "--out", os.path.join(B, "gen"), "--only", ONLY])
        src = subprocess.run(["git", "show", "HEAD:experiments/xrt/runtime/xrt_cpu.c"], cwd=ROOT, capture_output=True, check=True).stdout
        open(head_c, "wb").write(src)
        open(wt_c, "wb").write(open(os.path.join(XRT, "runtime", "xrt_cpu.c"), "rb").read())
        run(["cmd", "/c", os.path.join(HERE, "build_x87.cmd"), head_c, "_head"])
        if open(head_c, "rb").read() != open(wt_c, "rb").read():
            run(["cmd", "/c", os.path.join(HERE, "build_x87.cmd"), wt_c, "_wt"])
    hw32, rt64 = os.path.join(B, "x87_hw32.exe"), os.path.join(B, "x87_rt64_head.exe")
    rt64wt = os.path.join(B, "x87_rt64_wt.exe")
    res = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "host": {}}
    res["runtime_under_test"] = {
        "head_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "xrt_cpu_c_head_sha256": hashlib.sha256(open(head_c, "rb").read()).hexdigest(),
        "xrt_cpu_c_working_tree_snapshot_sha256": hashlib.sha256(open(wt_c, "rb").read()).hexdigest()
        if os.path.exists(wt_c) else None}
    wt_differs = os.path.exists(wt_c) and open(head_c, "rb").read() != open(wt_c, "rb").read() and os.path.exists(rt64wt)

    # ---------------------------------------------------------------- step 1: where the engine uses x87 transcendentals
    funcs = {}
    for t in TRACES:
        tp = os.path.join(XRT, "traces", f"{t}.json")
        out = os.path.join(B, f"find_{t}")
        run([PY, "-I", os.path.join(HERE, "find_x87.py"), CORE, tp, out])
        rep = json.load(open(os.path.join(out, "x87_functions.json")))
        for fn in rep["functions"]:
            funcs.setdefault(fn["rva"], {k: v for k, v in fn.items() if k != "executed_in_trace"})
            funcs[fn["rva"]].setdefault("executed_in", [])
            if fn["executed_in_trace"]:
                funcs[fn["rva"]]["executed_in"].append(t)
        res["core_x87_census"] = rep["instruction_census"]
    res["core_x87_functions"] = funcs

    # ---------------------------------------------------------------- host facts
    res["host"]["info_x64"] = json.loads(run([rt64, "info"]))
    res["host"]["info_x86"] = json.loads(run([hw32, "info"]))
    res["host"]["platform"] = platform.platform()
    try:
        res["host"]["cpu"] = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                                            capture_output=True, text=True).stdout.strip()
    except OSError:
        pass

    # ---------------------------------------------------------------- step 2/3: records (engine inputs, random, edges)
    res["records_generated"] = json.loads(run([rt64, "gen", "inputs.bin"]))["records"]
    res["records_hw32"] = json.loads(run([hw32, "records", "inputs.bin", "hw32.bin"]))
    run([rt64, "cmp", "inputs.bin", "hw32.bin", "cmp_records.json", "all"])
    res["records"] = json.load(open(os.path.join(B, "cmp_records.json")))
    for m in ("rt", "hx", "p66", "pfix"):
        run([rt64, "run", "inputs.bin", m, f"rt_{m}.bin"])
    run([rt64, "run", "inputs.bin", "rt", "rt_rt_nofma.bin", "nofma"])     # UCRT FMA3 paths disabled
    if wt_differs:
        run([rt64wt, "cmp", "inputs.bin", "hw32.bin", "cmp_records_wt.json", "rt"])
        run([rt64wt, "run", "inputs.bin", "rt", "rt_wt.bin"])
        res["working_tree_records"] = json.load(open(os.path.join(B, "cmp_records_wt.json")))
        res["working_tree_records_equal_pfix_model"] = (open(os.path.join(B, "rt_wt.bin"), "rb").read()
                                                        == open(os.path.join(B, "rt_pfix.bin"), "rb").read())

    # appInit timing loop: D += appSqrt(D) + 3.14; _ftol2(D)   (2^25 steps, block hashes)
    steps = str(1 << 25)
    res["timing_loop_hw"] = json.loads(run([hw32, "dummy", steps, "hw_dummy.bin"]))
    res["timing_loop_rt"] = json.loads(run([rt64, "dummy", steps, "hw_dummy.bin"]))
    if wt_differs:
        res["timing_loop_working_tree"] = json.loads(run([rt64wt, "dummy", steps, "hw_dummy.bin"]))

    # ---------------------------------------------------------------- exhaustive float32 script-native arguments
    if "--skip-exhaustive" not in sys.argv:
        for f in ("exh_x64.jsonl", "exh_nofma.jsonl", "fmadiff.jsonl", "atan2.jsonl"):
            if os.path.exists(os.path.join(EXH, f)):
                os.remove(os.path.join(EXH, f))
        hw32_runs = []
        for op in ops:
            run([rt64, "exhaustive", op, "exh/hw64", "exh/exh_x64.jsonl", "exh/mis", "rt,hx,p66", "all"])
            run([rt64, "exhaustive", op, "exh/hw64nf", "exh/exh_nofma.jsonl", "exh/mis", "rt", "all", "nofma"])
            for cores, prefix in (("all", "exh/hw32"), ("P", "exh/hw32P"), ("E", "exh/hw32E")):
                hw32_runs.append(json.loads(run([hw32, "exhaustive", op, prefix, cores])))
        json.dump(hw32_runs, open(os.path.join(EXH, "hw32_runs.json"), "w"))
        for op in [o for o in ops if o in ("sin", "cos", "tan")]:      # proposed portable helper set
            run([rt64, "exhaustive", op, "exh/hw64pf", "exh/exh_x64.jsonl", "exh/mis", "pfix", "all"])
        run([rt64, "fmadiff", ",".join(ops) if len(ops) == 1 else "all", "exh/fmadiff.jsonl"])
        run([rt64, "atan2", str(1 << 27), "exh/atan2.jsonl", "all"])
        if wt_differs:
            if os.path.exists(os.path.join(EXH, "exh_wt.jsonl")):
                os.remove(os.path.join(EXH, "exh_wt.jsonl"))
            for op in [o for o in ops if o in ("sin", "cos", "tan", "exp")]:
                run([rt64wt, "exhaustive", op, "exh/hw64wt", "exh/exh_wt.jsonl", "exh/miswt", "rt", "all"])
    hw32_runs = json.load(open(os.path.join(EXH, "hw32_runs.json"))) if os.path.exists(os.path.join(EXH, "hw32_runs.json")) else []
    xval = {}
    for op in ops:
        def rd(p):
            p = os.path.join(B, p)
            return open(p, "rb").read() if os.path.exists(p) else None
        a, b, c, p_, e_ = (rd(f"exh/hw64_{op}.bin"), rd(f"exh/hw64nf_{op}.bin"), rd(f"exh/hw32_{op}.bin"),
                           rd(f"exh/hw32P_{op}.bin"), rd(f"exh/hw32E_{op}.bin"))
        xval[op] = {"x64_ml64_kernel_equals_x86_inline_asm": a is not None and a == c,
                    "x64_kernel_repeat_run_equal": a is not None and a == b,
                    "p_cores_equal_e_cores": p_ is not None and p_ == e_,
                    "p_cores_equal_all_cores": p_ is not None and p_ == c,
                    "chunks": 4096, "hashed": "float store, 80-bit ST(0), condition codes, per 2^20 arguments"}
    res["exhaustive_hw_crosscheck"] = xval
    res["exhaustive_hw32_runs"] = hw32_runs
    res["exhaustive"] = jlines(os.path.join(EXH, "exh_x64.jsonl"))
    res["exhaustive_nofma"] = jlines(os.path.join(EXH, "exh_nofma.jsonl"))
    res["fma3_on_vs_off"] = jlines(os.path.join(EXH, "fmadiff.jsonl"))
    res["atan2_random_pairs"] = jlines(os.path.join(EXH, "atan2.jsonl"))
    if wt_differs:
        res["working_tree_exhaustive"] = jlines(os.path.join(EXH, "exh_wt.jsonl"))
    res["transient_events"] = jlines(os.path.join(EXH, "transient.jsonl"))   # recorded by hand, see README

    out = os.path.join(B, "results_raw.json")
    json.dump(res, open(out, "w"), indent=1)
    print("raw results:", out)
    run([PY, "-I", os.path.join(HERE, "analyze_extra.py"), B, CORE, os.path.join(B, "extra.json")])
    subprocess.run([PY, "-I", os.path.join(HERE, "make_results.py"), out, os.path.join(HERE, "results.json")], check=True)


if __name__ == "__main__":
    main()
