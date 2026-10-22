"""Static C++ EH metadata of a module (MSVC 7.0, x86 table-based EH) as uctrace event points.

Usage: python -I tools/xrt/eh_points.py <module> [<module> ...] [--out points.txt] [--json eh.json]

For every function that registers a C++ EH frame (push -1; push <handler>; ... where <handler> is
`mov eax, <FuncInfo>; jmp __CxxFrameHandler`), the FuncInfo (magic 0x19930520) is decoded:
  unwind map  (toState, action)            -> event point "unwind <action> state <s> frame <fn>"
  try blocks  (tryLow, tryHigh, catchHigh) -> for each catch clause: "catch <handler> <type> frame <fn>"
  continuations: a catch funclet ends with `mov eax, <continuation>; ret` -> "continue <cont> frame <fn>"
Event points let uctrace record, in order, which catch funclets, destructor funclets and continuations the
original executes; the translated runtime's exception dispatcher records the same events.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import x86 as X  # noqa: E402
from discover import Module  # noqa: E402

MAGIC_VC7 = 0x19930520


def frames(mod):
    """[(function entry, handler thunk, FuncInfo va)] for every C++ EH frame registration found."""
    img, out = mod.img, []
    for e, fn in mod.functions.items():
        insns = [fn.insns[v] for v in sorted(fn.insns)][:16]
        for k in range(1, len(insns)):
            a, b = insns[k - 1], insns[k]
            if not (a.mnemonic == "push" and b.mnemonic == "push" and a.operands[0].type == X.X86_OP_IMM
                    and b.operands[0].type == X.X86_OP_IMM and (a.operands[0].imm & 0xFFFFFFFF) == 0xFFFFFFFF):
                continue
            h = b.operands[0].imm & 0xFFFFFFFF
            hi = mod.decode(h)
            if hi is None or hi.mnemonic != "mov" or hi.operands[1].type != X.X86_OP_IMM:
                continue
            nj = mod.decode(h + hi.size)
            tgt = None
            if nj is not None and nj.mnemonic == "jmp":
                if nj.operands[0].type == X.X86_OP_IMM:
                    ti = mod.decode(nj.operands[0].imm & 0xFFFFFFFF)
                    if ti is not None and ti.mnemonic == "jmp" and mod.is_iat(ti.operands[0]):
                        tgt = img.iat[ti.operands[0].mem.disp & 0xFFFFFFFF][1]
                elif mod.is_iat(nj.operands[0]):
                    tgt = img.iat[nj.operands[0].mem.disp & 0xFFFFFFFF][1]
            if tgt == "__CxxFrameHandler":
                out.append((e, h, hi.operands[1].imm & 0xFFFFFFFF))
            break
    return out


def continuation_of(mod, funclet):
    """continuation address returned by a catch funclet (`mov eax, imm32; ret`), or None (e.g. a rethrow)."""
    fn = mod.functions.get(funclet)
    if fn is None:
        return None
    insns = [fn.insns[v] for v in sorted(fn.insns)]
    for a, b in zip(insns, insns[1:]):
        if a.mnemonic == "mov" and a.operands[0].type == X.X86_OP_REG and mod.md.reg_name(a.operands[0].reg) == "eax" \
                and a.operands[1].type == X.X86_OP_IMM and b.mnemonic in ("ret", "retn"):
            return a.operands[1].imm & 0xFFFFFFFF
    return None


def decode(mod):
    img = mod.img
    u32 = img.u32
    out = []
    for entry, thunk, fi in frames(mod):
        magic, max_state, punwind, ntry, ptry = (u32(fi + 4 * j) for j in range(5))
        f = {"function": entry, "thunk": thunk, "funcinfo": fi, "magic": magic, "unwind": [], "tries": []}
        if magic == MAGIC_VC7:
            for s in range(max_state):
                to, action = u32(punwind + 8 * s), u32(punwind + 8 * s + 4)
                f["unwind"].append({"state": s, "to": to - (1 << 32) if to & 0x80000000 else to, "action": action})
            for t in range(ntry):
                lo, hi, ch, ncat, pcat = (u32(ptry + 20 * t + 4 * j) for j in range(5))
                tb = {"low": lo, "high": hi, "catch_high": ch, "catches": []}
                for c in range(ncat):
                    adj, ptype, disp, handler = (u32(pcat + 16 * c + 4 * j) for j in range(4))
                    name = "..." if not ptype else bytes(img.image[ptype + 8 - img.base:ptype + 72 - img.base]).split(b"\0")[0].decode("latin-1")
                    tb["catches"].append({"adjectives": adj, "type": name, "disp": disp, "handler": handler,
                                          "continuation": continuation_of(mod, handler)})
                f["tries"].append(tb)
        out.append(f)
    return out


def main():
    args = sys.argv[1:]
    out = args[args.index("--out") + 1] if "--out" in args else None
    js = args[args.index("--json") + 1] if "--json" in args else None
    paths = [a for a in args if a not in (out, js) and not a.startswith("--")]
    lines, everything = [], {}
    for p in paths:
        mod = Module(p).run()
        name, base = mod.img.name, mod.img.base
        fr = decode(mod)
        everything[name] = fr
        seen = set()

        def point(va, label):
            if va and va not in seen:
                seen.add(va)
                lines.append(f"{name.lower()} {va - base:x} {label}")

        for f in fr:
            for u in f["unwind"]:
                point(u["action"], f"unwind {u['action']:#x} frame {f['function']:#x}")
            for t in f["tries"]:
                for c in t["catches"]:
                    point(c["handler"], f"catch {c['handler']:#x} {c['type']} frame {f['function']:#x}")
                    if c["continuation"]:
                        point(c["continuation"], f"continue {c['continuation']:#x} frame {f['function']:#x}")
        nt = sum(len(f["tries"]) for f in fr)
        print(f"{name}: {len(fr)} C++ EH frames ({sum(f['magic'] != MAGIC_VC7 for f in fr)} not VC7), {nt} try blocks, "
              f"{sum(len(f['unwind']) for f in fr)} unwind states, {len(seen)} event points")
    if out:
        with open(out, "w", newline="\n") as f:
            f.write("# generated by tools/xrt/eh_points.py: <module> <rva> <label>\n" + "\n".join(lines) + "\n")
    if js:
        with open(js, "w", newline="\n") as f:
            json.dump({k: [{kk: (hex(vv) if isinstance(vv, int) and kk in ("function", "thunk", "funcinfo", "magic") else vv)
                            for kk, vv in fr.items()} for fr in v] for k, v in everything.items()}, f, indent=1)


if __name__ == "__main__":
    main()
