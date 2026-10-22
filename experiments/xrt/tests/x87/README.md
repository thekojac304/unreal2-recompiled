# x87 model vs. real x87 hardware (Core.dll / UCC.exe)

Independent check of the runtime's x87 model (`runtime/xrt_cpu.c`, `runtime/xrt.h`: host doubles,
transcendentals through host libm) against the x87 unit of the machine, for every x87 transcendental,
rounding and square-root instruction the translated modules contain, with the inputs the engine
actually feeds them. Raw data: `results.json` (this directory). This validation changed no runtime file.

**Runtime under test:** `runtime/xrt_cpu.c` at commit 805e2fe (sha256 `82acc679...`), "rt" below.
While this validation ran, another session changed `xrt_cpu.c` in the working tree to adopt this
directory's `pfix` prototype (66-bit-pi reduction plus SDM special operands). That uncommitted snapshot
(sha256 `a39bf8c8...`, "wt") was measured separately. It is bit-identical to `pfix` on all 5,857,054
records and on all 2^32 float arguments of `Sin`/`Cos`/`Tan`, and it leaves `Exp` unchanged.

## Summary

| question | answer (rt = committed runtime) |
|---|---|
| Commandlet paths (HelloWorld, Simple, ArrayTest, also `hello`, `badclass`) | They execute `appSin` (sine table), `appSqrt` (sqrt table and the appInit timing loop) and `_ftol2`. Sqrt table: 16384/16384 floats identical. Timing loop: 2^25 steps of `D` and `_ftol2(D)` identical. `_ftol2`: 286,241 inputs identical. Sine table: 16383/16384 floats identical. `TrigFLOAT[8192]` (x = pi as a double) is `0x250D3000` (1.2246064e-16) on the hardware and `0x250D3132` (1.2246469e-16) in rt, 306 float ulps apart (66-bit pi, see below). No code that reads the table runs in any trace, so commandlet output is unaffected (consistent with the identical stdout/UCC.log). wt: 16384/16384 identical. |
| Basic rounding (`frndint`, `fistp m16/m32/m64`, `fist m16/m32`, all four RC modes through `xrt_fround`/`xrt_fist*`) | 0 mismatches in 1,071,240 records (every k + {0, 1/4, 1/2, 3/4, 0.5 - 1 ulp, 0.5 + 1 ulp} for k in [-2050, 2050], integer-range boundaries, 2^52/2^53/2^63, inf, NaN, -0, plus 20,000 random values, each x 4 RC). |
| `fsqrt` | 0 mismatches: all 2^32 float arguments of `Sqrt`, 250,000 random doubles over the whole exponent range, negatives, denormals, edges, the sqrt table and the timing loop. |
| `fild m64` above 2^53 (documented deviation) | `fild; fstp m64` identical (100,000 of 100,000: both round once). `fild; fistp m64` round trip differs in 89,932 of 100,000. `fild; fmul m64` / `fadd m64` differ by 1 double ulp in 24,746 / 13,992 of 100,000 (double rounding). Below 2^53: 0. Core.dll's `fild m64` sites load rdtsc deltas and cycle counts far below 2^53. |
| Script natives, all 2^32 float arguments (float in, float out) | `Sqrt`, `Exp`: 0 mismatches. `Atan`: 2. `Loge`: 6. `Sin`/`Cos`/`Tan` with abs(x) < 2^10: 0. With 2^10 <= abs(x) < 2^20: 8 / 2 / 8. With 2^20 <= abs(x) < 2^63: 314,698,626 / 314,705,336 / 345,660,490 of 721,420,288 (max 124,721,067 float ulps). `Sin`/`Cos`(+-inf): rt returns +-inf, the hardware QNaN. `Tan`(NaN, +-inf, finite abs(x) >= 2^63): rt returns a stale register (0.0 here), the hardware QNaN (1,107,296,256 arguments). |
| Do mismatches survive the engine's storage precision? | Mostly not for abs(x) < 2^20: rt and the hardware differ at double precision in 0.3-5 % of small arguments (UCRT is not correctly rounded; <= 0.93 double ulp for abs(x) < 1), but all of those disappear when stored as float, except the few listed. For abs(x) >= 2^20 and near multiples of pi, the mismatches do survive float storage. |
| Max error of rt against the hardware's 80-bit result | sin/cos/tan, abs(x) < 1: <= 0.93 double ulp. 1 <= abs(x) < 2^10: up to 6.2e5 double ulps near zeros of sin/cos (hardware pi66 error, relative). Large abs(x): ~1e17 to 2e20 double ulps. atan <= 0.52; fpatan <= 1.0; fyl2x <= 1.4; f2xm1 (abs(x) <= 1) <= 2.93; appLoge <= 1.54; appExp <= 710 (53-bit `fldl2e` constant), yet 0 float mismatches. |
| Hardware reference itself | 32-bit inline-asm and x64 ml64 kernels agree on every one of 2^32 x 7 sequences (float store, 80-bit ST(0), condition codes). P-cores and E-cores of the i7-14700K agree too. |
| Host dependence of rt | x64 UCRT switches to FMA3 code paths when the CPU has them. Over all 2^32 arguments of 7 natives, float results with FMA3 on and off: 0 differences. Doubles: 210 of 16384 sine-table entries and 0.5-1.4 % of trig records differ. |

