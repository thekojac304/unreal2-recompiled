"""Fixed non-game profile; never executes a queue-supplied command."""
import ctypes as C
import json
import os
from pathlib import Path
import struct
from . import core
from .windows import BoundedLoop, Read, Context


class Probe(BoundedLoop):
    def __init__(self, out, sandbox, case):
        self.out, self.sandbox, self.case = out, sandbox, case
        self.created, self.threads, self.rows, self.breakpoints = 0, {}, [], {}

    def log(self, kind, **values):
        row = dict(kind=kind, **values)
        with (self.out / "debug-events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
        self.rows.append(row)

    def mem(self, pointer, count):
        data, got = C.create_string_buffer(count), C.c_size_t()
        if not Read(self.process, pointer, data, count, C.byref(got)) or got.value != count:
            raise core.IntegrityFailure("fixture memory read failed")
        return data.raw

    def on_create(self, ev):
        self.breakpoints = {}

    def update(self, ctx, resume=False):
        ctx.arm(list(self.breakpoints), resume)
        self.log("breakpoints_readback", addresses=list(self.breakpoints), verified=True)

    def on_debugbreak(self, ev):
        self.target = core.read(self.sandbox / "ready.json")
        core.require(self.target["pid"] == self.process_obj.pid, "fixture PID")
        self.breakpoints = {self.target["target"]: "fixture-stop"}
        for thread, _ in self.threads.values():
            self.update(Context(thread))

    def hit(self, tag, ctx, tid):
        core.require(tag == "fixture-stop" and ctx.get("rip") == self.target["target"], "fixture stop address")
        core.require(self.mem(self.target["buffer"], 32) == b"\x55" * 32, "instruction executed")
        self.log("stopped_before_instruction", unmodified_buffer=True, thread=tid)
        if self.case == "fatal-stop":
            raise RuntimeError("injected fatal observation failure")
        self.stop_requested = True


def run(manifest, request, out, sandbox, stop):
    probe = Probe(out, sandbox, manifest["fixture_case"])
    result = None
    try:
        with (out / "stdout.bin").open("xb") as stdout, (out / "stderr.bin").open("xb") as stderr:
            result = probe.run([str(core.ROOT / manifest["executable"]), manifest["fixture_case"]], cwd=sandbox,
                               env=environment(sandbox), stdout=stdout, stderr=stderr,
                               timeout=request["timeout_seconds"], stop=stop)
        expected = request["expected_stop"]["kind"]
        passed = ((expected == "fixture-complete" and result.returncode == 0) or
                  (expected == "fixture-breakpoint" and probe.terminated_while_stopped))
        passed = passed and not (sandbox / "FORBIDDEN.txt").exists()
        return dict(classification="fixture-complete" if passed else "unclassified-discrepancy", passed=passed,
                    cleanup=probe.cleanup, gameplay_verified=False)
    finally:
        core.atomic(out / "cleanup.json", probe.cleanup)
        core.atomic(out / "assurance.json", dict(cleanup_verified=probe.cleanup.get('passed') is True,
                    integrity_verified=not (sandbox/'FORBIDDEN.txt').exists(),
                    fixture_defect=result is not None and result.returncode != 0))


def environment(sandbox):
    # No inherited XRT/DXVK/Python injection variables or queue-controlled environment.
    # Use Windows' known common-app-data folder, not a request/inherited override.
    folder = C.create_unicode_buffer(260)
    get_folder = C.WinDLL('shell32').SHGetFolderPathW
    get_folder.argtypes = [C.c_void_p,C.c_int,C.c_void_p,C.c_uint,C.c_wchar_p]
    get_folder.restype = C.c_long
    if get_folder(None,0x23,None,0,folder)!=0 or not folder.value:
        raise core.IntegrityFailure('cannot resolve trusted ProgramData for isolated helper')
    programdata = str(core.independent(folder.value))
    return {**{k: v for k, v in os.environ.items() if k.upper() in
                ("SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "USERPROFILE", "USERNAME", "LOCALAPPDATA", "APPDATA")},
            "ProgramData": programdata,
            "PATH": str(Path(os.environ["SystemRoot"]) / "System32"), "TEMP": str(sandbox), "TMP": str(sandbox)}
