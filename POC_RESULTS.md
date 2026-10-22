# Proof-of-concept results

Every experiment used the **real Unreal II files** of the installed GOG Special Edition. Original binaries were executed **only** from the sandbox copy (`sandbox/System`); the install itself was never written. Numbers are copied from tool output captured during the investigation (2026-10-22).

Each experiment answers seven questions: what was attempted, which artifacts were used, what compiled or ran, how correctness was established, what failed, what the result proves, and what it does not prove.

---

## E1 — Independent package reader: table layer

**Attempted.** Read the header, name, import and export tables of every package from scratch (`tools/pkgreader/upkg.py`), then check them against strong invariants.

**Artifacts.**
- Single player: 324 packages (`.u .un2 .utx .usx .uax .upx .ugx`), 1,670,554,353 bytes.
- XMP: 210 packages, 516.6 MB.
- The DLL export lists from `tools/pe`.

**Executed.**

```bash
python tools/pkgreader/validate_tables.py <game>/singleplayer --symbols out/symbols_sp
```

```bash
python tools/pkgreader/validate_tables.py <game>/multiplayer --symbols out/symbols_mp
```

**Correctness established by:**
1. Every table parses and ends exactly where the next region begins.
2. Header + names + imports + exports + all export payloads cover **every byte of every file**, with no overlaps: 0 gap bytes in both editions.
3. Every object reference is in range.
4. Cross-package resolution. Each import must name an existing export with the same outer path *and* class, or a C++-only class present in the matching DLL's export table.

**Results.**
- **Single player:** 0 parse failures, 0 table problems, 0 unaccounted bytes. That covers 240,898 names, 27,102 imports and 207,641 exports.
- **Imports, single player:**
  - 23,568 resolve to script or content exports.
  - 1,185 resolve to 44 intrinsic C++ classes, all found in the DLLs.
  - 7 are left unresolved by the checker:
    - 6 are stale references in old particle packages: to `U2Weapons.ImpactSounds.BulletWood01` and to the removed classes `ParticleSystems.AnimatedParticleTemplate` and `MultiSprite3DParticleTemplate`.
    - 1 is `Engine.PendingLevel`, an intrinsic class that the member-export heuristic misses; it is registered via `autoclassUPendingLevel`.
- **XMP:** 0 gaps. 29 imports point at texture packages that XMP does not ship.

**Failed.** Nothing in the table layer.

**Proves.**
- The container format of all three Unreal II package generations present (83, 110, 123/126) is fully understood at table level.
- Cross-package linkage of the shipped data is internally consistent.
- The C++-only class set that a reimplementation must register is enumerated.

**Does not prove.** Anything about object *payload* semantics; that is covered in E2 and E7.

---

## E2 — Object layer and bytecode tokenizer

**Attempted.**
- Parse every script field object: Class, State, Function, Struct, 10 property kinds, Enum, Const and TextBuffer.
- Tokenize all UnrealScript bytecode. Compute the on-disk and in-memory offsets of every token.

**Artifacts.** All single-player packages: **35,411 field objects**.

**Executed.**

```bash
python tools/pkgreader/validate_objects.py <game>/singleplayer
```

**Correctness established by:**
- **O1.** Each object's parse must consume *exactly* its serialized size.
- **O2.** Each token stream must end exactly at `ScriptSize`, measured in memory, with compact indices expanded to 4-byte pointers and names. Every Jump, JumpIfNot, Case, Iterator and label target must land on a token boundary.
- **O3.** Every Context, ClassContext and Skip size operand is compared with the independently computed in-memory size of the expression it guards.

**Results.**
- **O1:** 35,411 / 35,411 exact, 0 exceptions.
- **O2:** 8,666 bytecode bodies, 971,044 bytes in memory and 746,490 on disk. Every target lands on a token boundary.
- **O3:** consistent except in **83 structs**, where Unreal II's compiler emitted skip operands that disagree with the guarded expression. The cases involve `BoolVariable` and `LineNumber`-wrapped calls with parameters. Disassembling the original `UObject::execContext` shows the operand is used literally on "Accessed None", so these are latent bugs in the shipped game, not parser errors.
- **Legend deviations established along the way:**
  - the UClass leading reference list;
  - the extra UStruct int32;
  - the property flags `0x02000000` (description string) and `0x40000000` (three int32s);
  - the token set, including LineNumber, RangeConst and DebugInfo, and the absence of delegates.

