# msvcr70 differential test (`crt_diff`)

Independent validation of the runtime's MSVCR70 adapters against the real `msvcr70.dll`:

- `runtime/xrt_fmt.c`: `xrt_woutput` / `xrt_wformat`, the msvcr70 `_woutput` engine over guest varargs, used by
  the `_vsnwprintf` and `wprintf` adapters;
- `runtime/hle_msvcr70.c`: `_vsnwprintf` (return value, truncation, terminator), `wprintf`, `wcslen wcscpy wcscat
  wcsncpy wcscmp wcsncmp _wcsicmp _wcsnicmp wcschr wcsrchr wcsstr _wcsupr _wtoi rand srand memmove`.

Result (2026-10-22): **178,398 cases, 0 mismatches** with the default corpus, and 281,898 cases, 0 mismatches
with the extended float corpus. The adapters as they were before this test (commit `edb955c`) disagreed with the
real DLL on 4,452 of the 172,412 cases they could run at all, and crashed or aborted on the rest. Details in
[results.json](results.json) and below.

## Files

| File | What |
|---|---|
| `gen_corpus.py` | deterministic corpus generator (seeded); writes `corpus.txt` (line format in its docstring) |
| `crt_diff_core.h` | shared driver: parses the corpus, places strings/argument blocks in the test arena, runs each case, writes results |
| `ref.c` | reference side, x86: `LoadLibrary` of the sandbox `msvcr70.dll`, functions via `GetProcAddress`, every call under SEH |
| `cand.c` | candidate side, x64: links `runtime/xrt_fmt.c`, `hle_msvcr70.c`, `xrt_mem.c` (stubs for the rest); calls the adapters from `xrt_hle_msvcr70[]` |
| `compare.py` | generates the corpus, runs both sides, compares, prints a summary, optionally writes JSON |
| `i10_model.py` | Python model of msvcr70's double-to-digits code (`__dtold` + `$I10_OUTPUT`); generates the power-of-ten tables used in `xrt_fmt.c` |
| `build.cmd` | builds `ref.exe` (x86) and `cand.exe` (x64) into `experiments/xrt/build/crt_diff/` |
| `results.json` | summary of the last runs (default, extended, and the before-fix measurement) |

## How to run

From the workspace root:

```bat
experiments\xrt\tests\crt_diff\build.cmd
.venv\Scripts\python.exe -I experiments\xrt\tests\crt_diff\compare.py --json experiments\xrt\tests\crt_diff\results.json
rem extended float corpus (10x random doubles, ties, near-ties):
.venv\Scripts\python.exe -I experiments\xrt\tests\crt_diff\compare.py --i10 60000 --seed 7
rem check that the generated power-of-ten tables equal the ones in the DLL (reads it, stores nothing):
.venv\Scripts\python.exe -I experiments\xrt\tests\crt_diff\i10_model.py --check-dll sandbox_ref\hellofull\System\msvcr70.dll
```

`compare.py` exits 0 only when every case matches. The default run takes about 30 s. The `extended_run` and
`before_fix` sections of `results.json` were merged in from one-off runs: the extended command above, and
`cand.c` built against the commit `edb955c` versions of `xrt_fmt.c` and `hle_msvcr70.c` (`git show`), run on
the default corpus minus the cases that abort or crash those versions. Build products, the corpus
and the raw result files (about 70 MB each) stay in `experiments/xrt/build/crt_diff/` (git-ignored). The DLL is
only loaded from the read-only sandbox copy `sandbox_ref/hellofull/System/msvcr70.dll`; no game code runs.

## Method

- **Same inputs on both sides.** Each corpus line names a function, a format string and a typed argument list
  (int32, int64, double bits, wide/narrow string, NULL, `%n` slot, counted string). Each side builds the packed
  x86 argument block itself (strings in its own memory: real addresses on the reference side, guest addresses on
  the candidate side). The reference calls `_vsnwprintf` with a hand-built `va_list` (a pointer to the block) and
  `wprintf` with the block copied onto the stack as a by-value structure. The candidate calls the adapters with a
  `CPU` whose `ESP` points at `[return address][args...]` in guest memory, reads `EAX`, and checks the cdecl
  discipline (popped return address, `ESP`).
- **`_vsnwprintf`**: every case runs once with an 8192-character buffer, then with counts 0, L-1, L and L+1
  (L = full length): return value, buffer contents around the end including 8 sentinel characters after the
  count (terminator present or not, no overrun), and all `%n` targets after each call. `count` cases use counts
  whose byte size `count*2` wraps (0x40000000, 0x80000001, 0xC0000003, ...). The candidate also checks that a
  direct `xrt_wformat` call gives the same text as the adapter.
