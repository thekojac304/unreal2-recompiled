"""Independent reader for Unreal II (Legend UE2 branch) packages.

Written from scratch for this investigation; no Epic/Legend source used.
Handles the table layer (header, names, imports, exports) for package
versions 83..126 seen in the Unreal II install. Object payload parsing lives
in uobjects.py.
"""
import os
import struct

PKG_TAG = 0x9E2A83C1


class Reader:
    """Little-endian cursor over a bytes object."""

    __slots__ = ("data", "pos")

    def __init__(self, data, pos=0):
        self.data = data
        self.pos = pos

    def u8(self):
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.data, self.pos)[0]
        self.pos += 8
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return v

    def bytes(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError(f"read of {n} bytes at {self.pos} past end {len(self.data)}")
        v = self.data[self.pos:self.pos + n]
        self.pos += n
        return v

    def compact(self):
        """FCompactIndex: sign bit + 6 bits, then 7-bit continuation groups."""
        b0 = self.u8()
        value = b0 & 0x3F
        if b0 & 0x40:
            shift = 6
            while True:
                b = self.u8()
                value |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80) or shift > 27:
                    break
        return -value if b0 & 0x80 else value

    def fstring(self):
        n = self.compact()
        if n == 0:
            return ""
        if n > 0:
            raw = self.bytes(n)
            return raw[:-1].decode("latin1") if raw[-1:] == b"\0" else raw.decode("latin1")
        raw = self.bytes(-n * 2)
        s = raw.decode("utf-16le")
        return s[:-1] if s.endswith("\0") else s


class Import:
    __slots__ = ("class_package", "class_name", "outer", "name", "index")

    def __repr__(self):
        return f"Import({self.class_package}.{self.class_name} {self.name})"


class Export:
    __slots__ = ("class_ref", "super_ref", "outer", "name", "flags", "size", "offset", "index", "table_pos")

    def __repr__(self):
        return f"Export({self.name} size={self.size} off={self.offset})"


class Package:
    def __init__(self, path, data=None):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.data = data if data is not None else open(path, "rb").read()
        r = Reader(self.data)
        tag = r.u32()
        if tag != PKG_TAG:
            raise ValueError(f"{path}: bad tag {tag:08x}")
        ver = r.u32()
        self.version, self.licensee = ver & 0xFFFF, ver >> 16
        self.flags = r.u32()
        self.name_count, self.name_offset = r.i32(), r.i32()
        self.export_count, self.export_offset = r.i32(), r.i32()
        self.import_count, self.import_offset = r.i32(), r.i32()
        self.guid = None
        self.generations = []
        if self.version >= 68:
            self.guid = r.bytes(16)
            for _ in range(r.i32()):
                self.generations.append((r.i32(), r.i32()))
        self.header_end = r.pos
        self._read_names()
        self._read_imports()
        self._read_exports()

    # -- tables -----------------------------------------------------------
    def _read_names(self):
        r = Reader(self.data, self.name_offset)
        self.names = []
        self.name_flags = []
        for _ in range(self.name_count):
            if self.version >= 64:
                s = r.fstring()
            else:
                end = self.data.index(b"\0", r.pos)
                s = self.data[r.pos:end].decode("latin1")
                r.pos = end + 1
            self.names.append(s)
            self.name_flags.append(r.u32())
        self.names_end = r.pos

    def _read_imports(self):
        r = Reader(self.data, self.import_offset)
        self.imports = []
        for i in range(self.import_count):
            imp = Import()
            imp.class_package = self.names[r.compact()]
            imp.class_name = self.names[r.compact()]
            imp.outer = r.i32()
            imp.name = self.names[r.compact()]
            imp.index = -(i + 1)
            self.imports.append(imp)
        self.imports_end = r.pos

    def _read_exports(self):
        r = Reader(self.data, self.export_offset)
        self.exports = []
        for i in range(self.export_count):
            e = Export()
            e.table_pos = r.pos
            e.class_ref = r.compact()
            e.super_ref = r.compact()
            e.outer = r.i32()
            e.name = self.names[r.compact()]
            e.flags = r.u32()
            e.size = r.compact()
            e.offset = r.compact() if e.size > 0 else 0
            e.index = i + 1
            self.exports.append(e)
        self.exports_end = r.pos

    # -- references -------------------------------------------------------
    def obj(self, ref):
        if ref > 0:
            return self.exports[ref - 1]
        if ref < 0:
            return self.imports[-ref - 1]
        return None

    def class_name_of(self, exp):
        """Class name of an export ('Class' for UClass objects, ref 0)."""
        if exp.class_ref == 0:
            return "Class"
        o = self.obj(exp.class_ref)
        return o.name

    def objpath(self, ref_or_obj):
        o = self.obj(ref_or_obj) if isinstance(ref_or_obj, int) else ref_or_obj
        if o is None:
            return "None"
        parts = []
        while o is not None:
            parts.append(o.name)
            o = self.obj(o.outer)
        if isinstance(ref_or_obj, int) and ref_or_obj > 0 or isinstance(ref_or_obj, Export):
            parts.append(self.name)
        return ".".join(reversed(parts))

    def outermost(self, imp):
        o = imp
        while o.outer != 0:
            o = self.obj(o.outer)
        return o.name

    def payload(self, exp):
        return self.data[exp.offset:exp.offset + exp.size]
