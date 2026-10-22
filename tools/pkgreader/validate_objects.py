"""Parse every field object (classes, states, functions, structs, properties,
enums, consts, text buffers) in every script-bearing package and check:

  O1 parse consumes exactly the export's SerialSize
  O2 bytecode: token stream ends exactly at ScriptSize (in-memory) and every
     jump / case / iterator / label target lands on a token boundary
  O3 bytecode: every Context/ClassContext/Skip size operand equals the
     in-memory size of the expression it skips (independent size model check)
Usage: python validate_objects.py <dir> [<dir> ...] [--max-fail N] [--report out.json]
"""
import collections
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402
from uobjects import ObjectParser, ScriptError  # noqa: E402

FIELD_CLASSES = {"Class", "State", "Function", "Struct", "Enum", "Const", "TextBuffer",
                 "ByteProperty", "ObjectProperty", "ClassProperty", "StructProperty", "ArrayProperty",
                 "FixedArrayProperty", "MapProperty", "IntProperty", "FloatProperty", "BoolProperty",
                 "NameProperty", "StrProperty", "StringProperty", "PointerProperty"}
EXTS = (".u", ".un2", ".unr", ".utx", ".usx", ".uax", ".ukx", ".upx", ".ugx")


def main():
    args = sys.argv[1:]
    max_fail, report = 15, None
    if "--max-fail" in args:
        i = args.index("--max-fail"); max_fail = int(args[i + 1]); del args[i:i + 2]
    if "--report" in args:
        i = args.index("--report"); report = args[i + 1]; del args[i:i + 2]
    stats = collections.Counter()
    by_class = collections.Counter()
    failures = []
    opcode_hist = collections.Counter()
    natives_hist = collections.Counter()
    unk_values = collections.Counter()
    per_version = collections.Counter()
    for d in args:
        for dirpath, _, files in os.walk(d):
            if os.path.basename(dirpath).lower() == "save":
                continue
            for fname in sorted(files):
                if not fname.lower().endswith(EXTS):
                    continue
                p = Package(os.path.join(dirpath, fname))
                parser = ObjectParser(p)
                for e in p.exports:
                    cls = p.class_name_of(e)
                    if cls not in FIELD_CLASSES or e.size == 0:
                        continue
                    stats["objects"] += 1
                    try:
                        out = parser.parse(e)
                    except (ScriptError, ValueError, IndexError, KeyError, UnicodeDecodeError) as exc:
                        stats["exceptions"] += 1
                        if len(failures) < max_fail:
                            failures.append(f"{fname}:{p.objpath(e)} [{cls}] v{p.version}/{p.licensee} {type(exc).__name__}: {exc}")
                        continue
                    if not out["exact"]:
                        stats["inexact"] += 1
                        if len(failures) < max_fail:
                            failures.append(f"{fname}:{p.objpath(e)} [{cls}] v{p.version}/{p.licensee} consumed {out['consumed']} of {e.size}")
                        continue
                    stats["exact"] += 1
                    by_class[cls] += 1
                    per_version[(p.version, p.licensee)] += 1
                    if "script_size" in out:
                        stats["structs"] += 1
                        stats["script_bytes_mem"] += out["script_size"]
                        stats["script_bytes_disk"] += out["script_disk_size"]
                        unk_values[out["legend_unk"]] += 1
                        if out["script_size"]:
                            stats["with_bytecode"] += 1
                        opcode_hist.update(op for op in out["ops"] if op < 0x60)
                        natives_hist.update(out["natives_called"])
                        if out["bad_skips"]:
                            stats["bad_skip_structs"] += 1
                            if len(failures) < max_fail:
                                failures.append(f"{fname}:{p.objpath(e)} bad skips {out['bad_skips'][:3]}")
    print("objects:", stats["objects"], " exact:", stats["exact"], " inexact:", stats["inexact"],
          " exceptions:", stats["exceptions"])
    print("structs/functions/states/classes with script:", stats["with_bytecode"], "of", stats["structs"],
          " bytecode mem bytes:", stats["script_bytes_mem"], " disk bytes:", stats["script_bytes_disk"],
          " structs with bad skip sizes:", stats["bad_skip_structs"])
    print("by class:", dict(by_class.most_common()))
    print("by (version, licensee):", dict(per_version))
    print("legend_unk values (top):", unk_values.most_common(8))
    print("distinct opcodes used:", len(opcode_hist), " distinct native indices called:", len(natives_hist))
    for f in failures:
        print("  FAIL", f)
    if report:
        with open(report, "w", encoding="utf-8") as f:
            json.dump({"stats": stats, "by_class": by_class, "opcodes": {f"0x{k:02X}": v for k, v in sorted(opcode_hist.items())},
                       "natives_called": {str(k): v for k, v in sorted(natives_hist.items())},
                       "failures": failures}, f, indent=1)


if __name__ == "__main__":
    main()
