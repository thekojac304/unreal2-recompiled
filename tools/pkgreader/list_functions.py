"""List functions of a class with native index, flags and parameter signature.

Usage: python list_functions.py <package> <ClassName> [--native-only]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402
from uobjects import FUNC_Native, ObjectParser  # noqa: E402

CPF_Parm, CPF_OutParm, CPF_OptionalParm, CPF_ReturnParm = 0x80, 0x100, 0x10, 0x400
FLAG_NAMES = [(0x1, "final"), (0x2000, "static"), (0x400, "native"), (0x800, "event"),
              (0x1000, "operator"), (0x10, "preoperator"), (0x8, "latent"), (0x4, "iterator"),
              (0x200, "exec"), (0x100, "simulated")]


def prop_type(p, out, cls):
    base = cls.replace("Property", "").lower()
    if cls in ("ObjectProperty", "ClassProperty", "StructProperty", "ByteProperty") and out["extra"] and out["extra"][0]:
        return f"{base}<{p.objpath(out['extra'][0]).split('.')[-1]}>"
    if cls == "ArrayProperty":
        return "array"
    return base


def main():
    args = sys.argv[1:]
    native_only = "--native-only" in args
    p = Package(args[0])
    parser = ObjectParser(p)
    cls_exp = [e for e in p.exports if e.name == args[1] and p.class_name_of(e) == "Class"][0]
    for e in p.exports:
        if p.class_name_of(e) != "Function" or p.obj(e.outer) is not cls_exp:
            continue
        f = parser.parse(e)
        if native_only and not f["function_flags"] & FUNC_Native:
            continue
        params, ret = [], None
        child = f["children"]
        while child:
            ce = p.obj(child)
            c = parser.parse(ce)
            if c["class"].endswith("Property") and c["property_flags"] & CPF_Parm:
                t = prop_type(p, c, c["class"])
                if c["property_flags"] & CPF_ReturnParm:
                    ret = t
                else:
                    mods = ("out " if c["property_flags"] & CPF_OutParm else "") + \
                           ("optional " if c["property_flags"] & CPF_OptionalParm else "")
                    params.append(f"{mods}{t} {ce.name}")
            child = c["next"]
        flags = " ".join(n for bit, n in FLAG_NAMES if f["function_flags"] & bit)
        prec = f" prec={f['oper_precedence']}" if f["function_flags"] & 0x1000 else ""
        print(f"{f['native_index']:5} {flags:30} {ret or 'void':10} {e.name}({', '.join(params)}){prec}")


if __name__ == "__main__":
    main()
