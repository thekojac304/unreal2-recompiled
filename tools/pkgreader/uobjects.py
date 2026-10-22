"""Object-layer parsing for Unreal II (v110, Legend licensee 1331..2609) packages.

Independent implementation. Layouts were derived from the shipped data and
checked by exact payload consumption (see validate_objects.py). Opcode set is
the one recovered from Core.dll's native registration table (natives.py).
"""
import struct

from upkg import Reader

# ---------------------------------------------------------------------------
# Function / class flags (subset used here)
FUNC_Final, FUNC_Defined, FUNC_Iterator, FUNC_Latent = 0x1, 0x2, 0x4, 0x8
FUNC_PreOperator, FUNC_Singular, FUNC_Net, FUNC_NetReliable = 0x10, 0x20, 0x40, 0x80
FUNC_Simulated, FUNC_Exec, FUNC_Native, FUNC_Event = 0x100, 0x200, 0x400, 0x800
FUNC_Operator, FUNC_Static = 0x1000, 0x2000
CPF_Net = 0x20
RF_HasStack = 0x02000000

# ---------------------------------------------------------------------------
# Script tokens (values recovered from Core.dll GNatives registrations).
EX = {
    0x00: "LocalVariable", 0x01: "InstanceVariable", 0x02: "DefaultVariable", 0x04: "Return",
    0x05: "Switch", 0x06: "Jump", 0x07: "JumpIfNot", 0x08: "Stop", 0x09: "Assert", 0x0A: "Case",
    0x0B: "Nothing", 0x0C: "LabelTable", 0x0D: "GotoLabel", 0x0E: "EatString", 0x0F: "Let",
    0x10: "DynArrayElement", 0x11: "New", 0x12: "ClassContext", 0x13: "MetaCast", 0x14: "LetBool",
    0x15: "LineNumber", 0x16: "EndFunctionParms", 0x17: "Self", 0x18: "Skip", 0x19: "Context",
    0x1A: "ArrayElement", 0x1B: "VirtualFunction", 0x1C: "FinalFunction", 0x1D: "IntConst",
    0x1E: "FloatConst", 0x1F: "StringConst", 0x20: "ObjectConst", 0x21: "NameConst",
    0x22: "RotationConst", 0x23: "VectorConst", 0x24: "ByteConst", 0x25: "IntZero", 0x26: "IntOne",
    0x27: "True", 0x28: "False", 0x29: "NativeParm", 0x2A: "NoObject", 0x2C: "IntConstByte",
    0x2D: "BoolVariable", 0x2E: "DynamicCast", 0x2F: "Iterator", 0x30: "IteratorPop",
    0x31: "IteratorNext", 0x32: "StructCmpEq", 0x33: "StructCmpNe", 0x34: "UnicodeStringConst",
    0x35: "RangeConst", 0x36: "StructMember", 0x37: "DynArrayLength", 0x38: "GlobalFunction",
    0x39: "PrimitiveCast", 0x40: "DynArrayInsert", 0x41: "DynArrayRemove", 0x42: "DebugInfo",
}
EX_EndFunctionParms = 0x16
EX_ExtendedNative = 0x60
EX_FirstNative = 0x70
PTR = 4  # in-memory size of an object pointer / FName on the original 32-bit build


class ScriptError(Exception):
    pass


class Token:
    __slots__ = ("mem", "disk", "op", "args", "children")

    def __init__(self, mem, disk, op):
        self.mem, self.disk, self.op = mem, disk, op
        self.args = []
        self.children = []


