"""Generate the corpus of the msvcr70 differential test (see README.md).

Line kinds (read by crt_diff_core.h):
  P <id> <fmt> <arg>*        _vsnwprintf: unbounded, then counts 0, L-1, L, L+1 (L = full length)
  C <id> <counts> <fmt> <arg>*   _vsnwprintf with explicit counts (comma separated, decimal)
  W <id> <fmt> <arg>*        wprintf to stdout
  A <id> <fmt bytes> <arg>*  narrow sprintf (output length probed first; SKIP when 65536 characters or more)
  B <id> <func> <fmt> <arg>*  bounded printf (_snprintf/_vsnprintf: fmt bytes; _vsnwprintf: UTF-16) at
                             capacities 0, 1, 2, L-1, L, L+1, L+2, L+16, whole destination + guards recorded
  K <id> <func> <alloc> <counts> <fmt> <arg>*   bounded printf with explicit counts, fixed allocation
  E <id> <func> <null|alloc> <count> <fmt|null> <arg>*   error behaviour (separate file, one process each)
  S <id> <func> <arg>*       string function (w<hex> string, b<cap>,<hex> buffer, u<hex8> integer, 0 null)
  M <id> <size> <dst> <src> <n>   memmove inside one byte buffer
  R <id> <seed hex8|-> <n>   srand(seed) (unless '-') then n x rand()
CRT functions the original `ucc make` reaches (GlmLib.dll, Editor.dll, Core.dll), see crt_diff_core.h:
  V <id> <fmt bytes> <arg>*  vsprintf (as A)
  T <id> <func> <arg>*       strrchr, strchr, strncpy, _stricmp, atoi, toupper (s<off>,<hex> string at an
                             offset, b<off>,<cap> destination, u<hex8> integer)
  Q <id> <cmp> <width> <num> <hex>   qsort with a harness comparator; order and comparator call sequence
  Z <id> <op>*               malloc / realloc / _msize / free sequence
  X <id> <hex8>*             _set_se_translator sequence (separate file, one process each)
  F <id> <op>*               file-system sequence in the scratch tree FS_* below (separate file, one process each)
<fmt> and wide strings are hex UTF-16 code units ('~' = empty). printf arguments: i<hex8> int32,
q<hex16> int64, d<hex16> double bits, w<hex> wide string, a<hex> narrow string, n<k> pointer to %n slot k,
c<len>,<max>,<hex|~|!> counted string (! = NULL buffer), 0 NULL. Unused argument words are 0.
"""
import argparse
import datetime
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
        self.err_lines = []     # E lines: written to a separate file, one process per case
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

    @staticmethod
    def _bfmt(func, fmt):
        """format of a bounded function: UTF-16 units for _vsnwprintf, bytes otherwise; None = NULL format;
        returns None when a narrow format would need code points > 0xFF"""
        if fmt is None:
            return "null"
        if func == "_vsnwprintf":
            return hx(fmt)
        if isinstance(fmt, str):
            if any(ord(ch) > 0xFF for ch in fmt):
                return None
            fmt = fmt.encode("latin-1")
        return fmt.hex().upper() or "~"

    def B(self, cat, func, fmt, *args):
        f = self._bfmt(func, fmt)
        if f is not None:
            self.lines.append(" ".join(["B", self._id(cat), func, f] + list(args)))

    def K(self, cat, func, alloc, counts, fmt, *args):
        f = self._bfmt(func, fmt)
        if f is not None:
            self.lines.append(" ".join(["K", self._id(cat), func, str(alloc), ",".join("0x%X" % k for k in counts), f]
                                       + list(args)))

    def E(self, cat, func, dest, count, fmt, *args):
        f = self._bfmt(func, fmt)
        if f is not None:
            self.err_lines.append(" ".join(["E", self._id(cat), func, dest, "0x%X" % count, f] + list(args)))

    def V(self, cat, fmt, *args):
        """vsprintf; fmt as for A"""
        if isinstance(fmt, str):
            if any(ord(ch) > 0xFF for ch in fmt):
                return
            fmt = fmt.encode("latin-1")
        self.lines.append(" ".join(["V", self._id(cat), fmt.hex().upper() or "~"] + list(args)))

    def T(self, cat, func, *args):
        self.lines.append(" ".join(["T", self._id(cat), func] + list(args)))

    def Q(self, cat, cmp, width, num, data):
        assert len(data) == width * num
        self.lines.append("Q %s %s %d %d %s" % (self._id(cat), cmp, width, num, data.hex().upper() or "~"))

    def Z(self, cat, *ops):
        self.lines.append(" ".join(["Z", self._id(cat)] + list(ops)))

    def X(self, cat, *values):
        self.err_lines.append(" ".join(["X", self._id(cat)] + ["%08X" % (v & 0xFFFFFFFF) for v in values]))

    def F(self, cat, *ops):
        self.err_lines.append(" ".join(["F", self._id(cat)] + list(ops)))


