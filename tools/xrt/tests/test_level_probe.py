"""Focused safety regression: a second level run must fail before restoring any shared sandbox files."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
import json
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_xrt as R
import level_summary as S


class LevelLock(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows client lock")
    def test_other_client_does_not_restore_inputs(self):
        path = Path(R.WS) / "sandbox_cmp/level/System/Unreal2.ini"
        before = path.read_bytes() if path.exists() else None
        with R.CaseLock("graphics-client-session"):
            p = subprocess.run([sys.executable, "-I", str(Path(R.WS) / "tools/xrt/level_probe.py"), "candidate"],
                               capture_output=True, timeout=20)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"locked by another invocation", p.stderr)
        self.assertEqual(before, path.read_bytes() if path.exists() else None)

    @unittest.skipUnless(os.name == "nt", "Windows sandbox lock")
    def test_locked_run_does_not_restore_inputs(self):
        path = Path(R.WS) / "sandbox_cmp/level/System/Unreal2.ini"
        before = path.read_bytes() if path.exists() else None
        with R.CaseLock("level"):
            p = subprocess.run([sys.executable, "-I", str(Path(R.WS) / "tools/xrt/level_probe.py"), "candidate"],
                               capture_output=True, timeout=20)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"locked by another invocation", p.stderr)
        self.assertEqual(before, path.read_bytes() if path.exists() else None)


class Evidence(unittest.TestCase):
    def test_fatal_message_outcome_is_controlled_stop_not_gameplay(self):
        root = Path(R.WS) / "experiments/xrt/build/test_tmp"
        root.mkdir(exist_ok=True, parents=True)
        with tempfile.TemporaryDirectory(dir=root) as d:
            p=Path(d)
            meta={"id":"test","exit_code":75,"candidate":{},"runtime_sources":{},
                  "before":{"System/Unreal2.exe":"exe","System/Engine.dll":"engine"}}
            report={"run_id":"test","events_dropped":0,"exit_code":75,"outcome":"unsupported GetDC",
                    "modules":[{"name":"Unreal2.exe","sha256":"exe","functions_executed":1,"hit_rvas":[]},
                               {"name":"Engine.dll","sha256":"engine","functions_executed":1,"hit_rvas":["b5be0"]}],
                    "events":[{"kind":"fatal","code":75,"message":"unsupported GetDC"}]}
            (p/"meta.json").write_text(json.dumps(meta))
            (p/"report.json").write_text(json.dumps(report))
            result=S.candidate(p)
            self.assertTrue(result["milestones"]["L5"])
            self.assertFalse(result["milestones"]["L3"]) # a Tick entry alone proves no selected-map completed tick
            self.assertIsNone(result["world_state"])
            report["events"].append({"kind":"file_open","path":"..\\Maps\\CS_Intro.un2","ok":True})
            (p/"report.json").write_text(json.dumps(report))
            result=S.candidate(p)
            self.assertTrue(result["milestones"]["L1"])
            self.assertIsNone(result["milestones"]["L2"])
            self.assertIsNone(result["milestones"]["L3"]) # opening a map cannot establish actor initialization or a tick


if __name__ == "__main__":
    unittest.main()
