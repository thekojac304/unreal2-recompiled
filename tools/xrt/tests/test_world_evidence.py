"""Counterexamples to false level/frame success claims in the original observer."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from world_evidence import summarize


def fixture():
    events = []
    def point(label, **kw):
        events.append(dict(seq=len(events)+1, thread=0, label=label, esp="0x1000",
                           stack_top="0x10390b77", eax="0x00000000", ecx="0x2000", **kw))
    point("UGameEngine.LoadMap")
    point("FileReader.open", diagnostic_arg0_wide="..\\Maps\\CS_Intro.un2")
    point("FileReader.CreateFileW.return")
    for label in ["AActor.eventPreBeginPlay", "AActor.eventBeginPlay", "AActor.eventPostBeginPlay"]:
        point(label)
    point("UGameEngine.LoadMap.return")
    events[-1]["eax"] = "0x2000"
    point("ULevel.Tick")
    events[-1]["stack_top"] = "0x10393c1e"
    point("ULevel.Tick.return")
    events[-1]["stack_top"] = "0x10393c1e"
    point("UGameEngine.WorldTick.return", rva="0x93c1e")
    return dict(complete=True, events_dropped=0, exceptions_dropped=0, events=events,
                modules=[dict(name="Engine.dll", base="0x10300000")])


class WorldEvidence(unittest.TestCase):
    def test_map_open_and_postload_without_return_are_insufficient(self):
        trace = fixture()
        trace["events"] = trace["events"][:3]
        result = summarize(trace)
        self.assertFalse(result["selected_level_initialized"])
        self.assertFalse(result["completed_selected_world_ticks"])

    def test_selected_world_return_and_tick_are_correlated(self):
        result = summarize(fixture())
        self.assertTrue(result["selected_level_initialized"])
        self.assertEqual(len(result["completed_selected_world_ticks"]), 1)

    def test_later_success_cannot_repair_a_failed_selected_map_call(self):
        trace = fixture()
        trace["events"][6].update(label="UGameEngine.LoadMap.failure.return", eax="0x0")
        for label in ["UGameEngine.LoadMap", "UGameEngine.LoadMap.return"]:
            event = deepcopy(trace["events"][0])
            event.update(label=label, seq=len(trace["events"])+1, eax="0x3000")
            trace["events"].append(event)
        self.assertFalse(summarize(trace)["selected_level_initialized"])

    def test_entry_level_tick_does_not_count_for_selected_map(self):
        trace = fixture()
        trace["events"][7]["ecx"] = "0x3000"
        self.assertFalse(summarize(trace)["completed_selected_world_ticks"])

    def test_tick_entry_or_ret_without_return_to_caller_is_insufficient(self):
        for kept in [8, 9]:
            trace = fixture()
            trace["events"] = trace["events"][:kept]
            self.assertFalse(summarize(trace)["completed_selected_world_ticks"])

    def test_drops_or_incomplete_trace_cannot_establish_success(self):
        for field, value in [("complete", False), ("events_dropped", 1), ("exceptions_dropped", 1)]:
            trace = fixture()
            trace[field] = value
            self.assertFalse(summarize(trace)["selected_level_initialized"])
            self.assertFalse(summarize(trace)["completed_selected_world_ticks"])

    def test_hresult_without_game_call_does_not_establish_device_or_frame(self):
        trace = fixture()
        for label in ["D3D.CreateDevice.return.2", "D3D.Present.return.1"]:
            event = deepcopy(trace["events"][-1])
            event.update(label=label, seq=len(trace["events"])+1)
            trace["events"].append(event)
        result = summarize(trace)
        self.assertFalse(result["game_create_device"])
        self.assertFalse(result["game_present"])


if __name__ == "__main__":
    unittest.main()
