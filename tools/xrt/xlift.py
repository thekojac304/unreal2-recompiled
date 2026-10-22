"""xlift - static x86-32 (MSVC 7.0) -> C translator for whole modules (X1 translated runtime).

Each discovered guest function becomes `void f_<va>(CPU* c)` (experiments/xrt/runtime/xrt.h).
Guest registers, flags, x87 state and the guest stack are explicit; guest memory is the
runtime's flat 32-bit address space. Control flow:
  direct call    -> CALL(): push return address, call f_<target>, verify the popped return address
  indirect call  -> ICALL(): runtime dispatch (xrt_icall), fatal diagnostic if the target is unknown
  import call    -> through the IAT value written by the runtime loader (same dispatcher)
  jump table     -> switch over the dword loaded from the table (default: fatal diagnostic)
  other indirect jmp -> xrt_ijmp (tail dispatch)
  fs: segment    -> guest TEB of the executing guest thread (c->fs_base); SEH registration
                    records are ordinary guest-memory writes and are preserved as such
Anything the translator does not implement becomes xrt_trap(...) at that instruction: it stops
execution with the address, the instruction and guest diagnostics if (and only if) it is reached.
MMX/SSE instructions are always traps: the runtime's CPUID policy (xrt_cpu.c) reports no MMX/SSE
so original scalar paths are selected; reaching a vector instruction anyway is fatal.

x87 register-form arithmetic is decoded from the opcode bytes (Intel SDM tables), not from the
disassembler mnemonic, because the DC/DE register forms of fsub/fsubr and fdiv/fdivr are the
classic place where disassemblers disagree.

Evidence instrumentation (tools/xrt/marks.json, see the comment there): a mark emits XRT_MARK() before the
instruction at its address; a watch emits xrt_watch_store() after every instruction that stores to the watched
global through a constant address. Both only record; they never change guest state.

Usage:
  python -I tools/xrt/xlift.py <module> --out <dir> [--chunk 250] [--only 0xVA,...] [--marks FILE|--no-marks]
Outputs <dir>/<stem>_NNN.c, <stem>_protos.h, <stem>_table.c and <stem>_meta.json.
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
ALIAS = {"z": "e", "nz": "ne", "c": "b", "nc": "ae", "nae": "b", "nb": "ae", "na": "be", "nbe": "a",
         "nge": "l", "nl": "ge", "ng": "le", "nle": "g", "pe": "p", "po": "np"}
# D9 /reg=5,7 register forms, by ModRM byte (Intel SDM): constants and transcendental helpers
X87_CONST_BY_MODRM = {0xE8: "1.0", 0xE9: "XRT_L2T", 0xEA: "XRT_L2E", 0xEB: "XRT_PI", 0xEC: "XRT_LG2",
                      0xED: "XRT_LN2", 0xEE: "0.0"}
X87_HELPER_BY_MODRM = {0xF0: "xrt_f2xm1", 0xF1: "xrt_fyl2x", 0xF2: "xrt_fptan", 0xF3: "xrt_fpatan",
                       0xFA: "xrt_fsqrt", 0xFD: "xrt_fscale", 0xFE: "xrt_fsin", 0xFF: "xrt_fcos"}
STRING_OPS = {"movs", "stos", "cmps", "scas", "lods"}
X87_STORES = {"fst", "fstp", "fist", "fistp", "fisttp", "fnstsw", "fstsw", "fnstcw", "fstcw", "fnstenv", "fstenv",
              "fnsave", "fsave", "fbstp"}
CAPTURE_REGS = {"eax": 0, "ecx": 1, "edx": 2, "ebx": 3, "esp": 4, "ebp": 5, "esi": 6, "edi": 7}
DEFAULT_MARKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marks.json")
SIZE_SUFFIX = {"b": 1, "w": 2, "d": 4}


class Unsupported(Exception):
    pass


def cond_of(suffix):
    suffix = ALIAS.get(suffix, suffix)
    return COND.get(suffix)


def is_simd(md, ins):
    for op in ins.operands:
        if op.type == X.X86_OP_REG:
            n = md.reg_name(op.reg)
            if n.startswith("mm") or n.startswith("xmm"):
                return True
    m = ins.mnemonic
    return m in ("emms", "femms", "sfence", "lfence", "mfence") or m.startswith("prefetch")


def mask_hex(bits):
    return f"0x{(1 << bits) - 1:x}u"


class Lifter:
    def __init__(self, mod, marks=(), watches=(), stem="m"):
        self.mod = mod
        self.img = mod.img
        self.md = mod.md
        self.traps = collections.Counter()
        self.trap_sites = []
        self.stem = stem
        self.marks = list(marks)          # [(va, name, capture_reg_index or -1)]
        self.marks_at = collections.defaultdict(list)
        for k, (va, _, _) in enumerate(self.marks):
            self.marks_at[va].append(k)
        self.marks_emitted = set()
        self.watches = list(watches)      # [(addr, size, name)]
        self.watch_sites = collections.defaultdict(set)   # watch index -> store sites

    def watch_store_stmts(self, ins):
        """xrt_watch_store() calls for an instruction that stores to a watched global through a constant address."""
        out = []
        if not self.watches:
            return out
        for op in ins.operands:
            if op.type != X.X86_OP_MEM or op.mem.base or op.mem.index or op.mem.segment:
                continue
            if not (op.access & 2) and ins.mnemonic not in X87_STORES:
                continue
            a, n = op.mem.disp & 0xFFFFFFFF, max(op.size, 1)
            for w, (wa, wn, _) in enumerate(self.watches):
                if a < wa + wn and wa < a + n:
                    self.watch_sites[w].add(ins.address)
                    out.append(f"xrt_watch_store(c, &xrt_watches_{self.stem}[{w}], 0x{ins.address:x}u);")
        return out

    # ------------------------------------------------------------------ operands
    def rn(self, op):
        return self.md.reg_name(op.reg)

    def addr(self, op, with_segment=True):
        mm = op.mem
        parts = []
        seg = self.md.reg_name(mm.segment) if mm.segment else None
        if seg == "fs":
            if with_segment:
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

    def read(self, op, bits=None):
        """C expression (uint32_t, zero-extended) for an operand; immediates are masked to `bits`."""
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
            b = bits or op.size * 8 or 32
            return f"0x{op.imm & ((1 << b) - 1):x}u"
        if op.type == X.X86_OP_MEM:
            fn = {1: "rd8", 2: "rd16", 4: "rd32"}.get(op.size)
            if not fn:
                raise Unsupported(f"memory operand size {op.size}")
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

    def sti(self, op):
        n = self.rn(op)
        m = re.match(r"st\((\d)\)", n)
        if not m:
            raise Unsupported(f"x87 operand {n}")
        return int(m.group(1))

    def iat_name(self, op):
        if op.type == X.X86_OP_MEM and not op.mem.base and not op.mem.index and not op.mem.segment:
            hit = self.img.iat.get(op.mem.disp & 0xFFFFFFFF)
            if hit:
                return f"{hit[0]}!{hit[1]}"
        return None

    # ------------------------------------------------------------------ instruction translation
    def lift_insn(self, ins, fn):
        """Return C statements for one instruction. `fn` is the discover.Function being lifted."""
        m, ops, va = ins.mnemonic, ins.operands, ins.address
        if m.startswith("lock "):
            m = m[5:]       # capstone spells the prefix into the mnemonic ("lock add"); ins.prefix keeps it
        nxt = va + ins.size
        o = []
        bits = ops[0].size * 8 if ops and ops[0].type != X.X86_OP_IMM else 32
        if is_simd(self.md, ins):
            raise Unsupported(f"MMX/SSE instruction (guest CPUID policy reports no MMX/SSE)")
        prefix_rep = m.startswith(("rep ", "repe ", "repne ", "repz ", "repnz "))
        base_m = m.split(" ", 1)[1] if prefix_rep else m
        if ins.prefix[0] == 0xF0 and m not in ("add", "sub", "inc", "dec", "and", "or", "xor", "xchg", "xadd",
                                               "cmpxchg", "neg", "not", "adc", "sbb"):
            raise Unsupported("lock prefix on unexpected instruction")
        # lock-prefixed read-modify-write is atomic with respect to other guest threads because only
        # the thread holding the runtime's execution baton runs translated code (xrt_thread.c).

        if m == "mov":
            if ops[1].type == X.X86_OP_REG and self.rn(ops[1]) in ("es", "ds", "ss", "cs", "fs", "gs"):
                raise Unsupported("segment register read")
            if ops[0].type == X.X86_OP_REG and self.rn(ops[0]) in ("es", "ds", "ss", "cs", "fs", "gs"):
                raise Unsupported("segment register write")
            o.append(self.write(ops[0], self.read(ops[1], bits)))
        elif m == "movzx":
            o.append(self.write(ops[0], self.read(ops[1])))
        elif m == "movsx":
            sb = ops[1].size * 8
            o.append(self.write(ops[0], f"(uint32_t)(int32_t)(int{sb}_t)({self.read(ops[1])})"))
        elif m == "lea":
            if ops[0].size != 4:
                raise Unsupported("lea with 16-bit destination")
            o.append(self.write(ops[0], self.addr(ops[1], with_segment=False)))
        elif m in ("add", "sub", "cmp"):
            a, b = self.read(ops[0]), self.read(ops[1], bits)
            sign = "+" if m == "add" else "-"
            o.append(f"{{ uint32_t a_ = {a}, b_ = {b}; uint32_t r_ = (a_ {sign} b_) & {mask_hex(bits)}; "
                     f"fl_{'add' if m == 'add' else 'sub'}(c, a_, b_, r_, {bits});")
            if m != "cmp":
                o.append("  " + self.write(ops[0], "r_"))
            o.append("}")
        elif m in ("adc", "sbb"):
            a, b = self.read(ops[0]), self.read(ops[1], bits)
            msk = mask_hex(bits)
            if m == "adc":
                o.append(f"{{ uint64_t a_ = {a}, b_ = {b}; uint64_t w_ = a_ + b_ + c->cf; uint32_t r_ = (uint32_t)(w_ & {msk});")
                o.append(f"  c->cf = (uint32_t)(w_ >> {bits}) & 1u; c->of = msb((uint32_t)((a_ ^ r_) & (b_ ^ r_)), {bits});")
            else:
                o.append(f"{{ uint64_t a_ = {a}, b_ = {b}; uint32_t r_ = (uint32_t)((a_ - b_ - c->cf) & {msk});")
                o.append(f"  c->of = msb((uint32_t)((a_ ^ b_) & (a_ ^ r_)), {bits}); c->cf = a_ < b_ + c->cf;")
            o.append(f"  fl_szp(c, r_, {bits}); {self.write(ops[0], 'r_')} }}")
        elif m in ("and", "or", "xor", "test"):
            a, b = self.read(ops[0]), self.read(ops[1], bits)
            cop = {"and": "&", "test": "&", "or": "|", "xor": "^"}[m]
            o.append(f"{{ uint32_t r_ = ({a} {cop} {b}) & {mask_hex(bits)}; fl_logic(c, r_, {bits});")
            if m != "test":
                o.append("  " + self.write(ops[0], "r_"))
            o.append("}")
        elif m in ("inc", "dec"):
            a = self.read(ops[0])
            sign = "+" if m == "inc" else "-"
            fl = "fl_add" if m == "inc" else "fl_sub"
            o.append(f"{{ uint32_t a_ = {a}, cf_ = c->cf; uint32_t r_ = (a_ {sign} 1u) & {mask_hex(bits)}; "
                     f"{fl}(c, a_, 1u, r_, {bits}); c->cf = cf_; {self.write(ops[0], 'r_')} }}")
        elif m == "not":
            o.append(self.write(ops[0], f"~{self.read(ops[0])}"))
        elif m == "neg":
            a = self.read(ops[0])
            o.append(f"{{ uint32_t a_ = {a}; uint32_t r_ = (0u - a_) & {mask_hex(bits)}; fl_sub(c, 0u, a_, r_, {bits}); "
                     f"{self.write(ops[0], 'r_')} }}")
        elif m in ("shl", "sal", "shr", "sar", "rol", "ror"):
            o.extend(self.lift_shift(m, ops, bits))
        elif m in ("shld", "shrd"):
            if bits != 32:
                raise Unsupported(f"{m} with {bits}-bit operands")
            d, s = self.read(ops[0]), self.read(ops[1])
            cnt = self.read(ops[2], 8)
            o.append(f"{{ uint32_t n_ = ({cnt}) & 31u; if (n_) {{ uint32_t d_ = {d}, s_ = {s}, r_, cf_;")
            if m == "shld":
                o.append("  r_ = (d_ << n_) | (s_ >> (32u - n_)); cf_ = (d_ >> (32u - n_)) & 1u;")
            else:
                o.append("  r_ = (d_ >> n_) | (s_ << (32u - n_)); cf_ = (d_ >> (n_ - 1u)) & 1u;")
            o.append(f"  fl_logic(c, r_, 32); c->cf = cf_; c->of = msb(r_ ^ d_, 32); {self.write(ops[0], 'r_')} }} }}")
        elif m == "imul":
            o.extend(self.lift_imul(ops, bits))
        elif m == "mul":
            if len(ops) != 1:
                raise Unsupported("mul form")
            src = self.read(ops[0])
            if bits == 32:
                o.append(f"{{ uint64_t p_ = (uint64_t)c->r[0] * (uint64_t)({src}); c->r[0] = (uint32_t)p_; "
                         f"c->r[2] = (uint32_t)(p_ >> 32); c->cf = c->of = c->r[2] != 0; }}")
            elif bits == 8:
                o.append(f"{{ uint32_t p_ = (c->r[0] & 0xFFu) * ({src}); c->r[0] = (c->r[0] & 0xFFFF0000u) | (p_ & 0xFFFFu); "
                         f"c->cf = c->of = (p_ >> 8) != 0; }}")
            else:
                raise Unsupported(f"mul {bits}-bit")
        elif m in ("div", "idiv"):
            if len(ops) != 1 or bits != 32:
                raise Unsupported(f"{m} {bits}-bit")
            src = self.read(ops[0])
            if m == "div":
                o.append(f"{{ uint32_t d_ = {src}; uint64_t n_ = ((uint64_t)c->r[2] << 32) | c->r[0]; uint64_t q_; "
                         f"if (!d_) xrt_div0(c, 0x{va:x}u); q_ = n_ / d_; if (q_ > 0xFFFFFFFFull) xrt_div0(c, 0x{va:x}u); "
                         f"c->r[2] = (uint32_t)(n_ % d_); c->r[0] = (uint32_t)q_; }}")
            else:
                o.append(f"{{ int32_t d_ = (int32_t){src}; int64_t n_ = (int64_t)(((uint64_t)c->r[2] << 32) | c->r[0]); int64_t q_; "
                         f"if (!d_ || (d_ == -1 && n_ == INT64_MIN)) xrt_div0(c, 0x{va:x}u); q_ = n_ / d_; "
                         f"if (q_ > 2147483647LL || q_ < -2147483648LL) xrt_div0(c, 0x{va:x}u); "
                         f"c->r[2] = (uint32_t)(int32_t)(n_ % d_); c->r[0] = (uint32_t)(int32_t)q_; }}")
        elif m == "cdq":
            o.append("c->r[2] = (uint32_t)((int32_t)c->r[0] >> 31);")
        elif m == "cwde":
            o.append("c->r[0] = (uint32_t)(int32_t)(int16_t)(c->r[0] & 0xFFFFu);")
        elif m == "cbw":
            o.append("c->r[0] = (c->r[0] & 0xFFFF0000u) | ((uint32_t)(int16_t)(int8_t)(c->r[0] & 0xFFu) & 0xFFFFu);")
        elif m == "cwd":
            o.append("c->r[2] = (c->r[2] & 0xFFFF0000u) | (((c->r[0] >> 15) & 1u) ? 0xFFFFu : 0u);")
        elif m == "push":
            if ops[0].size != 4:
                raise Unsupported("16-bit push")
            o.append(f"{{ uint32_t v_ = {self.read(ops[0], 32)}; push32(c, v_); }}")
        elif m == "pop":
            if ops[0].size != 4:
                raise Unsupported("16-bit pop")
            o.append(f"{{ uint32_t v_ = pop32(c); {self.write(ops[0], 'v_')} }}")
        elif m == "xchg":
            if ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_REG and ops[0].reg == ops[1].reg:
                pass
            else:
                o.append(f"{{ uint32_t a_ = {self.read(ops[0])}, b_ = {self.read(ops[1])}; "
                         f"{self.write(ops[0], 'b_')} {self.write(ops[1], 'a_')} }}")
        elif m == "nop" or m in ("fwait", "wait"):
            pass
        elif m == "leave":
            o.append("c->r[4] = c->r[5]; c->r[5] = pop32(c);")
        elif m == "cld":
            o.append("c->df = 0;")
        elif m == "std":
            o.append("c->df = 1;")
        elif m == "clc":
            o.append("c->cf = 0;")
        elif m == "stc":
            o.append("c->cf = 1;")
        elif m == "cmc":
            o.append("c->cf ^= 1u;")
        elif base_m[:-1] in STRING_OPS and base_m[-1] in SIZE_SUFFIX:
            o.extend(self.lift_string(m, base_m, ins))
        elif m.startswith("set") and cond_of(m[3:]):
            o.append(self.write(ops[0], f"({cond_of(m[3:])}) ? 1u : 0u"))
        elif m.startswith("cmov") and cond_of(m[4:]):
            # the source is read even when the condition is false (as on hardware)
            o.append(f"{{ uint32_t v_ = {self.read(ops[1])}; if ({cond_of(m[4:])}) {{ {self.write(ops[0], 'v_')} }} }}")
        elif m == "bswap":
            o.append(f"{{ uint32_t v_ = {self.read(ops[0])}; {self.write(ops[0], '(v_ >> 24) | ((v_ >> 8) & 0xFF00u) | ((v_ << 8) & 0xFF0000u) | (v_ << 24)')} }}")
        elif m == "rdtsc":
            o.append("xrt_rdtsc(c);")
        elif m == "cpuid":
            o.append("xrt_cpuid(c);")
        elif m in ("int3", "hlt", "ud2", "int", "into"):
            raise Unsupported(f"{m} executed")
        elif m.startswith("f"):
            o.extend(self.lift_x87(ins))
        else:
            # control transfer is handled by lift_function; anything else is unsupported
            raise Unsupported(f"instruction {m}")
        return o

    def lift_shift(self, m, ops, bits):
        a = self.read(ops[0])
        cnt = "1u" if len(ops) == 1 else self.read(ops[1], 8)
        msk = mask_hex(bits)
        o = [f"{{ uint32_t n_ = ({cnt}) & 31u; if (n_) {{ uint32_t a_ = {a}, r_;"]
        if m in ("shl", "sal"):
            o.append(f"  uint32_t cf_ = (uint32_t)(((uint64_t)a_ << n_ >> {bits}) & 1u); r_ = (uint32_t)(((uint64_t)a_ << n_) & {msk});")
            o.append(f"  fl_logic(c, r_, {bits}); c->cf = cf_; c->of = msb(r_, {bits}) ^ cf_;")
        elif m == "shr":
            o.append(f"  uint32_t cf_ = (uint32_t)(((uint64_t)a_ >> (n_ - 1u)) & 1u); r_ = (uint32_t)((uint64_t)a_ >> n_);")
            o.append(f"  fl_logic(c, r_, {bits}); c->cf = cf_; c->of = msb(a_, {bits});")
        elif m == "sar":
            o.append(f"  int64_t s_ = (int64_t)(int32_t)(a_ << (32 - {bits})) >> (32 - {bits});")
            o.append(f"  uint32_t cf_ = (uint32_t)((s_ >> (n_ - 1u)) & 1); r_ = (uint32_t)(s_ >> n_) & {msk};")
            o.append(f"  fl_logic(c, r_, {bits}); c->cf = cf_; c->of = 0;")
        elif m == "rol":
            o.append(f"  uint32_t k_ = n_ % {bits}u; r_ = k_ ? ((a_ << k_) | (a_ >> ({bits}u - k_))) & {msk} : a_;")
            o.append(f"  c->cf = r_ & 1u; c->of = msb(r_, {bits}) ^ c->cf;")
        else:
            o.append(f"  uint32_t k_ = n_ % {bits}u; r_ = k_ ? ((a_ >> k_) | (a_ << ({bits}u - k_))) & {msk} : a_;")
            o.append(f"  c->cf = msb(r_, {bits}); c->of = msb(r_, {bits}) ^ msb(r_ << 1, {bits});")
        o.append(f"  {self.write(ops[0], 'r_')} }} }}")
        return o

    def lift_imul(self, ops, bits):
        if len(ops) == 1:
            src = self.read(ops[0])
            if bits == 32:
                return [f"{{ int64_t p_ = (int64_t)(int32_t)c->r[0] * (int64_t)(int32_t)({src}); c->r[0] = (uint32_t)p_; "
                        f"c->r[2] = (uint32_t)((uint64_t)p_ >> 32); c->cf = c->of = (p_ != (int64_t)(int32_t)c->r[0]); }}"]
            if bits == 8:
                return [f"{{ int32_t p_ = (int32_t)(int8_t)(c->r[0] & 0xFFu) * (int32_t)(int8_t)({src}); "
                        f"c->r[0] = (c->r[0] & 0xFFFF0000u) | ((uint32_t)p_ & 0xFFFFu); c->cf = c->of = (p_ != (int32_t)(int8_t)p_); }}"]
            raise Unsupported(f"one-operand imul {bits}-bit")
        if len(ops) == 2:
            a, b = self.read(ops[0]), self.read(ops[1])
        else:
            a, b = self.read(ops[1]), self.read(ops[2], bits)
        if bits == 32:
            return [f"{{ int64_t p_ = (int64_t)(int32_t)({a}) * (int64_t)(int32_t)({b}); uint32_t r_ = (uint32_t)p_; "
                    f"c->cf = c->of = (p_ != (int64_t)(int32_t)r_); {self.write(ops[0], 'r_')} }}"]
        if bits == 16:
            return [f"{{ int32_t p_ = (int32_t)(int16_t)({a}) * (int32_t)(int16_t)({b}); uint32_t r_ = (uint32_t)p_ & 0xFFFFu; "
                    f"c->cf = c->of = (p_ != (int32_t)(int16_t)r_); {self.write(ops[0], 'r_')} }}"]
        raise Unsupported(f"imul {bits}-bit")

    def lift_string(self, m, base_m, ins):
        op, size = base_m[:-1], SIZE_SUFFIX[base_m[-1]]
        bits = size * 8
        rd, wr = {1: ("rd8", "wr8"), 2: ("rd16", "wr16"), 4: ("rd32", "wr32")}[size]
        acc = {1: "(c->r[0] & 0xFFu)", 2: "(c->r[0] & 0xFFFFu)", 4: "c->r[0]"}[size]
        step = f"(c->df ? (uint32_t)-{size} : {size}u)"
        rep = m.split(" ", 1)[0] if " " in m else None
        if op == "stos":
            body = f"{wr}(c->r[7], ({'uint8_t' if size == 1 else 'uint16_t' if size == 2 else 'uint32_t'}){acc}); c->r[7] += st_;"
        elif op == "movs":
            body = f"{wr}(c->r[7], {rd}(c->r[6])); c->r[6] += st_; c->r[7] += st_;"
        elif op == "lods":
            if rep:
                raise Unsupported("rep lods")
            body = {1: "c->r[0] = (c->r[0] & 0xFFFFFF00u) | rd8(c->r[6]);",
                    2: "c->r[0] = (c->r[0] & 0xFFFF0000u) | rd16(c->r[6]);", 4: "c->r[0] = rd32(c->r[6]);"}[size] + " c->r[6] += st_;"
        elif op == "cmps":
            body = (f"{{ uint32_t a_ = {rd}(c->r[6]), b_ = {rd}(c->r[7]); c->r[6] += st_; c->r[7] += st_; "
                    f"fl_sub(c, a_, b_, (a_ - b_) & {mask_hex(bits)}, {bits}); }}")
        else:  # scas
            body = (f"{{ uint32_t b_ = {rd}(c->r[7]); c->r[7] += st_; "
                    f"fl_sub(c, {acc}, b_, ({acc} - b_) & {mask_hex(bits)}, {bits}); }}")
        if rep is None:
            return [f"{{ uint32_t st_ = {step}; {body} }}"]
        if op in ("cmps", "scas"):
            stop = {"repe": "!c->zf", "repz": "!c->zf", "rep": "!c->zf", "repne": "c->zf", "repnz": "c->zf"}[rep]
            return [f"{{ uint32_t st_ = {step}; while (c->r[1]) {{ {body} c->r[1]--; if ({stop}) break; }} }}"]
        if rep != "rep":
            raise Unsupported(f"{rep} with {op}")
        return [f"{{ uint32_t st_ = {step}; while (c->r[1]) {{ {body} c->r[1]--; }} }}"]

    # ------------------------------------------------------------------ x87
    def x87_bytes(self, ins):
        """(opcode, modrm) of an x87 escape instruction, skipping legacy prefixes."""
        b = bytes(ins.bytes)
        i = 0
        while b[i] in (0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0x66, 0x67, 0x9B, 0xF0, 0xF2, 0xF3):
            i += 1
        if not 0xD8 <= b[i] <= 0xDF:
            return None, None
        return b[i], b[i + 1]

    def lift_x87(self, ins):
        m, ops = ins.mnemonic, ins.operands
        opc, modrm = self.x87_bytes(ins)
        if opc is None:
            raise Unsupported(f"instruction {m}")
        mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
        o = []
        mem = ops[0] if ops and ops[0].type == X.X86_OP_MEM else None

        def memload(op, kind):
            a = self.addr(op)
            if kind == "f":
                if op.size == 4:
                    return f"(double)rdf32({a})"
                if op.size == 8:
                    return f"rdf64({a})"
                raise Unsupported("80-bit memory operand")
            return {2: f"(double)(int16_t)rd16({a})", 4: f"(double)(int32_t)rd32({a})", 8: f"(double)(int64_t)rd64({a})"}[op.size]

        def arith(dst, lhs, rhs, r):
            # r: 0 add 1 mul 4 sub 5 subr 6 div 7 divr, with dst = lhs op rhs
            if r == 0:
                return f"{dst} = {lhs} + {rhs};"
            if r == 1:
                return f"{dst} = {lhs} * {rhs};"
            if r == 4:
                return f"{dst} = {lhs} - {rhs};"
            if r == 5:
                return f"{dst} = {rhs} - {lhs};"
            if r == 6:
                return f"{dst} = {lhs} / {rhs};"
            if r == 7:
                return f"{dst} = {rhs} / {lhs};"
            raise AssertionError

        # ---- arithmetic and compare families (D8, DC, DA, DE) decoded from the encoding
        if opc in (0xD8, 0xDC, 0xDA, 0xDE) and not (opc == 0xDA and mod == 3) and not (opc == 0xDE and mod == 3 and reg in (2, 3) and modrm != 0xD9):
            if mod != 3:
                kind = "f" if opc in (0xD8, 0xDC) else "i"
                src = memload(mem, kind)
                if reg in (2, 3):
                    o.append(f"fcompare(c, *ST(c, 0), {src});")
                    if reg == 3:
                        o.append("fpop(c);")
                else:
                    o.append(f"{{ double m_ = {src}; {arith('*ST(c, 0)', '*ST(c, 0)', 'm_', reg)} }}")
                return o
            i = rm
            if opc == 0xD8:
                if reg in (2, 3):
                    o.append(f"fcompare(c, *ST(c, 0), *ST(c, {i}));")
                    if reg == 3:
                        o.append("fpop(c);")
                else:
                    o.append(arith("*ST(c, 0)", "*ST(c, 0)", f"*ST(c, {i})", reg))
                return o
            if opc == 0xDE and modrm == 0xD9:          # fcompp
                o.append("fcompare(c, *ST(c, 0), *ST(c, 1)); fpop(c); fpop(c);")
                return o
            if reg in (2, 3):
                raise Unsupported(f"x87 encoding {opc:02x} {modrm:02x}")
            # DC / DE register forms: ST(i) = ST(i) op ST(0); for sub/div the reg field is swapped:
            # reg 4 = FSUBR (ST(i) = ST(0) - ST(i)), 5 = FSUB, 6 = FDIVR, 7 = FDIV (Intel SDM)
            r = {0: 0, 1: 1, 4: 5, 5: 4, 6: 7, 7: 6}[reg]
            o.append(arith(f"*ST(c, {i})", f"*ST(c, {i})", "*ST(c, 0)", r))
            if opc == 0xDE:
                o.append("fpop(c);")
            return o
        # ---- loads, stores, constants, misc
        if opc == 0xD9:
            if mod != 3:
                a = self.addr(mem)
                if reg == 0:
                    o.append(f"fpush(c, (double)rdf32({a}));")
                elif reg in (2, 3):
                    o.append(f"wrf32({a}, (float)*ST(c, 0));")
                    if reg == 3:
                        o.append("fpop(c);")
                elif reg == 5:
                    o.append(f"xrt_fldcw(c, rd16({a}));")
                elif reg == 7:
                    o.append(f"wr16({a}, c->fcw);")
                else:
                    raise Unsupported(f"x87 environment instruction {m}")
                return o
            if reg == 0:
                o.append(f"{{ double v_ = *ST(c, {rm}); fpush(c, v_); }}")
            elif reg == 1:
                o.append(f"{{ double t_ = *ST(c, 0); *ST(c, 0) = *ST(c, {rm}); *ST(c, {rm}) = t_; }}")
            elif modrm == 0xD0:
                pass                                      # fnop
            elif modrm == 0xE0:
                o.append("*ST(c, 0) = -*ST(c, 0);")
            elif modrm == 0xE1:
                o.append("*ST(c, 0) = fabs(*ST(c, 0));")
            elif modrm == 0xE4:
                o.append("fcompare(c, *ST(c, 0), 0.0);")    # ftst
            elif modrm in X87_CONST_BY_MODRM:
                o.append(f"fpush(c, {X87_CONST_BY_MODRM[modrm]});")
            elif modrm == 0xFC:
                o.append("*ST(c, 0) = xrt_fround(c, *ST(c, 0));")
            elif modrm in X87_HELPER_BY_MODRM:
                o.append(f"{X87_HELPER_BY_MODRM[modrm]}(c);")
            else:
                raise Unsupported(f"x87 instruction {m}")
            return o
        if opc == 0xDD:
            if mod != 3:
                a = self.addr(mem)
                if reg == 0:
                    o.append(f"fpush(c, rdf64({a}));")
                elif reg in (2, 3):
                    o.append(f"wrf64({a}, *ST(c, 0));")
                    if reg == 3:
                        o.append("fpop(c);")
                elif reg == 7:
                    o.append(f"wr16({a}, fstatus(c));")
                else:
                    raise Unsupported(f"x87 instruction {m}")
                return o
            if reg in (2, 3):                              # fst/fstp st(i)
                o.append(f"*ST(c, {rm}) = *ST(c, 0);")
                if reg == 3:
                    o.append("fpop(c);")
            elif reg in (4, 5):                            # fucom/fucomp st(i)
                o.append(f"fcompare(c, *ST(c, 0), *ST(c, {rm}));")
                if reg == 5:
                    o.append("fpop(c);")
            else:
                raise Unsupported(f"x87 instruction {m}")
            return o
        if opc == 0xDB:
            if mod != 3:
                a = self.addr(mem)
                if reg == 0:
                    o.append(f"fpush(c, (double)(int32_t)rd32({a}));")
                elif reg in (2, 3):
                    o.append(f"wr32({a}, (uint32_t)xrt_fist32(c, *ST(c, 0)));")
                    if reg == 3:
                        o.append("fpop(c);")
                else:
                    raise Unsupported(f"x87 80-bit or unknown memory form {m}")
                return o
            if modrm == 0xE2:
                o.append("c->fsw &= 0x7F00u;")             # fnclex
            elif modrm == 0xE3:
                o.append("c->fcw = 0x037F; c->fsw = 0; c->top = 0;")   # fninit
            else:
                raise Unsupported(f"x87 instruction {m}")
            return o
        if opc == 0xDF:
            if mod != 3:
                a = self.addr(mem)
                if reg == 0:
                    o.append(f"fpush(c, (double)(int16_t)rd16({a}));")
                elif reg in (2, 3):
                    o.append(f"wr16({a}, (uint16_t)xrt_fist16(c, *ST(c, 0)));")
                    if reg == 3:
                        o.append("fpop(c);")
                elif reg == 5:
                    o.append(f"fpush(c, (double)(int64_t)rd64({a}));")
                elif reg == 7:
                    o.append(f"wr64({a}, (uint64_t)xrt_fist64(c, *ST(c, 0))); fpop(c);")
                else:
                    raise Unsupported(f"x87 BCD or unknown memory form {m}")
                return o
            if modrm == 0xE0:
                o.append("c->r[0] = (c->r[0] & 0xFFFF0000u) | fstatus(c);")   # fnstsw ax
            else:
                raise Unsupported(f"x87 instruction {m}")
            return o
        if opc == 0xDA and modrm == 0xE9:
            o.append("fcompare(c, *ST(c, 0), *ST(c, 1)); fpop(c); fpop(c);")   # fucompp
            return o
        raise Unsupported(f"x87 instruction {m}")

    # ------------------------------------------------------------------ functions
    def trap(self, va, why):
        self.traps[re.sub(r"0x[0-9a-f]+|\[[^\]]*\]|st\(\d\)", "X", why)[:80]] += 1
        self.trap_sites.append((va, why))
        why = why.replace("\\", "\\\\").replace('"', "'")
        return f'xrt_trap(c, 0x{va:x}u, "{why}");'

    def lift_function(self, fn, hit_index=None, stem=None):
        mod = self.mod
        order = sorted(fn.insns)
        labels = set()
        body = []
        # pass 1: emit, collecting goto targets
        for i, va in enumerate(order):
            ins = fn.insns[va]
            m, ops = ins.mnemonic, ins.operands
            nxt = va + ins.size
            text = f"{m} {ins.op_str}".strip()
            stmts = [f"XRT_MARK(&xrt_marks_{self.stem}[{k}]);   /* {self.marks[k][1]} */" for k in self.marks_at.get(va, ())]
            self.marks_emitted.update(self.marks_at.get(va, ()))
            stmts.append(f"P(0x{va:x}u); /* {text} */")
            terminal = False
            try:
                if m in JCC:
                    t = ops[0].imm & 0xFFFFFFFF
                    if t in fn.insns:
                        labels.add(t)
                        stmts.append(f"if ({cond_of(m[1:])}) goto L_{t:x};")
                    else:
                        stmts.append(f"if ({cond_of(m[1:])}) {{ {self.trap(va, f'branch to undecoded {t:#x}')} }}")
                elif m in ("loop", "loope", "loopne", "jecxz"):
                    t = ops[0].imm & 0xFFFFFFFF
                    if t not in fn.insns:
                        raise Unsupported(f"{m} to undecoded target")
                    labels.add(t)
                    if m == "jecxz":
                        stmts.append(f"if (c->r[1] == 0) goto L_{t:x};")
                    else:
                        extra = {"loop": "", "loope": " && c->zf", "loopne": " && !c->zf"}[m]
                        stmts.append(f"if (--c->r[1] != 0{extra}) goto L_{t:x};")
                elif m == "jmp":
                    terminal = True
                    if ops[0].type == X.X86_OP_IMM:
                        t = ops[0].imm & 0xFFFFFFFF
                        if t in fn.tails or (t not in fn.insns and t in mod.functions):
                            stmts.append(f"f_{t:x}(c); return;   /* tail call */")
                        elif t in fn.insns:
                            labels.add(t)
                            stmts.append(f"goto L_{t:x};")
                        else:
                            stmts.append(self.trap(va, f"jmp to undecoded {t:#x}"))
                    elif va in fn.jumptables:
                        targets = sorted(set(fn.jumptables[va]))
                        labels.update(targets)
                        cases = " ".join(f"case 0x{t:x}u: goto L_{t:x};" for t in targets)
                        stmts.append(f"switch ({self.read(ops[0])}) {{ {cases} default: "
                                     f"{self.trap(va, 'jump-table target outside the recovered table')} }}")
                    else:
                        imp = self.iat_name(ops[0])
                        note = f"   /* {imp} */" if imp else ""
                        stmts.append(f"xrt_ijmp(c, {self.read(ops[0])}, 0x{va:x}u); return;{note}")
                elif m == "call":
                    if ops[0].type == X.X86_OP_IMM:
                        t = ops[0].imm & 0xFFFFFFFF
                        if t in mod.functions:
                            stmts.append(f"CALL(f_{t:x}, 0x{nxt:x}u, 0x{va:x}u);")
                        else:
                            stmts.append(self.trap(va, f"call to undiscovered {t:#x}"))
                    else:
                        imp = self.iat_name(ops[0])
                        note = f"   /* {imp} */" if imp else ""
                        stmts.append(f"ICALL({self.read(ops[0])}, 0x{nxt:x}u, 0x{va:x}u);{note}")
                    if nxt not in fn.insns and nxt not in fn.fallthrough_into:
                        # discovery ended the block here: the callee is treated as noreturn
                        stmts.append(self.trap(nxt, "returned from a call treated as noreturn"))
                        terminal = True
                elif m in ("ret", "retn"):
                    n = ops[0].imm if ops else 0
                    stmts.append(f"RET({n}u);")
                    terminal = True
                else:
                    stmts.extend(self.lift_insn(ins, fn))
                    stmts.extend(self.watch_store_stmts(ins))
            except Unsupported as exc:
                stmts.append(self.trap(va, f"unsupported: {text}: {exc}"))
                terminal = True
            body.append((va, stmts))
            if not terminal and m not in ("int3", "hlt", "ud2"):
                if i + 1 < len(order) and order[i + 1] == nxt:
                    continue
                if nxt in fn.insns:
                    labels.add(nxt)
                    body.append((None, [f"goto L_{nxt:x};"]))
                elif nxt in fn.fallthrough_into or nxt in mod.functions:
                    body.append((None, [f"f_{nxt:x}(c); return;   /* falls through into the next function */"]))
                else:
                    body.append((None, [self.trap(nxt, "execution continued past decoded code")]))
        lines = [f"void f_{fn.entry:x}(CPU* c) {{", f"    XRT_ENTER(0x{fn.entry:x}u);"]
        if hit_index is not None:
            lines.append(f"    xrt_hits_{stem}[{hit_index}] = 1;")
        if order and order[0] != fn.entry:
            labels.add(fn.entry)
            lines.append(f"    goto L_{fn.entry:x};")
        for va, stmts in body:
            if va is not None and va in labels:
                lines.append(f"L_{va:x}:;")
            lines.extend("    " + s for s in stmts)
        lines.append("}")
        return lines


def load_marks(path, img):
    """Marks and watches for this module from the evidence-instrumentation file (see tools/xrt/marks.json)."""
    if not path:
        return [], [], None
    with open(path, "rb") as f:
        raw = f.read()
    cfg = json.loads(raw).get(img.name, {})

    def resolve(e, what):
        if "export" in e:
            if e["export"] not in img.exports:
                sys.exit(f"{path}: {img.name} has no export {e['export']} ({what} '{e['name']}')")
            return img.base + img.exports[e["export"]]
        return int(e["va"], 16)

    marks = []
    for e in cfg.get("marks", []):
        cap = e.get("capture")
        if cap is not None and cap not in CAPTURE_REGS:
            sys.exit(f"{path}: mark '{e['name']}': cannot capture {cap}")
        marks.append((resolve(e, "mark"), e["name"], CAPTURE_REGS[cap] if cap else -1))
    watches = [(resolve(e, "watch"), int(e.get("size", 4)), e["name"]) for e in cfg.get("watches", [])]
    for _, n, name in watches:
        if n not in (1, 2, 4):
            sys.exit(f"{path}: watch '{name}': size must be 1, 2 or 4")
    return marks, watches, hashlib.sha256(raw).hexdigest()


def c_string(s):
    if any(ch in s for ch in '"\\') or not s.isprintable() or not s.isascii():
        raise ValueError(f"mark/watch name must be printable ASCII without quotes or backslashes: {s!r}")
    return f'"{s}"'


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main():
    args = sys.argv[1:]
    path = args[0]
    out = args[args.index("--out") + 1]
    chunk = int(args[args.index("--chunk") + 1]) if "--chunk" in args else 250
    only = None
    if "--only" in args:
        only = {int(v, 16) for v in args[args.index("--only") + 1].split(",")}
    marks_path = None if "--no-marks" in args else (args[args.index("--marks") + 1] if "--marks" in args else DEFAULT_MARKS)
    os.makedirs(out, exist_ok=True)
    mod = Module(path).run()
    stem = re.sub(r"\W", "_", mod.img.name.rsplit(".", 1)[0])
    marks, watches, marks_digest = load_marks(marks_path, mod.img)
    lifter = Lifter(mod, marks, watches, stem)
    entries = sorted(e for e in mod.functions if only is None or e in only)
    conflicts = mod.conflicting()
    # regression guard (tracer finding): data recovered inside .text (jump tables and their byte
    # index tables) must never be treated as code.
    for a, b in mod.table_data:
        for e in entries:
            if a <= e < b:
                sys.exit(f"refusing: function entry {e:#x} lies inside .text data {a:#x}-{b:#x}")
    protos = [f"void f_{e:x}(CPU* c);" for e in sorted(mod.functions)]
    hdr = f"{stem}_protos.h"
    with open(os.path.join(out, hdr), "w", encoding="utf-8") as f:
        f.write(f"/* GENERATED by tools/xrt/xlift.py from {mod.img.name} - do not edit, do not distribute. */\n")
        f.write('#include "xrt.h"\n')
        f.write("\n".join(protos) + "\n")
        f.write(f"extern uint8_t xrt_hits_{stem}[];\n")
        f.write(f"extern XrtMark xrt_marks_{stem}[];\n")
        f.write(f"extern XrtWatchDef xrt_watches_{stem}[];\n")
    ninsns = 0
    files = []
    for k in range(0, len(entries), chunk):
        name = f"{stem}_{k // chunk:03d}.c"
        files.append(name)
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(f"/* GENERATED by tools/xrt/xlift.py from {mod.img.name} - do not edit, do not distribute. */\n")
            f.write(f'#include "{hdr}"\n\n')
            for j, e in enumerate(entries[k:k + chunk]):
                fn = mod.functions[e]
                ninsns += len(fn.insns)
                f.write("\n".join(lifter.lift_function(fn, k + j, stem)) + "\n\n")
    digest = sha256_file(path)
    tab = f"{stem}_table.c"
    with open(os.path.join(out, tab), "w", encoding="utf-8") as f:
        f.write(f"/* GENERATED by tools/xrt/xlift.py from {mod.img.name} - do not edit, do not distribute. */\n")
        f.write(f'#include "{hdr}"\n\n')
        f.write(f"static const XrtFuncEntry funcs[] = {{\n")
        for e in entries:
            f.write(f"    {{0x{e:x}u, f_{e:x}}},\n")
        f.write("};\n")
        f.write(f"uint8_t xrt_hits_{stem}[{max(len(entries), 1)}];\n")
        f.write(f"XrtMark xrt_marks_{stem}[{max(len(marks), 1)}] = {{\n")
        for va, name, cap in marks:
            f.write(f"    {{0x{va:x}u, {c_string(name)}, {cap}}},\n")
        f.write("" if marks else "    {0},\n")
        f.write("};\n")
        f.write(f"XrtWatchDef xrt_watches_{stem}[{max(len(watches), 1)}] = {{\n")
        for a, n, name in watches:
            f.write(f"    {{0x{a:x}u, {n}u, {c_string(name)}}},\n")
        f.write("" if watches else "    {0},\n")
        f.write("};\n")
        f.write(f'const XrtLiftedModule xrt_mod_{stem} = {{"{mod.img.name}", 0x{mod.img.base:x}u, 0x{mod.img.size:x}u, '
                f'"{digest}", funcs, {len(entries)}u, {len(lifter.trap_sites)}u, xrt_hits_{stem}, '
                f'xrt_marks_{stem}, {len(marks)}u, xrt_watches_{stem}, {len(watches)}u}};\n')
    if only is None:
        missing = [marks[k] for k in range(len(marks)) if k not in lifter.marks_emitted]
        if missing:
            sys.exit("marks at addresses that are not decoded instructions of any lifted function: "
                     + ", ".join(f"{va:#x} ({name})" for va, name, _ in missing))
    instrumentation = {
        "file": os.path.basename(marks_path) if marks_path else None, "sha256": marks_digest,
        "marks": [[hex(va), name] for va, name, _ in marks],
        "watches": [{"name": name, "addr": hex(a), "size": n,
                     "constant_address_store_sites": sorted(hex(v) for v in lifter.watch_sites[w])}
                    for w, (a, n, name) in enumerate(watches)]}
    meta = {"module": mod.img.name, "sha256": digest, "base": hex(mod.img.base), "functions": len(entries),
            "evidence_instrumentation": instrumentation,
            "instructions": ninsns, "static_traps": len(lifter.trap_sites), "trap_reasons": dict(lifter.traps.most_common()),
            "decode_conflicts": len(conflicts), "text_data_ranges": [[hex(a), hex(b)] for a, b in mod.table_data],
            "files": files + [tab, hdr], "discovery": mod.summary()}
    with open(os.path.join(out, f"{stem}_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"{mod.img.name}: {len(entries)} functions, {ninsns} instructions, {len(lifter.trap_sites)} static traps "
          f"-> {out} ({len(files)} chunks)")
    for r, n in lifter.traps.most_common(30):
        print(f"  {n:6}  {r}")


if __name__ == "__main__":
    main()
