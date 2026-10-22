"""Read-only PE reconnaissance for the Unreal II install.

Usage: python pe_recon.py <game System dir> <out dir>

Writes:
  <out>/pe_summary.json      per-module headers, sections, Rich header, imports, export count
  <out>/exports/<mod>.txt    raw export names (ordinal, rva, name)
  <out>/imports/<mod>.txt    imports grouped by DLL
Never writes to the game directory.
"""
import collections
import datetime
import json
import os
import struct
import sys

import pefile

# Best-effort names for Rich header product ids (from public richprint tables).
RICH_PRODID = {
    0x01: "Import0", 0x04: "Linker600", 0x06: "Cvtres500", 0x0A: "Utc12_C", 0x0B: "Utc12_CPP",
    0x0E: "Masm613", 0x0F: "Masm710", 0x12: "Masm614", 0x15: "Utc12_C_Std", 0x16: "Utc12_CPP_Std",
    0x19: "Implib700", 0x1A: "Cvtomf700", 0x1C: "Utc13_C", 0x1D: "Utc13_CPP", 0x2A: "Masm615",
    0x2B: "Utc13_LTCG_C", 0x2C: "Utc13_LTCG_CPP", 0x2D: "Masm620", 0x30: "Utc12_2_C", 0x31: "Utc12_2_CPP",
    0x3D: "Linker700", 0x3F: "Export700", 0x40: "Masm700", 0x45: "Cvtres700",
    0x5A: "Linker710", 0x5D: "Implib710", 0x5F: "Utc1310_C", 0x60: "Utc1310_CPP",
}


def rich(pe):
    r = pe.parse_rich_header()
    if not r:
        return None
    vals = r["values"]
    out = []
    for i in range(0, len(vals), 2):
        compid, count = vals[i], vals[i + 1]
        prodid, build = compid >> 16, compid & 0xFFFF
        out.append({"prodid": prodid, "name": RICH_PRODID.get(prodid, "?"), "build": build, "count": count})
    return out


def analyze(path):
    pe = pefile.PE(path, fast_load=False)
    fh, oh = pe.FILE_HEADER, pe.OPTIONAL_HEADER
    info = {
        "file": os.path.basename(path),
        "size": os.path.getsize(path),
        "machine": hex(fh.Machine),
        "timestamp": fh.TimeDateStamp,
        "timestamp_utc": datetime.datetime.fromtimestamp(fh.TimeDateStamp, datetime.UTC).isoformat(),
        "characteristics": hex(fh.Characteristics),
        "is_dll": bool(fh.Characteristics & 0x2000),
        "linker": f"{oh.MajorLinkerVersion}.{oh.MinorLinkerVersion:02d}",
        "image_base": hex(oh.ImageBase),
        "size_of_image": oh.SizeOfImage,
        "entry_rva": hex(oh.AddressOfEntryPoint),
        "subsystem": oh.Subsystem,
        "dll_characteristics": hex(oh.DllCharacteristics),
        "has_relocs": oh.DATA_DIRECTORY[5].Size != 0,
        "has_tls": oh.DATA_DIRECTORY[9].Size != 0,
        "has_debug_dir": oh.DATA_DIRECTORY[6].Size != 0,
        "has_loadconfig": oh.DATA_DIRECTORY[10].Size != 0,
        "has_delay_imports": oh.DATA_DIRECTORY[13].Size != 0,
        "sections": [
            {"name": s.Name.rstrip(b"\0").decode("latin1"), "vsize": s.Misc_VirtualSize,
             "rawsize": s.SizeOfRawData, "flags": hex(s.Characteristics), "entropy": round(s.get_entropy(), 3)}
            for s in pe.sections
        ],
        "rich": rich(pe),
    }
    imports = collections.OrderedDict()
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        dll = entry.dll.decode("latin1")
        names = []
        for imp in entry.imports:
            names.append(imp.name.decode("latin1") if imp.name else f"#ord{imp.ordinal}")
        imports[dll] = names
    info["imports"] = {k: len(v) for k, v in imports.items()}
    exports = []
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            exports.append((e.ordinal, e.address, e.name.decode("latin1") if e.name else None))
    info["export_count"] = len(exports)
    debug = []
    for d in getattr(pe, "DIRECTORY_ENTRY_DEBUG", []):
        entry = {"type": d.struct.Type}
        if d.entry is not None and hasattr(d.entry, "PdbFileName"):
            entry["pdb"] = d.entry.PdbFileName.rstrip(b"\0").decode("latin1")
        debug.append(entry)
    info["debug"] = debug
    pe.close()
    return info, imports, exports


def main():
    sysdir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(outdir, "exports"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "imports"), exist_ok=True)
    results = []
    for name in sorted(os.listdir(sysdir), key=str.lower):
        if not name.lower().endswith((".exe", ".dll", ".gpi")):
            continue
        path = os.path.join(sysdir, name)
        try:
            info, imports, exports = analyze(path)
        except pefile.PEFormatError as exc:
            results.append({"file": name, "error": str(exc)})
            continue
        results.append(info)
        with open(os.path.join(outdir, "exports", name + ".txt"), "w", encoding="utf-8") as f:
            for ordinal, rva, ename in exports:
                f.write(f"{ordinal}\t{rva:08x}\t{ename}\n")
        with open(os.path.join(outdir, "imports", name + ".txt"), "w", encoding="utf-8") as f:
            for dll, names in imports.items():
                f.write(f"[{dll}] {len(names)}\n")
                for n in names:
                    f.write(f"  {n}\n")
    with open(os.path.join(outdir, "pe_summary.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    # Console table
    print(f"{'module':24} {'link':5} {'base':10} {'reloc':5} {'exports':>7} imports")
    for r in results:
        if "error" in r:
            print(f"{r['file']:24} ERROR {r['error']}")
            continue
        imps = ", ".join(f"{k}:{v}" for k, v in r["imports"].items())
        print(f"{r['file']:24} {r['linker']:5} {r['image_base']:10} {str(r['has_relocs']):5} {r['export_count']:7} {imps}")


if __name__ == "__main__":
    main()