- **`wprintf`**: both sides write to their stdout redirected to a file; the result records the return value,
  `%n` targets and the byte range written (`\n` becomes `\r\n`, characters above 0xFF are not written).
- **String functions**: arguments in buffers with sentinels; results record the return value (pointers as
  argument-relative offsets) and every argument buffer afterwards. `rand` sequences start from the initial seed
  and after `srand` of edge seeds.

## Coverage (default corpus, seed 20261022)

| Category | Cases | Content |
|---|---:|---|
| `int` | 9,504 | every flag subset of `- + space # 0` plus odd orders/duplicates, x `d i u o x X`, x sizes `'' h l w I I32 I64 L ll hh N F lh hl I64h hI64 I32I64 I64I32`, widths incl. `*` (negative, 0, -0x7FFFFFFF), precisions incl. `.`, `.0`, `.40`, `.513`, `.600`, `.*` (negative, 600); 4 values each from int32/int64 edge cases |
| `intsweep` | 2,592 | width x precision (up to `.1000`) x flag sweep |
| `flt` | 6,460 | flags x `e E f g G` x 17 precisions (incl. `.*`, `.600`) x sizes x 3 special values each |
| `fltsweep` | 4,800 | 119 special values (0, -0.0, denormals, 1e-320, 1e308, DBL_MAX, 0.1, 0.125, 0.5/1.5/2.5, 9.9999, 1e21, 2^53+1, ties, +-INF, quiet/signalling NaN, the x86 indefinite 0xFFF8000000000000, ...) at every precision with and without `#` |
| `fltfix` | 31 | the specific checks requested (`%.2f` of 0.125, `%.0f` of 0.5/1.5/2.5, `%f` of 1e21, `%.20f`, `%.512f` of 1e308, ...) |
| `i10` / `fltrand` | 6,000 / 1,500 | 48,000 random doubles at `%.16e` (all 17 digits the CRT produces) and 6,000 at random formats |
| `ties` / `nearties` | 2,000 / 2,000 | 16,000 values with exactly 18 significant digits ending in 5, and 16,000 whose 18th digit is 4 or 5 followed by more digits |
| `str` / `chr` / `ptr` | 1,152 / 576 / 192 | `%s %S %hs %ls %ws %hS %lS %wS ...`, `%c %C %hc %lc %wc ...`, `%p` with sizes; NULL, empty, precision-truncated, non-ASCII and > 0xFF characters, lone surrogate, U+FFFF, narrow bytes 0x80-0xFF |
| `n` | 27 | `%n %hn %ln %I64n`, including `%n` after the output no longer fits |
| `odd` / `oddB` / `fuzz` | 268 / 20 / 4,000 | invalid and odd specifications (`%y`, `%5y`, `%I`, `%Iq`, `%I6`, trailing `%`, `%%`, `%-+ #010.3d`, `%5*d`, `%.*5d`, `%I64I64d`, ...), the `B` type after each kind of conversion, negative string precisions, and 4,000 random specifications |
| `cstr` | 104 | `%Z %wZ %hZ ...` counted strings |
| `trunc` / `count` | 48 / 4 | truncation boundaries, outputs > 0xFF, explicit counts with wrapping byte counts |
| `wprintf` | 182 | stdout output incl. characters > 0xFF in literals, `%s`, `%c` and padded fields |
| string functions | 6,108 | 31 strings (case variants, `@[`{`, Latin-1, > 0xFF, surrogate) pairwise for the comparisons, all `n` boundaries for `wcsncpy`/`wcsncmp`/`_wcsnicmp`, `wcschr`/`wcsrchr` with high bits set in the character argument |
| `wtoi` / `wtoiall` | 55 / 131,070 | numeric edge strings (overflow, signs, long leading whitespace, Unicode digits/spaces), and every UTF-16 code unit as `c5` and `1c` |
| `memmove` / `rand` | 11 / 10 | overlapping moves both ways; 40 values from the initial seed, 60 after each of 8 seeds, 2,000 more |

The extended run (`--i10 60000 --seed 7`) has 480,000 random doubles at `%.16e`, 60,000 at random formats,
160,000 exact ties and 160,000 near-ties.

## What the real msvcr70 does (and the runtime now does too)

Each item was found as a mismatch, confirmed against the DLL, and fixed in `runtime/xrt_fmt.c` or
`runtime/hle_msvcr70.c`. Before-fix counts are from the commit `edb955c` adapters on the same corpus.

1. **Digit generation** (`i10`, `ties`, `fltrand`, `flt`, `fltsweep`: about 2,700 cases). msvcr70 does not round correctly: it
   produces 17 digits with `$I10_OUTPUT` (80/96-bit arithmetic with power-of-ten tables and a truncated
   multiplication) rounded half-up on an 18th computed digit. Exact ties at the 18th digit usually come out
   rounded down (2251799813685247.75 prints `2.2517998136852477e+015`, not `...478`). Ported bit-exactly
   (`ld12mul`, `multtenpow12`, tables generated from exact arithmetic by `i10_model.py` and checked equal to the
   DLL's), together with `_fptostr`, `_cftoe2`, `_cftof2` and `_cftog` (incl. its rounding-expansion chop).
2. **-0.0** prints without a sign (`__dtold` drops it): `0.000000e+000`.
3. **Integer precision is capped at 512** (`%.513d` printed 513 digits).
4. **Parsing is the CRT's character-class state machine**: `%5*d` and `%.5*d` print `*d`, `%**d` prints `*d`.
5. **`B` is a type character with no conversion**: it prints the previous conversion's text again (`%d%B` of 42
   gives `4242`; `%s%B` re-reads the wide string as narrow bytes).
6. **`%Z` counted strings** were fatal; now implemented (narrow output stops at a NUL byte, `%wZ` uses
   Length/2 characters, NULL pointer or buffer prints `(null)`).
7. **Output counting (`charsout`)**: a failed write makes the count -1, a later successful write counts up from
   there, padding and wide text stop at a failure, the narrow-text loop does not, and the format loop stops once
   the count is negative. Consequences:
   - `_vsnwprintf` stops processing at the first character that does not fit, so a later `%n` is not stored
     (the old adapter formatted everything and stored it);
   - U+FFFF is stored but reported as a failure (`fputwc` returns the character, which equals `WEOF`): the
     result is -1, or a recovered count when padding follows (`[%-7s|...` with `L"￿"`);
   - `wprintf` of a character above 0xFF does not write it and continues with what follows in the same field
     (`x%-5sy` with `L"Ā"` writes `x    y` and returns 5; the old adapter stopped and returned -1).
8. **`_vsnwprintf` byte count**: the stream counter is `count*2` in 32 bits, tested by sign. Counts 0x40000000
   and 0xC0000000 behave as unlimited, 0x7FFFFFFF and 0xFFFFFFFF as 0, 0x80000001 as 1; 0xC0000003 writes
   `45|str` after three failed characters. The terminator is written as two single bytes only while they fit.
9. **Unbounded padding** (`%*d` with 0x7FFFFFFF) made the old formatter build a 2-billion-character string and
   abort with "host out of memory"; the CRT stops at the end of the buffer and returns -1.
10. **Buffer overflow**: `%.512f` of values from about 1e86 up overflowed `char d[600]` in the old `cfltcvt`
    (stack corruption, then a crash). Buffers are now sized for the largest output (825 bytes).
11. **`_wtoi`** is msvcr70's wide parser, not `WideCharToMultiByte` + `atol` of 19 characters: `iswspace`
    (U+0009-U+000D, U+0020, U+00A0 below U+0100; `GetStringTypeW` `C1_SPACE` above, U+FFFF excluded), optional
    sign, then digits from `_wchartodigit` (ASCII, fullwidth and 16 other Unicode decimal-digit blocks such as
    U+0660). `_wtoi(L"\x0663")` is 3; 20 spaces before a digit are skipped.

Code-level fixes with no observable difference in this corpus: signed overflow in `width = -width`
(INT_MIN), `-l` for INT64_MIN and width/precision digit accumulation now use unsigned arithmetic.

The string functions, `rand`/`srand`, `memmove`, `%p`, all flag/width/precision handling of `d i u o x X`, `%s`,
`%c`, and the INF/NaN spellings (`1.#INF`, `1.#QNAN`, `1.#SNAN`, `-1.#IND`, `1.$` rounding) already matched.

## Not covered (undefined behaviour or not reproducible)

- `%B` before any conversion: the CRT prints an uninitialised `textlen`/`text` (undefined; the runtime prints
  only the padding, which is what was observed). `%B` after a float with precision > 163: the CRT re-reads its
  freed heap buffer (undefined).
- `%Z` with a negative `Length` (reads past the buffer until a NUL byte); `%s`/`%n`/`%Z` with invalid pointers
  (both sides fault).
- `_vsnwprintf` counts larger than the real buffer when the output would overrun it; `wcscpy`/`wcscat` with
  overlapping arguments (undefined in C).
- Floating-point precision above 163 uses a heap buffer in the CRT; if that allocation fails it continues with
  precision 163. The runtime never fails this allocation.
- `wprintf` padding of about 2^31 characters (would write 2 GB to stdout).
- Locales other than "C", multibyte lead bytes, `rand` on several threads (per-thread state; one thread tested).
