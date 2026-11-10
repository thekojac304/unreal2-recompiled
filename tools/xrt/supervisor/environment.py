"""Read-only physical owner desktop gate, retaining the established API collector."""
import ctypes as C
from ctypes import wintypes as T
import importlib.util
from . import core


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ordinary_user():
    k, a = C.WinDLL("kernel32", use_last_error=True), C.WinDLL("advapi32", use_last_error=True)
    from .windows import api, checked, Close
    token = T.HANDLE()
    checked(api(a, "OpenProcessToken", [T.HANDLE, T.DWORD, C.POINTER(T.HANDLE)])(
        api(k, "GetCurrentProcess", [], T.HANDLE)(), 8, C.byref(token)))
    try:
        elevated, size = T.DWORD(), T.DWORD()
        checked(api(a, "GetTokenInformation", [T.HANDLE, C.c_int, C.c_void_p, T.DWORD, C.POINTER(T.DWORD)])(
            token, 20, C.byref(elevated), C.sizeof(elevated), C.byref(size)))
        core.require(elevated.value == 0, "elevated supervisor refused")
    finally:
        Close(token)


def gate(data, baseline, legacy):
    # Retains physical DisplayPort/NVIDIA/driver/input/cursor/session assertions.
    fingerprint = legacy.environment_gate(data)
    if baseline is not None and fingerprint != baseline:
        raise core.IntegrityFailure("owner session/display/input environment changed")
    return fingerprint


class Desktop:
    def __init__(self):
        self.owner = load("desktop_supervisor_owner_environment", core.ROOT / "out/recovery/session-aware-136-20261026-01/owner.py")
        self.expected = core.read_large(core.ROOT / "out/recovery/viewport-getobject-20261028-01/owner-evidence-audit.json")["baseline"]

    def check(self, out, tag):
        ordinary_user()
        observation = self.owner.observe()
        core.atomic(out / (tag + "-environment.json"), observation)
        return gate(observation, self.expected, self.owner)
