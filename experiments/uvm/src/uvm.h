// uvm - independent UnrealScript VM for Unreal II (Legend UE2 branch, package v110).
// Written from scratch for the feasibility study; contains no Epic/Legend code.
// Formats and semantics were derived from the shipped data and validated
// against the original engine (see POC_RESULTS.md).
#pragma once
#include <cstdint>
#include <cstring>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace uvm {

struct Object;
struct Class;
struct Struct;
struct Function;
struct Property;
struct Package;
struct Linker;

// ---------------------------------------------------------------- names
// Global, case-insensitive name table (FName semantics): first spelling wins.
struct Names {
    static int intern(const std::string& s);
    static const std::string& str(int idx);
    static int none();
};

// ---------------------------------------------------------------- values
struct Value {
    enum Kind : uint8_t { Nil, Byte, Int, Bool, Float, Obj, Name, Str, Agg };
    Kind kind = Nil;
    union {
        uint8_t b;
        int32_t i;
        bool z;
        float f;
        Object* o;
        int n;
    };
    std::string s;            // Str
    std::vector<Value> agg;   // struct fields (by struct slot) or dynamic array elements
    const Struct* strct = nullptr;  // for struct values

    Value() : i(0) {}
    static Value byte_(uint8_t v) { Value r; r.kind = Byte; r.i = 0; r.b = v; return r; }
    static Value int_(int32_t v) { Value r; r.kind = Int; r.i = v; return r; }
    static Value bool_(bool v) { Value r; r.kind = Bool; r.i = 0; r.z = v; return r; }
    static Value float_(float v) { Value r; r.kind = Float; r.f = v; return r; }
    static Value obj_(Object* v) { Value r; r.kind = Obj; r.o = v; return r; }
    static Value name_(int v) { Value r; r.kind = Name; r.n = v; return r; }
    static Value str_(std::string v) { Value r; r.kind = Str; r.s = std::move(v); return r; }
};

// ---------------------------------------------------------------- objects
enum class PropKind { Byte, Int, Bool, Float, Object, Class, Name, Str, Struct, Array, Unknown };

struct Object {
    virtual ~Object() = default;
    std::string name;
    Object* outer = nullptr;
    Class* cls = nullptr;          // class of the object (instances); metadata objects use metaClass()
    std::vector<Value> slots;      // instance property storage (layout from cls)
    std::string fullName() const;
    virtual const char* kindName() const { return "Object"; }
};

struct Field : Object {
    // Next field in the owner's Children list. Resolved lazily (Linker::next) so
    // loading a class does not recurse through hundreds of sibling fields.
    Field* nextField = nullptr;
    int nextRef = 0;
    Package* srcPkg = nullptr;
    bool nextResolved = false;
};

struct Property : Field {
    PropKind kind = PropKind::Unknown;
    int arrayDim = 1;
    uint32_t flags = 0;
    Struct* structType = nullptr;  // StructProperty
    Class* objClass = nullptr;     // ObjectProperty / ClassProperty
    Property* inner = nullptr;     // ArrayProperty
    int slot = -1;                 // first slot within owner layout (class, struct or frame)
    const char* kindName() const override { return "Property"; }
};

struct Token;
using TokenList = std::vector<Token>;

struct Token {
    uint8_t op = 0;
    uint16_t mem = 0;              // in-memory code offset (iCode) - jump targets use this
    uint16_t end = 0;              // in-memory offset just past this token (= original FFrame::Code when it warns)
    int32_t a = 0, b = 0, c = 0;   // integer operands (native index, jump target, skip, ...)
    float f[3] = {0, 0, 0};
    std::string s;                 // string constants
    int name = 0;                  // name operands (global name index)
    Object* obj = nullptr;         // object operands
    TokenList kids;
};

struct Struct : Field {
    Struct* superStruct = nullptr;
    Field* childField = nullptr;
    int childrenRef = 0;
    bool childrenResolved = false;
    std::vector<Property*> layout; // all properties incl. inherited, slot order
    int slotCount = 0;
    TokenList code;                // top-level statements
    std::unordered_map<uint16_t, size_t> stmtAt;  // mem offset -> statement index
    uint32_t scriptSize = 0;
    bool linked = false;
    const char* kindName() const override { return "Struct"; }
};

struct Function : Struct {
    uint32_t funcFlags = 0;
    int nativeIndex = 0;
    std::vector<Property*> params;     // in declaration order (excluding return)
    Property* ret = nullptr;
    const char* kindName() const override { return "Function"; }
};

struct State : Struct {
    const char* kindName() const override { return "State"; }
};

struct Class : State {
    uint32_t classFlags = 0;
    std::vector<Value> defaults;       // default object slots
    std::map<std::string, Function*> funcCache;
    struct RawDefaults { Package* pkg; size_t pos; size_t end; };
    std::vector<RawDefaults> pendingDefaults;
    Package* pkg = nullptr;
    Linker* linker = nullptr;
    const char* kindName() const override { return "Class"; }
    bool isChildOf(const Class* other) const;
    Function* findFunction(const std::string& name);
    Property* findProperty(const std::string& name);
};

