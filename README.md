# Unreal II: The Awakening — Native Port / Recompilation Feasibility Study

Investigation workspace for a modern, portable implementation of *Unreal II: The Awakening* (Legend Entertainment, 2003), targeting Windows, Linux and Android ARM64.

- **Investigation date:** 2026-10-22
- **Machine:** i7-14700K, Windows 11 Enterprise 10.0.26300
- **Game copy:** the user's GOG *Special Edition*, at `E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening`

The original installation was treated as **read-only** throughout, and so was the `Save` junction, which points into Proton Drive. Every run of original binaries used a copy of `singleplayer\System` in `sandbox\`.

## Status

**Recompilation checkpoint, 2026-10-23:** the translated client completes genuine Entry LoadMap, opens
CS_Intro.un2 and completes its package PostLoad, then stops at the DirectMusic `OLE32!CoInitialize`
boundary. CS_Intro LoadMap return, selected-world initialization/ticks and translated device/Presents
remain unreached. The pinned DXVK x64 query backend and measured floor/ceil adapters pass their focused
comparisons. The original reference completes CS_Intro initialization, four world ticks and three game Presents; visual/input gameplay
remains unverified. See [current status](CURRENT_STATUS.md) and [execution evidence](experiments/xrt/GRAPHICS_STARTUP.md).
The initial feasibility results follow.

Reconnaissance and seven proof-of-concept experiments are done (E1–E7 in [POC_RESULTS.md](POC_RESULTS.md)). The headline results were all validated against the **original game binaries and data**:

| # | Experiment | Result |
|---|---|---|
| E1 | Independent package reader, table layer | 324 single-player packages (1.67 GB) and 210 XMP packages parse with **0 unaccounted bytes**. 23,568 cross-package imports resolve to real exports, and 1,185 resolve to C++-only classes. Of the 7 imports the checker leaves unresolved, 6 are stale references in old shipped particle packages; the 7th is the intrinsic `UPendingLevel`. |
| E2 | Object layer and bytecode parser | **35,411 / 35,411** script objects consume exactly their serialized size. Every jump target in 8,666 bytecode bodies lands on a token boundary. Legend's format deviations are identified and documented. |
| E3 | Native interface recovered from machine code | Every bytecode opcode, cast and native index was recovered from the DLLs' `GRegisterNative` code. All 446 name-bound and 260 of 277 numbered natives match their script declarations by name. 12 more match under a different C++ name, and 5 have no implementation in any shipped DLL. All 213 native indices called from shipped bytecode are registered. |
| E4 | Original engine as an oracle | The original `UCC.exe` runs headless from the sandbox. It compiles our own UnrealScript with the original Unreal II compiler. |
| E5 | **Independent C++ UnrealScript VM** | **74 / 74** output lines are byte-identical to the original engine. The tests are 4 programs: our 54-test probe and 3 shipped Core commandlets, including ArrayTest's warning text and bytecode offsets. The match holds on **Windows x64 (MSVC)**, **Linux x86-64 (GCC)** and **Linux ARM64 (GCC, QEMU)**. |
| E6 | **Static x86→C lifting of real Core.dll code** | 13 functions (1,026 instructions, including the CRT `_ftol2` x87 helper) were lifted automatically. Output is **bit-identical** to the original DLL: 102,000 / 102,000 result lines on x64, Linux x86-64 and ARM64. The same minimal lifter handles 52–61% of all exported functions in Core, Engine and GlmLib. The blockers are measured. |
| E7 | Existing tools: UELib, content survey, Golem, DirectMusic, saves | UELib loads every package but leaves 109,719 objects partly unparsed. 1.6 GB of class-specific native payload was mapped across 253 classes. The Golem `.gem` and DirectMusic `.con` structures were surveyed. Save games are ordinary packages, and one parses cleanly. |

## Verdicts

The full reasoning is in [APPROACH_COMPARISON.md](APPROACH_COMPARISON.md) and [BLOCKERS.md](BLOCKERS.md).

| Target | Verdict |
|---|---|
| Modern Windows engine implementation | **CONDITIONAL GO.** Use the hybrid architecture, as a multi-year effort. |
| Native Linux port | **CONDITIONAL GO.** Same conditions as Windows. The portable core is already proven on Linux. |
| Android ARM64 port | **CONDITIONAL GO, long-term.** The script VM and lifted code are bit-exact on ARM64. Rendering, audio, Golem and performance are not yet proven. |
| Static native recompilation | **CONDITIONAL GO, as the recommended backbone.** It is bit-exact on sampled real code on x64 and ARM64. Whole-module lifting, with SEH and indirect calls, is not yet demonstrated; experiment X1 in ROADMAP.md decides it. |
| Full engine reconstruction (all native code rewritten) | **NO-GO** as a standalone goal. The effort is disproportionate. |

**Most promising architecture:** the **recompile-first hybrid (D-B)**. It works in stages:

1. All original native modules — including Golem (`GlmLib.dll`), physics, particles and the Legend UI — are statically recompiled into portable C in a shared guest address space. Their behaviour is therefore faithful by construction (method proven in E6).
2. The platform layer is replaced once: D3D8 via DXVK's D3D8 frontend or a custom renderer, SDL3, OpenAL Soft, and a DirectMusic subset.
3. Lifted parts are then progressively swapped for the independent components already proven here, starting with the portable package loader and UnrealScript VM (E5). Each swap is gated by the two differential oracles built here.

The fallback, if whole-module lifting fails, is the reimplement-first hybrid (D-R).

**Separate, immediate option:** players who just want the game running today should use compatibility layers instead: a D3D8 wrapper on Windows, Proton on Linux, Winlator on Android. That is not a port. See APPROACH_COMPARISON strategy C.

## Documents

| File | Contents |
|---|---|
| [RECONNAISSANCE.md](RECONNAISSANCE.md) | Binary, toolchain, package and file-format findings, with numbers |
| [ENGINE_ARCHITECTURE.md](ENGINE_ARCHITECTURE.md) | Subsystem and dependency map: recoverable, reusable, replaceable or unknown |
| [APPROACH_COMPARISON.md](APPROACH_COMPARISON.md) | Strategies A–D compared, with external prior art |
| [POC_RESULTS.md](POC_RESULTS.md) | Experiments E1–E7 in reproducible form: attempted, artifacts, compiled, validated, failed, proves, does not prove |
| [BLOCKERS.md](BLOCKERS.md) | Blockers and unresolved risks |
| [ROADMAP.md](ROADMAP.md) | Phased plan with objectively testable milestones, and the next three experiments |

## Layout

```
tools/pe/           PE reconnaissance: headers, Rich header, imports/exports, demangling,
                    native registration recovery, code statistics, x86 disassembly helpers
