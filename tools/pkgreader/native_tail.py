"""Show the bytes left after the tagged-property block for exports of given classes.

Usage: python native_tail.py <package> <Class> [<Class> ...] [--n 8]
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package, Reader  # noqa: E402
from uobjects import ObjectParser, RF_HasStack  # noqa: E402


def main():
    args = sys.argv[1:]
    n = 8
    if "--n" in args:
        i = args.index("--n"); n = int(args[i + 1]); del args[i:i + 2]
    p = Package(args[0])
    parser = ObjectParser(p)
    want = set(args[1:])
    hist = collections.Counter()
    shown = collections.Counter()
    for e in p.exports:
        cls = p.class_name_of(e)
        if cls not in want or e.size <= 0:
            continue
        r = Reader(p.data, e.offset)
        if e.flags & RF_HasStack:
            node = r.compact(); r.compact(); r.u64(); r.i32()
            if node:
                r.compact()
        props = parser.tagged_properties(r)
        tail = p.data[r.pos:e.offset + e.size]
        hist[(cls, len(tail))] += 1
        if shown[cls] < n:
            shown[cls] += 1
            print(f"{p.objpath(e):40} flags={e.flags:08x} props={len(props):3} tail({len(tail)})={tail[:48].hex(' ')}")
    print("tail length histogram:", dict(hist.most_common(12)))


if __name__ == "__main__":
    main()
