/* cases.c - owned test functions for experiments/xrt/tests/opt_diff (see README.md).
 *
 * Built as a 32-bit DLL (cl /O2 /arch:IA32, no CRT), lifted by tools/xrt/xlift.py with and without --opt, and
 * executed natively and lifted from identical inputs. Every exported test has the signature
 *   uint64_t __cdecl t_name(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed)
 * and must terminate for any input. The C tests produce the flag patterns MSVC emits (compare chains, 64-bit
 * compares, jump tables, setcc, x87 compares through fnstsw/test ah/jp, byte/word arithmetic, calls, indirect
 * calls, recursion, string instructions); the __asm tests keep flags alive across shifts by a zero count, inc/dec,
 * labels, loops, calls and the function return, which compilers never do but the analysis must still get right. */
#include <stdint.h>
#include <intrin.h>
#pragma intrinsic(_rotl, _rotr, __movsb, __stosd)

#define EXPORT __declspec(dllexport)
#define NOINLINE __declspec(noinline)

int _fltused;                          /* no CRT: the compiler's floating-point marker symbol */

static uint32_t rd(const uint8_t* p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }

/* arithmetic/logic chain with signed and unsigned compares consumed by jcc and setcc */
EXPORT uint64_t __cdecl t_mix(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint32_t h = seed, i, cnt = 0;
    int32_t s = 0;
    n &= 1023;
    for (i = 0; i + 4 <= n; i += 4) {
        uint32_t v = rd(in + i);
        h = (h ^ v) * 0x01000193u;
        if ((int32_t)v < 0) s -= (int32_t)(v >> 3); else s += (int32_t)(v & 0xFFFF);
        if (v > h) cnt++;
        if ((int32_t)v <= s) h += 7;
        cnt += (v & 0x80) != 0;
        cnt += (int32_t)h > s;
        cnt += h >= v;
        out[i & 255] ^= (uint8_t)(h >> (v & 7));
    }
    return ((uint64_t)cnt << 32) | (uint32_t)(h + s);
}

/* 64-bit add/sub/shift (adc, sbb, shld, shrd) and multi-jump 64-bit compares */
EXPORT uint64_t __cdecl t_wide(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint64_t a = seed | ((uint64_t)~seed << 32), b = 0x123456789abcdefull;
    int64_t sg = 0;
    uint32_t i;
    n &= 1023;
    for (i = 0; i + 8 <= n; i += 8) {
        uint64_t v = rd(in + i) | (uint64_t)rd(in + i + 4) << 32;
        a += v;
        b -= a >> 7;
        b ^= a << 13;
        if (a < b) a = (a << 1) | (b >> 63);
        if ((int64_t)v < sg) sg -= (int64_t)(v >> 1); else sg += (int64_t)(v >> 5);
        if (a == v) b++;
        if ((int64_t)a >= (int64_t)b) b += 3;
        *(uint64_t*)(out + (i & 248)) = a ^ b;
    }
    return a + b + (uint64_t)sg;
}

/* dense switch (jump table) */
EXPORT uint64_t __cdecl t_switch(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint32_t acc = seed, i;
    n &= 1023;
    for (i = 0; i < n; i++) {
        switch (in[i] & 15) {
        case 0: acc += 3; break;
        case 1: acc ^= acc >> 3; break;
        case 2: acc -= in[i]; break;
        case 3: acc = acc * 5 + 1; break;
        case 4: acc = ~acc; break;
        case 5: acc <<= 1; break;
        case 6: acc += acc >> 31; break;
        case 7: acc = (acc >> 1) | (acc << 31); break;
        case 8: if (acc & 1) acc += 11; break;
        case 9: acc -= i; break;
        case 10: acc |= 0x100; break;
        case 11: acc &= 0xFFFFFF7Fu; break;
        default: acc += in[i]; break;
        }
        out[i & 255] = (uint8_t)acc;
    }
    return acc;
}

/* x87 compares (fcomp / fnstsw ax / test ah / jp, jne) on arbitrary float bit patterns incl. NaN, inf */
EXPORT uint64_t __cdecl t_float(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    double x = (double)(int32_t)seed / 977.0, y = 0.5;
    uint32_t i, k = 0;
    (void)out;
    n &= 1023;
    for (i = 0; i + 4 <= n; i += 4) {
        float f = *(const float*)(in + i);
        double d = f;
        if (d < x) { x = x - d * 0.25; k++; }
        else if (d == x) k += 5;
        else x = x + d * 0.125;
        if (x > 1e6 || x < -1e6) x *= 0.5;
        if (!(d >= y)) y = y * 0.75 + 1.0;
        k += x != y;
        k += (d != d) << 4;
    }
    return ((uint64_t)(x != x) << 63) | ((uint64_t)(y > 0.0) << 62) | ((uint64_t)(x < y) << 61) | k;
}