def widen_narrow_args(args):
    """The wide printf generators type a %S argument as a narrow string (wide printf's %S reads one). In narrow
    printf %S reads a WIDE string, which would scan a narrow string's bytes past its allocation, so the narrow
    routes give every such argument (the only use of 'a' in those generators) a wide string of the same
    characters."""
    return ["w" + hx(bytes.fromhex(t[1:]).decode("latin-1")) if t.startswith("a") and t != "a~" else
            "w~" if t == "a~" else t for t in args]


class Narrow:
    """Routes the printf generators' cases to narrow sprintf ('A' lines, categories prefixed with 'n'). Numeric
    arguments mean the same in the narrow and the wide printf; string and character conversions do not (narrow
    %s is a narrow string), so those generators' string arguments only exercise identical bytes on both sides,
    and gen_str_narrow types them for the narrow _output. Narrow-string arguments are widened
    (widen_narrow_args)."""

    def __init__(self, c):
        self.c = c

    def P(self, cat, fmt, *args):
        self.c.A("n" + cat, fmt, *widen_narrow_args(args))

    def C(self, cat, counts, fmt, *args):
        self.c.A("n" + cat, fmt, *widen_narrow_args(args))

    def W(self, *a):
        pass


class Vsprintf:
    """Routes narrow printf cases to vsprintf ('V' lines, categories prefixed with 'v'): GlmLib's formatting helper
    (GlmLib+3e80) passes its va_list to vsprintf, the same narrow _output as sprintf"""

    def __init__(self, c):
        self.c = c

    def P(self, cat, fmt, *args):
        self.c.V("v" + cat, fmt, *widen_narrow_args(args))

    def C(self, cat, counts, fmt, *args):
        self.c.V("v" + cat, fmt, *widen_narrow_args(args))

    def A(self, cat, fmt, *args):            # narrow-typed generators (gen_str_narrow, gen_narrow_text)
        self.c.V("v" + cat, fmt, *args)

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


BOUNDED = ["_snprintf", "_vsnprintf", "_vsnwprintf"]


