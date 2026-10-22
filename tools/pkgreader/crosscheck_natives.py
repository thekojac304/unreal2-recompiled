"""Cross-check native functions declared in script packages against the native
registration table recovered from the DLL machine code (tools/pe/natives.py).

  N1 every script function with FUNC_Native and iNative>0 has a DLL registration
     at that index whose implementation is <Prefix><Class>::exec<Name>
  N2 every script function with FUNC_Native and iNative==0 has an exported
     int<Prefix><Class>exec<Name> variable in some DLL (name binding)
  N3 every numbered registration in the DLLs is claimed by a script function
  N4 every native index called from bytecode is registered
Usage: python crosscheck_natives.py <System dir> <native_table.json> [--report out.json]
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402
from uobjects import FUNC_Native, ObjectParser  # noqa: E402


def owner_class(p, e):
    o = p.obj(e.outer)
    while o is not None and p.class_name_of(o) != "Class":
        o = p.obj(o.outer)
    return o


def class_chain_is_actor(p_by_name, pkg, cls_exp):
    """True if the class derives from Engine.Actor (C++ prefix 'A')."""
    seen = 0
    p, e = pkg, cls_exp
    while e is not None and seen < 64:
        seen += 1
        if e.name == "Actor":
            return True
        ref = e.super_ref
        if ref == 0:
            return False
        o = p.obj(ref)
        if ref < 0:  # import: find the export in its package
            top = p.outermost(o).lower()
            q = p_by_name.get(top)
            if q is None:
                return False
            cand = [x for x in q.exports if x.name == o.name and q.class_name_of(x) == "Class"]
            if not cand:
                return False
            p, e = q, cand[0]
        else:
            e = o
    return False


def main():
    sysdir, table_path = sys.argv[1], sys.argv[2]
    report = sys.argv[sys.argv.index("--report") + 1] if "--report" in sys.argv else None
    with open(table_path, encoding="utf-8") as f:
        rows = json.load(f)
    numbered = collections.defaultdict(list)
    exported_vars = set()
    for r in rows:
        exported_vars.add(r["var"])
        if r["table"] == "native" and r["index"] >= 0:
            numbered[r["index"]].append(r)
    packages = {}
    for name in os.listdir(sysdir):
        if name.lower().endswith(".u"):
            p = Package(os.path.join(sysdir, name))
            packages[p.name.lower()] = p
    stats = collections.Counter()
    problems = []
    claimed = set()
    called = collections.Counter()
    for key, p in sorted(packages.items()):
        parser = ObjectParser(p)
        for e in p.exports:
            if p.class_name_of(e) not in ("Function", "Class", "State", "Struct") or e.size == 0:
                continue
            out = parser.parse(e)
            called.update(out.get("natives_called", []))
            if p.class_name_of(e) != "Function" or not out["function_flags"] & FUNC_Native:
                continue
            cls = owner_class(p, e)
            prefix = "A" if class_chain_is_actor(packages, p, cls) else "U"
            want_member = f"{prefix}{cls.name}::exec{e.name}"
            var = f"int{prefix}{cls.name}exec{e.name}"
            idx = out["native_index"]
            stats["native_functions"] += 1
            if idx > 0:
                stats["numbered"] += 1
                regs = numbered.get(idx, [])
                members = [(r["member"] or "").split("(")[0].split(" ")[-1] for r in regs]
                if want_member in members:
                    stats["N1_ok"] += 1
                    claimed.add(idx)
                elif idx < 0x70 and not regs:
                    stats["N1_opcode_only"] += 1  # e.g. operators re-using opcodes
                else:
                    stats["N1_fail"] += 1
                    problems.append(f"N1 {p.name}.{cls.name}.{e.name} iNative={idx} want {want_member} got {members}")
            else:
                stats["by_name"] += 1
                if var in exported_vars:
                    stats["N2_ok"] += 1
                else:
                    stats["N2_fail"] += 1
                    problems.append(f"N2 {p.name}.{cls.name}.{e.name} expects export {var}")
    unclaimed = [(i, [(r['module'], (r['member'] or '').split('(')[0].split(' ')[-1]) for r in regs])
                 for i, regs in sorted(numbered.items()) if i >= 0x70 and i not in claimed]
    uncalled_regs = [i for i in called if i not in numbered]
    print("native script functions:", stats["native_functions"], " numbered:", stats["numbered"],
          " bound by name:", stats["by_name"])
    print(f"N1 numbered index -> matching DLL exec member: {stats['N1_ok']}/{stats['numbered']}  (fail {stats['N1_fail']})")
    print(f"N2 name-bound -> exported int<Class>exec<Name>: {stats['N2_ok']}/{stats['by_name']}  (fail {stats['N2_fail']})")
    print(f"N3 numbered DLL registrations (>=0x70) not claimed by any script function: {len(unclaimed)}")
    for u in unclaimed[:15]:
        print("    ", u)
    print(f"N4 distinct native indices called from bytecode: {len(called)}; unregistered: {sorted(uncalled_regs)}")
    for pr in problems[:25]:
        print("  ", pr)
    if report:
        with open(report, "w", encoding="utf-8") as f:
            json.dump({"stats": stats, "problems": problems, "unclaimed": unclaimed,
                       "called_unregistered": uncalled_regs}, f, indent=1)


if __name__ == "__main__":
    main()