/* x87 arithmetic through compiled calls: float/double helpers return in ST(0), mixed with compares and stores */
NOINLINE static float fx_scale(float a, float b) { return a * 0.75f - b / 3.0f; }
NOINLINE static double fx_mix(double a, int k) { return (k & 1) ? a + k : a * 0.5 - k; }

EXPORT uint64_t __cdecl t_x87_calls(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    union { double d; uint64_t u; } r;
    double acc = (double)(int32_t)seed * 0.001, acc2 = 1.0;
    uint32_t i, k = 0;
    n &= 511;
    for (i = 0; i + 4 <= n; i += 4) {
        float f = *(const float*)(in + i);
        if (!(f == f) || f > 1e30f || f < -1e30f) f = (float)(int32_t)i;
        acc = acc + fx_scale(f, (float)acc2) * fx_mix(acc2, in[i]);
        acc2 = acc2 * 1.0001 + (acc < acc2 ? 0.5 : -0.25);
        if (acc > 1e9 || acc < -1e9) acc *= 1e-6;
        k += acc > acc2;
        *(float*)(out + (i & 252)) = (float)(acc - acc2);
    }
    r.d = acc;
    return r.u ^ k;
}

/* x87 values live on the register stack across calls (a callee squares ST(0) in place, another pushes 3), helpers
 * reached from the middle of a stack (fsqrt, fsin, fist, fnstcw/fldcw), fxch, reversed and popping arithmetic,
 * fcom/fcomp/fucom/fucompp with fnstsw ax, and a non-empty stack at a callee's entry. The fsin result only feeds a
 * sign test (the lifted helper is the host sin), and the returned status words keep only C0/C2/C3 and TOP (the
 * double model does not emulate the sticky exception bits or C1). */
static const double k_decay = 0.5;
static __declspec(naked) void x87_square(void) { __asm { fld st(0)
                                                         fmulp st(1), st(0)
                                                         ret } }
/* loads the caller's ST(1) on one branch only, then reads it after the merge (x87v must not keep values across labels) */
static __declspec(naked) void x87_branchy(void) { __asm { test eax, 0x100
                                                        jz merge
                                                        fld st(1)
                                                        fstp st(0)
                                                    merge:
                                                        fadd st(0), st(1)
                                                        ret } }
static const double k_three = 3.0;      /* not fldpi: the hardware loads pi with 64 mantissa bits, the model 53 */
static __declspec(naked) void x87_push_three(void) { __asm { fld qword ptr [k_three]
                                                          ret } }
EXPORT __declspec(naked) uint64_t __cdecl t_asm_x87(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    __asm {
        push esi
        push edi
        mov esi, [esp + 12]
        mov edi, [esp + 16]
        mov ecx, [esp + 20]
        and ecx, 15
        fld1
        fild dword ptr [esp + 24]
        fmul qword ptr [k_decay]
        jecxz done
    again:
        fild word ptr [esi]
        fabs
        fadd st(0), st(2)
        fsqrt
        call x87_square
        call x87_push_three
        fmulp st(1), st(0)
        fcom st(1)
        fnstsw ax
        call x87_branchy
        test ah, 1
        jz not_below
        fsub st(0), st(2)
    not_below:
        fxch st(1)
        fmul qword ptr [k_decay]
        faddp st(1), st(0)
        fst dword ptr [edi]
        fist dword ptr [edi + 4]
        fld st(0)
        fsin
        fldz
        fcompp
        fnstsw ax
        test ah, 0x41
        jnz no_flip
        fchs
        fsubr st(0), st(1)
    no_flip:
        fld st(0)
        fdivr st(0), st(2)
        fstp qword ptr [edi + 8]
        add esi, 2
        add edi, 16
        dec ecx
        jnz again
    done:
        sub esp, 4
        fnstcw word ptr [esp]
        fldcw word ptr [esp]
        add esp, 4
        fucom st(1)
        fnstsw ax
        mov edx, eax
        fistp dword ptr [edi]
        fstp st(0)
        fld1
        fldz
        fucompp
        fnstsw ax
        and eax, 0x7D00
        and edx, 0x7D00
        pop edi
        pop esi
        ret
    }
}

