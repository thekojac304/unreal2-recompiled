"""Regression tests for the X1 lifter (tools/xrt/xlift.py) and function discovery.

Needs the sandbox copy of Core.dll (sandbox_ref/hellofull/System); run with
  python -I -m unittest discover -s tools/xrt/tests -v
"""
import os
import sys
import unittest

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from discover import Module  # noqa: E402
from xlift import Lifter, Unsupported  # noqa: E402

WS = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CORE = os.path.join(WS, "sandbox_ref", "hellofull", "System", "Core.dll")

_mod = None


def core():
    global _mod
    if _mod is None:
        if not os.path.exists(CORE):
            raise unittest.SkipTest("sandbox copy of Core.dll not present")
        _mod = Module(CORE).run()
    return _mod


def lift_bytes(code, va=0x10000000):
    """Lift one instruction given as bytes (non-control-flow) and return the C statements."""
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    ins = next(md.disasm(code, va))
    return Lifter(core()).lift_insn(ins, None)


class DiscoveryRegression(unittest.TestCase):
    def test_switch_index_tables_are_data(self):
        """Tracer finding: the byte index table of a two-level switch must not become code."""
        m = core()
        self.assertTrue(m.data_in_text, "expected byte-index tables next to jump tables in Core.dll")
        for a, b in m.table_data:
            for e in m.functions:
                self.assertFalse(a <= e < b, f"function entry {e:#x} inside .text data {a:#x}-{b:#x}")
            for fn in m.functions.values():
                for va, ins in fn.insns.items():
                    self.assertFalse(va < b and va + ins.size > a, f"instruction {va:#x} overlaps .text data {a:#x}-{b:#x}")

    def test_referenced_text_addresses_are_not_all_data(self):
        """The fix above must not turn into 'every .text address used as data is data': relocated code
        pointers that are real entries stay functions (e.g. the MMX memcpy alignment target)."""
        m = core()
        self.assertIn(0x10101058, m.functions)


class X87Decoding(unittest.TestCase):
    """Register forms are decoded from the encoding (Intel SDM), not from the mnemonic."""

    def expr(self, code):
        return " ".join(lift_bytes(code))

    def test_d8_forms_st0_is_destination(self):
        self.assertIn("*ST(c, 0) = *ST(c, 0) - *ST(c, 1);", self.expr(b"\xd8\xe1"))   # fsub st(0), st(1)
        self.assertIn("*ST(c, 0) = *ST(c, 1) - *ST(c, 0);", self.expr(b"\xd8\xe9"))   # fsubr st(0), st(1)
        self.assertIn("*ST(c, 0) = *ST(c, 0) / *ST(c, 1);", self.expr(b"\xd8\xf1"))   # fdiv st(0), st(1)
        self.assertIn("*ST(c, 0) = *ST(c, 1) / *ST(c, 0);", self.expr(b"\xd8\xf9"))   # fdivr st(0), st(1)

    def test_dc_de_forms_swap_sub_and_div(self):
        self.assertEqual(self.expr(b"\xdc\xe9"), "*ST(c, 1) = *ST(c, 1) - *ST(c, 0);")             # fsub st(1), st(0)
        self.assertEqual(self.expr(b"\xdc\xe1"), "*ST(c, 1) = *ST(c, 0) - *ST(c, 1);")             # fsubr st(1), st(0)
        self.assertEqual(self.expr(b"\xde\xe9"), "*ST(c, 1) = *ST(c, 1) - *ST(c, 0); fpop(c);")    # fsubp st(1), st(0)
        self.assertEqual(self.expr(b"\xde\xe1"), "*ST(c, 1) = *ST(c, 0) - *ST(c, 1); fpop(c);")    # fsubrp st(1), st(0)
        self.assertEqual(self.expr(b"\xde\xf9"), "*ST(c, 1) = *ST(c, 1) / *ST(c, 0); fpop(c);")    # fdivp st(1), st(0)
        self.assertEqual(self.expr(b"\xde\xf1"), "*ST(c, 1) = *ST(c, 0) / *ST(c, 1); fpop(c);")    # fdivrp st(1), st(0)

    def test_compare_and_status(self):
        self.assertIn("fcompare(c, *ST(c, 0), *ST(c, 1)); fpop(c); fpop(c);", self.expr(b"\xde\xd9"))   # fcompp
        self.assertIn("fstatus(c)", self.expr(b"\xdf\xe0"))                                            # fnstsw ax

    def test_80bit_memory_forms_are_unsupported(self):
        with self.assertRaises(Unsupported):
            lift_bytes(b"\xdb\x28")       # fld tbyte ptr [eax]
        with self.assertRaises(Unsupported):
            lift_bytes(b"\xdb\x38")       # fstp tbyte ptr [eax]


class Traps(unittest.TestCase):
    def test_mmx_is_a_trap(self):
        with self.assertRaises(Unsupported):
            lift_bytes(b"\x0f\x6f\x06")   # movq mm0, qword ptr [esi]

    def test_noreturn_call_is_followed_by_a_trap(self):
        m = core()
        lifter = Lifter(m)
        # any function calling the _CxxThrowException thunk ends that block with a trap
        thunk = next(e for e, fn in m.functions.items()
                     if len(fn.insns) == 1 and next(iter(fn.insns.values())).mnemonic == "jmp"
                     and lifter.iat_name(next(iter(fn.insns.values())).operands[0]) == "MSVCR70.dll!_CxxThrowException")
        caller = next(fn for fn in m.functions.values() if thunk in fn.calls)
        text = "\n".join(lifter.lift_function(caller))
        self.assertIn("returned from a call treated as noreturn", text)

    def test_mmx_memcpy_path_traps_and_scalar_path_does_not(self):
        m = core()
        text = "\n".join(Lifter(m).lift_function(m.functions[0x10101000]))
        self.assertIn("MMX/SSE instruction", text)
        self.assertIn("P(0x101011f5u); /* rep movsd", text)        # the scalar fallback is translated code
        self.assertNotIn('xrt_trap(c, 0x101011f5u', text)


class IntegerSemantics(unittest.TestCase):
    def test_inc_preserves_carry(self):
        self.assertIn("cf_ = c->cf", " ".join(lift_bytes(b"\x40")))           # inc eax

    def test_sbb_uses_old_carry_for_both_result_and_flags(self):
        s = " ".join(lift_bytes(b"\x1b\xc0"))                                 # sbb eax, eax
        self.assertLess(s.index("a_ - b_ - c->cf"), s.index("c->cf = a_ < b_ + c->cf"))

    def test_idiv_checks_divide_error(self):
        self.assertIn("xrt_div0", " ".join(lift_bytes(b"\xf7\xf9")))           # idiv ecx

    def test_push_esp_relative_reads_before_decrement(self):
        s = " ".join(lift_bytes(b"\xff\x74\x24\x08"))                         # push dword ptr [esp+8]
        self.assertLess(s.index("rd32"), s.index("push32"))


if __name__ == "__main__":
    unittest.main()
