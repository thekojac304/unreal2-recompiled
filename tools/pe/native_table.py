"""Merge per-module native registrations into one table and print views.

Usage: python native_table.py <natives dir> [--opcodes] [--casts] [--dupes] [--json out.json]
"""
import json
import os
import sys


def load(nat_dir):
    rows = []
    for name in sorted(os.listdir(nat_dir)):
        if not name.endswith(".natives.json"):
            continue
        mod = name[:-len(".dll.natives.json")]
        with open(os.path.join(nat_dir, name), encoding="utf-8") as f:
            d = json.load(f)
        for r in d["registrations"]:
            if "index" in r:
                rows.append({"module": mod, "table": r.get("table", "native"), "index": r["index"],
                             "var": r["var"], "member": r["member"]})
        for v in d["name_bound_only"]:
            rows.append({"module": mod, "table": "byname", "index": -1, "var": v["var"], "member": v["member"]})
    return rows


def short(member):
    if not member:
        return "?"
    # "public: void __thiscall UObject::execLocalVariable(struct FFrame &,void * const)" -> UObject::execLocalVariable
    head = member.split("(")[0]
    return head.split(" ")[-1]


def main():
    args = sys.argv[1:]
    rows = load(args[0])
    if "--opcodes" in args:
        ops = sorted((r for r in rows if r["table"] == "native" and 0 <= r["index"] < 0x70), key=lambda r: r["index"])
        for r in ops:
            print(f"  0x{r['index']:02X} {short(r['member'])}")
    if "--casts" in args:
        for r in sorted((r for r in rows if r["table"] == "cast"), key=lambda r: r["index"]):
            print(f"  cast 0x{r['index']:02X} {short(r['member'])}")
    if "--dupes" in args:
        seen = {}
        for r in rows:
            if r["table"] == "native" and r["index"] >= 0:
                seen.setdefault(r["index"], []).append(f"{r['module']}:{short(r['member'])}")
        for k, v in sorted(seen.items()):
            if len(v) > 1:
                print(f"  DUPLICATE index {k}: {v}")
    if "--json" in args:
        out = args[args.index("--json") + 1]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=0)
    by_mod = {}
    for r in rows:
        by_mod.setdefault((r["module"], r["table"] if r["index"] >= 0 else "unnumbered"), 0)
        by_mod[(r["module"], r["table"] if r["index"] >= 0 else "unnumbered")] += 1
    print("counts:", {f"{m}/{t}": c for (m, t), c in sorted(by_mod.items())})


if __name__ == "__main__":
    main()