def gen_bounded(c, rng):
    """bounded printf, imported by Engine.dll and GlmLib.dll (_snprintf, _vsnprintf) and Core.dll (_vsnwprintf).
    Every B case runs at capacities 0, 1, 2, L-1, L, L+1, L+2 and L+16 (see crt_diff_core.h). String arguments
    are typed for the function's width: in the narrow functions %s is narrow and %S/%ls/%ws wide, in
    _vsnwprintf %s is wide and %S/%hs narrow; %C / %lc / %hc likewise."""
    for func in BOUNDED:
        wide = func == "_vsnwprintf"
        nat = (lambda v: W(v) if v is not None else NULL) if wide else (lambda v: A(v.encode("latin-1")) if v is not None else NULL)
        oth = (lambda v: A(v.encode("latin-1")) if v is not None else NULL) if wide else (lambda v: W(v) if v is not None else NULL)
        cat = {"_snprintf": "bsn", "_vsnprintf": "bvsn", "_vsnwprintf": "bvsnw"}[func]
        # output lengths around powers of two, and high characters in literal text
        c.B(cat + "lit", func, "")
        for k in [1, 2, 3, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 255, 256, 257, 511, 512, 1023, 1024,
                  1025, 4095, 4096, 4097]:
            c.B(cat + "lit", func, "x" * k)
        c.B(cat + "lit", func, "\x80\xe9\xff high" if not wide else "Ā中é high")
        # integers
        ivals = [0, 1, -1, 42, 255, 0x12345678, 0x7FFFFFFF, -0x80000000]
        for spec in ["%d", "%i", "%u", "%x", "%X", "%o", "%5d", "%-5d|", "%05d", "%+d", "% d", "%.3d", "%8.3d", "%#x",
                     "%#o", "%hd", "%ld", "%c", "%10d|%-10x|"]:
            for v in ivals:
                args = [I(v)] * spec.count("%")
                c.B(cat + "int", func, spec, *args)
        for spec in ["%*d", "%-*d|", "%.*d", "%*.*d"]:
            for w in [0, 3, 12, -12, 40]:
                for v in [7, -123456]:
                    args = [I(w)] * (spec.count("*")) + [I(v)]
                    c.B(cat + "int", func, spec, *args)
        for spec in ["%I64d", "%I64u", "%I64x", "%20I64d|"]:
            for v in [0, -1, 0x7FFFFFFFFFFFFFFF, -0x8000000000000000, 0x123456789ABCDEF]:
                c.B(cat + "int", func, spec, Q(v))
        # strings of the function's own width, and the other width
        svals = [None, "", "a", "abc", "hello world", "x" * 40, "y" * 300, "éÿ"]
        for spec in ["%s", "%10s", "%-10s|", "%.3s", "%.0s", "%10.3s", "%-8.40s|"]:
            for v in svals:
                c.B(cat + "str", func, spec, nat(v))
        for spec in ["%*s", "%-*s|", "%.*s"]:
            for w in [0, 5, -5, 50]:
                c.B(cat + "str", func, spec, I(w), nat("abcdef"))
        ovals = ([None, "", "abc", "x" * 40, "éÿ", "aĀb", "€"] if not wide
                 else [None, "", "abc", "x" * 40, "éÿ"])
        for spec in (["%S", "%ls", "%ws", "%-6S|", "%.2S", "%8S|"] if not wide else ["%S", "%hs", "%-6S|", "%.2S", "%8hs|"]):
            for v in ovals:
                c.B(cat + "xstr", func, spec, oth(v))
        for spec in (["%c", "%C", "%lc", "%-3C|", "%3c|"] if not wide else ["%c", "%C", "%hc", "%-3C|", "%3c|"]):
            for v in [0x41, 0xE9, 0x100, 0x20AC, 0]:
                c.B(cat + "chr", func, spec, I(v))
        # floating point
        fvals = [D(x) for x in [0.0, -0.0, 1.0, -1.5, 0.1, 0.125, 2.5, 9.9999, 123456.789, 1e21, 1e-5, 1e300,
                                5e-324]] + [DB(b) for b in [0x7FF0000000000000, 0xFFF0000000000000, 0x7FF8000000000000,
                                                            0xFFF8000000000000]]
        for spec in ["%f", "%.0f", "%.1f", "%.2f", "%10.3f", "%-10.3f|", "%+f", "%e", "%E", "%.10e", "%g", "%G", "%#g",
                     "%.17g", "%#.0f", "%010.2f"]:
            for v in fvals:
                c.B(cat + "flt", func, spec, v)
        for v in [D(1e300), D(-2.5), D(123.0)]:
            c.B(cat + "flt", func, "%.600f", v)
        # %n before and after the point where the output stops fitting
        for fmt, args in [("abc%n", ["n0"]), ("%s%n|%d%n", [nat("hello"), "n0", I(12345), "n1"]), ("%n", ["n0"]),
                          ("%10d%hn|", [I(5), "n0"]), ("x%ny%nz%n", ["n0", "n1", "n2"]),
                          ("0123456789%n0123456789%n", ["n0", "n1"])]:
            c.B(cat + "n", func, fmt, *args)
        # odd specifications and %p
        for fmt in ["%%", "100%%", "%5%", "%y", "abc%", "%-%d", "%I", "%Iq", "%.*%"]:
            c.B(cat + "odd", func, fmt, I(42), I(7))
        for spec in ["%p", "%10p", "%-10p|", "%#p"]:
            for v in [0, 0xDEADBEEF, 0x12AB]:
                c.B(cat + "ptr", func, spec, I(v))
        # Engine/GlmLib-style formats and random mixes
        for fmt, args in [("%s(%d): %s", [nat("File.cpp"), I(123), nat("message")]), ("%s.%s", [nat("Pkg"), nat("Obj")]),
                          ("%08X", [I(0xDEAD)]), ("%.2f%%", [D(99.5)]), ("%I64u bytes", [Q(123456789012)]),
                          ("[%3d] %-12s %6.2f", [I(7), nat("name"), D(3.14159)])]:
            c.B(cat + "mix", func, fmt, *args)
        specs = ["%d", "%u", "%x", "%5d", "%-5d|", "%f", "%.2f", "%g", "%e", "%s", "%10s", "%-10s|", "%c", "%%", "%p"]
        for _ in range(200):
            parts, args = [], []
            for _ in range(rng.randint(1, 6)):
                s = rng.choice(specs)
                parts.append(rng.choice(["", " ", ", ", "=", "x"]) + s)
                conv = s.rstrip("|")[-1]
                if s == "%%":
                    continue
                if conv in "feg":
                    args.append(rng.choice(fvals))
                elif conv == "s":
                    args.append(nat(rng.choice(["name", "", "café", None, "z" * 60])))
                else:
                    args.append(I(rng.choice(INT32)))
            c.B(cat + "mix", func, "".join(parts), *args)
        # explicit counts with a 64-character allocation (outputs at most 16 characters): huge, sign-flipping
        # and (for _vsnwprintf, whose byte count is count*2) wrapping counts
        counts = [0, 1, 2, 3, 0x3FFFFFFF, 0x40000000, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xC0000000, 0xC0000003,
                  0xFFFFFFFE, 0xFFFFFFFF]
        for fmt, args in [("", []), ("a", []), ("abc", []), ("%d|%s", [I(12345), nat("str")]), ("abcdefghij%n", ["n0"])]:
            c.K(cat + "cnt", func, 64, counts, fmt, *args)
        # intentional error behaviour, one process per case: NULL destination, NULL format
        ecat = cat + "err"
        for count, fmt, args in [(0, "", []), (0, "abc", []), (0, "%d", [I(12345)]), (1, "abc", []), (16, "abc", []),
                                 (0x7FFFFFFF, "abc", []), (0xFFFFFFFF, "abc", [])]:
            c.E(ecat, func, "null", count, fmt, *args)
        for count in (16, 0):
            c.E(ecat, func, "16", count, None)


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


