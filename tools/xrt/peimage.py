"""PE32 image model for the translated runtime (X1): sections, relocation, exports, imports.

The image can be rebased: relocations are applied to a private copy of the memory
image, so decoding (lifting) and the runtime loader see identical absolute addresses.
"""
import struct

import pefile

IMAGE_REL_BASED_ABSOLUTE = 0
IMAGE_REL_BASED_HIGHLOW = 3


class PEImage:
    def __init__(self, path, base=None):
        self.path = path
        self.pe = pefile.PE(path, fast_load=False)
        self.name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self.pref_base = self.pe.OPTIONAL_HEADER.ImageBase
        self.size = self.pe.OPTIONAL_HEADER.SizeOfImage
        self.image = bytearray(self.pe.get_memory_mapped_image())
        if len(self.image) < self.size:
            self.image.extend(b"\0" * (self.size - len(self.image)))
        self.relocs = []          # RVAs of HIGHLOW fixups
        for blk in getattr(self.pe, "DIRECTORY_ENTRY_BASERELOC", []):
            for e in blk.entries:
                if e.type == IMAGE_REL_BASED_HIGHLOW:
                    self.relocs.append(e.rva)
                elif e.type != IMAGE_REL_BASED_ABSOLUTE:
                    raise ValueError(f"{self.name}: unsupported relocation type {e.type}")
        self.base = self.pref_base
        if base is not None and base != self.pref_base:
            self.rebase(base)
        self.sections = []
        for s in self.pe.sections:
            self.sections.append({"name": s.Name.rstrip(b"\0").decode(errors="replace"), "rva": s.VirtualAddress,
                                  "vsize": s.Misc_VirtualSize, "raw": s.SizeOfRawData, "flags": s.Characteristics})
        self.entry_rva = self.pe.OPTIONAL_HEADER.AddressOfEntryPoint
        self.is_dll = bool(self.pe.FILE_HEADER.Characteristics & 0x2000)
        self.exports = {}         # name -> rva
        self.export_ordinals = {} # ordinal -> rva
        self.forwarders = {}
        exp = getattr(self.pe, "DIRECTORY_ENTRY_EXPORT", None)
        if exp:
            for e in exp.symbols:
                if e.forwarder:
                    self.forwarders[e.name.decode() if e.name else f"#{e.ordinal}"] = e.forwarder.decode()
                    continue
                if e.name:
                    self.exports[e.name.decode()] = e.address
                self.export_ordinals[e.ordinal] = e.address
        self.imports = []         # (iat_rva, dll, name-or-#ordinal)
        for entry in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", []):
            dll = entry.dll.decode()
            for imp in entry.imports:
                nm = imp.name.decode() if imp.name else f"#{imp.ordinal}"
                self.imports.append((imp.address - self.pe.OPTIONAL_HEADER.ImageBase, dll, nm))
        self.iat = {self.base + rva: (dll, nm) for rva, dll, nm in self.imports}
        tls = self.pe.OPTIONAL_HEADER.DATA_DIRECTORY[9]
        self.has_tls = tls.VirtualAddress != 0

    def rebase(self, new_base):
        delta = (new_base - self.base) & 0xFFFFFFFF
        for rva in self.relocs:
            v = struct.unpack_from("<I", self.image, rva)[0]
            struct.pack_into("<I", self.image, rva, (v + delta) & 0xFFFFFFFF)
        self.base = new_base

    # ---------------------------------------------------------------- queries
    def text_ranges(self):
        return [(self.base + s["rva"], self.base + s["rva"] + s["vsize"]) for s in self.sections if s["flags"] & 0x20000000]

    def in_text(self, va):
        return any(a <= va < b for a, b in self.text_ranges())

    def in_image(self, va):
        return self.base <= va < self.base + self.size

    def u32(self, va):
        return struct.unpack_from("<I", self.image, va - self.base)[0]

    def u8(self, va):
        return self.image[va - self.base]

    def bytes_at(self, va, n):
        off = va - self.base
        return bytes(self.image[off:off + n])

    def reloc_vas(self):
        return {self.base + r for r in self.relocs}

    def reloc_targets_in_text(self):
        out = set()
        for r in self.relocs:
            v = struct.unpack_from("<I", self.image, r)[0]
            if self.in_text(v):
                out.add(v)
        return out
