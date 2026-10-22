"""Registered comparison cases for tools/xrt/run_xrt.py.

A case fixes the commandlet arguments, the result the case must produce (independently of the comparison with the
original) and the milestone-evidence profile the translated run must satisfy (run_xrt.PROFILES). Case-specific
script natives are those the ORIGINAL executed for the case (uctrace function-entry traces, experiments/xrt/traces/
and fresh --trace runs); each must be a mark in tools/xrt/marks.json.

expect.negative marks an explicit negative test: only such a case may expect a nonzero exit code. A normal case
expects exit code 0, so equal nonzero exit codes of the original and the translated run never make it pass.
"""
import re
from dataclasses import dataclass, field

CASE_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


@dataclass(frozen=True)
class Expect:
    exit_code: int = 0
    stdout_contains: tuple = ()
    stdout_excludes: tuple = ()
    negative: bool = False

    def __post_init__(self):
        if self.exit_code != 0 and not self.negative:
            raise ValueError("a nonzero expected exit code requires negative=True")


@dataclass(frozen=True)
class Case:
    name: str
    args: tuple
    expect: Expect
    profile: str
    natives: tuple = ()          # mark names (Core.dll) of script natives the case must execute
    note: str = ""
    cxx_exceptions: bool = False  # the path throws C++ exceptions: exception evidence required; --trace compares
                                  # the throw/catch/unwind/resume sequence with the original's
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if not CASE_ID.match(self.name):
            raise ValueError(f"bad case id {self.name!r}")


HELLO_BANNER = ("ucc.exe: UnrealOS execution environment",)


def _hello(name, args, params_line, note="", cxx_exceptions=False):
    contains = HELLO_BANNER + ("Executing Class Core.HelloWorldCommandlet", "Hello, world!")
    natives = ("UObject::execLog", "UObject::execNotEqual_StringString")
    if params_line:
        contains += (params_line,)
        natives += ("UObject::execConcat_StringString",)
    return Case(name, tuple(args), Expect(0, contains, ("not found",)), "core_commandlet", natives, note,
                cxx_exceptions=cxx_exceptions)


CASES = {c.name: c for c in [
    _hello("hellofull", ["Core.HelloWorldCommandlet", "a", "b", "c"], "Command line parameters=a b c"),
    _hello("hello_noargs", ["Core.HelloWorldCommandlet"], None),
    _hello("hellonew", ["Core.HelloWorldCommandlet", "x=1", "-flag", "two words", "back\\slash", "ünï"],
           "Command line parameters=", "an argument string not used during development (quotes, backslash, Latin-1)"),
    _hello("hellofull_nosse", ["Core.HelloWorldCommandlet", "a", "b", "c", "-NOMMX", "-NOSSE"],
           "Command line parameters=a b c",
           "the original takes the scalar CPU paths the translated runtime's CPU policy selects: UCC.log must match "
           "including the 'CPU Features' line"),
    Case("simple", ("Core.SimpleCommandlet",),
         Expect(0, HELLO_BANNER + ("Executing Class Core.SimpleCommandlet",), ("not found",)), "core_commandlet",
         ("UObject::execLog", "UObject::execIntToString", "UObject::execFloatToString", "UObject::execLeft",
          "UObject::execMid", "UObject::execInStr")),
    Case("arraytest", ("Core.ArrayTest",),
         Expect(0, HELLO_BANNER + ("Executing Class Core.ArrayTest",), ("not found",)), "core_commandlet",
         ("UObject::execAssert", "UObject::execDynArrayLength", "UObject::execDynArrayInsert",
          "UObject::execDynArrayRemove", "UObject::execNew", "UObject::execEqualEqual_VectorVector")),
    # short-name lookup: UCC tries to load the class, which throws C++ exceptions inside Core, then finds the
    # commandlet through its .int alias (ShortName) - the original throws 14 C++ exceptions on this path
    _hello("hello", ["HelloWorld", "a", "b", "c"], "Command line parameters=a b c",
           "short alias: the lookup path throws and catches C++ exceptions in the original", cxx_exceptions=True),
    # unknown class: same exception path, no alias found; UCC prints an error and still exits with 0
    Case("badclass", ("NoSuchCommandletXYZ",),
         Expect(0, HELLO_BANNER + ("Commandlet NoSuchCommandletXYZ not found",), ("Executing Class",)), "core_error",
         note="lookup failure through the C++ exception path; the original reports it and exits with code 0",
         cxx_exceptions=True),
    # VMProbe.u (compiled in phase 0 by the original compiler, copied into every sandbox): 54 script tests over the
    # VM. Loading it makes Core load Engine.dll, whose static import GlmLib.dll is mapped first (rebased) and
    # initialised before it, as in the original; both run translated.
    Case("vmprobe", ("VMProbe.VMProbe",),
         Expect(0, HELLO_BANNER + ("Executing Class VMProbe.VMProbe", "T35=7 2187", "T54=done"), ("not found",)),
         "engine_commandlet",
         ("UObject::execLog", "UObject::execConcat_StringString", "UObject::execIntToString",
          "UObject::execFloatToString", "UObject::execLeft", "UObject::execMid", "UObject::execInStr",
          "UObject::execDynArrayLength", "UObject::execDynArrayInsert", "UObject::execDynArrayRemove",
          "UObject::execEqualEqual_VectorVector"),
         "Engine.dll and GlmLib.dll execute translated; the original runs Engine/GlmLib code (1429 and 981 functions)"),
]}

CORE_CASES = ("hellofull", "hello_noargs", "hellonew", "hellofull_nosse", "simple", "arraytest")