**Failed.**
- The first passes failed on exactly these deviations. Each was resolved only when its correlation held for **all** objects.
- XMP's v126 layout differs: 17,837 of 25,166 objects parse with the v110 parser. XMP is out of scope.

**Proves.** The script-bearing half of the data model is fully recoverable. A port can load the original bytecode without UnrealEd or the original DLLs.

**Does not prove.** That the token *semantics* are right. That is E3 and E5.

---

## E3 — Native interface recovered from machine code and cross-checked against script

**Attempted.** Rebuild the VM's real opcode table and the native-index table from the shipped DLLs instead of assuming stock UE2. Then cross-check them against every `native` function declared in the packages.

**Artifacts.** `Core.dll`, `Engine.dll`, `Legend.dll`, `ParticleSystems.dll`, `U2*.dll`, `UI.dll`, `IpDrv.dll`, `UWeb.dll`, `Editor.dll` and all System `.u` files.

**Executed.**
- `tools/pe/natives.py` decodes every `GRegisterNative` call site, using capstone to read the pushed index and the `int<Class>exec<Func>` reference.
- In Core.dll the registrations are inlined as stores into the exported `GNatives` and `GCasts` arrays; those are decoded the same way.
- `tools/pkgreader/crosscheck_natives.py` performs the cross-check.

**Results.**
- **Opcode map, as registered in Core.dll:** `00–02, 05–0B, 0D–17, 19–2A, 2C–2F, 32–39, 40–42`, plus `60–6F` for extended natives.
  - 0x15 is `execLineNumber`, 0x35 `execRangeConst` and 0x42 `execDebugInfo`.
  - There are no delegate opcodes.
  - `Return` (0x04), `LabelTable`, `Skip` and the IteratorPop/Next tokens are handled inline by the interpreter loop rather than registered.
- **Casts:** 32 casts, 0x39–0x59, with no 0x46. This is the stock UE1/UE2 `ECastToken` layout.
- **Native counts:** 723 native script functions, 277 numbered and 446 name-bound.
- **N1, numbered natives:** 260 / 277 have a registration at the same index whose implementation is named `<Prefix><Class>::exec<Name>`.
  - 12 register under a different C++ name, for example `Concat_StrStr` is implemented by `execConcat_StringString`, and `AtEqual_FloatRange` by `execColonEqual_FloatRange`.
  - **5 (`ScriptedTexture` natives 472–476) have no implementation in any shipped DLL.**
- **N2, name-bound natives:** 446 / 446 have the exported binding symbol.
- **N4, natives called from bytecode:** all 213 native indices called from shipped bytecode are registered.

**Failed.** The first decoder found only 9 Core registrations, because they are inlined. Recognising the inlined `mov [GNatives+4*i], reg` stores fixed it.

**Proves.**
- The script↔C++ boundary is enumerated exactly: opcodes, casts, and every native's index, name and owning class, matched to C++ symbols with full signatures.
- It is the precise specification a native reimplementation must satisfy.

**Does not prove.** The behaviour of any native, except for the subset tested in E5.

---

## E4 — The original engine as an oracle (sandboxed UCC)

**Attempted.** Use the original engine without touching the install, to produce ground truth.

**Artifacts.** A copy of `singleplayer\System` (34 MB) in `sandbox/System`.

**Executed.**
- `tools/run_ucc.ps1 help`, which lists commandlets including `make` and `batchexport`.
- `HelloWorld`.
- `make -ini=VMProbe.ini`: the **original Unreal II compiler** compiled our own `experiments/vmprobe/VMProbe/Classes/VMProbe.uc`. It reported 0 errors and 1 warning.
- `VMProbe.VMProbe`, `Core.SimpleCommandlet` and `Core.ArrayTest`.

**Correctness established by.** Engine banner and log: `Version: 2001`, `Compiled: Mar 14 2003 13:18:30`. The commandlets produced the expected output.

**Observations.**
- Starting the engine **rewrites `System\Golem.u`**, which explains the 2024 timestamp in the real install. Running from a copy is therefore necessary.
- The compiler enforces U2-specific rules, for example "Function 'Main' specifiers differ from original" and "Cast … is unnecessary".

**Proves.** Arbitrary UnrealScript can be compiled by the original toolchain and executed by the original VM, headless. That gives a reusable differential-testing oracle for any script-level reimplementation work.

**Does not prove.** Anything about rendering or game-time behaviour, which needs the full client and maps.

---

