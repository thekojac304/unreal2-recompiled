"""Translate one SSE2 math function of msvcr70.dll to C (x64, SSE2 intrinsics: the host executes the same SSE2
operations, so the double-precision results are bit-identical by construction of the instruction semantics).

  python -I tools/xrt/lift_sse2.py <msvcr70.dll> <entry VA hex> <C function name> --out <file.c>

The generated function is

  double <name>(double x, double y, const uint8_t* img, uint32_t* error_type)

with x at [esp+4] and y at [esp+0xc] on entry (the layout msvcr70's _CIpow wrapper builds for its SSE2 core), `img`
the DLL's image laid out at its preferred base (constant tables are read from it) and *error_type set to the code
the function passes to the DLL's math error handler (0 if none). The handler call itself is not translated: it
sets errno and consults _matherr, neither of which the runtime models; the result is the value the function stores
for it (checked against the DLL by tools/xrt/tests/crt_gatef). Anything outside the supported instruction subset
stops the translation. The output is a machine translation of proprietary code: write it under
experiments/xrt/gen/ (git-ignored), never commit it.
"""
import argparse
import hashlib
import os
import re
import sys

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ERROR_HANDLER = None   # set from the command line: the call target that is the math error handler

GPR = {"eax", "ecx", "edx", "esi", "edi", "ebx", "esp"}   # esp: an offset into the local stack array
GPR16 = {"ax": "eax", "cx": "ecx", "dx": "edx"}
XMM = {f"xmm{i}" for i in range(8)}


class Unsupported(Exception):
    pass


def mem_expr(op, base):
    """C expression (const uint8_t* / uint8_t*) for a memory operand."""
    m = re.fullmatch(r"(?:(byte|word|dword|qword|xmmword) ptr )?\[(.+)\]", op)
    if not m:
        raise Unsupported(op)
    inner = m.group(2).replace(" ", "")
    m2 = re.fullmatch(r"esp(?:([+-])0x([0-9a-f]+)|([+-])(\d+))?", inner)
    if m2:
        off = 0
        if m2.group(2):
            off = int(m2.group(2), 16) * (1 if m2.group(1) == "+" else -1)
        elif m2.group(4):
            off = int(m2.group(4)) * (1 if m2.group(3) == "+" else -1)
        return f"(stk + esp + {off})"
    m2 = re.fullmatch(r"0x([0-9a-f]+)", inner)
    if m2:
        return f"(img + 0x{int(m2.group(1), 16) - base:x}u)"
    m2 = re.fullmatch(r"(e[a-d]x|e[sd]i)(?:\*(\d))?\+0x([0-9a-f]+)", inner)
    if m2:
        scale = int(m2.group(2) or 1)
        return f"(img + {m2.group(1)} * {scale}u + 0x{int(m2.group(3), 16) - base:x}u)"
    raise Unsupported(op)


def imm(op):
    if re.fullmatch(r"-?0x[0-9a-f]+|-?\d+", op):
        v = int(op, 0) & 0xFFFFFFFF
        return f"0x{v:x}u"
    raise Unsupported(op)


def src32(op, base):
    if op in GPR:
        return op
    if op.startswith("dword ptr"):
        return f"ld32{mem_expr(op, base)}"
    return imm(op)


def xsrc(op, base, width):
    """__m128i operand: a register, or memory (64-bit loads zero the upper half, as a scalar load does)"""
    if op in XMM:
        return op
    p = mem_expr(op, base)
    return f"ld128{p}" if width == 128 else f"ld64x{p}"


