// Bytecode interpreter: expression evaluation, statements, calls, defaults.
#include <cctype>
#include <chrono>
#include <cstdio>
#include <deque>
#include <functional>
#include <iostream>

#include "uvm.h"

namespace uvm {

namespace {
constexpr uint32_t CPF_OutParm = 0x100;
constexpr uint32_t FUNC_Native = 0x400;
constexpr uint8_t EX_Nothing = 0x0B, EX_EndFunctionParms = 0x16;

// Temporaries produced when an rvalue is used where a reference is needed
// (e.g. member access on a function result). Cleared per statement.
thread_local std::deque<Value> g_temps;

Value* temp(Value v) {
    g_temps.push_back(std::move(v));
    return &g_temps.back();
}

bool isCoreObjectProp(const Property* p, const char* nm) {
    const Object* owner = p->outer;
    return owner && owner->name == "Object" && owner->outer && owner->outer->name == "Core" &&
           !owner->outer->outer && p->name == nm;
}

std::string hex4(unsigned v) {
    char buf[8];
    std::snprintf(buf, sizeof buf, "%04X", v & 0xFFFF);
    return buf;
}

double elapsedSeconds() {
    static const auto start = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}
}  // namespace

Class* metaClassOf(const Object* o) { return o ? o->cls : nullptr; }

Value zeroValue(const Property* p) {
    switch (p->kind) {
        case PropKind::Byte: return Value::byte_(0);
        case PropKind::Int: return Value::int_(0);
        case PropKind::Bool: return Value::bool_(false);
        case PropKind::Float: return Value::float_(0.f);
        case PropKind::Object:
        case PropKind::Class: return Value::obj_(nullptr);
        case PropKind::Name: return Value::name_(0);
        case PropKind::Str: return Value::str_("");
        case PropKind::Struct: {
            Value v;
            v.kind = Value::Agg;
            v.strct = p->structType;
            if (p->structType) {
                v.agg.resize(static_cast<size_t>(p->structType->slotCount));
                for (Property* f : p->structType->layout)
                    for (int k = 0; k < f->arrayDim; ++k) v.agg[static_cast<size_t>(f->slot + k)] = zeroValue(f);
            }
            return v;
        }
        case PropKind::Array: {
            Value v;
            v.kind = Value::Agg;
            return v;
        }
        default: return Value();
    }
}

Value VM::zeroOf(const Property* p) const { return zeroValue(p); }

// ---------------------------------------------------------------- defaults
namespace {
bool decodeTagged(Linker& L, Package* pkg, Reader& r, const Property* p, Value& out, int size);

bool decodeBinary(Linker& L, Package* pkg, Reader& r, const Property* p, Value& out) {
    switch (p->kind) {
        case PropKind::Byte: out = Value::byte_(r.u8()); return true;
        case PropKind::Int: out = Value::int_(r.i32()); return true;
        case PropKind::Bool: out = Value::bool_(r.u32() != 0); return true;
        case PropKind::Float: out = Value::float_(r.f32()); return true;
        case PropKind::Name: out = Value::name_(pkg->names.at(static_cast<size_t>(r.compact()))); return true;
        case PropKind::Str: out = Value::str_(r.fstring()); return true;
        case PropKind::Object:
        case PropKind::Class: out = Value::obj_(L.resolve(pkg, r.compact())); return true;
        case PropKind::Struct:
            out = zeroValue(p);
            for (Property* f : p->structType->layout)
                for (int k = 0; k < f->arrayDim; ++k)
                    if (!decodeBinary(L, pkg, r, f, out.agg[static_cast<size_t>(f->slot + k)])) return false;
            return true;
        case PropKind::Array: {
            out = zeroValue(p);
            int n = r.compact();
            for (int k = 0; k < n; ++k) {
                Value e = zeroValue(p->inner);
                if (!decodeBinary(L, pkg, r, p->inner, e)) return false;
                out.agg.push_back(std::move(e));
            }
            return true;
        }
        default: return false;
    }
}

bool decodeTagged(Linker& L, Package* pkg, Reader& r, const Property* p, Value& out, int size) {
    size_t start = r.pos;
    Reader sub{r.p, r.pos, r.pos + static_cast<size_t>(size)};
    bool ok = decodeBinary(L, pkg, sub, p, out) && sub.pos == sub.end;
    r.pos = start + static_cast<size_t>(size);
    return ok;
}
}  // namespace

void Linker::applyDefaults(Class* c) {
    if (c->pendingDefaults.empty() && !c->defaults.empty()) return;
    auto* sup = dynamic_cast<Class*>(c->superStruct);
    if (sup) {
        linkStruct(sup);
        applyDefaults(sup);
    }
    c->defaults.assign(static_cast<size_t>(c->slotCount), Value());
    for (Property* p : c->layout)
        for (int k = 0; k < p->arrayDim; ++k) c->defaults[static_cast<size_t>(p->slot + k)] = zeroValue(p);
    if (sup)
        for (size_t k = 0; k < sup->defaults.size(); ++k) c->defaults[k] = sup->defaults[k];
    for (auto& raw : c->pendingDefaults) {
        Reader r{raw.pkg->data.data(), raw.pos, raw.end};
        for (;;) {
            int nm = raw.pkg->names.at(static_cast<size_t>(r.compact()));
            if (nm == Names::none()) break;
            uint8_t info = r.u8();
            int type = info & 0x0F, sc = (info >> 4) & 7;
            if (type == 10) r.compact();
            static const int sizes[5] = {1, 2, 4, 12, 16};
            int size = sc < 5 ? sizes[sc] : sc == 5 ? r.u8() : sc == 6 ? r.u16() : r.i32();
            int index = 0;
            if ((info & 0x80) && type != 3) {
                uint8_t b0 = r.u8();
                if (!(b0 & 0x80)) index = b0;
                else if (!(b0 & 0x40)) index = ((b0 & 0x7F) << 8) | r.u8();
                else { index = (b0 & 0x3F) << 24; index |= r.u8() << 16; index |= r.u8() << 8; index |= r.u8(); }
            }
            Property* p = c->findProperty(Names::str(nm));
            if (!p || index >= p->arrayDim) { r.pos += static_cast<size_t>(size); continue; }
            Value& slot = c->defaults[static_cast<size_t>(p->slot + index)];
            if (type == 3) { slot = Value::bool_((info & 0x80) != 0); r.pos += static_cast<size_t>(size); continue; }
            Value v;
            if (decodeTagged(*this, raw.pkg, r, p, v, size)) slot = std::move(v);
            else if (verbose) std::fprintf(stderr, "default %s.%s not decoded\n", c->name.c_str(), p->name.c_str());
        }
    }
    c->pendingDefaults.clear();
    if (c->defaults.empty()) c->defaults.push_back(Value());  // mark as applied
}

// ---------------------------------------------------------------- objects
Object* VM::spawnObject(Class* c, const std::string& name) {
    auto o = std::make_unique<Object>();
    o->name = name;
    o->cls = c;
    o->slots = c->defaults;
    Object* raw = o.get();
    linker.owned.push_back(std::move(o));
    return raw;
}

void VM::log(const std::string& s) {
    output.push_back("ScriptLog: " + s);
    if (echo) std::cout << s << "\n";
}

// Same layout as the original FFrame warning:
// "<Class> <Object path> (Function <Pkg.Class.Func>:<code offset>) <message>"
void VM::warn(Frame& fr, uint16_t codeOffset, const std::string& msg) {
    std::string line = (fr.self && fr.self->cls ? fr.self->cls->name : std::string("None")) + " " +
                       (fr.self ? fr.self->fullName() : std::string("None")) + " (Function " +
                       fr.func->fullName() + ":" + hex4(codeOffset) + ") " + msg;
    output.push_back("ScriptWarning: " + line);
    if (echo) std::cout << line << "\n";
}

Object* VM::newObject(Class* c, Object* outer, int name) {
    std::string nm;
    if (name && name != Names::none()) nm = Names::str(name);
    else {
        // Original naming: <ClassName><N>, N counting per class.
        static std::map<const Class*, int> counters;
        nm = c->name + std::to_string(counters[c]++);
    }
    Object* o = spawnObject(c, nm);
    o->outer = outer;
    return o;
}

// ---------------------------------------------------------------- references
Value* VM::ref(Frame& fr, Object* ctx, const Token& t, Property** propOut, bool write) {
    Property* dummy = nullptr;
    Property*& prop = propOut ? *propOut : dummy;
    switch (t.op) {
        case 0x00: {  // LocalVariable
            prop = static_cast<Property*>(t.obj);
            return &fr.locals.at(static_cast<size_t>(prop->slot));
        }
        case 0x01: {  // InstanceVariable
            prop = static_cast<Property*>(t.obj);
            if (!ctx) throw std::runtime_error("instance variable without object");
            if (isCoreObjectProp(prop, "Name")) return temp(Value::name_(Names::intern(ctx->name)));
            if (isCoreObjectProp(prop, "Class")) return temp(Value::obj_(ctx->cls));
            if (isCoreObjectProp(prop, "Outer")) return temp(Value::obj_(ctx->outer));
            if (isCoreObjectProp(prop, "ObjectFlags")) return temp(Value::int_(0));
            return &ctx->slots.at(static_cast<size_t>(prop->slot));
        }
        case 0x02: {  // DefaultVariable
            prop = static_cast<Property*>(t.obj);
            Class* c = ctx->cls ? ctx->cls : dynamic_cast<Class*>(ctx);
            return &c->defaults.at(static_cast<size_t>(prop->slot));
        }
        case 0x2D:  // BoolVariable
            return ref(fr, ctx, t.kids[0], &prop, write);
        case 0x15:  // LineNumber
            fr.line = t.a;
            return ref(fr, ctx, t.kids[0], &prop, write);
        case 0x1A: {  // ArrayElement(index, variable): static array
            int idx = eval(fr, ctx, t.kids[0]).i;
            Value* base = ref(fr, ctx, t.kids[1], &prop, write);
            if (!base) return nullptr;
            if (idx < 0 || idx >= prop->arrayDim) {
                warn(fr, t.end, "Accessed array out of bounds (" + std::to_string(idx) + "/" + std::to_string(prop->arrayDim) + ")");
                return nullptr;
            }
            return base + idx;
        }
        case 0x10: {  // DynArrayElement(index, array)
            int idx = eval(fr, ctx, t.kids[0]).i;
            Property* arrProp = nullptr;
            Value* arr = ref(fr, ctx, t.kids[1], &arrProp);
            prop = arrProp ? arrProp->inner : nullptr;
            if (!arr) return nullptr;
            if (idx < 0 || static_cast<size_t>(idx) >= arr->agg.size()) {
                // Original: only an assignment target (Result==NULL) may grow the array;
                // any other access warns and yields no address.
                if (write && idx >= 0) {
                    while (arr->agg.size() <= static_cast<size_t>(idx)) arr->agg.push_back(zeroValue(prop));
                } else {
                    warn(fr, t.end, "Accessed array '" + (arrProp ? arrProp->name : std::string("?")) + "' out of bounds (" +
                                        std::to_string(idx) + "/" + std::to_string(arr->agg.size()) + ")");
                    return nullptr;
                }
            }
            return &arr->agg[static_cast<size_t>(idx)];
        }
        case 0x36: {  // StructMember(property, struct expr): struct operand is stepped as a read
            Property* member = static_cast<Property*>(t.obj);
            Value* sv = ref(fr, ctx, t.kids[0]);
            prop = member;
            if (!sv) return nullptr;
            return &sv->agg.at(static_cast<size_t>(member->slot));
        }
        case 0x19:  // Context
        case 0x12: {
            Value objv = eval(fr, ctx, t.kids[0]);
            Object* o = objv.o;
            if (!o) {
                // Original logs before reading the skip operand: Code is just past the object expression.
                warn(fr, t.kids[0].end, "Accessed None");
                return nullptr;
            }
            return ref(fr, o, t.kids[1], &prop, write);
        }
        default:
            return temp(eval(fr, ctx, t));
    }
}

// ---------------------------------------------------------------- calls
Value VM::call(Function* f, Object* self, std::vector<Value> args, std::vector<Value*> outRefs) {
    linker.linkStruct(f);
    Frame fr{f, self, {}, nullptr};
    fr.locals.resize(static_cast<size_t>(f->slotCount));
    for (Property* p : f->layout)
        for (int k = 0; k < p->arrayDim; ++k) fr.locals[static_cast<size_t>(p->slot + k)] = zeroValue(p);
    for (size_t k = 0; k < args.size() && k < f->params.size(); ++k)
        if (args[k].kind != Value::Nil) fr.locals[static_cast<size_t>(f->params[k]->slot)] = std::move(args[k]);

    Value result = f->ret ? zeroValue(f->ret) : Value();
    const TokenList& code = f->code;
    size_t pc = 0;
    auto jump = [&](int target) {
        auto it = f->stmtAt.find(static_cast<uint16_t>(target));
        if (it == f->stmtAt.end()) throw std::runtime_error("jump into the middle of a statement in " + f->fullName());
        pc = it->second;
    };
    bool done = false;
    while (!done && pc < code.size()) {
        g_temps.clear();
        const Token* t = &code[pc];
        while (t->op == 0x15) { fr.line = t->a; t = &t->kids[0]; }  // LineNumber wrapper
        ++stepsExecuted;
        switch (t->op) {
            case 0x09:  // Assert(line, expr): the original treats a failure as a critical error
                if (!eval(fr, self, t->kids[0]).z)
                    throw std::runtime_error("Assertion failed, line " + std::to_string(t->a) + " in " + f->fullName());
                break;
            case 0x04:  // Return
                if (t->kids[0].op != EX_Nothing) result = eval(fr, self, t->kids[0]);
                else if (f->ret) result = fr.locals[static_cast<size_t>(f->ret->slot)];
                done = true;
                continue;
            case 0x06: jump(t->a); continue;
            case 0x07:
                if (!eval(fr, self, t->kids[0]).z) { jump(t->a); continue; }
                break;
            case 0x05: {  // Switch
                Value sw = eval(fr, self, t->kids[0]);
                int size = t->a;
                ++pc;
                for (;;) {
                    const Token& c = code.at(pc);
                    if (c.op != 0x0A) throw std::runtime_error("switch without case");
                    if (c.a == 0xFFFF) { ++pc; break; }  // default
                    Value cv = eval(fr, self, c.kids[0]);
                    bool eq;
                    if (size == 0) eq = sw.s == cv.s;
                    else if (sw.kind == Value::Name) eq = sw.n == cv.n;
                    else if (sw.kind == Value::Byte) eq = sw.b == cv.b;
                    else if (sw.kind == Value::Float) eq = sw.f == cv.f;
                    else eq = sw.i == cv.i;
                    if (eq) { ++pc; break; }
                    jump(c.a);
                }
                continue;
            }
            case 0x0A:  // Case reached by fall-through: evaluate (and ignore) its value
                if (t->a != 0xFFFF) eval(fr, self, t->kids[0]);
                break;
            case 0x08: done = true; continue;  // Stop
            default:
                eval(fr, self, *t);
                break;
        }
        ++pc;
    }
    for (size_t k = 0; k < outRefs.size() && k < f->params.size(); ++k)
        if (outRefs[k]) *outRefs[k] = fr.locals[static_cast<size_t>(f->params[k]->slot)];
    return result;
}

Value VM::callNative(Frame& fr, Object* ctx, const Token& t, Function* decl, NativeFn fn) {
    NativeCall nc{*this, fr, ctx, t, decl, {}};
    for (const Token& k : t.kids)
        if (k.op != EX_EndFunctionParms) nc.args.push_back(&k);
    return fn(*this, nc);
}

Value VM::execFunction(Function* f, Object* self, Frame* caller, const Token* callTok, Frame*, Object* argCtx) {
    linker.linkStruct(f);
    if (f->funcFlags & FUNC_Native) {
        NativeFn fn = nullptr;
        if (f->nativeIndex) {
            auto it = nativesByIndex.find(f->nativeIndex);
            if (it != nativesByIndex.end()) fn = it->second;
        } else {
            auto it = nativesByName.find(f->name);
            if (it != nativesByName.end()) fn = it->second;
        }
        if (!fn) throw std::runtime_error("native not implemented: " + f->fullName());
        NativeCall nc{*this, *caller, argCtx, *callTok, f, {}};
        for (const Token& k : callTok->kids)
            if (k.op != EX_EndFunctionParms) nc.args.push_back(&k);
        // Natives run with 'self' as context object.
        nc.ctx = argCtx;
        Object* saved = nc.ctx;
        (void)saved;
        return fn(*this, nc);
    }
    std::vector<Value> args;
    std::vector<Value*> outs;
    size_t n = 0;
    for (const Token& k : callTok->kids) {
        if (k.op == EX_EndFunctionParms) break;
        Property* p = n < f->params.size() ? f->params[n] : nullptr;
        if (k.op == EX_Nothing) { args.push_back(Value()); outs.push_back(nullptr); }
        else if (p && (p->flags & CPF_OutParm)) {
            Value* r = ref(*caller, argCtx, k, nullptr, true);
            if (!r) r = temp(zeroValue(p));
            args.push_back(*r);
            outs.push_back(r);
        } else {
            args.push_back(eval(*caller, argCtx, k));
            outs.push_back(nullptr);
        }
        ++n;
    }
    // Arguments are evaluated in the caller's context object; the callee runs on 'self'.
    std::deque<Value> savedTemps;
    savedTemps.swap(g_temps);
    Value r = call(f, self, std::move(args), outs);
    g_temps.swap(savedTemps);
    return r;
}

// ---------------------------------------------------------------- casts
std::string fmtFloat(float f) {
    char buf[128];
    std::snprintf(buf, sizeof buf, "%f", static_cast<double>(f));
    return buf;
}

int32_t atoiUE(const std::string& s) {
    size_t i = 0;
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) ++i;
    bool neg = false;
    if (i < s.size() && (s[i] == '+' || s[i] == '-')) neg = s[i++] == '-';
    int64_t v = 0;
    while (i < s.size() && s[i] >= '0' && s[i] <= '9') { v = v * 10 + (s[i++] - '0'); if (v > 0x7fffffffLL + 1) break; }
    return static_cast<int32_t>(neg ? -v : v);
}

