"""Find code references to an address (or exported symbol) and disassemble around them.

Usage: python xref_disasm.py <dll> <export-name-or-hex-va> [--before N] [--after N] [--max N]
"""
import re
import struct
import sys

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs


def main():
    args = sys.argv[1:]
    before, after, max_hits = 24, 40, 5
    for flag in ("--before", "--after", "--max"):
        if flag in args:
            i = args.index(flag); val = int(args[i + 1]); del args[i:i + 2]
            if flag == "--before": before = val
            elif flag == "--after": after = val
            else: max_hits = val
    path, target = args[0], args[1]
    pe = pefile.PE(path)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    if target.startswith("0x"):
        va = int(target, 16)
    else:
        va = None
        for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if e.name and e.name.decode() == target:
                va = base + e.address
        if va is None:
            sys.exit(f"export {target} not found")
    print(f"target VA {va:#x}")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    needle = struct.pack("<I", va)
    hits = 0
    for sec in pe.sections:
        if not sec.Characteristics & 0x20000000:
            continue
        code = image[sec.VirtualAddress:sec.VirtualAddress + sec.Misc_VirtualSize]
        sec_va = base + sec.VirtualAddress
        for m in re.finditer(re.escape(needle), code):
            hits += 1
            if hits > max_hits:
                continue
            start = max(0, m.start() - before)
            # resync: find a start offset whose decode lands on the referencing instruction
            for s in range(start, m.start()):
                insns = list(md.disasm(code[s:m.start() + after], sec_va + s))
                if any(i.address <= sec_va + m.start() < i.address + i.size and i.address + i.size > sec_va + m.start() for i in insns):
                    break
            print(f"--- ref at {sec_va + m.start():#x}")
            for i in insns:
                print(f"  {i.address:08x}: {i.bytes.hex():<20} {i.mnemonic} {i.op_str}")
    print(f"total refs: {hits}")


if __name__ == "__main__":
    main()