def translate(ins, base, nxt):
    m, ops = ins.mnemonic, [o.strip() for o in ins.op_str.split(",")] if ins.op_str else []
    d = ops[0] if ops else None
    s = ops[1] if len(ops) > 1 else None

    def pd(x):
        return f"_mm_castsi128_pd({x})"

    def si(x):
        return f"_mm_castpd_si128({x})"

    def flags(kind, a, b, r):
        return f"fl_{kind}({a}, {b}, {r});"

    if m == "movlpd":
        if d in XMM:
            return f"{d} = {si(f'_mm_loadl_pd({pd(d)}, (const double*){mem_expr(s, base)})')};"
        return f"_mm_storel_pd((double*){mem_expr(d, base)}, {pd(s)});"
    if m == "movsd" and d in XMM and s in XMM:
        return f"{d} = {si(f'_mm_move_sd({pd(d)}, {pd(s)})')};"
    if m == "movapd":
        return f"{d} = {xsrc(s, base, 128)};"
    if m in ("andpd", "orpd", "xorpd", "pxor"):
        f = {"andpd": "_mm_and_si128", "orpd": "_mm_or_si128", "xorpd": "_mm_xor_si128", "pxor": "_mm_xor_si128"}[m]
        return f"{d} = {f}({d}, {xsrc(s, base, 128)});"
    if m in ("mulsd", "addsd", "subsd", "divsd"):
        f = {"mulsd": "_mm_mul_sd", "addsd": "_mm_add_sd", "subsd": "_mm_sub_sd", "divsd": "_mm_div_sd"}[m]
        return f"{d} = {si(f'{f}({pd(d)}, {pd(xsrc(s, base, 64))})')};"
    if m in ("mulpd", "addpd"):
        f = {"mulpd": "_mm_mul_pd", "addpd": "_mm_add_pd"}[m]
        return f"{d} = {si(f'{f}({pd(d)}, {pd(xsrc(s, base, 128))})')};"
    if m in ("psrlq", "psllq"):
        if s in XMM:
            f = "_mm_srl_epi64" if m == "psrlq" else "_mm_sll_epi64"
            return f"{d} = {f}({d}, {s});"
        f = "_mm_srli_epi64" if m == "psrlq" else "_mm_slli_epi64"
        return f"{d} = {f}({d}, {int(s, 0)});"
    if m == "pextrw":
        return f"{d} = (uint32_t)_mm_extract_epi16({s}, {int(ops[2], 0)});"
    if m == "pinsrw":
        return f"{d} = _mm_insert_epi16({d}, (int)({s} & 0xFFFF), {int(ops[2], 0)});"
    if m == "cvtdq2pd":
        return f"{d} = {si(f'_mm_cvtepi32_pd({s})')};"
    if m == "cvtsd2si":
        return f"{d} = (uint32_t)_mm_cvtsd_si32({pd(s)});"
    if m == "unpcklpd":
        return f"{d} = {si(f'_mm_unpacklo_pd({pd(d)}, {pd(s)})')};"
    if m == "pshufd":
        return f"{d} = _mm_shuffle_epi32({s}, {int(ops[2], 0)});"
    if m == "movd":
        if d in XMM:
            return f"{d} = _mm_cvtsi32_si128((int){s});"
        return f"{d} = (uint32_t)_mm_cvtsi128_si32({s});"
    if m in ("psubq", "psubd", "pcmpeqd", "pmaxsw"):
        f = {"psubq": "_mm_sub_epi64", "psubd": "_mm_sub_epi32", "pcmpeqd": "_mm_cmpeq_epi32", "pmaxsw": "_mm_max_epi16"}[m]
        return f"{d} = {f}({d}, {s});"
    if m == "pmovmskb":
        return f"{d} = (uint32_t)_mm_movemask_epi8({s});"
    # ---- integer
    if m == "mov":
        if d in GPR:
            return f"{d} = {src32(s, base)};"
        if d.startswith("dword ptr"):
            return f"st32({mem_expr(d, base)}, {src32(s, base)});"
        if d == "ax" and s.startswith("word ptr"):
            return f"eax = (eax & 0xFFFF0000u) | ld16{mem_expr(s, base)};"
        raise Unsupported(ins.op_str)
    if m in ("and", "or", "xor", "add", "sub", "cmp"):
        if d in GPR16:
            d32, mask = GPR16[d], "0xFFFF"
            sv = GPR16.get(s, None)
            sv = f"({sv} & 0xFFFFu)" if sv else imm(s)
            a = f"({d32} & 0xFFFFu)"
            if m != "cmp":
                raise Unsupported(ins.op_str)
            return f"fl_sub16({a}, {sv});"
        sv = src32(s, base)
        op = {"and": "&", "or": "|", "xor": "^", "add": "+", "sub": "-", "cmp": "-"}[m]
        kind = {"and": "logic", "or": "logic", "xor": "logic", "add": "add", "sub": "sub", "cmp": "sub"}[m]
        if m == "cmp":
            return f"{{ uint32_t r_ = {d} - {sv}; {flags(kind, d, sv, 'r_')} }}"
        return f"{{ uint32_t b_ = {sv}, a_ = {d}; {d} = a_ {op} b_; {flags(kind, 'a_', 'b_', d)} }}"
    if m == "neg":
        return f"{{ uint32_t a_ = {d}; {d} = 0u - a_; fl_sub(0u, a_, {d}); }}"
    if m == "shl":
        return f"{d} <<= {int(s, 0)};"
    if m == "sar":
        return f"{d} = (uint32_t)((int32_t){d} >> {int(s, 0)});"
    if m == "push":
        return f"esp -= 4; st32(stk + esp, {d});"
    if m == "pop":
        return f"{d} = ld32(stk + esp); esp += 4;"
    if m in ("fld", "fldz", "fld1"):
        if m == "fldz":
            return "fret = 0.0;"
        if m == "fld1":
            return "fret = 1.0;"
        return f"memcpy(&fret, {mem_expr(d, base)}, 8);"
    if m == "ret":
        return "return fret;"
    if m == "call":
        if int(d, 16) != ERROR_HANDLER:
            raise Unsupported(f"call {d}")
        # (pointer args at [esp], [esp+4], [esp+8]; the error type at [esp+0xc]; the result slot at [esp+0x10])
        return "*error_type = ld32(stk + esp + 12);"
    cond = {"je": "ZF", "jne": "!ZF", "ja": "(!CF && !ZF)", "jae": "!CF", "jb": "CF", "jbe": "(CF || ZF)",
            "jg": "(!ZF && SF == OF)", "jge": "(SF == OF)", "jl": "(SF != OF)", "jle": "(ZF || SF != OF)", "js": "SF"}
    if m in cond:
        return f"if ({cond[m]}) goto L_{int(d, 16):08x};"
    if m == "jmp":
        return f"goto L_{int(d, 16):08x};"
    raise Unsupported(f"{m} {ins.op_str}")


