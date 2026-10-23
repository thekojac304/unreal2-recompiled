"""Extract conservative original-client world evidence from explicit instruction observers.

The map-open must occur within a matched LoadMap call. A tick must use that returned
world, reach its RET and then its caller. Graphics HRESULTs come from game call sites.
This establishes API/world execution, not what pixels the user saw or interactive play.
"""
import argparse
from collections import Counter
import json
from pathlib import Path


def summarize(trace):
    valid = (trace.get("complete") is True and trace.get("events_dropped") == 0
             and trace.get("exceptions_dropped") == 0)
    events = trace.get("events", [])
    def points(label):
        return [e for e in events if e.get("label") == label]
    def key(e):
        return e.get("thread"), e.get("esp"), e.get("stack_top")
    selected = None
    for entry in points("UGameEngine.LoadMap"):
        returns = sorted([e for e in (points("UGameEngine.LoadMap.return") + points("UGameEngine.LoadMap.failure.return"))
                          if e["seq"] > entry["seq"] and key(e) == key(entry)], key=lambda e: e["seq"])
        if not returns:
            continue
        ret = returns[0]
        if ret["label"] != "UGameEngine.LoadMap.return" or not int(ret["eax"], 16):
            continue
        for opened in points("FileReader.open"):
            if (entry["seq"] < opened["seq"] < ret["seq"] and opened["thread"] == entry["thread"]
                    and opened.get("diagnostic_arg0_wide", "").replace("\\", "/").lower().endswith("/cs_intro.un2")):
                read_returns = [e for e in points("FileReader.CreateFileW.return")
                                if e["seq"] == opened["seq"] + 1 and e["thread"] == opened["thread"]
                                and e["eax"] != "0xffffffff"]
                if read_returns:
                    counts = Counter(e.get("label") for e in events if entry["seq"] < e["seq"] < ret["seq"])
                    selected = {"entry_seq": entry["seq"], "open_seq": opened["seq"],
                                "return_seq": ret["seq"], "world": ret["eax"],
                                "actors": {name: counts[name] for name in ["AActor.eventPreBeginPlay",
                                            "AActor.eventBeginPlay", "AActor.eventPostBeginPlay"]}}
    ticks = []
    if selected:
        engine = next(m for m in trace["modules"] if m["name"].lower() == "engine.dll")
        for entry in points("ULevel.Tick"):
            if entry["seq"] <= selected["return_seq"] or entry["ecx"] != selected["world"]:
                continue
            returns = [e for e in points("ULevel.Tick.return") if e["seq"] > entry["seq"] and key(e) == key(entry)]
            if not returns:
                continue
            ret = returns[0]
            callers = [e for e in points("UGameEngine.WorldTick.return") if e["seq"] > ret["seq"]
                       and e["thread"] == entry["thread"]
                       and int(entry["stack_top"], 16) == int(engine["base"], 16) + int(e["rva"], 16)]
            if callers:
                ticks.append({"entry_seq": entry["seq"], "ret_seq": ret["seq"], "caller_seq": callers[0]["seq"]})
    def successful_calls(call_label, return_label, popped):
        pairs = []
        for ret in points(return_label):
            calls = [e for e in points(call_label) if e["seq"] < ret["seq"] and e["thread"] == ret["thread"]
                     and int(e["esp"], 16) + popped == int(ret["esp"], 16)]
            if calls and ret["eax"] == "0x00000000":
                pairs.append({"call_seq": calls[-1]["seq"], "return_seq": ret["seq"], "hresult": ret["eax"]})
        return pairs
    devices = sum((successful_calls(f"D3D.CreateDevice.call.{i}", f"D3D.CreateDevice.return.{i}", 28)
                   for i in [1, 2]), [])
    presents = successful_calls("D3D.Present.call.1", "D3D.Present.return.1", 20)
    return {"observer_complete_without_drops": valid, "selected_map": selected,
            "selected_level_initialized": bool(valid and selected and all(selected["actors"].values())),
            "completed_selected_world_ticks": ticks if valid else [],
            "game_create_device": devices if valid else [], "game_present": presents if valid else [],
            "interactive_play_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.trace.read_text())), indent=2))