tools/pkgreader/    independent Python package reader + validators (tables, objects, bytecode,
                    native cross-check, content survey, script text, disassembler)
tools/lift/         lift_x86.py - function-level x86-32 -> C static lifter (+ coverage mode)
tools/run_ucc.ps1   runs the ORIGINAL UCC.exe from sandbox/System only
tools/riff_tree.py  RIFF/DirectMusic container inspector
experiments/vmprobe/    VMProbe.uc (our UnrealScript probe), build_probe.ps1, reference outputs
experiments/uvm/        uvm - independent C++17 UnrealScript VM (+ MSVC / Docker build scripts)
experiments/lift/       lifting harnesses (original-DLL x86 harness, lifted harness, runtime)
experiments/uelib_test/ .NET harness exercising UELib on Unreal II data
third_party/Unreal-Library/  shallow clone of EliotVU/Unreal-Library (MIT) at 8236c39
sandbox/            LOCAL ONLY: copy of the game's System folder for running original binaries
out/                LOCAL ONLY: generated reports, symbol dumps, native tables, JSON stats
.venv/              Python virtual environment (pefile, capstone)
```

## Reproducing

All commands assume the paths above. Tool versions used: Python 3.14 (`pefile` 2024.8.26, `capstone` 5.0.7), Visual Studio 2026 with MSVC 14.51 (x86 and x64), .NET SDK 10.0.402, and Docker 29.7 with `gcc:13` and `alpine:3.20` (arm64 under QEMU).

```bash
.venv/Scripts/python -I tools/pkgreader/validate_tables.py "<game>/singleplayer" --symbols out/symbols_sp
```

```bash
.venv/Scripts/python -I tools/pkgreader/validate_objects.py "<game>/singleplayer"
```

```bash
.venv/Scripts/python -I tools/pkgreader/crosscheck_natives.py sandbox/System out/native_table_sp.json
```

```bash
experiments/vmprobe/build_probe.ps1
```

```bash
experiments/uvm/build_msvc.cmd x64
```

```bash
experiments/uvm/build/x64/uvm.exe sandbox/System VMProbe.VMProbe --quiet --compare experiments/vmprobe/VMProbe.reference.txt
```

```bash
docker run --rm --platform linux/arm64 -v "E:/Unreal2-Port-Investigation:/work" alpine:3.20 sh -c "apk add --no-cache g++ && sh /work/experiments/uvm/run_linux_tests.sh linux-arm64"
```

```bash
experiments/lift/build_and_test.cmd
```

```bash
docker run --rm --platform linux/arm64 -v "E:/Unreal2-Port-Investigation:/work" alpine:3.20 sh -c "apk add --no-cache gcc musl-dev && sh /work/experiments/lift/run_linux_lift.sh linux-arm64"
```

The `out/` symbol and native tables are produced by `tools/pe/pe_recon.py`, `symbols.py`, `natives.py` and `native_table.py`. The exact invocations are in RECONNAISSANCE.md.

## Legal and redistribution boundaries

- **Never redistribute:**
  - `sandbox/` (original Legend/Epic binaries and packages)
  - `out/` (derived symbol dumps)
  - `experiments/lift/lifted_core.c` and `experiments/lift/build/` (machine translations of proprietary code)
  - any `.u` file
  - any extracted UnrealScript source (`tools/pkgreader/scripttext.py` prints copyrighted Legend/Epic source; keep it local)
- **Our own work** — all `tools/`, `experiments/*/src`, harnesses, `VMProbe.uc` and the documents — was written from scratch. It contains no Epic or Legend source.
- **Third-party code** is used under its license: UELib (MIT) and capstone/pefile (via pip).
- A `.gitignore` is provided that excludes all of the local-only material.
- **Ownership:** Unreal II's IP is held by Epic Games, and the game was delisted from Steam and GOG in December 2022 (per PCGamingWiki). Any public project should ship only original code and require users to supply their own game files.
