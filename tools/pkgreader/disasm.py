"""Disassemble the bytecode of one struct/function/state/class export.

Usage: python disasm.py <package> <Outer.Name path suffix> [--class Function]
Prints tokens as an indented tree with in-memory offsets.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402
from uobjects import EX, ObjectParser  # noqa: E402


def fmt_arg(p, tok, a):
    if tok.op in (0x00, 0x01, 0x02, 0x29, 0x20, 0x13, 0x2E, 0x1C, 0x36, 0x32, 0x33) and isinstance(a, int):
        return p.objpath(a)
    return repr(a)


def show(p, tok, depth=0, out=None):
    name = EX.get(tok.op, f"Native_{tok.args[0]}" if tok.op >= 0x60 else f"0x{tok.op:02X}")
    args = ", ".join(fmt_arg(p, tok, a) for a in tok.args)
    print(f"{tok.mem:5d} {'  ' * depth}{name}({args})")
    for c in tok.children:
        show(p, c, depth + 1)


def main():
    args = sys.argv[1:]
    want = None
    if "--class" in args:
        i = args.index("--class"); want = args[i + 1]; del args[i:i + 2]
    p = Package(args[0])
    parser = ObjectParser(p)
    for e in p.exports:
        path = p.objpath(e)
        if not path.lower().endswith(args[1].lower()):
            continue
        cls = p.class_name_of(e)
        if want and cls != want:
            continue
        out = parser.parse(e)
        print(f"== {path} [{cls}] script_size={out.get('script_size')} exact={out['exact']} flags={out.get('function_flags', 0):#x} native={out.get('native_index')}")
        for t in out.get("tokens", []):
            show(p, t)
        if out.get("bad_skips"):
            print("bad skips:", out["bad_skips"])


if __name__ == "__main__":
    main()
