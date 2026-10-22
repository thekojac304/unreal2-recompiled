// Core natives (operators, string, math) and primitive casts.
// Indices come from the GRegisterNative table recovered from the shipped
// Core.dll; behaviour follows UE2 conventions and is checked by the probe.
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>

#include "uvm.h"

namespace uvm {

Value zeroValue(const Property* p);
int32_t atoiUE(const std::string& s);

namespace {
Value vec(float x, float y, float z) {
    Value v; v.kind = Value::Agg; v.agg = {Value::float_(x), Value::float_(y), Value::float_(z)}; return v;
}
Value rot(int p, int y, int r) {
    Value v; v.kind = Value::Agg; v.agg = {Value::int_(p), Value::int_(y), Value::int_(r)}; return v;
}
float X(const Value& v) { return v.agg.at(0).f; }
float Y(const Value& v) { return v.agg.at(1).f; }
float Z(const Value& v) { return v.agg.at(2).f; }
std::string upper(std::string s) { for (auto& c : s) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c))); return s; }
std::string lowerS(std::string s) { for (auto& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c))); return s; }
int stricmp_(const std::string& a, const std::string& b) {
    return lowerS(a).compare(lowerS(b));
}
std::string vecStr(const Value& v) {
    char buf[160];
    std::snprintf(buf, sizeof buf, "%f,%f,%f", static_cast<double>(X(v)), static_cast<double>(Y(v)), static_cast<double>(Z(v)));
    return buf;
}
std::string rotStr(const Value& v) {
    char buf[64];
    std::snprintf(buf, sizeof buf, "%i,%i,%i", v.agg.at(0).i & 65535, v.agg.at(1).i & 65535, v.agg.at(2).i & 65535);
    return buf;
}
bool strToBool(const std::string& s) {
    if (stricmp_(s, "True") == 0) return true;
    if (stricmp_(s, "False") == 0) return false;
    return atoiUE(s) != 0;
}
}  // namespace

Value castValue(VM& vm, uint8_t code, const Value& v) {
    (void)vm;
    switch (code) {
        case 0x39: {  // RotatorToVector
            const double k = 3.14159265358979323846 / 32768.0;
            double p = v.agg.at(0).i * k, y = v.agg.at(1).i * k;
            return vec(static_cast<float>(std::cos(p) * std::cos(y)), static_cast<float>(std::cos(p) * std::sin(y)), static_cast<float>(std::sin(p)));
        }
        case 0x3A: return Value::int_(v.b);
        case 0x3B: return Value::bool_(v.b != 0);
        case 0x3C: return Value::float_(v.b);
        case 0x3D: return Value::byte_(static_cast<uint8_t>(v.i));
        case 0x3E: return Value::bool_(v.i != 0);
        case 0x3F: return Value::float_(static_cast<float>(v.i));
        case 0x40: return Value::byte_(v.z ? 1 : 0);
        case 0x41: return Value::int_(v.z ? 1 : 0);
        case 0x42: return Value::float_(v.z ? 1.f : 0.f);
        case 0x43: return Value::byte_(static_cast<uint8_t>(static_cast<int32_t>(v.f)));
        case 0x44: return Value::int_(static_cast<int32_t>(v.f));
        case 0x45: return Value::bool_(v.f != 0.f);
        case 0x47: return Value::bool_(v.o != nullptr);
        case 0x48: return Value::bool_(v.n != Names::none());
        case 0x49: return Value::byte_(static_cast<uint8_t>(atoiUE(v.s)));
        case 0x4A: return Value::int_(atoiUE(v.s));
        case 0x4B: return Value::bool_(strToBool(v.s));
        case 0x4C: return Value::float_(static_cast<float>(std::atof(v.s.c_str())));
        case 0x4F: return Value::bool_(X(v) != 0.f || Y(v) != 0.f || Z(v) != 0.f);
        case 0x51: return Value::bool_(v.agg.at(0).i || v.agg.at(1).i || v.agg.at(2).i);
        case 0x52: return Value::str_(std::to_string(v.b));
        case 0x53: return Value::str_(std::to_string(v.i));
        case 0x54: return Value::str_(v.z ? "True" : "False");
        case 0x55: return Value::str_(fmtFloat(v.f));
        case 0x56: return Value::str_(v.o ? v.o->fullName() : "None");
        case 0x57: return Value::str_(Names::str(v.n));
        case 0x58: return Value::str_(vecStr(v));
        case 0x59: return Value::str_(rotStr(v));
        default: {
            char buf[64];
            std::snprintf(buf, sizeof buf, "cast 0x%02X not implemented", code);
            throw std::runtime_error(buf);
        }
    }
}

