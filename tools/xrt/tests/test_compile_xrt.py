"""Unit tests for the compiler-milestone driver (tools/xrt/compile_xrt.py). No UCC run is executed.

  python -I -m unittest discover -s tools/xrt/tests -p "test_compile_xrt.py" -v

Layers:
  Logic       ini derivation, compile classification, package diff classification on synthetic packages, GUID
              checks, create_guid-vs-header evidence, XCP line extraction, expected-line comparison, combination
              matrix, write policy, argument validation.
  Judging     the real judging code (run_xrt.collect_* plus the driver's checks) on synthetic raw run directories:
              compile runs of both compilers, mutations of them, and a synthetic invocation (compiles + the four
              execution combinations) judged fresh and re-evaluated.
  Real data   the derivation applied to the install's Unreal2.ini (read only); skipped when it is not present.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import compile_xrt as C  # noqa: E402
import run_xrt as R  # noqa: E402

TMP_ROOT = os.path.join(R.WS, "experiments", "xrt", "build", "test_tmp")   # git-ignored
INSTALL_INI = r"E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening\singleplayer\System\Unreal2.ini"


def mkdtemp():
    os.makedirs(TMP_ROOT, exist_ok=True)
    return tempfile.mkdtemp(dir=TMP_ROOT)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------------------------------------ synthetic packages
def compact(v):
    sign, v = (0x80 if v < 0 else 0), abs(v)
    b0 = sign | (v & 0x3F)
    v >>= 6
    out = [b0 | (0x40 if v else 0)]
    while v:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
    return bytes(out)


GUID_A = bytes.fromhex("56c93e646550574fa9addfd3a68bda36")      # version nibble 4, variant 10xx
GUID_B = bytes.fromhex("85856fc384e0c34c82d1ef2c950516fd")


def g4(n):
    """a distinct RFC 4122 v4-shaped GUID (Windows memory layout) per n"""
    b = bytearray(hashlib.sha256(bytes([n])).digest()[:16])
    b[7] = 0x40 | (b[7] & 0x0F)
    b[8] = 0x80 | (b[8] & 0x3F)
    return bytes(b)


def make_pkg(guid=GUID_A, names=("None", "Core", "Class", "XrtCompileProbe"), payload=b"\x01\x02\x03\x04\x05",
             export_flags=0x70004):
    """a minimal, valid package (version 110, licensee 2609): 1 generation, names, 1 import, 1 export"""
    payload_off = 64
    name_off = payload_off + len(payload)
    names_blob = b"".join(compact(len(n) + 1) + n.encode("latin-1") + b"\0" + struct.pack("<I", 0x70010) for n in names)
    import_off = name_off + len(names_blob)
    imports_blob = compact(1) + compact(2) + struct.pack("<i", 0) + compact(3)
    export_off = import_off + len(imports_blob)
    exports_blob = (compact(-1) + compact(0) + struct.pack("<i", 0) + compact(3) + struct.pack("<I", export_flags)
                    + compact(len(payload)) + compact(payload_off))
    header = struct.pack("<IIIiiiiii", 0x9E2A83C1, (2609 << 16) | 110, 1, len(names), name_off, 1, export_off, 1,
                         import_off) + guid + struct.pack("<iii", 1, 1, len(names))
    assert len(header) == 64
    return header + payload + names_blob + imports_blob + exports_blob


def make_golem(guid=GUID_A):
    """the 64-byte header-only package layout of Golem.u (no names, imports or exports)"""
    return struct.pack("<IIIiiiiii", 0x9E2A83C1, (2609 << 16) | 110, 1, 0, 64, 0, 64, 0, 64) + guid + \
        struct.pack("<iii", 1, 0, 0)


# ------------------------------------------------------------------------------------------------ logic: ini
INI = (b"[URL]\r\nProtocol=unreal\r\nName=Pl\xe9yer\r\n[Editor.EditorEngine]\r\nExitCheck=True\r\n"
       b"EditPackages=Core\r\nEditPackages=Engine\r\nGridSize=(X=16.000000,Y=16.000000)\r\nEditPackages=Fire\r\n"
       b";EditPackages=Commented\r\n[Other.Section]\r\nEditPackages=Keep\r\nTail=1\r\n")


class IniDerivation(unittest.TestCase):
    def test_replacement_at_first_position_crlf(self):
        out, info = C.derive_ini(INI)
        want = (b"[URL]\r\nProtocol=unreal\r\nName=Pl\xe9yer\r\n[Editor.EditorEngine]\r\nExitCheck=True\r\n"
                b"EditPackages=Core\r\nEditPackages=XrtCompileProbe\r\nGridSize=(X=16.000000,Y=16.000000)\r\n"
                b";EditPackages=Commented\r\n[Other.Section]\r\nEditPackages=Keep\r\nTail=1\r\n")
        self.assertEqual(out, want)
        self.assertEqual(C.edit_packages(out), ["Core", "XrtCompileProbe"])
        self.assertEqual(C.edit_packages(INI), ["Core", "Engine", "Fire"])
        self.assertEqual(info["replaced_edit_packages"], ["Core", "Engine", "Fire"])
        self.assertEqual(info["first_edit_packages_line"], 6)

    def test_every_other_byte_unchanged(self):
        out, _ = C.derive_ini(INI)
        keep = [ln for ln in C.split_lines(INI) if not ln.startswith(b"EditPackages=") or b"Keep" in ln]
        got = [ln for ln in C.split_lines(out) if ln not in (b"EditPackages=Core\r\n", b"EditPackages=XrtCompileProbe\r\n")]
        self.assertEqual(keep, got)
        self.assertEqual(b"".join(C.split_lines(INI)), INI)
        self.assertIn(b"Pl\xe9yer", out)                    # latin-1 bytes untouched

    def test_lf_and_mixed_line_endings_kept(self):
        lf = INI.replace(b"\r\n", b"\n")
        out, _ = C.derive_ini(lf)
        self.assertNotIn(b"\r", out)
        self.assertIn(b"EditPackages=Core\nEditPackages=XrtCompileProbe\nGridSize", out)
        mixed = INI.replace(b"EditPackages=Core\r\n", b"EditPackages=Core\n").replace(b"EditPackages=Fire\r\n",
                                                                                         b"EditPackages=Fire\r\n")
        out, _ = C.derive_ini(mixed)
        self.assertIn(b"EditPackages=Core\nEditPackages=XrtCompileProbe\r\n", out)

    def test_case_and_spacing_of_key_and_section(self):
        data = b"[editor.EDITORENGINE]\r\n editpackages = Core\r\nEDITPACKAGES=Engine\r\nX=1\r\n"
        out, _ = C.derive_ini(data)
        self.assertEqual(out, b"[editor.EDITORENGINE]\r\nEditPackages=Core\r\nEditPackages=XrtCompileProbe\r\nX=1\r\n")

    def test_last_line_without_terminator(self):
        out, _ = C.derive_ini(b"[Editor.EditorEngine]\r\nEditPackages=Core")
        self.assertEqual(out, b"[Editor.EditorEngine]\r\nEditPackages=Core\r\nEditPackages=XrtCompileProbe")

    def test_missing_or_ambiguous_configuration_is_an_error(self):
        for data in (b"[URL]\r\nX=1\r\n", b"[Editor.EditorEngine]\r\nX=1\r\n",
                     b"[Editor.EditorEngine]\r\nEditPackages=Core\r\n[Editor.EditorEngine]\r\nEditPackages=Engine\r\n"):
            with self.assertRaises(R.HarnessError):
                C.derive_ini(data)

    @unittest.skipUnless(os.path.isfile(INSTALL_INI), "install Unreal2.ini not present")
    def test_install_ini(self):
        data = R.read_bytes(INSTALL_INI)                    # read only
        out, info = C.derive_ini(data)
        self.assertEqual(C.edit_packages(out), ["Core", "XrtCompileProbe"])
        self.assertGreater(len(info["replaced_edit_packages"]), 2)
        a, b = C.split_lines(data), C.split_lines(out)
        k = info["first_edit_packages_line"] - 1
        removed = [i for i, ln in enumerate(a) if C._key(C._body(ln)[0]) == b"editpackages"]
        self.assertEqual(b[:k], a[:k])
        self.assertEqual(b[k:k + 2], [b"EditPackages=Core" + C._body(a[k])[1], b"EditPackages=XrtCompileProbe" + C._body(a[removed[-1]])[1]])
        self.assertEqual(b[k + 2:], [ln for i, ln in enumerate(a) if i >= k and i not in removed])


# ------------------------------------------------------------------------------------------------ logic: classification
OK_OUT = (b"--------------------Core - Release--------------------\r\n--------------------XrtCompileProbe - Release"
          b"--------------------\r\nAnalyzing...\r\n1 Classes (IncActive=0)\r\nParsing XrtCompileProbe\r\nCompiling "
          b"XrtCompileProbe\r\nSuccess - 0 error(s), 0 warnings\r\n")
# the shape the original prints for the invalid variant (observed): the compile error leaves through appErrorf
ERR_OUT = (b"Analyzing...\r\n1 Classes (IncActive=0)\r\nParsing XrtCompileProbe\r\nCompiling XrtCompileProbe\r\n"
           b"E:\\ws\\sandbox_cmp\\xcp\\XrtCompileProbe\\Classes\\XrtCompileProbe.uc(14) : Error, Bad or missing expression "
           b"after '$'\r\nFailed due to errors.\r\r\n\r\r\nHistory: CompileError <- TryCompile <- UMakeCommandlet::Main\r\n"
           b"\r\nExiting due to error\r\n")


class Classification(unittest.TestCase):
    def cls(self, *a, **kw):
        return C.classify_compile(*a, **kw)["classification"]

    def test_success_requires_all_signals(self):
        self.assertEqual(self.cls(0, False, OK_OUT, False, True, True), "SUCCESS")

    def test_stale_package_not_written_by_the_run_is_not_success(self):
        self.assertEqual(self.cls(0, False, OK_OUT, True, False, True), "INCONSISTENT")
        self.assertEqual(self.cls(0, False, OK_OUT, True, True, True), "INCONSISTENT")    # existed before
        self.assertEqual(self.cls(0, False, OK_OUT, False, False, True), "INCONSISTENT")   # present, not written

    def test_exit_0_without_package_is_inconsistent(self):
        r = C.classify_compile(0, False, OK_OUT, False, False, False)
        self.assertEqual(r["classification"], "INCONSISTENT")
        self.assertTrue(any("no XrtCompileProbe.u" in x for x in r["reasons"]))

    def test_error_text_with_package_is_inconsistent(self):
        self.assertEqual(self.cls(1, False, ERR_OUT, False, True, True), "INCONSISTENT")
        self.assertEqual(self.cls(0, False, OK_OUT + b"Error: something\r\n", False, True, True), "INCONSISTENT")

    def test_failure_whatever_the_exit_code(self):
        for code in (0, 1, 3):
            self.assertEqual(self.cls(code, False, ERR_OUT, False, False, False), "FAILURE", code)

    def test_success_line_with_nonzero_exit_or_timeout_or_abort(self):
        self.assertEqual(self.cls(1, False, OK_OUT, False, True, True), "INCONSISTENT")
        self.assertEqual(self.cls(None, True, OK_OUT, False, True, True), "INCONSISTENT")
        self.assertEqual(self.cls(0, False, OK_OUT, False, True, True, aborted="XRT FATAL x"), "INCONSISTENT")
        self.assertEqual(self.cls(0, False, b"", False, False, False), "INCONSISTENT")
        self.assertEqual(self.cls(0, False, None, False, True, True), "INCONSISTENT")

    def test_messages(self):
        m = C.compile_messages(OK_OUT)
        self.assertTrue(m["success_line"])
        self.assertFalse(m["errors_reported"])
        self.assertEqual(m["diagnostics"], ["Success - 0 error(s), 0 warnings"])
        m = C.compile_messages(ERR_OUT)
        self.assertFalse(m["success_line"])
        self.assertTrue(m["errors_reported"])
        self.assertEqual(len(m["error_lines"]), 4)
        self.assertTrue(m["error_lines"][0].endswith("Error, Bad or missing expression after '$'"))
        self.assertTrue(C.compile_messages(b"Failure - 2 error(s), 0 warnings\r\n")["errors_reported"])
        self.assertEqual(self.cls(1, False, b"Failure - 2 error(s), 0 warnings\r\n", False, False, False), "FAILURE")


# ------------------------------------------------------------------------------------------------ logic: packages
class PackageDiff(unittest.TestCase):
    def test_reader_accepts_synthetic_packages(self):
        p = C.upkg.Package("X.u", make_pkg())
        self.assertEqual((p.version, p.licensee, p.names[3], p.exports[0].name, p.guid), (110, 2609, "XrtCompileProbe",
                                                                                        "XrtCompileProbe", GUID_A))
        self.assertEqual(C.upkg.Package("Golem.u", make_golem()).header_end, 64)

    def test_identical(self):
        r = C.compare_packages(make_pkg(), make_pkg(), "a", "b")
        self.assertEqual((r["classification"], r["differing_ranges"], r["at_most_guid"]), ("identical", [], True))

    def test_guid_only(self):
        r = C.compare_packages(make_pkg(GUID_A), make_pkg(GUID_B), "a", "b")
        self.assertEqual(r["classification"], "guid_only")
        self.assertTrue(all(36 <= s and e <= 52 for s, e in r["differing_ranges"]))
        self.assertEqual(r["unresolved_ranges"], [])
        self.assertEqual(r["structure"]["differences"], [])
        self.assertFalse(r["structure"]["guid_equal"])
        self.assertTrue(r["at_most_guid"])
        self.assertEqual(r["guid"], [GUID_A.hex(), GUID_B.hex()])

    def test_other_with_offsets(self):
        a, b = make_pkg(), make_pkg(payload=b"\x01\x02\xff\x04\x05")
        r = C.compare_packages(a, b, "a", "b")
        self.assertEqual(r["classification"], "other")
        self.assertEqual(r["differing_ranges"], [[66, 67]])
        self.assertEqual(r["unresolved_ranges"], [[66, 67]])
        self.assertFalse(r["at_most_guid"])
        d = r["structure"]["differences"]
        self.assertEqual([(x["table"], x["object"], x.get("field")) for x in d],
                         [("exports", "#1 XrtCompileProbe.XrtCompileProbe", "serialized bytes")])
        self.assertEqual(d[0]["ranges"], [[2, 3]])
        # GUID and payload together: still 'other', the GUID part is not unresolved
        r = C.compare_packages(make_pkg(GUID_A), make_pkg(GUID_B, payload=b"\x01\x02\xff\x04\x05"), "a", "b")
        self.assertEqual(r["classification"], "other")
        self.assertEqual(r["unresolved_ranges"], [[66, 67]])

    def test_size_and_table_differences(self):
        r = C.compare_packages(make_pkg(), make_pkg(payload=b"\x01\x02\x03\x04\x05\x06"), "a", "b")
        self.assertEqual(r["classification"], "other")
        self.assertEqual(r["differing_ranges"][-1][1], r["size"][1])
        tables = {x["table"] for x in r["structure"]["differences"]}
        self.assertTrue({"header", "exports"} <= tables, tables)
        r = C.compare_packages(make_pkg(), make_pkg(names=("None", "Core", "Class", "XrtCompileProbX")), "a", "b")
        self.assertIn(("names", "#3 XrtCompileProbe"), [(x["table"], x["object"]) for x in r["structure"]["differences"]])
        r = C.compare_packages(make_pkg(), make_pkg(export_flags=0x70005), "a", "b")
        self.assertEqual([x.get("field") for x in r["structure"]["differences"]], ["entry"])

    def test_unparseable_is_never_at_most_guid(self):
        bad = b"\x00" * 80
        r = C.compare_packages(bad, bad[:36] + GUID_B + bad[52:], "a", "b")
        self.assertEqual(r["classification"], "guid_only")
        self.assertFalse(r["structure"]["parsed"])
        self.assertFalse(r["at_most_guid"])

    def test_byte_ranges(self):
        self.assertEqual(C.byte_ranges(b"abcdef", b"abcdef"), [])
        self.assertEqual(C.byte_ranges(b"abcdef", b"xbcdyz"), [[0, 1], [4, 6]])
        self.assertEqual(C.byte_ranges(b"abc", b"abcde"), [[3, 5]])
        self.assertEqual(C.byte_ranges(b"abx", b"abcde"), [[2, 5]])
        self.assertEqual(C.byte_ranges(b"abcde", b"ab"), [[2, 5]])
        self.assertEqual(C.diff_class(b"a" * 60, b"a" * 36 + b"b" * 16 + b"a" * 8), "guid_only")
        self.assertEqual(C.diff_class(b"a" * 60, b"a" * 35 + b"b" * 17 + b"a" * 8), "other")
        self.assertEqual(C.diff_class(b"a" * 60, b"a" * 36 + b"b" * 17 + b"a" * 7), "other")
        self.assertEqual(C.diff_class(b"a" * 60, b"a" * 61), "other")


class Guid(unittest.TestCase):
    def test_v4_rule(self):
        g = C.guid_info(make_pkg(GUID_A))
        self.assertEqual((g["hex"], g["version_nibble"], g["variant_bits"], g["rfc4122_v4"]), (GUID_A.hex(), 4, "0x80", True))
        self.assertTrue(C.guid_info(make_pkg(GUID_B))["rfc4122_v4"])
        for byte7, byte8 in ((0x1f, 0xa9), (0x4f, 0xc9), (0x4f, 0x29), (0x5f, 0x89)):
            guid = bytearray(GUID_A)
            guid[7], guid[8] = byte7, byte8
            self.assertFalse(C.guid_info(make_pkg(bytes(guid)))["rfc4122_v4"], (hex(byte7), hex(byte8)))
        self.assertFalse(C.guid_info(b"short")["present"])
        # the Windows layout: Data3 is bytes 6..7 little-endian, so its high byte (version) is byte 7, not byte 6
        guid = bytearray(GUID_A)
        guid[6], guid[7] = 0x4f, 0x1f
        self.assertFalse(C.guid_info(make_pkg(bytes(guid)))["rfc4122_v4"])


def ev_list(*specs):
    return [dict(seq=i + 1, thread=0, kind=k, **kw) for i, (k, kw) in enumerate(specs)]


PKG_TARGET = "<sandbox>\\System\\XrtCompileProbe.u"


class CreateGuidEvidence(unittest.TestCase):
    def events(self, guid_hex, **kw):
        return ev_list(("create_guid", dict(result="0x00000000", bytes=GUID_B.hex())),
                       ("move_file", dict({"from": "<sandbox>\\System\\Save.tmp", "to": "<sandbox>\\System\\Golem.u", "ok": True})),
                       ("create_guid", dict(dict(result="0x00000000", bytes=guid_hex), **kw)),
                       ("move_file", dict({"from": "<sandbox>\\System\\Save.tmp", "to": PKG_TARGET, "ok": True})))

    def test_match(self):
        ok, detail = C.saved_guid_check(self.events(GUID_A.hex()), PKG_TARGET, make_pkg(GUID_A))
        self.assertTrue(ok, detail)
        ok, _ = C.saved_guid_check(self.events(GUID_A.hex().upper()), PKG_TARGET.lower(), make_pkg(GUID_A))
        self.assertTrue(ok)
        ok, _ = C.saved_guid_check(self.events(GUID_B.hex()), "<sandbox>\\System\\Golem.u", make_golem(GUID_B))
        self.assertTrue(ok)

    def test_mismatch_and_wrong_order(self):
        self.assertFalse(C.saved_guid_check(self.events(GUID_B.hex()), PKG_TARGET, make_pkg(GUID_A))[0])
        swapped = b"".join(GUID_A[i:i + 4][::-1] for i in range(0, 16, 4)).hex()    # dword-printed, not memory order
        self.assertFalse(C.saved_guid_check(self.events(swapped), PKG_TARGET, make_pkg(GUID_A))[0])

    def test_missing_or_malformed_evidence(self):
        ev = self.events(GUID_A.hex())
        self.assertFalse(C.saved_guid_check([e for e in ev if e["seq"] != 3], PKG_TARGET, make_pkg(GUID_A))[0])
        self.assertFalse(C.saved_guid_check(ev[:3], PKG_TARGET, make_pkg(GUID_A))[0])
        bad = self.events(GUID_A.hex())
        bad[3]["ok"] = False
        self.assertFalse(C.saved_guid_check(bad, PKG_TARGET, make_pkg(GUID_A))[0])
        old = self.events(GUID_A.hex())
        old[2].pop("bytes")
        old[2]["guid"] = GUID_A.hex()                       # an older report field: not accepted
        self.assertFalse(C.saved_guid_check(old, PKG_TARGET, make_pkg(GUID_A))[0])
        failed = self.events(GUID_A.hex(), result="0x80004005")
        self.assertFalse(C.saved_guid_check(failed, PKG_TARGET, make_pkg(GUID_A))[0])
        self.assertFalse(C.saved_guid_check(self.events(GUID_A.hex()), PKG_TARGET, None)[0])
        # the create_guid must come after the previous save: one before an earlier MoveFile does not count
        ev = ev_list(("create_guid", dict(result="0x00000000", bytes=GUID_A.hex())),
                     ("move_file", dict({"from": "x", "to": "<sandbox>\\System\\Golem.u", "ok": True})),
                     ("move_file", dict({"from": "x", "to": PKG_TARGET, "ok": True})))
        self.assertFalse(C.saved_guid_check(ev, PKG_TARGET, make_pkg(GUID_A))[0])
        # create_guid after the save does not count either
        ev = ev_list(("move_file", dict({"from": "x", "to": PKG_TARGET, "ok": True})),
                     ("create_guid", dict(result="0x00000000", bytes=GUID_A.hex())))
        self.assertFalse(C.saved_guid_check(ev, PKG_TARGET, make_pkg(GUID_A))[0])


# ------------------------------------------------------------------------------------------------ logic: output lines
class OutputLines(unittest.TestCase):
    def test_xcp_extraction(self):
        out = (b"=====\r\nExecuting Class XrtCompileProbe.XrtCompileProbe\r\nXCP tag=a greeting=b\r\n"
               b"ScriptLog: XCP grades=7:C 14:C \r\nnot XCPx\r\nXCP done\n")
        got, raw = C.xcp_lines(out)
        self.assertEqual(got, ["XCP tag=a greeting=b", "XCP grades=7:C 14:C ", "XCP done"])
        self.assertEqual(raw, ["XCP tag=a greeting=b", "ScriptLog: XCP grades=7:C 14:C ", "XCP done"])
        self.assertEqual(C.xcp_lines(b""), ([], []))
        self.assertEqual(C.xcp_lines(None), ([], []))

    def test_expected_comparison(self):
        exp = ["XCP a", "XCP grades=1:C ", "XCP done"]
        self.assertTrue(C.compare_expected(list(exp), exp)["ok"])
        r = C.compare_expected(["XCP a", "XCP grades=1:C", "XCP done"], exp)       # trailing space is significant
        self.assertFalse(r["ok"])
        self.assertEqual(r["first_difference"], 1)
        self.assertFalse(C.compare_expected(exp[:2], exp)["ok"])
        self.assertFalse(C.compare_expected(exp + ["XCP extra"], exp)["ok"])
        self.assertFalse(C.compare_expected(list(reversed(exp)), exp)["ok"])
        self.assertFalse(C.compare_expected([], exp)["ok"])

    def test_read_expected(self):
        d = mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "expected.txt")
        write(p, b"XCP a\r\nXCP b \nXCP c")
        self.assertEqual(C.read_expected(p), ["XCP a", "XCP b ", "XCP c"])
        write(p, b"XCP a\nXCP b\n")
        self.assertEqual(C.read_expected(p), ["XCP a", "XCP b"])

    def test_fixtures_present_and_well_formed(self):
        for v in ("v1", "v2", "v3"):
            lines = C.read_expected(C.expected_path(v))
            self.assertTrue(lines and all(ln.startswith("XCP ") for ln in lines), v)
            self.assertEqual(lines[-1], "XCP done")
        self.assertEqual(C.read_expected(C.expected_path("v1"))[0], C.SOURCE_CHANGE_LINES["v1"])
        self.assertEqual(C.read_expected(C.expected_path("v2"))[0], C.SOURCE_CHANGE_LINES["v2"])
        self.assertIn("XCP grades=7:C 14:C 21:A ", C.read_expected(C.expected_path("v3")))


class Matrix(unittest.TestCase):
    def test_combinations(self):
        full = C.combo_matrix(["original", "xrt"])
        self.assertEqual([(x["combo"], x["package"], x["engine"]) for x in full],
                         [("A", "original", "original"), ("B", "original", "xrt"), ("C", "xrt", "original"), ("D", "xrt", "xrt")])
        self.assertEqual([x["combo"] for x in C.combo_matrix(["original"])], ["A"])
        self.assertEqual([x["combo"] for x in C.combo_matrix(["xrt"])], ["D"])
        self.assertEqual(C.combo_matrix([]), [])

    def test_configuration_complete(self):
        plan = {"variants": list(C.VARIANTS), "compilers": list(C.COMPILERS), "repeat": 2, "skip_exec": False}
        self.assertTrue(C.configuration_complete(plan))
        for k, v in (("variants", ["v1", "v2", "v3"]), ("compilers", ["original"]), ("repeat", 1), ("skip_exec", True)):
            self.assertFalse(C.configuration_complete(dict(plan, **{k: v})), k)


class WritePolicy(unittest.TestCase):
    BEFORE = {"System/Core.u": "1", "System/Engine.u": "2", "System/Golem.u": "3", "System/XrtCompileProbe.ini": "4",
              "XrtCompileProbe/Classes/XrtCompileProbe.uc": "5"}

    def compile_policy(self, after):
        return C.write_policy(self.BEFORE, after, C.COMPILE_ALLOWED_MODIFIED, C.COMPILE_ALLOWED_CREATED)

    def test_documented_changes_allowed(self):
        after = dict(self.BEFORE, **{"System/Golem.u": "3x", "System/XrtCompileProbe.ini": "4x", "System/UCC.log": "6",
                                     "System/XrtCompileProbe.u": "7"})
        p = self.compile_policy(after)
        self.assertTrue(p["ok"], p)
        self.assertEqual(p["created"], ["System/UCC.log", "System/XrtCompileProbe.u"])
        self.assertTrue(self.compile_policy(dict(self.BEFORE))["ok"])
        self.assertTrue(self.compile_policy(dict(self.BEFORE, **{"system/ucc.log": "6"}))["ok"])     # case-insensitive

    def test_unexpected_writes(self):
        for after, word in ((dict(self.BEFORE, **{"System/Engine.u": "2x"}), "modified System/Engine.u"),
                            (dict(self.BEFORE, **{"XrtCompileProbe/Classes/XrtCompileProbe.uc": "5x"}), "modified"),
                            (dict(self.BEFORE, **{"System/Save.tmp": "8"}), "created System/Save.tmp"),
                            (dict(self.BEFORE, **{"XrtCompileProbe/Inc/XrtCompileProbeClasses.h": "9"}), "created"),
                            ({k: v for k, v in self.BEFORE.items() if k != "System/Golem.u"}, "deleted System/Golem.u")):
            p = self.compile_policy(after)
            self.assertFalse(p["ok"], after)
            self.assertTrue(any(u.startswith(word) for u in p["unexpected"]), p["unexpected"])

    def test_execution_policy(self):
        b = {"System/Core.u": "1", "System/XrtCompileProbe.u": "7"}
        self.assertTrue(C.write_policy(b, dict(b, **{"System/UCC.log": "6"}), C.EXEC_ALLOWED_MODIFIED, C.EXEC_ALLOWED_CREATED)["ok"])
        for after in (dict(b, **{"System/XrtCompileProbe.u": "7x"}), dict(b, **{"System/Golem.u": "3"}),
                      dict(b, **{"System/Unreal2.ini": "x"}) | {"System/Core.u": "1x"}):
            self.assertFalse(C.write_policy(b, after, C.EXEC_ALLOWED_MODIFIED, C.EXEC_ALLOWED_CREATED)["ok"], after)


class Arguments(unittest.TestCase):
    def test_usage_errors_exit_2_and_create_nothing(self):
        before = set(os.listdir(C.COMPILE_ROOT)) if os.path.isdir(C.COMPILE_ROOT) else set()
        for argv in (["--variants", "v9"], ["--variants", "v1,v1"], ["--variants", ""], ["--compilers", "gcc"],
                     ["--compilers", "xrt,xrt"], ["--repeat", "0"], ["--repeat", "1.5"], ["--repeat", "101"],
                     ["--timeout", "nan"], ["--timeout", "0.5"], ["--timeout", "x"], ["--bogus"], ["v1"],
                     ["--reevaluate"], ["--reevaluate", "C:\\nowhere"], ["--reevaluate", R.WS],
                     ["--reevaluate", C.COMPILE_ROOT, "--repeat", "1"], ["--var", "v1"]):
            self.assertEqual(C.main(argv), 2, argv)
        after = set(os.listdir(C.COMPILE_ROOT)) if os.path.isdir(C.COMPILE_ROOT) else set()
        self.assertEqual(before, after, "a rejected invocation must not create a result location")

    def test_parse(self):
        a = C.parse_args(["--variants", "v2,v1", "--compilers", "xrt,original", "--repeat", "3", "--timeout", "60", "--skip-exec"])
        self.assertEqual((a.variants, a.compilers, a.repeat, a.timeout, a.skip_exec),
                         (["v2", "v1"], ["original", "xrt"], 3, 60.0, True))
        a = C.parse_args([])
        self.assertEqual((a.variants, a.compilers, a.repeat, a.timeout), (list(C.VARIANTS), list(C.COMPILERS), 2, 900.0))

    def test_run_invocation_validates_before_creating_anything(self):
        for kw in (dict(repeat=0), dict(timeout=float("inf")), dict(variants=["nope"]), dict(compilers=["x"])):
            args = dict(variants=["v1"], compilers=["original"], repeat=1, timeout=10.0) | kw
            with self.assertRaises(R.UsageError):
                C.run_invocation(**args)


# ------------------------------------------------------------------------------------------------ judging (synthetic raw)
SRC = b"class XrtCompileProbe extends Commandlet;\n"
SOURCES = {"XrtCompileProbe.uc": sha(SRC)}
INI_DERIVED = C.derive_ini(INI)[0]
INI_SAVED = INI_DERIVED + b"[Saved]\r\nX=1\r\n"
GUEST = "E:\\ws\\sandbox_cmp\\xcp\\System\\UCC.exe"
BASE_FILES = {"System/UCC.exe": "a" * 64, "System/Core.dll": "b" * 64, "System/Editor.dll": "c" * 64,
              "System/Engine.u": "d" * 64, "System/Plugins/UnrImp.gpi": "e" * 64}
LOG = "Log: Log file open, 10/22/26 17:34:42\r\nInit: CPU Speed=3425.2 MHz\r\nLog: 5577.5ms Purging garbage\r\nExit: x\r\n"
EXEC_OUT_V1 = (b"=======================================\r\nucc.exe: UnrealOS execution environment\r\n"
               b"Executing Class XrtCompileProbe.XrtCompileProbe\r\nXCP tag=alpha-1 greeting=from-defaults\r\nXCP done\r\n")


def report(run_id, events, modules, exit_code=0, args=C.MAKE_ARGS, marks=()):
    ev = [dict(e, seq=i + 1, thread=e.get("thread", 0)) for i, e in enumerate(events)]
    ev.append({"seq": len(ev) + 1, "thread": 0, "kind": "process_exit_complete", "code": exit_code})
    return {"schema": 2, "run_id": run_id, "exit_code": exit_code, "outcome": "exited",
            "guest_command_line": subprocess.list2cmdline([GUEST] + list(args)), "modules": modules,
            "threads": [{"index": 0, "state": "running"}], "marks": list(marks), "watches": [],
            "watch_unattributed_changes": 0, "events_recorded": len(ev), "events_dropped": 0, "events": ev}


def compile_dir(base, compiler, guid=GUID_A, golem_guid=GUID_B, stdout=OK_OUT, exit_code=0, package=True,
                mutate_meta=None, mutate_report=None, extra_after=None, run_id=None):
    run_id = run_id or f"{compiler}-{guid.hex()[:6]}"
    pkg = make_pkg(guid)
    golem_old, golem_new = make_golem(GUID_A[::-1]), make_golem(golem_guid)
    before = dict(BASE_FILES, **{"System/Golem.u": sha(golem_old), "System/XrtCompileProbe.ini": sha(INI_DERIVED),
                                 "XrtCompileProbe/Classes/XrtCompileProbe.uc": sha(SRC)})
    written = {"System/Golem.u": golem_new, "System/XrtCompileProbe.ini": INI_SAVED, "System/UCC.log": LOG.encode()}
    if package:
        written["System/XrtCompileProbe.u"] = pkg
    after = dict(before, **{k: sha(v) for k, v in written.items()}, **(extra_after or {}))
    meta = {"kind": "compile", "variant": "v1", "compiler": compiler, "run_id": run_id, "trace": False,
            "args": list(C.MAKE_ARGS), "sandbox": "sandbox_cmp/xcp/System", "guest_exe": GUEST,
            "inputs": {"UCC.exe": "a" * 64}, "staged": dict(SOURCES), "probe_files_before_staging": [],
            "probe_files_before_run": ["System/XrtCompileProbe.ini", "XrtCompileProbe/Classes/XrtCompileProbe.uc"],
            "ini": {"edit_packages": ["Core", "XrtCompileProbe"], "sha256": sha(INI_DERIVED)},
            "sandbox_before": before, "sandbox_after": after, "written": {k: sha(v) for k, v in written.items()},
            "process_exit_code": exit_code, "command": [GUEST] + list(C.MAKE_ARGS),
            "command_line": subprocess.list2cmdline([GUEST] + list(C.MAKE_ARGS)), "seconds": 1.0}
    if mutate_meta:
        mutate_meta(meta)
    d = os.path.join(base, f"compile_{compiler}")
    write(os.path.join(d, "meta.json"), json.dumps(meta))
    write(os.path.join(d, "stdout.bin"), stdout)
    write(os.path.join(d, "UCC.log"), LOG.encode())
    write(os.path.join(d, C.INPUT_INI_COPY), INI_DERIVED)
    write(os.path.join(d, "before", "System", "Golem.u"), golem_old)
    for k, v in written.items():
        write(os.path.join(d, "written", k), v)
    if compiler == "xrt":
        write(os.path.join(d, "stderr.txt"), b"")
        write(os.path.join(d, "xrt.log"), f"[t-1] run id: {run_id}\n")
        events = [{"kind": "file_open", "path": "..\\XrtCompileProbe\\Classes\\XrtCompileProbe.uc", "ok": True,
                   "resolved": "<sandbox>\\XrtCompileProbe\\Classes\\XrtCompileProbe.uc"},
                  {"kind": "create_guid", "result": "0x00000000", "bytes": golem_guid.hex()},
                  {"kind": "move_file", "from": "<sandbox>\\System\\Save.tmp", "to": "<sandbox>\\System\\Golem.u", "ok": True}]
        if package:
            events += [{"kind": "create_guid", "result": "0x00000000", "bytes": guid.hex()},
                       {"kind": "move_file", "from": "<sandbox>\\System\\Save.tmp", "to": PKG_TARGET, "ok": True}]
        events.append({"kind": "dll_unloaded", "module": "UnrImp.gpi", "base": "0x036d0000"})
        mods = [{"name": "UCC.exe", "sha256": "a" * 64}, {"name": "Core.dll", "sha256": "b" * 64},
                {"name": "Editor.dll", "sha256": "c" * 64, "functions_executed": 3, "hit_rvas": ["1000", "68290", "85a50"]},
                {"name": "UnrImp.gpi", "sha256": "e" * 64, "unloaded": True}]
        rep = report(run_id, events, mods, exit_code)
        if mutate_report:
            mutate_report(rep)
        write(os.path.join(d, "report.json"), json.dumps(rep))
    return d


def drop_events(pred):
    """report mutation: remove the matching events, keeping the report well formed (renumbered, counts adjusted)"""
    def f(rep):
        rep["events"] = [e for e in rep["events"] if not pred(e)]
        for i, e in enumerate(rep["events"]):
            e["seq"] = i + 1
        rep["events_recorded"] = len(rep["events"]) + rep["events_dropped"]
    return f


class CompileJudging(unittest.TestCase):
    def setUp(self):
        self.tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def judge(self, compiler, variant="v1", **kw):
        d = compile_dir(os.path.join(self.tmp, f"t{len(os.listdir(self.tmp))}"), compiler, **kw)
        return C.judge_compile(d, variant, compiler, 1, SOURCES)[0]

    def failed(self, res):
        return [i["check"] for g in res["groups"] for i in g["checks"] if not i["ok"]]

    def test_valid_runs(self):
        for comp in ("original", "xrt"):
            res = self.judge(comp)
            self.assertEqual(res["classification"], "SUCCESS", comp)
            self.assertTrue(res["ok"], self.failed(res))
            self.assertEqual(res["golem_vs_shipped"]["classification"], "guid_only")
        self.assertEqual(len(self.judge("xrt")["groups"]), 2)

    def test_stale_package_and_unexpected_write(self):
        res = self.judge("original", mutate_meta=lambda m: m["sandbox_before"].update({"System/XrtCompileProbe.u": "f" * 64}))
        self.assertNotEqual(res["classification"], "SUCCESS")
        self.assertFalse(res["ok"])
        res = self.judge("original", extra_after={"System/Engine.u": "0" * 64})
        self.assertEqual(res["classification"], "SUCCESS")
        self.assertIn("modified System/Engine.u", res["write_policy"]["unexpected"])
        self.assertFalse(res["ok"])

    def test_configuration_and_source_checks(self):
        for mut in (lambda m: m["ini"].update(edit_packages=["Core", "Engine", "XrtCompileProbe"]),
                    lambda m: m["staged"].update({"XrtCompileProbe.uc": "0" * 64}),
                    lambda m: m.update(probe_files_before_staging=["System/XrtCompileProbe.u"]),
                    lambda m: m.update(probe_files_before_run=["System/XrtCompileProbe.ini", "Save/XrtCompileProbe.u"])):
            self.assertFalse(self.judge("original", mutate_meta=mut)["ok"])

    def test_negative_variant(self):
        res = self.judge("original", variant="invalid", stdout=ERR_OUT, exit_code=1, package=False)
        self.assertEqual(res["classification"], "FAILURE")
        self.assertTrue(res["ok"], self.failed(res))
        res = self.judge("xrt", variant="invalid", stdout=ERR_OUT, exit_code=1, package=False)
        self.assertTrue(res["ok"], self.failed(res))
        self.assertTrue(res["groups"][1]["info"]["unrimp_unloaded"])
        # the error path does not shut GlmLib down in the original: the unload is recorded, not required
        res = self.judge("xrt", variant="invalid", stdout=ERR_OUT, exit_code=1, package=False,
                         mutate_report=drop_events(lambda e: e["kind"] == "dll_unloaded"))
        self.assertTrue(res["ok"], self.failed(res))
        self.assertFalse(res["groups"][1]["info"]["unrimp_unloaded"])
        res = self.judge("original", variant="invalid")                  # success for the invalid source: FAIL
        self.assertFalse(res["ok"])
        res = self.judge("xrt", variant="invalid", stdout=ERR_OUT, exit_code=1, package=True)   # error + package
        self.assertEqual(res["classification"], "INCONSISTENT")
        self.assertFalse(res["ok"])

    def test_translated_evidence_is_required(self):
        drop = drop_events

        def editor(**kw):
            return lambda rep: rep["modules"][2].update(kw)
        mutations = {
            "source file_open": drop(lambda e: e["kind"] == "file_open"),
            "Editor rva 68290": editor(hit_rvas=["1000", "85a50"]),
            "Editor rva 85a50": editor(hit_rvas=["1000", "68290"]),
            "Editor not executed": editor(functions_executed=0),
            "Editor missing": lambda rep: rep["modules"].pop(2),
            "guid swapped": lambda rep: next(e for e in rep["events"] if e["kind"] == "create_guid" and e["bytes"] == GUID_A.hex())
            .update(bytes=GUID_B.hex()),
            "save missing": drop(lambda e: e["kind"] == "move_file" and e["to"] == PKG_TARGET),
            "UnrImp not unloaded": drop(lambda e: e["kind"] == "dll_unloaded"),
            "exit incomplete": drop(lambda e: e["kind"] == "process_exit_complete"),
            "fatal event": lambda rep: rep["events"].insert(0, {"seq": 0, "thread": 0, "kind": "fatal", "message": "x"}) or
            [e.update(seq=i + 1) for i, e in enumerate(rep["events"])] and rep.update(events_recorded=len(rep["events"])),
            "dropped events": lambda rep: rep.update(events_dropped=2, events_recorded=rep["events_recorded"] + 2),
            "outcome": lambda rep: rep.update(outcome="fatal"),
            "exit code": lambda rep: rep.update(exit_code=3),
            "module not from sandbox": lambda rep: rep["modules"][1].update(sha256="9" * 64),
            "command line": lambda rep: rep.update(guest_command_line=GUEST + " make"),
            "foreign report": lambda rep: rep.update(run_id="someone-else"),
        }
        for name, mut in mutations.items():
            res = self.judge("xrt", mutate_report=mut)
            self.assertFalse(res["ok"], name)

    def test_harness_error_and_missing_meta(self):
        d = compile_dir(os.path.join(self.tmp, "h"), "original", mutate_meta=lambda m: m.update(harness_error="HarnessError: x"))
        res, art = C.judge_compile(d, "v1", "original", 1, SOURCES)
        self.assertFalse(res["ok"])
        self.assertIsNone(art)
        os.makedirs(os.path.join(self.tmp, "empty"))
        res, art = C.judge_compile(os.path.join(self.tmp, "empty"), "v1", "original", 1, SOURCES)
        self.assertFalse(res["ok"])


def exec_dir(vdir, combo, pkg, engine, stdout=EXEC_OUT_V1, n_log=2, mutate_meta=None):
    d = os.path.join(vdir, f"exec_{combo}")
    run_id = f"exec-{combo}"
    before = dict(BASE_FILES, **{"System/XrtCompileProbe.u": sha(pkg)})
    after = dict(before, **{"System/UCC.log": sha(LOG.encode())})
    meta = {"kind": "exec", "combo": combo, "engine": engine, "run_id": run_id, "trace": False, "args": list(C.EXEC_ARGS),
            "guest_exe": GUEST, "source_package_sha256": sha(pkg), "loaded_package_sha256": sha(pkg),
            "probe_files_before_staging": [], "probe_files_before_run": ["System/XrtCompileProbe.u"],
            "sandbox_before": before, "sandbox_after": after, "written": {"System/UCC.log": sha(LOG.encode())},
            "process_exit_code": 0, "command_line": subprocess.list2cmdline([GUEST] + list(C.EXEC_ARGS))}
    if mutate_meta:
        mutate_meta(meta)
    write(os.path.join(d, "meta.json"), json.dumps(meta))
    write(os.path.join(d, "stdout.bin"), stdout)
    write(os.path.join(d, "UCC.log"), LOG.encode())
    write(os.path.join(d, "written", "System", "UCC.log"), LOG.encode())
    if engine == "xrt":
        write(os.path.join(d, "stderr.txt"), b"")
        write(os.path.join(d, "xrt.log"), f"[t-1] run id: {run_id}\n")
        events = [{"kind": "file_open", "path": "..\\System\\XrtCompileProbe.u", "ok": True, "resolved": PKG_TARGET},
                  {"kind": "mark", "name": "UCommandlet::Main", "module": "Core.dll", "va": "0x10100000", "stack_top": "0x00407100"},
                  {"kind": "mark", "name": "UObject::ProcessInternal", "module": "Core.dll", "va": "0x10100010",
                   "stack_top": "0x10100100"}]
        mods = [{"name": "UCC.exe", "sha256": "a" * 64}, {"name": "Core.dll", "sha256": "b" * 64}]
        marks = [{"module": "Core.dll", "name": "UObject::execLog", "va": "0x10100020", "count": n_log}]
        write(os.path.join(d, "report.json"), json.dumps(report(run_id, events, mods, 0, C.EXEC_ARGS, marks)))
    return d


class InvocationJudging(unittest.TestCase):
    """a synthetic v1 invocation (2 compiles per compiler, the four combinations) through judge_invocation"""

    def setUp(self):
        self.root = mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.inv = "20260101-000000-synth000"
        self.invdir = os.path.join(self.root, self.inv)
        self.plan = {"schema": 1, "invocation_id": self.inv, "variants": ["v1"], "compilers": ["original", "xrt"],
                     "repeat": 2, "timeout_s": 60.0, "skip_exec": False, "sources": {"v1": dict(SOURCES)}}
        os.makedirs(self.invdir)
        with open(os.path.join(self.invdir, "plan.json"), "w") as f:
            json.dump(self.plan, f)

    def build(self, guids=None, exec_stdout=None):
        vdir = os.path.join(self.invdir, "v1")
        guids = guids or {"original1": g4(1), "original2": g4(2), "xrt1": GUID_A, "xrt2": GUID_B}
        golems = {"original1": g4(3), "original2": g4(4), "xrt1": g4(5), "xrt2": g4(6)}
        for name, g in guids.items():
            comp, k = name[:-1], name[-1]
            d = compile_dir(os.path.join(self.root, "tmp", name), comp, guid=g, golem_guid=golems[name], run_id=name)
            shutil.move(d, os.path.join(vdir, f"compile_{comp}{k}"))
        pkgs = {"original": make_pkg(guids["original1"]), "xrt": make_pkg(guids["xrt1"])}
        for combo, p, e in C.COMBOS:
            exec_dir(vdir, combo, pkgs[p], e, stdout=(exec_stdout or {}).get(combo, EXEC_OUT_V1))

    def test_valid_invocation(self):
        self.build()
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        v = s["variants"]["v1"]
        failed = [(g["group"], i["check"], i["detail"]) for g in v["groups"] for i in g["checks"] if not i["ok"]]
        self.assertEqual(failed, [])
        self.assertEqual(v["verdict"], "PASS")
        self.assertEqual(s["verdict"], "INCOMPLETE")       # only v1: the milestone needs every variant
        self.assertEqual(len(v["package_pairs"]), 6)
        self.assertTrue(all(p["classification"] == "guid_only" for p in v["package_pairs"]))
        self.assertEqual([r["combo"] for r in v["exec"]["runs"]], ["A", "B", "C", "D"])
        self.assertFalse(v["exec"]["fixture_failure"])
        pub = C.public_summary(s)
        json.dumps(pub)
        self.assertEqual(pub["variants"]["v1"]["exec"]["runs"][3]["xcp_lines"], C.read_expected(C.expected_path("v1")))
        r = C.reevaluate(self.invdir, echo=lambda *_: None)
        self.assertEqual(r["verdict"], "REEVALUATED_INCOMPLETE")
        self.assertTrue(os.path.isfile(os.path.join(self.invdir, "summary.reevaluated.json")))

    def test_fixture_failure_is_loud_and_fails(self):
        bad = EXEC_OUT_V1.replace(b"alpha-1", b"alpha-2")
        self.build(exec_stdout={"A": bad})
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        self.assertEqual(s["verdict"], "FAIL")
        self.assertIn("v1", s["fixture_failures"])
        self.assertIn("FIXTURE", s["fixture_failures"]["v1"])

    def test_translated_engine_output_difference_fails(self):
        self.build(exec_stdout={"D": EXEC_OUT_V1.replace(b"XCP done", b"XCP dune")})
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        self.assertEqual(s["verdict"], "FAIL")
        failed = {i["check"] for g in s["variants"]["v1"]["groups"] for i in g["checks"] if not i["ok"]}
        self.assertIn("A vs D: stdout identical after normalise_stdout", failed)

    def test_reused_guid_fails(self):
        self.build(guids={"original1": g4(1), "original2": g4(1), "xrt1": GUID_A, "xrt2": GUID_B})
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        failed = {i["check"] for g in s["variants"]["v1"]["groups"] for i in g["checks"] if not i["ok"]}
        self.assertEqual(failed, {"every compile created its own package GUID (all distinct)"})

    def test_non_v4_translated_guid_fails(self):
        self.build(guids={"original1": g4(1), "original2": g4(2), "xrt1": bytes(range(16)), "xrt2": GUID_B})
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        failed = {i["check"] for g in s["variants"]["v1"]["groups"] for i in g["checks"] if not i["ok"]}
        self.assertEqual(failed, {"translated packages' GUIDs have the original's RFC 4122 v4 classification"})

    def test_package_difference_outside_guid_fails(self):
        self.build()
        d = os.path.join(self.invdir, "v1", "compile_xrt2")
        p = os.path.join(d, "written", "System", "XrtCompileProbe.u")
        data = bytearray(R.read_bytes(p))
        data[66] ^= 0xFF
        write(p, bytes(data))
        meta = json.loads(R.read_bytes(os.path.join(d, "meta.json")))
        meta["written"]["System/XrtCompileProbe.u"] = meta["sandbox_after"]["System/XrtCompileProbe.u"] = sha(bytes(data))
        write(os.path.join(d, "meta.json"), json.dumps(meta))
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        v = s["variants"]["v1"]
        self.assertEqual(v["verdict"], "FAIL")
        bad = [p for p in v["package_pairs"] if p["b"] == "xrt2"]
        self.assertTrue(bad and all(p["classification"] == "other" and p["unresolved_ranges"] == [[66, 67]] for p in bad))

    def test_missing_execution_fails(self):
        self.build()
        shutil.rmtree(os.path.join(self.invdir, "v1", "exec_C"))
        s = C.judge_invocation(self.invdir, self.plan, "fresh")
        self.assertEqual(s["variants"]["v1"]["verdict"], "FAIL")

    def build_invalid(self, xrt_stdout=ERR_OUT, xrt_exit=1, xrt_package=False):
        plan = dict(self.plan, variants=["invalid"], sources={"invalid": dict(SOURCES)})
        vdir = os.path.join(self.invdir, "invalid")
        for n, (comp, k) in enumerate((("original", 1), ("original", 2), ("xrt", 1), ("xrt", 2))):
            x = comp == "xrt"
            d = compile_dir(os.path.join(self.root, "tmp", f"{comp}{k}"), comp, guid=g4(10 + n), golem_guid=g4(20 + n),
                            stdout=xrt_stdout if x else ERR_OUT, exit_code=xrt_exit if x else 1,
                            package=xrt_package if x else False, run_id=f"{comp}{k}")
            shutil.move(d, os.path.join(vdir, f"compile_{comp}{k}"))
        return C.judge_invocation(self.invdir, plan, "fresh")

    def test_invalid_variant_equal_behaviour(self):
        s = self.build_invalid()
        v = s["variants"]["invalid"]
        failed = [(g["group"], i["check"]) for g in v["groups"] for i in g["checks"] if not i["ok"]]
        self.assertEqual(failed, [])
        self.assertEqual(v["verdict"], "PASS")
        self.assertIsNone(v["exec"])
        self.assertEqual(len(v["golem_pairs"]), 6)

    def test_invalid_variant_differences_fail(self):
        for kw, check in ((dict(xrt_exit=0), "original1 vs xrt1: same exit code"),
                          (dict(xrt_stdout=ERR_OUT.replace(b"after '$'", b"in '$'")),
                           "original1 vs xrt1: stdout identical after normalise_stdout"),
                          (dict(xrt_package=True), "compile classified FAILURE")):
            shutil.rmtree(self.invdir)
            os.makedirs(self.invdir)
            shutil.rmtree(os.path.join(self.root, "tmp"), True)
            s = self.build_invalid(**kw)
            v = s["variants"]["invalid"]
            self.assertEqual(v["verdict"], "FAIL", kw)
            failed = {i["check"] for g in v["groups"] for i in g["checks"] if not i["ok"]}
            self.assertIn(check, failed, kw)


# ------------------------------------------------------------------------------------------------ real data
def newest_real_invocation():
    if not os.path.isdir(C.COMPILE_ROOT):
        return None
    for name in sorted(os.listdir(C.COMPILE_ROOT), reverse=True):
        d = os.path.join(C.COMPILE_ROOT, name)
        if os.path.isfile(os.path.join(d, "summary.json")) and os.path.isfile(os.path.join(d, "plan.json")):
            return d
    return None


class RealArtifacts(unittest.TestCase):
    """the newest preserved invocation re-judged in memory (nothing written): the current code must reach the same
    verdict as the invocation did, and a tampered copy must fail"""

    def setUp(self):
        self.inv = newest_real_invocation()
        if self.inv is None:
            self.skipTest("no preserved compile invocation under experiments/xrt/results/raw/compile")
        self.plan = json.loads(R.read_bytes(os.path.join(self.inv, "plan.json")))
        self.prior = json.loads(R.read_bytes(os.path.join(self.inv, "summary.json")))

    def test_rejudged_verdict_matches(self):
        if self.prior.get("candidate_unchanged_during_invocation") is False or self.prior.get("harness_errors"):
            self.skipTest("the newest invocation was failed for a reason outside its raw artifacts")
        s = C.judge_invocation(self.inv, self.plan, "fresh")
        self.assertEqual(s["verdict"], self.prior["verdict"])
        for v, o in s["variants"].items():
            self.assertEqual(o["verdict"], self.prior["variants"][v]["verdict"], v)

    def test_tampered_package_fails(self):
        v = next((v for v in self.plan["variants"] if v not in C.NEGATIVE), None)
        if v is None:
            self.skipTest("no compiling variant in the newest invocation")
        tmp = mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        inv = os.path.join(tmp, self.plan["invocation_id"])
        shutil.copytree(self.inv, inv)
        run = os.path.join(inv, v, f"compile_{self.plan['compilers'][0]}1")
        p = os.path.join(run, "written", "System", "XrtCompileProbe.u")
        data = bytearray(R.read_bytes(p))
        data[60] ^= 1
        write(p, bytes(data))
        s = C.judge_invocation(inv, self.plan, "fresh")
        self.assertEqual(s["variants"][v]["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