/* 8- and 16-bit arithmetic */
EXPORT uint64_t __cdecl t_bytes(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint8_t a = (uint8_t)seed;
    uint16_t w = (uint16_t)(seed >> 8);
    int8_t sc = 0;
    uint32_t i, c = 0;
    n &= 1023;
    for (i = 0; i < n; i++) {
        uint8_t b = in[i];
        a = (uint8_t)(a + b);
        if (a < b) c++;
        w = (uint16_t)(w * 3 + b);
        if ((int16_t)w < 0) w ^= 0x5555;
        sc = (int8_t)(sc - (int8_t)b);
        if (sc > 50) sc -= 100;
        if ((uint8_t)(b - 0x30) < 10) c += 2;
        out[i & 255] = (uint8_t)(a ^ (uint8_t)w ^ (uint8_t)sc);
    }
    return a | (uint32_t)w << 8 | (uint32_t)(uint8_t)sc << 24 | (uint64_t)c << 32;
}

/* direct calls, recursion and indirect calls through a function table */
NOINLINE static uint32_t fib_mix(uint32_t k, uint32_t s) {
    if (k < 2) return s ^ k;
    return fib_mix(k - 1, s * 3) + fib_mix(k - 2, s + 1) - (k & 1);
}
NOINLINE static uint32_t op_add(uint32_t a, uint32_t b) { return a + b; }
NOINLINE static uint32_t op_sub(uint32_t a, uint32_t b) { return a - b; }
NOINLINE static uint32_t op_rot(uint32_t a, uint32_t b) { return _rotl(a, b & 31) ^ b; }
NOINLINE static uint32_t op_min(uint32_t a, uint32_t b) { return (int32_t)a < (int32_t)b ? a : b; }
static uint32_t (*const ops[4])(uint32_t, uint32_t) = { op_add, op_sub, op_rot, op_min };

EXPORT uint64_t __cdecl t_calls(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint32_t acc = seed, i, big = 0;
    n &= 511;
    for (i = 0; i < n; i++) {
        acc = ops[in[i] & 3](acc, in[i]);
        if (in[i] > 200) { acc ^= fib_mix(in[i] & 7, acc); big++; }
        out[i & 255] = (uint8_t)(acc >> 8);
    }
    return acc | (uint64_t)big << 32;
}

/* string instructions (rep movsb, rep stosd) and a compare loop */
EXPORT uint64_t __cdecl t_string(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint32_t i, eq = 0;
    n &= 255;
    __movsb(out, in, n);
    __stosd((unsigned long*)(out + 256), seed, n >> 2);
    for (i = 0; i < n; i++)
        eq += out[i] == in[(i + seed) & 255];
    return eq | (uint64_t)out[n] << 32;
}

/* shifts by a variable count (flags change only for a nonzero count) and rotates */
EXPORT uint64_t __cdecl t_shift(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint32_t a = seed, i, z = 0;
    int32_t s = (int32_t)seed;
    n &= 1023;
    for (i = 0; i < n; i++) {
        uint32_t k = in[i];
        s >>= k & 3;
        s ^= (int32_t)(k << 24);
        a = _rotl(a, k) ^ _rotr(a, 3);
        if ((a >> (k & 31)) == 0) z++;
        z += (s >> (k & 15)) < 0;
        a += (a << (k & 7)) < a;
        out[i & 255] = (uint8_t)(a ^ (uint32_t)s);
    }
    return a | (uint64_t)(z + (uint32_t)s) << 32;
}

/* division with nonzero divisors, signed and unsigned */
EXPORT uint64_t __cdecl t_div(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    uint32_t i, q = seed | 1;
    int32_t r = 0;
    (void)out;
    n &= 1023;
    for (i = 0; i + 4 <= n; i += 4) {
        uint32_t v = rd(in + i);
        uint32_t d = (v & 0xFFFF) | 1;
        q = q / d + q % d * 7;
        if ((int32_t)v != INT32_MIN) r += (int32_t)v / (int32_t)(d | 2) - (int32_t)v % 13;
        if (q < 100) q += v;
    }
    return q | (uint64_t)(uint32_t)r << 32;
}

/* ---- hand-written sequences that keep flags alive where compiled code never does */
NOINLINE __declspec(naked) static void keep_flags(void) {
    __asm {
        mov eax, eax
        lea eax, [eax + 0]
        ret
    }
}

NOINLINE __declspec(naked) static void carry_in(void) {
    __asm {
        adc eax, 0
        ret
    }
}

