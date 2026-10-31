"""Snippet and vector generator for the differential instruction test (see README.md).

For every census form and encoding class (census.json) it synthesizes relocatable test snippets: the
encoding class of the census (prefixes, opcode, ModRM reg extension, immediate width) with registers
chosen here and memory operands addressing the scratch windows through base registers, absolute
addresses inside the window, or ESP. Every snippet is checked by disassembling it again: it must
reproduce the census form key and encoding class exactly.

Writes to experiments/xrt/build/insn_diff/:
  cases.bin      snippets + input vectors for both harnesses (record layout: insn_diff.h)
  expect.bin     per case: defined-EFLAGS mask, defined x87 condition-code mask, flags (bit0: #DE per SDM)
  snippets.json  per snippet: form, encoding, variant, text, bytes, comparison rules
  id_lifted.c    the snippets lifted by tools/xrt/xlift.py (Lifter.lift_insn), one C function each

Usage: python -I gen.py [--seed N] [--scale F]
"""
import json
import math
import os
import random
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone import x86 as X

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "xrt"))
sys.path.insert(0, HERE)
import extended  # noqa: E402
from census import enc_key, encoding, opkind  # noqa: E402
from xlift import FLAGS, Lifter, Unsupported  # noqa: E402

BUILD = os.path.join(WS, "experiments", "xrt", "build", "insn_diff")
ID_DATA, ID_DATA_SIZE, ID_STACK, ID_STACK_SIZE = 0x20008000, 0x200, 0x2000BF00, 0x200
S0 = 0x2000C000
CODE_VA = 0x30000000
CF, PF, AF, ZF, SF, DF, OF = 0x1, 0x4, 0x10, 0x40, 0x80, 0x400, 0x800
ALLF = CF | PF | ZF | SF | OF | DF          # compared EFLAGS bits (AF is never compared: not modelled)
C0, C1, C2, C3 = 0x100, 0x200, 0x400, 0x4000
FCW = 0x027F

R32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"]
R16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]
R8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
STRING_OPS = {"movs", "stos", "cmps", "scas", "lods"}
SHIFTS = {"shl", "sal", "shr", "sar", "rol", "ror"}
ALU2 = {"add", "sub", "cmp", "adc", "sbb", "and", "or", "xor", "test"}
ALU1 = {"inc", "dec", "not", "neg"}
MOVES = {"mov", "movzx", "movsx", "lea", "xchg", "nop", "cdq", "cwd", "cwde", "cbw", "bswap"}
SETCC = ["seto", "setno", "setb", "setae", "sete", "setne", "setbe", "seta",
         "sets", "setns", "setp", "setnp", "setl", "setge", "setle", "setg"]

EDGES = {
    8: [0, 1, 2, 0x7E, 0x7F, 0x80, 0x81, 0xFE, 0xFF, 0x40],
    16: [0, 1, 0x7F, 0x80, 0xFF, 0x7FFF, 0x8000, 0x8001, 0xFFFE, 0xFFFF],
    32: [0, 1, 0x7F, 0x80, 0xFF, 0x7FFF, 0x8000, 0xFFFF, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFE, 0xFFFFFFFF],
}
IMM_LISTS = {
    1: [0, 1, 0x7F, 0x80, 0xFF, 0x10, None, None],
    2: [0, 1, 0x7FFF, 0x8000, 0xFFFF, None, None],
    4: [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0xFF, None, None],
}
SHIFT_IMMS = list(range(0, 34)) + [0x3F, 0x40, 0x80, 0xFF]

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True


def f64_bits(b):
    return struct.unpack("<d", struct.pack("<Q", b))[0]


QNAN, QNAN_NEG, QNAN_PAY = f64_bits(0x7FF8000000000000), f64_bits(0xFFF8000000000000), f64_bits(0x7FF8000000012345)
SNAN64 = 0x7FF0000000000123                      # memory-only (bits)
INF = float("inf")
F64_EDGE = [0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 1.5, -1.5, 2.5, -2.5, 3.5, -3.5, 0.49999999999999994,
            2.0 ** 52, 2.0 ** 52 + 1, 2.0 ** 53, -2.0 ** 53, 1e308, -1e308, 1.7976931348623157e308,
            2.2250738585072014e-308, 5e-324, -5e-324, 2147483647.0, 2147483647.5, 2147483648.0, -2147483648.0,
            -2147483648.5, -2147483649.0, 32767.0, 32767.5, 32768.0, -32768.0, -32768.5, -32769.0, 2.0 ** 63,
            -2.0 ** 63, 9223372036854774784.0, -9223372036854774784.0, 2.0 ** 62, 1e18, -1e18, INF, -INF, QNAN,
            QNAN_NEG, QNAN_PAY, math.pi, math.e, 1 / 3, 0.1, -0.1, 100.0, 1e10, 3.4028234663852886e38,
            1.401298464324817e-45, 1e-30, 1e30]
F32_EDGE_BITS = [0x00000000, 0x80000000, 0x3F800000, 0xBF800000, 0x3F000000, 0x3FC00000, 0x40200000, 0xC0200000,
                 0x7F7FFFFF, 0xFF7FFFFF, 0x00800000, 0x00000001, 0x80000001, 0x7F800000, 0xFF800000, 0x7FC00000,
                 0xFFC00000, 0x7FC12345, 0x7F800001, 0x4B800000, 0x4B800001, 0x4F000000, 0xCF000000, 0x3DCCCCCD,
                 0x5F000000, 0xDF000000]
INT_EDGE = {16: [0, 1, 0xFFFF, 0x7FFF, 0x8000, 0x8001, 2, 0xFFFE, 100],
            32: [0, 1, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000, 0x80000001, 2, 0xFFFFFFFE, 1000000, 16777217],
            64: [0, 1, (1 << 64) - 1, (1 << 63) - 1, 1 << 63, (1 << 63) + 1, 1 << 53, (1 << 53) + 1, (1 << 62) + 1,
                 (1 << 64) - (1 << 53) - 1, 0x7FFFFFFF, 0x80000000, 1 << 32]}

