"""Grep ASCII and UTF-16LE strings in binaries (read-only).

Usage: python strings_grep.py <regex> <file> [<file> ...] [--min N] [--max-hits N]
"""
import re
import sys


def strings(data, min_len):
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, data):
        yield m.start(), "A", m.group().decode("ascii")
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % min_len, data):
        yield m.start(), "W", m.group().decode("utf-16le")


def main():
    args = sys.argv[1:]
    min_len, max_hits = 4, 60
    if "--min" in args:
        i = args.index("--min"); min_len = int(args[i + 1]); del args[i:i + 2]
    if "--max-hits" in args:
        i = args.index("--max-hits"); max_hits = int(args[i + 1]); del args[i:i + 2]
    pattern = re.compile(args[0], re.I)
    for path in args[1:]:
        data = open(path, "rb").read()
        hits = sorted((off, kind, s) for off, kind, s in strings(data, min_len) if pattern.search(s))
        print(f"== {path} ({len(hits)} hits)")
        for off, kind, s in hits[:max_hits]:
            print(f"  {off:08x} {kind} {s[:200]}")


if __name__ == "__main__":
    main()
