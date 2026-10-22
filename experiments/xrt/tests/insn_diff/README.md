# Differential instruction test: native x86 vs lifted C (`insn_diff`)

Independent validation of the instruction semantics of `tools/xrt/xlift.py` (and of the helpers the lifted code
calls: the flag/x87 inlines in `runtime/xrt.h` and the x87 functions in `runtime/xrt_cpu.c`). Every
non-control-flow instruction form that occurs in `Core.dll` and `UCC.exe` is executed on the real CPU (32-bit
process) and as lifted C (compiled for x64 with the production flags), from identical input states; all
architecturally defined outputs are compared.

Measured on an Intel Core i7-14700K, Windows 11 (WOW64), Visual Studio 18 (MSVC x86 and x64), capstone 5.0.7, 2026-10-22.

**Current status (later on 2026-10-22).** The numbers in the sections below are from the first run, against the
original trig helpers; that run is kept as `results.before.json`. After the runtime adopted pi66 argument reduction
and the SDM NaN/inf rules (`xrt_cpu.c` a39bf8c8), and the lifter began routing `fninit` through `xrt_fldcw`, the
results are:
- default seed: 432,304 cases, 0 failures (`results.json`);
- seed 7 ×3: 1,293,592 cases, 0 failures (`results.seed7x3.json`).

The fsin/fcos/fptan NaN/inf failures are gone: the transcendental ULP histogram is 0/1/2/≥3 = 8174/411/13/0, with no
inf/nan cases. `fninit` now stops the lifted code by design and is counted as `fatal-by-design` (1,111 cases, 791
before). `mutation_check.py`: 13/13 still killed.

## How to run

From the workspace root (needs `sandbox_ref\hellofull\System\Core.dll` and `UCC.exe`, Visual Studio 18 with the
x86/x64 C++ tools and `ml.exe`, and `.venv` with capstone/pefile):

```bat
rem everything: census, snippets + vectors + lifted C, build both harnesses, run both, compare (about 1 min)
.venv\Scripts\python.exe -I experiments\xrt\tests\insn_diff\run.py
rem another vector set, 3x as many vectors per snippet (about 2 min)
.venv\Scripts\python.exe -I experiments\xrt\tests\insn_diff\run.py --seed 7 --scale 3
rem sensitivity check: injects 13 plausible lifter bugs into the generated C, each must be detected (about 4 min)
.venv\Scripts\python.exe -I experiments\xrt\tests\insn_diff\mutation_check.py
rem lifter unit tests (include the regression test for the bug found here)
.venv\Scripts\python.exe -I -m unittest discover -s tools\xrt\tests
```