# x87 instruction properties (Intel SDM): (pushes, pops, minimum depth, defined C0/C2/C3, value comparison)
X87 = {
    "fld": (1, 0, 0, 0, "exact"), "fild": (1, 0, 0, 0, "exact"), "fld1": (1, 0, 0, 0, "exact"),
    "fldz": (1, 0, 0, 0, "exact"), "fldl2e": (1, 0, 0, 0, "exact"), "fldln2": (1, 0, 0, 0, "exact"),
    "fldpi": (1, 0, 0, 0, "exact"), "fldlg2": (1, 0, 0, 0, "exact"), "fldl2t": (1, 0, 0, 0, "exact"),
    "fst": (0, 0, 1, 0, "exact"), "fstp": (0, 1, 1, 0, "exact"), "fist": (0, 0, 1, 0, "exact"),
    "fistp": (0, 1, 1, 0, "exact"),
    "fadd": (0, 0, 1, 0, "exact"), "fsub": (0, 0, 1, 0, "exact"), "fsubr": (0, 0, 1, 0, "exact"),
    "fmul": (0, 0, 1, 0, "exact"), "fdiv": (0, 0, 1, 0, "exact"), "fdivr": (0, 0, 1, 0, "exact"),
    "fiadd": (0, 0, 1, 0, "exact"), "fisub": (0, 0, 1, 0, "exact"), "fisubr": (0, 0, 1, 0, "exact"),
    "fimul": (0, 0, 1, 0, "exact"), "fidiv": (0, 0, 1, 0, "exact"), "fidivr": (0, 0, 1, 0, "exact"),
    "faddp": (0, 1, 2, 0, "exact"), "fsubp": (0, 1, 2, 0, "exact"), "fsubrp": (0, 1, 2, 0, "exact"),
    "fmulp": (0, 1, 2, 0, "exact"), "fdivp": (0, 1, 2, 0, "exact"), "fdivrp": (0, 1, 2, 0, "exact"),
    "fcom": (0, 0, 1, C0 | C2 | C3, "exact"), "fcomp": (0, 1, 1, C0 | C2 | C3, "exact"),
    "fucom": (0, 0, 1, C0 | C2 | C3, "exact"), "fucomp": (0, 1, 1, C0 | C2 | C3, "exact"),
    "fcompp": (0, 2, 2, C0 | C2 | C3, "exact"), "fucompp": (0, 2, 2, C0 | C2 | C3, "exact"),
    "ficom": (0, 0, 1, C0 | C2 | C3, "exact"), "ficomp": (0, 1, 1, C0 | C2 | C3, "exact"),
    "ftst": (0, 0, 1, C0 | C2 | C3, "exact"),
    "fxch": (0, 0, 2, 0, "exact"), "fchs": (0, 0, 1, 0, "exact"), "fabs": (0, 0, 1, 0, "exact"),
    "frndint": (0, 0, 1, 0, "exact"), "fsqrt": (0, 0, 1, 0, "exact"), "fscale": (0, 0, 2, 0, "exact"),
    "fsin": (0, 0, 1, C2, "ulp"), "fcos": (0, 0, 1, C2, "ulp"), "fptan": (1, 0, 1, C2, "ulp"),
    "fpatan": (0, 1, 2, 0, "ulp"), "fyl2x": (0, 1, 2, 0, "ulp"), "f2xm1": (0, 0, 1, 0, "ulp"),
    "fnstsw": (0, 0, 0, 0, "exact"), "fstsw": (0, 0, 0, 0, "exact"),
    "fnstcw": (0, 0, 0, 0, "exact"), "fstcw": (0, 0, 0, 0, "exact"), "fldcw": (0, 0, 0, 0, "exact"),
    "fnclex": (0, 0, 0, 0, "exact"), "fclex": (0, 0, 0, 0, "exact"),
    "fninit": (0, 0, 0, C0 | C2 | C3, "exact"), "finit": (0, 0, 0, C0 | C2 | C3, "exact"),
}
# fldcw operands: the modelled control word (and accepted variants), then states the runtime refuses
FLDCW_VALUES = [0x027F, 0x127F, 0x027F, 0x037F, 0x0E7F, 0x067F, 0x007F, 0x027E]


def fcw_in_model(cw):
    """Mirror of xrt_fldcw()'s documented model: PC=53-bit, RC=nearest, all exceptions masked."""
    return ((cw >> 8) & 3) == 2 and ((cw >> 10) & 3) == 0 and (cw & 0x3F) == 0x3F


# ---------------------------------------------------------------- helpers
def form_key(ins):
    kinds = tuple(opkind(md, op) for op in ins.operands)
    return f"{ins.mnemonic} " + ",".join(kinds) if kinds else ins.mnemonic


def dis(code):
    return list(md.disasm(code, CODE_VA))


def u32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def mem_bytes(regf, base, index, scale, disp, dsize):
    """ModRM [+SIB] [+disp] for a 32-bit memory operand; base/index are register numbers or None."""
    ss = {1: 0, 2: 1, 4: 2, 8: 3}[scale]
    if base is None and index is None:
        return bytes([(regf << 3) | 5]) + u32(disp)
    if base is None:
        return bytes([(regf << 3) | 4, (ss << 6) | (index << 3) | 5]) + u32(disp)
    if dsize == 0 and base == 5:
        dsize = 8
    mod = {0: 0, 8: 1, 32: 2}[dsize]
    if index is not None or base == 4:
        out = bytes([(mod << 6) | (regf << 3) | 4, (ss << 6) | ((4 if index is None else index) << 3) | base])
    else:
        out = bytes([(mod << 6) | (regf << 3) | base])
    if dsize == 8:
        out += struct.pack("<b", disp)
    elif dsize == 32:
        out += u32(disp)
    return out


def build(enc, regf=None, rm=None, mem=None, imm=None, moffs=None):
    b = bytes(enc["pre"]) + bytes(enc["opc"])
    if "modrm" in enc:
        b += bytes([enc["modrm"]])
    elif enc.get("rm_is_reg") is not None:
        rf = enc["ext"] if "ext" in enc else regf
        if enc["rm_is_reg"]:
            b += bytes([0xC0 | (rf << 3) | rm])
        else:
            b += mem_bytes(rf, *mem)
    elif enc.get("moffs"):
        b += u32(moffs)
    if "imm_size" in enc:
        b += (imm & ((1 << (8 * enc["imm_size"])) - 1)).to_bytes(enc["imm_size"], "little")
    return b


def xorshift(s):
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF
    return s


