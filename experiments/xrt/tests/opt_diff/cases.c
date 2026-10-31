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