/* CF from add survives inc (adc reads it); a shift by cl = 0 leaves the cmp flags for jb; sbb/cmc read CF;
 * flags of a cmp reach a jcc after a call to a flag-preserving function and after a label merge; a callee
 * reads the caller's CF */
EXPORT __declspec(naked) uint64_t __cdecl t_asm_flags(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    __asm {
        push ebx
        push esi
        push edi
        push ebp
        mov esi, [esp + 20]
        mov ebp, [esp + 24]
        mov ecx, [esp + 28]
        and ecx, 255
        mov eax, [esp + 32]
        xor edx, edx
        xor ebx, ebx
    top:
        test ecx, ecx
        jz done
        movzx edi, byte ptr [esi]
        cmp edi, 0x80
        call carry_in
        add eax, 0x9E3779B9
        inc ebx
        adc edx, 0
        add eax, edi
        push ecx
        mov ecx, edi
        and ecx, 3
        cmp eax, edx
        shl ebx, cl
        pop ecx
        jb below
        xor eax, 0x55
    below:
        sbb edi, edi
        add eax, edi
        cmc
        adc ebx, 0
        cmp ebx, eax
        call keep_flags
        jg greater
        dec edx
        jmp merge
    greater:
        inc edx
        test edi, 1
    merge:
        setz byte ptr [ebp]
        sete al
        inc ebp
        dec ecx
        inc esi
        jmp top
    done:
        cmp eax, ebx
        pop ebp
        pop edi
        pop esi
        pop ebx
        ret
    }
}

/* Interprocedural flag liveness (--opt iflags): the flags a callee returns (if_cmp), flags a callee leaves unwritten
 * for the caller (if_inc keeps CF), flags a callee reads from its caller (if_adc), a tail jump into a flag-returning
 * function whose direct callers read only CF while the tail path's caller reads ZF (if_tail -> if_cmp0), a function
 * called both directly and through a pointer (if_sub_ind: its returns must keep the flags the indirect site reads,
 * here ZF, although the direct site reads only CF) and an indirectly called callee that reads the caller's CF
 * (if_adc_ind, CF from a cmp: stc is materialized unconditionally). */
static __declspec(naked) void if_cmp(void) { __asm { cmp eax, edx
                                                     ret } }
static __declspec(naked) void if_inc(void) { __asm { inc eax
                                                     ret } }
static __declspec(naked) void if_adc(void) { __asm { adc eax, ebx
                                                     ret } }
static __declspec(naked) void if_cmp0(void) { __asm { cmp edx, 1   /* ZF opposite to the and in if_tail */
                                                      ret } }
static __declspec(naked) void if_tail(void) { __asm { and edx, 1
                                                      jmp if_cmp0 } }
static __declspec(naked) void if_sub_ind(void) { __asm { sub eax, edx
                                                         ret } }
static __declspec(naked) void if_adc_ind(void) { __asm { adc eax, 1
                                                         ret } }
EXPORT __declspec(naked) uint64_t __cdecl t_asm_iflags(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    __asm {
        push ebx
        push esi
        push edi
        push ebp
        mov esi, [esp + 20]
        mov ebp, [esp + 24]
        mov ecx, [esp + 28]
        and ecx, 127
        mov eax, [esp + 32]
        xor ebx, ebx
        mov edi, offset if_sub_ind
        jecxz if_done
    if_top:
        movzx edx, byte ptr [esi]
        call if_cmp
        jb if_a1
        add ebx, 3
    if_a1:
        cmp edx, 0x80
        call if_inc
        adc ebx, 0
        cmp eax, edx
        call if_adc
        jbe if_a2
        xor ebx, 0x55
    if_a2:
        call if_cmp0
        adc ebx, 0
        push edx
        call if_tail
        setz dl
        add bl, dl
        pop edx
        call if_sub_ind
        sbb ebx, 0
        call edi
        setz dl
        add bl, dl
        cmp ebx, 0x40
        mov edx, offset if_adc_ind
        call edx
        add ebx, eax
        mov byte ptr [ebp], bl
        inc ebp
        inc esi
        dec ecx
        jnz if_top
    if_done:
        mov edx, eax
        mov eax, ebx
        pop ebp
        pop edi
        pop esi
        pop ebx
        ret
    }
}

