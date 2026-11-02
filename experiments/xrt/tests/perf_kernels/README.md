# Translation-overhead kernels (`perf_kernels`)

Owned C kernels shaped like the game's hot paths, compiled by the x86 compiler with the x87 code generator
(`cl /O2 /arch:IA32`, no CRT), run natively and as `tools/xrt/xlift.py` output on the runtime's CPU model
(`out/dev-init/runtime/xrt.h`). They measure the cost of the translation itself, isolated from the game, the D3D8
layer and the host: the ratio "translated / native x86 on the same CPU" per kernel, for any `--opt` list and any
x64 compiler flag set, in about a minute and without a game launch. No game bytes are involved anywhere.

| kernel | shape | what it stresses in the translation |
|---|---|---|
| `k_bones` | 64-bone skeleton, parent-chain quaternion/translation composition through a per-kind function table (the GlmLib `Node::GetTransform` shape) | x87 arithmetic with memory operands, one indirect call per bone, register spills around calls |
| `k_verts` | 1024 vertices through a per-iteration rotation matrix, normals renormalised (`fsqrt`), clamped lighting, bounding box | float loads/stores, compare chains (`fcom/fnstsw`), the x87 value cache |
| `k_actors` | 256 polymorphic actors (vtable `tick`/`touch`): integration, box bounce, a six-state switch, grid hashing, pairwise touches | indirect calls, flags at boundaries, jump tables, mixed int/float |
| `k_strings` | case-insensitive FNV hashing, hash-table probing with string compares, byte copies | byte loads/stores, compare loops, `c->pc` stores, reduced flag updates |
| `k_bsp` | 2047-node BSP traversal of 512 points | pointer chasing, signed-distance compares, branches |

Only `+ - * /`, `fsqrt`, compares and conversions are used (no transcendental x87 instruction, whose hardware result
is not bit-exact in the model), so every translated checksum must equal the native one; `run.py` exits 1 otherwise.

```bat
rem game option set vs plain, game compiler flags (about a minute)
.venv\Scripts\python.exe -I experiments\xrt\tests\perf_kernels\run.py
rem translator options and compiler flag sets side by side
.venv\Scripts\python.exe -I experiments\xrt\tests\perf_kernels\run.py --opt base,flags,icall,iflags,pc,regs,sse,x87,x87v,x87w --opt base,flags,icall,iflags,pc,regs,sse,x87,x87v,x87w,cflags,rdtsc --cl "/O2 /fp:strict" --cl "/O2 /fp:strict /arch:AVX2"
rem export the lifted C + portable bench.c for a Linux / AArch64 cross build (see the Docker notes in the session journal)
.venv\Scripts\python.exe -I experiments\xrt\tests\perf_kernels\run.py --export experiments\xrt\build\perf_kernels\export
```

`bench.c` is portable C (Windows: `VirtualAlloc`/`__try`; POSIX: `mmap`/`SIGSEGV`), so the exported directory builds
with `gcc`/`clang` for Linux x86-64 and AArch64: `cc -O2 -I. -Ilifted lifted/*.c bench.c -lm -o bench`, then
`./bench image.bin BASE out.bin REPS k_name=0xVA:N ...` with the values from `reference.json`; the checksums must
match the native ones recorded there. Timings under QEMU user emulation are not meaningful; the AArch64 run checks
correctness, and `-S` output compares code generation.

Caveats: the x86 compiler here is the current MSVC (`/arch:IA32`), not the game's VC7, so the instruction mix is
similar but not identical; the kernels have no D3D8 calls, no runtime adapters and no C++ exception frames, so they
show the translated-code share of a frame only (about two thirds in the TutA cutscene), not the whole frame.

## Measured (2026-11-01, Ryzen 9 9950X3D, host partly loaded by other tasks: +-5% run to run)

Ratios are translated median time / native x86 median time (lower is better); plain = `xlift` without options.

