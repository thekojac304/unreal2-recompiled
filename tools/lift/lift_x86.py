"""Function-level static lifter: 32-bit x86 (MSVC 7.0 code) -> portable C.

Feasibility experiment for Unreal II static recompilation. Supports the
integer + x87 instruction subset needed by the selected Core.dll routines and
FAILS LOUDLY on anything else (unsupported instruction, indirect jump, ...).
That failure mode is also used to measure coverage over whole modules.

Usage:
  python lift_x86.py <dll> --out lifted.c --func <export-substring>[=cname] ... [--import NAME=host_fn ...]
  python lift_x86.py <dll> --coverage [--limit N]      (try every exported function, report)
"""
import collections
import re
import struct
import sys

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone import x86 as X

REG32 = {"eax": 0, "ecx": 1, "edx": 2, "ebx": 3, "esp": 4, "ebp": 5, "esi": 6, "edi": 7}
REG16 = {"ax": 0, "cx": 1, "dx": 2, "bx": 3, "sp": 4, "bp": 5, "si": 6, "di": 7}
REG8L = {"al": 0, "cl": 1, "dl": 2, "bl": 3}
REG8H = {"ah": 0, "ch": 1, "dh": 2, "bh": 3}
JCC = {"je": "c->zf", "jne": "!c->zf", "jl": "(c->sf != c->of)", "jge": "(c->sf == c->of)",
       "jle": "(c->zf || c->sf != c->of)", "jg": "(!c->zf && c->sf == c->of)", "jb": "c->cf", "jae": "!c->cf",
       "jbe": "(c->cf || c->zf)", "ja": "(!c->cf && !c->zf)", "js": "c->sf", "jns": "!c->sf", "jp": "c->pf",
       "jnp": "!c->pf", "jo": "c->of", "jno": "!c->of"}


class Unsupported(Exception):
    pass


