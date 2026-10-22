"""Generate the corpus of the msvcr70 differential test (see README.md).

Line kinds (read by crt_diff_core.h):
  P <id> <fmt> <arg>*        _vsnwprintf: unbounded, then counts 0, L-1, L, L+1 (L = full length)
  C <id> <counts> <fmt> <arg>*   _vsnwprintf with explicit counts (comma separated, decimal)
  W <id> <fmt> <arg>*        wprintf to stdout
  A <id> <fmt bytes> <arg>*  narrow sprintf (output length probed first; SKIP when 65536 characters or more)
  S <id> <func> <arg>*       string function (w<hex> string, b<cap>,<hex> buffer, u<hex8> integer, 0 null)
  M <id> <size> <dst> <src> <n>   memmove inside one byte buffer
  R <id> <seed hex8|-> <n>   srand(seed) (unless '-') then n x rand()
<fmt> and wide strings are hex UTF-16 code units ('~' = empty). printf arguments: i<hex8> int32,
q<hex16> int64, d<hex16> double bits, w<hex> wide string, a<hex> narrow string, n<k> pointer to %n slot k,
c<len>,<max>,<hex|~|!> counted string (! = NULL buffer), 0 NULL. Unused argument words are 0.
"""
import argparse
import random
import struct

INF = float("inf")


def units(s):
    if isinstance(s, (list, tuple)):
        return list(s)
    out = []
    for ch in s:
        o = ord(ch)
        if o > 0xFFFF:
            o -= 0x10000
            out += [0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)]
        else:
            out.append(o)
    return out


def hx(s):
    return "".join("%04X" % u for u in units(s)) or "~"


def I(v):
    return "i%08X" % (v & 0xFFFFFFFF)


def Q(v):
    return "q%016X" % (v & 0xFFFFFFFFFFFFFFFF)


def D(x):
    return "d%016X" % struct.unpack("<Q", struct.pack("<d", x))[0]


def DB(bits):
    return "d%016X" % bits


def W(s):
    return "w" + hx(s)


def A(b):
    return "a" + (b.hex().upper() or "~")


def CS(length, maxlen, data):
    if data is None:
        return "c%d,%d,!" % (length, maxlen)
    return "c%d,%d,%s" % (length, maxlen, data.hex().upper() or "~")


NULL = "0"


class Corpus:
    def __init__(self):
        self.lines = []
        self.counts = {}

    def _id(self, cat):
        n = self.counts.get(cat, 0)
        self.counts[cat] = n + 1
        return "%s.%d" % (cat, n)

    def P(self, cat, fmt, *args):
        self.lines.append(" ".join(["P", self._id(cat), hx(fmt)] + list(args)))

    def C(self, cat, counts, fmt, *args):
        self.lines.append(" ".join(["C", self._id(cat), ",".join(str(c) for c in counts), hx(fmt)] + list(args)))

    def W(self, cat, fmt, *args):
        self.lines.append(" ".join(["W", self._id(cat), hx(fmt)] + list(args)))

    def S(self, cat, func, *args):
        self.lines.append(" ".join(["S", self._id(cat), func] + list(args)))

    def M(self, cat, size, dst, src, n):
        self.lines.append("M %s %d %d %d %d" % (self._id(cat), size, dst, src, n))

    def R(self, cat, seed, n):
        self.lines.append("R %s %s %d" % (self._id(cat), "-" if seed is None else "%08X" % (seed & 0xFFFFFFFF), n))

    def A(self, cat, fmt, *args):
        """narrow sprintf; fmt is bytes or a str of code points <= 0xFF (other formats are not narrow: dropped)"""
        if isinstance(fmt, str):
            if any(ord(ch) > 0xFF for ch in fmt):
                return
            fmt = fmt.encode("latin-1")
        self.lines.append(" ".join(["A", self._id(cat), fmt.hex().upper() or "~"] + list(args)))


class Narrow:
    """Routes the printf generators' cases to narrow sprintf ('A' lines, categories prefixed with 'n'). Numeric
    arguments mean the same in the narrow and the wide printf; string and character conversions do not (narrow
    %s is a narrow string), so those generators' string arguments only exercise identical bytes on both sides,
    and gen_str_narrow types them for the narrow _output."""

    def __init__(self, c):
        self.c = c

    def P(self, cat, fmt, *args):
        self.c.A("n" + cat, fmt, *args)

    def C(self, cat, counts, fmt, *args):
        self.c.A("n" + cat, fmt, *args)

    def W(self, *a):
        pass


FLAGS = "-+ #0"
ALL_FLAGS = ["".join(c for i, c in enumerate(FLAGS) if m >> i & 1) for m in range(32)]
ODD_FLAGS = ["0-", "#-0+ ", "--", "00", "++", "  ", "+ ", " +", "0#", "-0", "#0-", "0+-# "]

INT32 = [0, 1, -1, 7, 8, 9, 10, 15, 16, 255, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF,
         123456789, -123456789, 0x12345678, -32768, -32769, 0x1FFFF]
