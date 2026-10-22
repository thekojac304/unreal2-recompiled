"""Print the RIFF chunk tree of a file (read-only), e.g. DirectMusic .con containers.

Usage: python riff_tree.py <file> [--depth N] [--max N]
"""
import struct
import sys


def walk(data, start, end, depth, max_depth, budget, counts):
    pos = start
    while pos + 8 <= end and budget[0] > 0:
        cid = data[pos:pos + 4].decode("latin1")
        size = struct.unpack_from("<I", data, pos + 4)[0]
        body = pos + 8
        counts[cid] = counts.get(cid, 0) + 1
        if cid in ("RIFF", "LIST"):
            form = data[body:body + 4].decode("latin1")
            counts[f"{cid}:{form}"] = counts.get(f"{cid}:{form}", 0) + 1
            if depth <= max_depth:
                print(f"{'  ' * depth}{cid} {form} size={size}")
                budget[0] -= 1
            walk(data, body + 4, min(body + size, end), depth + 1, max_depth, budget, counts)
        else:
            if depth <= max_depth:
                preview = ""
                if cid in ("UNAM", "guid", "vers"):
                    preview = data[body:body + min(size, 64)].decode("utf-16le", "replace") if cid == "UNAM" else data[body:body + 16].hex()
                print(f"{'  ' * depth}{cid} size={size} {preview}")
                budget[0] -= 1
        pos = body + size + (size & 1)


def main():
    args = sys.argv[1:]
    depth, max_lines = 3, 80
    if "--depth" in args:
        i = args.index("--depth"); depth = int(args[i + 1]); del args[i:i + 2]
    if "--max" in args:
        i = args.index("--max"); max_lines = int(args[i + 1]); del args[i:i + 2]
    data = open(args[0], "rb").read()
    counts = {}
    walk(data, 0, len(data), 0, depth, [max_lines], counts)
    print("chunk counts:", dict(sorted(counts.items(), key=lambda kv: -kv[1])[:30]))


if __name__ == "__main__":
    main()