## E5 — Independent C++ UnrealScript VM, differential-tested on three platforms

**Attempted.** Execute **original Unreal II bytecode** in an independent VM written from scratch: `experiments/uvm`, C++17, about 1,860 lines, no Epic or Legend code. The VM:
- loads the real `Core.u` (and `VMProbe.u`);
- links classes, structs, properties and defaults (including tagged default arrays);
- decodes bytecode into token trees;
- interprets them with 116 Core natives (114 by index, 2 by name) and 29 of the 32 casts.

**Artifacts.**
- **Shipped Core.u commandlets:** `HelloWorldCommandlet`, `SimpleCommandlet`, and **`ArrayTest`**, Epic/Legend's own dynamic-array test.
- **Our probe:** `VMProbe.u`, 54 deterministic tests compiled by the original compiler. They cover:
  - integer and float arithmetic, including overflow, shifts, `>>>`, and `*=` and `/=` with float operands;
  - float32 formatting (`123456789.0` → `123456792.000000`);
  - byte wraparound;
  - strings (`Mid`, `Left`, `Right`, `InStr`, `Caps`, `Locs`, `Chr`, `Asc`, comparisons, `~=`) and string→int/float/bool parsing;
  - Legend's `Split`;
  - names and name switches;
  - control flow: `for`, `while`, `do..until`, `switch` with fall-through, `break` and `continue`;
  - recursion, static functions, `out` and optional parameters, short-circuit `&&`/`||` with side effects;
  - vectors (dot, cross, `VSize`, `Normal`, `==`) and rotators (`string(rotator)` normalises modulo 65536);
  - dynamic arrays (growth on write, `Insert`/`Remove`), static arrays, struct copy and comparison;
  - defaults, `ClassIsChildOf`, `IsA`, dynamic casts, and `Class.Name`.

**Executed.**
- **Windows x64 (MSVC 14.51):** `experiments/uvm/build_msvc.cmd x64`, then the comparisons.
- **Linux x86-64 (GCC 13.5):** `docker run gcc:13 … run_linux_tests.sh linux-x64`.
- **Linux ARM64 (GCC 13.2, musl, QEMU):** `docker run --platform linux/arm64 alpine:3.20 … run_linux_tests.sh linux-arm64`.

**Correctness established by.** References captured from the original engine: the probe's stdout, and the `UCC.log` `ScriptLog:` and `ScriptWarning:` lines for the shipped commandlets. These are compared line by line with the VM's output.

**Results.** 74 / 74 output lines identical on all three platforms:

| Program | Lines identical to the original engine | Notes |
|---|---|---|
| VMProbe (ours, original-compiled) | **54 / 54** | 21,566 interpreter steps |
| Core.HelloWorldCommandlet (shipped) | **2 / 2** | |
| Core.SimpleCommandlet (shipped) | **9 / 9** | |
| Core.ArrayTest (shipped) | **9 / 9** | Includes the original's exact warning text *and bytecode offsets*, e.g. `(Function Core.ArrayTest.RegularTests:0090) Accessed array 'TestArray' out of bounds (5/2)`, and all of ArrayTest's internal `assert`s passing |

**Timing:**
- Release x64: VMProbe takes 8.4 ms to load and link Core.u plus VMProbe.u, and 1.17 ms to run.
- The ARM64 numbers were taken under QEMU emulation and say nothing about native performance.

**Semantics discovered and matched**, all confirmed against the original:
- **Dynamic-array growth.** An out-of-bounds element grows the array **only when it is the direct assignment target**. Reached through a struct member or used as a read, it warns and yields no address. This mirrors `Result==NULL` in the original.
- **`Remove` past the end** warns and still removes whatever exists.
- **Warning code offset** equals the end of the token being executed. For `Accessed None` it is the end of the object expression.
- **Assign-through-None** in Unreal II is printed with a timestamp and `(line N)`, using Legend's `LineNumber` tracking. The timestamp is non-deterministic and is normalised in the comparison.

**Failed.**
- The first build crashed through stack exhaustion. It recursed through the `next` chain of 1,000 fields; lazy field linking fixed it.
- One ArrayTest warning line carries a wall-clock timestamp, so exact comparison needs normalisation.

**Proves.**
- Original Unreal II gameplay bytecode can run **bit-exactly outside the original engine, on ARM64 as well as x86-64**, given a correct object model.
- The VM semantics are recoverable to the level of error messages and code offsets.
- This is the core of the hybrid architecture.