INT64 = [0, 1, -1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x100000000, 0x7FFFFFFFFFFFFFFF, -0x8000000000000000, -2,
         1234567890123456789, -1234567890123456789, 0xFFFFFFFF00000000, 0x123456789ABCDEF0]
SIZES = ["", "h", "l", "w", "I", "I32", "I64", "L", "ll", "hh", "N", "F", "lh", "hl", "I64h", "hI64", "I32I64",
         "I64I32"]


def is64(size):
    """msvcr70: the last I32/I64 wins"""
    k64, k32 = size.rfind("I64"), size.rfind("I32")
    return k64 >= 0 and k64 > k32


def width_choices(rng):
    w = rng.choice(["", "1", "2", "7", "12", "25", "*", "*", "0"])
    args = []
    if w == "*":
        args.append(I(rng.choice([9, -9, 0, 1, -1, 3, 20, -20, -0x7FFFFFFF])))
    return w, args


def prec_choices(rng, big=True):
    p = rng.choice([""] * 3 + [".", ".0", ".1", ".2", ".5", ".6", ".12", ".40", ".*", ".*"] + ([".600", ".513"] if big else []))
    args = []
    if p == ".*":
        args.append(I(rng.choice([3, -1, -7, 0, 1, 30, 600 if big else 30])))
    return p, args


def gen_int(c, rng):
    convs = "diuoxX"
    for flags in ALL_FLAGS + ODD_FLAGS:
        for conv in convs:
            for size in SIZES:
                for _ in range(2):
                    w, wa = width_choices(rng)
                    p, pa = prec_choices(rng)
                    spec = "%" + flags + w + p + size + conv
                    vals = rng.sample(INT64 if is64(size) else INT32, 4)
                    if is64(size) and rng.random() < 0.5:
                        vals[0] = rng.getrandbits(64)
                    fmt = "|".join([spec] * len(vals))
                    args = []
                    for v in vals:
                        args += wa + pa + [Q(v) if is64(size) else I(v)]
                    c.P("int", "[" + fmt + "]", *args)
    # deterministic sweep: width x precision for a few specs
    for conv in convs:
        for w in ["", "0", "1", "5", "11", "-5", "05", "-05"]:
            for p in ["", ".", ".0", ".1", ".3", ".11", ".512", ".600", ".1000"]:
                for flags in ["", "#", "+", " ", "0", "-"]:
                    spec = "%" + flags + w + p + conv
                    c.P("intsweep", spec + "|" + spec + "|" + spec, I(0), I(-42), I(0x7FFFFFFF))


SPECIAL_D = [0.0, -0.0, 1.0, -1.0, 0.1, -0.1, 0.125, 0.5, 1.5, 2.5, 3.5, -0.5, -1.5, -2.5, 9.9999, 9.99999, 99.999,
             0.99999999, 0.95, 0.995, 9.5, 99.5, 999.5, 999999.5, 9999995.0, 0.05, 0.15, 0.25, 0.35, 0.45, 2.675, 1.005,
             1e-5, 1e-4, 0.0001234, 0.00001234, 123456.0, 1234567.0, 123456789.0, 1e15, 1e16, 1e17, 1e21, 1e22, 1e23,
             1e100, 1e300, 1e308, 1.7976931348623157e308, 2.2250738585072014e-308, 2.225073858507201e-308, 1e-310,
             1e-320, 5e-324, 123.456, 3.141592653589793, 2.0 / 3.0, 1.0 / 3.0, 0.3, 0.7, 0.1 + 0.2,
             9007199254740993.0, 2.0 ** 53, 2.0 ** 63, 2.0 ** 64, 123456789012345678.0, 1e-7, 5e-5, 0.000015,
             2251799813685247.25, 2251799813685247.75, 4503599627370495.5, 0.30000000000000004, 1.0000000000000002,
             0.9999999999999999, 4.35, 8.345, 1e-300, 1.5e-323, 100.0, 1000000.0, 1e6 - 0.5, 0.00009999, 0.0001,
             6.02214076e23, 1.602176634e-19, 299792458.0, 65536.0, 4294967296.0, 0.6931471805599453,
             7.000000000000001, 1e-6, 1e-5 * 0.99999, 12345.6789, -987654.321, 5.0, 25.0, 125.0, 0.015625]
SPECIAL_BITS = [0x7FF0000000000000, 0xFFF0000000000000,             # +-INF
                0x7FF8000000000000, 0xFFF8000000000000,             # quiet NaN, x86 'indefinite'
                0x7FF8000000000001, 0xFFF8000000000001, 0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF,
                0x7FF0000000000001, 0xFFF0000000000001, 0x7FF4000000000000, 0x7FF7FFFFFFFFFFFF,   # signalling NaN
                0x0000000000000001, 0x8000000000000001, 0x000FFFFFFFFFFFFF, 0x0008000000000000,   # denormals
                0x0010000000000000, 0x7FEFFFFFFFFFFFFF, 0x3FF0000000000001, 0x3FEFFFFFFFFFFFFF]
