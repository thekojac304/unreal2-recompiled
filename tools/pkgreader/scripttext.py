"""Print (or save) the embedded UnrealScript source (ScriptText) of classes.

Usage: python scripttext.py <package> <ClassName|*> [--out dir]
NOTE: the text is Legend/Epic copyrighted source. Keep extracted copies local
(out/ is git-ignored); do not redistribute.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402
from uobjects import ObjectParser  # noqa: E402


def main():
    args = sys.argv[1:]
    out_dir = None
    if "--out" in args:
        i = args.index("--out"); out_dir = args[i + 1]; del args[i:i + 2]
    p = Package(args[0])
    parser = ObjectParser(p)
    for e in p.exports:
        if p.class_name_of(e) != "Class" or (args[1] != "*" and e.name.lower() != args[1].lower()):
            continue
        c = parser.parse(e)
        if not c["script_text"]:
            continue
        text = parser.parse(p.obj(c["script_text"]))["text"]
        if out_dir:
            d = os.path.join(out_dir, p.name, "Classes")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, e.name + ".uc"), "w", encoding="utf-8", newline="") as f:
                f.write(text)
        else:
            print(text)


if __name__ == "__main__":
    main()