`run.py` exits 0 when no failure is left that is not attributed (see `ATTRIBUTION` in `compare.py`). It writes
`results.json` (this directory, machine-readable summary) and, under `experiments\xrt\build\insn_diff\`
(git-ignored), `mismatches.txt` (up to 4 annotated examples per form and category: snippet bytes, inputs, both
outputs), `census.json`, `snippets.json`, `cases.bin`/`expect.bin`, `id_lifted.c` and the two executables.

| File | Role |
|---|---|
| `census.py` | runs `tools/xrt/discover.py`'s `Module(path).run()` over Core.dll and UCC.exe and groups every instruction of every discovered function into forms and encoding classes |
| `gen.py` | synthesizes snippets per encoding class, re-disassembles each one, generates input vectors, lifts the snippets with `Lifter.lift_insn`, writes cases and the lifted C |
| `extended.py` | example encodings of forms outside the census that the lifter implements (reported separately) and of forms it leaves as traps (listed only) |
| `insn_diff.h` | input/output record layouts and the window fill shared by both harnesses |
| `native_run.asm`, `native_x86.c` | 32-bit harness: loads GPRs/EFLAGS/x87 state, jumps into the snippet, captures everything (FNSAVE for x87) |
| `lifted_x64.c` | 64-bit harness: same cases through the generated C on `runtime/xrt_cpu.c` + `xrt_mem.c` (4 GB guest reservation) |
| `compare.py` | compares only defined outputs, classifies differences, writes `results.json` |
| `run.py`, `build.cmd`, `build_lifted.cmd`, `mutation_check.py` | driver, builds, sensitivity check |

No bytes of the game binaries are written anywhere: snippets are synthesized from opcode classes, and `census.json`
holds mnemonics, opcode classes and counts only. Only the census reads the modules (as data); no code of Core.dll
or UCC.exe is executed by this test.

## Method

**Census.** 113,695 non-control-flow instructions (Core.dll + UCC.exe; excluded: jcc/jmp/call/ret 25,114, MMX/SSE
102 (traps by design), rdtsc 33, cpuid 1) in **203 forms** = (mnemonic incl. rep/lock prefix, operand kinds r8/r16/r32,
imm, m8..m64, st0/sti) and **294 encoding classes** (operand-size/rep prefix, opcode bytes, ModRM reg extension for
group opcodes, full ModRM for x87 register forms, immediate width, moffs). Memory operands use 33 addressing-mode
shapes; 2,218 use `fs:` (all `fs:[0]`, SEH registration). The 298 `fnstsw ax` are followed by `test ah, 0x44/1/0x41/5`
only (C0/C2/C3; never C1 or AL).

**Snippets** keep the census encoding class and choose registers and addressing here; each is re-disassembled and
must reproduce the census form key and encoding class exactly. Variants per class: random distinct registers,
same register for both operands, high-byte registers, operand = eax/edx for mul/div, operand = ecx for shifts by cl,
`esp` as operand where the census has it, and for memory forms `[base+disp8]`, `[base+index*scale+disp32]`,
`[disp32]`, `[esp+disp8]` and register-operand-aliases-the-base. Immediates: 0, 1, sign boundaries, all-ones and
random values; shift/rotate counts 0..33 and 0x3F/0x40/0x80/0xFF. Extra snippets: all 16 `setcc` conditions (the
condition table is shared with jcc), a 34-shape addressing-mode matrix through `lea`/`mov`, `fs:` reads and writes,
and every x87 compare followed by `fnstsw ax; test ah, mask` with the census masks.

**Vectors** (320 per snippet, 40-48 per immediate variant, 400 for division; at least 320 per form): all-pairs of
edge values (0, 1, 0x7F, 0x80, 0xFF, 0x7FFF, 0x8000, 0xFFFF, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, ...) then random
values (uniform, small signed, powers of two +-1); random upper bits around 8/16-bit operands; random
CF/PF/AF/ZF/SF/DF/OF with carry-in 0 and 1 for adc/sbb; cl 0..33 then random 0..255; string ops with DF 0/1, counts
0..5 then up to 24, overlapping `movs` (edi = esi +- k*size), `cmps` buffers made equal for 0..8 bytes; division
with quotient-valid, zero-divisor, overflow (incl. INT_MIN/-1) and random operands, the #DE outcome predicted from
the SDM per case; x87 stacks of the needed depth (never over/underflowing) with 0, -0, +-1, +-0.5, 1.5, +-2.5,
3.5, values at the int16/int32/int64 conversion limits (+-0.5), 2^52/2^53/2^63, double max/min/denormals,
+-inf, QNaNs, random values; float/int memory operands incl. float denormals, SNaN/QNaN; transcendental domains
(trig in [-10,10] and [-1e6,1e6] plus +-2^63, f2xm1 in [-1,1], fyl2x x>0, fscale integer and fractional scales).

**Native side.** A 64 KB scratch region at 0x20000000 (data window 0x20008000 + 0x200, stack window around
ESP = 0x2000C000) is allocated at the same address on both sides, so pointer values need no relocation. The asm
loads FCW 0x027F and the x87 stack, EFLAGS (popfd), all eight GPRs including ESP, jumps to the snippet, which ends
with `jmp [g_back]`; then it stores all GPRs, EFLAGS and the FNSAVE image (FCW, FSW with TOP, tag word, ST(0)..ST(7)
converted from 80-bit to double with an exactness flag). #DE inside a snippet is caught with a vectored handler that
resumes at a recovery label (frame-based SEH cannot be used while ESP points into the scratch region). The TEB
fields a snippet may write (ExceptionList, ArbitraryUserPointer) are saved and restored around every case; the
lifted side gets the native TEB snapshot at the same guest address as `c->fs_base`.

**Lifted side.** `gen.py` lifts the same bytes with `Lifter(stub).lift_insn(ins, None)` (stub module: empty IAT)
into `void s_N(CPU*)`; `id_lifted.c` is compiled with the flags `build_xrt.cmd` uses for `gen\*.c`
(`/O1 /fp:strict`) and linked with `runtime\xrt_cpu.c` and `xrt_mem.c` (`/O2 /fp:strict`). `xrt_div0`, `xrt_trap`,
`xrt_fatal`, `xrt_badret`, `xrt_icall`, `xrt_ijmp` record the outcome and longjmp back; `xrt_preempt`/`xrt_log`
are no-ops. The ABI (`CPU`, `f_<va>(CPU*)`, `xrt.h` macros) is used unchanged.

**What is compared** (only architecturally defined outputs, Intel SDM):

| output | rule |
|---|---|
| status | both complete, or both #DE (native `#DE` exception vs. lifted `xrt_div0`); any other combination fails |
| GPRs | all 8, all 32 bits (partial-register writes must preserve the rest) |
| memory | hashes of the data and stack windows and of the writable TEB fields (+ log of changed bytes) |
| EFLAGS | CF PF ZF SF OF DF, AF never (not modelled; no instruction in these modules reads it). Masked as undefined: SF/ZF/PF after mul/imul; CF/OF/SF/ZF/PF after div/idiv; OF after shifts/rotates/shld/shrd with masked count != 1; CF after shl/shr with count >= operand width. Count 0 = all flags must be preserved |
| x87 | TOP always; FCW; C0/C2/C3 only after fcom/fucom/ficom/ftst/fninit (C2 also after fsin/fcos/fptan); ST(i) only for registers the hardware tags as valid, bit-exact for basic arithmetic/loads/stores/conversions, ULP distance for fsin/fcos/fptan/fpatan/fyl2x/f2xm1 |
| `fnstsw ax` | AX upper 16 bits, TOP and (after a compare) C0/C2/C3; the other bits are counted as `fnstsw-unmodelled` |

Differences the model deliberately does not represent are counted in separate "model" categories, never as
failures: `x87-not-a-double` (the hardware register holds a value that is not a double: 64-bit significand or
exponent beyond double range), `x87-transcendental`, `x87-nan-payload`, `x87-c1`, `x87-exception-flags`,
`fnstsw-unmodelled`, `fatal-by-design` (fldcw to a state outside the model).

## Results

Seed 20261022, scale 1: **2,627 snippets, 432,304 cases** (census forms 260,928; extended forms 171,376).

* **Census coverage: 203/203 forms, 294/294 encoding classes.** Integer, string, stack, setcc and fs: forms:
  **no failure**. #DE: 2,642 cases (div/idiv r32/m32; 732 divide-by-zero, 1,910 quotient overflow incl. INT_MIN/-1)
  raise #DE on the CPU and reach `xrt_div0` in the lifted code; no case where only one side faulted; the per-case
  SDM prediction in `gen.py` agreed with the hardware every time.
* **20 failing cases, all attributed to the runtime, not the lifter**: `fsin` 3, `fcos` 11, `fptan` 6 (finding 2).
* **Extended forms (179 forms outside the census): no failure** after the lifter fix below (before it: every
  `lock`-prefixed form, 16,464 cases, failed).
* Second vector set (`--seed 7 --scale 3`, 1,293,592 cases): 73 failures, again only fsin/fcos/fptan and only NaN/+-inf operands.
* **Sensitivity**: all 13 injected lifter bugs are detected (table below).

### Finding 1 - lifter bug, fixed: `lock`-prefixed instructions were always traps

