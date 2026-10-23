# msvcr70 floor at the genuine level-loading boundary

The native x86 fixture loads only the sandbox copy of msvcr70.dll and calls its
export through a function pointer. The x64 fixture links the actual CRT adapter,
x87 helpers and guest memory, checks cdecl return/ESP and callee-saved registers,
and verifies the returned x87 value and surviving deeper stack values.

Run from the workspace root:

```powershell
cmd /d /c experiments\xrt\tests\floor_boundary\build.cmd
.venv/Scripts/python -I experiments/xrt/tests/floor_boundary/compare.py
.venv/Scripts/python -I experiments/xrt/tests/floor_boundary/compare.py --function ceil
```

The 73,920-case corpus for each function includes actual appRound/appCeil operands, both signs of zero,
subnormals, neighbours of integral boundaries, magnitudes through DBL_MAX,
infinities, quiet/signalling NaNs and payloads, plus seeded random binary64 values.
Every value runs with six initial status/stack configurations and both FLDCW
inputs 027f and 023f. Native readback is 027f for either: reserved bit 6 reads as
one. Full result bits, FCW, FSW (including TOP/condition/sticky flags), errno and
deeper stack values must match exactly. No differences are masked or waived.
An unsupported 037f control word remains an explicit fatal negative, rather than
a successful floor comparison. Each run has a fresh raw evidence directory.

The measured original client selects msvcr70's SSE2 floor path. The adapter uses
integer bit manipulation, with no host floor/libm call. It preserves signed zero,
rounds negative fractions down, preserves NaN sign/payload while quieting SNaN,
sets EDOM for NaNs, and models the measured x87 FLD side effects. Unmasked
exceptions, other precision/rounding controls, custom math-error handlers, an
already-full x87 stack and CRT SSE2-disabled fallback are outside this oracle.
They are not counted as passing behavior.

`graphics_reference.py --stop-after-floor 8` observes the original's first eight
appRound calls/returns, SSE2 versus x87 branch, operands, FCW/FSW/tag/registers and
MXCSR. It stops before world initialization and is not a gameplay reference.
The translated first operand/result/control word matches the original. Its
incoming x87 precision sticky bit is already absent (0100 versus native 0120),
and remains absent after floor (3900 versus 3920). That existing general x87
arithmetic-status limitation remains visible; the adapter is independently
tested with both clean and seeded sticky flags. Guest SIMD status is not modeled
by the runtime, which rejects guest SIMD instructions; native MXCSR observation
is retained rather than claimed as a translated state comparison.

The subsequently encountered `ceil` boundary (`Core.dll+171fa`, appCeil) uses
the same bit algorithm with the rounding direction reversed. Its independent
native comparison also has zero differences across 73,920 cases. In particular,
negative fractions between -1 and 0 return negative zero. `--stop-after-ceil 1`
records its original operand, return, branch and FPU state separately.
