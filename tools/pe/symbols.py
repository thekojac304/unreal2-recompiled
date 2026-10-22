"""Demangle MSVC export names and build per-class indexes.

Usage: python symbols.py <exports dir> <out dir>
Reads <exports dir>/<module>.txt produced by pe_recon.py. Writes:
  <out>/<module>.demangled.txt   ordinal, rva, demangled name
  <out>/<module>.classes.json    {class: [member signatures]}
"""
import collections
import ctypes
import json
import os
import re
import sys

dbghelp = ctypes.WinDLL("dbghelp.dll")
dbghelp.UnDecorateSymbolName.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32]
dbghelp.UnDecorateSymbolName.restype = ctypes.c_uint32
UNDNAME_COMPLETE = 0
UNDNAME_NAME_ONLY = 0x1000


def undecorate(name, flags=UNDNAME_COMPLETE):
    buf = ctypes.create_string_buffer(4096)
    n = dbghelp.UnDecorateSymbolName(name.encode("latin1"), buf, 4096, flags)
    return buf.value[:n].decode("latin1") if n else name


def owner_class(mangled):
    """Return the class a mangled member belongs to, or None for free functions/data."""
    if not mangled.startswith("?"):
        return None
    full = undecorate(mangled, UNDNAME_NAME_ONLY)
    # e.g. "AActor::Tick", "TArray<unsigned short>::TArray<unsigned short>", "UObject::`vftable'"
    depth, cut = 0, -1
    for i, ch in enumerate(full):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif depth == 0 and full.startswith("::", i):
            cut = i
    return full[:cut] if cut > 0 else None


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for fname in sorted(os.listdir(src)):
        module = fname[:-4]
        classes = collections.defaultdict(list)
        lines = []
        with open(os.path.join(src, fname), encoding="utf-8") as f:
            for line in f:
                ordinal, rva, name = line.rstrip("\n").split("\t")
                if name == "None":
                    continue
                dem = undecorate(name)
                lines.append(f"{ordinal}\t{rva}\t{dem}")
                cls = owner_class(name)
                classes[cls or "<global>"].append(dem)
        with open(os.path.join(out, module + ".demangled.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(out, module + ".classes.json"), "w", encoding="utf-8") as f:
            json.dump(classes, f, indent=0, sort_keys=True)
        print(f"{module:24} exports={len(lines):5} classes={len(classes):4}")


if __name__ == "__main__":
    main()