FLOAT_VALS = [D(x) for x in SPECIAL_D] + [DB(b) for b in SPECIAL_BITS]
FPRECS = ["", ".0", ".1", ".2", ".3", ".4", ".6", ".10", ".15", ".16", ".17", ".18", ".20", ".25", ".40", ".*", ".600"]


def gen_float(c, rng):
    for flags in ALL_FLAGS + ODD_FLAGS[:6]:
        for conv in "eEfgG":
            for p in FPRECS:
                for _ in range(2):
                    w, wa = width_choices(rng)
                    pa = []
                    pp = p
                    if p == ".*":
                        pa = [I(rng.choice([-1, 0, 3, 17, 30, 600]))]
                    size = rng.choice(["", "", "l", "L", "h", "I64"])
                    spec = "%" + flags + w + pp + size + conv
                    vals = rng.sample(FLOAT_VALS, 3)
                    args = []
                    for v in vals:
                        args += wa + pa + [v]
                    c.P("flt", "[" + "|".join([spec] * 3) + "]", *args)
    # every special value at every precision for each conversion, plain and '#'
    for conv in "efgEG":
        for p in FPRECS[:-2] + [".512"]:
            for flags in ["", "#"]:
                spec = "%" + flags + p + conv
                for k in range(0, len(FLOAT_VALS), 4):
                    vals = FLOAT_VALS[k:k + 4]
                    c.P("fltsweep", "|".join([spec] * len(vals)), *vals)
    # requested specific checks
    for spec, x in [("%.2f", 0.125), ("%.0f", 0.5), ("%.0f", 1.5), ("%.0f", 2.5), ("%.0f", 3.5), ("%.0f", -0.5),
                    ("%f", 1e21), ("%f", 1e308), ("%.20f", 0.1), ("%.20f", 1.0 / 3.0), ("%.20e", 0.1),
                    ("%.30g", 0.1), ("%.17g", 0.1), ("%.4f", 9.99995), ("%.3f", 9.9999), ("%.0e", 9.5),
                    ("%.0e", 0.5), ("%g", 100000.0), ("%g", 1000000.0), ("%g", 999999.5), ("%.3g", 99.95),
                    ("%.3g", 0.0001), ("%g", 0.0001), ("%g", 0.00001), ("%#g", 0.0001), ("%#.3g", 1.0),
                    ("%.512f", 1e308), ("%.512e", -1e-300), ("%.512g", 0.1), ("%600.3f", 2.5), ("%-600.3f", 2.5)]:
        c.P("fltfix", spec, D(x))


def rand_double(rng):
    k = rng.random()
    if k < 0.45:
        while True:
            b = rng.getrandbits(64)
            if (b >> 52) & 0x7FF != 0x7FF:
                return b
    if k < 0.6:   # denormals and tiny
        return rng.getrandbits(52) | (rng.getrandbits(1) << 63) | (rng.choice([0, 0, 1, 2]) << 52)
    if k < 0.8:   # short decimals
        digits = rng.randint(1, 17)
        m = rng.randrange(10 ** (digits - 1), 10 ** digits)
        e = rng.randint(-30, 30)
        return struct.unpack("<Q", struct.pack("<d", float("%de%d" % (m, e))))[0]
    # dyadic values with exactly representable decimal tails (exact ties at 17/18 digits)
    m = rng.getrandbits(53) | 1
    sh = rng.randint(0, 12)
    return struct.unpack("<Q", struct.pack("<d", m / float(1 << sh)))[0]


