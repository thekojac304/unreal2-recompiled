"""xlift - static x86-32 (MSVC 7.0) -> C translator for whole modules (X1 translated runtime).

Each guest function becomes `void f_<va>(CPU* c)`. Guest registers, flags, x87 state and the
guest stack are explicit; guest memory is the runtime's flat 32-bit address space. Control flow:
  direct call   -> push return address, call f_<target>, check the popped return address
  indirect call -> xrt_icall(c, target, return-address)   (runtime dispatch table, fatal if unknown)
  jump table    -> switch over the recovered case labels (default: fatal diagnostic)
  other indirect jmp -> xrt_ijmp(c, target)                (tail dispatch, fatal if unknown)
  fs: segment   -> guest TEB (SEH chain at fs:[0])
Functions that install a C++ EH registration (`mov fs:[0], esp`) get a host resume point so the
runtime's __CxxFrameHandler can transfer control to catch continuations.
Anything the translator does not implement becomes xrt_trap(...) at that instruction: it stops
execution with the address, mnemonic and guest backtrace if (and only if) it is reached.

Usage:
  python -I tools/xrt/xlift.py <module> --out <dir> [--base 0x..] [--select all|trace:<depmap.json>]
                               [--closure] [--chunk 300]
"""
import collections
import hashlib
import json
import os
import re
import sys

from capstone import x86 as X

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from discover import JCC, Module  # noqa: E402

REG32 = {"eax": 0, "ecx": 1, "edx": 2, "ebx": 3, "esp": 4, "ebp": 5, "esi": 6, "edi": 7}
REG16 = {"ax": 0, "cx": 1, "dx": 2, "bx": 3, "sp": 4, "bp": 5, "si": 6, "di": 7}
REG8L = {"al": 0, "cl": 1, "dl": 2, "bl": 3}
REG8H = {"ah": 0, "ch": 1, "dh": 2, "bh": 3}
COND = {"e": "c->zf", "ne": "!c->zf", "l": "(c->sf != c->of)", "ge": "(c->sf == c->of)",
        "le": "(c->zf || c->sf != c->of)", "g": "(!c->zf && c->sf == c->of)", "b": "c->cf", "ae": "!c->cf",
        "be": "(c->cf || c->zf)", "a": "(!c->cf && !c->zf)", "s": "c->sf", "ns": "!c->sf", "p": "c->pf",
        "np": "!c->pf", "o": "c->of", "no": "!c->of"}
MASK = {8: "0xFFu", 16: "0xFFFFu", 32: "0xFFFFFFFFu"}
X87_CONST = {"fld1": "1.0", "fldz": "0.0", "fldpi": "XRT_PI", "fldl2e": "XRT_L2E", "fldl2t": "XRT_L2T",
             "fldlg2": "XRT_LG2", "fldln2": "XRT_LN2"}
SIMD_PREFIXES = ("movq", "movd", "movnt", "prefetch", "emms", "sfence", "lfence", "mfence", "pxor", "padd", "psub",
                 "pmul", "pand", "por", "punpck", "pack", "psll", "psrl", "psra", "pcmp", "pshuf", "movaps", "movups",
                 "movss", "movlps", "movhps", "movsd ", "shufps", "mulps", "addps", "subps", "divps", "andps", "orps",
                 "xorps", "cmp", "movmskps", "maxps", "minps", "sqrtps", "rsqrtps", "rcpps", "cvt", "comiss", "ucomiss",
                 "unpck", "movhlps", "movlhps", "andnps", "mulss", "addss", "subss", "divss", "sqrtss", "maxss", "minss")


class Unsupported(Exception):
    pass


def is_simd(ins):
    for op in ins.operands:
        if op.type == X.X86_OP_REG:
            n = ins.reg_name(op.reg)
            if n.startswith("mm") or n.startswith("xmm"):
                return True
    return ins.mnemonic in ("emms", "sfence", "lfence", "mfence") or ins.mnemonic.startswith("prefetch")