/* loop/loopne/jecxz, flags read across a backward edge, and flags returned to the caller */
EXPORT __declspec(naked) uint64_t __cdecl t_asm_loops(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    __asm {
        push ebx
        push esi
        mov esi, [esp + 12]
        mov ecx, [esp + 20]
        and ecx, 127
        mov eax, [esp + 24]
        xor edx, edx
        jecxz empty
        cmp eax, 0x80000000
    again:
        mov bl, byte ptr [esi]
        jae hi
        add edx, 3
    hi:
        inc esi
        cmp bl, 0x7F
        loopne again
        jecxz empty
        cmp bl, 0x10
        jb again2
        add eax, edx
    again2:
        sub eax, 1
        loop again2
    empty:
        mov ecx, eax
        shr ecx, 5
        and ecx, 7
        neg eax
        shr edx, cl
        sbb eax, 0
        imul edx, edx, 3
        jo ovf
        jmp fin
    ovf:
        or eax, 1
    fin:
        test eax, eax
        pop esi
        pop ebx
        ret
    }
}

/* --opt sse: x87 compares of arbitrary float/double bit patterns (NaN payloads, signed zeros, infinities, denormals) in
 * register, memory and ftst forms, and fst/fstp dword/qword to unaligned, overlapping and adjacent out addresses whose
 * neighbouring bytes stay observable: a wrong store width or a wrong unordered/equal rule changes the result. A double
 * NaN from `in` is replaced by the float at the same address before it is stored as a double (x87 fld quiets a
 * signalling NaN, the double model keeps its bits: an existing, unrelated model difference the test avoids). */
EXPORT __declspec(naked) uint64_t __cdecl t_asm_sse(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    __asm {
        push esi
        push edi
        push ebx
        mov esi, [esp + 16]
        mov edi, [esp + 20]
        mov ecx, [esp + 24]
        and ecx, 31
        mov ebx, [esp + 28]
        test ecx, ecx
        jz sse_done
    sse_top:
        fld dword ptr [esi]
        fld qword ptr [esi + 4]
        fucom st(0)
        fnstsw ax
        test ah, 4
        jz sse_ordered
        fstp st(0)
        fld dword ptr [esi + 4]
    sse_ordered:
        fcom st(1)
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        fcom dword ptr [esi + 1]
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        fucom st(1)
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        fcom qword ptr [esi + 4]
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        ftst
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        fst dword ptr [edi + 1]
        fst qword ptr [edi + 3]
        fxch st(1)
        fst dword ptr [edi + 9]
        fcomp dword ptr [edi + 9]
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        fstp qword ptr [edi + 16]
        mov byte ptr [edi + 20], bl
        fld dword ptr [edi + 16]
        fucomp st(0)
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        rol ebx, 3
        fldz
        fld dword ptr [esi + 12]
        fucompp
        fnstsw ax
        and eax, 0x4500
        xor ebx, eax
        add esi, 13
        add edi, 24
        dec ecx
        jnz sse_top
    sse_done:
        mov eax, ebx
        xor edx, edx
        pop ebx
        pop edi
        pop esi
        ret
    }
}

/* --opt x87w: x87 values written (not yet stored to c->st) when control leaves the straight-line run: a conditional
 * forward branch, a block falling through into a label, a backward loop edge, an early exit with values on the stack,
 * fxch, and popped slots (the model keeps a popped value in c->st; the full-state compare sees all eight). */
EXPORT __declspec(naked) uint64_t __cdecl t_asm_x87w(const uint8_t* in, uint8_t* out, uint32_t n, uint32_t seed) {
    __asm {
        push esi
        push edi
        mov esi, [esp + 12]
        mov edi, [esp + 16]
        mov ecx, [esp + 20]
        and ecx, 15
        fld1
        fild dword ptr [esp + 24]
        fmul qword ptr [k_decay]
        test ecx, ecx
        jz w_done
    w_top:
        fild word ptr [esi]
        fadd st(0), st(2)
        fxch st(1)
        fsub st(0), st(1)
        test byte ptr [esi + 2], 1
        jz w_skip
        fld st(1)
        fmulp st(1), st(0)
        fxch st(2)
        fadd qword ptr [k_decay]
        fxch st(2)
    w_skip:
        fld st(0)
        fstp dword ptr [edi]
        fxch st(1)
        fstp st(0)
        fmul qword ptr [k_decay]
        add esi, 3
        add edi, 4
        dec ecx
        jnz w_top
    w_done:
        fstp qword ptr [edi]
        fstp qword ptr [edi + 8]
        mov eax, [edi]
        mov edx, [edi + 12]
        pop edi
        pop esi
        ret
    }
}
