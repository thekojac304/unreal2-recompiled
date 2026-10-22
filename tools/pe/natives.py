"""Recover the UnrealScript native/opcode registration table from game DLLs.

UE2-style modules register natives in static initialisers that call
GRegisterNative(index, &int<Class><execFunc>). This tool:
  1. maps exported extern "C" variables named int<Class>exec<Name> to the
     function they point at (and to the demangled member export at that RVA),
  2. finds every call to GRegisterNative (direct in Core.dll, via the import
     address table elsewhere) and decodes the two pushed arguments,
  3. writes <out>/<module>.natives.json: [{index, var, func_rva, member}].
Usage: python natives.py <dll> [<dll> ...] --out <dir>
"""
import json
import os
import re
import struct
import sys

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from symbols import undecorate  # noqa: E402

REG_MANGLED = "?GRegisterNative@@YAEHABQ8UObject@@AEXAAUFFrame@@QAX@Z@Z"


def analyze(path):
    pe = pefile.PE(path)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    exports = {}
    by_rva = {}
    for e in getattr(pe, "DIRECTORY_ENTRY_EXPORT", type("x", (), {"symbols": []})).symbols:
        if e.name:
            n = e.name.decode("latin1")
            exports[n] = e.address
            by_rva.setdefault(e.address, []).append(n)
    # Variables int<Class>exec<Name> hold a pointer to the native implementation.
    var_info = {}
    for name, rva in exports.items():
        if re.match(r"^int[A-Z]\w*exec\w+$", name):
            func_va = struct.unpack_from("<I", image, rva)[0]
            func_rva = func_va - base
            members = [undecorate(m) for m in by_rva.get(func_rva, []) if m.startswith("?")]
            var_info[base + rva] = {"var": name, "func_rva": func_rva, "member": members[0] if members else None}
    # Locate GRegisterNative call targets.
    direct_targets = set()
    iat_slots = set()
    if REG_MANGLED in exports:
        direct_targets.add(base + exports[REG_MANGLED])
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for imp in entry.imports:
            if imp.name and imp.name.decode("latin1") == REG_MANGLED:
                iat_slots.add(imp.address)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    regs = []
    for sec in pe.sections:
        if not sec.Characteristics & 0x20000000:
            continue
        code = image[sec.VirtualAddress:sec.VirtualAddress + sec.Misc_VirtualSize]
        sec_va = base + sec.VirtualAddress
        # Candidate call sites: E8 rel32 or FF 15 abs32 to GRegisterNative.
        for m in re.finditer(rb"\xE8(....)|\xFF\x15(....)", code, re.S):
            at = m.start()
            if m.group(1) is not None:
                target = (sec_va + at + 5 + struct.unpack("<i", m.group(1))[0]) & 0xFFFFFFFF
                if target not in direct_targets:
                    continue
            else:
                if struct.unpack("<I", m.group(2))[0] not in iat_slots:
                    continue
            # Decode a short window before the call and take the last two pushes.
            window_start = max(0, at - 24)
            best = None
            for start in range(window_start, at):
                insns = list(md.disasm(code[start:at], sec_va + start))
                if not insns or insns[-1].address + insns[-1].size != sec_va + at:
                    continue
                pushes = [i for i in insns if i.mnemonic == "push"]
                if len(pushes) >= 2:
                    best = pushes[-2:]
                    break
            if best is None:
                regs.append({"call_va": sec_va + at, "error": "could not decode pushes"})
                continue
            # cdecl: last push is the first argument (index), previous is &int<...>.
            idx_op, ref_op = best[1].op_str, best[0].op_str
            try:
                index = int(idx_op, 0)
                ref = int(ref_op, 0)
            except ValueError:
                regs.append({"call_va": sec_va + at, "error": f"non-constant push {ref_op}, {idx_op}"})
                continue
            if index >= 0x80000000:
                index -= 0x100000000
            info = var_info.get(ref, {"var": f"<va {ref:#x}>", "func_rva": None, "member": None})
            regs.append({"index": index, **info})
    # Core.dll inlines GRegisterNative/GRegisterCast:
    # "mov reg,[int<...>]" then "mov [GNatives+4*i],reg" (or GCasts for conversions).
    tables = {}
    for n, rva in exports.items():
        if n.startswith("?GNatives@@"):
            tables["native"] = (base + rva, 4096)
        elif n.startswith("?GCasts@@"):
            tables["cast"] = (base + rva, 256)
    for table, (lo, count) in tables.items():
        hi = lo + 4 * count
        for sec in pe.sections:
            if not sec.Characteristics & 0x20000000:
                continue
            code = image[sec.VirtualAddress:sec.VirtualAddress + sec.Misc_VirtualSize]
            sec_va = base + sec.VirtualAddress
            for var_va, info in var_info.items():
                for m in re.finditer(re.escape(struct.pack("<I", var_va)), code):
                    # the load is either A1 <addr> (1-byte opcode) or 8B /r <addr> (2 bytes)
                    for op_len in (1, 2):
                        s = m.start() - op_len
                        insns = list(md.disasm(code[s:s + 48], sec_va + s))
                        if not insns or insns[0].mnemonic != "mov" or f"{var_va:#x}" not in insns[0].op_str:
                            continue
                        reg = insns[0].op_str.split(",")[0].strip()
                        for ins in insns[1:8]:
                            mm = re.match(r"dword ptr \[(0x[0-9a-f]+)\], (\w+)$", ins.op_str)
                            if ins.mnemonic == "mov" and mm and mm.group(2) == reg:
                                dest = int(mm.group(1), 16)
                                if lo <= dest < hi:
                                    regs.append({"index": (dest - lo) // 4, **info, "table": table})
                                    break
                        break
    pe.close()
    # The inlined registration stores twice (first-call and steady-state paths): dedupe.
    seen = set()
    unique = []
    for r in regs:
        key = (r.get("table", "native"), r.get("index"), r.get("var"), r.get("error"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    regs = unique
    unregistered = [v for va, v in var_info.items() if v["var"] not in {r.get("var") for r in regs}]
    return regs, unregistered


def main():
    args = sys.argv[1:]
    i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    os.makedirs(out, exist_ok=True)
    for path in args:
        regs, unregistered = analyze(path)
        mod = os.path.basename(path)
        good = [r for r in regs if "index" in r]
        numbered = [r for r in good if r["index"] >= 0]
        errors = [r for r in regs if "error" in r]
        with open(os.path.join(out, mod + ".natives.json"), "w", encoding="utf-8") as f:
            json.dump({"registrations": regs, "name_bound_only": unregistered}, f, indent=1)
        print(f"{mod:22} GRegisterNative calls={len(regs):4} numbered={len(numbered):4} "
              f"index<0={len(good) - len(numbered):4} decode_errors={len(errors)} "
              f"exported exec vars never registered={len(unregistered)}")


if __name__ == "__main__":
    main()