class Lifter:
    def __init__(self, path):
        self.pe = pefile.PE(path)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.image = self.pe.get_memory_mapped_image()
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.md.detail = True
        self.exports = {}
        for e in self.pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if e.name:
                self.exports[e.name.decode()] = self.base + e.address
        self.iat = {}
        for entry in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                self.iat[imp.address] = imp.name.decode() if imp.name else f"ord{imp.ordinal}"
        self.text = [s for s in self.pe.sections if s.Characteristics & 0x20000000]
        self.func_entries = set(self.exports.values())
        self._scan_call_targets()
        self.host_imports = {}

    def _scan_call_targets(self):
        for sec in self.text:
            code = self.image[sec.VirtualAddress:sec.VirtualAddress + sec.Misc_VirtualSize]
            va = self.base + sec.VirtualAddress
            for m in re.finditer(rb"\xE8(....)", code, re.S):
                t = (va + m.start() + 5 + struct.unpack("<i", m.group(1))[0]) & 0xFFFFFFFF
                if self.in_text(t):
                    self.func_entries.add(t)

    def in_text(self, va):
        for s in self.text:
            if self.base + s.VirtualAddress <= va < self.base + s.VirtualAddress + s.Misc_VirtualSize:
                return True
        return False

    def decode(self, va):
        off = va - self.base
        insns = list(self.md.disasm(self.image[off:off + 16], va, 1))
        if not insns:
            raise Unsupported(f"undecodable at {va:#x}")
        return insns[0]

    # ------------------------------------------------------------ discovery
    def discover(self, entry):
        insns, todo, targets, tails, callees = {}, [entry], set(), set(), set()
        while todo:
            va = todo.pop()
            while va not in insns:
                ins = self.decode(va)
                insns[va] = ins
                m = ins.mnemonic
                nxt = va + ins.size
                ops = ins.operands
                if m in JCC:
                    t = ops[0].imm
                    targets.add(t)
                    todo.append(t)
                    targets.add(nxt)
                elif m == "jmp":
                    if ops[0].type == X.X86_OP_MEM and ops[0].mem.base == 0 and ops[0].mem.index == 0 \
                            and (ops[0].mem.disp & 0xFFFFFFFF) in self.iat:
                        break   # import thunk: tail call into a host function
                    if ops[0].type != X.X86_OP_IMM:
                        raise Unsupported(f"indirect jmp at {va:#x}: {ins.op_str}")
                    t = ops[0].imm
                    if t in self.func_entries and t != entry:
                        tails.add(t)
                    else:
                        targets.add(t)
                        todo.append(t)
                    break
                elif m in ("ret", "retn"):
                    break
                elif m == "call":
                    if ops[0].type == X.X86_OP_IMM:
                        callees.add(ops[0].imm)
                    elif not (ops[0].type == X.X86_OP_MEM and ops[0].mem.base == 0 and ops[0].mem.index == 0
                              and (ops[0].mem.disp & 0xFFFFFFFF) in self.iat):
                        raise Unsupported(f"indirect call at {va:#x}: {ins.op_str}")
                elif m in ("int3", "hlt"):
                    raise Unsupported(f"{m} reached at {va:#x}")
                va = nxt
        return insns, targets, tails, callees

    # ------------------------------------------------------------ operands
    def addr(self, op):
        mm = op.mem
        if mm.segment != 0:
            raise Unsupported("segment override (fs:/gs:) - SEH/TLS access")
        parts = []
        if mm.base:
            parts.append(self.reg(self.md.reg_name(mm.base)))
        if mm.index:
            parts.append(f"{self.reg(self.md.reg_name(mm.index))}*{mm.scale}u")
        if mm.disp or not parts:
            parts.append(f"0x{mm.disp & 0xFFFFFFFF:x}u")
        return "(uint32_t)(" + " + ".join(parts) + ")"

    @staticmethod
    def reg(name):
        if name in REG32:
            return f"c->r[{REG32[name]}]"
        if name in REG16:
            return f"(c->r[{REG16[name]}] & 0xFFFFu)"
        if name in REG8L:
            return f"(c->r[{REG8L[name]}] & 0xFFu)"
        if name in REG8H:
            return f"((c->r[{REG8H[name]}] >> 8) & 0xFFu)"
        raise Unsupported(f"register {name}")

    def read(self, op, ins):
        if op.type == X.X86_OP_REG:
            return self.reg(self.md.reg_name(op.reg))
        if op.type == X.X86_OP_IMM:
            return f"0x{op.imm & self.mask(op.size * 8):x}u"
        if op.type == X.X86_OP_MEM:
            return {1: "rd8", 2: "rd16", 4: "rd32"}[op.size] + f"({self.addr(op)})"
        raise Unsupported(f"operand type in {ins.mnemonic} {ins.op_str}")

    def write(self, op, val):
        if op.type == X.X86_OP_REG:
            n = self.md.reg_name(op.reg)
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
            return {1: "wr8", 2: "wr16", 4: "wr32"}[op.size] + f"({self.addr(op)}, (uint{op.size * 8}_t)({val}));"
        raise Unsupported("write to non-lvalue")

    @staticmethod
    def mask(bits):
        return (1 << bits) - 1

    def sti(self, op):
        n = self.md.reg_name(op.reg)
        m = re.match(r"st\((\d)\)", n)
        if not m:
            raise Unsupported(f"x87 operand {n}")
        return int(m.group(1))

    # ------------------------------------------------------------ translation
    def lift_insn(self, ins, entry):
        m, ops, va = ins.mnemonic, ins.operands, ins.address
        nxt = va + ins.size
        o = []
        bits = ops[0].size * 8 if ops and ops[0].type != X.X86_OP_IMM else 32
        if m == "mov":
            o.append(self.write(ops[0], self.read(ops[1], ins)))
        elif m == "movzx":
            o.append(self.write(ops[0], self.read(ops[1], ins)))
        elif m == "movsx":
            sb = ops[1].size * 8
            o.append(self.write(ops[0], f"(uint32_t)(int32_t)(int{sb}_t)({self.read(ops[1], ins)})"))
        elif m == "lea":
            o.append(self.write(ops[0], self.addr(ops[1])))
        elif m in ("add", "sub", "cmp"):
            a, b = self.read(ops[0], ins), self.read(ops[1], ins)
            if ops[1].type == X.X86_OP_IMM:
                b = f"0x{ops[1].imm & self.mask(bits):x}u"
            sign = "+" if m == "add" else "-"
            o.append(f"{{ uint32_t a_ = {a}, b_ = {b}; uint32_t r_ = (a_ {sign} b_) & 0x{self.mask(bits):x}u;")
            o.append(f"  fl_{'add' if sign == '+' else 'sub'}(c, a_, b_, r_, {bits});")
            if m != "cmp":
                o.append("  " + self.write(ops[0], "r_"))
            o.append("}")
        elif m in ("adc", "sbb"):
            a, b = self.read(ops[0], ins), self.read(ops[1], ins)
            if ops[1].type == X.X86_OP_IMM:
                b = f"0x{ops[1].imm & self.mask(bits):x}u"
            msk = f"0x{self.mask(bits):x}u"
            if m == "adc":
                o.append(f"{{ uint64_t a_ = {a}, b_ = {b}; uint64_t w_ = a_ + b_ + c->cf; uint32_t r_ = (uint32_t)(w_ & {msk});")
                o.append(f"  c->cf = (uint32_t)(w_ >> {bits}) & 1u; c->of = msb((uint32_t)((a_ ^ r_) & (b_ ^ r_)), {bits});")
            else:
                o.append(f"{{ uint64_t a_ = {a}, b_ = {b}; uint32_t r_ = (uint32_t)((a_ - b_ - c->cf) & {msk});")
                o.append(f"  c->cf = a_ < b_ + c->cf; c->of = msb((uint32_t)((a_ ^ b_) & (a_ ^ r_)), {bits});")
            o.append(f"  c->zf = r_ == 0; c->sf = msb(r_, {bits}); c->pf = parity8(r_); {self.write(ops[0], 'r_')} }}")
        elif m in ("and", "or", "xor", "test"):
            a, b = self.read(ops[0], ins), self.read(ops[1], ins)
            if ops[1].type == X.X86_OP_IMM:
                b = f"0x{ops[1].imm & self.mask(bits):x}u"
            cop = {"and": "&", "test": "&", "or": "|", "xor": "^"}[m]
            o.append(f"{{ uint32_t r_ = ({a} {cop} {b}) & 0x{self.mask(bits):x}u; fl_logic(c, r_, {bits});")
            if m != "test":
                o.append("  " + self.write(ops[0], "r_"))
            o.append("}")
        elif m in ("inc", "dec"):
            a = self.read(ops[0], ins)
            sign = "+" if m == "inc" else "-"
            o.append(f"{{ uint32_t a_ = {a}; uint32_t r_ = (a_ {sign} 1u) & 0x{self.mask(bits):x}u; "
                     f"fl_incdec(c, a_, r_, {bits}, {1 if m == 'inc' else 0}); {self.write(ops[0], 'r_')} }}")
        elif m == "not":
            o.append(self.write(ops[0], f"~{self.read(ops[0], ins)}"))
        elif m == "neg":
            a = self.read(ops[0], ins)
            o.append(f"{{ uint32_t a_ = {a}; uint32_t r_ = (0u - a_) & 0x{self.mask(bits):x}u; fl_sub(c, 0u, a_, r_, {bits}); "
                     f"c->cf = a_ != 0; {self.write(ops[0], 'r_')} }}")
        elif m in ("shl", "shr", "sar", "rol", "ror"):
            a = self.read(ops[0], ins)
            cnt = "1u" if len(ops) == 1 else self.read(ops[1], ins)
            o.append(f"{{ uint32_t n_ = ({cnt}) & 31u; uint32_t a_ = {a}; if (n_) {{ uint32_t r_;")
            msk = f"0x{self.mask(bits):x}u"
            if m == "shl":
                o.append(f"  r_ = (uint32_t)(((uint64_t)a_ << n_) & {msk}); {{ uint32_t cf_ = (uint32_t)(((uint64_t)a_ << n_ >> {bits}) & 1u);")
                o.append(f"  fl_logic(c, r_, {bits}); c->cf = cf_; c->of = msb(r_, {bits}) ^ cf_; }}")
            elif m == "shr":
                o.append(f"  r_ = a_ >> n_; {{ uint32_t cf_ = (a_ >> (n_ - 1)) & 1u; fl_logic(c, r_, {bits}); c->cf = cf_; c->of = msb(a_, {bits}); }}")
            elif m == "sar":
                o.append(f"  int32_t s_ = (int32_t)(a_ << (32 - {bits})) >> (32 - {bits}); r_ = (uint32_t)(s_ >> n_) & {msk};")
                o.append(f"  {{ uint32_t cf_ = (uint32_t)(s_ >> (n_ - 1)) & 1u; fl_logic(c, r_, {bits}); c->cf = cf_; c->of = 0; }}")
            elif m == "rol":
                o.append(f"  uint32_t k_ = n_ % {bits}; r_ = k_ ? ((a_ << k_) | (a_ >> ({bits} - k_))) & {msk} : a_; c->cf = r_ & 1u;")
            else:
                o.append(f"  uint32_t k_ = n_ % {bits}; r_ = k_ ? ((a_ >> k_) | (a_ << ({bits} - k_))) & {msk} : a_; c->cf = msb(r_, {bits});")
            o.append(f"  {self.write(ops[0], 'r_')} }} }}")
        elif m == "imul" and len(ops) >= 2:
            src = self.read(ops[1], ins) if len(ops) == 2 else self.read(ops[1], ins)
            mul = self.read(ops[0], ins) if len(ops) == 2 else f"0x{ops[2].imm & 0xFFFFFFFF:x}u"
            o.append(f"{{ int64_t p_ = (int64_t)(int32_t)({src}) * (int64_t)(int32_t)({mul}); uint32_t r_ = (uint32_t)p_; "
                     f"c->cf = c->of = (p_ != (int64_t)(int32_t)r_); {self.write(ops[0], 'r_')} }}")
        elif m == "mul" and len(ops) == 1 and bits == 32:
            o.append(f"{{ uint64_t p_ = (uint64_t)c->r[0] * (uint64_t)({self.read(ops[0], ins)}); c->r[0] = (uint32_t)p_; "
                     f"c->r[2] = (uint32_t)(p_ >> 32); c->cf = c->of = c->r[2] != 0; }}")
        elif m == "cdq":
            o.append("c->r[2] = (uint32_t)((int32_t)c->r[0] >> 31);")
        elif m == "push":
            v = self.read(ops[0], ins)
            if ops[0].type == X.X86_OP_IMM:
                v = f"0x{ops[0].imm & 0xFFFFFFFF:x}u"
            o.append(f"{{ uint32_t v_ = {v}; push32(c, v_); }}")
        elif m == "pop":
            o.append(f"{{ uint32_t v_ = pop32(c); {self.write(ops[0], 'v_')} }}")
        elif m == "nop":
            pass
        elif m == "leave":
            o.append("c->r[4] = c->r[5]; c->r[5] = pop32(c);")
        elif m in ("rep stosd", "rep stosb", "stosd", "stosb", "rep movsd", "rep movsb", "movsd", "movsb") and (
                m.startswith("rep") or not ops or ops[0].type == X.X86_OP_MEM):
            # direction flag assumed clear (MSVC code never sets DF across calls)
            unit = 4 if m.endswith("d") else 1
            body = (f"wr32(c->r[7], c->r[0]);" if unit == 4 else "wr8(c->r[7], (uint8_t)c->r[0]);") if "stos" in m else \
                (f"wr32(c->r[7], rd32(c->r[6])); c->r[6] += 4u;" if unit == 4 else "wr8(c->r[7], rd8(c->r[6])); c->r[6] += 1u;")
            if m.startswith("rep"):
                o.append(f"while (c->r[1]) {{ {body} c->r[7] += {unit}u; c->r[1]--; }}")
            else:
                o.append(f"{{ {body} c->r[7] += {unit}u; }}")
        elif m in JCC:
            o.append(f"if ({JCC[m]}) goto L_{ops[0].imm:x};")
        elif m.startswith("set") and ("j" + m[3:]) in JCC:
            o.append(self.write(ops[0], f"({JCC['j' + m[3:]]}) ? 1u : 0u"))
        elif m == "jmp" and ops[0].type == X.X86_OP_MEM:
            imp = self.iat[ops[0].mem.disp & 0xFFFFFFFF]
            if imp not in self.host_imports:
                raise Unsupported(f"no host implementation for import {imp}")
            o.append(f"{self.host_imports[imp]}(c); return;   /* tail call to import {imp} */")
        elif m == "jmp":
            t = ops[0].imm
            if t in self.func_entries and t != entry:
                o.append(f"f_{t:x}(c); return;   /* tail call */")
            else:
                o.append(f"goto L_{t:x};")
        elif m == "call":
            if ops[0].type == X.X86_OP_IMM:
                o.append(f"push32(c, 0x{nxt:x}u); f_{ops[0].imm:x}(c);")
            else:
                imp = self.iat[ops[0].mem.disp & 0xFFFFFFFF]
                if imp not in self.host_imports:
                    raise Unsupported(f"no host implementation for import {imp}")
                o.append(f"push32(c, 0x{nxt:x}u); {self.host_imports[imp]}(c);   /* import {imp} */")
        elif m in ("ret", "retn"):
            n = ops[0].imm if ops else 0
            o.append(f"c->r[4] += {4 + n}u; return;")
        elif m == "sahf":
            o.append("{ uint32_t ah_ = (c->r[0] >> 8) & 0xFFu; c->cf = ah_ & 1u; c->pf = (ah_ >> 2) & 1u; c->zf = (ah_ >> 6) & 1u; c->sf = (ah_ >> 7) & 1u; }")
        elif m == "fnstsw":
            o.append(self.write(ops[0], "fstatus(c)"))
        else:
            o.extend(self.lift_x87(ins))
        return o

    def lift_x87(self, ins):
        m, ops = ins.mnemonic, ins.operands
        o = []

        def memload(op):
            a = self.addr(op)
            return {4: f"(double)rdf32({a})", 8: f"rdf64({a})"}[op.size]

        arith = {"fadd": "+", "fsub": "-", "fmul": "*", "fdiv": "/", "fsubr": "r-", "fdivr": "r/"}
        if m == "fld":
            if ops[0].type == X.X86_OP_MEM:
                if ops[0].size == 10:
                    raise Unsupported("80-bit fld")
                o.append(f"fpush(c, {memload(ops[0])});")
            else:
                o.append(f"{{ double v_ = *ST(c, {self.sti(ops[0])}); fpush(c, v_); }}")
        elif m == "fild":
            a = self.addr(ops[0])
            src = {2: f"(double)(int16_t)rd16({a})", 4: f"(double)(int32_t)rd32({a})", 8: f"(double)(int64_t)rd64({a})"}[ops[0].size]
            o.append(f"fpush(c, {src});")
        elif m in ("fld1", "fldz"):
            o.append(f"fpush(c, {'1.0' if m == 'fld1' else '0.0'});")
        elif m in ("fst", "fstp"):
            if ops[0].type == X.X86_OP_MEM:
                a = self.addr(ops[0])
                if ops[0].size == 4:
                    o.append(f"wrf32({a}, (float)*ST(c, 0));")
                elif ops[0].size == 8:
                    o.append(f"wrf64({a}, *ST(c, 0));")
                else:
                    raise Unsupported("80-bit fst")
            else:
                o.append(f"*ST(c, {self.sti(ops[0])}) = *ST(c, 0);")
            if m == "fstp":
                o.append("fpop(c);")
        elif m in ("fist", "fistp"):
            a = self.addr(ops[0])
            if ops[0].size == 8:
                o.append(f"wr64({a}, (uint64_t)fist64(c, *ST(c, 0)));")
            elif ops[0].size == 4:
                o.append(f"wr32({a}, (uint32_t)fist32(c, *ST(c, 0)));")
            else:
                o.append(f"{{ int32_t v_ = fist32(c, *ST(c, 0)); wr16({a}, (v_ < -32768 || v_ > 32767) ? 0x8000u : (uint16_t)v_); }}")
            if m == "fistp":
                o.append("fpop(c);")
        elif m in arith or (m.endswith("p") and m[:-1] in arith):
            popping = m not in arith
            op = arith[m[:-1] if popping else m]
            if len(ops) == 1 and ops[0].type == X.X86_OP_MEM:
                dst = lhs = "*ST(c, 0)"
                rhs = memload(ops[0])
            elif len(ops) == 2:
                d, s = self.sti(ops[0]), self.sti(ops[1])
                dst = lhs = f"*ST(c, {d})"
                rhs = f"*ST(c, {s})"
            elif len(ops) == 1:
                i = self.sti(ops[0])
                if popping:      # fxxxp st(i): st(i) = st(i) op st0, pop
                    dst = lhs = f"*ST(c, {i})"
                    rhs = "*ST(c, 0)"
                else:            # fxxx st(i): st0 = st0 op st(i)
                    dst = lhs = "*ST(c, 0)"
                    rhs = f"*ST(c, {i})"
            else:                # fxxxp: st1 = st1 op st0, pop
                dst = lhs = "*ST(c, 1)"
                rhs = "*ST(c, 0)"
            expr = f"({rhs} {op[1]} {lhs})" if op.startswith("r") else f"({lhs} {op} {rhs})"
            o.append(f"{dst} = {expr};")
            if popping:
                o.append("fpop(c);")
        elif m == "fchs":
            o.append("*ST(c, 0) = -*ST(c, 0);")
        elif m == "fabs":
            o.append("*ST(c, 0) = fabs(*ST(c, 0));")
        elif m == "fsqrt":
            o.append("*ST(c, 0) = sqrt(*ST(c, 0));")
        elif m == "frndint":
            o.append("*ST(c, 0) = fround(c, *ST(c, 0));")
        elif m == "fxch":
            i = self.sti(ops[0]) if ops else 1
            o.append(f"{{ double t_ = *ST(c, 0); *ST(c, 0) = *ST(c, {i}); *ST(c, {i}) = t_; }}")
        elif m in ("fcom", "fcomp", "fucom", "fucomp"):
            rhs = memload(ops[0]) if ops and ops[0].type == X.X86_OP_MEM else (f"*ST(c, {self.sti(ops[0])})" if ops else "*ST(c, 1)")
            o.append(f"fcompare(c, *ST(c, 0), {rhs});")
            if m.endswith("p"):
                o.append("fpop(c);")
        elif m in ("fcompp", "fucompp"):
            o.append("fcompare(c, *ST(c, 0), *ST(c, 1)); fpop(c); fpop(c);")
        elif m in ("fnstcw", "fstcw"):
            o.append(f"wr16({self.addr(ops[0])}, c->fcw);")
        elif m == "fldcw":
            o.append(f"c->fcw = rd16({self.addr(ops[0])});")
        else:
            raise Unsupported(f"instruction {m} {ins.op_str}")
        return o

    def lift_function(self, entry):
        insns, targets, tails, callees = self.discover(entry)
        lines = [f"void f_{entry:x}(CPU* c) {{"]
        order = sorted(insns)
        for i, va in enumerate(order):
            ins = insns[va]
            if va in targets:
                lines.append(f"L_{va:x}:;")
            body = self.lift_insn(ins, entry)
            lines.append(f"    /* {va:08x}: {ins.mnemonic} {ins.op_str} */")
            lines.extend("    " + b for b in body)
            # fall-through into a non-adjacent block needs an explicit goto
            if ins.mnemonic not in ("jmp", "ret", "retn") and (i + 1 == len(order) or order[i + 1] != va + ins.size):
                lines.append(f"    goto L_{va + ins.size:x};")
                targets.add(va + ins.size)
        lines.append("}")
        return lines, callees | tails, len(insns)


