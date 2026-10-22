"""Print the first bytes of class exports next to table metadata (layout exploration).

Usage: python class_heads.py <package> [N]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package, Reader  # noqa: E402


def main():
    p = Package(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    shown = 0
    for e in p.exports:
        if p.class_name_of(e) != "Class":
            continue
        head = p.payload(e)[:14]
        r = Reader(p.data, e.offset)
        first = r.compact()
        print(f"{e.name:28} idx={e.index:5} super={e.super_ref:5} flags={e.flags:08x} size={e.size:6} "
              f"first_ci={first:6} ({p.names[first] if 0 <= first < len(p.names) else '-'}) head={head.hex(' ')}")
        shown += 1
        if shown >= n:
            break


if __name__ == "__main__":
    main()
