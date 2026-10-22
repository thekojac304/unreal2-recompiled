"""Summarise uctrace dependency traces into the X1 dependency map.

Usage: python -I tools/xrt/depmap.py <trace.json>... [--out depmap.json]
Prints, per case: game modules executed, functions first-hit per module, imports called from
game modules, exceptions, x87 control words, and the union across cases.
"""
import json
import sys

SYSTEM_HINTS = ("\\windows\\", "\\system32\\", "\\syswow64\\", "\\winsxs\\")


def main():
    args = sys.argv[1:]
    out = args[args.index("--out") + 1] if "--out" in args else None
    files = [a for a in args if a.endswith(".json") and a != out]
    union_funcs, union_imps, cases = {}, {}, {}
    for f in files:
        d = json.load(open(f))
        name = f.replace("\\", "/").rsplit("/", 1)[-1][:-5]
        game_mods = [m for m in d["modules"] if not any(h in m["path"].lower() for h in SYSTEM_HINTS)]
        c = {"exit_code": d["exit_code"], "threads": d["threads"],
             "game_modules_mapped": [m["name"] for m in game_mods],
             "functions_hit": {m["name"]: m["hit"] for m in d["modules"] if m["instrumented"]},
             "imports_called": len(d["imports"]),
             "cxx_throws": sum(1 for e in d["exceptions"] if e["code"] == "0xe06d7363"),
             "other_exceptions": sorted({e["code"] for e in d["exceptions"] if e["code"] != "0xe06d7363"}),
             "x87_cw": [w["cw"] for w in d["x87_control_words_seen"]], "controlfp_calls": d["controlfp_calls"]}
        cases[name] = c
        for m in d["modules"]:
            if m["instrumented"]:
                union_funcs.setdefault(m["name"], set()).update(m["hit_rvas"])
        for i in d["imports"]:
            union_imps[i["name"]] = union_imps.get(i["name"], 0) + i["calls_from_instrumented"]
        print(f"{name:10} exit={c['exit_code']} threads={c['threads']} hit={c['functions_hit']} imports={c['imports_called']} "
              f"throws={c['cxx_throws']} other_exc={c['other_exceptions']} cw={c['x87_cw']}")
        print(f"           game modules mapped: {', '.join(c['game_modules_mapped'])}")
    print("union of functions executed:", {k: len(v) for k, v in union_funcs.items()})
    print("union of imports called from game code:", len(union_imps))
    if out:
        json.dump({"cases": cases, "union_functions": {k: sorted(v) for k, v in union_funcs.items()},
                   "union_imports": dict(sorted(union_imps.items()))}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
