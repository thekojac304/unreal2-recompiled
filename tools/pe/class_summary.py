"""Print the most-exported classes per module from symbols.py output.

Usage: python class_summary.py <symbols dir> <Module> [<Module> ...] [--top N]
"""
import json
import os
import sys


def main():
    args = sys.argv[1:]
    top_n = 45
    if "--top" in args:
        i = args.index("--top"); top_n = int(args[i + 1]); del args[i:i + 2]
    sym_dir = args[0]
    for mod in args[1:]:
        with open(os.path.join(sym_dir, f"{mod}.dll.classes.json"), encoding="utf-8") as f:
            d = json.load(f)
        named = [c for c in d if not c.startswith("`") and c != "<global>"]
        named.sort(key=lambda c: -len(d[c]))
        print(f"== {mod}: {len(named)} classes, {len(d.get('<global>', []))} free symbols")
        print("   " + ", ".join(f"{c}({len(d[c])})" for c in named[:top_n]))


if __name__ == "__main__":
    main()
