"""Readers for the x87 harness files and an exact (big-integer) reference for sin/cos/tan/exp/log.

Used by analyze.py; no third-party packages (mpmath is not available in the workspace venv).
"""
import struct
from fractions import Fraction

REC = struct.Struct("<IIIIQQ")                  # op, aux, set, idx, a, b
OUT = struct.Struct("<10sHIQQQII")              # r80, fsw, r32, r64, i64, x, flags, pad

OPS = {1: "fsin", 2: "fcos", 3: "fptan", 4: "fpatan", 5: "fyl2x", 6: "f2xm1", 7: "fscale", 8: "fsqrt", 9: "frndint",
       10: "fistp_m16", 11: "fistp_m32", 12: "fistp_m64", 13: "fist_m16", 14: "fist_m32", 15: "fild_m64",
       16: "fild_m64+fistp_m64", 17: "fild_m64+fmul_m64", 18: "fild_m64+fadd_m64", 19: "fld_constant",
       32: "appSin", 33: "appCos", 34: "appTan", 35: "appAtan", 36: "appAtan2", 37: "appSqrt", 38: "appExp",
       39: "appLoge", 40: "FGlobalMath_sine_table", 41: "FGlobalMath_sqrt_table", 42: "_ftol2"}
SETS = ["edge", "pi_multiples", "rand_small", "rand_medium", "rand_large", "rand_out_of_range", "rand_tiny",
        "f2xm1_domain", "f2xm1_outside_domain_UB", "fyl2x_y1", "fyl2x_near1", "fyl2x_rand", "fyl2x_special",
        "fpatan_rand", "fpatan_special", "fscale_rand", "fscale_special", "fsqrt_rand", "round_halfway",
        "round_rand", "fild64_above_2p53", "fild64_below_2p53", "constants", "engine_sintab", "engine_sqrttab",
        "engine_rand_small", "engine_rand_large", "engine_exp_range", "engine_loge_range", "engine_edge",
        "ftol_timing_loop", "ftol_edge", "ftol_out_of_range_UB", "engine_atan2_rand"]


def load(path, st):
    data = open(path, "rb").read()
    return [st.unpack_from(data, i) for i in range(0, len(data), st.size)]


def d(bits):
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def f(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def frac80(r80):
    """exact value of an 80-bit extended (finite) as a Fraction; None for inf/nan"""
    mant = int.from_bytes(r80[:8], "little")
    se = int.from_bytes(r80[8:10], "little")
    e, neg = se & 0x7FFF, se >> 15
    if e == 0x7FFF:
        return None
    v = Fraction(mant) * Fraction(2) ** (max(e, 1) - 16383 - 63)
    return -v if neg else v


def frac_d(bits):
    x = d(bits)
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return Fraction(x)


def frac_f(bits):
    x = f(bits)
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return Fraction(x)


# ---------------------------------------------------------------- exact reference (fixed point)
PREC = 400                                       # bits of the fixed-point reference


def _arctan_inv(x, bits):
    one = 1 << bits
    s = t = one // x
    n, x2, sign = 1, x * x, -1
    while t:
        t //= x2
        n += 2
        s += sign * (t // n)
        sign = -sign
    return s


PI_FIX = 4 * (4 * _arctan_inv(5, PREC + 20) - _arctan_inv(239, PREC + 20)) >> 20    # pi * 2^PREC


def _fix(q):            # Fraction -> fixed point integer (scale 2^PREC), rounded
    return round(q * (1 << PREC))


def _sincos_fix(r):     # r fixed point, |r| <= pi/4 -> (sin, cos) fixed point
    one = 1 << PREC
    s, t, n = r, r, 1
    while t:
        t = -t * r // one * r // one // ((n + 1) * (n + 2))
        n += 2
        s += t
    c, t, n = one, one, 0
    while t:
        t = -t * r // one * r // one // ((n + 1) * (n + 2))
        n += 2
        c += t
    return s, c


def sin_cos_exact(x, period_fix=None):
    """sin and cos of Fraction x as Fractions (error ~2^-390 absolute); period_fix overrides pi (fixed point)
    to model a reduced-precision pi."""
    p = PI_FIX if period_fix is None else period_fix
    xf = _fix(x)
    half = p // 2
    k = (2 * xf + half) // (2 * half)          # nearest multiple of pi/2
    r = xf - k * half
    s, c = _sincos_fix(r)
    q = k % 4
    sv, cv = [(s, c), (c, -s), (-s, -c), (-c, s)][q]
    return Fraction(sv, 1 << PREC), Fraction(cv, 1 << PREC)


def ulps_double(err, ref):
    """|err| in units of the double ulp at |ref|"""
    if ref == 0:
        return float("inf") if err else 0.0
    a = abs(ref)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    ue = max(e - 52, -1074)
    return float(abs(err) / Fraction(2) ** ue)


def ulps_float(err, ref):
    if ref == 0:
        return float("inf") if err else 0.0
    a = abs(ref)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    ue = max(e - 23, -149)
    return float(abs(err) / Fraction(2) ** ue)


P66_FIX = 0x3243F6A8885A308D3 << (PREC - 64)    # the x87's 66-bit pi, as fixed point
