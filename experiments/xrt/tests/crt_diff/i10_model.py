"""Python model of msvcr70's double -> decimal digit generation (_fltout2 = __dtold + $I10_OUTPUT(ld, 17)).

Written from the published CRT algorithm (x10fout.c / mantold.c / tenpow.c) and checked against the real DLL
by this test. Used to (1) generate the power-of-ten tables for runtime/xrt_fmt.c from exact arithmetic and
(2) cross-check the C port. `--check-dll` compares the generated tables with the ones inside the sandbox copy
of msvcr70.dll (read-only; nothing from the DLL is stored).

12-byte numbers (_LDBL12) are modelled as 96-bit integers: bits 0..79 mantissa (bit 79 explicit leading 1),
bits 80..95 exponent (bias 0x3FFF) with the sign in bit 95.
"""
import argparse
import struct
import sys
from fractions import Fraction

M96 = (1 << 96) - 1


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def ld12mul(x, y):
    """__ld12mul: truncated 80x80-bit product (partial products of words i+j >= 4), round to nearest-even"""
    ex, ey = (x >> 80) & 0xFFFF, (y >> 80) & 0xFFFF
    sign = (ex ^ ey) & 0x8000
    ex &= 0x7FFF
    ey &= 0x7FFF
    es = ex + ey
    if ex >= 0x7FFF or ey >= 0x7FFF or (es & 0xFFFF) > 0xBFFD:
        return (0x7FFF | sign) << 80 | 0x8000 << 64
    if (es & 0xFFFF) <= 0x3FBF:
        return 0
    if ex == 0:
        es += 1
        if x & ((1 << 80) - 1) == 0 and not (x >> 80) & 0x7FFF:
            return (x & ((1 << 80) - 1)) | sign << 80
    if ey == 0:
        es += 1
        if y & ((1 << 80) - 1) == 0 and not (y >> 80) & 0x7FFF:
            return 0
    t = [0] * 7          # tempman words (index 6 only absorbs an impossible carry)
    for i in range(5):
        for j in range(5 - i):
            prod = ((x >> 16 * (i + j)) & 0xFFFF) * ((y >> 16 * (4 - j)) & 0xFFFF)
            r = (t[i] | t[i + 1] << 16) + prod
            t[i], t[i + 1] = r & 0xFFFF, (r >> 16) & 0xFFFF
            if r >> 32:
                t[i + 2] = (t[i + 2] + 1) & 0xFFFF
    tm = sum(t[k] << 16 * k for k in range(6))
    es = (es + 0xC002) & 0xFFFFFFFF
    if s16(es) > 0:
        while not tm >> 95:
            tm = (tm << 1) & M96
            es = (es + 0xFFFF) & 0xFFFFFFFF
            if s16(es) <= 0:
                break
    if s16(es) <= 0:
        es = (es + 0xFFFF) & 0xFFFFFFFF
        if s16(es) < 0:
            n = (-es) & 0xFFFF
            es = (es + n) & 0xFFFFFFFF
            sticky = 0
            for _ in range(n):
                sticky += tm & 1
                tm >>= 1
            if sticky:
                tm |= 1
    if (tm & 0xFFFF) > 0x8000 or (tm & 0x1FFFF) == 0x18000:
        a, b, c = (tm >> 16) & 0xFFFFFFFF, (tm >> 48) & 0xFFFFFFFF, (tm >> 80) & 0xFFFF
        if a == 0xFFFFFFFF:
            a = 0
            if b == 0xFFFFFFFF:
                b = 0
                if c == 0xFFFF:
                    es += 1
                    c = 0x8000
                else:
                    c += 1
            else:
                b += 1
        else:
            a += 1
        tm = (tm & 0xFFFF) | a << 16 | b << 48 | c << 80
    if (es & 0xFFFF) >= 0x7FFF:
        return (0x7FFF | sign) << 80 | 0x8000 << 64
    return ((es | sign) & 0xFFFF) << 80 | (tm >> 16)


def ld12_of_fraction(v):
    """table entry for a positive rational: 64-bit mantissa rounded to nearest (ties to even); the low word
    holds the next 16 bits of the value rounded to nearest at 80 bits, as tenpow.c stores them"""
    e = v.numerator.bit_length() - v.denominator.bit_length()
    if Fraction(2) ** e > v:
        e -= 1
    scaled = v / Fraction(2) ** (e - 79)          # in [2^79, 2^80)
    t80 = scaled.numerator // scaled.denominator
    if scaled - t80 >= Fraction(1, 2):             # the low word is rounded to nearest (ties up)
        t80 += 1
    s64 = v / Fraction(2) ** (e - 63)
    m64 = s64.numerator // s64.denominator
    rem = s64 - m64
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and m64 & 1):
        m64 += 1
    exp = 0x3FFF + e
    if m64 >> 64:                                  # rounding carried out of 64 bits
        m64 >>= 1
        exp += 1
    return exp << 80 | m64 << 16 | (t80 & 0xFFFF)


GROUPS = 3        # 10^1..10^7, 10^8..10^56, 10^64..10^448: enough for every double (|exponent| < 512)
POS = [ld12_of_fraction(Fraction(10) ** (d * 8 ** g)) for g in range(GROUPS) for d in range(1, 8)]
NEG = [ld12_of_fraction(Fraction(1, 10 ** (d * 8 ** g))) for g in range(GROUPS) for d in range(1, 8)]
ONE_TENTH = 0x3FFB << 80 | int("CC" * 10, 16)    # 1/10 truncated to 80 bits, as $I10_OUTPUT uses it


