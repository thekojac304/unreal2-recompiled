import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from supervisor import core as C


class Policy(unittest.TestCase):
    def setUp(self):
        self.ident = str(uuid.uuid4())
        self.batch = dict(id=str(uuid.uuid4()), started_at=1000, expires_at=10000, genuine_limit=5)
        self.r = dict(version=1, id=self.ident, batch_id=self.batch["id"], created_at=1001, expires_at=1100,
                      objective="Measure registered-window callback boundary", candidate="out/desktop-supervisor/candidates/" + self.ident + ".json",
                      manifest_sha256="a" * 64, expected_stop=dict(kind="permanent-stop", guest_address="0x0696f292"),
                      scope=C.SCOPE, timeout_seconds=60)

    def parse(self, r=None):
        return C.parse_request(self.r if r is None else r, self.batch, now=1002)

    def test_valid_request(self):
        self.assertEqual(self.parse(), self.r)

    def test_strict_fields_and_types(self):
        for field, value in [("argv", ["cmd.exe"]), ("timeout_seconds", 61), ("timeout_seconds", True),
                             ("version", True), ("objective", "short"), ("manifest_sha256", "x" * 64),
                             ("candidate", "E:/evil.exe"), ("scope", "gameplay"), ("id", "replay")]:
            with self.subTest(field=field), self.assertRaises(C.Rejected):
                r = copy.deepcopy(self.r);r[field] = value;self.parse(r)

    def test_authorization_stale_future_expired(self):
        for field, value in [("batch_id", str(uuid.uuid4())), ("created_at", 999), ("created_at", 1010),
                             ("expires_at", 1001), ("expires_at", 9999)]:
            with self.subTest(field=field), self.assertRaises(C.Rejected):
                r = copy.deepcopy(self.r);r[field] = value;self.parse(r)
        self.batch["genuine_limit"] = 0
        with self.assertRaises(C.Rejected):self.parse()

    def test_permanent_stop_cannot_advance(self):
        self.r["expected_stop"]["guest_address"] = "0x0696f293"
        with self.assertRaises(C.Rejected):self.parse()
        self.r["expected_stop"] = dict(kind="first-unsupported-or-permanent",guest_address="0x0696f292")
        self.parse()

    def test_unsupported_is_narrow(self):
        self.r["expected_stop"] = dict(kind="unsupported-method", code=76, format="WM_GETOBJECT: unmeasured arguments")
        self.parse()
        for fmt in ["x87 mismatch", "WM_GETOBJECT: corrupt pointer", "arbitrary fatal"]:
            self.r["expected_stop"]["format"] = fmt
            with self.assertRaises(C.Rejected):self.parse()

    def test_classified_fatal_can_continue_only_after_verified_termination(self):
        stop=dict(kind='first-unsupported-or-permanent',guest_address='0x0696f292')
        fatal=dict(kind='fatal_entry',code=76,format='WM_GETOBJECT: unmeasured arguments',diagnostic_read_errors=[],runtime_fatal_body_executed=False)
        rows=[fatal,dict(kind='terminated_before_continue')]
        self.assertTrue(C.expected_fatal(rows,stop))
        self.assertFalse(C.expected_fatal(rows[:1],stop))
        for key,value in [('code',74),('format','x87 mismatch'),('diagnostic_read_errors',['failed']),('runtime_fatal_body_executed',True)]:
            bad=copy.deepcopy(rows);bad[0][key]=value;self.assertFalse(C.expected_fatal(bad,stop))
        self.assertFalse(C.expected_fatal(rows+[dict(fatal)],stop))
        fatal['code']=75;fatal['format']='call to import %s, which has no host implementation (from %s)'
        self.assertFalse(C.expected_fatal(rows,stop))
        rows.append(dict(kind='import_boundary',symbol='user32.dll!GetSomething'))
        self.assertTrue(C.expected_fatal(rows,stop))
        rows[-1]['symbol']='kernel32.dll!DeleteFileA';self.assertFalse(C.expected_fatal(rows,stop))

    def test_json_duplicates_nonfinite_oversize(self):
        for value in [b'{"a":1,"a":2}', b'{"a":NaN}', b"{", b"[]" * C.MAX_BYTES]:
            with self.subTest(value=value[:40]), self.assertRaises(C.Rejected):C.loads(value)

    def test_paths(self):
        with tempfile.TemporaryDirectory(dir=C.ROOT / "out") as d:
            root = Path(d);(root / "approved").mkdir();(root / "approved/file").touch()
            self.assertTrue(C.project_path("approved/file", ["approved"], root=root).is_file())
            for value in ["approved/../file", "approved//file", "approved/file.", "approved/NUL", "approved/file:ads",
                          "approved\\file", "C:/file", "//server/share", "other/file", "approved/./file"]:
                with self.subTest(value=value), self.assertRaises(C.Rejected):C.project_path(value, ["approved"], root=root)
            import os
            os.link(root / "approved/file", root / "approved/link")
            with self.assertRaises(C.Rejected):C.project_path("approved/link", ["approved"], root=root)

    def test_junction_escape(self):
        import _winapi
        with tempfile.TemporaryDirectory(dir=C.ROOT / "out") as d:
            root=Path(d);(root/'approved').mkdir();(root/'elsewhere').mkdir();(root/'elsewhere/file').touch()
            _winapi.CreateJunction(str(root/'elsewhere'),str(root/'approved/junction'))
            with self.assertRaises(C.Rejected):C.project_path('approved/junction/file',['approved'],root=root)
            (root/'approved/junction').rmdir()

    def test_source_and_dependency_mismatches(self):
        with tempfile.TemporaryDirectory(dir=C.ROOT/'out') as d:
            root=Path(d);exe=root/'experiments/xrt/build/desktop-supervisor/fixture.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
            src=root/'tools/xrt/fixture.c';src.parent.mkdir(parents=True);src.write_text('source')
            m=dict(version=1,kind='fixture',executable=exe.relative_to(root).as_posix(),sha256=C.sha(exe),pdb_sha256=None,
                   build_record=None,build_record_sha256=None,sources={src.relative_to(root).as_posix():'0'*64},dependencies={},fixture_case='ok-a')
            self.r['scope']=C.FIXTURE_SCOPE
            with self.assertRaises(C.IntegrityFailure):C.validate_manifest(m,self.r,root=root)
            m['sources']={src.relative_to(root).as_posix():C.sha(src)}
            m['dependencies']={exe.relative_to(root).as_posix():'0'*64}
            with self.assertRaises(C.IntegrityFailure):C.validate_manifest(m,self.r,root=root)

    def test_durable_replay_budget_unchanged_hash(self):
        with tempfile.TemporaryDirectory(dir=C.ROOT / "out") as d:
            path = Path(d) / "ledger.jsonl"
            ledger = C.Ledger(path)
            for i in range(5):
                self.r["id"] = str(uuid.uuid4())
                ledger.claim(self.r, dict(kind="genuine", sha256=str(i) * 64), self.batch)
            with self.assertRaises(C.Rejected):ledger.claim(self.r, dict(kind="genuine", sha256="f" * 64), self.batch)
            self.r["id"] = str(uuid.uuid4())
            with self.assertRaises(C.Rejected):ledger.claim(self.r, dict(kind="genuine", sha256="f" * 64), self.batch)
            ledger = C.Ledger(path);self.batch["id"] = str(uuid.uuid4())
            with self.assertRaises(C.Rejected):ledger.claim(self.r, dict(kind="genuine", sha256="0" * 64), self.batch)
            path.write_text(path.read_text().replace('"sequence": 2', '"sequence": 99'))
            with self.assertRaises(C.IntegrityFailure):C.Ledger(path)

    def test_manifest_mismatch_and_fixture_allowlist(self):
        with tempfile.TemporaryDirectory(dir=C.ROOT / "out") as d:
            root = Path(d);exe = root / "experiments/xrt/build/desktop-supervisor/fixture.exe";exe.parent.mkdir(parents=True);exe.write_bytes(b"fixture")
            src=root / "tools/xrt/fixture.c";src.parent.mkdir(parents=True);src.write_text("source")
            self.r["scope"] = C.FIXTURE_SCOPE
            m=dict(version=1,kind="fixture",executable=exe.relative_to(root).as_posix(),sha256=C.sha(exe),pdb_sha256=None,
                   build_record=None,build_record_sha256=None,sources={src.relative_to(root).as_posix():C.sha(src)},dependencies={},fixture_case="ok-a")
            C.validate_manifest(m,self.r,root=root)
            m["fixture_case"]="cmd.exe"
            with self.assertRaises(C.Rejected):C.validate_manifest(m,self.r,root=root)
            m["fixture_case"]="ok-a";exe.write_bytes(b"tampered")
            with self.assertRaises(C.IntegrityFailure):C.validate_manifest(m,self.r,root=root)

    def test_ledger_freezes_nested_authorization_records(self):
        with tempfile.TemporaryDirectory(dir=C.ROOT/'out') as d:
            ledger=C.Ledger(Path(d)/'ledger.jsonl')
            ledger.append('batch-authorized',batch=self.batch)
            self.batch['recovery_policy']='unapproved'
            self.assertNotIn('recovery_policy',ledger.rows[0]['batch'])
            self.assertEqual(ledger.rows,C.Ledger(ledger.path).rows)

    def test_programdata_comes_from_windows_not_inherited_override(self):
        import os
        from unittest.mock import patch
        from supervisor.fixture import environment
        baseline=environment(C.ROOT/'sandbox_cmp')['ProgramData']
        with patch.dict(os.environ,ProgramData='E:\\untrusted-folder',XRT_BINARY='untrusted'):
            env=environment(C.ROOT/'sandbox_cmp')
        self.assertEqual(env['ProgramData'],baseline)
        self.assertNotIn('XRT_BINARY',env)

    def test_environment_gate_fails_closed(self):
        from supervisor.environment import gate
        class Legacy:
            def environment_gate(self, data):
                C.require(data.get("physical") and data.get("input") and data.get("nvidia") and data.get("console"), "desktop gate")
                return data
        data=dict(physical=True,input=True,nvidia=True,console=True,session=1)
        self.assertEqual(gate(data,data,Legacy()),data)
        for key in ("physical","input","nvidia","console"):
            bad=dict(data);bad[key]=False
            with self.assertRaises(C.Rejected):gate(bad,data,Legacy())
        bad=dict(data);bad["session"]=2
        with self.assertRaises(C.IntegrityFailure):gate(bad,data,Legacy())


if __name__ == "__main__":unittest.main()
