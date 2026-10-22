// Package loading and linking for Unreal II v110 packages.
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <fstream>
#include <iterator>

#include "uvm.h"

namespace uvm {

// ---------------------------------------------------------------- names
namespace {
struct NameStore {
    std::vector<std::string> strs;
    std::unordered_map<std::string, int> index;  // lower-case key
};
NameStore& store() {
    static NameStore s;
    if (s.strs.empty()) { s.strs.push_back("None"); s.index["none"] = 0; }
    return s;
}
std::string lower(std::string s) {
    for (auto& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}
}  // namespace

int Names::intern(const std::string& s) {
    auto& st = store();
    auto key = lower(s);
    auto it = st.index.find(key);
    if (it != st.index.end()) return it->second;
    int idx = static_cast<int>(st.strs.size());
    st.strs.push_back(s);
    st.index[key] = idx;
    return idx;
}
const std::string& Names::str(int idx) { return store().strs.at(static_cast<size_t>(idx)); }
int Names::none() { return 0; }

std::string Object::fullName() const {
    std::string n = name;
    for (Object* o = outer; o; o = o->outer) n = o->name + "." + n;
    return n;
}

// ---------------------------------------------------------------- reader
int32_t Reader::compact() {
    uint8_t b0 = u8();
    int32_t v = b0 & 0x3F;
    if (b0 & 0x40) {
        int shift = 6;
        for (;;) {
            uint8_t b = u8();
            v |= static_cast<int32_t>(b & 0x7F) << shift;
            shift += 7;
            if (!(b & 0x80) || shift > 27) break;
        }
    }
    return (b0 & 0x80) ? -v : v;
}

std::string Reader::fstring() {
    int32_t n = compact();
    std::string out;
    if (n > 0) {
        need(static_cast<size_t>(n));
        out.assign(reinterpret_cast<const char*>(p + pos), static_cast<size_t>(n));
        pos += static_cast<size_t>(n);
        if (!out.empty() && out.back() == '\0') out.pop_back();
    } else if (n < 0) {
        // UTF-16 string: keep the low byte (all probe/test strings are Latin-1).
        for (int32_t k = 0; k < -n; ++k) {
            uint16_t ch = u16();
            if (ch) out.push_back(static_cast<char>(ch < 256 ? ch : '?'));
        }
    }
    return out;
}

// ---------------------------------------------------------------- package
std::string Package::className(const ExportEntry& e) const {
    if (e.classRef == 0) return "Class";
    if (e.classRef < 0) return Names::str(imports[static_cast<size_t>(-e.classRef - 1)].name);
    return Names::str(exports[static_cast<size_t>(e.classRef - 1)].name);
}

int Package::outermostImport(int ref) const {
    const ImportEntry* imp = &imports[static_cast<size_t>(-ref - 1)];
    while (imp->outer < 0) imp = &imports[static_cast<size_t>(-imp->outer - 1)];
    return imp->name;
}

Package* Linker::load(const std::string& name) {
    auto key = lower(name);
    auto it = packages.find(key);
    if (it != packages.end()) return it->second.get();
    auto pkg = std::make_unique<Package>();
    pkg->name = name;
    pkg->linker = this;
    std::ifstream f(systemDir + "/" + name + ".u", std::ios::binary);
    if (!f) throw std::runtime_error("cannot open package " + name + ".u in " + systemDir);
    pkg->data.assign(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
    Reader r{pkg->data.data(), 0, pkg->data.size()};
    if (r.u32() != 0x9E2A83C1u) throw std::runtime_error("bad package tag: " + name);
    uint32_t ver = r.u32();
    pkg->version = ver & 0xFFFF;
    pkg->licensee = static_cast<uint16_t>(ver >> 16);
    if (pkg->version != 110) throw std::runtime_error("unsupported package version in " + name);
    r.u32();  // package flags
    int32_t nc = r.i32(), no = r.i32(), ec = r.i32(), eo = r.i32(), ic = r.i32(), io = r.i32();
    r.pos = static_cast<size_t>(no);
    for (int32_t k = 0; k < nc; ++k) {
        pkg->names.push_back(Names::intern(r.fstring()));
        r.u32();  // name flags
    }
    r.pos = static_cast<size_t>(io);
    for (int32_t k = 0; k < ic; ++k) {
        ImportEntry e{};
        e.classPackage = pkg->names.at(static_cast<size_t>(r.compact()));
        e.className = pkg->names.at(static_cast<size_t>(r.compact()));
        e.outer = r.i32();
        e.name = pkg->names.at(static_cast<size_t>(r.compact()));
        pkg->imports.push_back(e);
    }
    r.pos = static_cast<size_t>(eo);
    for (int32_t k = 0; k < ec; ++k) {
        ExportEntry e{};
        e.classRef = r.compact();
        e.superRef = r.compact();
        e.outer = r.i32();
        e.name = pkg->names.at(static_cast<size_t>(r.compact()));
        e.flags = r.u32();
        e.size = r.compact();
        e.offset = e.size > 0 ? r.compact() : 0;
        pkg->exports.push_back(e);
    }
    Package* raw = pkg.get();
    packages[key] = std::move(pkg);
    if (verbose) std::fprintf(stderr, "loaded %s: %d names %d imports %d exports\n", name.c_str(), nc, ic, ec);
    return raw;
}

Object* Linker::resolve(Package* pkg, int ref) {
    if (ref == 0) return nullptr;
    if (ref > 0) return loadExport(pkg, ref);
    const ImportEntry& imp = pkg->imports.at(static_cast<size_t>(-ref - 1));
    if (imp.outer == 0) return nullptr;  // a package object itself: not materialised
    // Collect the path below the top-level package.
    std::vector<int> path;
    const ImportEntry* cur = &imp;
    path.push_back(cur->name);
    while (cur->outer < 0) {
        const ImportEntry* o = &pkg->imports.at(static_cast<size_t>(-cur->outer - 1));
        if (o->outer == 0) break;
        path.push_back(o->name);
        cur = o;
    }
    std::reverse(path.begin(), path.end());
    Package* target = load(Names::str(pkg->outermostImport(ref)));
    // Find the export whose outer chain matches the path and whose class matches.
    for (size_t k = 0; k < target->exports.size(); ++k) {
        const ExportEntry& e = target->exports[k];
        if (e.name != path.back()) continue;
        if (Names::str(e.name) != Names::str(path.back())) continue;
        int outer = e.outer;
        bool ok = true;
        for (size_t d = path.size() - 1; d-- > 0;) {
            if (outer <= 0 || target->exports[static_cast<size_t>(outer - 1)].name != path[d]) { ok = false; break; }
            outer = target->exports[static_cast<size_t>(outer - 1)].outer;
        }
        if (!ok || outer != 0) continue;
        if (Names::intern(target->className(e)) != imp.className) continue;
        return loadExport(target, static_cast<int>(k + 1));
    }
    // C++-only ("intrinsic") classes such as Core.Class or Engine.Level have no
    // script export; the original DLLs register them at startup. Synthesize them.
    if (Names::str(imp.className) == "Class" && path.size() == 1) {
        std::string key = lower(target->name) + "." + lower(Names::str(imp.name));
        auto it = intrinsics.find(key);
        if (it != intrinsics.end()) return it->second;
        auto c = std::make_unique<Class>();
        c->name = Names::str(imp.name);
        c->linked = true;
        c->defaults.push_back(Value());
        Class* raw = c.get();
        owned.push_back(std::move(c));
        intrinsics[key] = raw;
        if (verbose) std::fprintf(stderr, "intrinsic class %s.%s synthesized\n", target->name.c_str(), raw->name.c_str());
        return raw;
    }
    throw std::runtime_error("unresolved import " + Names::str(imp.className) + " " + Names::str(imp.name) +
                             " in package " + Names::str(pkg->outermostImport(ref)));
}

namespace {
constexpr uint32_t CPF_Net = 0x20, CPF_Parm = 0x80, CPF_ReturnParm = 0x400;
constexpr uint32_t RF_HasStack = 0x02000000;

PropKind kindFromClassName(const std::string& c) {
    if (c == "ByteProperty") return PropKind::Byte;
    if (c == "IntProperty") return PropKind::Int;
    if (c == "BoolProperty") return PropKind::Bool;
    if (c == "FloatProperty") return PropKind::Float;
    if (c == "ObjectProperty") return PropKind::Object;
    if (c == "ClassProperty") return PropKind::Class;
    if (c == "NameProperty") return PropKind::Name;
    if (c == "StrProperty") return PropKind::Str;
    if (c == "StructProperty") return PropKind::Struct;
    if (c == "ArrayProperty") return PropKind::Array;
    return PropKind::Unknown;
}
}  // namespace

Object* Linker::loadExport(Package* pkg, int index) {
    ExportEntry& e = pkg->exports.at(static_cast<size_t>(index - 1));
    if (e.object) return e.object;
    return create(pkg, index);
}

Object* Linker::create(Package* pkg, int index) {
    ExportEntry& e = pkg->exports.at(static_cast<size_t>(index - 1));
    std::string cls = pkg->className(e);
    std::unique_ptr<Object> obj;
    PropKind pk = kindFromClassName(cls);
    if (cls == "Class") obj = std::make_unique<Class>();
    else if (cls == "Function") obj = std::make_unique<Function>();
    else if (cls == "State") obj = std::make_unique<State>();
    else if (cls == "Struct") obj = std::make_unique<Struct>();
    else if (pk != PropKind::Unknown) obj = std::make_unique<Property>();
    else obj = std::make_unique<Object>();   // Enum, Const, TextBuffer, content objects: opaque
    Object* o = obj.get();
    owned.push_back(std::move(obj));
    e.object = o;
    o->name = Names::str(e.name);
    if (e.outer > 0) {
        o->outer = loadExport(pkg, e.outer);
    } else {
        if (!pkg->packageObject) {
            auto po = std::make_unique<Object>();
            po->name = pkg->name;
            pkg->packageObject = po.get();
            owned.push_back(std::move(po));
        }
        o->outer = pkg->packageObject;
    }

    if (e.size <= 0) return o;
    Reader r{pkg->data.data(), static_cast<size_t>(e.offset), static_cast<size_t>(e.offset + e.size)};
    if (e.flags & RF_HasStack) {
        int node = r.compact();
        r.compact();
        r.u64();
        r.i32();
        if (node) r.compact();
    }
    auto skipTagged = [&](Reader& rr) {
        for (;;) {
            int nm = rr.compact();
            if (pkg->names.at(static_cast<size_t>(nm)) == Names::none()) return;
            uint8_t info = rr.u8();
            int type = info & 0x0F, sc = (info >> 4) & 7;
            if (type == 10) rr.compact();
            static const int sizes[5] = {1, 2, 4, 12, 16};
            int size = sc < 5 ? sizes[sc] : sc == 5 ? rr.u8() : sc == 6 ? rr.u16() : rr.i32();
            if ((info & 0x80) && type != 3) {
                uint8_t b0 = rr.u8();
                if (b0 & 0x80) { rr.u8(); if (b0 & 0x40) { rr.u8(); rr.u8(); } }
            }
            rr.pos += static_cast<size_t>(size);
        }
    };

    if (dynamic_cast<Class*>(o)) {
        int n = r.compact();
        for (int k = 0; k < n; ++k) r.compact();   // Unreal II class prefix ref list
    } else {
        skipTagged(r);
    }

    if (auto* s = dynamic_cast<Struct*>(o)) {
        int superRef = r.compact();
        s->srcPkg = pkg;
        s->nextRef = r.compact();
        r.compact();                       // ScriptText
        s->childrenRef = r.compact();
        r.compact();                       // FriendlyName
        r.i32(); r.i32();                  // Line, TextPos
        r.i32();                           // Unreal II extra int
        uint32_t scriptSize = r.u32();
        s->scriptSize = scriptSize;
        s->superStruct = dynamic_cast<Struct*>(resolve(pkg, superRef));
        parseScript(pkg, r, s, scriptSize);
        if (auto* f = dynamic_cast<Function*>(o)) {
            f->nativeIndex = r.u16();
            r.u8();                        // operator precedence
            f->funcFlags = r.u32();
            if (f->funcFlags & 0x40) r.u16();
        }
        if (dynamic_cast<State*>(o)) {
            r.u64(); r.u64(); r.u16(); r.u32();
        }
        if (auto* c = dynamic_cast<Class*>(o)) {
            c->pkg = pkg;
            c->linker = this;
            c->classFlags = r.u32();
            r.pos += 16;                   // GUID
            int deps = r.compact();
            for (int k = 0; k < deps; ++k) { r.compact(); r.u32(); r.u32(); }
            int imps = r.compact();
            for (int k = 0; k < imps; ++k) r.compact();
            r.compact();                   // ClassWithin
            r.compact();                   // ClassConfigName
            int hide = r.compact();
            for (int k = 0; k < hide; ++k) r.compact();
            c->pendingDefaults.push_back({pkg, r.pos, r.end});
            c->cls = nullptr;
        }
    } else if (auto* p = dynamic_cast<Property*>(o)) {
        p->kind = pk;
        r.compact();                       // SuperField
        p->srcPkg = pkg;
        p->nextRef = r.compact();
        p->arrayDim = r.i32();
        p->flags = r.u32();
        r.compact();                       // Category
        if (p->flags & CPF_Net) r.u16();
        if (p->flags & 0x02000000) r.fstring();
        if (p->flags & 0x40000000) { r.i32(); r.i32(); r.i32(); }
        switch (pk) {
            case PropKind::Byte: r.compact(); break;  // enum
            case PropKind::Object: p->objClass = dynamic_cast<Class*>(resolve(pkg, r.compact())); break;
            case PropKind::Class:
                p->objClass = dynamic_cast<Class*>(resolve(pkg, r.compact()));
                resolve(pkg, r.compact());
                break;
            case PropKind::Struct: p->structType = dynamic_cast<Struct*>(resolve(pkg, r.compact())); break;
            case PropKind::Array: p->inner = dynamic_cast<Property*>(resolve(pkg, r.compact())); break;
            default: break;
        }
    }
    if (r.pos != r.end && dynamic_cast<Field*>(o) && !dynamic_cast<Class*>(o))
        throw std::runtime_error("object layout mismatch for " + o->fullName());
    return o;
}

// ---------------------------------------------------------------- script decoding
namespace {
struct ScriptDecoder {
    Linker& L;
    Package* pkg;
    Reader& r;
    uint32_t size;
    uint32_t mem = 0;

    uint8_t b() { mem += 1; return r.u8(); }
    uint16_t w() { mem += 2; return r.u16(); }
    int32_t i() { mem += 4; return r.i32(); }
    float f() { mem += 4; return r.f32(); }
    Object* obj() { mem += 4; return L.resolve(pkg, r.compact()); }
    int name() { mem += 4; return pkg->names.at(static_cast<size_t>(r.compact())); }
    std::string zstr() {
        std::string s;
        for (;;) { char c = static_cast<char>(r.u8()); ++mem; if (!c) break; s.push_back(c); }
        return s;
    }
    std::string wzstr() {
        std::string s;
        for (;;) { uint16_t c = r.u16(); mem += 2; if (!c) break; s.push_back(static_cast<char>(c < 256 ? c : '?')); }
        return s;
    }
    void params(Token& t) {
        for (;;) {
            t.kids.push_back(expr());
            if (t.kids.back().op == 0x16) return;
        }
    }
    Token expr() {
        if (mem >= size) throw std::runtime_error("bytecode overrun");
        Token t;
        t.mem = static_cast<uint16_t>(mem);
        uint8_t op = b();
        t.op = op;
        if (op >= 0x60) {
            t.a = op >= 0x70 ? op : ((op - 0x60) << 8) | b();
            params(t);
            t.end = static_cast<uint16_t>(mem);
            return t;
        }
        switch (op) {
            case 0x00: case 0x01: case 0x02: case 0x29: case 0x20: t.obj = obj(); break;
            case 0x04: case 0x0D: case 0x0E: case 0x2D: case 0x37: t.kids.push_back(expr()); break;
            case 0x05: t.a = b(); t.kids.push_back(expr()); break;
            case 0x06: t.a = w(); break;
            case 0x07: t.a = w(); t.kids.push_back(expr()); break;
            case 0x09: t.a = w(); t.kids.push_back(expr()); break;
            case 0x0A: t.a = w(); if (t.a != 0xFFFF) t.kids.push_back(expr()); break;
            case 0x0C:
                for (;;) { int nm = name(); i(); if (nm == Names::none()) break; }
                break;
            case 0x0F: case 0x14: case 0x10: case 0x1A:
                t.kids.push_back(expr()); t.kids.push_back(expr()); break;
            case 0x11: for (int k = 0; k < 4; ++k) t.kids.push_back(expr()); break;
            case 0x12: case 0x19:
                t.kids.push_back(expr()); t.a = w(); t.b = b(); t.kids.push_back(expr()); break;
            case 0x13: case 0x2E: t.obj = obj(); t.kids.push_back(expr()); break;
            case 0x15: t.a = w(); t.kids.push_back(expr()); break;
            case 0x08: case 0x0B: case 0x16: case 0x17: case 0x25: case 0x26: case 0x27: case 0x28:
            case 0x2A: case 0x30: case 0x31: break;
            case 0x18: t.a = w(); t.kids.push_back(expr()); break;
            case 0x1B: case 0x38: t.name = name(); params(t); break;
            case 0x1C: t.obj = obj(); params(t); break;
            case 0x1D: t.a = i(); break;
            case 0x1E: t.f[0] = f(); break;
            case 0x1F: t.s = zstr(); break;
            case 0x21: t.name = name(); break;
            case 0x22: t.a = i(); t.b = i(); t.c = i(); break;
            case 0x23: t.f[0] = f(); t.f[1] = f(); t.f[2] = f(); break;
            case 0x24: case 0x2C: t.a = b(); break;
            case 0x2F: t.kids.push_back(expr()); t.a = w(); break;
            case 0x32: case 0x33: t.obj = obj(); t.kids.push_back(expr()); t.kids.push_back(expr()); break;
            case 0x34: t.s = wzstr(); break;
            case 0x35: t.f[0] = f(); t.f[1] = f(); break;
            case 0x36: t.obj = obj(); t.kids.push_back(expr()); break;
            case 0x39: t.a = b(); t.kids.push_back(expr()); break;
            case 0x40: case 0x41: for (int k = 0; k < 3; ++k) t.kids.push_back(expr()); break;
            case 0x42: t.a = i(); t.b = i(); t.c = i(); b(); break;
            default: {
                char buf[64];
                std::snprintf(buf, sizeof buf, "unknown opcode 0x%02X", op);
                throw std::runtime_error(buf);
            }
        }
        t.end = static_cast<uint16_t>(mem);
        return t;
    }
};
}  // namespace

void Linker::parseScript(Package* pkg, Reader& r, Struct* s, uint32_t scriptSize) {
    ScriptDecoder d{*this, pkg, r, scriptSize};
    while (d.mem < scriptSize) {
        s->stmtAt[static_cast<uint16_t>(d.mem)] = s->code.size();
        s->code.push_back(d.expr());
    }
    if (d.mem != scriptSize) throw std::runtime_error("script size mismatch in " + s->fullName());
}

// ---------------------------------------------------------------- linking
Field* Linker::children(Struct* s) {
    if (!s->childrenResolved) {
        s->childrenResolved = true;
        s->childField = s->srcPkg ? dynamic_cast<Field*>(resolve(s->srcPkg, s->childrenRef)) : nullptr;
    }
    return s->childField;
}

Field* Linker::next(Field* f) {
    if (!f->nextResolved) {
        f->nextResolved = true;
        f->nextField = f->srcPkg ? dynamic_cast<Field*>(resolve(f->srcPkg, f->nextRef)) : nullptr;
    }
    return f->nextField;
}

void Linker::linkStruct(Struct* s) {
    if (s->linked) return;
    s->linked = true;
    if (s->superStruct) {
        linkStruct(s->superStruct);
        s->layout = s->superStruct->layout;
        s->slotCount = s->superStruct->slotCount;
    }
    // Functions do not inherit locals from their super function.
    if (dynamic_cast<Function*>(s)) { s->layout.clear(); s->slotCount = 0; }
    auto* fn = dynamic_cast<Function*>(s);
    for (Field* f = children(s); f; f = next(f)) {
        auto* p = dynamic_cast<Property*>(f);
        if (!p) continue;
        p->slot = s->slotCount;
        s->slotCount += p->arrayDim;
        s->layout.push_back(p);
        if (p->kind == PropKind::Struct && p->structType) linkStruct(p->structType);
        if (p->kind == PropKind::Array && p->inner && p->inner->kind == PropKind::Struct && p->inner->structType)
            linkStruct(p->inner->structType);
        if (fn && (p->flags & CPF_Parm)) {
            if (p->flags & CPF_ReturnParm) fn->ret = p;
            else fn->params.push_back(p);
        }
    }
    // Nested structs/functions are linked on demand.
}

Class* Linker::findClass(const std::string& pkgName, const std::string& name) {
    Package* p = load(pkgName);
    for (size_t k = 0; k < p->exports.size(); ++k) {
        if (p->className(p->exports[k]) == "Class" && lower(Names::str(p->exports[k].name)) == lower(name)) {
            auto* c = dynamic_cast<Class*>(loadExport(p, static_cast<int>(k + 1)));
            linkStruct(c);
            applyDefaults(c);
            return c;
        }
    }
    return nullptr;
}

bool Class::isChildOf(const Class* other) const {
    for (const Struct* s = this; s; s = s->superStruct)
        if (s == other) return true;
    return false;
}

Function* Class::findFunction(const std::string& n) {
    auto key = lower(n);
    auto it = funcCache.find(key);
    if (it != funcCache.end()) return it->second;
    Function* found = nullptr;
    for (Struct* s = this; s && !found; s = s->superStruct)
        for (Field* f = linker->children(s); f; f = linker->next(f))
            if (auto* fn = dynamic_cast<Function*>(f); fn && lower(fn->name) == key) { found = fn; break; }
    funcCache[key] = found;
    return found;
}

Property* Class::findProperty(const std::string& n) {
    auto key = lower(n);
    for (Property* p : layout)
        if (lower(p->name) == key) return p;
    return nullptr;
}

}  // namespace uvm
