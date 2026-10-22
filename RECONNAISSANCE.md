# Reconnaissance: Unreal II executables, packages and file formats

Everything below was measured on the installed game, read-only, on 2026-10-22, unless it is marked *external*. Raw outputs are in `out/` (local only).

## 1. Environment and installation

**Host machine.**
- **Hardware and OS:** Intel i7-14700K (28 threads), 63.7 GB RAM, Windows 11 Enterprise 10.0.26300.
- **Free disk:** 315 GB on E:, 124 GB on C:.

**Toolchain present.**
- **Microsoft:** Visual Studio Community 2026 (18.10) with MSVC 14.44 and 14.51, x86 and x64 targets, but no ARM64 target. Windows SDK 10.0.26100.
- **Runtimes:** Python 3.14.5, .NET SDK 10.0.402, Java 17, Node, Git.
- **Containers:** Docker 29.7.2 on WSL2, with QEMU user emulation for `linux/arm64` (verified: `uname -m` reports `aarch64`).
- **Not present:** Ghidra, IDA, MinGW, clang, cdb, and the ASan runtime.

**Game install.** GOG *Unreal 2 - The Awakening Special Edition* (`gameId 1207658677`), at `E:\Launchbox\Games\PC Games\Unreal 2 - The Awakening`.

| Part | Contents |
|---|---|
| `singleplayer\` | The campaign. Launched via `System\Unreal2.exe`. |
| `multiplayer\` | **XMP** (eXpanded MultiPlayer). Launched via `SYSTEM\U2XMP.exe`. A separate, newer engine build; see §7. |
| `singleplayer\Save` | A **junction** into Proton Drive holding 10 pinned `.usa` saves dated March 2022. Treated as read-only. |
| `goggame-1207658677.dll` | GOG Galaxy stub, linked with VC 9.0 (2015). It is not part of the game. |

**Single-player content by type:**

| Ext | Files | MB | What it is |
|---|---:|---:|---|
| `.utx` | 57 | 662 | Unreal texture packages |
| `.usx` | 35 | 342 | Static-mesh packages |
| `.uax` | 77 | 311 | Sound packages |
| `.un2` | 47 | 226 | Maps. These are Unreal packages; the extension is specific to Unreal II. |
| `.ogg` | 1919 | 206 | Voice-over (Ogg Vorbis) |
| `.con` | 8 | 84 | **DirectMusic containers** (RIFF `DMCN`) for adaptive music |
| `.dds`/`.tga` | 281/44 | 74/23 | Golem mesh textures (external image files) |
| `.gem` | 226 | 61 | **Golem** skeletal meshes (`LGEM` v1) |
| `.upx` | 4 | 36 | Prefab packages (package version 83) |
| `.u` | 100 | 17 | Script packages (System and ParticleRes) |
| `.ugx` | 5 | 0.06 | Unreal packages of `LegendMesh` objects that point to `.gem` files |
| `.u2s` | 1028 | 0.9 | Plain-text actor and level scripts, run by native code in U2AI |
| `.dlg` | 215 | 0.7 | Plain-text INI-style dialog trees, run by U2Dialog |
| `.ui` | 17 | 0.2 | Text UI scripts, run by the Legend UI module |

## 2. Executables and native modules (single-player `System`)

**Toolchain.** Every runtime module is a 32-bit x86 PE built with **Visual C++ .NET 2002**.
- **Rich header:** `Utc13_C/CPP` and `Linker700` build **9466** (13.00.9466). It also contains some objects from VC6.0 build 8943/9044 (likely third-party static libraries) and from pre-release VC7 builds 8830/9178.
- **C runtime:** `msvcr70.dll` and `msvcp70.dll`.
- **TCHAR:** `unsigned short`, so this is a Unicode build. The mangling uses `G`, i.e. without `/Zc:wchar_t`.

**Build identity.**
- **Timestamp:** all engine and game modules carry PE timestamps of **2003-03-14 18:19–18:27 UTC**.
- **Engine log:** `UCC.log` reports `Version: 2001` and `Compiled: Mar 14 2003 13:18:30`.
- **Codeline:** PDB and assert paths read `c:\Unreal2\U2_829\...`, a Legend codeline named after Epic build 829.
- **GlmLib:** built separately on 2002-12-16 from `c:\Dev\Unreal2\Golem\Src\Kernel\Release\GlmLib.pdb`.

**Modified launcher.** `Unreal2.exe` has a nonsensical timestamp, `0x21544C46` (1987-09-20). Its Rich header shows the same toolchain, so the executable was probably post-processed, for example by the publisher or GOG. Every other module has a plausible timestamp.

**Optional headers.** No module has `/GS`, ASLR, NX or SafeSEH flags (`DllCharacteristics=0`). Relocations are present in the DLLs and stripped from the EXEs. No module uses TLS.

| Module | Code (KB) | Exports | Native classes (`autoclass*`) | Notable imports |
|---|---:|---:|---:|---|
| `Unreal2.exe` | 84 | 1 | – | Window, Core, Engine, DDRAW (`DirectDrawCreate`), DBGHELP (crash stack walk) |
| `Core.dll` | 419 | 2680 | 35 | WINMM timers, vorbisfile, ole32 (`CoCreateGuid`) |
| `Engine.dll` | 2059 | 6132 | 226 | Core (751), **GlmLib (82)**, ole32 `CoCreateInstance` (**DirectMusic**), GDI (fonts) |
| `D3DDrv.dll` | 116 | 32 | 1 | **d3d8 `Direct3DCreate8`**, **GlmLib (28: Golem materials and shaders)** |
| `WinDrv.dll` | 38 | 84 | 2 | **DINPUT8 `DirectInput8Create`**, IMM32, USER32 |
| `ALAudio.dll` | 37 | 49 | 1 | Core, Engine, vorbisfile. OpenAL is loaded dynamically (`DefOpenAL32.dll`, EAX 3.0). |
| `GlmLib.dll` (Golem) | 2145 | 2838 | – | d3d8, DINPUT, WS2_32, dbghelp, comdlg32, COMCTL32. Both runtime and editor. |
| `ParticleSystems.dll` | 379 | 1965 | 89 | Core, Engine |
| `UI.dll` | 592 | 1621 | 3 | Core, Engine |
| `U2Dialog.dll` | 224 | 299 | 10 | Core, Engine, UI |
| `Legend.dll` | 30 | 236 | 15 | Core, Engine |
| `U2.dll` / `U2AI.dll` | 25 / 16 | 123 / 48 | 6 / 2 | Core, Engine, UI, ParticleSystems |
| `Fire.dll`, `IpDrv.dll`, `UWeb.dll` | 46 / 65 / 12 | – | 7 / 10 / 2 | WSOCK32 (IpDrv) |
| `Window.dll`, `Editor.dll`, `UnrealEd.exe` | – | – | 1 / 49 / 24 | Editor only, not needed for the game |
| Third-party | | | | `ogg`/`vorbis`/`vorbisfile` (VC7), `DefOpenAL32.dll` (Creative OpenAL 0.990, VC6), `encvag.dll` (Sony VAG encoder, 1999; console tooling), `DbgHelp.dll` |

Exports are full C++ decorated names. Undecorated, they give **~18,000 symbols** with class, method and signature: Core 123 classes, Engine 384, GlmLib 148, ParticleSystems 136, UI 81, Window 321, and so on. This is an unusually rich map for a stripped retail game.

**RTTI** is compiled out: only 1–11 `.?AV` type descriptors per module. However, **vtables are exported by name**: Core 61, Engine 312, GlmLib 142, UI 77. Engine also exports 151 `event*` script-call wrappers, 240 across all modules.

**Engine.dll compared with UT2004** (the reference UE2 install on this machine, build 3369):
- **Shared:** 315 classes.
- **Unreal II only:** 69 classes, such as `ULegendMesh`/`ULegendMeshInstance`, `ALicenseePawn`/`ALicenseeController`, `ACoverVolume`/`ACoverPoint`/`ACoverSpot`, `AScriptedLight`, `UTextureArray`, `URenderTarget`, `AMusicScriptEvent`, `FLineManager`, `ADecal` and `UShadowBitmapMaterialFallback`.
- **UT2004 only:** 166 classes. This is consistent with an **older** UE2 branch plus Legend features.
- **Core (Unreal II only):** a Loki small-object allocator, `FTimerManager`, the `FExecDispatch`/`FExecVar` command system, and `FFileStream`.

### Code characteristics relevant to recompilation

Measured with `tools/pe/code_stats.py`, a linear sweep that is approximate where data sits inside `.text`, over the 17 runtime modules:

| Metric | Value |
|---|---|
| Code bytes / instructions | 6.59 MB / **~2.27 M** |
| x87 FPU instructions | **184,534** (8.1%). Engine 77k, GlmLib 85k. |
| SSE / MMX / 3DNow! | 983 / 1,665 / 30. Almost all in GlmLib. |
| Calls | 140,857 total. 66,320 direct, 43,696 to imports, **30,132 indirect via register or vtable**, 709 via global function pointers. |
| Jump tables / other indirect jumps | 186 / 240 |
| `fs:` accesses (SEH frame setup) | **23,665**. UE `guard`/`unguard` uses C++ EH in nearly every function. |
| EH imports | `__CxxFrameHandler`, `_CxxThrowException` and `_except_handler3` in every module. Engine and GlmLib also use `_setjmp3`/`longjmp`. |
| FPU control-word ops in `.text` | 78, in GlmLib |

## 3. Unreal package format (Unreal II branch)

| Population | Package version / licensee | Count |
|---|---|---|
| Single-player `.u` (System) | 110 / **2609** | 26 |
| Single-player content: maps, textures, sounds, meshes, most ParticleRes | 110 / **2481** | 254 |
| Single-player old particle packages | 110 / **1331** and 110 / **1585** | 18 + 7 |
| Single-player `.ugx`, 5 maps, Golem texture packages | 110 / 2609 | 16 |
| Prefabs `.upx` | **83** / 635 and 83 / 763 | 4 |
| XMP | 123 / 0 and **126 / 0** (plus 23 single-player-era 110 packages) | 210 |

Legend apparently used the licensee field as a running format number. The format is the standard UE1/UE2 layout:
- **Header:** 64 bytes, with a GUID and one generation entry.
- **Name table:** at offset 64, as length-prefixed strings followed by flags.
- **Import and export tables:** at the end of the file.
- **Object data:** compact-index serialization.

The independent reader in `tools/pkgreader` is checked as follows (details in POC_RESULTS E1/E2):

- **Tables.**
  - **Single player:** 324 packages and **1,670,554,353 bytes**. Every byte is accounted for by header, tables and export payloads (0 gap bytes). That covers 240,898 names, 27,102 imports and 207,641 exports.
  - **XMP:** 210 packages, 516.6 MB, 0 gap bytes.
- **Import resolution.**
  - 23,568 imports resolve to an export with the same path and class.
  - 1,185 imports name **44 C++-only classes** (`Core.Class`, `Engine.Level`, `Engine.Model`, `Engine.Polys`, `Engine.StaticMeshInstance`, `Engine.LegendMesh`, `Engine.RenderDevice`, ...), all present in the DLL exports.
  - 7 imports are left unresolved by the checker:
    - 6 are stale references inside old particle packages to `U2Weapons.ImpactSounds` and to removed `ParticleSystems` template classes.
    - 1 is `UPendingLevel`, which is in fact an intrinsic class registered via `autoclassUPendingLevel`.

### Unreal II deviations from stock UE2 serialization

These were found from the data and confirmed by exact byte consumption across all packages:

1. **`UClass` objects start with a counted list of object references** instead of a tagged-property block. The references are properties, e.g. `Pickup` lists `Actor.bHidden`, `Actor.Rotation` and `Actor.Velocity`. UELib calls this list `u2NetProperties`.
2. **`UStruct` has an extra int32** between `TextPos` and `ScriptSize`. It is 0 in 10,067 structs and 1 in 26.
3. **`UProperty` flag `0x02000000`** appends an FString description, e.g. `U2ZoneInfo.LocationDescription`.
4. **`UProperty` flag `0x40000000`** appends three int32s, e.g. `Pawn.Health` = (0, 255, 1), which looks like an editor range.
5. **Every `AActor` has 4 extra bytes** after its tagged properties. They were 0 in every sample. This explains UELib's ~110k objects with unparsed bytes.
6. **Bytecode tokens.** The VM token set was recovered from Core.dll's registration code (see §5):
   - **Added:** `EX_LineNumber` (0x15, a word line number followed by an expression), `EX_RangeConst` (0x35, two floats), `EX_DebugInfo` (0x42).
   - **Missing:** there are **no delegate tokens**, unlike UT2004.
7. **Script packages embed their UnrealScript source** (`ScriptText`, 1,317 `TextBuffer`s). This made source-level validation and the probe experiments possible. The source is copyrighted and kept local.
8. **83 functions (0.8%) carry `Context` skip operands that do not match the guarded expression size.** Examples are `Outer.bStasis` (5 vs 6) and `Outer.FormatFloat(...)` (5 vs 86). Disassembling the original `UObject::execContext` (`Core.dll` 0x10126910) shows the skip is used literally after "Accessed None", so these are latent bytecode bugs in the shipped game.

### Script and native inventory (single-player System)

- **Script objects:** 1,317 classes, 8,245 functions, 405 states, 126 structs, 121 enums, 824 consts and about 23,000 properties, for **35,411** field objects in total.
- **Bytecode:** 8,666 bodies, 971,044 bytes in memory and 746,490 on disk.
- **Native functions declared in script:** **723**. 277 are bound by index and 446 by name (resolved through the exported `int<Class>exec<Name>` symbols).
- **VM opcodes:** 70 registered (0x00–0x42 plus 0x60–0x6F), and **32 primitive casts** (codes 0x39–0x59, with no 0x46).
- **Natives registered in the DLLs:**

| Module | Natives |
|---|---|
| Core | 249 numbered (including opcodes) + 48 by name |
| Engine | 92 numbered + 257 by name |
| ParticleSystems | 2 numbered + 39 by name |
| UI | 26 |
| IpDrv | 22 |
| U2Dialog | 21 |
| Editor | 14 |
| Legend | 10 |
| UWeb | 9 |
| U2 | 6 |
| U2AI | 1 |

- **Unimplemented natives:** `Engine.ScriptedTexture` declares natives 472–476, but *no shipped DLL contains a `UScriptedTexture` implementation*. UT2004 has one.
- **Core.Object additions** (252 functions): a `Range` type with its own operators, timers (`AddTimer`/`RemoveTimer`), reflective `CallFunction`/`DefinesFunction`, `Split`, `StrArray`, `EnumStr`, `Blend`/`Ablend`, `ProgressSeed`, `FDecision`, and the script-implemented `?`/`!` truthiness operators on vectors, strings, objects and other types.

### Content objects (non-script exports)

Single player: **172,157 objects, 1,618 MB**. The generic object layer (state frame plus tagged properties) parses for all of them, with 0 failures or overruns. **253 classes** carry native binary payloads after their properties, totalling 1,603 MB:

| Class | Native MB |
|---|---:|
| Texture | 708.5 |
| StaticMesh | 374.5 |
| Sound | 328.2 |
| Model (BSP) | 86.5 |
| StaticMeshInstance | 54.5 |
| TerrainInfo | 23.6 |
| Polys | 11.7 |
| TextureArray (Legend) | 5.2 |
| Legend particle templates | several MB |
| TerrainSector, Palette, Font, Level, ConvexVolume | smaller |

79 classes are fully described by tagged properties. See `out/content_survey_sp.json`.

## 4. Proprietary Legend formats

**Golem** (`GlmLib.dll`, `.gem`, `.ugx`, `U2.gws`):
- **Files:** all **226 `.gem` files (64.4 MB) start with `LGEM`, version 1, and a size field equal to the file size, followed by exactly 5 (count, offset) section entries.** They are self-describing but not yet decoded.
- **Unreal-side references:** `.ugx` files are ordinary Unreal packages (110/2609) of `LegendMesh` objects that refer to Golem assets by name. `U2.gws` is an INI-style Golem workspace (`RootFolder=..\Meshes`).
- **Textures:** loaded from loose `.dds`/`.tga` files.
- **GlmLib exports:** 148 C++ classes in namespace `GLM`:
  - `RGem*` resources: File, Model, TrianglesData, BoneHierarchy, Materials, LodInfo, **Ragdoll**, Scripts, Blueprint.
  - `A*` "abilities" (behaviour scripts).
  - `W*` editor windows.
  - `RVss*`, Visual SourceSafe integration.
- **Engine linkage:** Engine's `ULegendMesh` and `ULegendMeshInstance` (103 exports) bridge to Golem. Karma `physKarma` and `physKarmaRagDoll` log *"This physics type is obsolete in U2 829"*, so ragdolls come from Golem.
- **External tools:** UE Viewer explicitly does not support Unreal II, and no Golem exporter is known.

**Adaptive music:** `.con` files are DirectMusic Containers. Engine.dll logs "Initializing DirectMusic…" and "Loading DirectMusic Script: %s…".
- **Contents across the 8 files:** 8 DirectMusic Scripts (`DMSC`, AudioVBScript), 98 segments, 444 tracks (including lyric/marker and wave tracks), and 97 embedded waves. 95 of the waves are MS-ADPCM stereo 44.1 kHz and 2 are PCM.
- **Last-run behaviour:** the user's last game log shows "Initializing DirectMusic…" and "Loading DirectMusic Script: Intro.Script1…".

**Text formats:** `.u2s` (event/trigger/goto command scripts), `.dlg` (INI conversations with speaker, text and sound references) and `.ui` are human-readable and straightforward to reimplement.

**Save games** (`Save<N>.usa`): ordinary Unreal packages (110/2609) that snapshot the whole level object graph. `Save7.usa` has 807 exports, 323 imports and 0 gap bytes. The architecture is the standard UE one, serializing the `ULevel` with `RF_HasStack` actor state frames. Compatibility therefore depends on the full native serialization of every actor class.

## 5. Native interface recovery method

1. The `int<Class>exec<Name>` exported variables point to the implementations.
2. Every `GRegisterNative` call site was disassembled. In other DLLs these go through the import address table. In Core.dll the call is inlined as stores into the exported `GNatives`/`GCasts` arrays.
3. The pushed index or store offset gives the token or native number.

Results are in `out/native_table_sp.json` and the opcode list is in POC_RESULTS E3. To reproduce:

```bash
.venv/Scripts/python -I tools/pe/natives.py sandbox/System/Core.dll sandbox/System/Engine.dll --out out/natives_sp
```

```bash
.venv/Scripts/python -I tools/pe/native_table.py out/natives_sp --opcodes --casts --json out/native_table_sp.json
```

## 6. Observed runtime state on this machine

`singleplayer\System\Unreal2.log`, the user's last session on 2024-09-18, read-only:
- **Hardware detected:** D3D8 on an **NVIDIA GeForce RTX 3070** (`nvldumd.dll`), reporting VS 1.1 and PS 1.4.
- **Startup:** Karma started, DirectMusic initialised, and map `CS_Intro` loaded with its DirectMusic script.
- **Crash:** after a series of window resizes, the session ended with:
  > `Critical: Error setting display mode: CreateDevice failed (D3DERR_DEVICELOST)`
- **Interpretation:** the original D3D8 renderer has the fullscreen-mode problem on modern Windows that PCGamingWiki documents (*external*).

The original engine also **runs headless** here: the sandboxed `UCC.exe` runs `HelloWorld`, `make` and our own commandlets (E4).

## 7. XMP (multiplayer)

- **Build:** a separate binary set built 2004-01-19 with the same VC7.0 toolchain.
- **Differences from single player:** no GlmLib (it uses standard UE2 `.ukx` skeletal animation); adds `Vehicles.dll`, `IFC23.dll` (force feedback), `libexpat` and an `openal.so` (Linux).
- **Packages:** versions 123 and 126 with licensee 0. Their struct and class layouts differ from single-player v110: the v110 object parser handles 17,837 of 25,166 XMP field objects, and structs and classes fail.
- **Scope:** XMP is a different engine generation and is out of scope here except for table-level parsing, which is clean.
