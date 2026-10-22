"""Tabulate property flag bits against unexplained trailing bytes (layout exploration).

Usage: python prop_extras.py <dir>
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402
from uobjects import ObjectParser  # noqa: E402


def main():
    by_bits = collections.defaultdict(collections.Counter)
    samples = {}
    for dirpath, _, files in os.walk(sys.argv[1]):
        for fname in files:
            if not fname.lower().endswith(".u"):
                continue
            p = Package(os.path.join(dirpath, fname))
            parser = ObjectParser(p)
            for e in p.exports:
                cls = p.class_name_of(e)
                if not cls.endswith("Property") or e.size == 0:
                    continue
                out = parser.parse(e)
                extra = e.size - out["consumed"]
                flags = out["property_flags"]
                for bit in range(32):
                    if flags & (1 << bit):
                        by_bits[1 << bit][extra > 0] += 1
                if extra:
                    key = (flags & 0xFFFF0000, extra)
                    samples.setdefault(key, (p.objpath(e), p.payload(e)[out["consumed"]:].hex(" ")))
    print("bit        no-extra  with-extra")
    for bit in sorted(by_bits):
        c = by_bits[bit]
        print(f"0x{bit:08x} {c[False]:8} {c[True]:8}")
    for (hi, extra), (path, tail) in sorted(samples.items()):
        print(f"flags_hi=0x{hi:08x} extra={extra:3} {path}: {tail[:120]}")


if __name__ == "__main__":
    main()