**Does not prove.**
- **Not exercised yet:** states and latent actions, timers, iterators (`foreach`), replication, and actor and level natives (Engine).
- **Scale:** 116 of 723 natives are implemented.
- **Performance:** nothing about performance under real game load.

---

## E6 — Static x86→C lifting of real Core.dll code, differential-tested on three platforms

**Attempted.** Translate real machine code from the original `Core.dll` into portable C with an automatic, function-level lifter (`tools/lift/lift_x86.py`, about 500 lines). The lifter is capstone-based:
- explicit CPU state;
- paged guest memory, with the DLL's sections mapped at their original addresses;
- an x87 register stack that honours the FPU control word's rounding mode;
- lazily computed EFLAGS;
- host thunks for CRT imports.

The lifted output is then compared bit-for-bit with the original DLL.

**Artifacts.**
- **Original routines, from the export table:** `appMemCrc`, `appStrCrcCaps`, `appMD5Transform`, `appBlend(float)`, `appAblend(float)`, `appRound`, `appFloor`, `appCeil`, `appSRandInit` and `appSRand`.
- **Pulled in transitively:** the internal `appStrlen` thunk and the statically linked CRT **`_ftol2`** (x87 + int64 + compare/branch).
- **Size:** **13 functions, 1,026 instructions**.
- **Features exercised:** 8/16-bit partial registers, `rep stosd`, `adc`, `leave`, x87 `fld`/`fild`/`fistp`/`fst`/arithmetic/`fxch`, tail calls through the import table, and global state (`GSRandSeed`, `GCRCTable`).

**Executed.**
- **Original side:** a 32-bit harness (`harness_original.c`, MSVC x86) `LoadLibrary`s the original `Core.dll` from the sandbox and calls the exports through `GetProcAddress`.
- **Lifted side:** a portable harness (`harness_lifted.c` + `lifted_core.c`) built with MSVC x64 (`/fp:strict`), GCC 13.5 on x86-64, and GCC 13.2 on **ARM64**, each with both `-ffp-contract=off` and `=fast`.
- **Inputs:** both sides use an identical deterministic generator. Each of the five test families runs 20,000 random cases (`memcrc`, `strcrccaps`, `md5`, `blend`/`ablend` and `round`/`floor`/`ceil`), plus a 2,000-value `appSRand` sequence:
  - random buffers and wide strings;
  - MD5 states and blocks;
  - floats including exact .5 halves, negatives and raw bit patterns.

**Correctness established by.** Byte comparison of the 102,000 result lines, with line endings normalised. The outputs are non-trivial: for example 20,000 / 20,000 distinct MD5 and blend values.

**Results:**

| Target | Compiler | Result |
|---|---|---|
| Windows x64 | MSVC 14.51 | **IDENTICAL** (102,000 lines) |
| Linux x86-64 | GCC 13.5, FP contraction off and fast | **IDENTICAL** |
| Linux ARM64 (QEMU) | GCC 13.2, FP contraction off and fast | **IDENTICAL** |

**Coverage probe.** How many exported functions can be lifted, looking only at each function's own body, with *this minimal* instruction subset and no indirect-call dispatcher:

| Module | Liftable / exported entry points | Main blockers |
|---|---|---|
| Core.dll | 1,266 / 2,088 (**60.6%**) | Indirect calls (541), SEH `fs:` frames (250) |
| Engine.dll | 2,519 / 4,818 (**52.3%**) | Indirect calls (~1,300), SEH (945), jump tables (30) |
| GlmLib.dll | 1,393 / 2,543 (**54.8%**) | Indirect calls (~940), SEH (176), `fsin` and others |
| D3DDrv.dll | 6 / 27 (22%) | Indirect (COM / D3D vtable) calls |

**Failed.**
- Each first attempt stopped on an unsupported construct: `adc`, `leave`, `rep stosd`, and a `jmp [IAT]` thunk.
- The CRLF-versus-LF line-ending artefact initially made every Linux line differ. It was not a semantic difference.

**Proves.**
- Real MSVC 7.0 Unreal II machine code, x87 included, can be mechanically translated into portable C that is **bit-exact on x86-64 and ARM64**.
- The 32-bit "load the original DLL and call its exports" harness works as an oracle for any native function.
- What blocks full-program recompilation is now measured: vtable and indirect calls, pervasive SEH, jump tables, and the DirectX/COM/Win32 imports. All are known problems for which other projects have solutions.