### Deviations, classified

| # | deviation (rt) | demonstrated by | class | engine reachability | wt |
|---|---|---|---|---|---|
| 1 | `fsin`/`fcos`/`fptan` reduce with the exact pi (libm); the x87 uses a 66-bit pi (`0x3243F6A8885A308D3 * 2^-64`). Up to 1.2e8 float ulps for large abs(x); 306 float ulps for sin(pi). The runtime README's "last bits" understates this. | records (pi multiples, large), exhaustive, sine table; exact big-integer check: the hardware is within 0.00033 double ulp of sin/cos/tan reduced with pi66, in every sampled set | fidelity bug (defined hardware behaviour) | sine-table entry 8192 (start-up, not read in commandlets); script trig with abs(x) >= ~1e4 | fixed |
| 2 | `fsin`/`fcos`/`fptan` of +-inf: rt leaves inf and sets C2; the hardware gives QNaN indefinite with C2 = 0 (SDM #IA, masked) | records edge, exhaustive (2 args per op) | bug | script `Sin`/`Cos`/`Tan`(+-inf) | fixed |
| 3 | `fptan` of NaN/inf: rt sets C2 and pushes nothing; the hardware clears C2 and pushes the NaN result (not 1.0, measured). `appTan` then returns a stale model register | records (C2, pushed value), exhaustive `Tan` (16,777,216 args) | bug | script `Tan`(NaN/+-inf) | fixed |
| 4 | `appTan` with finite abs(x) >= 2^63: `fptan` leaves the operand (C2 = 1), `fstp st(0)` empties the stack, and the caller's `fstp m32` underflows. The hardware stores QNaN indefinite (masked stack fault); rt has no tag word and stores a stale register (0.0 in a fresh thread). | records (5,000 + 12 edge), exhaustive (1,090,519,040 args) | model limitation (x87 stack-fault response not modelled), defined by the SDM | script `Tan` of huge values | **remains** |
| 5 | `fscale` with a NaN scale, 0 x 2^+inf, inf x 2^-inf: rt evaluates `(int)NaN` (undefined in C; MSVC gives INT_MIN) and returns 0 or inf; the hardware returns NaN | records fscale_special (9) | bug, C UB in `xrt_fscale` | none: in `appExp`, ST(1) NaN/inf implies ST(0) NaN (exhaustive `Exp` incl. +-inf/NaN: 0 mismatches) | fixed |
| 6 | Double rounding (64 -> 53 -> 24 bits): the hardware rounds its 64-bit result once to float | exhaustive, with the hardware significand bits in results.json (e.g. sin(9830.3984375): `...7ffffffee4` below the float LSB) | inherent in a double register model (ABI) | `Sin` 4, `Atan` 2, most of `Loge`'s 6 float arguments | remains |
| 7 | 53-bit `fldl2e`/`fldln2`/`fldpi` constants and double intermediates in `appExp`/`appLoge` | records (appExp <= 710 double ulps), exhaustive | inherent (ABI) | 0 float mismatches for `Exp`, part of `Loge`'s 6 | remains |
| 8 | 80-bit exponent range of intermediates: `appExp(+-DBL_MAX)` gives inf/0 on the hardware and NaN in rt | records engine_edge | documented deviation | not from float arguments (max 3.4e38) | remains |
| 9 | `fild m64` above 2^53 | records fild64 | documented deviation | no Core.dll site | remains |
| 10 | NaN details: SNaN not quieted at double precision; NaN sign/payload of `fyl2x`/`atan2` with NaN operands; C2 after `fsin`(NaN) | records (nan_payload_only, c2) | payload only, never visible after float storage except as a different NaN | none | C2/SNaN fixed; payload remains |
| 11 | `f2xm1` outside [-1, 1] | records f2xm1_outside_domain_UB | **undefined** (SDM), not a bug | `appExp` only calls it with abs(x) <= 0.5 | n/a |
| 12 | `_ftol2` of NaN/inf/abs(x) >= 2^63 | records ftol_out_of_range_UB: identical anyway | C UB (out-of-range conversion), identical | n/a | n/a |

## 1. Where the modules use these instructions

Found with `tools/xrt/discover.py`'s `Module` over `sandbox_ref/hellofull/System/Core.dll`
(`find_x87.py`); "executed" is the original's `hit_rvas` in `experiments/xrt/traces/*.json`.
`UCC.exe` contains none of them (one `fild`). Core.dll contains exactly one each of `fsin`, `fcos`,
`fptan`, `fyl2x`, `f2xm1`, `fscale`, `frndint`, `fsqrt`, two `fpatan`, one `fistp` (in the statically
linked CRT `_ftol2`), no `fsincos`/`fprem`/`fxtract`/`fyl2xp1`/`fninit`/`fldcw`/`fnstcw`/`fisttp`.
All transcendental instructions sit in eight tiny exported leaf functions:

| rva | function | body | executed in traces | engine callers and inputs | stored as |
|---|---|---|---|---|---|
| 0x16fa0 | `appSin(double)` | `fld m64; fsin` | all (start-up) | `FGlobalMath::FGlobalMath` sine table: `x_i = (double)(i+i) * (pi/16384)`, i = 0..16383 (`fild m32; fadd st,st; fmul m64`); script `Sin` (`execSin`, float in/out); `FQuat::FQuatToAngAxis`, rva 0x335f0 | float32 (`fstp m32` into `GMath`) |
| 0x17010 | `appSqrt(double)` | `fld m64; fsqrt` | all (start-up) | `FGlobalMath` sqrt table: `(double)i * 2^-14`, i = 0..16383; `appInit` CPU-speed loop (rva 0x5b990): `D = (sqrt(D) + 3.14) + D` from `D = 0`, then `_ftol2(D)`, for 3 x 200 ms; script `Sqrt`, `VSize`, `VSize2D`; vector/quaternion/sphere size and normalisation | float32 (tables, script), float64 (`fstp m64`, timing loop) |
| 0x16fc0 | `appCos(double)` | `fld m64; fcos` | VMProbe only | script `Cos`; `FQuat::AngAxisToFQuat`; rva 0x335f0 | float32 |
| 0x16fe0 | `appTan(double)` | `fld m64; fptan; fstp st(0)` | none | script `Tan` | float32 |
| 0x16ff0 | `appAtan(double)` | `fld m64; fld1; fpatan` | VMProbe only | script `Atan` | float32 |
| 0x17000 | `appAtan2(double Y, double X)` | `fld Y; fld X; fpatan` | none | script `Atan2`; `FVector::Rotation`; `FCoords::OrthoRotation` | float32 |
| 0x16f60 | `appExp(double)` | `fldl2e; fmul m64; fld st0; frndint; fxch; fsub st,st1; f2xm1; fld1; faddp; fscale; fstp st1` | none | script `Exp` | float32 |
| 0x16f80 | `appLoge(double)` | `fldln2; fld m64; fyl2x` | none | script `Loge` | float32 |
| 0x5d510 | CRT `_ftol2` | `fistp m64` (RC = nearest) + `fild m64` + sign correction = truncation | all | every float-to-integer cast; the timing loop | int64 |

The three memory constants the mirrored sequences load (`pi/16384` as a double, `2^-14` as a float,
`3.14` as a double) were checked against the operands in Core.dll (`check_constants.py`; loop bounds
16384). Script natives convert the float argument exactly to double (`fld m32; fstp m64`) and store the
result with `fstp m32`. The only code in Core.dll that reads the sine table (`GMath` + 0x8c:
`FVector::RotateAngleAxis` and the two `FCoords` `FRotator` operators) does not execute in any trace;
nothing in Core.dll reads the sqrt table. The `fild m64` sites (appSeconds' rdtsc delta, appInit's
rdtsc values, StaticExit's cycle statistics) load values far below 2^53 and appInit stores them
immediately with `fstp m64`.

## 2-4. Results

### Exact engine inputs

| input set | n | rt float mismatches | rt double mismatches | wt / pfix float |
|---|---|---|---|---|
| FGlobalMath sine table (`appSin`, stored float) | 16384 | 1 (index 8192, 306 ulps) | 516 (580 with FMA3 off) | 0 |
| FGlobalMath sqrt table (`appSqrt`, stored float) | 16384 | 0 | 0 | 0 |
| appInit timing loop, `D` (stored double) and `_ftol2(D)` | 2^25 steps (block hashes) | 0 | 0 | 0 |
| `_ftol2` on loop values, edges, random doubles | 286,241 | 0 (integer) | - | 0 |
| arguments built by the mirrored callers (sine-table x) | 16384 | 0 (bit-identical doubles) | - | 0 |

### All float32 arguments of the script natives (2^32 each)

Float mismatches by argument class, rt (committed) and the alternative helper models. Classes:
abs(x) < 2^-30 / < 1 / < 2^10 / < 2^20 / < 2^63 / >= 2^63 or inf / NaN.

| op | model | total | by class | max float ulps (abs(x) < 2^20 / larger) |
|---|---|---|---|---|
| sin | rt | 314,698,636 | 0 / 0 / 0 / 8 / 314,698,626 / 2 / 0 | 1 / 124,100,293 |
| sin | hx | 4 | 0 / 0 / 0 / 2 / 2 / 0 / 0 | 1 / 1 |
| sin | p66 | 6 | 0 / 0 / 0 / 2 / 2 / 2 / 0 | 1 / 1 |
| sin | pfix = wt | 4 | 0 / 0 / 0 / 2 / 2 / 0 / 0 | 1 / 1 |
| cos | rt | 314,705,340 | 0 / 0 / 0 / 2 / 314,705,336 / 2 / 0 | 1 / 124,452,595 |
| cos | hx, pfix = wt | 0 | - | - |
| cos | p66 | 2 | +-inf only | - |
| tan | rt | 1,452,956,754 | 0 / 0 / 0 / 8 / 345,660,490 / 1,090,519,042 / 16,777,214 | 1 / 124,721,067 |
| tan | hx | 1,090,519,042 | 0 / 0 / 0 / 0 / 2 / 1,090,519,040 / 0 | 0 / 1 |
| tan | p66 | 1,107,296,256 | 0 / 0 / 0 / 0 / 0 / 1,090,519,042 / 16,777,214 | 0 / 0 |
| tan | pfix = wt | 1,090,519,040 | 0 / 0 / 0 / 0 / 0 / 1,090,519,040 / 0 | 0 / 0 |
| atan | rt, hx, p66 | 2 | x = +-0.069052003 (double rounding) | 1 |
| sqrt | all | 0 | - | - |
| exp | all (wt too) | 0 | - | - |
| loge | rt, p66 | 6 | 1 / 1 / 1 / 0 / 1 / 2 / 0 | 1 |
| loge | hx | 5 | 0 / 1 / 1 / 0 / 1 / 2 / 0 | 1 |

`Atan2` (no exhaustive enumeration possible): 2^27 random float pairs (half with exponents in
[-20, 20]), 0 float mismatches for every model (rt: 499 NaN-payload-only differences).
All sin/cos/tan, atan and loge mismatches for abs(x) < 2^20 are listed completely in
`build/x87/exh/mis_*.bin` (sorted, with the hardware's 80-bit value). The arguments VMProbe uses
(`Sin(0.5)`, `Cos(0.5)`, `Atan(1.0)`, `Sqrt(2.0)`) are not among them.

### Single instructions with random and edge operands (records, rt)

| set / op | n | double mismatches | float mismatches | max double ulps vs 80-bit hardware value |
|---|---|---|---|---|
| fsin / fcos / fptan, abs(x) in [2^-30, 16) | 100,000 each | 594 / 816 / 835 | 0 | 0.89 / 1.43 / 0.95 |
| same, abs(x) in [8, 2^20) | 50,000 each | 14,858 / 14,845 / 20,467 | 0 | 1.8e4 / 4.9e4 / 9.1e4 (pi66 near zeros) |
| same, abs(x) in [2^20, 2^63) | 50,000 each | 49,967 / 49,962 / 50,000 | 21,685 / 21,716 / 23,768 | up to 8.7e16 |
| same, multiples of pi +- 2 ulps (k in [-1000, 1000]) | 30,009 each | 18,006 / 7,972 / 25,036 | 17,500 / 7,500 / 25,000 | 6.1e14 |
| fsin / fcos / fptan, abs(x) in [2^63, 2^1023] | 5,000 each | 0 | 0 | (operand unchanged, C2 = 1: correct) |
| f2xm1, x in [-1, 1] | 100,002 | 43,731 | 0 | 2.93 |
| fyl2x (y = 1 / x near 1 / random) | 100,000 each | 24 / 12,660 / 25,107 | 0 | 0.5 / 1.19 / 1.4 |
| fpatan random (all signs, exponents to +-1023) | 120,000 | 113 | 0 | 1.0 |
| fpatan / appAtan2 special grid (+-0, +-inf, NaN, ...) | 121 each | 0 | 0 | - |
| fscale random (scale in [-1100, 1100], fractional) | 50,000 | 0 | 0 | 0 |
| fscale specials | 105 | 9 | 9 | deviation 5 |
| fld constants (`fld1`, `fldl2t`, `fldl2e`, `fldpi`, `fldlg2`, `fldln2`, `fldz`) | 7 | 0 as doubles | 0 | 0.37 (the hardware constants have 64 bits) |
| `appExp` x in [-750, 750] / `appLoge` | 100,000 each | 18,821 / 31,126 | 0 / 0 | 709 / 1.47 |

FMA3 on vs off (`_set_FMA3_enable`): float results of all records identical; double results differ for
1,422 of 255,117 `fsin`, 1,468 `fcos`, 3,482 `fptan`, 14 `f2xm1`, 1 `atan` records and 210 of the
16384 sine-table entries. The hardware match is slightly better with FMA3 on (516 against 580
double mismatches in the sine table).

## Improvements

All of these were measured as helper prototypes on the same lifted code (`x87_alt.c`). No runtime
file was edited here.

1. **66-bit-pi argument reduction (`p66`), portable C.** Reduce abs(x) > pi/4 exactly against
   pi66/2 = `0x3243F6A8885A308D3 * 2^-65`, using 128-bit integer arithmetic (`_umul128`): an estimate
   `k = nearbyint(x * 2/pi)`, one correction step with `dk = round(r / P)`, then a final +-1 check
   against P/2. Convert the remainder with a sticky bit (correctly rounded to double), pick the
   quadrant from `k & 3`, and evaluate host `sin`/`cos`/`tan`. Evidence:
   * hardware fsin/fcos/fptan are within 0.00033 double ulp of the exact pi66-reduced function in
     every sampled set (small, medium, large, pi multiples), against up to 7e15 double ulps of the
     true sin/cos/tan;
   * the float mismatches of `Sin`/`Cos`/`Tan` drop from 314.7M / 314.7M / 345.7M to 2 / 0 / 0
     finite ones, and the sine table becomes identical.

   Cost in the exhaustive loop: about the same as rt (sin: 81 s against 77 s for 2^32
   evaluations including the hardware kernel).
2. **SDM special operands (`pfix` = `p66` plus these).**
   * `fsin`/`fcos`/`fptan`: NaN gives the quieted NaN and inf gives QNaN indefinite, both with C2 = 0;
     `fptan` then pushes that same NaN (measured: not 1.0). Only a finite abs(x) >= 2^63 sets C2.
   * `fscale`: NaNs propagate, 0 x 2^+inf and inf x 2^-inf give QNaN indefinite, and a NaN or
     infinite scale is never converted to `int`.

   Evidence: all edge records match, including C2 and the pushed value. `Sin`/`Cos` are exact except
   for the double-rounding cases, and `Tan` differs only for finite abs(x) >= 2^63 (deviation 4).
   This set has been adopted in the working tree by another session (wt above); it is bit-identical
   to `pfix` in every measurement here. (The exhaustive `pfix` runs predate the correction of the
   pushed value from 1.0 to the NaN. That correction cannot change a stored result, because `appTan`
   pops the pushed value; a `Tan` rerun produced the same per-chunk hashes.)
3. **"Higher precision from the C library on x64":** not available. MSVC's `long double` is `double`,
   so UCRT cannot evaluate in 80 bits. The only higher-precision path on an x64 Windows host is the
   x87 unit itself, executed in 64-bit mode (`hx`, three-instruction ml64 helpers). It gives the
   hardware's double exactly for single instructions (0 double mismatches for fsin/fcos/fptan/fsqrt
   records) and on float storage leaves only the double-rounding cases.

   It does not help `appExp`/`appLoge` (53-bit constants in the lifted code), deviation 4 or 8, and
   it is not portable (x86-64 hosts only; x87 implementations other than this Intel part were
   not tested). For float-stored results, `pfix` reaches the same agreement portably.
4. **Not cheap, therefore only reported:**
   * double rounding and 64-bit constants (deviations 6-8) need 80-bit registers or round-to-odd
     intermediates, which is a CPU-struct ABI change;
   * deviation 4 needs a tag word, or at least an "empty" marker for popped registers, read by `fstp`.
5. **Host independence at double precision** (optional): calling `_set_FMA3_enable(0)` at start-up
   makes UCRT results independent of FMA3 availability (measured above: changes doubles only).

Also noted, not reachable in these modules: `xlift.py` translates `fninit` as `c->fcw = 0x037F`
(64-bit precision) without going through `xrt_fldcw`. Neither UCC.exe nor Core.dll contains `fninit`,
`fldcw` or `fnstcw`; the only control-word change is UCC's `_controlfp(_PC_53, _MCW_PC)`.

## How the comparison works

* `x87_hw32.exe` (32-bit, MSVC inline `__asm`, FCW 0x027F, which is also the FCW a 32-bit process starts
  with) executes each operation as the engine's instruction sequence on the hardware and stores ST(0)
  as 80-bit, double and float (`fstp m80/m64/m32` from the same register), plus FSW and integer stores.
  It never runs code from the game modules; the sequences are written out in the harness.
* `x87_rt64.exe` (x64) links `runtime/xrt_cpu.c` compiled with the runtime's own flags
  (`/O2 /fp:strict`, static UCRT) and the lifted Core.dll functions themselves
  (`xlift.py --only` of the eight `app*` functions and `_ftol2`, compiled with the lifted-code flags
  `/O1 /fp:strict`, verified identical to the full-module translation). Calls go through `CALL()` on a
  CPU struct over a small guest memory; caller sequences (script natives, `FGlobalMath` loops, timing
  loop) are mirrored with the statements `xlift.py` emits for those instructions.
* Records (`x87_rt64 gen`): about 5.9 million (operation, input) pairs: every sine/sqrt table index,
  2^25 timing-loop steps, edge values, multiples of pi, random arguments by magnitude, fyl2x/fpatan/
  fscale special-operand grids, rounding ties for all four RC modes, int64 above 2^53. Both harnesses
  evaluate the same file; `x87_rt64 cmp` compares bit for bit.
* Exhaustive float32: every one of the 2^32 float arguments of the script natives `Sin`, `Cos`, `Tan`,
  `Atan`, `Sqrt`, `Exp`, `Loge` (`x87_rt64 exhaustive`). The hardware side runs in-process through ml64
  kernels (`x87_hw64.asm`, x87 in 64-bit mode); their results (float store, 80-bit register and
  condition codes) were compared with the 32-bit harness over all 2^32 arguments by per-2^20-chunk
  hashes, so the 32-bit reference covers the whole space.
* Alternative helper models, evaluated with the same lifted code (`x87_alt.c`, compiled into renamed
  copies of the lifted functions; prototypes only, nothing in `runtime/` changed): `hx` executes the x87
  instruction on the host (x64) with the result rounded to the model's double; `p66` uses libm after an
  exact argument reduction with the x87's 66-bit pi; `pfix` is `p66` plus SDM special-operand handling
  for `fsin`/`fcos`/`fptan` (NaN, infinity) and `fscale`.

## Reproduce

```bat
rem from the workspace root; build products go to experiments\xrt\build\x87 (git-ignored)
.venv\Scripts\python -I experiments\xrt\tests\x87\run_x87.py --build
rem   --build lifts the helpers, snapshots runtime\xrt_cpu.c at HEAD (x87_rt64_head.exe, the runtime
rem   under test) and, if the working tree differs, the working-tree copy (x87_rt64_wt.exe)
rem   --quick: exhaustive runs for sin only; --skip-exhaustive: reuse build\x87\exh
rem single steps (in experiments\xrt\build\x87):
x87_rt64_head gen inputs.bin
x87_hw32 records inputs.bin hw32.bin
x87_rt64_head cmp inputs.bin hw32.bin cmp_records.json all
x87_rt64_head exhaustive sin exh/hw64 exh/exh_x64.jsonl exh/mis rt,hx,p66,pfix all
x87_hw32 exhaustive sin exh/hw32 all
rem   (then compare exh\hw32_sin.bin with exh\hw64_sin.bin: identical per-chunk hashes)
x87_rt64_head fmadiff all exh/fmadiff.jsonl
x87_hw32 dummy 33554432 hw_dummy.bin
x87_rt64_head dummy 33554432 hw_dummy.bin
.venv\Scripts\python -I experiments\xrt\tests\x87\summarize_records.py cmp_records.json rt
.venv\Scripts\python -I experiments\xrt\tests\x87\analyze.py experiments\xrt\build\x87 engine_sintab FGlobalMath_sine_table rt
```

Validity notes: FSW exception flags and C1 are not compared (the model does not keep them; the engine
never reads them after these instructions); C2 is compared for `fsin`/`fcos`/`fptan`. Only this Intel
CPU was measured. One of more than 1e11 float comparisons differed once and not again: a `Tan` argument whose
hardware float read back with bit 30 flipped right after the same buffer had hashed correctly. The
rerun was clean; it is kept in `results.json` under `transient_events`. All hardware hashes repeated
across at least five independent runs per operation.

The full run takes about an hour on a 28-thread i7-14700K (each exhaustive pass is 2^32 evaluations of
the hardware sequence and of each model).

| file | purpose |
|---|---|
| `find_x87.py` | step 1: functions containing the instructions, executed flags, disassembly to build dir |
| `check_constants.py` | the constants of the mirrored engine sequences equal the engine's operands |
| `x87_common.h` | record formats, operation ids, hashing, P/E-core affinity |
| `x87_hw32.c` | 32-bit hardware reference |
| `x87_hw64.asm` | x87 kernels for the in-process exhaustive runs and the `hx` model |
| `x87_rt64.c` | runtime side, generator, comparison, exhaustive, FMA3 and timing-loop checks |
| `x87_alt.c` | alternative helper models `hx`, `p66`, `pfix` |
| `build_x87.cmd`, `run_x87.py`, `make_results.py`, `analyze_extra.py` | build (optionally against another `xrt_cpu.c`), full run, supporting analyses, results.json |
| `x87data.py`, `analyze.py`, `summarize_records.py` | readers, exact big-integer sin/cos reference, mismatch listings |