Capstone spells the prefix into the mnemonic (`lock add`), so `lift_insn`'s check
`ins.prefix[0] == 0xF0 and m not in ("add", "sub", ..., "sbb")` never matched and every lock-prefixed
read-modify-write raised `Unsupported("lock prefix on unexpected instruction")`, i.e. became `xrt_trap` instead of
the intended plain RMW (atomic under the runtime's execution baton). Demonstrated by the extended forms `lock
add/sub/and/or/xor/adc/sbb m32,r32` and `lock inc/dec/neg/not m32`: native result vs. lifted trap in all 16,464
cases. Fix (`tools/xrt/xlift.py`, 2 lines, no ABI change): strip `"lock "` from the mnemonic before dispatch; the
prefix check still sees `ins.prefix`. Regression test: `IntegerSemantics.test_lock_prefixed_rmw_lifts_like_the_plain_instruction`
in `tools/xrt/tests/test_xlift.py` (fails without the fix). Core.dll and UCC.exe contain no lock-prefixed
instruction: their lifted output is byte-identical with and without the fix (checked by lifting both ways). `lock
xadd`/`lock cmpxchg` still trap because xadd/cmpxchg are not implemented (Engine.dll may need them).

### Finding 2 - runtime deviation (not changed here: `runtime/*.c` is out of scope for this test)

`xrt_cpu.c`'s `trig_out_of_range()` tests `!(fabs(x) < 2^63)`, which is also true for NaN and +-inf. For such
operands `xrt_fsin`/`xrt_fcos`/`xrt_fptan` set C2 = 1 and leave ST(0) unchanged (fptan pushes nothing). The
hardware returns a NaN with C2 = 0: NaN in gives the same QNaN; +-inf gives the invalid-operation default
(0xFFF8000000000000, IE set); `fptan` stores that NaN and pushes it as well (both ST(0) and ST(1) NaN, TOP-1).
All 20 failing cases are exactly the NaN/+-inf inputs (every finite input, including |x| >= 2^63, matches in C2 and
TOP). Suggested change: treat only finite |x| >= 2^63 as out of range; for NaN/inf store `isnan(x) ? x : -NaN`
(indefinite), clear C2, and for fptan push the same NaN instead of 1.0. Practical impact is low (the engine's
fsin/fcos/fptan arguments are finite), but the C2 test `fnstsw ax; test ah, 4` would take the wrong branch on NaN.

### Finding 3 - model differences (by design; counts in `results.json`)

| category | cases | cause |
|---|---:|---|
| `x87-not-a-double` | 2,679 | register value beyond double precision/range on the hardware. Documented in `experiments/xrt/README.md` for >53-bit `fild m64` (600 cases) and the 80-bit exponent range of intermediates (products/quotients that overflow or are subnormal in double). **Not yet documented: `fldl2e`, `fldln2` (both in the census) and `fldpi/fldlg2/fldl2t` load 64-bit-significand constants on the hardware** (FCW.PC does not apply to constant loads); rounded to double they equal the model's constants, so only the last bit of following x87 arithmetic can differ |
| `x87-transcendental` | 512 | host libm vs. the x87's own argument reduction (66-bit pi); see the ULP table |
| `x87-nan-payload` | 40 | x87 vs. SSE NaN propagation (which operand's payload/sign survives) and `fld m64` of an SNaN (the hardware quiets it, the model copies the bits) |
| `x87-c1` | 12,130 | C1 (round-up indication) is not modelled; never read by these modules (all `fnstsw ax` consumers test 0x01/0x04/0x40) |
| `x87-exception-flags` | 33,048 | sticky exception flags (PE, IE, ...) not modelled (all exceptions masked); never read |
| `fnstsw-unmodelled` | 1,226 | the same bits as seen in AX after `fnstsw ax` |
| `fatal-by-design` | 791 | `fldcw` with 0x037F, 0x0E7F, 0x067F, 0x007F, 0x027E: `xrt_fldcw` stops (precision/rounding/mask outside the model); 0x027F and 0x127F load and match |

Transcendental ULP distance (lifted vs. hardware result rounded to double; trig by |x| of the operand):

| instruction | |x| < pi/4 | pi/4 <= |x| < 10 | 10 <= |x| < 1e6 | larger / NaN / inf |
|---|---|---|---|---|
| fsin | 22 exact | 181 exact, 9 at 1, 8 at >=3 | 8 exact, 20 at 1, 6 at 2, 44 at >=3 | 13 exact, 8 at >=3, 1 NaN/inf |
| fcos | 30 exact | 177 exact, 5 at 1, 3 at >=3 | 6 exact, 14 at 1, 11 at 2, 49 at >=3 | 8 exact, 7 at >=3, 10 NaN/inf |
| fptan (tan) | 32 exact | 169 exact, 13 at 1, 7 at >=3 | 1 exact, 3 at 1, 1 at 2, 74 at >=3 | 10 exact, 4 at >=3, 6 NaN/inf |

`f2xm1` (|x| <= 1): 180 exact, 131 at 1 ULP, 9 at 2; `fyl2x`: 253 exact, 67 at 1; `fpatan`: 318 exact, 2 at 1.
Large-|x| differences are the hardware's reduction error (the lifted results are the correctly reduced ones).

**Latent model gap (not in the census, no failure in single-instruction tests):** the lifter translates `fninit`
as `c->fcw = 0x037F` directly, bypassing `xrt_fldcw`'s check, so after an `fninit` the model would silently keep
53-bit rounding while the hardware uses 64-bit precision. Lifting it as `xrt_fldcw(c, 0x037F)` (fatal, like any
other control word outside the model) would make the limitation explicit.

**Not implemented by the lifter (traps if reached; listed in `results.json`, not run):** fxam, fprem, fprem1,
fincstp, fdecstp, ffree, fcmovcc, fcomi/fucomi(p), fbld/fbstp, 80-bit fld/fstp, fldenv/fnstenv/frstor/fnsave,
fxtract, fsincos, fyl2xp1, mul/imul r16 (one operand), div/idiv r8/r16, rcl/rcr, bt/bts/btr/btc, bsf/bsr,
xadd, cmpxchg, sahf/lahf, pushfd/popfd, pushad/popad, xlat. None occurs in Core.dll/UCC.exe.

### Sensitivity check (`mutation_check.py`)

Each mutation edits the generated C as a plausible lifter bug would; the cases are rerun and must produce new
failures. All are detected:

| injected defect | sites in the generated C | failed cases (baseline 20) |
|---|---:|---:|
| adc ignores carry-in (killed) | 45 | 3185 |
| sbb carry-out ignores carry-in (killed) | 52 | 890 |
| shr CF taken from the wrong bit (killed) | 164 | 1172 |
| setl condition inverted (killed) | 4 | 1300 |
| high-byte register write clobbers the low byte (killed) | 317 | 30158 |
| 8-bit compare flags computed at 32 bits (killed) | 64 | 5354 |
| idiv quotient overflow not detected (killed) | 7 | 951 |
| string ops ignore DF (killed) | 9 | 1435 |
| fsub/fsubp ST(i),ST(0) operand order swapped (killed) | 2 | 640 |
| sar shifts logically (killed) | 41 | 805 |
| movsx from 16 bits treated as 8 bits (killed) | 8 | 1605 |
| x87 fild m64 read as m32 (killed) | 4 | 184 |
| fs: operands off by 4 bytes (killed) | 14 | 4486 |

## Coverage

Census forms by family (`enc` = census encoding classes; all are covered):

| family | census forms | census instructions | census encoding classes | snippets | cases | #DE cases | failed cases |
|---|---:|---:|---:|---:|---:|---:|---:|
| alu1 | 11 | 1907 | 22 | 35 | 11200 | 0 | 0 |
| alu2 | 67 | 18088 | 90 | 683 | 76448 | 0 | 0 |
| div | 4 | 22 | 4 | 14 | 5600 | 2642 | 0 |
| dshift | 2 | 2 | 2 | 4 | 1280 | 0 | 0 |
| flagop | 1 | 2 | 1 | 1 | 320 | 0 | 0 |
| move | 27 | 52097 | 40 | 354 | 78192 | 0 | 0 |
| mul | 8 | 201 | 9 | 46 | 9280 | 0 | 0 |
| setcc | 6 | 132 | 6 | 24 | 7680 | 0 | 0 |
| shift | 7 | 589 | 10 | 126 | 8400 | 0 | 0 |
| stack | 5 | 33619 | 16 | 35 | 6848 | 0 | 0 |
| string | 8 | 570 | 8 | 8 | 2560 | 0 | 0 |
| x87 | 57 | 6466 | 86 | 166 | 53120 | 0 | 20 |
| **total** | **203** | **113695** | **294** | **1496** | **260928** | **2642** | **20** |

Extended forms (outside the census; implemented by the lifter):

| family | extended forms | encoding classes | snippets | cases | failed cases |
|---|---:|---:|---:|---:|---:|
| alu1 | 12 | 12 | 39 | 12480 | 0 |
| alu2 | 31 | 31 | 191 | 33664 | 0 |
| dshift | 4 | 4 | 30 | 4000 | 0 |
| flagop | 4 | 4 | 4 | 1280 | 0 |
| move | 28 | 30 | 65 | 20800 | 0 |
| mul | 5 | 6 | 33 | 5392 | 0 |
| other | 1 | 1 | 1 | 320 | 0 |
| setcc | 12 | 12 | 28 | 8960 | 0 |
| shift | 24 | 27 | 591 | 36800 | 0 |
| stack | 1 | 1 | 4 | 1280 | 0 |
| string | 19 | 19 | 19 | 6080 | 0 |
| x87 | 37 | 37 | 82 | 26240 | 0 |
| x87seq | 1 | 1 | 44 | 14080 | 0 |
| **total** | **179** | **185** | **1131** | **171376** | **0** |

Census forms (sorted by occurrences in Core.dll + UCC.exe; `variants` = distinct register/addressing variants):

| form | census instrs | census enc. classes | variants | snippets | cases | failed | model-only differences (cases) |
|---|---:|---:|---:|---:|---:|---:|---|
| `mov r32,m32` | 20297 | 2 | 48 | 54 | 17280 | 0 |  |
| `push r32` | 16600 | 7 | 1 | 8 | 2560 | 0 |  |
| `mov m32,r32` | 10827 | 2 | 50 | 50 | 16000 | 0 |  |
| `push imm` | 10735 | 2 | 1 | 16 | 768 | 0 |  |
| `mov r32,r32` | 6942 | 1 | 4 | 4 | 1280 | 0 |  |
| `pop r32` | 6254 | 5 | 1 | 6 | 1920 | 0 |  |
| `lea r32,m32` | 5524 | 1 | 39 | 39 | 12480 | 0 |  |
| `add r32,imm` | 5128 | 3 | 3 | 28 | 1344 | 0 |  |
| `test r32,r32` | 2966 | 1 | 2 | 2 | 640 | 0 |  |
| `mov m32,imm` | 2886 | 1 | 4 | 14 | 672 | 0 |  |
| `mov r32,imm` | 2832 | 7 | 1 | 56 | 2688 | 0 |  |
| `xor r32,r32` | 2137 | 1 | 2 | 2 | 640 | 0 |  |
| `fld m32` | 1720 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 106 |
| `cmp r32,r32` | 1558 | 1 | 2 | 2 | 640 | 0 |  |
| `inc r32` | 1491 | 7 | 1 | 7 | 2240 | 0 |  |
| `fstp m32` | 1005 | 1 | 4 | 4 | 1280 | 0 | x87-c1 463, x87-exception-flags 923 |
| `fmul m32` | 1003 | 1 | 4 | 4 | 1280 | 0 | x87-c1 286, x87-exception-flags 630, x87-not-a-double 13 |
| `sub r32,imm` | 957 | 3 | 3 | 28 | 1344 | 0 |  |
| `cmp m32,r32` | 859 | 1 | 5 | 5 | 1600 | 0 |  |
| `add r32,r32` | 702 | 1 | 4 | 4 | 1280 | 0 |  |
| `mov m8,imm` | 684 | 1 | 4 | 14 | 672 | 0 |  |
| `mov m8,r8` | 563 | 2 | 9 | 9 | 2880 | 0 |  |
| `movzx r32,m8` | 552 | 1 | 5 | 5 | 1600 | 0 |  |
| `test r8,imm` | 494 | 2 | 3 | 18 | 864 | 0 |  |
| `and r32,imm` | 493 | 3 | 3 | 28 | 1344 | 0 |  |
| `rep stosd m32,r32` | 420 | 1 | 1 | 1 | 320 | 0 |  |
| `cmp r32,imm` | 411 | 3 | 2 | 24 | 1152 | 0 |  |
| `faddp sti` | 382 | 6 | 1 | 6 | 1920 | 0 | x87-c1 622, x87-exception-flags 1272 |
| `cmp r32,m32` | 375 | 1 | 5 | 5 | 1600 | 0 |  |
| `fnstsw r16` | 298 | 1 | 1 | 1 | 320 | 0 | fnstsw-unmodelled 10, x87-exception-flags 10 |
| `cmp m8,imm` | 260 | 1 | 4 | 14 | 672 | 0 |  |
| `mov r8,m8` | 226 | 1 | 9 | 9 | 2880 | 0 |  |
| `sub r32,r32` | 219 | 1 | 4 | 4 | 1280 | 0 |  |
| `cmp r16,imm` | 207 | 3 | 2 | 22 | 1056 | 0 |  |
| `sar r32,imm` | 192 | 2 | 1 | 39 | 1840 | 0 |  |
| `shr r32,imm` | 187 | 2 | 1 | 39 | 1840 | 0 |  |
| `fadd m32` | 185 | 1 | 4 | 4 | 1280 | 0 | x87-c1 240, x87-exception-flags 520 |
| `fcomp m32` | 183 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 174 |
| `shl r32,imm` | 182 | 2 | 1 | 39 | 1840 | 0 |  |
| `fsub m32` | 177 | 1 | 4 | 4 | 1280 | 0 | x87-c1 197, x87-exception-flags 471, x87-nan-payload 1 |
| `dec r32` | 170 | 6 | 1 | 6 | 1920 | 0 |  |
| `cdq` | 156 | 1 | 1 | 1 | 320 | 0 |  |
| `or r32,r32` | 152 | 1 | 2 | 2 | 640 | 0 |  |
| `cmp m32,imm` | 151 | 2 | 4 | 28 | 1344 | 0 |  |
| `mov r16,m16` | 150 | 2 | 8 | 8 | 2560 | 0 |  |
| `and r32,r32` | 143 | 1 | 2 | 2 | 640 | 0 |  |
| `fstp m64` | 143 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 70 |
| `fxch st0,sti` | 136 | 5 | 1 | 5 | 1600 | 0 | x87-exception-flags 91 |
| `mov m16,r16` | 135 | 1 | 5 | 5 | 1600 | 0 |  |
| `fstp st0` | 128 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 20 |
| `fsubp sti` | 119 | 4 | 1 | 4 | 1280 | 0 | x87-c1 407, x87-exception-flags 852, x87-nan-payload 1, x87-not-a-double 1 |
| `fmul sti` | 111 | 7 | 1 | 7 | 2240 | 0 | x87-c1 647, x87-exception-flags 1475, x87-nan-payload 1, x87-not-a-double 99 |
| `fchs` | 107 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 14 |
| `neg r32` | 98 | 1 | 1 | 1 | 320 | 0 |  |
| `or r32,imm` | 96 | 3 | 2 | 24 | 1152 | 0 |  |
| `imul r32,r32,imm` | 94 | 2 | 2 | 20 | 960 | 0 |  |
| `fld st0` | 92 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 16 |
| `cmp m16,imm` | 89 | 2 | 4 | 27 | 1296 | 0 |  |
| `test m8,imm` | 86 | 1 | 4 | 14 | 672 | 0 |  |
| `rep movsd m32,m32` | 82 | 1 | 1 | 1 | 320 | 0 |  |
| `fld sti` | 78 | 6 | 1 | 6 | 1920 | 0 | x87-exception-flags 140 |
| `fild m32` | 77 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 59 |
| `mov m16,imm` | 71 | 1 | 4 | 13 | 624 | 0 |  |
| `fdiv m32` | 69 | 1 | 4 | 4 | 1280 | 0 | x87-c1 355, x87-exception-flags 814, x87-not-a-double 18 |
| `not r32` | 69 | 1 | 1 | 1 | 320 | 0 |  |
| `fst m32` | 68 | 1 | 4 | 4 | 1280 | 0 | x87-c1 475, x87-exception-flags 877 |
| `sete r8` | 67 | 1 | 4 | 4 | 1280 | 0 |  |
| `nop` | 66 | 1 | 1 | 1 | 320 | 0 |  |
| `fmul m64` | 64 | 1 | 4 | 4 | 1280 | 0 | x87-c1 384, x87-exception-flags 860, x87-not-a-double 76 |
| `add r32,m32` | 63 | 1 | 5 | 5 | 1600 | 0 |  |
| `imul r32,r32` | 62 | 1 | 2 | 2 | 640 | 0 |  |
| `sbb r32,r32` | 58 | 1 | 2 | 2 | 676 | 0 |  |
| `test r8,r8` | 55 | 1 | 3 | 3 | 960 | 0 |  |
| `fcom m32` | 54 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 164 |
| `movzx r32,m16` | 53 | 1 | 5 | 5 | 1600 | 0 |  |
| `inc m32` | 46 | 1 | 4 | 4 | 1280 | 0 |  |
| `setne r8` | 37 | 1 | 4 | 4 | 1280 | 0 |  |
| `movzx r32,r8` | 36 | 1 | 3 | 3 | 960 | 0 |  |
| `imul r32,m32` | 35 | 1 | 5 | 5 | 1600 | 0 |  |
| `rep stosb m8,r8` | 34 | 1 | 1 | 1 | 320 | 0 |  |
| `movzx r32,r16` | 33 | 1 | 2 | 2 | 640 | 0 |  |
| `or m32,imm` | 33 | 2 | 4 | 28 | 1344 | 0 |  |
| `fcomp sti` | 30 | 1 | 1 | 2 | 640 | 0 | x87-exception-flags 58 |
| `fild m64` | 29 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 48, x87-not-a-double 600 |
| `cmp m16,r16` | 28 | 1 | 5 | 5 | 1600 | 0 |  |
| `push m32` | 27 | 1 | 4 | 4 | 1280 | 0 |  |
| `sub r32,m32` | 27 | 1 | 5 | 5 | 1600 | 0 |  |
| `test r16,r16` | 27 | 1 | 2 | 2 | 640 | 0 |  |
| `fld m64` | 26 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 90, x87-nan-payload 33 |
| `test m32,r32` | 26 | 1 | 5 | 5 | 1600 | 0 |  |
| `fcomp m64` | 25 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 150 |
| `fsub sti` | 25 | 2 | 1 | 2 | 640 | 0 | x87-c1 212, x87-exception-flags 430 |
| `stosw m16,r16` | 25 | 1 | 1 | 1 | 320 | 0 |  |
| `add m32,imm` | 24 | 2 | 4 | 28 | 1344 | 0 |  |
| `test r32,imm` | 24 | 2 | 2 | 16 | 768 | 0 |  |
| `test m32,imm` | 22 | 1 | 4 | 14 | 672 | 0 |  |
| `fadd st0,st0` | 21 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 21, x87-not-a-double 4 |
| `and m32,imm` | 20 | 2 | 4 | 28 | 1344 | 0 |  |
| `cmp r8,imm` | 18 | 2 | 3 | 18 | 864 | 0 |  |
| `idiv r32` | 16 | 1 | 3 | 3 | 1200 | 0 |  |
| `shl r32,r8` | 16 | 1 | 2 | 2 | 640 | 0 |  |
| `mov r8,imm` | 15 | 4 | 1 | 32 | 1536 | 0 |  |
| `mov r8,r8` | 15 | 1 | 3 | 3 | 960 | 0 |  |
| `fmulp sti` | 14 | 2 | 1 | 2 | 640 | 0 | x87-c1 197, x87-exception-flags 417, x87-not-a-double 22 |
| `or m32,r32` | 14 | 1 | 5 | 5 | 1600 | 0 |  |
| `or r32,m32` | 14 | 1 | 5 | 5 | 1600 | 0 |  |
| `cmp r16,r16` | 13 | 1 | 2 | 2 | 640 | 0 |  |
| `dec m32` | 12 | 1 | 4 | 4 | 1280 | 0 |  |
| `fstp sti` | 12 | 4 | 1 | 4 | 1280 | 0 | x87-exception-flags 85 |
| `add m32,r32` | 11 | 1 | 5 | 5 | 1600 | 0 |  |
| `and r32,m32` | 10 | 1 | 5 | 5 | 1600 | 0 |  |
| `and r8,imm` | 10 | 2 | 3 | 18 | 864 | 0 |  |
| `fdivr m64` | 10 | 1 | 4 | 4 | 1280 | 0 | x87-c1 348, x87-exception-flags 780, x87-not-a-double 39 |
| `movsx r16,r8` | 10 | 1 | 3 | 3 | 960 | 0 |  |
| `and r8,r8` | 9 | 1 | 3 | 3 | 960 | 0 |  |
| `fdivr m32` | 9 | 1 | 4 | 4 | 1280 | 0 | x87-c1 406, x87-exception-flags 866, x87-nan-payload 1, x87-not-a-double 19 |
| `setg r8` | 9 | 1 | 4 | 4 | 1280 | 0 |  |
| `setge r8` | 9 | 1 | 4 | 4 | 1280 | 0 |  |
| `sub m32,r32` | 9 | 1 | 5 | 5 | 1600 | 0 |  |
| `cmp r8,m8` | 8 | 1 | 6 | 6 | 1920 | 0 |  |
| `fsubr m32` | 8 | 1 | 4 | 4 | 1280 | 0 | x87-c1 189, x87-exception-flags 454, x87-nan-payload 2 |
| `movzx r16,m8` | 8 | 1 | 5 | 5 | 1600 | 0 |  |
| `or r8,r8` | 8 | 1 | 3 | 3 | 960 | 0 |  |
| `shr r32,r8` | 8 | 1 | 2 | 2 | 640 | 0 |  |
| `xor r8,r8` | 8 | 1 | 3 | 3 | 960 | 0 |  |
| `adc r32,r32` | 7 | 1 | 2 | 2 | 676 | 0 |  |
| `cmp r16,m16` | 7 | 1 | 5 | 5 | 1600 | 0 |  |
| `cmp r8,r8` | 7 | 1 | 3 | 3 | 960 | 0 |  |
| `fdivp sti` | 7 | 1 | 1 | 1 | 320 | 0 | x87-c1 141, x87-exception-flags 276, x87-not-a-double 9 |
| `dec r8` | 6 | 1 | 2 | 2 | 640 | 0 |  |
| `fadd m64` | 6 | 1 | 4 | 4 | 1280 | 0 | x87-c1 286, x87-exception-flags 649, x87-not-a-double 6 |
| `inc r8` | 6 | 1 | 2 | 2 | 640 | 0 |  |
| `add r8,imm` | 5 | 2 | 3 | 18 | 864 | 0 |  |
| `fcom m64` | 5 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 116 |
| `fsub m64` | 5 | 1 | 4 | 4 | 1280 | 0 | x87-c1 251, x87-exception-flags 597 |
| `movsx r16,m8` | 5 | 1 | 5 | 5 | 1600 | 0 |  |
| `not r8` | 5 | 1 | 2 | 2 | 640 | 0 |  |
| `setl r8` | 5 | 1 | 4 | 4 | 1280 | 0 |  |
| `setle r8` | 5 | 1 | 4 | 4 | 1280 | 0 |  |
| `test m8,r8` | 5 | 1 | 6 | 6 | 1920 | 0 |  |
| `adc m32,r32` | 4 | 1 | 5 | 5 | 1672 | 0 |  |
| `add r8,r8` | 4 | 1 | 3 | 3 | 960 | 0 |  |
| `fadd sti` | 4 | 2 | 1 | 2 | 640 | 0 | x87-c1 227, x87-exception-flags 444 |
| `fdiv m64` | 4 | 1 | 4 | 4 | 1280 | 0 | x87-c1 321, x87-exception-flags 778, x87-not-a-double 36 |
| `fdiv sti` | 4 | 1 | 1 | 1 | 320 | 0 | x87-c1 136, x87-exception-flags 267, x87-not-a-double 13 |
| `fst m64` | 4 | 1 | 4 | 4 | 1280 | 0 | x87-exception-flags 66 |
| `imul r32` | 4 | 1 | 3 | 3 | 960 | 0 |  |
| `movsx r32,m16` | 4 | 1 | 5 | 5 | 1600 | 0 |  |
| `sbb r32,imm` | 4 | 1 | 1 | 8 | 384 | 0 |  |
| `adc r32,imm` | 3 | 1 | 1 | 8 | 384 | 0 |  |
| `and m32,r32` | 3 | 1 | 5 | 5 | 1600 | 0 |  |
| `div r32` | 3 | 1 | 3 | 3 | 1200 | 0 |  |
| `inc m8` | 3 | 1 | 4 | 4 | 1280 | 0 |  |
| `leave` | 3 | 1 | 1 | 1 | 320 | 0 |  |
| `movzx r16,r8` | 3 | 1 | 3 | 3 | 960 | 0 |  |
| `mul r32` | 3 | 1 | 3 | 3 | 960 | 0 |  |
| `rep movsb m8,m8` | 3 | 1 | 1 | 1 | 320 | 0 |  |
| `rep stosw m16,r16` | 3 | 1 | 1 | 1 | 320 | 0 |  |
| `shl r8,r8` | 3 | 1 | 3 | 3 | 960 | 0 |  |
| `and r8,m8` | 2 | 1 | 6 | 6 | 1920 | 0 |  |
| `cld` | 2 | 1 | 1 | 1 | 320 | 0 |  |
| `fld1` | 2 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 12 |
| `fpatan` | 2 | 1 | 1 | 1 | 320 | 0 | x87-c1 183, x87-exception-flags 299, x87-transcendental 2 |
| `idiv m32` | 2 | 1 | 4 | 4 | 1600 | 0 |  |
| `mov r16,r16` | 2 | 1 | 2 | 2 | 640 | 0 |  |
| `sbb r8,r8` | 2 | 1 | 3 | 3 | 960 | 0 |  |
| `stosb m8,r8` | 2 | 1 | 1 | 1 | 320 | 0 |  |
| `xchg r32,r32` | 2 | 1 | 3 | 4 | 1280 | 0 |  |
| `xor r32,imm` | 2 | 2 | 2 | 16 | 768 | 0 |  |
| `xor r32,m32` | 2 | 1 | 5 | 5 | 1600 | 0 |  |
| `add r16,m16` | 1 | 1 | 5 | 5 | 1600 | 0 |  |
| `and m8,r8` | 1 | 1 | 6 | 6 | 1920 | 0 |  |
| `cmp m8,r8` | 1 | 1 | 6 | 6 | 1920 | 0 |  |
| `div m32` | 1 | 1 | 4 | 4 | 1600 | 0 |  |
| `f2xm1` | 1 | 1 | 1 | 1 | 320 | 0 | x87-c1 153, x87-exception-flags 307, x87-transcendental 140 |
| `fcom sti` | 1 | 1 | 1 | 2 | 640 | 0 | x87-exception-flags 51 |
| `fcos` | 1 | 1 | 1 | 1 | 320 | 11 | x87-c1 151, x87-exception-flags 306, x87-transcendental 99 |
| `fdivrp sti` | 1 | 1 | 1 | 1 | 320 | 0 | x87-c1 140, x87-exception-flags 266, x87-not-a-double 9 |
| `fidiv m32` | 1 | 1 | 4 | 4 | 1280 | 0 | x87-c1 358, x87-exception-flags 868, x87-not-a-double 14 |
| `fistp m64` | 1 | 1 | 4 | 4 | 1280 | 0 | x87-c1 211, x87-exception-flags 757 |
| `fldl2e` | 1 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 19, x87-not-a-double 320 |
| `fldln2` | 1 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 14, x87-not-a-double 320 |
| `fptan` | 1 | 1 | 1 | 1 | 320 | 6 | x87-c1 124, x87-exception-flags 303, x87-transcendental 108 |
| `frndint` | 1 | 1 | 1 | 1 | 320 | 0 | x87-c1 114, x87-exception-flags 262 |
| `fscale` | 1 | 1 | 1 | 1 | 320 | 0 | x87-exception-flags 9, x87-not-a-double 6 |
| `fsin` | 1 | 1 | 1 | 1 | 320 | 3 | x87-c1 163, x87-exception-flags 303, x87-transcendental 96 |
| `fsqrt` | 1 | 1 | 1 | 1 | 320 | 0 | x87-c1 139, x87-exception-flags 289 |
| `fsubr m64` | 1 | 1 | 4 | 4 | 1280 | 0 | x87-c1 270, x87-exception-flags 621, x87-nan-payload 1 |
| `fyl2x` | 1 | 1 | 1 | 1 | 320 | 0 | x87-c1 148, x87-exception-flags 300, x87-transcendental 67 |
| `imul m8` | 1 | 1 | 4 | 4 | 1280 | 0 |  |
| `imul r16,m16` | 1 | 1 | 5 | 5 | 1600 | 0 |  |
| `mul m32` | 1 | 1 | 4 | 4 | 1280 | 0 |  |
| `neg r8` | 1 | 1 | 2 | 2 | 640 | 0 |  |
| `or m8,imm` | 1 | 1 | 4 | 14 | 672 | 0 |  |
| `or r8,imm` | 1 | 1 | 3 | 18 | 864 | 0 |  |
| `repe cmpsb m8,m8` | 1 | 1 | 1 | 1 | 320 | 0 |  |
| `sar r32,r8` | 1 | 1 | 2 | 2 | 640 | 0 |  |
| `shld r32,r32,r8` | 1 | 1 | 2 | 2 | 640 | 0 |  |
| `shrd r32,r32,r8` | 1 | 1 | 2 | 2 | 640 | 0 |  |
| `sub m32,imm` | 1 | 1 | 4 | 14 | 672 | 0 |  |
| `sub r8,imm` | 1 | 1 | 1 | 8 | 384 | 0 |  |
| `sub r8,r8` | 1 | 1 | 3 | 3 | 960 | 0 |  |
| `xor m32,imm` | 1 | 1 | 4 | 14 | 672 | 0 |  |

Extended forms tested: `adc m32,imm`, `adc r8,imm`, `adc r8,r8`, `add m16,imm`, `add m8,r8`, `add r16,r16`, `and r16,r16`, `bswap r32`, `cbw`, `clc`, `cmc`, `cmova r32,r32`, `cmovae r32,r32`, `cmovb r32,r32`, `cmovbe r32,r32`, `cmove r16,r16`, `cmove r32,m32`, `cmove r32,r32`, `cmovg r32,r32`, `cmovge r32,r32`, `cmovl r32,r32`, `cmovle r32,r32`, `cmovne r32,r32`, `cmovno r32,r32`, `cmovnp r32,r32`, `cmovns r32,r32`, `cmovo r32,r32`, `cmovp r32,r32`, `cmovs r32,r32`, `cmpsb m8,m8`, `cmpsd m32,m32`, `cmpsw m16,m16`, `cwd`, `cwde`, `dec m16`, `dec m8`, `fabs`, `fadd sti,st0`, `fcompp`, `fdiv sti,st0`, `fdivr sti`, `fdivr sti,st0`, `fiadd m32`, `ficom m32`, `ficomp m16`, `fidivr m16`, `fild m16`, `fimul m16`, `fist m16`, `fist m32`, `fistp m16`, `fistp m32`, `fisub m32`, `fisubr m32`, `fldcw m16`, `fldl2t`, `fldlg2`, `fldpi`, `fldz`, `fmul sti,st0`, `fnclex`, `fninit`, `fnstcw m16`, `fnstsw m16`, `fst sti`, `fsub sti,st0`, `fsubr sti`, `fsubr sti,st0`, `fsubrp sti`, `ftst`, `fucom sti`, `fucomp sti`, `fucompp`, `imul r16,r16`, `imul r16,r16,imm`, `imul r8`, `inc r16`, `lock adc m32,r32`, `lock add m32,r32`, `lock and m32,r32`, `lock dec m32`, `lock inc m32`, `lock neg m32`, `lock not m32`, `lock or m32,r32`, `lock sbb m32,r32`, `lock sub m32,r32`, `lock xor m32,r32`, `lodsb r8,m8`, `lodsd r32,m32`, `lodsw r16,m16`, `movsb m8,m8`, `movsd m32,m32`, `movsw m16,m16`, `movsx r32,m8`, `movsx r32,r16`, `movsx r32,r8`, `mul m8`, `mul r8`, `neg m32`, `neg m8`, `neg r16`, `not m32`, `not r16`, `or r16,imm`, `or r16,r16`, `or r8,m8`, `pop m32`, `rep movsw m16,m16`, `repe cmpsd m32,m32`, `repe scasb r8,m8`, `repne cmpsb m8,m8`, `repne scasb r8,m8`, `repne scasd r32,m32`, `rol m32,r8`, `rol r16,imm`, `rol r16,r8`, `rol r32,imm`, `rol r32,r8`, `rol r8,imm`, `rol r8,r8`, `ror m32,imm`, `ror r16,r8`, `ror r32,imm`, `ror r32,r8`, `ror r8,imm`, `ror r8,r8`, `sar m8,imm`, `sar r16,r8`, `sar r8,imm`, `sar r8,r8`, `sbb m32,r32`, `sbb m8,imm`, `sbb r16,r16`, `sbb r32,m32`, `sbb r8,imm`, `scasb r8,m8`, `scasd r32,m32`, `scasw r16,m16`, `seta r8`, `setae r8`, `setb r8`, `setbe r8`, `sete m8`, `setg m8`, `setno r8`, `setnp r8`, `setns r8`, `seto r8`, `setp r8`, `sets r8`, `shl m32,r8`, `shl r16,r8`, `shl r8,imm`, `shld m32,r32,r8`, `shld r32,r32,imm`, `shr m32,imm`, `shr r16,imm`, `shr r16,r8`, `shr r8,r8`, `shrd m32,r32,r8`, `shrd r32,r32,imm`, `stc`, `std`, `stosd m32,r32`, `sub m8,r8`, `sub r16,imm`, `sub r16,r16`, `test m16,r16`, `test r16,imm`, `wait`, `x87 compare; fnstsw ax; test ah, imm`, `xchg m32,r32`, `xchg r16,r16`, `xchg r8,r8`, `xor m8,imm`, `xor r16,r16`, `xor r8,imm`, `xor r8,m8`

## Limits of this test

* x87 stack overflow/underflow and the tag word, unmasked x87 exceptions, control words other than 0x027F (except
  the fldcw/fninit/fnstcw tests), SNaNs in registers and 80-bit memory operands (traps by design) are not tested.
* AF is never compared (not modelled). Segment overrides other than `fs:` with an absolute displacement (the only
  census use) and the address-size prefix (absent from the census) are not tested.
* `lock` atomicity is not tested (single-threaded harness; the runtime relies on its execution baton).
* Control transfer is out of scope; the shared condition table is covered through all 16 `setcc` conditions.
* Results are for one CPU (Intel Core i7-14700K). Defined outputs do not depend on the model; the transcendental
  ULP figures and the exact C1/exception-flag patterns may differ on other x87 implementations.