def main():
    global ERROR_HANDLER
    ap = argparse.ArgumentParser()
    ap.add_argument("dll")
    ap.add_argument("entry")
    ap.add_argument("name")
    ap.add_argument("--error-handler", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ERROR_HANDLER = int(a.error_handler, 16)
    raw = open(a.dll, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    entry = int(a.entry, 16)
    seen, work, targets = {}, [entry], set()
    while work:
        va = work.pop()
        while va not in seen:
            ins = next(md.disasm(image[va - base: va - base + 16], va), None)
            if ins is None:
                sys.exit(f"cannot decode at {va:#x}")
            seen[va] = ins
            m = ins.mnemonic
            if m.startswith("j"):
                t = int(ins.op_str, 16)
                targets.add(t)
                work.append(t)
                if m == "jmp":
                    break
            if m == "ret":
                break
            va += ins.size
    order = sorted(seen)
    body = []
    for i, va in enumerate(order):
        ins = seen[va]
        nxt = order[i + 1] if i + 1 < len(order) else None
        if i and order[i - 1] + seen[order[i - 1]].size != va:
            prev = seen[order[i - 1]]
            if prev.mnemonic not in ("jmp", "ret"):
                body.append(f"    goto L_{va:08x};")
        try:
            c = translate(ins, base, nxt)
        except Unsupported as e:
            sys.exit(f"unsupported at {va:#x}: {ins.mnemonic} {ins.op_str} ({e})")
        label = f"L_{va:08x}: " if va in targets else ""
        body.append(f"    {label}{c} /* {va:08x} {ins.mnemonic} {ins.op_str} */")
    last = seen[order[-1]]
    if last.mnemonic not in ("jmp", "ret"):
        sys.exit("the function does not end with jmp/ret")
    used = {f"L_{t:08x}" for t in targets}
    defined = {f"L_{va:08x}" for va in order}
    if used - defined:
        sys.exit(f"jump targets outside the function: {sorted(used - defined)}")
    src = f"""/* GENERATED by tools/xrt/lift_sse2.py - machine translation of proprietary code (msvcr70.dll), do not commit.
 * source: {a.dll.replace(chr(92), '/')} sha256 {sha}, function {entry:#x}, {len(order)} instructions */
#include <emmintrin.h>
#include <stdint.h>
#include <string.h>

const char {a.name}_sha256[] = "{sha}";

static uint32_t ld32(const uint8_t* p) {{ uint32_t v; memcpy(&v, p, 4); return v; }}
static uint32_t ld16(const uint8_t* p) {{ uint16_t v; memcpy(&v, p, 2); return v; }}
static void st32(uint8_t* p, uint32_t v) {{ memcpy(p, &v, 4); }}
static __m128i ld128(const uint8_t* p) {{ return _mm_loadu_si128((const __m128i*)p); }}
static __m128i ld64x(const uint8_t* p) {{ return _mm_loadl_epi64((const __m128i*)p); }}

double {a.name}(double x, double y, const uint8_t* img, uint32_t* error_type) {{
    __m128i xmm0 = _mm_setzero_si128(), xmm1 = xmm0, xmm2 = xmm0, xmm3 = xmm0, xmm4 = xmm0, xmm5 = xmm0, xmm6 = xmm0,
            xmm7 = xmm0;
    uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0, esi = 0, edi = 0, esp = 256;
    uint8_t stk[512];
    int ZF = 0, SF = 0, CF = 0, OF = 0;
    double fret = 0.0;
#define fl_logic(a, b, r) (ZF = (r) == 0, SF = (int)((r) >> 31), CF = 0, OF = 0)
#define fl_add(a, b, r) (ZF = (r) == 0, SF = (int)((r) >> 31), CF = (r) < (a), OF = (int)((~((a) ^ (b)) & ((a) ^ (r))) >> 31))
#define fl_sub(a, b, r) (ZF = (r) == 0, SF = (int)((r) >> 31), CF = (a) < (b), OF = (int)((((a) ^ (b)) & ((a) ^ (r))) >> 31))
#define fl_sub16(a, b) do {{ uint32_t r16_ = ((a) - (b)) & 0xFFFFu; ZF = r16_ == 0; SF = (int)(r16_ >> 15); CF = (a) < (b); OF = (int)(((((a) ^ (b)) & ((a) ^ r16_)) >> 15) & 1); }} while (0)
    memset(stk, 0, sizeof stk);
    memcpy(stk + esp + 4, &x, 8);
    memcpy(stk + esp + 12, &y, 8);
    *error_type = 0;
    (void)ebx; (void)esi; (void)edi;
{chr(10).join(body)}
#undef fl_logic
#undef fl_add
#undef fl_sub
#undef fl_sub16
}}
"""
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="\n") as f:
        f.write(src)
    print(f"{a.name}: {len(order)} instructions from {entry:#x} -> {a.out}")


if __name__ == "__main__":
    main()