# ---------------------------------------------------------------- CRT dependencies of `ucc make`
# The msvcr70 functions the original `ucc make -ini=XrtCompileProbe.ini` reaches (main session's import trace):
# without a runtime adapter yet, GlmLib.dll's vsprintf, strrchr, strncpy, fopen, fclose, _getcwd, _fullpath,
# _findfirst, _findnext, _findclose, _errno, _chdir and Editor.dll's _set_se_translator; newly reached with an
# adapter, qsort (Core.dll), toupper, atoi, _stricmp (GlmLib.dll) and _msize; strchr is GlmLib's partner of strrchr.

def S8(b, off=0):
    """narrow string argument at byte offset off of its region"""
    return "s%d,%s" % (off, b.hex().upper() or "~")


def B8(cap, off=0):
    """destination of cap bytes at byte offset off of its region"""
    return "b%d,%d" % (off, cap)


def U(v):
    return "u%08X" % (v & 0xFFFFFFFF)


PATHS = [b"", b"a", b"\\", b".", b"Core.u", b"..\\System\\Core.u", b"C:\\UT2\\System\\Editor.int", b"a.b.c", b"noext",
         b"dir.d\\file", b"\\\\srv\\share\\x.y", b"trailing\\", b"caf\xe9\\na\xefve.txt", b"\x81\\x\x81\\.",
         b"x" * 300 + b"\\y.z", b"/fwd/slash.u", b"..", b"\\\\", b"a\\b\\c\\d\\e.f.g"]


def gen_tstr(c, rng):
    """strrchr / strchr (GlmLib looks for '.' and '\\' in paths), strncpy, _stricmp, atoi, toupper"""
    chars = [0x5C, 0x2E, 0x2F, 0, 0x15C, 0xFFFFFF5C, 0xE9, 0xFFFFFFE9, 0x80, 0x81, 0x100, 0x78, 0x41, 0x61]
    for func in ("strrchr", "strchr"):
        cat = "t" + func
        for p in PATHS:
            for ch in chars:
                c.T(cat, func, S8(p), U(ch))
        for off in (1, 2, 3, 5, 15):
            for p in (b"Core.u", b"..\\System\\Core.u", b"x" * 37 + b"\\", b"", b"\\"):
                for ch in (0x5C, 0x2E, 0):
                    c.T(cat, func, S8(p, off), U(ch))
        alpha = b"ab\\.:/\xe9"
        for _ in range(150):
            p = bytes(rng.choice(alpha) for _ in range(rng.randint(0, 70)))
            c.T(cat, func, S8(p, rng.randint(0, 15)), U(rng.choice(list(alpha) + [0, 0x15C, 0xFFFFFFE9])))
    # strncpy: a destination of exactly n bytes (and of n + 7, to show where the zero padding stops)
    srcs = [b"", b"a", b"abc", b"Core.u", b"..\\System\\Editor.int", b"x" * 259, b"y" * 260, b"z" * 300, b"\xe9\xff\x80",
            b"0123456789abcdef"]
    for s in srcs:
        L = len(s)
        for n in sorted({0, 1, 2, 3, 4, L - 1, L, L + 1, L + 2, L + 3, L + 4, L + 17, 260, 261}):
            if n < 0:
                continue
            for doff, soff in ((0, 0), (1, 0), (0, 1), (3, 2), (2, 3)):
                c.T("tstrncpy", "strncpy", B8(n, doff), S8(s, soff), U(n))
            c.T("tstrncpy", "strncpy", B8(n + 7), S8(s), U(n))
    for _ in range(150):
        s = bytes(rng.randint(1, 255) for _ in range(rng.randint(0, 40)))
        n = rng.randint(0, 50)
        c.T("tstrncpy", "strncpy", B8(n + rng.randint(0, 3), rng.randint(0, 15)), S8(s, rng.randint(0, 15)), U(n))
    # _stricmp: only A-Z fold (so the characters between 'Z' and 'a' order differently from strcmp); exact returns
    pairs = [(b"", b""), (b"a", b""), (b"", b"a"), (b"abc", b"ABC"), (b"Core.u", b"CORE.U"), (b"core.u", b"core.v"),
             (b"[", b"a"), (b"[", b"A"), (b"_", b"a"), (b"_", b"A"), (b"@", b"`"), (b"Z", b"z"), (b"z", b"{"),
             (b"\xc0", b"\xe0"), (b"\xe9", b"\xc9"), (b"\x80", b"\x7f"), (b"abc", b"abd"), (b"abd", b"abc"),
             (b"ab", b"abc"), (b"ABC", b"ab"), (b"Golem.u", b"golem.U"), (b"\xff", b""), (b"", b"\xff"),
             (b"Engine.EngineVersion", b"engine.engineversion"), (b"a" * 300, b"A" * 300),
             (b"a" * 300, b"A" * 299 + b"B")]
    for x, y in pairs:
        for ox, oy in ((0, 0), (1, 2), (3, 1)):
            c.T("tstricmp", "_stricmp", S8(x, ox), S8(y, oy))
    alpha = b"aAzZ[_`{@\xe9\xc9 .\\"
    for _ in range(300):
        x = bytes(rng.choice(alpha) for _ in range(rng.randint(0, 12)))
        y = bytes(ch ^ 0x20 if rng.random() < 0.5 and chr(ch).isalpha() and ch < 0x80 else ch for ch in x)
        if rng.random() < 0.3:
            y = bytes(rng.choice(alpha) for _ in range(rng.randint(0, 12)))
        c.T("tstricmp", "_stricmp", S8(x), S8(y))
    # atoi (atol): white space by the "C" ctype table, one sign, decimal digits, wrap-around
    nums = [b"", b"0", b"1", b"123", b"-123", b"+5", b"  42", b"\t\n\v\f\r 7", b"2147483647", b"2147483648",
            b"-2147483648", b"-2147483649", b"4294967296", b"4294967297", b"99999999999", b"12abc", b"abc", b"0x1A",
            b"1e5", b"--5", b"+-5", b"- 5", b"-", b"+", b" ", b"007", b"-0", b"\xa05", b"\x855", b"\x1c5", b"5\xe9",
            b"1234567890123456789", b"9" * 40, b"3000000000", b"-3000000000", b"+2147483647", b"Version=926", b"926",
            b" -0012x"]
    for s in nums:
        for off in (0, 3):
            c.T("tatoi", "atoi", S8(s, off))
    for ch in range(1, 256):
        c.T("tatoiall", "atoi", S8(bytes([ch]) + b"5"))
    # toupper (GlmLib: 11932 calls): every unsigned char value, EOF, and values outside that range
    for v in list(range(-1, 256)) + [256, 0x161, 0x17A, 0x1E9, -2, -128, -129, -0x80000000, 0x7FFFFFFF, 0x10061,
                                     0xFFFFFF61, 0xFFFFFFE9]:
        c.T("ttoupper", "toupper", U(v))


