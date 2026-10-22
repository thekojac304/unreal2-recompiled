"""Approximate instruction statistics relevant to static recompilation (read-only).

Linear sweep of executable sections with capstone (counts are approximate: data
embedded in .text, e.g. jump tables, can be mis-decoded). Reports per module:
code size, instructions, x87/MMX/SSE/3DNow! usage, indirect calls/jumps,
jump tables, SEH/C++ EH markers, privileged/odd instructions.
Usage: python code_stats.py <dll/exe> [...] [--json out.json]
"""
import collections
import json
import os
import re
import sys

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs, CS_GRP_JUMP, CS_GRP_CALL
from capstone import x86 as X

X87_PREFIX = ("f",)
MMX = {"movd", "movq", "paddb", "paddw", "paddd", "psubb", "psubw", "psubd", "pmullw", "pmulhw", "pand",
       "pandn", "por", "pxor", "punpcklbw", "punpckhbw", "packuswb", "packsswb", "psrlw", "psllw", "psrlq",
       "psllq", "pcmpeqb", "pcmpgtb", "emms", "pmaddwd", "psraw", "psrad", "punpcklwd", "punpckldq"}
AMD3DNOW = {"femms", "pfadd", "pfsub", "pfmul", "pfrcp", "pfrsqrt", "pfrcpit1", "pfrcpit2", "pfrsqit1",
            "pfacc", "pfmax", "pfmin", "pfcmpge", "pfcmpgt", "pfcmpeq", "pi2fd", "pf2id", "pavgusb",
            "pmulhrw", "pfsubr", "prefetch", "prefetchw", "pswapd", "pfnacc", "pfpnacc", "pi2fw", "pf2iw"}


def classify(ins):
    m = ins.mnemonic
    if m.startswith("f") and m not in ("femms",):
        return "x87"
    if m in AMD3DNOW or m.startswith("pf"):
        return "3dnow"
    if m in MMX:
        return "mmx"
    if re.match(r"^(v)?(add|sub|mul|div|min|max|sqrt|rsqrt|rcp|and|andn|or|xor|cmp|mov|unpck|shuf|cvt)\w*(ps|ss|pd|sd)$", m) \
            or m in ("movaps", "movups", "movss", "movhlps", "movlhps", "shufps", "ldmxcsr", "stmxcsr", "prefetchnta",
                     "prefetcht0", "prefetcht1", "prefetcht2", "comiss", "ucomiss", "cvttss2si", "cvtss2si", "cvtsi2ss",
                     "movntps", "sfence", "movhps", "movlps"):
        return "sse"
    return "int"


def analyze(path):
    pe = pefile.PE(path)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    iat = set()
    imports = set()
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for imp in entry.imports:
            iat.add(imp.address)
            if imp.name:
                imports.add(imp.name.decode("latin1"))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    s = collections.Counter()
    mnem = collections.Counter()
    for sec in pe.sections:
        if not sec.Characteristics & 0x20000000:
            continue
        code = image[sec.VirtualAddress:sec.VirtualAddress + sec.Misc_VirtualSize]
        s["code_bytes"] += len(code)
        for ins in md.disasm(code, base + sec.VirtualAddress):
            if ins.id == 0:  # skipped data
                s["undecodable_bytes"] += ins.size
                continue
            s["instructions"] += 1
            s[classify(ins)] += 1
            mnem[ins.mnemonic] += 1
            ops = ins.operands
            if ins.group(CS_GRP_CALL):
                s["calls"] += 1
                if ops and ops[0].type == X.X86_OP_IMM:
                    s["calls_direct"] += 1
                elif ops and ops[0].type == X.X86_OP_MEM and ops[0].mem.base == 0 and ops[0].mem.index == 0:
                    if ops[0].mem.disp & 0xFFFFFFFF in iat:
                        s["calls_import"] += 1
                    else:
                        s["calls_indirect_global"] += 1
                else:
                    s["calls_indirect_reg_or_vtable"] += 1
            elif ins.mnemonic == "jmp" and ops:
                if ops[0].type == X.X86_OP_MEM:
                    if ops[0].mem.index != 0 and ops[0].mem.scale == 4:
                        s["jump_tables"] += 1
                    elif ops[0].mem.base == 0 and ops[0].mem.index == 0 and ops[0].mem.disp & 0xFFFFFFFF in iat:
                        s["jmp_import_thunks"] += 1
                    else:
                        s["jmp_indirect_other"] += 1
                elif ops[0].type == X.X86_OP_REG:
                    s["jmp_indirect_reg"] += 1
            if ins.mnemonic == "mov" and "fs:" in ins.op_str:
                s["fs_segment_accesses(SEH)"] += 1
            if ins.mnemonic in ("fldcw", "fnstcw", "fstcw"):
                s["fpu_control_word_ops"] += 1
            if ins.mnemonic in ("rdtsc", "cpuid", "int", "in", "out", "sysenter", "cli", "sti", "hlt"):
                s[f"special_{ins.mnemonic}"] += 1
            if ins.mnemonic == "ret" and ops:
                s["ret_imm(stdcall/thiscall)"] += 1
    eh = sorted(i for i in imports if re.search(r"CxxFrameHandler|except_handler|CxxThrowException|_setjmp|longjmp|_EH_prolog", i))
    s["imports_total"] = len(imports)
    pe.close()
    return s, eh, mnem


def main():
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json"); out = args[i + 1]; del args[i:i + 2]
    results = {}
    total = collections.Counter()
    keys = ["code_bytes", "instructions", "int", "x87", "sse", "mmx", "3dnow", "calls", "calls_direct", "calls_import",
            "calls_indirect_reg_or_vtable", "calls_indirect_global", "jump_tables", "jmp_indirect_other",
            "jmp_indirect_reg", "fs_segment_accesses(SEH)", "fpu_control_word_ops", "ret_imm(stdcall/thiscall)",
            "undecodable_bytes"]
    print("module".ljust(20) + "".join(k[:11].rjust(12) for k in keys))
    for path in args:
        s, eh, mnem = analyze(path)
        name = os.path.basename(path)
        results[name] = {"stats": s, "eh_imports": eh, "top_mnemonics": mnem.most_common(25)}
        total.update(s)
        print(name[:19].ljust(20) + "".join(str(s.get(k, 0)).rjust(12) for k in keys))
        if eh:
            print("    EH imports:", ", ".join(eh))
    print("TOTAL".ljust(20) + "".join(str(total.get(k, 0)).rjust(12) for k in keys))
    print("(column headers truncated to 11 chars; see --json for full names)")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"modules": results, "total": total}, f, indent=1)


if __name__ == "__main__":
    main()
