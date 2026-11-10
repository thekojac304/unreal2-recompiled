"""Windows jobs, file pins, and bounded debugger event loop.

Only debug registers/RF are changed. Target code, data and results are never patched.
"""
import ctypes as C
from ctypes import wintypes as T
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import threading
import time

from .core import IntegrityFailure, independent, sha

K = C.WinDLL("kernel32", use_last_error=True)


def api(dll, name, args, result=T.BOOL):
    f = getattr(dll, name)
    f.argtypes, f.restype = args, result
    return f


def checked(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


Close = api(K, "CloseHandle", [T.HANDLE])
Read = api(K, "ReadProcessMemory", [T.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)])
GetCtx = api(K, "GetThreadContext", [T.HANDLE, C.c_void_p])
SetCtx = api(K, "SetThreadContext", [T.HANDLE, C.c_void_p])
Continue = api(K, "ContinueDebugEvent", [T.DWORD, T.DWORD, T.DWORD])


class ExceptionRecord(C.Structure):
    _fields_ = [("code", T.DWORD), ("flags", T.DWORD), ("record", C.c_void_p), ("address", C.c_void_p),
                ("count", T.DWORD), ("info", C.c_ulonglong * 15)]


class ExceptionInfo(C.Structure):
    _fields_ = [("record", ExceptionRecord), ("first", T.DWORD)]


class CreateProcessInfo(C.Structure):
    _fields_ = [("file", T.HANDLE), ("process", T.HANDLE), ("thread", T.HANDLE), ("base", C.c_void_p),
                ("offset", T.DWORD), ("size", T.DWORD), ("teb", C.c_void_p), ("start", C.c_void_p),
                ("name", C.c_void_p), ("unicode", T.WORD)]


class CreateThreadInfo(C.Structure):
    _fields_ = [("thread", T.HANDLE), ("teb", C.c_void_p), ("start", C.c_void_p)]


class LoadInfo(C.Structure):
    _fields_ = [("file", T.HANDLE), ("base", C.c_void_p), ("offset", T.DWORD), ("size", T.DWORD),
                ("name", C.c_void_p), ("unicode", T.WORD)]


class DebugString(C.Structure):
    _fields_ = [("data", C.c_void_p), ("unicode", T.WORD), ("length", T.WORD)]


class Info(C.Union):
    _fields_ = [("exception", ExceptionInfo), ("process", CreateProcessInfo), ("thread", CreateThreadInfo),
                ("load", LoadInfo), ("exit", T.DWORD), ("string", DebugString), ("raw", C.c_byte * 160)]


class Event(C.Structure):
    _fields_ = [("code", T.DWORD), ("pid", T.DWORD), ("tid", T.DWORD), ("u", Info)]


Wait = api(K, "WaitForDebugEvent", [C.POINTER(Event), T.DWORD])
REGS = dict(zip("rax rcx rdx rbx rsp rbp rsi rdi r8 r9 r10 r11 r12 r13 r14 r15 rip".split(), range(120, 249, 8)))


