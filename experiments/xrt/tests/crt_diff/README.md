# msvcr70 differential test (`crt_diff`)

Independent validation of the runtime's MSVCR70 adapters against the real `msvcr70.dll`:

- `runtime/xrt_fmt.c`: `xrt_woutput` / `xrt_wformat`, the msvcr70 `_woutput` engine over guest varargs, used by
  the `_vsnwprintf` and `wprintf` adapters;
- `runtime/hle_msvcr70.c`: `_vsnwprintf` (return value, truncation, terminator), `wprintf`, `wcslen wcscpy wcscat
  wcsncpy wcscmp wcsncmp _wcsicmp _wcsnicmp wcschr wcsrchr wcsstr _wcsupr _wtoi rand srand memmove`.

**Recovery validation (2026-10-22, compiler integration working tree).** The expanded suite runs 244,110 cases:
110 mismatches, 1,796 PENDING, exit 1; all 189 filesystem reference self-checks reproduce. This is a failing
component result, separate from the passing compiler acceptance. Exact runtime/harness/binary hashes, outcomes
and environment are in [results.json](results.json). The earlier narrow/wide/float measurements remain in that
file's historical sections.

| Open category | Cases differing | Finding |
|---|---:|---|
| `zrealloc` | 1 | `realloc(NULL,0)` succeeds, but `_msize` is 1 in msvcr70 and 0 in the adapter |
| `ffull` | 3 | last-error state on `_fullpath` buffer/path failures |
| `fff` | 64 | `_findfirst` last-error state (the recorded data match in the representative case) |
| `ffind` | 20 | directory enumeration last-error state |
| `fopen` | 22 | last-error state and `_iob` FILE descriptor fields on failure/close |

Every mismatch has a one-line reproducer under `repro/`; the runner continues to fail on them.
The four former NULL-destination `_vsnwprintf` mismatches are resolved: all 887 bounded wide cases, including
nine isolated errors, match. `_snprintf` and `_vsnprintf` still lack adapters, so their 1,796 cases remain
PENDING rather than passing. All other compared categories have zero mismatches, including the 31,175 new
`vsprintf` cases and the qsort comparator-call traces. No optional filesystem/time-zone expansion was used
to assert broader CRT compatibility or to delay the completed compiler milestone.

Earlier formatter-only result (2026-10-22): **178,398 cases, 0 mismatches** with the default corpus, and 281,898 cases, 0 mismatches
with the extended float corpus. The adapters as they were before this test (commit `edb955c`) disagreed with the
real DLL on 4,452 of the 172,412 cases they could run at all, and crashed or aborted on the rest. Details in
[results.json](results.json) and below.