#define NATIVE(fn) static Value fn(VM& vm, NativeCall& c)
#define UNUSED (void)vm

// ---- bool
NATIVE(n_Not) { UNUSED; return Value::bool_(!c.z(0)); }
NATIVE(n_EqBool) { UNUSED; bool a = c.z(0); return Value::bool_(a == c.z(1)); }
NATIVE(n_NeBool) { UNUSED; bool a = c.z(0); return Value::bool_(a != c.z(1)); }
NATIVE(n_AndAnd) { UNUSED; return Value::bool_(c.z(0) ? c.z(1) : false); }   // arg 1 is an EX_Skip: only evaluated if needed
NATIVE(n_XorXor) { UNUSED; bool a = c.z(0); return Value::bool_(a != c.z(1)); }
NATIVE(n_OrOr) { UNUSED; return Value::bool_(c.z(0) ? true : c.z(1)); }
// ---- byte
NATIVE(n_MulEqByte) { UNUSED; Value* a = c.refArg(0); a->b = static_cast<uint8_t>(a->b * c.arg(1).b); return *a; }
NATIVE(n_DivEqByte) { UNUSED; Value* a = c.refArg(0); uint8_t b = c.arg(1).b; a->b = b ? static_cast<uint8_t>(a->b / b) : 0; return *a; }
NATIVE(n_AddEqByte) { UNUSED; Value* a = c.refArg(0); a->b = static_cast<uint8_t>(a->b + c.arg(1).b); return *a; }
NATIVE(n_SubEqByte) { UNUSED; Value* a = c.refArg(0); a->b = static_cast<uint8_t>(a->b - c.arg(1).b); return *a; }
NATIVE(n_PreIncByte) { UNUSED; Value* a = c.refArg(0); ++a->b; return *a; }
NATIVE(n_PreDecByte) { UNUSED; Value* a = c.refArg(0); --a->b; return *a; }
NATIVE(n_PostIncByte) { UNUSED; Value* a = c.refArg(0); Value r = *a; ++a->b; return r; }
NATIVE(n_PostDecByte) { UNUSED; Value* a = c.refArg(0); Value r = *a; --a->b; return r; }
// ---- int
NATIVE(n_ComplInt) { UNUSED; return Value::int_(~c.i(0)); }
NATIVE(n_NegInt) { UNUSED; return Value::int_(-c.i(0)); }
NATIVE(n_MulInt) { UNUSED; int a = c.i(0); return Value::int_(static_cast<int32_t>(static_cast<uint32_t>(a) * static_cast<uint32_t>(c.i(1)))); }
NATIVE(n_DivInt) { int a = c.i(0), b = c.i(1); if (!b) { vm.log("Divide by zero"); return Value::int_(0); } return Value::int_(a / b); }
NATIVE(n_AddInt) { UNUSED; int a = c.i(0); return Value::int_(static_cast<int32_t>(static_cast<uint32_t>(a) + static_cast<uint32_t>(c.i(1)))); }
NATIVE(n_SubInt) { UNUSED; int a = c.i(0); return Value::int_(static_cast<int32_t>(static_cast<uint32_t>(a) - static_cast<uint32_t>(c.i(1)))); }
NATIVE(n_Shl) { UNUSED; int a = c.i(0); return Value::int_(static_cast<int32_t>(static_cast<uint32_t>(a) << (c.i(1) & 31))); }
NATIVE(n_Shr) { UNUSED; int a = c.i(0); return Value::int_(a >> (c.i(1) & 31)); }
NATIVE(n_Shrr) { UNUSED; int a = c.i(0); return Value::int_(static_cast<int32_t>(static_cast<uint32_t>(a) >> (c.i(1) & 31))); }
NATIVE(n_LtInt) { UNUSED; int a = c.i(0); return Value::bool_(a < c.i(1)); }
NATIVE(n_GtInt) { UNUSED; int a = c.i(0); return Value::bool_(a > c.i(1)); }
NATIVE(n_LeInt) { UNUSED; int a = c.i(0); return Value::bool_(a <= c.i(1)); }
NATIVE(n_GeInt) { UNUSED; int a = c.i(0); return Value::bool_(a >= c.i(1)); }
NATIVE(n_EqInt) { UNUSED; int a = c.i(0); return Value::bool_(a == c.i(1)); }
NATIVE(n_NeInt) { UNUSED; int a = c.i(0); return Value::bool_(a != c.i(1)); }
NATIVE(n_AndInt) { UNUSED; int a = c.i(0); return Value::int_(a & c.i(1)); }
NATIVE(n_XorInt) { UNUSED; int a = c.i(0); return Value::int_(a ^ c.i(1)); }
NATIVE(n_OrInt) { UNUSED; int a = c.i(0); return Value::int_(a | c.i(1)); }
NATIVE(n_MulEqIntF) { UNUSED; Value* a = c.refArg(0); a->i = static_cast<int32_t>(a->i * c.f(1)); return *a; }
NATIVE(n_DivEqIntF) { UNUSED; Value* a = c.refArg(0); a->i = static_cast<int32_t>(a->i / c.f(1)); return *a; }
NATIVE(n_AddEqInt) { UNUSED; Value* a = c.refArg(0); a->i += c.i(1); return *a; }
NATIVE(n_SubEqInt) { UNUSED; Value* a = c.refArg(0); a->i -= c.i(1); return *a; }
NATIVE(n_PreIncInt) { UNUSED; Value* a = c.refArg(0); ++a->i; return *a; }
NATIVE(n_PreDecInt) { UNUSED; Value* a = c.refArg(0); --a->i; return *a; }
NATIVE(n_PostIncInt) { UNUSED; Value* a = c.refArg(0); Value r = *a; ++a->i; return r; }
NATIVE(n_PostDecInt) { UNUSED; Value* a = c.refArg(0); Value r = *a; --a->i; return r; }
NATIVE(n_Min) { UNUSED; int a = c.i(0), b = c.i(1); return Value::int_(a < b ? a : b); }
NATIVE(n_Max) { UNUSED; int a = c.i(0), b = c.i(1); return Value::int_(a > b ? a : b); }
NATIVE(n_Clamp) { UNUSED; int v = c.i(0), a = c.i(1), b = c.i(2); return Value::int_(v < a ? a : v < b ? v : b); }
// ---- float
NATIVE(n_NegF) { UNUSED; return Value::float_(-c.f(0)); }
NATIVE(n_PowF) { UNUSED; float a = c.f(0); return Value::float_(static_cast<float>(std::pow(a, c.f(1)))); }
NATIVE(n_MulF) { UNUSED; float a = c.f(0); return Value::float_(a * c.f(1)); }
NATIVE(n_DivF) { float a = c.f(0), b = c.f(1); if (b == 0.f) { vm.log("Divide by zero"); return Value::float_(0); } return Value::float_(a / b); }
NATIVE(n_ModF) { UNUSED; float a = c.f(0); return Value::float_(std::fmod(a, c.f(1))); }
NATIVE(n_AddF) { UNUSED; float a = c.f(0); return Value::float_(a + c.f(1)); }
NATIVE(n_SubF) { UNUSED; float a = c.f(0); return Value::float_(a - c.f(1)); }
NATIVE(n_LtF) { UNUSED; float a = c.f(0); return Value::bool_(a < c.f(1)); }
NATIVE(n_GtF) { UNUSED; float a = c.f(0); return Value::bool_(a > c.f(1)); }
NATIVE(n_LeF) { UNUSED; float a = c.f(0); return Value::bool_(a <= c.f(1)); }
NATIVE(n_GeF) { UNUSED; float a = c.f(0); return Value::bool_(a >= c.f(1)); }
NATIVE(n_EqF) { UNUSED; float a = c.f(0); return Value::bool_(a == c.f(1)); }
NATIVE(n_NeF) { UNUSED; float a = c.f(0); return Value::bool_(a != c.f(1)); }
NATIVE(n_ApproxF) { UNUSED; float a = c.f(0); return Value::bool_(std::fabs(a - c.f(1)) < 1.e-4f); }
NATIVE(n_MulEqF) { UNUSED; Value* a = c.refArg(0); a->f *= c.f(1); return *a; }
NATIVE(n_DivEqF) { UNUSED; Value* a = c.refArg(0); a->f /= c.f(1); return *a; }
NATIVE(n_AddEqF) { UNUSED; Value* a = c.refArg(0); a->f += c.f(1); return *a; }
NATIVE(n_SubEqF) { UNUSED; Value* a = c.refArg(0); a->f -= c.f(1); return *a; }
NATIVE(n_Abs) { UNUSED; return Value::float_(std::fabs(c.f(0))); }
NATIVE(n_Sin) { UNUSED; return Value::float_(static_cast<float>(std::sin(c.f(0)))); }
NATIVE(n_Cos) { UNUSED; return Value::float_(static_cast<float>(std::cos(c.f(0)))); }
NATIVE(n_Tan) { UNUSED; return Value::float_(static_cast<float>(std::tan(c.f(0)))); }
NATIVE(n_Atan) { UNUSED; return Value::float_(static_cast<float>(std::atan(c.f(0)))); }
NATIVE(n_Exp) { UNUSED; return Value::float_(static_cast<float>(std::exp(c.f(0)))); }
NATIVE(n_Loge) { UNUSED; return Value::float_(static_cast<float>(std::log(c.f(0)))); }
NATIVE(n_Sqrt) { UNUSED; float a = c.f(0); return Value::float_(a > 0 ? static_cast<float>(std::sqrt(a)) : 0.f); }
NATIVE(n_Square) { UNUSED; float a = c.f(0); return Value::float_(a * a); }
NATIVE(n_FMin) { UNUSED; float a = c.f(0), b = c.f(1); return Value::float_(a < b ? a : b); }
NATIVE(n_FMax) { UNUSED; float a = c.f(0), b = c.f(1); return Value::float_(a > b ? a : b); }
NATIVE(n_FClamp) { UNUSED; float v = c.f(0), a = c.f(1), b = c.f(2); return Value::float_(v < a ? a : v < b ? v : b); }
NATIVE(n_Lerp) { UNUSED; float t = c.f(0), a = c.f(1), b = c.f(2); return Value::float_(a + t * (b - a)); }
// ---- string
NATIVE(n_Concat) { UNUSED; std::string a = c.s(0); return Value::str_(a + c.s(1)); }
NATIVE(n_At) { UNUSED; std::string a = c.s(0); return Value::str_(a + " " + c.s(1)); }
NATIVE(n_LtS) { UNUSED; std::string a = c.s(0); return Value::bool_(a.compare(c.s(1)) < 0); }
NATIVE(n_GtS) { UNUSED; std::string a = c.s(0); return Value::bool_(a.compare(c.s(1)) > 0); }
NATIVE(n_LeS) { UNUSED; std::string a = c.s(0); return Value::bool_(a.compare(c.s(1)) <= 0); }
NATIVE(n_GeS) { UNUSED; std::string a = c.s(0); return Value::bool_(a.compare(c.s(1)) >= 0); }
NATIVE(n_EqS) { UNUSED; std::string a = c.s(0); return Value::bool_(a.compare(c.s(1)) == 0); }
NATIVE(n_NeS) { UNUSED; std::string a = c.s(0); return Value::bool_(a.compare(c.s(1)) != 0); }
NATIVE(n_ApproxS) { UNUSED; std::string a = c.s(0); return Value::bool_(stricmp_(a, c.s(1)) == 0); }
NATIVE(n_Len) { UNUSED; return Value::int_(static_cast<int32_t>(c.s(0).size())); }
NATIVE(n_InStr) { UNUSED; std::string s = c.s(0); auto p = s.find(c.s(1)); return Value::int_(p == std::string::npos ? -1 : static_cast<int32_t>(p)); }
NATIVE(n_Mid) {
    UNUSED;
    std::string s = c.s(0);
    int i = c.i(1);
    int j = c.given(2) ? c.i(2) : 65535;   // optional count defaults to "rest of string"
    if (i < 0) { j += i; i = 0; }
    if (j < 0 || i >= static_cast<int>(s.size())) return Value::str_("");
    return Value::str_(s.substr(static_cast<size_t>(i), static_cast<size_t>(j)));
}
NATIVE(n_Left) { UNUSED; std::string s = c.s(0); int n = c.i(1); return Value::str_(n <= 0 ? "" : s.substr(0, static_cast<size_t>(n))); }
NATIVE(n_Right) {
    UNUSED;
    std::string s = c.s(0);
    int n = c.i(1);
    if (n <= 0) return Value::str_("");
    return Value::str_(static_cast<size_t>(n) >= s.size() ? s : s.substr(s.size() - static_cast<size_t>(n)));
}
NATIVE(n_Caps) { UNUSED; return Value::str_(upper(c.s(0))); }
NATIVE(n_Locs) { UNUSED; return Value::str_(lowerS(c.s(0))); }
NATIVE(n_Chr) { UNUSED; int i = c.i(0); return Value::str_(i ? std::string(1, static_cast<char>(i)) : std::string()); }
NATIVE(n_Asc) { UNUSED; std::string s = c.s(0); return Value::int_(s.empty() ? 0 : static_cast<unsigned char>(s[0])); }
NATIVE(n_Split) {
    UNUSED;
    std::string s = c.s(0), in = c.s(1);
    Value* l = c.refArg(2);
    Value* r = c.refArg(3);
    bool right = c.given(4) && c.z(4);
    auto p = right ? s.rfind(in) : s.find(in);
    if (p == std::string::npos || in.empty()) return Value::bool_(false);
    l->s = s.substr(0, p);
    r->s = s.substr(p + in.size());
    return Value::bool_(true);
}
NATIVE(n_Log) { std::string s = c.s(0); vm.log(s); return Value(); }
// ---- names / objects / classes
NATIVE(n_EqName) { UNUSED; int a = c.arg(0).n; return Value::bool_(a == c.arg(1).n); }
NATIVE(n_NeName) { UNUSED; int a = c.arg(0).n; return Value::bool_(a != c.arg(1).n); }
NATIVE(n_EqObj) { UNUSED; Object* a = c.arg(0).o; return Value::bool_(a == c.arg(1).o); }
NATIVE(n_NeObj) { UNUSED; Object* a = c.arg(0).o; return Value::bool_(a != c.arg(1).o); }
NATIVE(n_ClassIsChildOf) {
    UNUSED;
    auto* a = dynamic_cast<Class*>(c.arg(0).o);
    auto* b = dynamic_cast<Class*>(c.arg(1).o);
    return Value::bool_(a && b && a->isChildOf(b));
}
NATIVE(n_IsA) {
    UNUSED;
    int want = c.arg(0).n;
    for (Struct* s = c.ctx ? c.ctx->cls : nullptr; s; s = s->superStruct)
        if (Names::intern(s->name) == want) return Value::bool_(true);
    return Value::bool_(false);
}
// ---- vectors / rotators
NATIVE(n_NegVec) { UNUSED; Value a = c.arg(0); return vec(-X(a), -Y(a), -Z(a)); }
NATIVE(n_MulVecF) { UNUSED; Value a = c.arg(0); float b = c.f(1); return vec(X(a) * b, Y(a) * b, Z(a) * b); }
NATIVE(n_MulFVec) { UNUSED; float a = c.f(0); Value b = c.arg(1); return vec(X(b) * a, Y(b) * a, Z(b) * a); }
NATIVE(n_MulVecVec) { UNUSED; Value a = c.arg(0), b = c.arg(1); return vec(X(a) * X(b), Y(a) * Y(b), Z(a) * Z(b)); }
NATIVE(n_DivVecF) { UNUSED; Value a = c.arg(0); float b = c.f(1); float r = 1.f / b; return vec(X(a) * r, Y(a) * r, Z(a) * r); }
NATIVE(n_AddVec) { UNUSED; Value a = c.arg(0), b = c.arg(1); return vec(X(a) + X(b), Y(a) + Y(b), Z(a) + Z(b)); }
NATIVE(n_SubVec) { UNUSED; Value a = c.arg(0), b = c.arg(1); return vec(X(a) - X(b), Y(a) - Y(b), Z(a) - Z(b)); }
NATIVE(n_EqVec) { UNUSED; Value a = c.arg(0), b = c.arg(1); return Value::bool_(X(a) == X(b) && Y(a) == Y(b) && Z(a) == Z(b)); }
NATIVE(n_NeVec) { UNUSED; Value a = c.arg(0), b = c.arg(1); return Value::bool_(X(a) != X(b) || Y(a) != Y(b) || Z(a) != Z(b)); }
NATIVE(n_Dot) { UNUSED; Value a = c.arg(0), b = c.arg(1); return Value::float_(X(a) * X(b) + Y(a) * Y(b) + Z(a) * Z(b)); }
NATIVE(n_Cross) {
    UNUSED;
    Value a = c.arg(0), b = c.arg(1);
    return vec(Y(a) * Z(b) - Z(a) * Y(b), Z(a) * X(b) - X(a) * Z(b), X(a) * Y(b) - Y(a) * X(b));
}
NATIVE(n_VSize) { UNUSED; Value a = c.arg(0); return Value::float_(static_cast<float>(std::sqrt(X(a) * X(a) + Y(a) * Y(a) + Z(a) * Z(a)))); }
NATIVE(n_Normal) {
    UNUSED;
    Value a = c.arg(0);
    float sq = X(a) * X(a) + Y(a) * Y(a) + Z(a) * Z(a);
    if (sq < 1.e-8f) return vec(0, 0, 0);
    float s = 1.f / static_cast<float>(std::sqrt(sq));
    return vec(X(a) * s, Y(a) * s, Z(a) * s);
}
NATIVE(n_AddRot) {
    UNUSED;
    Value a = c.arg(0), b = c.arg(1);
    return rot(a.agg[0].i + b.agg[0].i, a.agg[1].i + b.agg[1].i, a.agg[2].i + b.agg[2].i);
}
NATIVE(n_SubRot) {
    UNUSED;
    Value a = c.arg(0), b = c.arg(1);
    return rot(a.agg[0].i - b.agg[0].i, a.agg[1].i - b.agg[1].i, a.agg[2].i - b.agg[2].i);
}
NATIVE(n_EqRot) { UNUSED; Value a = c.arg(0), b = c.arg(1); return Value::bool_(a.agg[0].i == b.agg[0].i && a.agg[1].i == b.agg[1].i && a.agg[2].i == b.agg[2].i); }