class Context:
    def __init__(self, thread):
        self.buf = C.create_string_buffer(1248)
        self.ptr = (C.addressof(self.buf) + 15) & ~15
        self.thread = thread
        C.c_uint32.from_address(self.ptr + 48).value = 0x10001b
        checked(GetCtx(thread, self.ptr))

    def get(self, name):
        return C.c_uint64.from_address(self.ptr + REGS[name]).value

    def snapshot(self):
        return dict(registers={k: self.get(k) for k in REGS}, eflags=C.c_uint32.from_address(self.ptr + 68).value,
                    mxcsr=C.c_uint32.from_address(self.ptr + 52).value, fxsave=C.string_at(self.ptr + 256, 512).hex())

    def arm(self, addresses, resume=False):
        if len(addresses) > 4:
            raise IntegrityFailure("hardware breakpoint slot exhaustion")
        for i in range(4):
            C.c_uint64.from_address(self.ptr + 72 + 8 * i).value = addresses[i] if i < len(addresses) else 0
        C.c_uint64.from_address(self.ptr + 104).value = 0
        C.c_uint64.from_address(self.ptr + 112).value = sum(1 << (2 * i) for i in range(len(addresses)))
        C.c_uint32.from_address(self.ptr + 48).value = 0x100010 | (1 if resume else 0)
        if resume:
            C.c_uint32.from_address(self.ptr + 68).value |= 0x10000
        checked(SetCtx(self.thread, self.ptr))
        actual = Context(self.thread)
        dr = [C.c_uint64.from_address(actual.ptr + 72 + 8 * i).value for i in range(4)]
        dr7 = C.c_uint64.from_address(actual.ptr + 112).value
        if dr != addresses + [0] * (4 - len(addresses)) or dr7 & 0xffff00ff != sum(1 << (2 * i) for i in range(len(addresses))):
            raise IntegrityFailure("breakpoint readback mismatch")


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong), ("flags", T.DWORD),
                ("min_ws", C.c_size_t), ("max_ws", C.c_size_t), ("active_limit", T.DWORD),
                ("affinity", C.c_size_t), ("priority", T.DWORD), ("scheduling", T.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_ulonglong * 6), ("process_memory", C.c_size_t),
                ("job_memory", C.c_size_t), ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [("times", C.c_longlong * 4), ("faults", T.DWORD), ("total", T.DWORD),
                ("active", T.DWORD), ("terminated", T.DWORD)]