class ScriptReader:
    """Tokenises serialized UnrealScript bytecode.

    Tracks both the on-disk position and the in-memory code offset (iCode),
    because compact indices on disk expand to 4-byte pointers/names in memory.
    Jump/skip operands are in-memory offsets, which lets us self-check.
    """

    def __init__(self, r, script_size, pkg):
        self.r = r
        self.size = script_size
        self.mem = 0
        self.pkg = pkg
        self.jump_targets = []   # (from token, target mem offset)
        self.skips = []          # (token, expected mem size of skipped expr, start mem)
        self.starts = set()      # mem offsets where a token starts
        self.natives = []        # native indices called
        self.ops = []            # every opcode seen

    # primitive operand readers (advance disk + mem)
    def b(self):
        self.mem += 1
        return self.r.u8()

    def w(self):
        self.mem += 2
        return self.r.u16()

    def i(self):
        self.mem += 4
        return self.r.i32()

    def f(self):
        self.mem += 4
        return self.r.f32()

    def obj(self):
        self.mem += PTR
        return self.r.compact()

    def name(self):
        self.mem += PTR
        idx = self.r.compact()
        if not 0 <= idx < len(self.pkg.names):
            raise ScriptError(f"bad name index {idx}")
        return self.pkg.names[idx]

    def zstr(self):
        start = self.r.pos
        end = self.r.data.index(b"\0", start)
        self.r.pos = end + 1
        self.mem += end + 1 - start
        return self.r.data[start:end].decode("latin1")

    def wzstr(self):
        start = self.r.pos
        while self.r.data[self.r.pos:self.r.pos + 2] != b"\0\0":
            self.r.pos += 2
        self.r.pos += 2
        self.mem += self.r.pos - start
        return self.r.data[start:self.r.pos - 2].decode("utf-16le")

    # ------------------------------------------------------------------
    def read_all(self):
        tokens = []
        while self.mem < self.size:
            tokens.append(self.expr())
        if self.mem != self.size:
            raise ScriptError(f"script overran: mem {self.mem} != size {self.size}")
        for tok, target in self.jump_targets:
            if target != 0xFFFF and target not in self.starts and target != self.size:
                raise ScriptError(f"jump from {tok.mem} ({EX.get(tok.op, tok.op)}) to {target}: not a token boundary")
        return tokens

    def params(self, tok):
        while True:
            t = self.expr()
            tok.children.append(t)
            if t.op == EX_EndFunctionParms:
                return

    def expr(self):
        if self.mem >= self.size:
            raise ScriptError(f"expression expected past end at mem {self.mem}")
        tok = Token(self.mem, self.r.pos, None)
        self.starts.add(self.mem)
        op = self.b()
        tok.op = op
        self.ops.append(op)
        a, c = tok.args, tok.children
        if op >= EX_FirstNative or EX_ExtendedNative <= op < EX_FirstNative:
            idx = op if op >= EX_FirstNative else ((op - EX_ExtendedNative) << 8) | self.b()
            a.append(idx)
            self.natives.append(idx)
            self.params(tok)
        elif op in (0x00, 0x01, 0x02, 0x29, 0x20):          # variables / NativeParm / ObjectConst
            a.append(self.obj())
        elif op == 0x04 or op in (0x0D, 0x0E, 0x2D, 0x37):  # Return, GotoLabel, EatString, BoolVariable, DynArrayLength
            c.append(self.expr())
        elif op == 0x05:                                     # Switch: size byte + expr
            a.append(self.b())
            c.append(self.expr())
        elif op == 0x06:                                     # Jump
            target = self.w()
            a.append(target)
            self.jump_targets.append((tok, target))
        elif op == 0x07:                                     # JumpIfNot
            target = self.w()
            a.append(target)
            self.jump_targets.append((tok, target))
            c.append(self.expr())
        elif op == 0x09:                                     # Assert: line + expr
            a.append(self.w())
            c.append(self.expr())
        elif op == 0x0A:                                     # Case
            nxt = self.w()
            a.append(nxt)
            if nxt != 0xFFFF:
                self.jump_targets.append((tok, nxt))
                c.append(self.expr())
        elif op == 0x0C:                                     # LabelTable
            while True:
                label = self.name()
                where = self.i()
                a.append((label, where))
                if label == "None":
                    break
                self.jump_targets.append((tok, where))
        elif op in (0x0F, 0x14, 0x10, 0x1A):                 # Let, LetBool, DynArrayElement, ArrayElement
            c.append(self.expr())
            c.append(self.expr())
        elif op == 0x11:                                     # New
            for _ in range(4):
                c.append(self.expr())
        elif op in (0x12, 0x19):                             # ClassContext / Context
            c.append(self.expr())
            skip = self.w()
            size = self.b()
            a += [skip, size]
            start = self.mem
            c.append(self.expr())
            self.skips.append((tok, skip, start, self.mem))
        elif op in (0x13, 0x2E):                             # MetaCast / DynamicCast
            a.append(self.obj())
            c.append(self.expr())
        elif op == 0x15:                                     # LineNumber: word line + expr
            a.append(self.w())
            c.append(self.expr())
        elif op in (0x16, 0x17, 0x08, 0x0B, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x30, 0x31):
            pass                                             # no operands
        elif op == 0x18:                                     # Skip
            skip = self.w()
            a.append(skip)
            start = self.mem
            c.append(self.expr())
            self.skips.append((tok, skip, start, self.mem))
        elif op == 0x1B or op == 0x38:                       # VirtualFunction / GlobalFunction
            a.append(self.name())
            self.params(tok)
        elif op == 0x1C:                                     # FinalFunction
            a.append(self.obj())
            self.params(tok)
        elif op == 0x1D:
            a.append(self.i())
        elif op == 0x1E:
            a.append(self.f())
        elif op == 0x1F:
            a.append(self.zstr())
        elif op == 0x21:
            a.append(self.name())
        elif op == 0x22:
            a += [self.i(), self.i(), self.i()]
        elif op == 0x23:
            a += [self.f(), self.f(), self.f()]
        elif op in (0x24, 0x2C):
            a.append(self.b())
        elif op == 0x2F:                                     # Iterator: expr + end offset
            c.append(self.expr())
            target = self.w()
            a.append(target)
            self.jump_targets.append((tok, target))
        elif op in (0x32, 0x33):                             # StructCmpEq/Ne
            a.append(self.obj())
            c.append(self.expr())
            c.append(self.expr())
        elif op == 0x34:
            a.append(self.wzstr())
        elif op == 0x35:                                     # RangeConst: two floats
            a += [self.f(), self.f()]
        elif op == 0x36:                                     # StructMember: property + struct expr
            a.append(self.obj())
            c.append(self.expr())
        elif op == 0x39:                                     # PrimitiveCast
            a.append(self.b())
            c.append(self.expr())
        elif op in (0x40, 0x41):                             # DynArrayInsert / Remove
            for _ in range(3):
                c.append(self.expr())
        elif op == 0x42:                                     # DebugInfo
            a += [self.i(), self.i(), self.i(), self.b()]
        else:
            raise ScriptError(f"unknown opcode 0x{op:02X} at mem {tok.mem} disk {tok.disk}")
        return tok

    def check_skips(self):
        """Context skip == size of the guarded expression. EX_Skip (short-circuit
        operand of && / ||) also covers the EX_EndFunctionParms that follows it."""
        bad = []
        data = self.r.data
        for tok, skip, start, end in self.skips:
            expected = end - start
            if tok.op == 0x18:
                expected += 1
            if skip != expected:
                bad.append((tok.mem, EX.get(tok.op), skip, expected))
        return bad


