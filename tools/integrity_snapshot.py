"""Read-only integrity snapshot of the game install (and, metadata only, the Save junction).

Usage:
  python -I tools/integrity_snapshot.py <install-dir> <out.json>
  python -I tools/integrity_snapshot.py --compare <before.json> <after.json>

Every regular file under the install is hashed (SHA-256). Reparse points (the
singleplayer/Save junction into Proton Drive) are NOT followed for hashing: only
their entries' names, sizes and mtimes are listed, so personal saves are never
read and cloud placeholders are never hydrated.
"""
import hashlib
import json
import os
import stat
import sys


def is_reparse(path):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT) or os.path.islink(path)


def snapshot(root):
    files, junctions = {}, {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        keep = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if is_reparse(full):
                listing = {}
                try:
                    for e in os.scandir(full):
                        st = e.stat(follow_symlinks=False)
                        listing[e.name] = [st.st_size, int(st.st_mtime)]
                except OSError as exc:
                    listing["<error>"] = str(exc)
                junctions[os.path.relpath(full, root)] = listing
            else:
                keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            full = os.path.join(dirpath, f)
            st = os.lstat(full)
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            files[os.path.relpath(full, root)] = [st.st_size, int(st.st_mtime), h.hexdigest()]
    return {"root": root, "files": files, "junctions": junctions}


def main():
    if sys.argv[1] == "--compare":
        a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[2:4])
        diffs = []
        for k in sorted(set(a["files"]) | set(b["files"])):
            if a["files"].get(k) != b["files"].get(k):
                diffs.append(f"file {k}: {a['files'].get(k)} -> {b['files'].get(k)}")
        if a["junctions"] != b["junctions"]:
            diffs.append("junction listing changed")
        print(f"files: {len(a['files'])} vs {len(b['files'])}; differences: {len(diffs)}")
        for d in diffs[:50]:
            print("  " + d)
        sys.exit(1 if diffs else 0)
    snap = snapshot(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=0, sort_keys=True)
    total = sum(v[0] for v in snap["files"].values())
    print(f"{len(snap['files'])} files, {total} bytes hashed; {len(snap['junctions'])} junction(s) listed (metadata only)")


if __name__ == "__main__":
    main()