def multtenpow12(x, pw):
    if pw == 0:
        return x
    table = POS
    if pw < 0:
        pw, table = -pw, NEG
    g = 0
    while pw:
        last3 = pw & 7
        pw >>= 3
        if last3:
            y = table[g * 7 + last3 - 1]
            if (y & 0xFFFF) >= 0x8000:            # "unround": the stored 64-bit mantissa was rounded up
                lo = (((y >> 16) & 0xFFFFFFFF) - 1) & 0xFFFFFFFF
                y = (y & ~(0xFFFFFFFF << 16)) | lo << 16
            x = ld12mul(x, y)
        g += 1
    return x


def dtold(bits):
    exp, sign = (bits >> 52) & 0x7FF, bits >> 63
    manhi, manlo = (bits >> 32) & 0xFFFFF, bits & 0xFFFFFFFF
    msb = 0x80000000
    if exp == 0x7FF:
        ldexp = 0x7FFF
    elif exp == 0:
        if manhi == 0 and manlo == 0:
            return 0, 0, 0                         # the sign of -0.0 is dropped
        ldexp = 0x3FFF - 0x3FF + 1
        msb = 0
    else:
        ldexp = exp + 0x3FFF - 0x3FF
    mh = ((manhi << 11) | msb | (manlo >> 21)) & 0xFFFFFFFF
    ml = (manlo << 11) & 0xFFFFFFFF
    while not mh & 0x80000000:
        mh = ((mh << 1) | (ml >> 31)) & 0xFFFFFFFF
        ml = (ml << 1) & 0xFFFFFFFF
        ldexp -= 1
    return (sign << 15 | ldexp) & 0xFFFF, mh, ml


def i10_output(expw, manhi, manlo, ndigits=17, fformat=False):
    """returns (sign char, decimal exponent, mantissa digit string)"""
    sign = "-" if expw & 0x8000 else " "
    expn = expw & 0x7FFF
    if expn == 0 and manhi == 0 and manlo == 0:
        return " ", 0, "0"
    if expn == 0x7FFF:
        if manhi == 0x80000000 and manlo == 0:
            return sign, 1, "1#INF"
        if not manhi & 0x40000000:
            return sign, 1, "1#SNAN"
        if sign == "-" and manhi == 0xC0000000 and manlo == 0:
            return sign, 1, "1#IND"
        return sign, 1, "1#QNAN"
    r = s32(expn * 0x4D10 + ((expn >> 8) + 2 * (manhi >> 24)) * 0x4D - 0x134312F4)
    ir = s16(r >> 16)
    x = expn << 80 | manhi << 48 | manlo << 16
    x = multtenpow12(x, -ir)
    if (x >> 80) & 0xFFFF >= 0x3FFF:
        ir += 1
        x = ld12mul(x, ONE_TENTH)
    dexp = ir
    if fformat:
        ndigits += ir
        if ndigits <= 0:
            return " ", 0, "0"
    ndigits = min(ndigits, 21)
    ub = ((x >> 80) & 0xFFFF) - 0x3FFE
    x &= (1 << 80) - 1
    x = (x << 8) & M96
    if ub < 0:
        x >>= (-ub) & 0xFF
    dig = []
    for _ in range(ndigits + 1):
        x = (x * 10) & M96
        dig.append(x >> 88)
        x &= (1 << 88) - 1
    p = ndigits - 1
    if dig[ndigits] >= 5:
        while p >= 0 and dig[p] == 9:
            dig[p] = 0
            p -= 1
        if p < 0:
            p = 0
            dexp += 1
        dig[p] += 1
    else:
        while p >= 0 and dig[p] == 0:
            p -= 1
        if p < 0:
            return " ", 0, "0"
    return sign, dexp, "".join(chr(48 + d) for d in dig[:p + 1])


def fltout(bits):
    return i10_output(*dtold(bits))


def e16(bits):
    """what msvcr70 prints for %.16e (all 17 digits of the mantissa, no further rounding)"""
    sign, dexp, man = fltout(bits)
    if not man[0].isdigit() or "#" in man:
        return None
    man = (man + "0" * 17)[:17]
    e = dexp - 1 if man[0] != "0" else 0
    return "%s%s.%se%s%03d" % ("-" if sign == "-" else "", man[0], man[1:], "-" if e < 0 else "+", abs(e))


def check_dll(path):
    import pefile
    pe = pefile.PE(path, fast_load=True)
    img = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    ok = True
    # the tables sit next to each other in .data; find each generated entry
    for name, tab in (("pos", POS), ("neg", NEG)):
        blob = b"".join(v.to_bytes(12, "little") for v in tab)
        k = img.find(blob)
        print("%s table (%d entries): %s" % (name, len(tab), "found at %#x" % (base + k) if k >= 0 else "NOT FOUND"))
        ok &= k >= 0
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-dll")
    ap.add_argument("--c-tables", action="store_true", help="print the tables as C initialisers")
    a = ap.parse_args()
    if a.check_dll:
        sys.exit(0 if check_dll(a.check_dll) else 1)
    if a.c_tables:
        for name, tab in (("pow10_pos", POS), ("pow10_neg", NEG)):
            print("static const Ld12 %s[%d] = {" % (name, len(tab)))
            for k, v in enumerate(tab):
                g, d = divmod(k, 7)
                words = ", ".join("0x%04X" % ((v >> 16 * i) & 0xFFFF) for i in range(6))
                print("    {{%s}},   /* 1e%s%d */" % (words, "-" if tab is NEG else "", (d + 1) * 8 ** g))
            print("};")


if __name__ == "__main__":
    main()
