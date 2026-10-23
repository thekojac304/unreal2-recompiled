"""Structured evidence for the bounded client experiment. A known blocker is NEVER gameplay PASS.

Usage: level_summary.py --reference <run> <run> --candidate <run> [<run>] --out <new-json>
World completion is deliberately unverified if a future run advances beyond these observers. No actor
state is invented when LoadMap was not reached, and a tick entry is never promoted to a completed tick.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_xrt as R


def read(path):
    return json.loads(path.read_text())


def reference(root):
    if (root / "INVALIDATED.json").exists():
        raise ValueError(f"invalidated reference: {root}")
    meta, trace = read(root / "meta.json"), read(root / "trace.json")
    if trace.get("run_id") != meta["id"] or not trace.get("complete") or not trace.get("debuggee_terminated"):
        raise ValueError("incomplete or misbound original trace")
    if trace.get("events_dropped") or trace.get("calls_dropped"):
        raise ValueError("original evidence was dropped")
    events = trace["events"]
    labels = {e.get("label"): e for e in events if e.get("kind") == "point"}
    load = "UGameEngine.LoadMap" in labels
    caps_call, caps_return = labels.get("D3D.GetDeviceCaps.call"), labels.get("D3D.GetDeviceCaps.return")
    state = {"L0": "UGameEngine.Init" in labels, "L1": None if load else False,
             "L2": None if load else False, "L3": None if load else False, "L4": None if load else False,
             "L5": trace["termination_reason"] in ["event_limit", "time_limit"]}
    boundary = {"factory_non_null": bool(int(labels["D3D.Direct3DCreate8.return"]["eax"],16)) if "D3D.Direct3DCreate8.return" in labels else None,
                "adapter_count": int(labels["D3D.GetAdapterCount.return"]["eax"],16) if "D3D.GetAdapterCount.return" in labels else None,
                "adapter": int(caps_call["stack_args"][0],16) if caps_call else None,
                "device_type": int(caps_call["stack_args"][1],16) if caps_call else None,
                "caps_hresult": caps_return["eax"] if caps_return else None,
                "error": labels.get("Launcher.Error.Serialize", {}).get("diagnostic_arg0_wide")}
    return {"path": R.rel(str(root)), "milestones": state, "boundary": boundary, "world_state": None,
            "world_state_reason": "LoadMap not entered" if not load else "completion/state observers not yet implemented; no pass",
            "module_bases": {m["name"]:m["base"] for m in trace["modules"] if m["name"] in ["Unreal2.exe","Core.dll","Engine.dll","GlmLib.dll","Window.dll","WinDrv.dll","D3DDrv.dll"]},
            "factory_pointer": labels.get("D3D.Direct3DCreate8.return",{}).get("eax"),
            "input_hashes": meta["before"], "exit_code": trace["exit_code"], "termination": trace["termination_reason"]}


def candidate(root):
    meta, report = read(root / "meta.json"), read(root / "report.json")
    if report.get("run_id") != meta["id"] or report.get("events_dropped"):
        raise ValueError("candidate report invalid or incomplete")
    modules = {m["name"]:m for m in report["modules"]}
    if "Unreal2.exe" not in modules or "UCC.exe" in modules:
        raise ValueError("candidate did not map the real client executable")
    for name, module in modules.items():
        if module["sha256"] != meta["before"].get("System/"+name):
            raise ValueError(f"candidate input/lift mismatch: {name}")
    events = report["events"]
    has_init = any(int(r,16)==0x8f460 for r in modules.get("Engine.dll",{}).get("hit_rvas",[]))
    opened = any(e.get("kind")=="file_open" and e.get("ok") and e.get("path","").replace("\\","/").lower().endswith("cs_intro.un2") for e in events)
    fatal = [e for e in events if e["kind"]=="fatal"]
    return {"path": R.rel(str(root)), "binary": meta["candidate"], "runtime_sources": meta["runtime_sources"],
            "milestones": {"L0":has_init,"L1":opened,"L2":None if opened else False,"L3":None if opened else False,
                           "L4":None if opened else False,
                           "L5":bool(fatal) and fatal[-1].get("code")==report["exit_code"]==meta["exit_code"]
                                and fatal[-1].get("message")==report["outcome"]},
            "world_state":None,"world_state_reason":"client stopped before map initialization",
            "outcome":report["outcome"],"exit_code":report["exit_code"],"fatal":fatal,
            "modules_executed":{n:m["functions_executed"] for n,m in modules.items()},"input_hashes":meta["before"]}


def differences(a,b,prefix=""):
    out=[]
    for key in sorted(a.keys() | b.keys()):
        if a.get(key)!=b.get(key): out.append({"field":prefix+key,"a":a.get(key),"b":b.get(key)})
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference",nargs="+",type=Path,required=True)
    ap.add_argument("--candidate",nargs="+",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    refs=[reference(p) for p in a.reference]
    cands=[candidate(p) for p in a.candidate]
    if any(r["milestones"]["L1"] is not False for r in refs+cands):
        raise ValueError("execution advanced beyond this bounded blocker profile; add completion/state observers before classifying")
    comparisons=[]
    for other in refs[1:]:
        comparisons.append({"a":refs[0]["path"],"b":other["path"],"input_differences":differences(refs[0]["input_hashes"],other["input_hashes"]),
                            "boundary_differences":differences(refs[0]["boundary"],other["boundary"]),
                            "module_base_differences":differences(refs[0]["module_bases"],other["module_bases"]),
                            "factory_pointers":[refs[0]["factory_pointer"],other["factory_pointer"]]})
    stable={"map":"CS_Intro.un2","reference_milestones":refs[0]["milestones"],"boundary":refs[0]["boundary"],"world_state":None}
    summary={"verdict":"BLOCKED_BEFORE_LEVEL_LOAD","references":refs,"candidates":cands,"repeat_comparisons":comparisons,
             "structured_boundary_summary":stable,"boundary_sha256":hashlib.sha256(json.dumps(stable,sort_keys=True).encode()).hexdigest(),
             "world_comparison":{"performed":False,"reason":"no selected-map world or completed tick on either side","digest":None},
             "controls":{"clock":"uncontrolled","random_seed":"uncontrolled","input":"same command/config/content restored before each run"},
             "known_crt":{"expanded_mismatches":110,"pending":1796,"acp932_differences":6,"status":"open baseline; not passes"}}
    with a.out.open("x",encoding="utf-8") as f:json.dump(summary,f,indent=2)
    print(a.out)
    return 0


if __name__=="__main__":
    sys.exit(main())
