# Blockers and unresolved technical risks

**Severity scale:**

| Severity | Meaning |
|---|---|
| **H** | Must be solved for any native port |
| **M** | Significant effort or uncertainty |
| **L** | Bounded |

**Evidence labels:** [D] demonstrated in this workspace, [M] measured, [X] external, [S] speculation.

## Hard technical blockers

| ID | Blocker | Severity | Evidence | Affects | Mitigation |
|---|---|---|---|---|---|
| B1 | **Golem**: proprietary skeletal animation, mesh, material, ragdoll and "ability" system | H | [M] GlmLib.dll: 2.15 MB of code, 85k x87 instructions, 148 classes. 226 `.gem` files (`LGEM` v1, 5 sections, undecoded). Characters, creatures and weapons all use it. D3DDrv calls Golem materials and shaders directly. No external tool supports it (UE Viewer lists Unreal II as unsupported [X]). | A, D-R | **Lift GlmLib (B / D-B).** The exported `RGem*` reader classes are a strong starting point for format reverse engineering later. Much of GlmLib is editor-only, which narrows the scope. |
| B2 | **DirectMusic adaptive music**, including **AudioVBScript** scripts | H | [M] 8 `.con` DMCN containers: 8 DMSC scripts, 98 segments, 444 tracks, 97 waves (95 MS-ADPCM). Engine drives it through COM. [X] No complete open implementation: GothicKit/dmusic (MIT) is incomplete with no stated script support, and Wine dmime/dmscript is partial. Proton users delete `.con` files to start the game. | All, including C under Wine | Implement only the DirectMusic subset these 8 containers use. First enumerate the track types and script calls actually present. Fallback: offline-render stems and drive transitions from `MusicScriptEvent` (loses fidelity). |
| B3 | **Direct3D 8 renderer** (fixed function, VS 1.1 / PS 1.4) plus Legend render iterators | H | [M] `Direct3DCreate8` in D3DDrv and GlmLib. System D3D8 and d3d8to9 fail HAL caps with D3DERR_NOTAVAILABLE on this machine. dgVoodoo2 2.87.5 x86/D3D11 now lets the original complete CS_Intro LoadMap, tick that selected world and create/present its game device; visual/input play is unverified. The translated client enters UGameEngine::Init and UWindowsClient::Init, then stops at DirectInput8Create before LoadMap (experiments/xrt/GRAPHICS_STARTUP.md). | All non-Windows targets; Windows legacy D3D8/D3D9 path | Short term: a D3D8 wrapper (C). B/D-B: HLE through DXVK's D3D8 frontend (zlib; Vulkan; DXVK 3.x needs Vulkan 1.4 [X]), or a minimal custom D3D8-on-Vulkan/GLES layer. Long term: a native renderer. |
| B4 | **Pervasive C++ EH / SEH** | H for B | [M] 23,665 `fs:` accesses, so about 12k functions with exception frames. `__CxxFrameHandler` and `_CxxThrowException` are imported by every module. Engine and GlmLib also use `setjmp`/`longjmp`. [X] pcrecomp excludes guest SEH. | B, D-B | Model the guest SEH chain in the lifter runtime: a handler-table walk with longjmp-style unwinding, or map `_CxxThrowException` and catch funclets to host exceptions. The common path never throws, so the first iterations can trap instead of unwinding. |
| B5 | **Indirect control flow** | H for B | [M] About 30k indirect register/vtable calls, 709 calls via function-pointer globals, 186 jump tables and 240 other indirect jumps. [D] These are the top blocker in the coverage probe. [M] Mitigating factor: RTTI is compiled out, but the **vtables are exported by name** (`??_7…@@6B@`): 61 in Core, 312 in Engine, 142 in GlmLib and 77 in UI. | B, D-B | A guest-VA → lifted-function dispatch table, filled from exports (about 18k symbols, including the vtables themselves), relocation-referenced code pointers and recursive discovery. Jump-table recovery follows MSVC's standard pattern. |
| B6 | **Volume of native engine behaviour**, if it is reimplemented rather than lifted | H for A/D-R | [M] 410 native classes and 723 script natives (Engine has 226 classes and 349 natives). Movement and physics feel, BSP collision and navigation. | A, D-R | Avoid it by recompiling first (D-B). Replace subsystems one at a time, each against a differential oracle. |

## Technical risks