def gen_qsort(c, rng):
    """qsort (Core.dll, GlmLib.dll): the final order and the exact sequence of comparator calls, which also fixes the
    order of equal keys. Harness comparators: int32 ascending (i32), int32 difference with wrap-around (diff),
    descending (desc), first byte only with a unique tag in the rest of the element (key), always equal (zero)."""
    nums = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 16, 17, 31, 32, 33, 64, 100, 257, 1000]

    def keys(pat, n, wide):
        if pat == "sorted":
            return list(range(n))
        if pat == "reversed":
            return list(range(n, 0, -1))
        if pat == "equal":
            return [7] * n
        if pat == "random":
            return [rng.randrange(1 << 32) if wide else rng.randrange(256) for _ in range(n)]
        if pat == "few":
            return [rng.randrange(4) for _ in range(n)]
        if pat == "organ":
            return [min(i, n - 1 - i) for i in range(n)]
        if pat == "saw":
            return [i % 7 for i in range(n)]
        k = list(range(n))                                   # almost sorted
        for _ in range(max(1, n // 20)):
            if n > 1:
                i, j = rng.randrange(n), rng.randrange(n)
                k[i], k[j] = k[j], k[i]
        return k

    for cmp, width in [("i32", 4), ("diff", 4), ("desc", 4), ("i32", 12), ("key", 1), ("key", 3), ("key", 8),
                       ("key", 64), ("zero", 8)]:
        for n in nums:
            for pat in ["sorted", "reversed", "equal", "random", "few", "organ", "saw", "almost"]:
                data = bytearray()
                for i, k in enumerate(keys(pat, n, cmp != "key")):
                    tag = i.to_bytes(4, "little") * 16
                    if cmp == "key":
                        data += bytes([k & 0xFF]) + tag[:width - 1]
                    else:
                        data += (k & 0xFFFFFFFF).to_bytes(4, "little") + tag[:width - 4]
                c.Q("q" + cmp, cmp, width, n, bytes(data))
    c.Q("qedge", "i32", 0, 5, b"")                           # element size 0
    c.Q("qedge", "i32", 0, 0, b"")


def gen_heap(c, rng):
    """malloc / realloc / _msize / free (Core.dll calls _msize 3094 times): _msize of every block, realloc growth and
    shrinkage, realloc from NULL and to 0"""
    sizes = [0, 1, 2, 3, 4, 5, 7, 8, 9, 12, 15, 16, 17, 24, 31, 32, 33, 63, 64, 65, 100, 255, 256, 257, 1000, 1016,
             1017, 1023, 1024, 1025, 4080, 4081, 4096, 4097, 8192, 65536, 65537, 1 << 20, (1 << 20) + 1]
    for n in sizes:
        c.Z("zsize", "m0,%d" % n, "s0", "f0")
    c.Z("zrealloc", "m0,10", "s0", "r0,5", "s0", "r0,100", "s0", "r0,4096", "s0", "r0,1", "s0", "r0,0", "f0")
    c.Z("zrealloc", "r0,16", "s0", "r0,16", "s0", "r0,15", "s0", "r0,17", "s0", "f0")
    c.Z("zrealloc", "r0,0", "s0", "f0")                    # realloc(NULL, 0) is malloc(0): a block
    c.Z("zrealloc", "m0,0", "s0", "r0,1", "s0", "r0,0", "f0")
    c.Z("zrealloc", "m0,100", "m1,100", "f0", "r1,200", "s1", "m0,50", "s0", "r0,5000", "s0", "f0", "f1")
    for _ in range(40):
        live, ops = [False] * 4, []
        for _ in range(24):
            k, op = rng.randrange(4), rng.choice("mrsf")
            if op == "m" and not live[k]:
                ops.append("m%d,%d" % (k, rng.choice(sizes[1:])))
                live[k] = True
            elif op == "r":
                ops.append("r%d,%d" % (k, rng.choice(sizes[1:])))
                live[k] = True
            elif op == "s" and live[k]:
                ops.append("s%d" % k)
            elif op == "f":
                ops.append("f%d" % k)
                live[k] = False
        ops += ["f%d" % k for k in range(4) if live[k]]
        c.Z("zmix", *ops)


def gen_setse(c):
    """_set_se_translator (Editor.dll installs a translator during its initialisation)"""
    c.X("xsetse", 0x10001234)
    c.X("xsetse", 0x10001234, 0x20005678, 0)
    c.X("xsetse", 0, 0)
    c.X("xsetse", 0xFFFFFFFF, 1, 0x10001234)


# ---------------------------------------------------------------- scratch tree of the F lines
# compare.py builds it (experiments\xrt\build\crt_diff\fs\root) before every F process: these names, contents,
# attributes, creation and write times; every access time is the run's start time (see compare.py).
def ft(y, mo, d, h=0, mi=0, s=0, frac=0):
    """FILETIME (100 ns units since 1601-01-01 UTC) of a UTC time"""
    days = (datetime.date(y, mo, d) - datetime.date(1601, 1, 1)).days
    return (days * 86400 + h * 3600 + mi * 60 + s) * 10 ** 7 + frac


RO, HID, SYS, ARC, NORMAL = 0x1, 0x2, 0x4, 0x20, 0x80
W03, S03 = ft(2003, 1, 15, 12), ft(2003, 7, 15, 12)
FS_MARKER = "crt_diff_fs.marker"          # crt_diff_core.h runs F lines only where this file exists
FS_ROOT_TIMES = (W03, S03)                # creation, write of the root and of its parent
FS_DIRS = [                               # relative path, attributes, creation, write
    ("System", 0, W03, S03), ("System\\Sub", 0, S03, W03), ("Maps", 0, W03, W03), ("dst", 0, S03, S03),
    ("empty", 0, W03, ft(2026, 3, 8, 7)), ("w", 0, W03, S03), ("deep", 0, W03, S03), ("deep\\a", 0, W03, S03),
    ("deep\\a\\b", 0, W03, S03), ("deep\\a\\b\\c", 0, W03, S03), ("rodir", RO, W03, S03), ("hiddir", HID, S03, W03)]
FS_TIMES = {                              # UTC write times: time_t limits, 1970 and Eastern time zone transitions
    "t1601.txt": ft(1601, 1, 2), "t1969.txt": ft(1969, 7, 20, 20, 17), "t1970a.txt": ft(1970, 1, 1, 3, 59, 59),
    "t1970b.txt": ft(1970, 1, 1, 5), "t1970c.txt": ft(1970, 1, 2), "t1980.txt": ft(1980, 1, 1),
    "t2038a.txt": ft(2038, 1, 19, 3, 14, 7), "t2038b.txt": ft(2038, 1, 19, 3, 14, 8),
    "t2038c.txt": ft(2038, 1, 18, 20), "t2099.txt": ft(2099, 12, 31, 23, 59, 59),
    "frac.txt": ft(2003, 1, 15, 12, 0, 0, 9999999),
    "dst\\spring_before.txt": ft(2026, 3, 8, 6, 59, 59), "dst\\spring_after.txt": ft(2026, 3, 8, 7),
    "dst\\fall_edt.txt": ft(2026, 11, 1, 5, 30), "dst\\fall_est.txt": ft(2026, 11, 1, 6, 30),
    "dst\\fall_after.txt": ft(2026, 11, 1, 7), "dst\\old2006_spring.txt": ft(2006, 4, 2, 7),
    "dst\\old2006_fall.txt": ft(2006, 10, 29, 6, 30), "dst\\new2007.txt": ft(2007, 3, 11, 7),
    "dst\\summer.txt": ft(2025, 7, 4, 16), "dst\\winter.txt": ft(2025, 12, 25, 17),
    "dst\\leap.txt": ft(2024, 2, 29, 12), "dst\\newyear.txt": ft(2026, 1, 1, 4, 59, 59)}
FS_FILES = [                              # relative path (code points <= 0xFF), contents, attributes, creation, write
    (FS_MARKER, b"crt_diff scratch tree\r\n", ARC, W03, W03),
    ("a.txt", b"hello", ARC, W03, S03), ("B.U", bytes(range(256)) * 4, ARC, S03, W03),
    ("Long Name With Spaces.int", b"[Engine.GameInfo]\r\nbFlag=True\r\n", ARC, W03, S03),
    ("name.with.dots.u", b"abc", ARC, W03, S03), ("noext", b"", ARC, W03, S03), ("caf\xe9.txt", b"x" * 12, ARC, S03, S03),
    ("ro.txt", b"read only", RO | ARC, W03, S03), ("hid.dat", b"h", HID | ARC, W03, S03),
    ("sys.dat", b"s", SYS | ARC, W03, S03), ("plain.bin", b"\0" * 7, NORMAL, W03, S03),
    ("System\\Core.u", b"\xc1\x83\x2a\x9e" + b"\0" * 60, ARC, W03, S03), ("System\\Engine.u", b"E" * 100, ARC, S03, W03),
    ("System\\Editor.int", b"[Public]\r\n", ARC, W03, S03), ("System\\GlmLib.ini", b"[GlmLib]\r\n", ARC, W03, S03),
    ("System\\golem.U", b"g", ARC, W03, S03), ("System\\Sub\\x.u", b"x", ARC, W03, S03),
    ("Maps\\Entry.un2", b"m" * 33, ARC, W03, S03), ("Maps\\x.U", b"", ARC, W03, S03),
    ("w\\existing.bin", b"0123456789", ARC, W03, S03), ("deep\\a\\b\\c\\leaf.txt", b"leaf", ARC, W03, S03),
    ("rodir\\in.txt", b"in", ARC, W03, S03)]
_SPECIAL = sorted(FS_TIMES.items())
FS_FILES += [(name, name.encode("latin-1"), ARC, _SPECIAL[(i + 1) % len(_SPECIAL)][1], t)
             for i, (name, t) in enumerate(_SPECIAL)]


def gen_fs(c):
    """the file-system calls GlmLib makes in editor mode: _getcwd(buf, 260), _fullpath(buf, path, 260), _chdir and
    errno (2 / 13 / 17 choose its message), _findfirst existence checks (it reads attrib, time_write and size),
    _findfirst / _findnext / _findclose listings, fopen "rb" / "wb" and fclose"""
    def h8(b):
        return "-" if b is None else (b.hex().upper() or "~")

    def cwd(buf, size):
        return "cwd:%s:%s" % (buf, size)

    def full(buf, size, p):
        return "full:%s:%s:%s" % (buf, size, h8(p))

    def cd(p):
        return "cd:" + h8(p)

    def opn(p, m):
        return "open:%s:%s" % (h8(p), h8(m))

    for size in ["260", "L+1", "L+2", "L", "L-1", "1", "0"]:
        c.F("fcwd", cwd("=", size))
    for size in ["0", "1", "260", "L", "L+1"]:
        c.F("fcwd", cwd("-", size))
    for p in [b"System", b"System\\", b"system", b"SYSTEM/", b"deep\\a\\b\\c", b"deep/a/../a/b", b".\\Maps\\..\\System",
              b"..", b".", b"", b"nonexist", b"a.txt", b"nonexist\\x", b"empty", b"rodir", b"hiddir", b"System\\Core.u",
              b"caf\xe9.txt", b"deep\\a\\b\\c\\..\\..\\..\\..\\Maps", b"System\\Sub\\"]:
        c.F("fchdir", cd(p), cwd("=", "260"))
    c.F("fchdir", cd(b"nonexist"), cd(b"System"), cwd("=", "260"))          # a success leaves errno alone
    c.F("fchdir", cd(b"System"), cd(b".."), cwd("=", "260"), cd(b"Maps"), cwd("=", "L+1"), cwd("=", "L"))
    for p in [b"a.txt", b"System\\..\\a.txt", b".", b"..", b"", None, b"C:\\x\\y\\..\\z", b"c:/x//y/./", b"\\x\\y", b"/x",
              b"\\\\srv\\share\\a\\..\\b", b"C:foo", b"a. ", b"a...", b"trailing\\", b"x" * 300, b"x" * 230,
              b"System\\*.u", b"\\\\?\\C:\\x\\..\\y", b"caf\xe9.txt", b"..\\" * 12 + b"top", b"\\\\.\\COM1", b"NUL",
              b"deep\\a\\b\\c\\leaf.txt"]:
        c.F("ffull", full("=", "260", p))
    for p in [b"a.txt", b"System\\Core.u"]:
        for size in ["P+1", "P+2", "P", "P-1", "1", "0"]:
            c.F("ffull", full("=", size, p))
    for p, size in [(b"a.txt", "0"), (b"a.txt", "260"), (b"a.txt", "1"), (b"x" * 300, "0"), (None, "0"), (b"", "0")]:
        c.F("ffull", full("-", size, p))
    c.F("ffull", cd(b"deep\\a"), full("=", "260", b"..\\x.u"), full("=", "260", b"b\\c\\leaf.txt"))
    names = [n.encode("latin-1") for n, *_ in FS_FILES] + [d.encode("latin-1") for d, *_ in FS_DIRS]
    for p in names + [b"b.u", b"System\\", b"nonexist", b"nonexist\\x", b"", b".", b"..", b"*", b"System\\*.u",
                      b"empty\\*", b"deep\\a\\..\\a"]:
        c.F("fff", "ff:" + h8(p))
    for p in [b"*", b"*.*", b"*.u", b"*.U", b"System\\*.u", b"System\\*", b"dst\\*", b"empty\\*", b"deep\\*", b"*.txt",
              b"?.txt", b"nomatch*.xyz", b"nonexist\\*", b"Maps\\*.un2", b"*.", b"t*", b"System/*.int", b"hiddir\\*",
              b"rodir\\*", b"deep\\a\\b\\c\\*"]:
        c.F("ffind", "find:" + h8(p))
    c.F("ffind", cd(b"System"), "find:" + h8(b"*.u"))
    c.F("ffind", "find:" + h8(b"nomatch*"), "find:" + h8(b"System\\*.u"))
    for p, m in [(b"a.txt", b"rb"), (b"B.U", b"rb"), (b"nonexist.txt", b"rb"), (b"System", b"rb"), (b"ro.txt", b"rb"),
                 (b"hid.dat", b"rb"), (b"", b"rb"), (b"nonexist\\x.bin", b"rb"), (b"a.txt", b"r"), (b"w\\new.bin", b"wb"),
                 (b"w\\existing.bin", b"wb"), (b"ro.txt", b"wb"), (b"hid.dat", b"wb"), (b"sys.dat", b"wb"),
                 (b"System", b"wb"), (b"nonexist\\x.bin", b"wb"), (b"w\\NEW2.BIN", b"w"), (b"rodir\\new.bin", b"wb"),
                 (b"w\\" + b"n" * 250, b"wb"), (b"w\\" + b"n" * 300, b"wb")]:
        c.F("fopen", opn(p, m))
    c.F("fopen", opn(b"nonexist.txt", b"rb"), opn(b"a.txt", b"rb"))      # a success leaves errno alone
    c.F("fopen", cd(b"w"), opn(b"rel.bin", b"wb"), opn(b"rel.bin", b"rb"), opn(b"existing.bin", b"rb"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--i10", type=int, default=6000, help="cases of 8 random doubles at %%.16e")
    ap.add_argument("--narrow-i10", type=int, default=2000, help="the same for narrow sprintf")
    ap.add_argument("--errors-out", help="write the lines that run one process per case here: E (intentional error "
                                         "behaviour), X (_set_se_translator), F (file system)")
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
    # bounded printf, from its own random stream (the corpus above stays unchanged)
    gen_bounded(c, random.Random(a.seed + 2))
    # CRT dependencies of `ucc make`, from their own random stream (the corpus above stays unchanged)
    dr = random.Random(a.seed + 3)
    v = Vsprintf(c)
    for g in (gen_int, gen_float, gen_ptr, gen_n, gen_odd, gen_counted, gen_trunc, gen_str_narrow, gen_narrow_text):
        g(v, dr)
    gen_tstr(c, dr)
    gen_qsort(c, dr)
    gen_heap(c, dr)
    gen_setse(c)
    gen_fs(c)
    with open(a.out, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(c.lines) + "\n")
    if a.errors_out:
        with open(a.errors_out, "w", encoding="ascii", newline="\n") as f:
            f.write("\n".join(c.err_lines) + "\n")
    total = sum(c.counts.values())
    print("corpus: %d cases -> %s" % (total, a.out))
    for k in sorted(c.counts):
        print("  %-10s %6d" % (k, c.counts[k]))


if __name__ == "__main__":
    main()