| variant | actors | bones | bsp | strings | verts | geomean |
|---|---|---|---|---|---|---|
| plain lift, cl /O2 /fp:strict | 5.8 | 6.7 | 4.4 | 11.7 | 5.9 | 6.5 |
| game set 2026-10-31 (base,flags,icall,iflags,pc,regs,sse,x87,x87v,x87w), cl | 2.4 | 2.4 | 1.2 | 1.7 | 1.5 | 1.8 |
| + cflags,rdtsc, cl, lean entry | 2.2 | 2.1 | 1.1 | 1.6 | 1.4 | 1.6 |
| + lazypc | 2.0 | 1.8 | 1.1 | 1.5 | 1.2 | 1.5 |
| + addr64 (full set), cl | 1.7 | 1.3 | 1.0 | 1.3 | 1.4 | 1.3 |
| full set, clang-cl 23 /O2 /fp:strict | 1.9 | 1.4 | 1.0 | 1.5 | 1.1 | 1.3 |
| full set, clang-cl /O2 /fp:precise (no FMA on the baseline x86-64 target) | 1.7 | 1.5 | 1.0 | 1.4 | 0.9 | 1.2 |
| plain lift, clang-cl /O2 /fp:strict | 4.3 | 4.2 | 2.4 | 6.7 | 4.1 | 4.1 |

Every variant reproduced the native checksums. clang-cl is the largest compiler-side effect (40% on the plain lift, about
10% on the full option set); `/arch:AVX2`, `/GS-`, `/GL` and `/fp:precise` under cl moved the kernels by at most a few
percent. Cross builds of the exported full-set lift: gcc 13 Linux x86-64 (native run in the `gcc:13` container) and the
aarch64 gcc 8.3 static cross build (`ghcr.io/loveretro/tg5040-toolchain`) run under QEMU in `alpine:3.20` (arm64) both
reproduced all five checksums (AArch64 timings under emulation are not meaningful). clang 23 `-S` for the full-set lift:
AArch64 needs 0.94x the instructions of x86-64 (5324 vs 5635 for the 17 functions), dominated by CPU-struct loads/stores
and float/double conversions.

### 2026-11-02: call/return protocol options (`restrict`, `rv`, `regcache`) and whole-program optimization

Same harness, 9 repetitions, measured under the owner's background host load (absolute ratios are a few percent above the
quiet-host table; compare rows within this table). "C1 set" is the 2026-11-01 game build's option list
(`base,flags,icall,iflags,pc,regs,sse,x87,x87v,x87w,cflags,rdtsc,lazypc,addr64`), "C3 set" adds `restrict,rv,regcache`.

| variant | actors | bones | bsp | strings | verts | geomean |
|---|---|---|---|---|---|---|
| plain lift, cl /O2 /fp:strict | 6.24 | 7.05 | 4.24 | 12.05 | 6.31 | 6.77 |
| plain lift, cl /O2 /fp:strict /GL | 6.06 | 7.08 | 4.02 | 11.94 | 6.52 | 6.69 |
| C1 set, cl /O2 /fp:strict | 1.90 | 1.61 | 1.01 | 1.50 | 1.61 | 1.49 |
| C1 set, cl /O2 /fp:strict /GL | 1.89 | 1.65 | 1.04 | 1.33 | 1.38 | 1.43 |
| C3 set, cl /O2 /fp:strict | 1.91 | 1.62 | 1.07 | 1.58 | 1.44 | 1.50 |
| C3 set, cl /O2 /fp:strict /GL | 1.85 | 1.72 | 1.05 | 1.04 | 1.43 | 1.38 |

Every variant reproduced the native checksums. The kernels contain only 10 translated call sites, so the per-call
savings of `rv` (no `c->rv` store/load per call) and `regcache` (reloads of the live registers only) cannot show here:
C1 and C3 are equal within noise. The call-heavy kernel is `strings` (`k_strlen`/`k_hash` through translated calls): with
the C3 set under `/GL` the compiler can inline the small translated callees (their return value is now a plain `uint32_t`
and `c` is `__restrict`), 1.58x -> 1.04x native. The game decides (`tools/xrt/dev/PERF_REPORT_20261102.md`).