Value castValue(VM& vm, uint8_t code, const Value& v);

// ---------------------------------------------------------------- eval
Value VM::eval(Frame& fr, Object* ctx, const Token& t) {
    ++stepsExecuted;
    if (t.op >= 0x60) {
        auto it = nativesByIndex.find(t.a);
        if (it == nativesByIndex.end()) throw std::runtime_error("native index " + std::to_string(t.a) + " not implemented");
        auto d = nativeDecl.find(t.a);
        return callNative(fr, ctx, t, d == nativeDecl.end() ? nullptr : d->second, it->second);
    }
    switch (t.op) {
        case 0x00: case 0x01: case 0x02: case 0x10: case 0x1A: case 0x36: case 0x2D: {
            Property* p = nullptr;
            Value* v = ref(fr, ctx, t, &p);
            if (v) return *v;
            return p ? zeroValue(p) : Value();   // original: result buffer stays zeroed
        }
        case 0x0F: case 0x14: {  // Let / LetBool
            const Token& lhs = t.kids[0];
            if (lhs.op == 0x37) {  // assignment to dynamic array Length
                Property* ap = nullptr;
                Value* arr = ref(fr, ctx, lhs.kids[0], &ap);
                int n = eval(fr, ctx, t.kids[1]).i;
                if (!arr) return Value();
                if (n < 0) n = 0;
                arr->agg.resize(static_cast<size_t>(n), ap && ap->inner ? zeroValue(ap->inner) : Value());
                return Value();
            }
            Property* p = nullptr;
            Value* dst = ref(fr, ctx, lhs, &p, true);
            if (!dst) {
                // Unreal II formats this one with a time stamp and the current script line.
                char buf[96];
                std::snprintf(buf, sizeof buf, "%.3f Attempt to assign variable through None (line %d)",
                              elapsedSeconds(), fr.line);
                warn(fr, lhs.end, buf);
                eval(fr, ctx, t.kids[1]);   // the right-hand side is still evaluated (into scratch memory)
                return Value();
            }
            Value v = eval(fr, ctx, t.kids[1]);
            if (dst->kind == Value::Byte && v.kind == Value::Int) v = Value::byte_(static_cast<uint8_t>(v.i));
            *dst = std::move(v);
            return Value();
        }
        case 0x37: {  // DynArrayLength
            Value* arr = ref(fr, ctx, t.kids[0]);
            return Value::int_(arr ? static_cast<int32_t>(arr->agg.size()) : 0);
        }
        case 0x40: case 0x41: {  // DynArrayInsert / DynArrayRemove (array, index, count)
            Property* ap = nullptr;
            Value* arr = ref(fr, ctx, t.kids[0], &ap);
            int idx = eval(fr, ctx, t.kids[1]).i;
            int cnt = eval(fr, ctx, t.kids[2]).i;
            if (!arr) return Value();
            auto& v = arr->agg;
            int num = static_cast<int>(v.size());
            if (t.op == 0x40) {
                if (idx < 0 || idx > num || cnt < 0) {
                    warn(fr, t.end, "Attempt to insert " + std::to_string(cnt) + " elements at " + std::to_string(idx) +
                                        " an " + std::to_string(num) + "-element array");
                    return Value();
                }
                v.insert(v.begin() + idx, static_cast<size_t>(cnt), ap && ap->inner ? zeroValue(ap->inner) : Value());
            } else {
                if (idx < 0 || cnt < 0 || idx + cnt > num) {
                    if (cnt == 1)
                        warn(fr, t.end, "Attempt to remove element " + std::to_string(idx) + " in an " + std::to_string(num) + "-element array");
                    else
                        warn(fr, t.end, "Attempt to remove elements " + std::to_string(idx) + " through " +
                                            std::to_string(idx + cnt - 1) + " in an " + std::to_string(num) + "-element array");
                    // The original still removes what exists (ArrayTest: remove(0,6) on 5 elements leaves 0).
                    if (idx < 0 || idx >= num) return Value();
                    cnt = num - idx;
                }
                v.erase(v.begin() + idx, v.begin() + idx + cnt);
            }
            return Value();
        }
        case 0x11: {  // New(outer, name, flags, class)
            Object* outer = eval(fr, ctx, t.kids[0]).o;
            Value nameV = eval(fr, ctx, t.kids[1]);
            eval(fr, ctx, t.kids[2]);
            auto* cls = dynamic_cast<Class*>(eval(fr, ctx, t.kids[3]).o);
            if (!cls) { warn(fr, t.end, "New: class is None"); return Value::obj_(nullptr); }
            linker.linkStruct(cls);
            linker.applyDefaults(cls);
            return Value::obj_(newObject(cls, outer ? outer : transientPackage, nameV.kind == Value::Name ? nameV.n : 0));
        }
        case 0x19: case 0x12: {  // Context / ClassContext
            Value objv = eval(fr, ctx, t.kids[0]);
            if (!objv.o) {
                warn(fr, t.kids[0].end, "Accessed None");
                return Value();
            }
            return eval(fr, objv.o, t.kids[1]);
        }
        case 0x1B: case 0x38: {  // VirtualFunction / GlobalFunction
            Function* f = ctx->cls ? ctx->cls->findFunction(Names::str(t.name)) : nullptr;
            if (!f) throw std::runtime_error("function not found: " + Names::str(t.name));
            return execFunction(f, ctx, &fr, &t, &fr, ctx);
        }
        case 0x1C: {  // FinalFunction
            auto* f = static_cast<Function*>(t.obj);
            return execFunction(f, ctx, &fr, &t, &fr, ctx);
        }
        case 0x1D: return Value::int_(t.a);
        case 0x1E: return Value::float_(t.f[0]);
        case 0x1F: return Value::str_(t.s);
        case 0x34: return Value::str_(t.s);
        case 0x20: return Value::obj_(t.obj);
        case 0x21: return Value::name_(t.name);
        case 0x24: case 0x2C: return t.op == 0x24 ? Value::byte_(static_cast<uint8_t>(t.a)) : Value::int_(t.a);
        case 0x25: return Value::int_(0);
        case 0x26: return Value::int_(1);
        case 0x27: return Value::bool_(true);
        case 0x28: return Value::bool_(false);
        case 0x2A: return Value::obj_(nullptr);
        case 0x17: return Value::obj_(ctx);
        case 0x0B: case 0x16: return Value();
        case 0x15: return eval(fr, ctx, t.kids[0]);       // LineNumber
        case 0x18: return eval(fr, ctx, t.kids[0]);       // Skip (evaluated when not short-circuited)
        case 0x0E: eval(fr, ctx, t.kids[0]); return Value();  // EatString
        case 0x22: {  // RotationConst
            Value v; v.kind = Value::Agg; v.agg = {Value::int_(t.a), Value::int_(t.b), Value::int_(t.c)};
            return v;
        }
        case 0x23: {  // VectorConst
            Value v; v.kind = Value::Agg; v.agg = {Value::float_(t.f[0]), Value::float_(t.f[1]), Value::float_(t.f[2])};
            return v;
        }
        case 0x39: return castValue(*this, static_cast<uint8_t>(t.a), eval(fr, ctx, t.kids[0]));
        case 0x2E: case 0x13: {  // DynamicCast / MetaCast
            Value v = eval(fr, ctx, t.kids[0]);
            auto* target = dynamic_cast<Class*>(t.obj);
            if (t.op == 0x2E) {
                Class* c = metaClassOf(v.o);
                return Value::obj_(c && target && c->isChildOf(target) ? v.o : nullptr);
            }
            auto* asClass = dynamic_cast<Class*>(v.o);
            return Value::obj_(asClass && target && asClass->isChildOf(target) ? v.o : nullptr);
        }
        case 0x32: case 0x33: {  // StructCmpEq / Ne
            Value a = eval(fr, ctx, t.kids[0]);
            Value b = eval(fr, ctx, t.kids[1]);
            std::function<bool(const Value&, const Value&)> same = [&](const Value& x, const Value& y) -> bool {
                if (x.kind != y.kind) return false;
                switch (x.kind) {
                    case Value::Byte: return x.b == y.b;
                    case Value::Int: return x.i == y.i;
                    case Value::Bool: return x.z == y.z;
                    case Value::Float: return x.f == y.f;
                    case Value::Obj: return x.o == y.o;
                    case Value::Name: return x.n == y.n;
                    case Value::Str: {
                        if (x.s.size() != y.s.size()) return false;
                        for (size_t k = 0; k < x.s.size(); ++k)
                            if (std::tolower(static_cast<unsigned char>(x.s[k])) != std::tolower(static_cast<unsigned char>(y.s[k]))) return false;
                        return true;
                    }
                    case Value::Agg:
                        if (x.agg.size() != y.agg.size()) return false;
                        for (size_t k = 0; k < x.agg.size(); ++k) if (!same(x.agg[k], y.agg[k])) return false;
                        return true;
                    default: return true;
                }
            };
            bool eq = same(a, b);
            return Value::bool_(t.op == 0x32 ? eq : !eq);
        }
        default: {
            char buf[80];
            std::snprintf(buf, sizeof buf, "opcode 0x%02X not implemented in eval", t.op);
            throw std::runtime_error(buf);
        }
    }
}

// ---------------------------------------------------------------- native call helpers
bool NativeCall::given(size_t k) const { return k < args.size() && args[k]->op != EX_Nothing; }
Value NativeCall::arg(size_t k) {
    if (!given(k)) return Value();
    return vm.eval(frame, ctx, *args[k]);
}
Value* NativeCall::refArg(size_t k) {
    // Natives fetch out-parameters with a result buffer (a read): no array growth.
    Property* p = nullptr;
    Value* v = vm.ref(frame, ctx, *args[k], &p);
    return v ? v : temp(p ? zeroValue(p) : Value());
}

}  // namespace uvm