**Does not prove.**
- Lifting of code with indirect calls, SEH or jump tables. Lifting of whole modules, or of anything that touches D3D8, DirectMusic or Win32.
- That 80-bit x87 edge cases match. The model is the Windows default 53-bit precision. Exponent range, denormals and `fild` of integers wider than 53 bits are not modelled.
- Anything about performance.

---

## E7 — Existing tools, content payloads, proprietary formats, saves and runtime state

**E7a. UELib (EliotVU/Unreal-Library, MIT), tested on this build.**

UELib was built from source: commit 8236c39, .NET 10, with git versioning disabled because the clone is shallow. The harness is `experiments/uelib_test`.

- **Package loading:** all 321 single-player packages load.
- **Build detection:**
  - licensee 2481 and 2609 are detected as `Unreal2`, matching UELib's `[Build(110,110,2481,2609)]` entry;
  - **licensee 1331 and 1585 (25 particle packages) are detected as `Unknown`**.
- **Forced deserialization of all 207,568 exports:** 24 exceptions, and **109,719 objects with unparsed trailing bytes**. These include nearly every actor (the Unreal II 4-byte `AActor` tail from E7b), the Legend property extras, and some array defaults.
- **Decompilation:** `Decompile()` ran on all 1,317 classes with 0 exceptions. *Textual correctness was not verified.*
- **Proves:** UELib is a strong starting point for script browsing and decompilation.
- **Does not prove:** fidelity for content objects. UELib is C# and Windows-oriented, and is not a runtime.

**E7b. Content payload survey.** Tool: `tools/pkgreader/content_survey.py`.
- **Generic layer:** 172,157 single-player content objects (1,618 MB) were parsed through the state frame and tagged properties with 0 failures.
- **Native payloads:** **253 classes carry native payloads totalling 1,603 MB**. The largest are Texture (708.5 MB), StaticMesh (374.5 MB), Sound (328.2 MB), Model (86.5 MB) and StaticMeshInstance (54.5 MB).
- **Actor tail:** every actor ends with 4 bytes after its properties (0 in all samples).
- **Proves:** which classes need native loaders, and how much data each covers.
- **Does not prove:** the decoding of those payloads.

**E7c. Golem.** All 226 `.gem` files share one structure: `LGEM` v1, a size field equal to the file length, and 5 section entries with valid offsets. GlmLib's 2,838 exports name the reader classes (`RGemFile`, `RGemModel`, `RGemTrianglesData`, `RGemBoneHierarchy`, `RGemRagdoll`, …). Not decoded.

**E7d. DirectMusic.**
- The 8 `.con` files hold 8 DirectMusic Scripts, 98 segments, 444 tracks and 97 waves (95 MS-ADPCM).
- Engine.dll strings confirm DirectMusic and the script loading.
- **External:** GothicKit/dmusic is MIT and explicitly incomplete, with no stated script or container support. Wine has partial dmime/dmscript. ProtonDB reports deleting `.con` files as a launch workaround, which implies music failures under Wine.

**E7e. Saves.** `Save7.usa`, read-only, is a v110/2609 package with 807 exports, 323 imports and **0 gap bytes**. It is a full level snapshot.

**E7f. Runtime state.** The user's last real session log (2024-09-18):
- D3D8 initialised on the RTX 3070, along with Karma, DirectMusic and the intro map;
- the session then ended with `CreateDevice failed (D3DERR_DEVICELOST)` while switching to fullscreen.

So the original game does **not** currently run cleanly on this machine without a compatibility fix. The full graphical game was **not** launched during this investigation, to avoid changing display modes on the user's desktop or touching the install's ini files.

---

## Summary of what is demonstrated versus speculative

**Demonstrated here, with real data and an oracle:**
- complete package and script decoding;
- exact native-interface specification;
- an independent VM that is bit-exact against the original on x64, Linux and ARM64;
- static lifting of real x86/x87 engine code that is bit-exact against the original on x64, Linux and ARM64;
- quantified coverage and blockers;
- a map of every content class that needs native loading;
- confirmation of the platform dependency surface: D3D8, DirectInput8, DirectMusic, OpenAL with EAX, and Win32.

**Not demonstrated (open):**
- rendering anything from Unreal II data;
- the Golem format or runtime;
- DirectMusic playback;
- Engine actor and physics natives;
- states and latent actions in the new VM;
- whole-module recompilation;
- running the full original game under any wrapper or emulator;
- performance on any target;
- anything on a real Android device.