// ---------------------------------------------------------------- packages
struct Reader {
    const uint8_t* p;
    size_t pos, end;
    uint8_t u8() { need(1); return p[pos++]; }
    uint16_t u16() { need(2); uint16_t v; std::memcpy(&v, p + pos, 2); pos += 2; return v; }
    int32_t i32() { need(4); int32_t v; std::memcpy(&v, p + pos, 4); pos += 4; return v; }
    uint32_t u32() { return static_cast<uint32_t>(i32()); }
    uint64_t u64() { need(8); uint64_t v; std::memcpy(&v, p + pos, 8); pos += 8; return v; }
    float f32() { need(4); float v; std::memcpy(&v, p + pos, 4); pos += 4; return v; }
    int32_t compact();
    std::string fstring();
    void need(size_t n) const {
        if (pos + n > end) throw std::runtime_error("read past end of object");
    }
};

struct ImportEntry { int classPackage, className, outer, name; };
struct ExportEntry {
    int classRef, superRef, outer, name;
    uint32_t flags;
    int32_t size, offset;
    Object* object = nullptr;
    bool loading = false;
};

struct Package {
    std::string name;
    Object* packageObject = nullptr;   // outer of top-level exports (gives Core.Class.Func paths)
    std::vector<uint8_t> data;
    uint16_t version = 0, licensee = 0;
    std::vector<int> names;            // package name index -> global name index
    std::vector<ImportEntry> imports;
    std::vector<ExportEntry> exports;
    Linker* linker = nullptr;
    std::string className(const ExportEntry& e) const;
    int outermostImport(int ref) const;
};

struct Linker {
    std::string systemDir;
    std::map<std::string, std::unique_ptr<Package>> packages;   // lower-case name
    std::vector<std::unique_ptr<Object>> owned;
    std::map<std::string, Class*> intrinsics;     // "core.class" -> synthesized class
    Package* load(const std::string& name);
    Object* resolve(Package* pkg, int ref);
    Object* loadExport(Package* pkg, int index);   // 1-based
    Class* findClass(const std::string& pkg, const std::string& name);
    Field* children(Struct* s);
    Field* next(Field* f);
    void linkStruct(Struct* s);
    void applyDefaults(Class* c);
    bool verbose = false;
private:
    Object* create(Package* pkg, int index);
    void parseScript(Package* pkg, Reader& r, Struct* s, uint32_t scriptSize);
};

// ---------------------------------------------------------------- VM
struct Frame {
    Function* func;
    Object* self;
    std::vector<Value> locals;
    Frame* caller = nullptr;
    int line = 0;                  // last EX_LineNumber seen (Unreal II debugging aid)
};

struct NativeCall;  // argument access helper for natives
using NativeFn = Value (*)(struct VM&, NativeCall&);

struct VM {
    Linker& linker;
    explicit VM(Linker& l) : linker(l) {}
    std::unordered_map<int, NativeFn> nativesByIndex;
    std::unordered_map<std::string, NativeFn> nativesByName;   // "Class.Function"
    std::unordered_map<int, Function*> nativeDecl;             // index -> declaring Function
    std::vector<std::string> output;                           // Log() lines
    bool echo = true;
    uint64_t stepsExecuted = 0;

    Object* spawnObject(Class* c, const std::string& name);
    Value call(Function* f, Object* self, std::vector<Value> args, std::vector<Value*> outRefs = {});
    void registerCoreNatives();
    void registerNativeDecls();

    // interpreter
    Value eval(Frame& fr, Object* ctx, const Token& t);
    // Address of an lvalue. write=true means the token is the direct target of an
    // assignment (original: Step with Result==NULL), which lets dynamic arrays grow.
    // Returns nullptr where the original leaves GPropAddr NULL (out of bounds, None).
    Value* ref(Frame& fr, Object* ctx, const Token& t, Property** propOut = nullptr, bool write = false);
    void warn(Frame& fr, uint16_t codeOffset, const std::string& msg);
    Object* newObject(Class* c, Object* outer, int name);
    Object* transientPackage = nullptr;
    Value execFunction(Function* f, Object* self, Frame* caller, const Token* callTok, Frame* argFrame, Object* argCtx);
    Value callNative(Frame& fr, Object* ctx, const Token& t, Function* decl, NativeFn fn);
    Value zeroOf(const Property* p) const;
    void log(const std::string& s);
};

struct NativeCall {
    VM& vm;
    Frame& frame;
    Object* ctx;
    const Token& tok;
    Function* decl;
    std::vector<const Token*> args;    // argument expressions (EX_Nothing / missing => not given)
    Value arg(size_t i);
    Value* refArg(size_t i);
    bool given(size_t i) const;
    int32_t i(size_t k) { return arg(k).i; }
    float f(size_t k) { return arg(k).f; }
    bool z(size_t k) { return arg(k).z; }
    std::string s(size_t k) { return arg(k).s; }
};

std::string fmtFloat(float f);
Class* metaClassOf(const Object* o);

}  // namespace uvm
