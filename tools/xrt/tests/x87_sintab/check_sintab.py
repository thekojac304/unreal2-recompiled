"""Compare the FGlobalMath sine table and the fsin edge arguments: hardware x87 vs the runtime model(s).

Usage: python -I check_sintab.py   (after build_and_run.cmd; reads experiments/xrt/build/x87_sintab/*.txt)
Exit status 0 when the current runtime's table is float32-identical to the hardware's and, for the edge arguments,
C2, NaN-ness and the float32 value of the result match. Differences in the double-precision bits are listed, not
failed: the model is claimed float32-faithful on these inputs (measured), not bit-exact at double precision.
"""
import os
import struct
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "experiments", "xrt", "build", "x87_sintab")


def load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return None
    tab, edges, cw = {}, {}, None
    for line in open(p):
        if line.startswith("# fcw"):
            cw = line.split()[2]
        elif line.startswith("e"):
            k, a, r, c2 = line.split()
            edges[k] = (a, r, int(c2))
        elif line.strip():
            i, u = line.split()
            tab[int(i)] = u
    return cw, tab, edges


def ulp_distance(a, b):
    ia, ib = struct.unpack("<i", bytes.fromhex(a)[::-1])[0], struct.unpack("<i", bytes.fromhex(b)[::-1])[0]
    ia = ia if ia >= 0 else -(ia & 0x7FFFFFFF)
    ib = ib if ib >= 0 else -(ib & 0x7FFFFFFF)
    return abs(ia - ib)


def f32_of(h):
    return struct.pack("<f", struct.unpack("<d", bytes.fromhex(h)[::-1])[0]) if not is_nan64(h) else b"nan"


def is_nan64(h):
    v = int(h, 16)
    return (v >> 52) & 0x7FF == 0x7FF and v & ((1 << 52) - 1)


def report(label, hw, rt):
    cw_h, tab_h, edge_h = hw
    cw_r, tab_r, edge_r = rt
    diff = [(i, tab_h[i], tab_r[i], ulp_distance(tab_h[i], tab_r[i])) for i in sorted(tab_h) if tab_h[i] != tab_r.get(i)]
    print(f"{label}: control word hw {cw_h} model {cw_r}; sine table entries {len(tab_h)}, float32 differences {len(diff)}")
    for i, a, b, u in diff[:10]:
        print(f"   i={i} hw {a} model {b} ({u} ulp)")
    # edges: C2, NaN-ness and the float32 rounding of the result must match; the double-level distance is reported
    edge_bad, double_only = [], []
    for k in sorted(edge_h, key=lambda s: int(s[1:])):
        (a, rh, ch), (_, rr, cr) = edge_h[k], edge_r[k]
        if (rh, ch) == (rr, cr):
            continue
        same_nan = bool(is_nan64(rh)) == bool(is_nan64(rr))
        same_f32 = is_nan64(rh) or f32_of(rh) == f32_of(rr)
        (double_only if ch == cr and same_nan and same_f32 else edge_bad).append((a, rh, ch, rr, cr))
    print(f"   fsin edge arguments: {len(edge_h)}; differing in C2, NaN-ness or float32 value: {len(edge_bad)}; "
          f"double-precision bits only: {len(double_only)}")
    for a, rh, ch, rr, cr in edge_bad:
        print(f"   x={a}: hw {rh} C2={ch}  model {rr} C2={cr}")
    for a, rh, ch, rr, cr in double_only:
        print(f"   x={a}: hw {rh} model {rr} ({abs(int(rh, 16) - int(rr, 16))} double ulp; same float32)")
    return len(diff), len(edge_bad)


def main():
    hw = load("hw.txt")
    rt = load("rt.txt")
    if not hw or not rt:
        sys.exit("run build_and_run.cmd first")
    old = load("rt_old.txt")
    if old:
        report("previous runtime model (git revision given to build_and_run.cmd)", hw, old)
    d, e = report("current runtime model", hw, rt)
    sys.exit(0 if d == 0 and e == 0 else 1)


if __name__ == "__main__":
    main()
