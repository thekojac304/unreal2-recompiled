"""Make the probe DLL use the EH runtime of the game: msvcr70.dll's VC7 frame handler.

Usage: python -I patch_probe.py <ehprobe.dll>   (patches in place, prints what it changed)
  - import names: _CxxThrowException@8 -> _CxxThrowException, __CxxFrameHandler3 -> __CxxFrameHandler (the import
    library from the .def keeps the x86 decoration; msvcr70.dll exports the undecorated names)
  - FuncInfo magic 0x19930522 (VC8+, adds pESTypeList and EHFlags after the VC7 fields) -> 0x19930520 (VC7): the
    first seven fields have the same layout, which is all the VC7 handler reads
Every patched FuncInfo must be the one a handler thunk (`mov eax, FuncInfo; jmp ...`) of the DLL refers to; the
script refuses otherwise.
"""
import struct
import sys

import pefile


def main():
    path = sys.argv[1]
    pe = pefile.PE(path)
    data = bytearray(pe.__data__)
    renames = {b"_CxxThrowException@8": b"_CxxThrowException", b"__CxxFrameHandler3": b"__CxxFrameHandler"}
    done = set()
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        if entry.dll.lower() != b"msvcr70.dll":
            sys.exit(f"unexpected import DLL {entry.dll}")
        for imp in entry.imports:
            if imp.name in renames:
                off = data.find(imp.name + b"\0")        # the name of the hint/name entry (unique in this DLL)
                if off < 0 or data.find(imp.name + b"\0", off + 1) >= 0:
                    sys.exit(f"import name {imp.name} not found exactly once")
                new = renames[imp.name]
                data[off:off + len(imp.name)] = new + b"\0" * (len(imp.name) - len(new))
                done.add(imp.name)
                print(f"import {imp.name.decode()} -> {new.decode()}")
    if done != set(renames):
        sys.exit(f"imports not found: {set(renames) - done}")
    # FuncInfo records referenced by handler thunks: B8 <FuncInfo> E9 <rel32> | FF 25 <IAT>
    text = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
    base = pe.OPTIONAL_HEADER.ImageBase
    tstart, tend = text.PointerToRawData, text.PointerToRawData + text.SizeOfRawData
    patched = 0
    for i in range(tstart, tend - 10):
        if data[i] == 0xB8 and data[i + 5] in (0xE9, 0xFF):
            fi = struct.unpack_from("<I", data, i + 1)[0]
            rva = fi - base
            try:
                off = pe.get_offset_from_rva(rva)
            except Exception:  # noqa: BLE001 - not an address inside the image
                continue
            if off is None or off + 4 > len(data):
                continue
            magic = struct.unpack_from("<I", data, off)[0]
            if magic == 0x19930522:
                struct.pack_into("<I", data, off, 0x19930520)
                patched += 1
                print(f"FuncInfo {fi:#x} (thunk at file offset {i:#x}): magic 0x19930522 -> 0x19930520")
            elif magic == 0x19930520:
                pass
    left = sum(1 for k in range(0, len(data) - 4, 4) if struct.unpack_from("<I", data, k)[0] == 0x19930522)
    if not patched or left:
        sys.exit(f"patched {patched} FuncInfo records, {left} unpatched 0x19930522 values remain")
    pe.close()
    with open(path, "wb") as f:
        f.write(data)
    print(f"patched {patched} FuncInfo records")


if __name__ == "__main__":
    main()
