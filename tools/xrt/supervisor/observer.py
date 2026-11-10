"""Construct the retained observer with the complete bounded-loop interface.

Construction only: this module never creates a debuggee or submits a request.
Both production and non-game qualification use this integration point.
"""
from types import MethodType

from . import core
from .windows import BoundedLoop


def construct(legacy, out, plan, check_environment, allowed_modules):
    capture = legacy.observer(out, plan, check_environment)
    # The retained class predates BoundedLoop. Binding run alone does not add
    # the other mixin methods that it calls (notably module_record).
    for name, method in vars(BoundedLoop).items():
        if not name.startswith("_") and callable(method):
            setattr(capture, name, MethodType(method, capture))
    capture.allowed_modules = list(allowed_modules)
    core.require(bool(capture.allowed_modules), "observer module profile absent")
    for name in ("on_create", "update", "hit", "mem", "log", "cstring", "u64",
                 "sym", "cpu_state", "words", "snapshot_events"):
        core.require(callable(getattr(capture, name, None)), "observer method absent: " + name)
    core.require(capture.created == 0 and capture.base == 0 and capture.cpu is None,
                 "observer must be unexecuted")
    for name, kind in (("threads", dict), ("breakpoints", dict), ("rows", list), ("syms", dict)):
        value = getattr(capture, name, None)
        core.require(isinstance(value, kind) and (name == "syms" or not value),
                     "observer initial state invalid: " + name)
    core.require(capture._fatal_evidence_installed, "instance fatal evidence absent")
    fatal_hit = capture.hit

    def hit(self, tag, ctx, tid):
        if tag == "fatal_entry" and ctx.get("rdx") & 0xffffffff == 75:
            self.log("import_boundary", symbol=self.cstring(ctx.get("r9")),
                     dependency=self.cstring(self.u64(ctx.get("rsp") + 40)))
        return fatal_hit(tag, ctx, tid)

    capture.hit = MethodType(hit, capture)
    return capture
