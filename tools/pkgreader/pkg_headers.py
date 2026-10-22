"""Survey Unreal package headers (read-only).

Usage: python pkg_headers.py <dir> [<dir> ...]
Prints tag, version, licensee version, flags, table counts/offsets and generation info.
"""
import collections
import os
import struct
import sys

PKG_TAG = 0x9E2A83C1
EXTS = (".u", ".un2", ".unr", ".utx", ".usx", ".uax", ".ukx", ".upx", ".umx", ".usa", ".uxx")


def header(path):
    with open(path, "rb") as f:
        data = f.read(4096)
    if len(data) < 36:
        return {"error": f"short ({len(data)} bytes)"}
    tag, ver, flags, nc, no, ec, eo, ic, io = struct.unpack_from("<IIIIIIIII", data, 0)
    if tag != PKG_TAG:
        return {"error": f"bad tag {tag:08x}"}
    h = {"version": ver & 0xFFFF, "licensee": ver >> 16, "flags": flags, "names": (nc, no),
         "exports": (ec, eo), "imports": (ic, io)}
    pos = 36
    if h["version"] >= 68:
        h["guid"] = data[pos:pos + 16].hex()
        pos += 16
        gen_count = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        gens = []
        for _ in range(min(gen_count, 64)):
            gens.append(struct.unpack_from("<ii", data, pos))
            pos += 8
        h["generations"] = gens
    h["header_end"] = pos
    return h


def main():
    by_ver = collections.Counter()
    for d in sys.argv[1:]:
        for dirpath, _, files in os.walk(d):
            if os.path.basename(dirpath).lower() == "save":
                continue
            for name in sorted(files):
                if not name.lower().endswith(EXTS):
                    continue
                path = os.path.join(dirpath, name)
                h = header(path)
                rel = os.path.relpath(path, d)
                if "error" in h:
                    print(f"{rel:50} ERROR {h['error']}")
                    continue
                by_ver[(os.path.splitext(name)[1].lower(), h["version"], h["licensee"])] += 1
                print(f"{rel:50} v={h['version']:3} lic={h['licensee']:3} flags={h['flags']:08x} "
                      f"N={h['names'][0]:6}@{h['names'][1]:<9} E={h['exports'][0]:6}@{h['exports'][1]:<9} "
                      f"I={h['imports'][0]:5}@{h['imports'][1]:<9} gens={len(h.get('generations', []))} hdr_end={h['header_end']}")
    print("\nSummary (ext, version, licensee) -> count")
    for k, v in sorted(by_ver.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
