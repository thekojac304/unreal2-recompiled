"""Instruction-form census for the differential instruction test (experiments/xrt/tests/insn_diff).

Runs tools/xrt/discover.py's Module over the sandbox copies of Core.dll and UCC.exe, collects every
instruction of every discovered function and groups the non-control-flow ones by form:
  (mnemonic incl. rep/lock prefix, operand kinds and sizes)
with operand kinds r8/r16/r32 (r8h for ah/ch/dh/bh is recorded as a variant), imm, m8..m80, st0/sti, sreg.
Inside a form, each encoding class (operand-size/rep prefix, opcode bytes, ModRM reg extension for group
opcodes, full ModRM for x87 register forms, immediate width) is recorded, because the test snippets keep
the encoding class of the census.

Output (build directory, derived from the game binaries, never committed):
  experiments/xrt/build/insn_diff/census.json
Only ISA-level facts are written (mnemonics, opcode classes, counts), no code bytes of the modules.

Usage: python -I experiments/xrt/tests/insn_diff/census.py [--sandbox sandbox_ref/hellofull/System]
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(WS, "tools", "xrt"))
from capstone import x86 as X  # noqa: E402
from discover import JCC, Module  # noqa: E402
from xlift import Lifter, Unsupported, is_simd  # noqa: E402

CONTROL = JCC | {"call", "jmp", "ret", "retn", "loop", "loope", "loopne", "jecxz", "iret", "iretd"}
EXCLUDED = {"cpuid", "rdtsc", "int3", "hlt"}
# opcodes whose ModRM reg field is an opcode extension (one-byte map unless noted)
GROUP1 = {0x80, 0x81, 0x83, 0xC0, 0xC1, 0xD0, 0xD1, 0xD2, 0xD3, 0xF6, 0xF7, 0xFE, 0xFF, 0x8F, 0xC6, 0xC7}
GROUP2 = {0xBA, 0x00, 0x01, 0x18, 0xAE, 0xC7}   # after 0F
REG8H = {"ah", "ch", "dh", "bh"}
SREG = {"es", "cs", "ss", "ds", "fs", "gs"}


def opkind(md, op):
    if op.type == X.X86_OP_REG:
        n = md.reg_name(op.reg)
        if n.startswith("st("):
            return "st0" if n == "st(0)" else "sti"
        if n in SREG:
            return "sreg"
        return {1: "r8", 2: "r16", 4: "r32"}.get(op.size, f"r?{op.size}")
    if op.type == X.X86_OP_IMM:
        return "imm"
    if op.type == X.X86_OP_MEM:
        return f"m{op.size * 8}"
    return "?"


def encoding(md, ins):
    """Encoding class: dict with prefix bytes kept by snippets, opcode bytes, ModRM rule, immediate width."""
    b = bytes(ins.bytes)
    i = 0
    pre = []
    while b[i] in (0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0x66, 0x67, 0xF0, 0xF2, 0xF3):
        pre.append(b[i])
        i += 1
    seg = [p for p in pre if p in (0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65)]
    keep = [p for p in pre if p not in (0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65)]
    if ins.modrm_offset:
        opc = b[i:ins.modrm_offset]
    else:
        ends = [len(b)] + ([ins.imm_offset] if ins.imm_size else []) + ([ins.disp_offset] if ins.disp_size else [])
        opc = b[i:min(ends)]
    enc = {"pre": keep, "opc": list(opc), "seg": seg}
    if ins.modrm_offset:
        modrm = b[ins.modrm_offset]
        mod, reg = modrm >> 6, (modrm >> 3) & 7
        x87 = len(opc) == 1 and 0xD8 <= opc[0] <= 0xDF
        if x87 and mod == 3:
            enc["modrm"] = modrm                  # register form: the whole ModRM selects the instruction
        elif x87 or (len(opc) == 1 and opc[0] in GROUP1) or (len(opc) == 2 and opc[0] == 0x0F and opc[1] in GROUP2):
            enc["ext"] = reg
        enc["rm_is_reg"] = mod == 3
    else:
        enc["reg_in_opcode"] = None
    if ins.imm_size:
        enc["imm_size"] = ins.imm_size
    if not ins.modrm_offset and ins.disp_size:
        enc["moffs"] = True                       # A0-A3: absolute address without ModRM
    return enc


def enc_key(enc):
    parts = [" ".join(f"{p:02x}" for p in enc["pre"]), " ".join(f"{o:02x}" for o in enc["opc"])]
    if "modrm" in enc:
        parts.append(f"modrm={enc['modrm']:02x}")
    if "ext" in enc:
        parts.append(f"/{enc['ext']}")
    if enc.get("rm_is_reg") is not None and "modrm" not in enc:
        parts.append("rm=reg" if enc["rm_is_reg"] else "rm=mem")
    if enc.get("moffs"):
        parts.append("moffs")
    if "imm_size" in enc:
        parts.append(f"imm{enc['imm_size'] * 8}")
    return " ".join(p for p in parts if p)


def addr_mode(md, op):
    mm = op.mem
    seg = md.reg_name(mm.segment) if mm.segment else ""
    s = []
    if seg and seg != "ds":
        s.append(seg + ":")
    if mm.base:
        b = md.reg_name(mm.base)
        s.append("esp" if b == "esp" else "ebp" if b == "ebp" else "base")
    if mm.index:
        s.append(f"idx*{mm.scale}")
    if mm.disp:
        s.append("disp8" if -128 <= mm.disp <= 127 and (mm.base or mm.index) else "disp32")
    return "+".join(s) or "disp32"


def census(paths):
    forms = {}
    fnstsw_consumers = collections.Counter()
    addr_modes = collections.Counter()
    excluded = collections.Counter()
    totals = {}
    for path in paths:
        mod = Module(path).run()
        lifter = Lifter(mod)
        md = mod.md
        seen = {}
        for fn in mod.functions.values():
            for va, ins in fn.insns.items():
                seen[va] = ins
        order = sorted(seen)
        totals[mod.img.name] = len(order)
        for k, va in enumerate(order):
            ins = seen[va]
            m = ins.mnemonic
            if m in CONTROL or m in EXCLUDED or is_simd(md, ins):
                excluded[("simd" if is_simd(md, ins) else m)] += 1
                continue
            kinds = tuple(opkind(md, op) for op in ins.operands)
            key = f"{m} " + ",".join(kinds) if kinds else m
            f = forms.setdefault(key, {"mnemonic": m, "kinds": list(kinds), "count": 0, "modules": {},
                                       "encodings": {}, "variants": collections.Counter(), "lift": collections.Counter()})
            f["count"] += 1
            f["modules"][mod.img.name] = f["modules"].get(mod.img.name, 0) + 1
            enc = encoding(md, ins)
            ek = enc_key(enc)
            e = f["encodings"].setdefault(ek, {"enc": enc, "count": 0, "example": f"{m} {ins.op_str}"})
            e["count"] += 1
            for op in ins.operands:
                if op.type == X.X86_OP_REG and md.reg_name(op.reg) in REG8H:
                    f["variants"]["r8h"] += 1
                if op.type == X.X86_OP_REG and md.reg_name(op.reg) == "esp":
                    f["variants"]["esp-operand"] += 1
                if op.type == X.X86_OP_MEM:
                    am = addr_mode(md, op)
                    addr_modes[am] += 1
                    f["variants"]["addr:" + am] += 1
                    if op.mem.base and op.mem.base in [o.reg for o in ins.operands if o.type == X.X86_OP_REG]:
                        f["variants"]["reg-aliases-base"] += 1
            if len(ins.operands) == 2 and all(o.type == X.X86_OP_REG for o in ins.operands) \
                    and ins.operands[0].reg == ins.operands[1].reg:
                f["variants"]["same-reg"] += 1
            try:
                lifter.lift_insn(ins, None)
                f["lift"]["ok"] += 1
            except Unsupported as exc:
                f["lift"][f"unsupported: {exc}"] += 1
            if m == "fnstsw" and ins.operands and ins.operands[0].type == X.X86_OP_REG:
                nxt = [seen[order[j]] for j in range(k + 1, min(k + 4, len(order)))]
                chain = []
                for n in nxt:
                    chain.append(f"{n.mnemonic} {n.op_str}".strip())
                    if n.mnemonic in ("test", "and", "sahf", "cmp", "mov", "shr", "sar", "bt") or n.mnemonic in JCC:
                        break
                fnstsw_consumers[" ; ".join(chain)] += 1
    out = {"modules": totals, "excluded": dict(excluded.most_common()), "addr_modes": dict(addr_modes.most_common()),
           "fnstsw_ax_consumers": dict(fnstsw_consumers.most_common()), "forms": {}}
    for key in sorted(forms, key=lambda k: -forms[k]["count"]):
        f = forms[key]
        f["variants"] = dict(f["variants"])
        f["lift"] = dict(f["lift"])
        out["forms"][key] = f
    return out


def main():
    args = sys.argv[1:]
    sb = os.path.join(WS, "sandbox_ref", "hellofull", "System")
    if "--sandbox" in args:
        sb = args[args.index("--sandbox") + 1]
    paths = [os.path.join(sb, "Core.dll"), os.path.join(sb, "UCC.exe")]
    out = census(paths)
    dst = os.path.join(WS, "experiments", "xrt", "build", "insn_diff")
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, "census.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    n = sum(f["count"] for f in out["forms"].values())
    print(f"{len(out['forms'])} forms, {sum(len(f['encodings']) for f in out['forms'].values())} encoding classes, "
          f"{n} instructions (modules: {out['modules']})")


if __name__ == "__main__":
    main()