def main():
    args = sys.argv[1:]
    lifter = Lifter(args[0])
    if "--coverage" in args:
        limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 10 ** 9
        lifter.host_imports = {n: "host" for n in lifter.iat.values()}  # assume imports are provided
        reasons = collections.Counter()
        ok = n = insn_ok = insn_all = 0
        for name, va in sorted(lifter.exports.items(), key=lambda kv: kv[1])[:limit]:
            if not lifter.in_text(va):
                continue
            n += 1
            try:
                insns, *_ = lifter.discover(va)
                insn_all += len(insns)
                for ins in insns.values():
                    lifter.lift_insn(ins, va)
                ok += 1
                insn_ok += len(insns)
            except Unsupported as exc:
                reasons[re.sub(r"0x[0-9a-f]+|\[.*\]|st\(\d\)", "X", str(exc))[:70]] += 1
            except (KeyError, IndexError, ValueError) as exc:
                reasons[f"lifter error {type(exc).__name__}"] += 1
        print(f"exported code entry points: {n}; liftable with current subset: {ok} ({100.0 * ok / max(n, 1):.1f}%)")
        print("top blocking reasons:")
        for r, k in reasons.most_common(25):
            print(f"  {k:6}  {r}")
        return
    out = args[args.index("--out") + 1]
    wanted = []
    i = 0
    while i < len(args):
        if args[i] == "--func":
            spec = args[i + 1]
            pat, _, cname = spec.partition("=")
            va = lifter.exports.get(pat) or next(v for k, v in lifter.exports.items() if pat in k)
            wanted.append((va, cname or None))
            i += 2
        elif args[i] == "--import":
            k, _, v = args[i + 1].partition("=")
            lifter.host_imports[k] = v
            i += 2
        else:
            i += 1
    done, queue, body, protos, aliases, total_insns = set(), [va for va, _ in wanted], [], [], [], 0
    while queue:
        va = queue.pop()
        if va in done:
            continue
        done.add(va)
        lines, deps, cnt = lifter.lift_function(va)
        total_insns += cnt
        body.extend(lines + [""])
        protos.append(f"void f_{va:x}(CPU* c);")
        queue.extend(d for d in deps if d not in done)
    for va, cname in wanted:
        if cname:
            aliases.append(f"void {cname}(CPU* c) {{ f_{va:x}(c); }}")
    with open(out, "w", encoding="utf-8") as f:
        f.write("/* GENERATED by tools/lift/lift_x86.py from the original Core.dll - do not edit. */\n")
        f.write('#include "x86rt.h"\n')
        for k, v in sorted(lifter.host_imports.items()):
            f.write(f"void {v}(CPU* c);\n")
        f.write("\n".join(protos) + "\n\n")
        f.write("\n".join(body))
        f.write("\n".join(aliases) + "\n")
    print(f"lifted {len(done)} functions ({total_insns} instructions) -> {out}")


if __name__ == "__main__":
    main()
