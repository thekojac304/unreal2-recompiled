"""Survey non-script (content) exports: parse the generic UObject part (state frame +
tagged-property block) and measure what remains per class. Remaining bytes are the
class's native serialization (Texture mips, StaticMesh buffers, BSP, ...), i.e. what a
reimplementation must load with class-specific native code.

Usage: python content_survey.py <dir> [<dir> ...] [--json out.json]
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package, Reader  # noqa: E402
from uobjects import ObjectParser, RF_HasStack  # noqa: E402

FIELD = {"Class", "State", "Function", "Struct", "Enum", "Const", "TextBuffer"}
EXTS = (".u", ".un2", ".utx", ".usx", ".uax", ".upx", ".ugx", ".unr", ".ukx")


def main():
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json"); out = args[i + 1]; del args[i:i + 2]
    stats = collections.defaultdict(lambda: collections.Counter())
    fails = collections.Counter()
    samples = {}
    for d in args:
        for dirpath, _, files in os.walk(d):
            if os.path.basename(dirpath).lower() == "save":
                continue
            for fn in files:
                if not fn.lower().endswith(EXTS):
                    continue
                p = Package(os.path.join(dirpath, fn))
                if p.version != 110:
                    continue
                parser = ObjectParser(p)
                for e in p.exports:
                    cls = p.class_name_of(e)
                    if cls in FIELD or cls.endswith("Property") or e.size <= 0:
                        continue
                    s = stats[cls]
                    s["objects"] += 1
                    s["bytes"] += e.size
                    r = Reader(p.data, e.offset)
                    try:
                        if e.flags & RF_HasStack:
                            node = r.compact(); r.compact(); r.u64(); r.i32()
                            if node:
                                r.compact()
                        parser.tagged_properties(r)
                    except Exception as exc:  # noqa: BLE001
                        s["parse_fail"] += 1
                        fails[cls] += 1
                        samples.setdefault(cls, f"{fn}:{p.objpath(e)} {type(exc).__name__}: {exc}")
                        continue
                    left = e.offset + e.size - r.pos
                    if left < 0:
                        s["overrun"] += 1
                        samples.setdefault(cls, f"{fn}:{p.objpath(e)} overran by {-left}")
                        continue
                    s["prop_bytes"] += r.pos - e.offset
                    s["native_bytes"] += left
                    if left:
                        s["with_native"] += 1
    rows = sorted(stats.items(), key=lambda kv: -kv[1]["bytes"])
    print(f"{'class':28} {'objects':>8} {'MB':>9} {'native MB':>10} {'w/native':>9} {'fail':>5}")
    for cls, s in rows[:45]:
        print(f"{cls:28} {s['objects']:8} {s['bytes'] / 1e6:9.2f} {s['native_bytes'] / 1e6:10.2f} "
              f"{s['with_native']:9} {s['parse_fail'] + s['overrun']:5}")
    tot = collections.Counter()
    for s in stats.values():
        tot.update(s)
    print(f"TOTAL classes={len(stats)} objects={tot['objects']} bytes={tot['bytes'] / 1e6:.1f}MB "
          f"native={tot['native_bytes'] / 1e6:.1f}MB parse_fail={tot['parse_fail']} overrun={tot['overrun']}")
    pure_prop = sorted(c for c, s in stats.items() if s["with_native"] == 0 and not s["parse_fail"] and not s["overrun"])
    print(f"classes fully described by tagged properties ({len(pure_prop)}): {', '.join(pure_prop[:60])}")
    native = sorted(c for c, s in stats.items() if s["with_native"])
    print(f"classes with native payload ({len(native)}): {', '.join(native)}")
    for c, smp in list(samples.items())[:10]:
        print("  sample:", smp)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({c: dict(s) for c, s in stats.items()}, f, indent=1)


if __name__ == "__main__":
    main()