# ---------------------------------------------------------------------------
class ObjectParser:
    """Parses field objects (Class/State/Function/Struct/properties/Enum/Const/TextBuffer)."""

    PROPERTY_EXTRA = {
        "ByteProperty": ("obj",), "ObjectProperty": ("obj",), "ClassProperty": ("obj", "obj"),
        "StructProperty": ("obj",), "ArrayProperty": ("obj",), "FixedArrayProperty": ("obj", "i32"),
        "MapProperty": ("obj", "obj"), "IntProperty": (), "FloatProperty": (), "BoolProperty": (),
        "NameProperty": (), "StrProperty": (), "StringProperty": ("i32",), "PointerProperty": (),
    }

    def __init__(self, pkg, layout=None):
        self.pkg = pkg
        self.layout = layout or {}

    def parse(self, exp):
        cls = self.pkg.class_name_of(exp)
        r = Reader(self.pkg.data, exp.offset)
        end = exp.offset + exp.size
        out = {"class": cls, "name": exp.name}
        self.object_header(r, exp, out)
        if cls == "Class":
            self.class_(r, out)
        elif cls == "State":
            self.state(r, out)
        elif cls == "Function":
            self.function(r, out)
        elif cls == "Struct":
            self.struct(r, out)
        elif cls in self.PROPERTY_EXTRA:
            self.property(r, out, cls)
        elif cls == "Enum":
            self.field(r, out)
            out["values"] = [self.pkg.names[r.compact()] for _ in range(r.compact())]
        elif cls == "Const":
            self.field(r, out)
            out["value"] = r.fstring()
        elif cls == "TextBuffer":
            out["pos"], out["top"] = r.i32(), r.i32()
            out["text"] = r.fstring()
        else:
            raise ValueError(f"not a field class: {cls}")
        out["consumed"] = r.pos - exp.offset
        out["exact"] = r.pos == end
        return out

    def object_header(self, r, exp, out):
        if exp.flags & RF_HasStack:
            node = r.compact()
            out["stack"] = {"node": node, "state_node": r.compact(), "probe_mask": r.u64(),
                            "latent": r.i32()}
            if node != 0:
                out["stack"]["offset"] = r.compact()
        if self.pkg.class_name_of(exp) == "Class":
            # Unreal II specific: a UClass starts with a counted list of object
            # references (observed: properties, e.g. Pickup -> Actor.bHidden,
            # Actor.Rotation, Actor.Velocity), not a tagged-property block.
            out["class_prefix_refs"] = [r.compact() for _ in range(r.compact())]
        else:
            out["props"] = self.tagged_properties(r)

    def tagged_properties(self, r):
        props = []
        while True:
            name = self.pkg.names[r.compact()]
            if name == "None":
                return props
            info = r.u8()
            ptype, size_code, flag = info & 0x0F, (info >> 4) & 0x07, bool(info & 0x80)
            struct_name = self.pkg.names[r.compact()] if ptype == 10 else None
            size = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(size_code)
            if size_code == 5:
                size = r.u8()
            elif size_code == 6:
                size = r.u16()
            elif size_code == 7:
                size = r.i32()
            index = 0
            if flag and ptype != 3:
                b0 = r.u8()
                if b0 & 0x80 == 0:
                    index = b0
                elif b0 & 0xC0 == 0x80:
                    index = ((b0 & 0x7F) << 8) | r.u8()
                else:
                    index = ((b0 & 0x3F) << 24) | (r.u8() << 16) | (r.u8() << 8) | r.u8()
            value = r.bytes(size)
            props.append({"name": name, "type": ptype, "size": size, "index": index,
                          "bool": flag if ptype == 3 else None, "struct": struct_name, "raw": value})

    def field(self, r, out):
        out["super_field"] = r.compact()
        out["next"] = r.compact()

    def struct(self, r, out, is_function=False):
        self.field(r, out)
        out["script_text"] = r.compact()
        out["children"] = r.compact()
        out["friendly_name"] = self.pkg.names[r.compact()]
        out["line"] = r.i32()
        out["text_pos"] = r.i32()
        out["legend_unk"] = r.i32()       # extra int seen in every Unreal II struct (meaning TBD)
        size = r.i32()
        out["script_size"] = size
        out["script_disk_start"] = r.pos
        sr = ScriptReader(r, size, self.pkg)
        out["tokens"] = sr.read_all() if size else []
        out["script_disk_size"] = r.pos - out["script_disk_start"]
        out["natives_called"] = sr.natives
        out["ops"] = sr.ops
        out["bad_skips"] = sr.check_skips()

    def function(self, r, out):
        self.struct(r, out, True)
        out["native_index"] = r.u16()
        out["oper_precedence"] = r.u8()
        flags = r.u32()
        out["function_flags"] = flags
        if flags & FUNC_Net:
            out["rep_offset"] = r.u16()

    def state(self, r, out):
        self.struct(r, out)
        out["probe_mask"] = r.u64()
        out["ignore_mask"] = r.u64()
        out["label_table_offset"] = r.u16()
        out["state_flags"] = r.u32()

    def class_(self, r, out):
        self.state(r, out)
        out["class_flags"] = r.u32()
        out["guid"] = r.bytes(16).hex()
        deps = []
        for _ in range(r.compact()):
            deps.append((r.compact(), r.u32(), r.u32()))
        out["dependencies"] = deps
        out["package_imports"] = [self.pkg.names[r.compact()] for _ in range(r.compact())]
        out["within"] = r.compact()
        out["config_name"] = self.pkg.names[r.compact()]
        if self.layout.get("hide_categories", True):
            out["hide_categories"] = [self.pkg.names[r.compact()] for _ in range(r.compact())]
        out["defaults"] = self.tagged_properties(r)

    def property(self, r, out, cls):
        self.field(r, out)
        out["array_dim"] = r.i32()
        out["property_flags"] = r.u32()
        out["category"] = self.pkg.names[r.compact()]
        if out["property_flags"] & CPF_Net:
            out["rep_offset"] = r.u16()
        # Unreal II additions, established by flag/trailing-byte correlation over all packages:
        if out["property_flags"] & 0x02000000:      # description string (e.g. U2ZoneInfo.LocationDescription)
            out["description"] = r.fstring()
        if out["property_flags"] & 0x40000000:      # three ints, e.g. Pawn.Health = (0, 255, 1)
            out["legend_range"] = (r.i32(), r.i32(), r.i32())
        extra = []
        for kind in self.PROPERTY_EXTRA[cls]:
            extra.append(r.compact() if kind == "obj" else r.i32())
        out["extra"] = extra