def window_fill(seed):
    """Python copy of id_fill() (insn_diff.h) without patches: (data, stack)."""
    s = seed or 0x9E3779B9
    data, stack = bytearray(), bytearray()
    for _ in range(ID_DATA_SIZE // 4):
        s = xorshift(s)
        data += struct.pack("<I", s)
    for _ in range(ID_STACK_SIZE // 4):
        s = xorshift(s)
        stack += struct.pack("<I", s)
    return data, stack


def reg_slot(name):
    """(physical register, bit shift, width) of a GPR name."""
    if name in R32:
        return R32.index(name), 0, 32
    if name in R16:
        return R16.index(name), 0, 16
    i = R8.index(name)
    return i & 3, (8 if i >= 4 else 0), 8


def base_mnem(m):
    return m.split(" ", 1)[1] if m.startswith(("rep ", "repe ", "repne ", "lock ")) else m


def is_cmov(bm):
    return bm.startswith("cmov")


def is_string(bm):
    return bm[:-1] in STRING_OPS and bm[-1] in "bwd"


def rval(w):
    m = (1 << w) - 1
    r = random.random()
    if r < 0.45:
        return random.getrandbits(w)
    if r < 0.62:
        return random.randint(-20, 20) & m
    if r < 0.78:
        return random.choice(EDGES[w]) & m
    if r < 0.92:
        return ((1 << random.randrange(w)) + random.choice([-1, 0, 1])) & m
    return random.getrandbits(w) & random.getrandbits(w)


def rflags():
    f = 2
    for b in (CF, PF, AF, ZF, SF, DF, OF):
        if random.random() < 0.5:
            f |= b
    return f


def rf64(kind="gen"):
    r = random.random()
    if kind == "gen":
        if r < 0.35:
            return random.choice(F64_EDGE)
        if r < 0.60:
            return random.uniform(-1000, 1000)
        if r < 0.80:
            return random.choice([-1, 1]) * random.uniform(1, 2) * 2.0 ** random.randint(-60, 60)
        if r < 0.90:
            return float(random.randint(-100, 100))
        while True:
            b = random.getrandbits(64)
            if (b >> 52) & 0x7FF != 0x7FF:
                return f64_bits(b)
    if kind == "int":                       # values around integer conversion boundaries
        if r < 0.5:
            return random.choice(F64_EDGE)
        lim = random.choice([2.0 ** 15, 2.0 ** 31, 2.0 ** 63, 2.0 ** 53, 1.0])
        return random.choice([-1, 1]) * lim + random.choice([-1.5, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 1.5]) * \
            (lim * 2.0 ** -52 if lim > 2.0 ** 52 else 1.0)
    if kind == "frac":
        if r < 0.3:
            return random.choice(F64_EDGE)
        return random.randint(-10 ** 6, 10 ** 6) + random.choice([0.5, 0.25, 0.75, 0.5 + 2 ** -30, random.random()])
    if kind == "trig":
        if r < 0.15:
            return random.choice([0.0, -0.0, math.pi, -math.pi, math.pi / 2, math.pi / 4, 1.0, -1.0, 1e-300, INF,
                                  -INF, QNAN, 2.0 ** 63, -2.0 ** 63, 2.0 ** 62, 1e19, 9223372036854774784.0])
        if r < 0.75:
            return random.uniform(-10, 10)
        return random.uniform(-1e6, 1e6)
    if kind == "unit":                      # f2xm1 domain [-1, 1]
        if r < 0.15:
            return random.choice([0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 1e-300, 2 ** -60])
        return random.uniform(-1, 1)
    if kind == "pos":                       # fyl2x x operand
        if r < 0.15:
            return random.choice([1.0, 2.0, 0.5, 0.0, -1.0, INF, 5e-324, 1e308, QNAN])
        return random.choice([1, 1, 1, 1e-10, 1e10]) * random.uniform(0, 4)
    if kind == "scale":
        if r < 0.2:
            return random.choice([0.0, 1.0, -1.0, 0.5, -0.5, 1.5, 10.0, -10.0, 1023.0, -1074.0, 52.9, -1022.5])
        return float(random.randint(-200, 200)) + random.choice([0.0, 0.0, 0.5, 0.75])
    if kind == "sqrt":
        if r < 0.2:
            return random.choice([0.0, -0.0, 1.0, 2.0, -1.0, INF, -INF, 5e-324, 1e308, QNAN, 4.0, 0.25])
        return random.uniform(0, 1) * 10.0 ** random.randint(-30, 30)
    raise ValueError(kind)


def f32_bits_of(v):
    try:
        return struct.unpack("<I", struct.pack("<f", v))[0]
    except OverflowError:
        return 0x7F800000 if v > 0 else 0xFF800000


def rf32_bits():
    r = random.random()
    if r < 0.35:
        return random.choice(F32_EDGE_BITS)
    if r < 0.90:
        return f32_bits_of(rf64())
    return random.getrandbits(32)


def rint(w):
    if random.random() < 0.4:
        return random.choice(INT_EDGE[w]) & ((1 << w) - 1)
    return rval(w) if w <= 32 else (random.getrandbits(64) if random.random() < 0.5
                                    else random.randint(-10 ** 6, 10 ** 6) & ((1 << 64) - 1))


# ---------------------------------------------------------------- snippets
class Snip:
    def __init__(self, code, form, enc, variant, family, extra=None):
        self.code = code
        self.insns = dis(code)
        assert sum(i.size for i in self.insns) == len(code), (code.hex(), [i.mnemonic for i in self.insns])
        self.form, self.enc, self.variant, self.family = form, enc, variant, family
        self.extra = extra or {}
        self.text = "; ".join(f"{i.mnemonic} {i.op_str}".strip() for i in self.insns)
        self.cases = []

    def meta(self):
        return {"form": self.form, "enc": self.enc, "variant": self.variant, "family": self.family,
                "text": self.text, "bytes": self.code.hex(), **self.extra}


def regs_of(ins):
    return [md.reg_name(op.reg) for op in ins.operands if op.type == X.X86_OP_REG]


def mems_of(ins):
    return [op for op in ins.operands if op.type == X.X86_OP_MEM]


def implicit_regs(ins):
    m = base_mnem(ins.mnemonic)
    if m in ("mul", "div", "idiv", "cdq", "cwd") or (m == "imul" and len(ins.operands) == 1):
        return {0, 2}
    if m in ("cbw", "cwde", "fnstsw"):
        return {0}
    if is_string(m):
        return {0, 1, 6, 7}
    if m in ("push", "pop"):
        return {4}
    if m == "leave":
        return {4, 5}
    if m in SHIFTS | {"shld", "shrd"}:
        return {1}
    return set()


def family_of(m):
    bm = base_mnem(m)
    if is_string(bm):
        return "string"
    if bm in MOVES or is_cmov(bm):
        return "move"
    if bm in ALU2:
        return "alu2"
    if bm in ALU1:
        return "alu1"
    if bm in SHIFTS:
        return "shift"
    if bm in ("shld", "shrd"):
        return "dshift"
    if bm in ("mul", "imul"):
        return "mul"
    if bm in ("div", "idiv"):
        return "div"
    if bm in ("push", "pop", "leave"):
        return "stack"
    if bm in ("cld", "std", "clc", "stc", "cmc"):
        return "flagop"
    if bm.startswith("set"):
        return "setcc"
    if bm.startswith("f"):
        return "x87"
    return "other"


def try_build(form, ek, enc, **kw):
    try:
        code = build(enc, **kw)
    except (KeyError, TypeError, struct.error):
        return None
    ins = dis(code)
    if len(ins) != 1 or ins[0].size != len(code):
        return None
    if form_key(ins[0]) != form or enc_key(encoding(md, ins[0])) != ek:
        return None
    return code


def mem_modes(form, ek, enc, avoid, regf, rnd):
    """(variant, code) for the memory addressing modes used for every memory encoding class."""
    out = []
    free = [r for r in (3, 6, 7, 5, 2, 1, 0) if r not in avoid and r != regf]
    if not free:
        free = [r for r in (3, 6, 7, 5) if r not in avoid]
    b = rnd.choice(free)
    idx_free = [r for r in free if r != b] or [r for r in (6, 7, 3) if r != b]
    i = rnd.choice(idx_free)
    sc = rnd.choice([1, 2, 4, 8])
    imm = enc.get("imm_size") and 0
    for variant, mem in (("[base+disp8]", (b, None, 1, rnd.randint(-0x40, 0x3F), 8)),
                         ("[base+index*scale+disp32]", (b, i, sc, rnd.randint(-0x40, 0x40), 32)),
                         ("[disp32]", (None, None, 1, ID_DATA + 0x100 + rnd.randint(0, 0x3F), 32)),
                         ("[esp+disp8]", (4, None, 1, rnd.choice([0, 4, 8, -4, -8, 12, 0x1C, 3]), 8))):
        if variant == "[esp+disp8]" and regf == 4:
            continue
        code = try_build(form, ek, enc, regf=regf, mem=mem, imm=imm)
        if code:
            out.append((variant, mem, code))
    return out


def snippets_for_encoding(form, f, ek, e, rnd):
    """All snippets (Snip) for one census encoding class."""
    enc = e["enc"]
    m = f["mnemonic"]
    fam = family_of(m)
    kinds = f["kinds"]
    variants_seen = f.get("variants", {})
    out = []
    imm_size = enc.get("imm_size")
    if imm_size:
        if fam == "shift":
            imms = SHIFT_IMMS
        else:
            imms = [v if v is not None else rnd.getrandbits(8 * imm_size) for v in IMM_LISTS[imm_size]]
    else:
        imms = [None]
    # implicit registers from a probe encoding
    probe_regs = set()
    bases = []                                         # (variant, kwargs)
    if "modrm" in enc or (enc.get("rm_is_reg") is None):
        if enc.get("moffs"):
            for k in range(3):
                bases.append((f"moffs#{k}", {"moffs": ID_DATA + 0x100 + rnd.randint(0, 0x3F)}))
        else:
            bases.append(("fixed", {}))
    elif enc["rm_is_reg"]:
        has_ext = "ext" in enc
        cands = []
        nreg = sum(1 for k in kinds if k.startswith("r"))
        for _ in range(40):
            rm = rnd.randrange(8)
            rf = None if has_ext else rnd.randrange(8)
            cands.append(("regs", {"rm": rm, "regf": rf}))
        if not has_ext and nreg >= 2:
            for r in rnd.sample(range(8), 8):
                cands.append(("same-reg", {"rm": r, "regf": r}))
        if "r8" in kinds:
            for _ in range(20):
                cands.append(("high-byte", {"rm": rnd.randrange(4, 8), "regf": None if has_ext else rnd.randrange(8)}))
                if not has_ext:
                    cands.append(("high-byte", {"rm": rnd.randrange(8), "regf": rnd.randrange(4, 8)}))
        if fam in ("mul", "div") and has_ext:
            cands.append(("operand=eax", {"rm": 0, "regf": None}))
            cands.append(("operand=edx", {"rm": 2, "regf": None}))
        if fam in ("shift", "dshift") and has_ext and "r8" in kinds:
            cands.append(("operand=ecx", {"rm": 1, "regf": None}))
        if variants_seen.get("esp-operand"):
            cands.append(("esp-operand(rm)", {"rm": 4, "regf": None if has_ext else rnd.choice([0, 1, 3, 6])}))
            if not has_ext:
                cands.append(("esp-operand(reg)", {"rm": rnd.choice([0, 1, 3, 6]), "regf": 4}))
        got = {}
        for variant, kw in cands:
            if variant in got and variant != "regs":
                continue
            if variant == "regs" and "regs" in got:
                continue
            imm = imms[0] if imms[0] is not None else None
            code = try_build(form, ek, enc, imm=imm, **kw)
            if not code:
                continue
            ins = dis(code)[0]
            names = regs_of(ins)
            if not variant.startswith("esp-operand") and any(n in ("esp", "sp") for n in names):
                continue
            if variant.startswith("esp-operand") and "esp" not in names:
                continue
            if variant == "high-byte" and not any(n in R8[4:] for n in names):
                continue
            if variant == "regs" and nreg >= 2 and len(set(reg_slot(n)[0] for n in names)) < nreg:
                continue
            if variant == "regs" and fam in ("mul", "div") and any(reg_slot(n)[0] in (0, 2) for n in names):
                continue
            if variant == "regs" and fam in ("shift", "dshift") and any(reg_slot(n)[0] == 1 for n in names[:1]):
                continue
            got[variant] = kw
            bases.append((variant, kw))
    else:
        has_ext = "ext" in enc
        imm0 = imms[0] if imms[0] is not None else 0
        probe = try_build(form, ek, enc, regf=None if has_ext else 0, mem=(3, None, 1, 8, 8), imm=imm0)
        if probe is None and not has_ext:
            for rf in range(8):
                probe = try_build(form, ek, enc, regf=rf, mem=(3, None, 1, 8, 8), imm=imm0)
                if probe:
                    break
        if probe is None:
            raise RuntimeError(f"cannot synthesize {form} / {ek}")
        pins = dis(probe)[0]
        avoid = implicit_regs(pins)
        rf = None
        if not has_ext:
            choices = [r for r in (0, 1, 2, 3, 5, 6, 7) if r not in avoid]
            rnd.shuffle(choices)
            for r in choices:
                if try_build(form, ek, enc, regf=r, mem=(3, None, 1, 8, 8), imm=imm0):
                    rf = r
                    break
        for variant, mem, code in mem_modes(form, ek, enc, avoid | ({rf} if rf is not None else set()), rf, rnd):
            bases.append((variant, {"regf": rf, "mem": mem}))
        if not has_ext and any(k.startswith("r") for k in kinds):
            # register operand aliases the base register of the memory operand
            for b in (3, 0, 1, 2):
                if b in avoid:
                    continue
                mem = (b, None, 1, rnd.randint(-0x40, 0x3F), 8)
                if try_build(form, ek, enc, regf=b, mem=mem, imm=imm0):
                    bases.append(("reg-aliases-base", {"regf": b, "mem": mem}))
                    break
            if "r8" in kinds:
                for r in (4, 5, 6, 7):
                    mem = (3 if r != 7 else 6, None, 1, rnd.randint(-0x40, 0x3F), 8)
                    code = try_build(form, ek, enc, regf=r, mem=mem, imm=imm0)
                    if code and any(n in R8[4:] for n in regs_of(dis(code)[0])):
                        bases.append(("high-byte", {"regf": r, "mem": mem}))
                        break
    if not bases:
        raise RuntimeError(f"no snippet for {form} / {ek}")
    for vi, (variant, kw) in enumerate(bases):
        use_imms = imms if (vi == 0 or fam == "shift" and vi < 2) else [imms[0], imms[-1]] if imms[0] is not None else [None]
        if variant.startswith("moffs"):
            use_imms = imms
        for imm in dict.fromkeys(use_imms):
            code = try_build(form, ek, enc, imm=imm, **kw)
            if code is None:
                continue
            v = variant + (f" imm={imm:#x}" if imm is not None else "")
            out.append(Snip(code, form, ek, v, fam, {"imm": imm}))
    return out


def extra_snippets(census, rnd):
    """Forms outside the census that validate shared lifter tables, and x87 status consumer sequences."""
    out = []
    # setcc: all 16 conditions (the condition table is shared with jcc)
    for cc in range(16):
        for rm in (rnd.choice([0, 1, 2, 3]), rnd.choice([4, 5, 6, 7])):
            code = bytes([0x0F, 0x90 + cc, 0xC0 | rm])
            out.append(Snip(code, f"{SETCC[cc]} r8", f"0f {0x90 + cc:02x} rm=reg", f"cond-table rm={R8[rm]}",
                            "setcc", {"extra": "condition table (shared with jcc)"}))
    # addressing-mode matrix through lea (registers arbitrary: no access) and mov r32, m32 / mov m32, r32
    modes = [("[base]", (3, None, 1, 0, 0)), ("[ebp+0]", (5, None, 1, 0, 8)), ("[esp]", (4, None, 1, 0, 0)),
             ("[base+disp8]", (6, None, 1, -0x24, 8)), ("[base+disp32]", (7, None, 1, 0x7C, 32)),
             ("[ebp+disp8]", (5, None, 1, 0x10, 8)), ("[ebp+disp32]", (5, None, 1, -0x90, 32)),
             ("[esp+disp8]", (4, None, 1, 0x14, 8)), ("[esp+disp32]", (4, None, 1, 0x20, 32)),
             ("[disp32]", (None, None, 1, ID_DATA + 0x120, 32))]
    for sc in (1, 2, 4, 8):
        modes += [(f"[base+index*{sc}]", (3, 6, sc, 0, 0)), (f"[base+index*{sc}+disp8]", (1, 7, sc, -0x10, 8)),
                  (f"[base+index*{sc}+disp32]", (6, 3, sc, 0x40, 32)), (f"[index*{sc}+disp32]", (None, 7, sc, ID_DATA + 0x80, 32)),
                  (f"[ebp+index*{sc}+disp32]", (5, 2, sc, -0x30, 32)), (f"[esp+index*{sc}+disp8]", (4, 1, sc, 0x08, 8))]
    lea = {"pre": [], "opc": [0x8D], "rm_is_reg": False}
    movl = {"pre": [], "opc": [0x8B], "rm_is_reg": False}
    movs = {"pre": [], "opc": [0x89], "rm_is_reg": False}
    for name, mem in modes:
        used = {r for r in mem[:2] if r is not None}
        rf = next(r for r in (0, 2, 1, 3, 6, 7) if r not in used)
        out.append(Snip(build(lea, regf=rf, mem=mem), "lea r32,m32", "8d rm=mem", f"addr-matrix {name}", "move",
                        {"extra": "addressing modes (lea: no memory access)"}))
        out.append(Snip(build(movl, regf=rf, mem=mem), "mov r32,m32", "8b rm=mem", f"addr-matrix {name}", "move",
                        {"extra": "addressing modes"}))
        out.append(Snip(build(movs, regf=rf, mem=mem), "mov m32,r32", "89 rm=mem", f"addr-matrix {name}", "move",
                        {"extra": "addressing modes"}))
    # fs: (SEH registration in the census: mov eax, fs:[0] / mov fs:[0], ecx|esp|eax). The native side
    # addresses its real TEB; the lifted side gets the same snapshot at the same guest address.
    for disp in (0, 0x18, 0x14, 0x04, 0x30, 0x24):
        out.append(Snip(bytes([0x64, 0xA1]) + u32(disp), "mov r32,m32", "a1 moffs", f"fs:[{disp:#x}]", "move",
                        {"extra": "fs: segment (TEB)"}))
        out.append(Snip(bytes([0x64, 0x8B, 0x0D]) + u32(disp), "mov r32,m32", "8b rm=mem", f"fs:[{disp:#x}]",
                        "move", {"extra": "fs: segment (TEB)"}))
    for disp in (0, 0x14):
        for rf in (1, 4, 2):
            out.append(Snip(bytes([0x64, 0x89, 0x05 | (rf << 3)]) + u32(disp), "mov m32,r32", "89 rm=mem",
                            f"fs:[{disp:#x}] reg={['eax', 'ecx', 'edx', 'ebx', 'esp'][rf]}", "move",
                            {"extra": "fs: segment (TEB)"}))
        out.append(Snip(bytes([0x64, 0xA3]) + u32(disp), "mov m32,r32", "a3 moffs", f"fs:[{disp:#x}]", "move",
                        {"extra": "fs: segment (TEB)"}))
    # x87 compare -> fnstsw ax -> test ah, mask (the consumer masks found in the census)
    masks = sorted({int(t.split("test ah, ")[1], 0) for t in census["fnstsw_ax_consumers"] if "test ah, " in t})
    cmps = [bytes([0xD8, 0x5B, 0x10]), bytes([0xD8, 0x53, 0x10]), bytes([0xDC, 0x5B, 0x10]), bytes([0xDC, 0x53, 0x10]),
            bytes([0xD8, 0xD9]), bytes([0xD8, 0xD1]), bytes([0xDE, 0xD9]), bytes([0xDD, 0xE1]), bytes([0xDD, 0xE9]),
            bytes([0xDA, 0xE9]), bytes([0xD9, 0xE4])]
    for cb in cmps:
        for mk in masks:
            code = cb + bytes([0xDF, 0xE0, 0xF6, 0xC4, mk])
            out.append(Snip(code, "x87 compare; fnstsw ax; test ah, imm", "sequence", f"mask={mk:#x}", "x87seq",
                            {"extra": "fnstsw consumer pattern from the census"}))
    return out


# ---------------------------------------------------------------- vectors
class Case:
    __slots__ = ("r", "eflags", "nst", "st", "patches", "seed", "fmask", "ccmask", "flags")

    def __init__(self):
        self.r = [random.getrandbits(32) for _ in range(8)]
        self.r[4] = S0 - 4 * random.randint(0, 8)
        self.eflags = rflags()
        self.nst = 0
        self.st = [0.0] * 8
        self.patches = []
        self.seed = random.getrandbits(32) | 1
        self.fmask = ALLF
        self.ccmask = 0
        self.flags = 0

    def setreg(self, name, val):
        p, sh, w = reg_slot(name)
        msk = ((1 << w) - 1) << sh
        self.r[p] = (self.r[p] & ~msk & 0xFFFFFFFF) | ((val << sh) & msk)

    def getreg(self, name):
        p, sh, w = reg_slot(name)
        return (self.r[p] >> sh) & ((1 << w) - 1)

    def poke(self, addr, data):
        for k in range(0, len(data), 8):
            self.patches.append((addr + k, bytes(data[k:k + 8])))
        assert len(self.patches) <= 4

    def pack(self, snip):
        pt = b""
        for a, b in self.patches[:4]:
            pt += struct.pack("<IB3x", a, len(b)) + b.ljust(8, b"\0")
        pt = pt.ljust(64, b"\0")
        return struct.pack("<II8IIIHHI8d", snip, self.seed, *self.r, self.eflags, self.nst, FCW, 0, 0,
                           *self.st) + pt


def ea_of(case, op):
    mm = op.mem
    a = mm.disp
    if mm.base:
        a += case.r[reg_slot(md.reg_name(mm.base))[0]]
    if mm.index:
        a += case.r[reg_slot(md.reg_name(mm.index))[0]] * mm.scale
    return a & 0xFFFFFFFF


def is_fs(op):
    return op.type == X.X86_OP_MEM and op.mem.segment and md.reg_name(op.mem.segment) == "fs"


def setup_addresses(case, ins, lea=False):
    """Give address registers pointer values (data or stack window) and index registers small values."""
    for op in mems_of(ins):
        mm = op.mem
        if is_fs(op):
            continue
        if mm.segment and md.reg_name(mm.segment) == "es" or is_string(base_mnem(ins.mnemonic)):
            continue
        if lea:
            continue
        if mm.base and md.reg_name(mm.base) != "esp":
            case.r[reg_slot(md.reg_name(mm.base))[0]] = ID_DATA + 0x80 + random.randint(0, 0x40)
        if mm.index:
            case.r[reg_slot(md.reg_name(mm.index))[0]] = random.randint(0, 15)


def data_slots(ins, addr_regs):
    """Explicit data operands: ('reg', name, width) / ('mem', op, width); lea has no memory operand access."""
    out = []
    lea = ins.mnemonic == "lea"
    for op in ins.operands:
        if op.type == X.X86_OP_REG:
            n = md.reg_name(op.reg)
            if n.startswith("st") or n in ("es", "cs", "ss", "ds", "fs", "gs"):
                continue
            if reg_slot(n)[0] in addr_regs:
                continue
            out.append(("reg", n, op.size * 8))
        elif op.type == X.X86_OP_MEM and not lea and not is_fs(op):
            out.append(("mem", op, op.size * 8))
    return out


def addr_regs_of(ins):
    s = {4}
    for op in mems_of(ins):
        if op.mem.base:
            s.add(reg_slot(md.reg_name(op.mem.base))[0])
        if op.mem.index:
            s.add(reg_slot(md.reg_name(op.mem.index))[0])
    return s


def put(case, slot, val, w):
    if slot[0] == "reg":
        case.setreg(slot[1], val)
    else:
        a = ea_of(case, slot[1])
        case.poke(a, (val & ((1 << w) - 1)).to_bytes(w // 8, "little"))


def flag_mask(ins, case, count=None):
    """Defined EFLAGS bits after `ins` (Intel SDM), given the case's input state."""
    bm = base_mnem(ins.mnemonic)
    w = ins.operands[0].size * 8 if ins.operands else 32
    if bm in SHIFTS or bm in ("shld", "shrd"):
        c = count & 0x1F
        if c == 0:
            return ALLF
        mk = ALLF
        if c != 1:
            mk &= ~OF
        if bm in ("shl", "sal", "shr") and c >= w:
            mk &= ~CF
        if bm in ("shld", "shrd") and c > w:
            mk = DF
        return mk
    if bm in ("mul", "imul"):
        return ALLF & ~(SF | ZF | PF)
    if bm in ("div", "idiv"):
        return DF
    return ALLF


def gen_integer(sn, n):
    ins = sn.insns[0]
    bm = base_mnem(ins.mnemonic)
    fam = sn.family
    lea = bm == "lea"
    addr = set() if lea else addr_regs_of(ins)
    if bm == "leave":
        addr |= {5}
    slots = data_slots(ins, addr)
    count_slot = None
    if fam in ("shift", "dshift") and ins.operands[-1].type == X.X86_OP_REG and len(ins.operands) >= 2 \
            and md.reg_name(ins.operands[-1].reg) == "cl":
        count_slot = slots.pop()
    implicit = []
    if fam == "mul" and len(ins.operands) == 1:
        implicit = [("reg", {8: "al", 16: "ax", 32: "eax"}[ins.operands[0].size * 8], ins.operands[0].size * 8)]
    if bm in ("cdq", "cwde", "cbw", "cwd"):
        implicit = [("reg", "eax" if bm in ("cdq", "cwde") else "ax", 32 if bm in ("cdq", "cwde") else 16)]
    slots = implicit + slots
    widths = [s[2] for s in slots]
    sched = []
    if len(slots) == 2:
        e0 = EDGES[widths[0]] if widths[0] in EDGES else [0]
        e1 = EDGES[widths[1]] if widths[1] in EDGES else [0]
        sched = [(a, b) for a in e0 for b in e1]
    elif len(slots) == 1 and slots[0][2] in EDGES:
        sched = [(a,) for a in EDGES[slots[0][2]] for _ in (0, 1)]
    cases = []
    for k in range(max(n, len(sched) * (2 if bm in ("adc", "sbb") else 1) if n >= 100 else n)):
        c = Case()
        setup_addresses(c, ins, lea)
        if bm == "leave":
            c.r[5] = S0 - 4 * random.randint(-8, 8)
        if bm in ("push", "pop") or ins.mnemonic.startswith("push") or bm == "leave":
            pass
        if k < len(sched) * (2 if bm in ("adc", "sbb") else 1):
            vals = sched[k % len(sched)] if sched else ()
            if bm in ("adc", "sbb"):
                c.eflags = (c.eflags & ~CF) | (CF if k >= len(sched) else 0)
            elif bm in ("inc", "dec", "not", "neg") or len(slots) == 1:
                c.eflags = (c.eflags & ~CF) | (k & 1)
        else:
            vals = tuple(rval(w) if w in EDGES else 0 for w in widths)
        for s, v in zip(slots, vals):
            if s[2] in EDGES:
                put(c, s, v, s[2])
        cnt = None
        if count_slot is not None:
            cnt = k if k < 34 else (random.randint(0, 255) if random.random() < 0.6 else random.randint(0, 40))
            c.setreg("cl", cnt)
        elif fam in ("shift", "dshift"):
            cnt = 1 if len(ins.operands) == 1 or ins.operands[-1].type != X.X86_OP_IMM else ins.operands[-1].imm
        c.fmask = flag_mask(ins, c, cnt)
        cases.append(c)
    return cases


def gen_div(sn, n):
    ins = sn.insns[0]
    bm = base_mnem(ins.mnemonic)
    op = ins.operands[0]
    signed = bm == "idiv"
    addr = addr_regs_of(ins)
    cases = []
    edges_d = [1, 0xFFFFFFFF, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 3, 0x10000, 0]
    edges_n = [0, 1, (1 << 64) - 1, 0x7FFFFFFF, (1 << 64) - (1 << 31), 1 << 32, (1 << 63), (1 << 63) - 1, 0xFFFFFFFF,
               (1 << 64) - 0xFFFFFFFF]
    for k in range(n):
        c = Case()
        setup_addresses(c, ins)
        if k < len(edges_d) * len(edges_n):
            d, num = edges_d[k // len(edges_n)], edges_n[k % len(edges_n)]
        else:
            r = random.random()
            d = rval(32)
            if r < 0.12:
                d = 0
            if r < 0.6 and d:
                sd = d - (1 << 32) if signed and d >> 31 else d
                if signed:
                    q = random.randint(-(1 << 31), (1 << 31) - 1) if random.random() < 0.5 else random.randint(-100, 100)
                    rem = random.randint(0, abs(sd) - 1) * (1 if random.random() < 0.5 else -1)
                    if q * sd + rem != 0 and (q * sd + rem > 0) != (rem > 0) and rem != 0:
                        rem = -rem
                    num = (q * sd + rem) & ((1 << 64) - 1)
                else:
                    q = random.getrandbits(32) if random.random() < 0.5 else random.randint(0, 100)
                    num = q * d + random.randint(0, d - 1)
            elif r < 0.8:
                num = random.getrandbits(64)
            else:
                num = random.getrandbits(32) | (random.choice([0, 0xFFFFFFFF, 1, 0x7FFFFFFF, 0x80000000]) << 32)
        num &= (1 << 64) - 1
        if op.type == X.X86_OP_REG:
            p = reg_slot(md.reg_name(op.reg))[0]
            if p == 0:
                num = (num & ~0xFFFFFFFF) | d
            elif p == 2:
                num = (num & 0xFFFFFFFF) | (d << 32)
            c.r[p] = d
        c.r[0], c.r[2] = num & 0xFFFFFFFF, num >> 32
        if op.type == X.X86_OP_MEM:
            c.poke(ea_of(c, op), d.to_bytes(4, "little"))
        if signed:
            sn_ = num - (1 << 64) if num >> 63 else num
            sd = d - (1 << 32) if d >> 31 else d
            de = sd == 0 or not (-(1 << 31) <= int(abs(sn_) // abs(sd)) * (1 if (sn_ < 0) == (sd < 0) else -1) < (1 << 31))
        else:
            de = d == 0 or num // d > 0xFFFFFFFF
        c.flags = 1 if de else 0
        c.fmask = DF
        cases.append(c)
    return cases


def gen_string(sn, n):
    ins = sn.insns[0]
    m = ins.mnemonic
    rep = " " in m
    bm = base_mnem(m)
    size = {"b": 1, "w": 2, "d": 4}[bm[-1]]
    op = bm[:-1]
    cases = []
    for k in range(n):
        c = Case()
        cnt = (k % 6) if k < 72 else random.randint(0, 24)
        down = (k // 6) % 2 if k < 72 else random.random() < 0.5
        c.eflags = (c.eflags & ~DF) | (DF if down else 0)
        base = ID_DATA + 0x100
        esi = base + random.randint(-0x20, 0x20) * (1 if random.random() < 0.5 else size)
        if op == "movs" and random.random() < 0.5:
            edi = esi + size * random.randint(-3, 3) + random.choice([0, 0, 1])        # overlapping copies
        else:
            edi = base + random.choice([-0x60, 0x60, -0x50, 0x48]) + random.randint(0, 7)
        c.r[6], c.r[7] = esi & 0xFFFFFFFF, edi & 0xFFFFFFFF
        if rep:
            c.r[1] = cnt
        c.r[0] = rval(32)
        if op in ("cmps", "scas"):
            data, _ = window_fill(c.seed)
            span = max(cnt, 1) * size
            j = random.randint(0, min(span, 8))
            if op == "cmps" and j:
                # make the first j compared bytes equal so that repe/repne stop at different points
                if down:
                    src = data[esi - ID_DATA - j + size: esi - ID_DATA + size]
                    c.poke(edi - j + size, src)
                else:
                    src = data[esi - ID_DATA: esi - ID_DATA + j]
                    c.poke(edi, src)
            if op == "scas":
                c.r[0] = int.from_bytes(data[edi - ID_DATA: edi - ID_DATA + 4], "little") if random.random() < 0.5 else c.r[0]
        cases.append(c)
    return cases


def gen_setcc(sn, n):
    cases = []
    for k in range(max(n, 128)):
        c = Case()
        setup_addresses(c, sn.insns[0])
        bits = k % 128
        f = 2
        for i, b in enumerate((CF, PF, AF, ZF, SF, DF, OF)):
            if bits >> i & 1:
                f |= b
        c.eflags = f if k < 128 else rflags()
        cases.append(c)
    return cases


def x87_props(ins):
    m = ins.mnemonic
    p = X87.get(m)
    if p is None:
        raise RuntimeError(f"no x87 properties for {m}")
    pushes, pops, need, cc, mode = p
    for op in ins.operands:
        if op.type == X.X86_OP_REG:
            n = md.reg_name(op.reg)
            if n.startswith("st("):
                need = max(need, int(n[3]) + 1)
    if m == "fcompp" or (m == "fucompp"):
        need = 2
    return pushes, pops, need, cc, mode


def st_kind(m):
    return {"fsin": "trig", "fcos": "trig", "fptan": "trig", "f2xm1": "unit", "fsqrt": "sqrt",
            "frndint": "frac", "fistp": "int", "fist": "int"}.get(m, "gen")


def gen_x87(sn, n):
    cases = []
    seq = sn.family == "x87seq"
    ins = sn.insns[0]
    m = ins.mnemonic
    pushes, pops, need, cc, mode = x87_props(ins)
    maxd = 8 - pushes
    mem = mems_of(ins)
    for k in range(n):
        c = Case()
        setup_addresses(c, ins)
        c.nst = random.randint(need, maxd)
        kind = st_kind(m)
        for i in range(8):
            c.st[i] = rf64(kind)
        if m == "fpatan":
            c.st[0], c.st[1] = rf64("gen"), rf64("gen")
        if m == "fyl2x":
            c.st[0], c.st[1] = rf64("pos"), rf64("gen")
        if m == "fscale":
            c.st[0], c.st[1] = rf64("gen") if random.random() < 0.3 else random.uniform(-4, 4), rf64("scale")
        if (m.startswith("fcom") or m.startswith("fucom") or seq) and random.random() < 0.35:
            c.st[1] = c.st[0]                      # equal operands
        if m in ("fnstsw", "fstsw") and mem:
            # the stored status word includes the sticky exception flags and C1, which the model does not
            # keep: inputs are normal finite numbers so that loading them raises no exception
            for i in range(8):
                c.st[i] = random.choice([1.0, -2.5, 3.0e10, -7.25e-5, 0.1, 12345.0])
        if m in ("fninit", "finit"):
            c.flags |= 2                      # loads FCW 0x037F (64-bit precision) through xrt_fldcw: stops by design
        for op in mem:
            a = ea_of(c, op)
            w = op.size
            if m.startswith("fi") and m not in ("fist", "fistp"):
                v = rint(w * 8)
                c.poke(a, v.to_bytes(w, "little"))
            elif m in ("fst", "fstp", "fist", "fistp", "fnstsw", "fstsw", "fnstcw", "fstcw"):
                pass
            elif m == "fldcw":
                cw = FLDCW_VALUES[k % len(FLDCW_VALUES)] if k < 64 else random.choice(FLDCW_VALUES)
                c.poke(a, cw.to_bytes(2, "little"))
                if not fcw_in_model(cw):
                    c.flags |= 2              # the lifted runtime stops here by design (xrt_fldcw)
            elif w == 4:
                if random.random() < 0.35:
                    bits = f32_bits_of(c.st[0])
                else:
                    bits = rf32_bits()
                c.poke(a, bits.to_bytes(4, "little"))
            elif w == 8:
                r = random.random()
                bits = struct.unpack("<Q", struct.pack("<d", c.st[0] if r < 0.3 else rf64()))[0]
                if r > 0.98:
                    bits = SNAN64
                c.poke(a, bits.to_bytes(8, "little"))
        c.ccmask = cc
        cases.append(c)
    return cases


def vectors(sn, scale):
    fam = sn.family
    imm_variant = sn.extra.get("imm") is not None
    base_n = 320 if not imm_variant else 48
    if fam in ("shift", "dshift") and imm_variant:
        base_n = 40
    n = max(24, int(base_n * scale))
    if fam == "div":
        return gen_div(sn, max(n, 400))
    if fam == "string":
        return gen_string(sn, n)
    if fam == "setcc":
        return gen_setcc(sn, n)
    if fam in ("x87", "x87seq"):
        return gen_x87(sn, n)
    return gen_integer(sn, n)


def extended_forms(census):
    """Pseudo-census entries for extended.EXAMPLES that are not census encodings, and the lifter's
    answer for extended.UNSUPPORTED_EXAMPLES (deliberate traps: listed, not run)."""
    lifter = Lifter(_StubMod())
    forms = {}
    for code in extended.examples():
        ins = dis(code)
        assert len(ins) == 1 and ins[0].size == len(code), code.hex()
        i = ins[0]
        fk = form_key(i)
        enc = encoding(md, i)
        ek = enc_key(enc)
        if fk in census["forms"] and ek in census["forms"][fk]["encodings"]:
            continue
        f = forms.setdefault(fk, {"mnemonic": i.mnemonic, "kinds": [opkind(md, op) for op in i.operands],
                                  "count": 0, "encodings": {}, "variants": {}})
        f["encodings"].setdefault(ek, {"enc": enc, "count": 0, "example": f"{i.mnemonic} {i.op_str}".strip()})
    unsupported = []
    for code in extended.unsupported_examples():
        i = dis(code)[0]
        try:
            lifter.lift_insn(i, None)
            why = None
        except Unsupported as exc:
            why = str(exc)
        unsupported.append({"text": f"{i.mnemonic} {i.op_str}".strip(), "bytes": code.hex(), "lifter": why})
    return forms, unsupported


# ---------------------------------------------------------------- lifting
class _StubImg:
    iat = {}


class _StubMod:
    img = _StubImg()
    md = md


FLAG_BITS = {"cf": 0x001, "pf": 0x004, "zf": 0x040, "sf": 0x080, "of": 0x800}


def snippet_liveness(sn, lifter, live_end):
    """Flags live after each instruction of the snippet when `live_end` is live after its last one (the same
    backward rule as Lifter.flag_liveness on straight-line code)."""
    out = [None] * len(sn.insns)
    live = frozenset(live_end)
    for k in range(len(sn.insns) - 1, -1, -1):
        out[k] = live
        eff = lifter.flag_effect(sn.insns[k])
        uses, kills = eff if eff is not None else (FLAGS, frozenset())
        live = uses | (live - kills)
    return out


def lift_snippet(sn, idx, lifter, live_end=None):
    lines = [f"static void s_{idx}(CPU* c) {{"]
    live = snippet_liveness(sn, lifter, live_end) if live_end is not None else [None] * len(sn.insns)
    for ins, lv in zip(sn.insns, live):
        text = f"{ins.mnemonic} {ins.op_str}".strip()
        lines.append(f"    P(0x{ins.address:x}u); /* {text} */")
        lifter.live = lv
        try:
            stmts = lifter.lift_insn(ins, None)
        except Unsupported as exc:
            why = f"unsupported: {text}: {exc}".replace("\\", "\\\\").replace('"', "'")
            stmts = [f'xrt_trap(c, 0x{ins.address:x}u, "{why}");']
        finally:
            lifter.live = None
        lines.extend("    " + s for s in stmts)
    lines.append("}")
    return lines


def main():
    args = sys.argv[1:]
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 20261022
    scale = float(args[args.index("--scale") + 1]) if "--scale" in args else 1.0
    random.seed(seed)
    rnd = random.Random(seed + 1)
    with open(os.path.join(BUILD, "census.json"), encoding="utf-8") as f:
        census = json.load(f)
    snips = []
    for form, fdesc in census["forms"].items():
        for ek, e in fdesc["encodings"].items():
            snips.extend(snippets_for_encoding(form, fdesc, ek, e, rnd))
    snips.extend(extra_snippets(census, rnd))
    ext_forms, ext_unsupported = extended_forms(census)
    for form, fdesc in ext_forms.items():
        for ek, e in fdesc["encodings"].items():
            for sn in snippets_for_encoding(form, fdesc, ek, e, rnd):
                sn.extra["extended"] = True
                snips.append(sn)
    lifter = Lifter(_StubMod())
    # --live-random (xlift --opt flags): each snippet gets a random set of flags live after it; flags outside the
    # set are not compared (they may be stale by design), everything else is compared as usual
    live_rnd = random.Random(seed + 2) if "--live-random" in args else None
    dead_bits = []
    blob = b""
    offs = []
    allcases = []
    clines = ['/* GENERATED by experiments/xrt/tests/insn_diff/gen.py from synthesized test snippets. */',
              '#include "xrt.h"', ""]
    meta = []
    for idx, sn in enumerate(snips):
        cases = vectors(sn, scale)
        offs.append((len(blob), len(sn.code)))
        blob += sn.code
        for c in cases:
            allcases.append((idx, c))
        live_end = None
        if live_rnd is not None:
            live_end = frozenset(f for f in sorted(FLAGS) if live_rnd.random() < 0.5)
        dead_bits.append(sum(b for f, b in FLAG_BITS.items() if live_end is not None and f not in live_end))
        clines.extend(lift_snippet(sn, idx, lifter, live_end))
        d = sn.meta()
        d["id"] = idx
        if live_end is not None:
            d["live_flags"] = sorted(live_end)
        d["ncases"] = len(cases)
        if sn.family in ("x87", "x87seq"):
            d["x87"] = dict(zip(("pushes", "pops", "need", "cc", "mode"), x87_props(sn.insns[0])))
        if sn.family == "x87seq":
            d["x87"]["cc"] = C0 | C2 | C3
        meta.append(d)
    clines.append("const XrtFn id_fns[] = {")
    clines.extend(f"    s_{i}," for i in range(len(snips)))
    clines.append("};")
    clines.append(f"const uint32_t id_nfns = {len(snips)}u;")
    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "id_lifted.c"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(clines) + "\n")
    with open(os.path.join(BUILD, "cases.bin"), "wb") as f:
        f.write(b"XDIN" + struct.pack("<III", 1, len(snips), len(allcases)))
        for o, ln in offs:
            f.write(struct.pack("<II", o, ln))
        f.write(struct.pack("<I", len(blob)) + blob)
        for idx, c in allcases:
            f.write(c.pack(idx))
    with open(os.path.join(BUILD, "expect.bin"), "wb") as f:
        for idx, c in allcases:
            f.write(struct.pack("<HHB", c.fmask & ~dead_bits[idx] & 0xFFFF, c.ccmask, c.flags))
    with open(os.path.join(BUILD, "snippets.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"seed": seed, "scale": scale, "snippets": meta, "extended_unsupported": ext_unsupported},
                  f, indent=0)
    print(f"gen: {len(snips)} snippets, {len(allcases)} cases")


if __name__ == "__main__":
    main()
