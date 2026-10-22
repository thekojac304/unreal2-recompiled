"""Condense build/x87/results_raw.json (run_x87.py) into the committed tests/x87/results.json.

Usage: python -I make_results.py <results_raw.json> <results.json>
The output holds counts, hashes, verdicts and a few argument/result bit patterns of math operations;
no bytes of the game binaries.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

# Step 1 analysis (disassembly of Core.dll with tools/xrt/discover.py; see README.md)
ENGINE_USAGE = {
    "0x16fa0": {"name": "appSin(double)", "body": "fld qword [esp+4]; fsin; ret",
                "callers": ["FGlobalMath::FGlobalMath (sine table, executed)", "UObject::execSin (script Sin, float in/out)",
                            "FQuat::FQuatToAngAxis", "one unnamed function at rva 0x335f0"],
                "engine_inputs": "sine table: x_i = (double)(2*i) * (pi/16384), i = 0..16383 (fild dword i; fadd st,st; "
                                 "fmul qword pi/16384), result stored with fstp dword (float32) into GMath; execSin: any float",
                "storage": "float32"},
    "0x16fc0": {"name": "appCos(double)", "body": "fld qword [esp+4]; fcos; ret",
                "callers": ["UObject::execCos (float in/out)", "FQuat::AngAxisToFQuat", "rva 0x335f0"],
                "engine_inputs": "script Cos(float)", "storage": "float32"},
    "0x16fe0": {"name": "appTan(double)", "body": "fld qword [esp+4]; fptan; fstp st(0); ret",
                "callers": ["UObject::execTan (float in/out)"], "engine_inputs": "script Tan(float)", "storage": "float32"},
    "0x16ff0": {"name": "appAtan(double)", "body": "fld qword [esp+4]; fld1; fpatan; ret",
                "callers": ["UObject::execAtan (float in/out)"], "engine_inputs": "script Atan(float)", "storage": "float32"},
    "0x17000": {"name": "appAtan2(double Y, double X)", "body": "fld qword [esp+4]; fld qword [esp+0xc]; fpatan; ret",
                "callers": ["UObject::execAtan2", "FVector::Rotation", "FCoords::OrthoRotation"],
                "engine_inputs": "script Atan2(float,float); rotations", "storage": "float32"},
    "0x17010": {"name": "appSqrt(double)", "body": "fld qword [esp+4]; fsqrt; ret",
                "callers": ["FGlobalMath::FGlobalMath (sqrt table, executed)", "appInit CPU-speed timing loop (rva 0x5b990, executed)",
                            "UObject::execSqrt/execVSize/execVSize2D", "FVector/FPoint/FQuat/FSphere size and normalisation"],
                "engine_inputs": "sqrt table: (double)i * 2^-14, i = 0..16383, stored float32; timing loop: D(n+1) = (sqrt(D(n)) + 3.14) "
                                 "+ D(n), D(0) = 0, stored double, then _ftol2(D); runs ~200 ms x 3 at start-up",
                "storage": "float32 (tables, script), float64 (timing loop)"},
    "0x16f60": {"name": "appExp(double)", "body": "fldl2e; fmul qword [esp+4]; fld st0; frndint; fxch; fsub st,st1; f2xm1; fld1; "
                                                  "faddp; fscale; fstp st1; ret",
                "callers": ["UObject::execExp (float in/out)"], "engine_inputs": "script Exp(float)", "storage": "float32"},
    "0x16f80": {"name": "appLoge(double)", "body": "fldln2; fld qword [esp+4]; fyl2x; ret",
                "callers": ["UObject::execLoge (float in/out)"], "engine_inputs": "script Loge(float)", "storage": "float32"},
}
OTHER_SITES = {
    "0x5d510 (_ftol2, statically linked CRT)": "fistp qword (RC=nearest) + fild + correction = C truncation; executed (timing loop, "
                                               "every float->int cast); the only fistp in Core.dll",
    "fild qword sites": "appSeconds (rva 0x33460: rdtsc delta), appInit (rva 0x5b990: rdtsc values, each immediately stored with "
                        "fstp qword), stats sort/StaticExit (cycle counters x GSecondsPerCycle); no fild/fistp qword copy idiom",
    "UCC.exe": "no transcendental, frndint, fsqrt, fistp; one fild",
    "not present in Core.dll/UCC.exe": "fsincos, fyl2xp1, fprem, fprem1, fxtract, fninit, fldcw/fnstcw, fisttp",
}


def compact_groups(groups):
    out = []
    for g in groups:
        o = {k: g[k] for k in ("set", "op", "n", "mismatch_double", "mismatch_float", "float_zero_sign_only", "nan_payload_only",
                               "c2_mismatch", "int_mismatch", "arg_mismatch", "fptan_push_mismatch", "fptan_pushed_value_mismatch",
                               "max_ulp_double_vs_hw80", "max_ulp_double_vs_hw_double", "max_ulp_float")}
        if g["mismatch_float"] or g["int_mismatch"] or g["arg_mismatch"] or g["fptan_push_mismatch"]:
            o["examples"] = [{k: e[k] for k in ("a", "a_val", "b", "idx", "hw80", "hw64", "rt64", "hw32", "rt32", "hw_i64",
                                                 "rt_i64", "hw_x", "rt_x")} for e in g["examples"][:2]]
        out.append(o)
    return out


def main():
    raw = json.load(open(sys.argv[1]))
    core = os.path.join(ROOT, "sandbox_ref", "hellofull", "System", "Core.dll")
    consts = json.loads(subprocess.run([sys.executable, "-I", os.path.join(HERE, "check_constants.py"), core],
                                       capture_output=True, text=True, check=True).stdout)
    usage = []
    for rva, fn in sorted(raw["core_x87_functions"].items()):
        u = {"rva": rva, "x87_ops": fn["ops"], "executed_in_traces": fn["executed_in"]}
        u.update(ENGINE_USAGE.get(rva, {}))
        usage.append(u)
    res = {
        "schema": "experiments/xrt/tests/x87 results v1",
        "generated": raw["generated"],
        "host": raw["host"],
        "step1_engine_usage": {"core_x87_instruction_census": raw["core_x87_census"], "functions": usage,
                               "other_sites": OTHER_SITES, "constants_check": consts},
        "records": {"count": raw["records_generated"], "hw32": raw["records_hw32"],
                    "models": {m["model"]: compact_groups(m["groups"]) for m in raw["records"]["models"]}},
        "timing_loop": {"hw": raw["timing_loop_hw"], "rt": raw["timing_loop_rt"]},
        "exhaustive_float32": raw["exhaustive"],
        "exhaustive_float32_fma3_disabled": raw["exhaustive_nofma"],
        "exhaustive_hw_crosscheck": raw["exhaustive_hw_crosscheck"],
        "exhaustive_hw32_runs": raw["exhaustive_hw32_runs"],
        "fma3_on_vs_off": raw["fma3_on_vs_off"],
        "atan2_random_pairs": raw["atan2_random_pairs"],
        "runtime_under_test": raw.get("runtime_under_test"),
        "transient_events": raw.get("transient_events", []),
    }
    if "working_tree_records" in raw:
        res["working_tree_runtime"] = {
            "note": "runtime/xrt_cpu.c changed in the working tree during this validation (another session adopted the pfix "
                    "prototype); that snapshot was measured separately with the same records and exhaustive passes",
            "records_bit_identical_to_pfix_model": raw.get("working_tree_records_equal_pfix_model"),
            "records": compact_groups(raw["working_tree_records"]["models"][0]["groups"]),
            "timing_loop": raw.get("timing_loop_working_tree"),
            "exhaustive_float32": raw.get("working_tree_exhaustive", []),
        }
    extra = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "extra.json")
    if os.path.exists(extra):
        res["analysis"] = json.load(open(extra))
    with open(sys.argv[2], "w", newline="\n") as f:
        json.dump(res, f, indent=1)
        f.write("\n")
    print("wrote", sys.argv[2])


if __name__ == "__main__":
    main()
