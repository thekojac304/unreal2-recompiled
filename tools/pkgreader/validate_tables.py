"""Validate the table layer of every package in one or more directories.

Checks, per package:
  T1 name/import/export tables parse and end exactly where the next region starts
  T2 every export payload lies inside the file, payloads do not overlap
  T3 header + tables + payloads account for every byte of the file (gaps reported)
  T4 every object reference in the tables is in range
Across packages (per directory set):
  X1 every import whose outermost package exists in the set resolves to an export
     with the same name, same outer path and same class name
Usage: python validate_tables.py <dir> [<dir> ...] [--report out.json]
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from upkg import Package  # noqa: E402

EXTS = (".u", ".un2", ".unr", ".utx", ".usx", ".uax", ".ukx", ".upx", ".umx", ".ugx")


def check_package(p):
    problems = []
    regions = [(0, p.header_end, "header"), (p.name_offset, p.names_end, "names"),
               (p.import_offset, p.imports_end, "imports"), (p.export_offset, p.exports_end, "exports")]
    n_objs = len(p.imports) + len(p.exports)
    for e in p.exports:
        for ref in (e.class_ref, e.super_ref, e.outer):
            if not (-len(p.imports) <= ref <= len(p.exports)):
                problems.append(f"T4 export {e.index} ref {ref} out of range")
        if e.size > 0:
            if e.offset < 0 or e.offset + e.size > len(p.data):
                problems.append(f"T2 export {e.name} payload [{e.offset},{e.offset + e.size}) outside file")
            regions.append((e.offset, e.offset + e.size, f"export:{e.name}"))
    for imp in p.imports:
        if not (-len(p.imports) <= imp.outer <= len(p.exports)):
            problems.append(f"T4 import {imp.name} outer {imp.outer} out of range")
    regions.sort()
    covered = 0
    pos = 0
    gaps = []
    for start, end, label in regions:
        if start < pos:
            problems.append(f"T2 overlap: {label} starts {start} before {pos}")
        elif start > pos:
            gaps.append((pos, start))
        covered += end - start
        pos = max(pos, end)
    if pos < len(p.data):
        gaps.append((pos, len(p.data)))
    gap_bytes = sum(b - a for a, b in gaps)
    return problems, gaps, gap_bytes, n_objs


def main():
    args = sys.argv[1:]
    report_path = symbols_dir = None
    if "--report" in args:
        i = args.index("--report"); report_path = args[i + 1]; del args[i:i + 2]
    if "--symbols" in args:
        i = args.index("--symbols"); symbols_dir = args[i + 1]; del args[i:i + 2]
    packages = {}
    failures = []
    for d in args:
        for dirpath, _, files in os.walk(d):
            if os.path.basename(dirpath).lower() == "save":
                continue
            for name in files:
                if name.lower().endswith(EXTS):
                    path = os.path.join(dirpath, name)
                    try:
                        p = Package(path)
                    except Exception as exc:  # noqa: BLE001 - report every failure
                        failures.append((path, repr(exc)))
                        continue
                    packages.setdefault(p.name.lower(), p)
    totals = collections.Counter()
    per_pkg = {}
    for key, p in sorted(packages.items()):
        problems, gaps, gap_bytes, n_objs = check_package(p)
        totals["packages"] += 1
        totals["bytes"] += len(p.data)
        totals["gap_bytes"] += gap_bytes
        totals["names"] += len(p.names)
        totals["imports"] += len(p.imports)
        totals["exports"] += len(p.exports)
        totals["problems"] += len(problems)
        per_pkg[p.name] = {"version": p.version, "licensee": p.licensee, "problems": problems,
                           "gaps": gaps[:10], "gap_bytes": gap_bytes}
    # X1: cross-package import resolution, keyed by (package, path below package, class)
    index = set()
    for key, p in packages.items():
        for e in p.exports:
            full = p.objpath(e).lower()
            sub = full.split(".", 1)[1] if "." in full else ""
            index.add((key, sub, p.class_name_of(e).lower()))
    native_classes = load_native_classes(symbols_dir) if symbols_dir else {}
    resolved = unresolved_pkg_missing = unresolved = intrinsic = 0
    missing_pkgs = collections.Counter()
    intrinsic_names = collections.Counter()
    unresolved_samples = []
    for key, p in packages.items():
        for imp in p.imports:
            if imp.class_name == "Package" and imp.outer == 0:
                continue  # top-level package reference itself
            top = p.outermost(imp).lower()
            if top not in packages:
                unresolved_pkg_missing += 1
                missing_pkgs[top] += 1
                continue
            parts = []
            o = imp
            while o.outer != 0:
                parts.append(o.name)
                o = p.obj(o.outer)
            sub = ".".join(reversed(parts)).lower()
            if (top, sub, imp.class_name.lower()) in index:
                resolved += 1
                continue
            # Classes that exist only in C++ (no script export) are registered by the DLL at runtime.
            if imp.class_name == "Class" and imp.outer < 0 and p.obj(imp.outer).outer == 0:
                cxx = native_classes.get(top, set())
                if ("u" + imp.name.lower()) in cxx or ("a" + imp.name.lower()) in cxx:
                    intrinsic += 1
                    intrinsic_names[f"{top}.{imp.name}"] += 1
                    continue
            unresolved += 1
            if len(unresolved_samples) < 40:
                unresolved_samples.append(f"{p.name}: {imp.class_package}.{imp.class_name} {top}.{sub}")
    print(f"packages parsed: {totals['packages']}  parse failures: {len(failures)}")
    for path, err in failures:
        print(f"  FAIL {path}: {err}")
    print(f"bytes: {totals['bytes']:,}  unaccounted gap bytes: {totals['gap_bytes']:,}")
    print(f"names: {totals['names']:,} imports: {totals['imports']:,} exports: {totals['exports']:,}")
    print(f"table problems: {totals['problems']}")
    for name, info in per_pkg.items():
        if info["problems"] or info["gap_bytes"]:
            print(f"  {name}: v{info['version']}/{info['licensee']} problems={info['problems'][:3]} gaps={info['gaps'][:3]} gap_bytes={info['gap_bytes']}")
    print(f"X1 imports resolved to a script/content export: {resolved:,}")
    print(f"X1 imports of C++-only (intrinsic) classes found in DLL exports: {intrinsic:,} "
          f"({len(intrinsic_names)} distinct)")
    print("   ", ", ".join(sorted(intrinsic_names)))
    print(f"X1 imports into packages absent from the set: {unresolved_pkg_missing} -> {dict(missing_pkgs)}")
    print(f"X1 unresolved: {unresolved}")
    for s in unresolved_samples:
        print("  ", s)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({"totals": totals, "failures": failures, "packages": per_pkg,
                       "x1": {"resolved": resolved, "intrinsic": intrinsic,
                              "intrinsic_names": intrinsic_names, "unresolved": unresolved,
                              "missing_pkg": dict(missing_pkgs), "samples": unresolved_samples}}, f, indent=1)


def load_native_classes(symbols_dir):
    """{package: {lowercase C++ class names}} from symbols.py output (<Pkg>.dll.classes.json)."""
    out = {}
    for name in os.listdir(symbols_dir):
        if name.lower().endswith(".dll.classes.json"):
            with open(os.path.join(symbols_dir, name), encoding="utf-8") as f:
                out[name[:-len(".dll.classes.json")].lower()] = {c.lower() for c in json.load(f)}
    return out


if __name__ == "__main__":
    main()