void VM::registerCoreNatives() {
    struct { int idx; NativeFn fn; } table[] = {
        {112, n_Concat}, {114, n_EqObj}, {115, n_LtS}, {116, n_GtS}, {119, n_NeObj}, {120, n_LeS}, {121, n_GeS},
        {122, n_EqS}, {123, n_NeS}, {124, n_ApproxS}, {125, n_Len}, {126, n_InStr}, {127, n_Mid}, {128, n_Left},
        {129, n_Not}, {130, n_AndAnd}, {131, n_XorXor}, {132, n_OrOr}, {133, n_MulEqByte}, {134, n_DivEqByte},
        {135, n_AddEqByte}, {136, n_SubEqByte}, {137, n_PreIncByte}, {138, n_PreDecByte}, {139, n_PostIncByte},
        {140, n_PostDecByte}, {141, n_ComplInt}, {143, n_NegInt}, {144, n_MulInt}, {145, n_DivInt}, {146, n_AddInt},
        {147, n_SubInt}, {148, n_Shl}, {149, n_Shr}, {150, n_LtInt}, {151, n_GtInt}, {152, n_LeInt}, {153, n_GeInt},
        {154, n_EqInt}, {155, n_NeInt}, {156, n_AndInt}, {157, n_XorInt}, {158, n_OrInt}, {159, n_MulEqIntF},
        {160, n_DivEqIntF}, {161, n_AddEqInt}, {162, n_SubEqInt}, {163, n_PreIncInt}, {164, n_PreDecInt},
        {165, n_PostIncInt}, {166, n_PostDecInt}, {168, n_At}, {169, n_NegF}, {170, n_PowF}, {171, n_MulF},
        {172, n_DivF}, {173, n_ModF}, {174, n_AddF}, {175, n_SubF}, {176, n_LtF}, {177, n_GtF}, {178, n_LeF},
        {179, n_GeF}, {180, n_EqF}, {181, n_NeF}, {182, n_MulEqF}, {183, n_DivEqF}, {184, n_AddEqF}, {185, n_SubEqF},
        {186, n_Abs}, {187, n_Sin}, {188, n_Cos}, {189, n_Tan}, {190, n_Atan}, {191, n_Exp}, {192, n_Loge},
        {193, n_Sqrt}, {194, n_Square}, {196, n_Shrr}, {210, n_ApproxF}, {211, n_NegVec}, {212, n_MulVecF},
        {213, n_MulFVec}, {214, n_DivVecF}, {215, n_AddVec}, {216, n_SubVec}, {217, n_EqVec}, {218, n_NeVec},
        {219, n_Dot}, {220, n_Cross}, {225, n_VSize}, {226, n_Normal}, {231, n_Log}, {234, n_Right}, {235, n_Caps},
        {236, n_Chr}, {237, n_Asc}, {242, n_EqBool}, {243, n_NeBool}, {244, n_FMin}, {245, n_FMax}, {246, n_FClamp},
        {247, n_Lerp}, {249, n_Min}, {250, n_Max}, {251, n_Clamp}, {254, n_EqName}, {255, n_NeName},
        {258, n_ClassIsChildOf}, {296, n_MulVecVec}, {303, n_IsA}, {316, n_AddRot}, {317, n_SubRot}, {142, n_EqRot},
    };
    for (auto& e : table) nativesByIndex[e.idx] = e.fn;
    nativesByName["Locs"] = n_Locs;
    nativesByName["Split"] = n_Split;
}

void VM::registerNativeDecls() {
    Class* obj = linker.findClass("Core", "Object");
    for (Field* f = linker.children(obj); f; f = linker.next(f))
        if (auto* fn = dynamic_cast<Function*>(f); fn && fn->nativeIndex) {
            linker.linkStruct(fn);
            nativeDecl[fn->nativeIndex] = fn;
        }
}

}  // namespace uvm