class Lifter:
    def __init__(self, mod):
        self.mod = mod
        self.img = mod.img
        self.md = mod.md
        self.stats = collections.Counter()
        self.traps = collections.Counter()

    # ------------------------------------------------------------------ operands
    def rn(self, op):
        return self.md.reg_name(op.reg)

    def addr(self, op):
        mm = op.mem
        parts = []
        seg = self.md.reg_name(mm.segment) if mm.segment else None
        if seg == "fs":
            parts.append("c->fs_base")
        elif seg not in (None, "ds", "ss", "es", "cs"):
            raise Unsupported(f"segment {seg}")
        if mm.base:
            parts.append(self.reg_read32(self.md.reg_name(mm.base)))
        if mm.index:
            parts.append(f"{self.reg_read32(self.md.reg_name(mm.index))}*{mm.scale}u")
        if mm.disp or not parts:
            parts.append(f"0x{mm.disp & 0xFFFFFFFF:x}u")
        return "(uint32_t)(" + " + ".join(parts) + ")"

    @staticmethod
    def reg_read32(name):
        if name not in REG32:
            raise Unsupported(f"address register {name}")
        return f"c->r[{REG32[name]}]"

    def read(self, op, size=None):
        size = size or op.size
        if op.type == X.X86_OP_REG:
            n = self.rn(op)
            if n in REG32:
                return f"c->r[{REG32[n]}]"
            if n in REG16:
                return f"(c->r[{REG16[n]}] & 0xFFFFu)"
            if n in REG8L:
                return f"(c->r[{REG8L[n]}] & 0xFFu)"
            if n in REG8H:
                return f"((c->r[{REG8H[n]}] >> 8) & 0xFFu)"
            raise Unsupported(f"register {n}")
        if op.type == X.X86_OP_IMM:
            return f"0x{op.imm & ((1 << (size * 8)) - 1):x}u"
        if op.type == X.X86_OP_MEM:
            fn = {1: "rd8", 2: "rd16", 4: "rd32"}.get(size)
            if not fn:
                raise Unsupported(f"memory operand size {size}")
            return f"{fn}({self.addr(op)})"
        raise Unsupported("operand type")

    def write(self, op, val):
        if op.type == X.X86_OP_REG:
            n = self.rn(op)
            if n in REG32:
                return f"c->r[{REG32[n]}] = (uint32_t)({val});"
            if n in REG16:
                return f"c->r[{REG16[n]}] = (c->r[{REG16[n]}] & 0xFFFF0000u) | ((uint32_t)({val}) & 0xFFFFu);"
            if n in REG8L:
                return f"c->r[{REG8L[n]}] = (c->r[{REG8L[n]}] & 0xFFFFFF00u) | ((uint32_t)({val}) & 0xFFu);"
            if n in REG8H:
                return f"c->r[{REG8H[n]}] = (c->r[{REG8H[n]}] & 0xFFFF00FFu) | (((uint32_t)({val}) & 0xFFu) << 8);"
            raise Unsupported(f"write register {n}")
        if op.type == X.X86_OP_MEM:
            fn = {1: "wr8", 2: "wr16", 4: "wr32"}.get(op.size)
            if not fn:
                raise Unsupported(f"memory write size {op.size}")
            return f"{fn}({self.addr(op)}, (uint{op.size * 8}_t)({val}));"
        raise Unsupported("write to non-lvalue")

    def imm_or_read(self, op, bits):
        if op.type == X.X86_OP_IMM:
            return f"0x{op.imm & ((1 << bits) - 1):x}u"
        return self.read(op)

    def sti(self, op):
        n = self.rn(op)
        m = re.match(r"st\((\d)\)", n)
        if not m:
            raise Unsupported(f"x87 operand {n}")
        return int(m.group(1))

    # ------------------------------------------------------------------ instruction translation
    def lift_insn(self, ins, fn, eh):
        m, ops, va = ins.mnemonic, ins.operands, ins.address
        nxt = va + ins.size
        o = []
        bits = ops[0].size * 8 if ops and ops[0].type != X.X86_OP_IMM else 32
        if is_simd(ins):
            raise Unsupported(f"MMX/SSE instruction '{m} {ins.op_str}' (CPUID reports no MMX/SSE; path should be unreachable)")
        if ins.prefix[0] in (0xF0,):     # lock prefix: atomicity is moot under the runtime's single execution baton
            pass
        if m in ("mov", "movzx"):
            if ops[0].type == X.X86_OP_MEM and ops[0].mem.segment and self.md.reg_name(ops[0].mem.segment) == "fs" \
                    and ops[0].mem.disp == 0 and not ops[0].mem.base and not ops[0].mem.index:
                o.append(self.write(ops[0], self.read(ops[1])))
                if ops[1].type == X.X86_OP_REG and self.rn(ops[1]) == "esp" and eh:
                    o.append("xrt_eh_note(c, &ehf_);")
                return o
            if ops[1].type == X.X86_OP_REG and self.rn(ops[1]) in ("es", "ds", "ss", "cs", "fs", "gs"):
                raise Unsupported("segment register read")
            o.append(self.write(ops[0], self.read(ops[1])))
        elif m == "movsx":
            sb = ops[1].size * 8
            o.append(self.write(