class Job:
    def __init__(self):
        self.handle = checked(api(K, "CreateJobObjectW", [C.c_void_p, T.LPCWSTR], T.HANDLE)(None, None))
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000 | 0x400  # kill on close; die on unhandled exception
        try:
            checked(api(K, "SetInformationJobObject", [T.HANDLE, C.c_int, C.c_void_p, T.DWORD])(
                self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except BaseException:
            self.close()
            raise

    def assign(self, process):
        checked(api(K, "AssignProcessToJobObject", [T.HANDLE, T.HANDLE])(self.handle, process))

    def kill(self):
        checked(api(K, "TerminateJobObject", [T.HANDLE, T.UINT])(self.handle, 0x1362))

    def active(self):
        a = Accounting()
        checked(api(K, "QueryInformationJobObject", [T.HANDLE, C.c_int, C.c_void_p, T.DWORD, C.c_void_p])(
            self.handle, 1, C.byref(a), C.sizeof(a), None))
        return a.active

    def close(self):
        if self.handle:
            checked(Close(self.handle))
            self.handle = None


class FilePins(ExitStack):
    def pin(self, path, expected):
        independent(path)
        handle = api(K, "CreateFileW", [T.LPCWSTR, T.DWORD, T.DWORD, C.c_void_p, T.DWORD, T.DWORD, T.HANDLE], T.HANDLE)(
            str(path), 0x80000000, 1, None, 3, 0x80, None)  # read sharing only
        if handle == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        self.callback(Close, handle)
        if sha(path) != expected:
            raise IntegrityFailure("pinned file hash mismatch: " + str(path))


class Exclusive:
    def __init__(self, path):
        self.path = independent(path)

    def __enter__(self):
        self.h = api(K, "CreateFileW", [T.LPCWSTR, T.DWORD, T.DWORD, C.c_void_p, T.DWORD, T.DWORD, T.HANDLE], T.HANDLE)(
            str(self.path), 0xc0000000, 0, None, 4, 0x80, None)
        if self.h == C.c_void_p(-1).value:
            raise IntegrityFailure("another supervisor owns the queue (or lock inaccessible)")
        return self

    def __exit__(self, *args):
        checked(Close(self.h))


class BoundedLoop:
    """Mixin for the retained observer. DEBUG_ONLY_THIS_PROCESS + Job tree."""
    def module_record(self, handle):
        if not handle:
            raise IntegrityFailure("loaded image has no verifiable file handle")
        buffer=C.create_unicode_buffer(32768)
        length=api(K,"GetFinalPathNameByHandleW",[T.HANDLE,T.LPWSTR,T.DWORD,T.DWORD],T.DWORD)(handle,buffer,len(buffer),0)
        if not 0<length<len(buffer):
            raise IntegrityFailure("cannot identify loaded module")
        path=Path(buffer.value.removeprefix("\\\\?\\"))
        system=Path(os.environ["SystemRoot"]).resolve()
        system_module=any(path.resolve().is_relative_to(system/name) for name in ('System32','SysWOW64','WinSxS'))
        allowed={Path(p).resolve() for p in getattr(self,"allowed_modules",[self.process_obj.args[0]])}
        if not system_module and path.resolve() not in allowed:
            raise IntegrityFailure("loaded image outside approved dependency profile: "+str(path))
        self.log("module_identity",path=str(path),sha256=sha(path),system_dependency=system_module)

    def run(self, cmd, *, cwd, env, stdout, stderr, timeout, stop=lambda: False):
        if self.created:
            raise IntegrityFailure("one launch per observer")
        self.created = 1
        self.stop_requested = self.terminated_while_stopped = False
        self.cleanup = dict(passed=False)
        job = Job()
        finished = threading.Event()
        expired = threading.Event()
        pending = None
        event_process = None
        initial = False
        p = None
        terminate = api(K, "TerminateProcess", [T.HANDLE, T.UINT])
        start = time.monotonic()
        # Independent watchdog does not rely on debug callbacks returning promptly.
        def watchdog():
            while not finished.wait(.05):
                if time.monotonic() - start >= timeout or stop():
                    expired.set()
                    try:
                        job.kill()
                    except OSError:
                        pass
                    return
        guard = threading.Thread(target=watchdog, daemon=True, name="attempt-watchdog")
        try:
            p = self.process_obj = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                                   creationflags=2, close_fds=True)
            self.process = int(p._handle)
            guard.start()
            self.log("launch", command=cmd, cwd=str(cwd), pid=p.pid, timeout_seconds=timeout)
            while True:
                if expired.is_set():
                    raise TimeoutError("watchdog or local stop")
                ev = Event()
                C.set_last_error(0)
                if not Wait(C.byref(ev), 100):
                    if C.get_last_error() != 121:
                        raise C.WinError(C.get_last_error())
                    continue
                pending = (ev.pid, ev.tid)
                self.log("debug_event", code=ev.code, pid=ev.pid, tid=ev.tid,
                         raw=C.string_at(C.byref(ev), C.sizeof(ev)).hex())
                status, done = 0x10002, False
                if ev.code == 3:
                    event_process = ev.u.process.process
                    # Process is stopped at CREATE_PROCESS_DEBUG_EVENT before loader/user code.
                    job.assign(self.process)
                    self.log("job_assigned_before_continue", pid=p.pid)
                    self.base = ev.u.process.base
                    self.threads[ev.tid] = (ev.u.process.thread, ev.u.process.teb)
                    try:self.module_record(ev.u.process.file)
                    finally:
                        if ev.u.process.file:Close(ev.u.process.file)
                    self.on_create(ev)
                    self.update(Context(ev.u.process.thread))
                    self.log("process_created", pid=p.pid, tid=ev.tid, base=self.base)
                elif ev.code == 2:
                    self.threads[ev.tid] = (ev.u.thread.thread, ev.u.thread.teb)
                    self.update(Context(ev.u.thread.thread))
                elif ev.code == 4:
                    item = self.threads.pop(ev.tid, None)
                    if item:
                        Close(item[0])
                elif ev.code == 6:
                    self.log("module_loaded", base=ev.u.load.base)
                    try:self.module_record(ev.u.load.file)
                    finally:
                        if ev.u.load.file:Close(ev.u.load.file)
                elif ev.code == 8:
                    info = ev.u.string
                    length = int(info.length) * (2 if info.unicode else 1)
                    self.log("output_debug_string", unicode=bool(info.unicode), bytes=self.mem(info.data, length).hex() if length else "")
                elif ev.code == 1:
                    ex = ev.u.exception
                    self.log("exception", code=ex.record.code, address=ex.record.address, first_chance=ex.first)
                    if ex.record.code == 0x80000003:
                        if not initial:
                            initial = True
                        else:
                            self.on_debugbreak(ev)
                    elif ex.record.code == 0x80000004:
                        ctx = Context(self.threads[ev.tid][0])
                        tag = self.breakpoints.get(ctx.get("rip"))
                        if not tag:
                            raise IntegrityFailure("unexpected hardware breakpoint")
                        self.hit(tag, ctx, ev.tid)
                        if not self.stop_requested:
                            self.update(ctx, True)
                    else:
                        # Keep first chance C++ exceptions available to guest handlers.
                        if not ex.first:
                            raise IntegrityFailure("unhandled host exception")
                        status = 0x80010001
                elif ev.code == 5:
                    self.exit = ev.u.exit
                    self.log("process_exited", pid=ev.pid, exit_code=self.exit)
                    done = True
                if self.stop_requested:
                    checked(terminate(self.process, 0x1361))
                    self.terminated_while_stopped = True
                    self.log("terminated_before_continue", pid=ev.pid, tid=ev.tid)
                    self.stop_requested = False
                checked(Continue(ev.pid, ev.tid, status))
                pending = None
                if done:
                    break
            p.wait(timeout=5)
            if expired.is_set():
                raise TimeoutError("watchdog or local stop")
            return subprocess.CompletedProcess(cmd, self.exit)
        except BaseException:
            if p and p.poll() is None:
                # Terminate root even if job assignment failed. Never continue a live fault.
                killed = bool(terminate(self.process, 0x1362))
                # The independent watchdog may already have terminated the Job.
                # Windows can deny a second TerminateProcess until EXIT events
                # are drained; a successful Job termination still guarantees
                # that releasing a pending debug event cannot resume live code.
                if not killed:
                    job.kill()
                if pending:
                    self.log("terminated_before_continue", pid=pending[0], tid=pending[1], observation_failed=True)
            if pending:
                Continue(*pending, 0x10002)
                pending = None
            end = time.monotonic() + 5
            while p and p.poll() is None and time.monotonic() < end:
                ev = Event()
                if Wait(C.byref(ev), 50):
                    self.log("cleanup_debug_event", code=ev.code, pid=ev.pid, tid=ev.tid)
                    if ev.code == 6 and ev.u.load.file:
                        Close(ev.u.load.file)
                    Continue(ev.pid, ev.tid, 0x10002)
            if p:
                p.wait(timeout=5)
            raise
        finally:
            finished.set()
            if guard.is_alive():
                guard.join(timeout=2)
            job.kill()
            end = time.monotonic() + 5
            while job.active() and time.monotonic() < end:
                time.sleep(.02)
            active = job.active()
            job.close()
            for handle, _ in self.threads.values():
                Close(handle)
            self.threads = {}
            if event_process:
                Close(event_process)
            self.cleanup = dict(passed=active == 0 and (p is None or p.poll() is not None),
                                remaining_job_processes=active, root_exit=p.returncode if p else None,
                                watchdog=expired.is_set(), seconds=time.monotonic() - start,
                                kill_on_close=True, normal_guest_cleanup_claimed=False)
            self.log("process_tree_cleanup", **self.cleanup)
            if not self.cleanup["passed"]:
                raise IntegrityFailure("process tree cleanup incomplete")

    def on_debugbreak(self, ev):
        raise IntegrityFailure("unexpected software breakpoint")

