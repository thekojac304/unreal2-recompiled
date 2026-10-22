"""Hex-dump an export payload with the package's name table at hand.

Usage: python dumpexp.py <package> <ExportName> [--class C] [--bytes N]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402


def main():
    args = sys.argv[1:]
    want_class, nbytes = None, 256
    if "--class" in args:
        i = args.index("--class"); want_class = args[i + 1]; del args[i:i + 2]
    if "--bytes" in args:
        i = args.index("--bytes"); nbytes = int(args[i + 1]); del args[i:i + 2]
    p = Package(args[0])
    for e in p.exports:
        if e.name.lower() != args[1].lower():
            continue
        cls = p.class_name_of(e)
        if want_class and cls.lower() != want_class.lower():
            continue
        print(f"{p.objpath(e)} class={cls} super={p.objpath(e.super_ref) if e.super_ref else None} "
              f"flags={e.flags:08x} size={e.size} off={e.offset}")
        data = p.payload(e)[:nbytes]
        for row in range(0, len(data), 16):
            chunk = data[row:row + 16]
            hexs = " ".join(f"{b:02x}" for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  {row:04x}: {hexs:<48} {asc}")


if __name__ == "__main__":
    main()
