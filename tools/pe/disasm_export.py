"""Disassemble an exported function (by mangled-name substring) until ret/limit.

Usage: python disasm_export.py <dll> <substring> [--max N] [--follow]
Annotates call/jmp targets and absolute addresses with export names.
"""
import re
import struct
import sys

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from symbols import undecorate  # noqa: E402


def main():
    args = sys.argv[1:]
    max_insn = 160
    if "--max" in args:
        i = args.index("--max"); max_insn = int(args[i + 1]); del args[i:i + 2]
    pe = pefile.PE(args[0])
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    names = {}
    for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if e.name:
            names[base + e.address] = undecorate(e.name.decode())
    iat = {}
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for imp in entry.imports:
            nm = imp.name.decode() if imp.name else f"ord{imp.ordinal}"
            iat[imp.address] = f"{entry.dll.decode()}!{undecorate(nm)}"
    matches = [(va, n) for va, n in names.items() if args[1] in n]
    if not matches:
        sys.exit("no match")
    va, n = matches[0]
    print(f"== {n} @ {va:#x}  (matches: {len(matches)})")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    code = image[va - base: va - base + 4096]
    count = 0
    for ins in md.disasm(code, va):
        note = ""
        for m in re.finditer(r"0x[0-9a-f]+", ins.op_str):
            a = int(m.group(), 16)
            if a in names:
                note += f"  ; {names[a][:110]}"
            elif a in iat:
                note += f"  ; [{iat[a][:110]}]"
        print(f"  {ins.address:08x}: {ins.bytes.hex():<18} {ins.mnemonic:6} {ins.op_str}{note}")
        count += 1
        if count >= max_insn:
            break


if __name__ == "__main__":
    main()