| ID | Risk | Severity | Evidence or reasoning | Mitigation |
|---|---|---|---|---|
| R1 | **x87 semantics.** 80-bit intermediates, exponent range, denormals, `fild` of integers wider than 53 bits, transcendental instructions (`fsin`, `fpatan`, `fsqrt` precision), and FPU control-word changes (78 `fldcw`/`fnstcw` in GlmLib) | M | [D] Bit-exact for 102k sampled results under the default 53-bit precision control. [M] 185k x87 instructions in total. Host libm's `sin` is not bit-identical to x87 `fsin`. | Use soft-float or long-double paths for the instruction forms that need them. Run differential tests per subsystem. Accept last-bit divergence where gameplay is not sensitive, and **measure** it in the level-simulation diff (ROADMAP X2). |
| R2 | **Karma (MathEngine) role is unclear**: `physKarma` is "obsolete in U2 829", yet Karma still initialises for game and level | M | [M] Strings and log lines | Trace Karma calls in a headless level simulation. Lifting covers it either way. Note that MathEngine code is statically linked third-party code. |
| R3 | **Latent bytecode bugs** in 83 shipped functions (wrong `Context` skip lengths) | L | [D] E2. The original `execContext` uses the skip literally. | Decide: bug-compatible (keep the original skip) or fixed (skip the parsed expression). A fixed VM differs only on "Accessed None" paths. |
| R4 | **Unimplemented natives**: `ScriptedTexture` 472–476 | L | [D] E3 | Confirm they are never called at runtime. If they are, implement them or stub them as the original's `execUndefined` would. |
| R5 | **Unreal II content serialization not yet decoded**: the 4-byte `AActor` tail, Legend particle-template payloads, `TextureArray`, `LegendMesh`, `ScriptedLight`, and the U2 variants of `StaticMesh`, `Model` and `Terrain` | M | [D] E7b: 253 classes with native payloads (1.6 GB), only partly understood | Covered by lifting (B/D-B). For reimplementation, decode class by class and check that each export's payload is consumed exactly. |
| R6 | **The engine writes into its install folder**: it rewrites `System\Golem.u` at startup [D], and the ini, log and Running.ini files | L | [D] E4 | Redirect writes to a user directory in any port. |
| R7 | **Frame-rate and timing assumptions**: water animation glitches above 60 FPS, mouse issues | M | [X] PCGamingWiki | A fixed-timestep option. Test at 120/144 Hz. |
| R8 | **Android performance and Vulkan availability** | M | Unmeasured. DXVK 3.x needs Vulkan 1.4; devices launched before Android 16 may only have 1.3 [X]. Timings under emulated ARM64 here are meaningless. | Measure on real hardware early (ROADMAP X3). Consider DXVK 2.x or a GLES/Vulkan 1.1 path. |
| R9 | **Distribution and legal constraints** | H (non-technical) | Unreal II IP: Epic Games. Delisted December 2022 [X]. No source access. Lifted C is a derivative of proprietary code. MathEngine/Karma, Ogg/Vorbis and OpenAL have their own licences. | Ship only original code: lifter, runtime, HLE, VM and tools. Require a user-supplied game copy and run the lift locally. Consider contacting rights holders, as OldUnreal did with Epic for UT2004 (2025) [X]. |
| R10 | **XMP is a different engine generation** (v126 layouts, no Golem, Vehicles.dll) | L | [D] E1/E2 | Out of scope. Treat it as a second project that reuses the tooling. |
| R11 | **Win32 HLE breadth**: window, messages, GDI text, registry, file APIs, threads, timers | M | [M] Import lists (KERNEL32, USER32, GDI32, ADVAPI32, SHELL32, ole32) | Implement on demand, driven by the imports actually reached. The surface is moderate: Core imports 38 KERNEL32 functions and WinDrv 57 from USER32. |
| R12 | **Editor dependence** | L | The game does not need UnrealEd, Editor.dll or GlmEd | Exclude from all builds |
| R13 | **Test oracles need the original x86 build** | L | x86 harnesses run on Windows x86/x64 only | Keep a Windows x64 CI runner for the oracles. ARM64 runs compare against stored reference outputs, as done here. |

## Unknowns that need experiments, not more analysis

1. **Golem:** the `.gem` section semantics, and how much of GlmLib's runtime path the game actually touches.
2. **DirectMusic:** which track and script features the 8 containers really use.
3. **Engine native serialization:** the exact formats for U2 BSP, static meshes and terrain. Compare them against UE2 (UT2004) to see what can be borrowed.
4. **Performance:** of lifted code on ARM64 phones.
5. **Determinism:** of lifted x87 code over long simulations.
6. **Behaviour:** of the original under DXVK, d3d8to9 and dgVoodoo2 on this machine. This is the cheapest way to settle the player-facing compatibility answer.