**Narrow `sprintf` (added later the same day, gate F).** `A` lines run the `sprintf` adapter, which uses
`xrt_output` (msvcr70's narrow `_output`), against the real `sprintf`: 31,175 narrow cases. These are the
integer/float/pointer/`%n`/odd/fuzz/counted/truncation generators routed to narrow output, plus narrow-typed
`%s %S %hs %ls %c %C` cases, high-bit format bytes, wide text stopped by the C-locale `wctomb`, and 600 random
mixes of common conversions. Result: **0 mismatches** in both corpora (209,573 and 312,985 cases).

The first run found 17 mismatches, now fixed in `xrt_fmt.c`:
- **The case:** a narrow-string conversion (`%s`, `%hs`) whose precision is negative but not -1, which
  `%.*5s` with a `*` argument of -1 produces (-1*10+5).
- **The real narrow `_output`** counts narrow text with `while (i-- && *p)`, so it prints the whole string
  (including `(null)`).
- **The runtime** printed none of it, the rule the wide `_woutput` correctly uses for its narrow-string branch.
- Wide-string conversions in narrow output (`%S`, `%ls`, `%ws`) always matched.

`sprintf` has no bound. Each `A` case therefore first measures its output length on both sides (reference: the
real `_vsnprintf` into a 65,536-character buffer; candidate: `xrt_output` with a sink that refuses the 65,537th
character). Outputs of 65,536 characters or more are reported as `SKIP` on both sides; a disagreement about that
would itself be a mismatch.

## Bounded printf: `_snprintf`, `_vsnprintf`, `_vsnwprintf` (Editor.dll / ucc make phase)

**Scope.** These are the bounded printf functions the modules import:
- `_snprintf` and `_vsnprintf`: Engine.dll and GlmLib.dll;
- `_vsnwprintf`: Core.dll.

`_snwprintf` is imported by no module and is excluded. `vsprintf` and `swprintf` are unbounded and outside this
target. The reference is the real `msvcr70.dll`.

**Method.**
- **B lines** (narrow functions: format as bytes; `_vsnwprintf`: UTF-16). The function under test first measures
  the full length L with a 16,384-character capacity. Each case then runs at capacities 0, 1, 2, L-1, L, L+1, L+2
  and L+16, each in a fresh allocation of exactly that capacity.
  - Destination region: `[16 guard bytes 0xA5][capacity characters 0xCC][16 guard bytes 0x5A]`. The callee gets
    the address after the front guard.
  - Recorded per call: the return value, every byte of the region (both guards included, so an underrun,
    overrun, missing or extra terminator, or a write past the end all show), and the `%n` targets.
  - `_snprintf` receives its varargs on the stack after (buffer, count, format), which exercises the adapter's
    guest varargs marshalling. The `va_list` functions receive a pointer to the argument block.
  - String and character arguments are typed for the function's width: narrow `%s`, wide `%S %ls %ws %C %lc` in
    the narrow functions, and the reverse (`%S %hs %C %hc`) in `_vsnwprintf`.
  - Coverage: literals of 0-4097 characters, integers (flags, width/precision, `*`, `I64`), strings incl. NULL
    and 300 characters, cross-width text incl. characters above 0xFF, `%c`/`%C`, floats incl. INF/NaN and
    `%.600f`, `%n` before and after the cut-off, odd specifications, `%p`, Engine/GlmLib-style formats and 200
    random mixes per function.
- **K lines.** Explicit counts 0, 1, 2, 3, 0x3FFFFFFF, 0x40000000, 0x7FFFFFFF, 0x80000000, 0x80000001,
  0xC0000000, 0xC0000003, 0xFFFFFFFE, 0xFFFFFFFF, with a 64-character allocation and guards. Every output is at
  most 16 characters, so all inputs stay valid for the allocation whatever the CRT does with the count.
- **E lines** (intentional error behaviour, in `errors.txt`): NULL destination with various counts, and NULL
  format.
  - `compare.py` runs each in its own reference and candidate process. The candidate harness has no fault
    handler, so a fault ends its process.
  - A fault on both sides is a match, and both codes are recorded in `results.json`.

**PENDING.** The candidate looks its adapters up by export name in `xrt_hle_msvcr70[]`. A function with no
adapter yet (`_snprintf` and `_vsnprintf` as of `bfb8118`: unbound, fatal if called) gets `PENDING` on the
candidate side. Its reference results are still recorded, and it compares automatically once an adapter is
registered. PENDING is never counted as passed: `compare.py` exits 3 when cases are pending and nothing
mismatched.

**Historical results**, runtime commit `bfb8118` (runtime sources clean; provenance with source and binary SHA-256 in
`results.json`):
- Default corpus (seed 20261022): 212,250 cases plus 27 isolated, **4 mismatches**, **1,796 PENDING**.
- Extended corpus (seed 7): 315,662 cases, the same 4 mismatches and 1,796 PENDING.

| Function | Cases | Result |
|---|---:|---|
| `_vsnwprintf` (B, K) | 878 | 0 mismatches: whole region including both guards byte-identical, at every capacity and count |
| `_vsnwprintf` (E, isolated) | 9 | **4 mismatches (open, reported to the main session)**. With a NULL destination and count 0, 0x7FFFFFFF or 0xFFFFFFFF, msvcr70 returns the full length (3 for `L"abc"`, 5 for `%d` of 12345) and the adapter returns -1. NULL with count 1 or 16, and a NULL format, fault on both sides. Reproducers: `repro/bvsnwerr.{1,2,5,6}.txt` |
| `_snprintf`, `_vsnprintf` (B, K, E) | 1,796 | PENDING: no runtime adapter. Reference recorded |

**Reference behaviour seen in the E lines**, the contract a future adapter must reproduce:
- **Narrow `_snprintf`/`_vsnprintf` with a NULL destination:** return the full length for every count (0, 1, 16,
  0x7FFFFFFF, 0xFFFFFFFF) and never fault.
- **`_vsnwprintf` with a NULL destination:** returns the length when count 0, or `count*2` read as an int, is
  not positive. Otherwise it faults at the terminator store.
- **A NULL format** faults in all three functions.

This fits msvcr70's string stream writing nothing while its base is NULL (it only counts).

Each reproducer in `repro/` is a one-line corpus with both results in comment lines (the drivers skip `#` lines).
Rerun one with `ref.exe <dll> <file> out.txt` and `cand.exe <file> out.txt`, in their own processes for `E` lines.
`compare.py` rewrites `repro/` on every run.

## CRT dependencies of `ucc make` (V, T, Q, Z, X, F lines)

**Scope.** The main session traced the original `ucc make -ini=XrtCompileProbe.ini` with entries for Editor.dll
and Window.dll. These lines cover the msvcr70 functions that trace reaches.

Reached without a runtime adapter at the time of the trace:
- GlmLib.dll: `vsprintf`, `strrchr`, `strncpy`, `fopen`, `fclose`, `_getcwd`, `_fullpath`, `_findfirst`, `_findnext`,
  `_findclose`, `_errno`, `_chdir`;
- Editor.dll: `_set_se_translator`.

Newly reached, with an adapter already:
- `qsort` (Core.dll);
- `toupper`, `atoi`, `_stricmp` (GlmLib.dll);
- `_msize` with `malloc`/`realloc`/`free`.

`strchr` is included as GlmLib's partner of `strrchr`. `swscanf`, `swprintf`, `_snprintf` and `_vsnprintf` are not
reached on this path, so no new lines were added for them. The test cases follow what GlmLib actually does, read from
its call sites:
- `vsprintf(buf ? buf : static, fmt, va)` at GlmLib+3e80;
- `strrchr(s, '.')` and `strrchr(s, '\\')`;
- `_getcwd(buf, 260)` and `_fullpath(buf, path, 260)`;
- `_chdir` followed by a switch on errno 2/13/17;
- an existence check at GlmLib+0x72d30 that reads `attrib`, `time_write` and `size`;
- the `_findfirst`/`_findnext`/`_findclose` listing loop of DISK_FindFiles at GlmLib+0x73760;
- `fopen` with "rb" and "wb", then `fclose`.

**Method.** All lines use the same arena, guards and PENDING rule as the printf lines.
- **V `vsprintf`.** The narrow printf generators (integers, floats, pointers, `%n`, odd specifications, counted
  strings, truncation, narrow-typed strings, narrow text and mixes) are routed through `vsprintf` with a `va_list`,
  about 31,000 cases. Each case records the whole buffer up to the terminator plus 8 guard bytes, and the `%n` targets.
- **T string and character functions.** Strings are placed at byte offsets 0-15 inside guarded regions (this
  exercises the alignment paths of msvcr70's assembly routines). Each case records the whole region and any returned
  pointer as a buffer-relative offset.
  - `strrchr`/`strchr`: path-like strings, with character arguments including 0, high-bit values (both sign
    extensions) and values above 0xFF.
  - `strncpy`: n = 0..4, len-1..len+17, 260 and 261, into destinations of exactly n bytes and of n+7 bytes (which
    shows where the zero padding stops).
  - `_stricmp`: exact return values, including the characters between 'Z' and 'a', high bytes and long strings.
  - `atoi`: whitespace by the C-locale table, signs, overflow, and every byte as a leading character.
  - `toupper`: -1..255 and values outside that range.
- **Q `qsort`.** Element widths 0, 1, 3, 4, 8, 12 and 64; 0 to 1,000 elements; sorted, reversed, equal, random,
  few-distinct, organ-pipe, sawtooth and almost-sorted inputs.
  - Comparators: int32, a wrapping difference, descending, first byte only (the rest of each element is a unique tag,
    so the order of equal keys is visible), and constant 0.
  - Recorded: the array with guards, the number of comparator calls, a hash of the full sequence of (a, b) element
    offsets, and the first 256 pairs. So the test fixes the algorithm itself, not only a sorted result.
  - The reference passes native comparators. The candidate's adapter calls guest code through `xrt_call_guest`; the
    harness answers only its own sentinel addresses and is fatal for anything else.
- **Z heap.** `malloc` of 0 to 1 MiB+1 bytes, `realloc` growth and shrinkage, `realloc` from NULL and to 0, and 40
  random sequences.
  - Every block is filled with a pattern, and `realloc` checks every kept byte.
  - Recorded: success, whether `realloc` kept the content, and `_msize` values. Addresses are never recorded.
  - `_msize` of a slot left empty by a NULL result is recorded as `s:null` and never called, since that would be an
    invalid input.
- **X `_set_se_translator`.** Sequences of values, each line in a fresh process (the translator is per-thread
  state), recording each returned previous value. No structured exception is raised, so no translator runs.
- **F file system.** Sequences of `_getcwd`, `_fullpath`, `_chdir`, `_findfirst` (existence check), the
  `_findfirst`/`_findnext`/`_findclose` listing loop and `fopen`/`fclose`, with errno read through `_errno` after
  every call. Each line runs in a fresh pair of processes whose current directory is a scratch tree,
  `experiments/xrt/build/crt_diff/fs/root`.
  - **Tree contents** (defined in `gen_corpus.py` `FS_*`): attributes R/H/S/normal, a Latin-1 name, a long name with
    spaces, read-only and hidden directories, and an empty directory.
  - **Tree times:** creation and write times are fixed historical values covering the `time_t` limits (1601, 1969,
    the first local hour of 1970, 2038-01-19 03:14:07/08Z, 2099) and US Eastern DST transitions (2006 and 2026 rules,
    the ambiguous hour of 2026-11-01, a leap day, a new year).
  - **Rebuild:** `compare.py` rebuilds the tree before every process: it deletes the old tree, writes every file,
    sets times bottom-up with `SetFileTime` (root and its parent included), then sets attributes.
  - **Access times** are the run's start time. NTFS refreshes a last-access time that is more than an hour old when
    the file is opened, so a historical access time would not stay fixed.
  - **Snapshot:** after each process, `compare.py` takes a snapshot of the tree (names, attributes, sizes, content
    hashes) and compares it too, which shows what "wb" created or truncated.
  - **Self-check:** the reference runs every F line a second time later in the run. A reference that does not
    reproduce itself fails the case.
  - **Recorded values:** after every call, the thread's Win32 last error (`le=`, set to 0x5555 just before the
    call, so a call that never sets it shows) and errno, read through `_errno`.
    - `_finddata_t` (280 bytes: `attrib`, `time_create`, `time_access`, `time_write`, `size`, `name[260]`) is
      recorded whole, pre-filled with 0xCC, guarded, and reused across a listing as GlmLib does.
    - Find handles are recorded only as valid/-1.
    - `fopen` records which `_iob` entry it returned. `fopen` and `fclose` both record the `FILE` records
      `_iob[3..5]` (`_flag`, `_file`, `_cnt`, `_charbuf`, `_bufsiz`; pointers as 0/P).
  - **Partial output:** both drivers flush the result line before every call. A process that dies in a call leaves
    the ops before it.
  - **Safety:** the harness refuses F lines in a directory without the tree's marker file.
  - **Sandbox root:** the candidate uses the tree's parent as its sandbox root, the same shape as a run, whose
    current directory `System` sits one level below the sandbox.
  - **Environment:** every process (the generator, both sides, every isolated run) runs without `TZ` and
    `__MSVCRT_HEAP_SELECT`. So the CRT uses the system time zone and its default heap (the system heap; the variable
    would select a small-block heap and change `_msize`).
  - **Recorded run conditions** (`results.json`, `fs`): the system time zone from `GetTimeZoneInformation` (names,
    biases, whether DST was in effect at the start, and whether that changed during the run), and the ANSI code page.
- **Outcomes of isolated lines.**
  - A reference fault matches only a candidate that dies with the same exception code, after the same partial
    output (and, for F lines, the same tree).
  - A candidate `xrt_fatal` is its own outcome, `fatal`. A harness stub or a harness exit is `harness-error`.
    Neither ever matches a reference fault.
- **Rerunning a case.** `compare.py --repro repro\<id>.txt` (or `--repro <id>`) reruns one case on both sides the
  way the full run ran it:
  - for an F line, the tree is rebuilt with the reproducer's `t0` before each process;
  - the reference runs twice;
  - it prints both outcomes, the decoded F results and the tree differences.
- **Narrow routes.** The wide-printf generators type a `%S` argument as a narrow string, which is what wide printf's
  `%S` reads. In narrow printf `%S` reads a wide string, so the A and V routes give those arguments a wide string with
  the same characters (`widen_narrow_args`).
  - This corrected five pre-existing A lines: `noddB.2`, `noddB.16`, `noddB.17`, `noddB.19`, `ntrunc.7`. Before
    the correction, their `%S` scanned past the narrow string's allocation; no result depended on it.
- **Candidate build.** The candidate links `hle_kernel32.c`, for the handle table and the sandbox guard the
  file-system adapters use, and `xrt_msvcr70img.c`, for `_dosmaperr`'s table read from the DLL image.
  - The image is loaded once from `sandbox_ref/hellofull/System/msvcr70.dll`, the same file as the reference, and
    SHA-checked against the DLL the runtime was translated from.
  - It also links the translated `_CIpow` core (`gen/msvcr70/pow_sse2.c`, generated by `build_xrt.cmd`, never
    committed).
  - The rest of the runtime is replaced by `STUB_K32DEPS` stubs, which are fatal for threads, modules, the baton and
    diagnostics. The guest last error is the TEB word.

<!-- results of the committed runtime run go here -->

## Files

| File | What |
|---|---|
| `gen_corpus.py` | deterministic corpus generator (seeded); writes `corpus.txt` (line format in its docstring) |
| `crt_diff_core.h` | shared driver: parses the corpus, places strings/argument blocks in the test arena, runs each case, writes results |
| `ref.c` | reference side, x86: `LoadLibrary` of the sandbox `msvcr70.dll`, functions via `GetProcAddress`, every call under SEH |
| `cand.c` | candidate side, x64: links `runtime/xrt_fmt.c`, `hle_msvcr70.c`, `xrt_mem.c`, `hle_kernel32.c`, `xrt_msvcr70img.c` (stubs for the rest); calls the adapters from `xrt_hle_msvcr70[]`; optional third argument: the sandbox holding `System\msvcr70.dll` |
| `compare.py` | generates the corpus, runs both sides, compares, runs E/X/F lines one process each (F in the rebuilt scratch tree, reference twice), prints a summary, optionally writes JSON |
| `i10_model.py` | Python model of msvcr70's double-to-digits code (`__dtold` + `$I10_OUTPUT`); generates the power-of-ten tables used in `xrt_fmt.c` |
| `build.cmd` | builds `ref.exe` (x86) and `cand.exe` (x64) into `experiments/xrt/build/crt_diff/`; deletes both first and fails unless both exist afterwards |
| `results.json` | summary of the last runs (default, extended, and the before-fix measurement), with provenance: commit, dirty files, SHA-256 of the runtime sources and of `ref.exe`/`cand.exe`, commands, seed, counts, adapters present, exclusions |
| `repro/` | one reproducer per mismatch of the latest run (one-line corpus plus both results) |

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

`compare.py` exits 0 when every case was compared and matched, 1 on any mismatch, and 3 when nothing mismatched
but some cases are PENDING. The default run takes about 30 s. `compare.py --json` writes only the
default-run sections; the others were merged in by hand from one-off runs:
- `extended_run`: the extended command above, now including the narrow cases;
- `extended_run_wide_only`: the same command before the narrow cases existed;
- `narrow_sprintf`: the narrow summary;
- `before_fix`: `cand.c` built against the commit `edb955c` versions of `xrt_fmt.c` and `hle_msvcr70.c`
  (`git show`), run on the default corpus minus the cases that abort or crash those versions.

Build products, the corpus and the raw result files (about 70 MB each) stay in `experiments/xrt/build/crt_diff/` (git-ignored). The DLL is
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