def gen_i10(c, rng, n):
    """17-digit decimal mantissas (what _fltout2/$I10_OUTPUT produce): %.16e prints all of them."""
    for _ in range(n):
        vals = [DB(rand_double(rng)) for _ in range(8)]
        c.P("i10", "|".join(["%.16e"] * 8), *vals)
    for _ in range(n // 4):
        spec = "%" + rng.choice(["", "#", "+", "0", "-"]) + rng.choice(["", "30"]) + "." + str(rng.randint(0, 25)) + rng.choice("efgEG")
        vals = [DB(rand_double(rng)) for _ in range(4)]
        c.P("fltrand", "|".join([spec] * 4), *vals)
    # exact ties at the 18th significant digit: m/2^sh (m odd) has the digits of m*5^sh, which end in 5;
    # choose m so that there are exactly 18 of them
    for _ in range(n // 3):
        vals = []
        for _ in range(8):
            sh = rng.randint(2, 25)        # sh = 1 would need m >= 2e16 > 2^53
            lo, hi = -(-10 ** 17 // 5 ** sh), min(10 ** 18 // 5 ** sh, 1 << 53)
            m = rng.randrange(lo, hi) | 1
            if m >= hi:
                m -= 2
            vals.append(D((-1) ** rng.getrandbits(1) * m / float(1 << sh)))
        c.P("ties", "|".join(["%.16e"] * 8), *vals)
    # near ties: exact expansions whose 18th significant digit is 4 or 5 with more digits after it
    from decimal import Decimal
    for _ in range(n // 3):
        vals = []
        while len(vals) < 8:
            m = rng.getrandbits(53) | 1
            sh = rng.randint(3, 70)
            x = m / float(1 << sh) * (10.0 ** rng.randint(-5, 5) if rng.random() < 0.3 else 1.0)
            digits = format(abs(Decimal(x)), "f").replace(".", "").lstrip("0")
            if len(digits) > 18 and digits[17] in "45":
                vals.append(D(x))
        c.P("nearties", "|".join(["%.16e"] * 8), *vals)


WSTRS = [None, "", "a", "abc", "Hello, World", "éüÿ", "ĀΩ中", "￿", [0xD800, 0x78],
         "a b", "tab\there", "x" * 40, "\u0080\u009f"]
ASTRS = [None, b"", b"a", b"abc", b"\x80\xe9\xff", b"caf\xe9", b"Hello, World", b"y" * 40]
CHARS = [0, 0x41, 0x7A, 0xE9, 0xFF, 0x100, 0x10041, 0xFFFF, 0x12345678, 0x20AC, 0x80]


def gen_str(c, rng):
    for flags in ALL_FLAGS:
        for conv, size in [("s", ""), ("S", ""), ("s", "h"), ("s", "l"), ("s", "w"), ("S", "h"), ("S", "l"),
                           ("S", "w"), ("s", "I64"), ("S", "L"), ("s", "hw"), ("s", "wh")]:
            for _ in range(3):
                w, wa = width_choices(rng)
                p, pa = prec_choices(rng, big=False)
                spec = "%" + flags + w + p + size + conv
                narrow = (conv == "S" and size not in ("l", "w")) or (conv == "s" and size == "h") or ("h" in size)
                if size in ("hw", "wh"):
                    narrow = True    # FL_SHORT is tested first
                pool = ASTRS if narrow else WSTRS
                vals = rng.sample(pool, 3)
                args = []
                for v in vals:
                    if v is None:
                        args += wa + pa + [NULL]
                    else:
                        args += wa + pa + [A(v) if narrow else W(v)]
                c.P("str", "[" + "|".join([spec] * 3) + "]", *args)
        for conv, size in [("c", ""), ("C", ""), ("c", "h"), ("c", "l"), ("c", "w"), ("C", "h"), ("C", "l"),
                           ("C", "w"), ("c", "I64")]:
            for _ in range(2):
                w, wa = width_choices(rng)
                p, pa = prec_choices(rng, big=False)
                spec = "%" + flags + w + p + size + conv
                vals = rng.sample(CHARS, 4)
                args = []
                for v in vals:
                    args += wa + pa + [I(v)]
                c.P("chr", "[" + "|".join([spec] * 4) + "]", *args)


def gen_str_narrow(c, rng):
    """narrow printf: %s is a narrow string unless l or w is given; %S is wide unless h is given (l/w are tested
    before h); %c takes an int and prints its low byte; %C, %lc, %wc print a wide character through the C-locale
    wctomb (nothing for a character above 0xFF); wide string text stops at the first such character"""
    for flags in ALL_FLAGS:
        for conv, size in [("s", ""), ("S", ""), ("s", "h"), ("s", "l"), ("s", "w"), ("S", "h"), ("S", "l"),
                           ("S", "w"), ("s", "I64"), ("S", "L"), ("s", "hw"), ("s", "wh")]:
            for _ in range(2):
                w, wa = width_choices(rng)
                p, pa = prec_choices(rng, big=False)
                spec = "%" + flags + w + p + size + conv
                wide = "l" in size or "w" in size or (conv == "S" and "h" not in size)
                vals = rng.sample(WSTRS if wide else ASTRS, 3)
                args = []
                for v in vals:
                    args += wa + pa + [NULL if v is None else (W(v) if wide else A(v))]
                c.A("nstr", "[" + "|".join([spec] * 3) + "]", *args)
        for conv, size in [("c", ""), ("C", ""), ("c", "h"), ("c", "l"), ("c", "w"), ("C", "h"), ("C", "l"),
                           ("C", "w"), ("c", "I64")]:
            w, wa = width_choices(rng)
            p, pa = prec_choices(rng, big=False)
            spec = "%" + flags + w + p + size + conv
            vals = rng.sample(CHARS, 4)
            args = []
            for v in vals:
                args += wa + pa + [I(v)]
            c.A("nchr", "[" + "|".join([spec] * 4) + "]", *args)


def gen_narrow_text(c, rng):
    """narrow-only behaviour: high-bit format bytes, wide text through wctomb, and mixes of the common
    conversions (GlmLib's sprintf use is plain %s/%d/%f/%x formatting)"""
    fixed = [(b"plain", []), (b"\x80\x81\xe9\xff high", []), (b"%s|%S", [A(b"n\xe9"), W("wé")]),
             (b"%S|", [W("abĀcd")]), (b"%-8S|", [W("abĀcd")]), (b"%8S|", [W("Ā")]),
             (b"%.2S|", [W("éĀx")]), (b"%ls|%ws|%hs|%hS|", [W("wide"), W("w2"), A(b"nar"), A(b"n2")]),
             (b"%C|%-3C|%lc|%wc|%hC|", [I(0x100), I(0x41), I(0xE9), I(0x20AC), I(0x141)]),
             (b"%c%c%c", [I(0x141), I(0x80), I(0)]), (b"%S%n|", [W("aĀb"), "n0"]),
             (b"%s %d %f %g %e %x %X %o %p %c %%",
              [A(b"GlmLib"), I(-5), D(3.14159), D(1e-5), D(1e21), I(255), I(255), I(8), I(0x1234), I(0x41)]),
             (b"%.3f %8.2f %-8.2f| %+.1e %#x %#o %05d %-5d| %.0f %.10g",
              [D(2.0 / 3), D(-1234.5678), D(0.005), D(-6.02e23), I(0xBEEF), I(8), I(-42), I(7), D(2.5), D(1.0 / 3)]),
             (b"%I64d %I64u %I64x %I64X", [Q(-1), Q(2 ** 63), Q(0x123456789ABCDEF), Q(-2)]),
             (b"(%f, %f, %f)", [D(1.5), D(-0.0), D(1e-300)]), (b"%s=%d", [A(b"Key"), I(1)]), (b"%s", [NULL])]
    # a '*' precision of -1 followed by digits leaves a negative precision other than -1 (-1*10+d)
    for spec in ["%.*5s|", "%.*0s|", "%.*12s|", "%.*3hs|", "%-8.*5s|", "%.*5S|", "%.*0S|", "%.*5ls|", "%.*5ws|",
                 "%8.*5S|"]:
        wide = "S" in spec or "l" in spec or "w" in spec
        for v in (["narrow", "", "éxÿ"] if not wide else ["wide", "", "éx", "aĀb"]):
            fixed.append((spec.encode(), [I(-1), W(v) if wide else A(v.encode("latin-1"))]))
        fixed.append((spec.encode(), [I(-1), NULL]))
    for f, a in fixed:
        c.A("ntext", f, *a)
    specs = ["%d", "%i", "%u", "%x", "%X", "%08X", "%5d", "%-5d|", "%f", "%.2f", "%8.3f", "%g", "%e", "%s", "%10s",
             "%-10s|", "%c", "%%", "%p", "%.0f", "%+d", "%03d", "%lf", "%ld", "%lu"]
    for _ in range(600):
        parts, args = [], []
        for _ in range(rng.randint(1, 6)):
            s = rng.choice(specs)
            parts.append(rng.choice(["", " ", ", ", "=", "x", "\xe9"]) + s)
            conv = s[-1] if s[-1] != "|" else s[-2]
            if s == "%%":
                continue
            if conv in "feg":
                args.append(rng.choice(FLOAT_VALS))
            elif conv == "s":
                args.append(rng.choice([A(b"name"), A(b""), A(b"caf\xe9"), NULL, A(b"x" * 60)]))
            else:
                args.append(I(rng.choice(INT32)))
        c.A("nmix", "".join(parts), *args)


def gen_ptr(c, rng):
    for flags in ALL_FLAGS:
        for size in ["", "h", "l", "I64", "I32", "w"]:
            w, wa = width_choices(rng)
            p, pa = prec_choices(rng)
            spec = "%" + flags + w + p + size + "p"
            vals = [0, 1, 0xDEADBEEF, 0x12AB, 0xFFFFFFFF] if size != "I64" else [0, 1, 0x123456789ABCDEF0, -1]
            args = []
            for v in vals:
                args += wa + pa + [Q(v) if size == "I64" else I(v)]
            c.P("ptr", "|".join([spec] * len(vals)), *args)


def gen_n(c, rng):
    cases = [("%n", [0]), ("abc%n", [0]), ("abc%hn|%n", [0, 1]), ("%5d%ln", [None, 0]), ("%s%n%s%n", [None, 0, None, 1]),
             ("%-10s%n.", [None, 0]), ("%10n|", [0]), ("%-5n|", [0]), ("%.3n|", [0]), ("%I64n", [0]),
             ("%hhn", [0]), ("x%wn", [0]), ("%%%n", [0]), ("Āā%n", [0]), ("%c%n", [None, 0]),
             ("%*n", [None, 0]), ("%n%n%n", [0, 1, 2])]
    for fmt, slots in cases:
        args = []
        for s in slots:
            if s is None:
                if "%s" in fmt or "%-10s" in fmt:
                    args.append(W("hello"))
                else:
                    args.append(I(77))
            else:
                args.append("n%d" % s)
        c.P("n", fmt, *args)
    # %n after the output exceeds the buffer: covered by the L-1 truncation run of every case; long prefixes too
    for k in [1, 5, 31, 64, 200]:
        c.P("n", "x" * k + "%n" + "y" * k + "%n", "n0", "n1")
        c.P("n", "%*d%n", I(k), I(7), "n0")


def gen_odd(c, rng):
    fixed = ["%y", "%5y", "%I", "%Iq", "%I6", "%I3", "%I64", "%I32", "%I6d", "%I3d", "%I64q", "%I32q", "%", "abc%",
             "%%", "%5%", "%-5%", "%.3%", "%l%", "%-+ #010.3d", "%-", "%5", "%.", "%l", "%h", "%w", "%L", "%N",
             "%F", "%5*d", "%**d", "%.5*d", "%.**d", "%*5d", "%.*5d", "%-*d", "%0*d", "%l5d", "%h.3d", "%.3-d",
             "%#5.3+d", "%5.d", "%.-3d", "%+-+-d", "%0.0d", "%00005d", "%-0005d", "%é", "%Ť", "%ų",
             "%Ťd", "%5Ť", "%A", "%a", "%D", "%O", "%U", "%H", "%J", "%z", "%{", "%~", "%\t", "%\n",
             "% ", "%#", "%-+", "%Bd", "%5B|", "x%B", "%d%B", "%T", "%v", "%r", "%q", "%b", "%m", "%k", "%j",
             "%t", "%llx", "%hhx", "%Ix", "%Iu", "%Io", "%IX", "%Ii", "%Id", "%Ic", "%Is", "%Ie", "%Ip", "%In",
             "%lld", "%I64I64d", "%hld", "%lhd", "%Lf", "%lf", "%hf", "%Lg", "%I64e", "%NFd", "%Fs", "%Ns",
             "%.*.*d", "%*.*d", "%-*.*d", "%5.5.5d", "%..5d", "%*%", "%.*%", "%.%", "%h%", "%I%", "%I6%",
             "100%", "%%d", "%%%%", "%%%", "50%%", "%-%d", "%5%d", "%0%", "%I64%", "%c%", "a%%b%%c",
             "Ā%d中%s￿", "%d\u0000tail", "%I6", "%I64", "%I3", "%I32", "%I"]
    for f in fixed:
        if "\u0000" in f:
            f = f.split("\u0000")[0]
        if f in ("%Fs", "%Ns"):              # size prefixes that still end in a %s conversion
            a1, a2 = [W("str"), W("x")], [W("s2"), W("y")]
        elif "%s" in f:
            a1, a2 = [I(42), W("str")], [I(-1), W("s2")]
        else:
            a1, a2 = [I(42), I(-3), I(5), I(9), I(11)], [I(0x7FFFFFFF), I(3), I(7), I(1), I(2)]
        c.P("odd", f, *a1)
        c.P("odd", "<" + f + ">", *a2)
    # 'B' (type class, no conversion) after each kind of conversion, and negative string precisions
    for f, a in [("%d%B", [I(42)]), ("%s%B", [W("str")]), ("%S%B", [A(b"nar")]), ("%c%B", [I(0x141)]),
                 ("%hc%B", [I(0x41)]), ("%f%B", [D(2.5)]), ("%-8.3e|%B|", [D(-1.5)]), ("%5d%-5B|", [I(-7)]),
                 ("%p%B", [I(0xABC)]), ("%d%n%B", [I(5), "n0"]), ("%Z%B", [CS(3, 4, b"abc")]),
                 ("%wZ%B", [CS(4, 4, "ab".encode("utf-16-le"))]), ("%x%c%B", [I(0x1234), I(0x4142)]),
                 ("%f%c%B", [D(123.5), I(0x39)]), ("%#o%+08B|", [I(8)]), ("%s%B%B", [W("Āx")]),
                 ("%.*5s|%.*5S|", [I(-1), W("wide"), I(-1), A(b"narrow")]),
                 ("%.*0s|%.*0S|", [I(-1), W("wide"), I(-1), A(b"narrow")]), ("%.*s|", [I(-1), W("all")]),
                 ("%.*s|%.*S|", [I(-2), W("neg"), I(-2), A(b"neg")])]:
        c.P("oddB", f, *a)
    # random specs from the full alphabet, all-zero arguments (safe for every conversion except %n / %Z)
    alpha = list("-+ #0123456789*.hlwILNF") + list("diuoxXcCsSeEfgGp%") + list("yzBqAaDHJéĀ") + ["I64", "I32"]
    for _ in range(4000):
        parts = []
        for _ in range(rng.randint(1, 3)):
            parts.append(rng.choice(["", "x", "ā", " ", "ab"]))
            parts.append("%" + "".join(rng.choice(alpha) for _ in range(rng.randint(0, 7))))
        parts.append(rng.choice(["", "!", "中"]))
        c.P("fuzz", "".join(parts))


def gen_counted(c, rng):
    for spec in ["%Z", "%wZ", "%hZ", "%lZ", "%10Z", "%-10Z|", "%.2Z", "%.2wZ", "%010Z", "%+Z", "%.0Z", "%IZ", "%I64Z"]:
        for arg in [NULL, CS(3, 4, b"abc"), CS(0, 0, b""), CS(6, 8, b"a\x00b\xe9cd"), CS(4, 4, "Āz".encode("utf-16-le")),
                    CS(5, 5, None), CS(2, 2, b"xyz"), CS(8, 8, "wide".encode("utf-16-le"))]:
            c.P("cstr", spec, arg)


def gen_trunc(c, rng):
    c.P("trunc", "")
    c.P("trunc", "a")
    c.P("trunc", "abc")
    c.P("trunc", "Āā中")
    c.P("trunc", "%s", W("x" * 300))
    c.P("trunc", "%300d|", I(5))
    c.P("trunc", "%-300d|", I(5))
    c.P("trunc", "%.300d|", I(5))
    c.P("trunc", "%S|%s", A(b"narrow\xe9"), W("Āwide"))
    for k in range(1, 40):
        c.P("trunc", "%d" * k, *[I(i * 37) for i in range(k)])
    # explicit counts, including ones whose byte count (count*2) overflows a 32-bit int
    big_counts = [0x3FFFFFFF, 0x40000000, 0x7FFFFFFF, 0x80000000, 0x80000001, 0x80000004, 0x80000010, 0xFFFFFFFF,
                  0xC0000000, 0xC0000003]
    for fmt, args in [("", []), ("a", []), ("abc", []), ("%d|%s", [I(12345), W("str")])]:
        c.C("count", [0, 1, 2, 3, 4, 5, 8, 16] + big_counts, fmt, *args)


def gen_wprintf(c, rng):
    fixed = [("plain\n", []), ("crlf\r\n", []), ("two\n\nlines\n", []), ("%d|%s|%c\n", [I(42), W("wé"), I(0x41)]),
             ("éÿ\n", []), ("aĀb\n", []), ("Ā\n", []), ("x%sy\n", [W("Ā")]),
             ("x%-5sy\n", [W("Ā")]), ("x%5sy\n", [W("Ā")]), ("x%-5cy\n", [I(0x100)]), ("x%5cy\n", [I(0x100)]),
             ("x%-5sy%n\n", [W("Ā"), "n0"]), ("%s%n\n", [W("abĀcd"), "n0"]), ("%-8s|%n\n", [W("abĀ"), "n0"]),
             ("%S\n", [A(b"caf\xe9")]), ("%c%c%c\n", [I(0x41), I(0x101), I(0x42)]), ("%-3c|%-3c|\n", [I(0x101), I(0x41)]),
             ("中%d\n", [I(5)]), ("%d中%d\n", [I(5), I(6)]), ("%s\n", [W("x" * 5000)]), ("", []),
             ("%%\n", []), ("\x1a\n", []), ("\r", []), ("\n", []), ("%5.1f|%e|%g\n", [D(2.25), D(-1e-5), D(1e21)]),
             ("%s|%s\n", [W("aĀ"), W("b")]), ("%-6S|\n", [A(b"\xff")]), ("%-4ls|\n", [W("￿")]),
             ("%-3hc|\n", [I(0x1E9)]), ("%-3lc|%d\n", [I(0x1E9), I(7)])]
    for f, a in fixed:
        c.W("wprintf", f, *a)
    for _ in range(150):
        spec = "%" + rng.choice(ALL_FLAGS) + rng.choice(["", "5", "12"]) + rng.choice(["", ".2", ".0"]) + rng.choice("diuxXoceEfgGsS")
        conv = spec[-1]
        if conv in "eEfgG":
            arg = rng.choice(FLOAT_VALS)
        elif conv == "s":
            arg = W(rng.choice(["abc", "éè", "Āx", ""]))
        elif conv == "S":
            arg = A(rng.choice([b"abc", b"\xe9", b""]))
        elif conv == "c":
            arg = I(rng.choice([0x41, 0xE9, 0x100, 0]))
        else:
            arg = I(rng.choice(INT32))
        c.W("wprintf", "<" + spec + ">\n", arg)


STRS = ["", "a", "A", "abc", "ABC", "abd", "ab", "abcd", "Hello", "hello", "HELLO", "hellO", "@[`{", "_", "^", "Z", "z",
        "é", "É", "Ā", "ā", "￿", "aĀ", "Aā", "中文", "mixed Case 123",
        "AbCdEfGhIjKlMnOpQrStUvWxYz", "ÀÞßàþÿ", "x" * 50, "tab\tsep", [0xD800, 0x41]]


def gen_strings(c, rng):
    for s in STRS:
        c.S("wcslen", "wcslen", W(s))
        c.S("wcscpy", "wcscpy", "b%d,%s" % (len(units(s)) + 3, hx("zzzzzzzz")), W(s))
        c.S("wcsupr", "_wcsupr", W(s))
        for t in rng.sample(STRS, 6):
            c.S("wcscat", "wcscat", "b%d,%s" % (len(units(s)) + len(units(t)) + 2, hx(s)), W(t))
            for n in [0, 1, 2, 3, len(units(t)), len(units(t)) + 1, len(units(t)) + 4]:
                c.S("wcsncpy", "wcsncpy", "b%d,%s" % (max(n, 1) + 2, hx("yyyyyyyy")), W(t), I(n))
    all_ascii = "".join(chr(i) for i in range(1, 128))
    latin1 = "".join(chr(i) for i in range(128, 256))
    c.S("wcsupr", "_wcsupr", W(all_ascii))
    c.S("wcsupr", "_wcsupr", W(latin1))
    c.S("wcsupr", "_wcsupr", W("".join(chr(i) for i in range(0x100, 0x200))))
    for a in STRS:
        for b in STRS:
            c.S("wcscmp", "wcscmp", W(a), W(b))
            c.S("wcsicmp", "_wcsicmp", W(a), W(b))
            n = rng.choice([0, 1, 2, 3, 5, 100, 0xFFFFFFFF])
            c.S("wcsncmp", "wcsncmp", W(a), W(b), I(n))
            c.S("wcsnicmp", "_wcsnicmp", W(a), W(b), I(n))
    for ch in [0x41, 0x61, 0x5B, 0x40, 0x60, 0x7B]:
        for d in [0x41, 0x61, 0x5B, 0x40, 0x60, 0x7B, 0xE9, 0xC9, 0x100]:
            c.S("wcsicmp", "_wcsicmp", W([ch]), W([d]))
            c.S("wcsnicmp", "_wcsnicmp", W([ch, 0x31]), W([d, 0x32]), I(2))
    hay = ["", "a", "abcabc", "hello world", "ĀāĀ", "aaaa", "abcdabce", "x中y"]
    for h in hay:
        for ch in [0, 0x61, 0x62, 0x63, 0x6F, 0x100, 0x10061, 0xFFFF0062, 0x4E2D, 0x7A]:
            c.S("wcschr", "wcschr", W(h), I(ch))
            c.S("wcsrchr", "wcsrchr", W(h), I(ch))
        for needle in ["", "a", "bc", "abc", "abce", "world", "āĀ", "aa", "aaaaa", "zz", "x中y", "c"]:
            c.S("wcsstr", "wcsstr", W(h), W(needle))
    nums = ["", "0", "1", "123", "-123", "+5", "  42", "\t\n\v\f\r 7", "2147483647", "2147483648", "-2147483648",
            "-2147483649", "4294967296", "4294967297", "99999999999", "12abc", "abc", "0x1A", "1e5", "--5", "+-5", "- 5",
            "-", "+", " ", "007", "-0", "１２", "1２", "²", "٣", " 5", " 5", "　5",
            "5é", "é5", "123" + " " * 20, " " * 18 + "5", " " * 19 + "5", " " * 20 + "5", "1234567890123456789X",
            "1234567890123456789", "123456789012345678", "1234567890123456789 tail text", "42 and a long trailing text",
            "-17 trailing 中文 text here", "中12", "12中34", "9" * 19, "1" + "0" * 9, "3000000000",
            "-3000000000", "+2147483647", "­5", "‒7"]
    for s in nums:
        c.S("wtoi", "_wtoi", W(s))
    # every UTF-16 code unit as a leading character (iswspace / sign / digit) and as a second digit
    for u in range(1, 0x10000):
        c.S("wtoiall", "_wtoi", W([u, 0x35]))
        c.S("wtoiall", "_wtoi", W([0x31, u]))
    for size, d, s, n in [(32, 0, 8, 16), (32, 8, 0, 16), (32, 4, 4, 8), (32, 0, 1, 31), (32, 1, 0, 31), (32, 5, 9, 0),
                          (64, 3, 17, 40), (64, 17, 3, 40), (300, 0, 7, 290), (300, 7, 0, 290), (16, 2, 3, 1)]:
        c.M("memmove", size, d, s, n)
    c.R("rand", None, 40)     # initial state: seed 1
    for seed in [0, 1, 2, 12345, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0xDEADBEEF]:
        c.R("rand", seed, 60)
    c.R("rand", None, 2000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--i10", type=int, default=6000, help="cases of 8 random doubles at %%.16e")
    ap.add_argument("--narrow-i10", type=int, default=2000, help="the same for narrow sprintf")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    c = Corpus()
    gen_int(c, rng)
    gen_float(c, rng)
    gen_i10(c, rng, a.i10)
    gen_str(c, rng)
    gen_ptr(c, rng)
    gen_n(c, rng)
    gen_odd(c, rng)
    gen_counted(c, rng)
    gen_trunc(c, rng)
    gen_wprintf(c, rng)
    gen_strings(c, rng)
    # narrow sprintf, from its own random stream so that the wide corpus above stays unchanged
    nr = random.Random(a.seed + 1)
    n = Narrow(c)
    gen_int(n, nr)
    gen_float(n, nr)
    gen_i10(n, nr, a.narrow_i10)
    gen_ptr(n, nr)
    gen_n(n, nr)
    gen_odd(n, nr)
    gen_counted(n, nr)
    gen_trunc(n, nr)
    gen_str_narrow(c, nr)
    gen_narrow_text(c, nr)
    with open(a.out, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(c.lines) + "\n")
    total = sum(c.counts.values())
    print("corpus: %d cases -> %s" % (total, a.out))
    for k in sorted(c.counts):
        print("  %-10s %6d" % (k, c.counts[k]))


if __name__ == "__main__":
    main()
