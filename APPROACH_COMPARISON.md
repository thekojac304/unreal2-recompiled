# Comparing implementation strategies A–D

**Evidence labels** used in this document:

| Label | Meaning |
|---|---|
| **[D]** | Demonstrated in this workspace (POC_RESULTS) |
| **[M]** | Measured from the shipped binaries and data |
| **[X]** | External, from web research with the URL given and not re-tested here |
| **[S]** | Speculation or engineering judgment |

Effort figures are order-of-magnitude judgments **[S]**, derived from the measured code and data volumes. They are not estimates from detailed planning.

## Scale that every strategy must face [M]

- **Native code:** 6.6 MB and about 2.27 M x86 instructions across 17 runtime modules. Of that, Engine is 2.06 MB, GlmLib (Golem) 2.15 MB, UI 0.59 MB, ParticleSystems 0.38 MB and Core 0.42 MB.
- **Native classes:** 410 registered with the object system.
- **Natives:** 723 declared in script, plus 70 opcodes and 32 casts.
- **Native loaders:** needed for 253 content classes, about 1.6 GB.
- **Platform dependencies:** Direct3D 8 with VS 1.1/PS 1.4, DirectInput 8, **DirectMusic, including AudioVBScript scripts**, OpenAL with EAX 3, and Win32.
- **x86 specifics:** about 185k x87 instructions, about 30k indirect calls, and C++ EH/SEH in about 12k functions.
- **Script:** 1,317 classes and 971 KB of bytecode, fully decodable [D].

---

## A. Source-level native engine reconstruction

**What.** Re-create the engine, rather than the game logic, in new source code that runs the original packages. This is the SurrealEngine model, which does the same for UE1.

**Architecture.** A new C++ engine containing:
- package loader and UnrealScript VM — **both already exist here** [D];
- the actor framework, physics and collision, BSP and static mesh rendering, terrain and navigation;
- Golem animation (decoded from scratch), particles, the Legend UI, dialog, `.u2s` and `.dlg` interpreters, DirectMusic and audio;
- every one of the 723 natives and the 253 content-class loaders.

**Evidence for.**
- The data and script layers decode completely [D].
- The VM is bit-exact on three platforms [D].
- Exported C++ signatures give the exact shape of every native method [M].
- Embedded script source shows script-side intent [M].

**Evidence against.**
- The volume of native behaviour to re-derive is large, especially physics and movement feel, Golem, particles and the renderer [M].
- Golem's format and runtime are undocumented, with no external tools [M][X].
- *Precedent:* SurrealEngine (UE1, much smaller per game) has been in development for years and is still partial for several titles [X: github.com/dpjudas/SurrealEngine].

**Effort.** Very high: several person-years, probably 5–10+ for full fidelity [S].

**Risks.**
- Gameplay-feel drift in movement, physics and AI timing.
- Golem may be unrecoverable without lifting.
- DirectMusic.
- A long time to the first playable build.

**Performance.** The best of all options: native and modern [S].

**Portability.** The best: any platform, including iOS and consoles [S].

**Maintenance.** The best long-term readability. Behavioural parity has to be proven class by class [S].

**Verdict.** **NO-GO as the primary strategy.** It is the long-term destination of D, not the starting point.

---

## B. Static binary recompilation (x86 → C → any CPU)

**What.** Mechanically translate all original native modules into portable C. The game then runs as a native process on x64 and ARM64, with platform APIs (D3D8, DirectInput, DirectMusic, Win32, CRT) provided by HLE replacement code.

**Evidence for.**
- **Correctness of the translation:** real Core.dll code, including x87 and the CRT's `_ftol2`, lifted automatically, was bit-exact against the original DLL across 102,000 results on x64, Linux x86-64 and ARM64 [D, E6].
- **Coverage:** a deliberately minimal lifter already handles 52–61% of all exported functions in Core, Engine and GlmLib. The rest is blocked almost entirely by indirect calls and SEH, which are known and solved problems in other recompilers [D].
- **Function boundaries:** these binaries are unusually well-suited. Every module exports almost all of its C++ methods with full signatures (about 18k symbols), so function boundaries, calling conventions and many vtable slots are known [M].
- **The toolchain is uniform:** VC 7.0 (9466) throughout [M].
- **Proprietary subsystems come along unchanged:** Golem, Karma, particles, UI and the AI and dialog interpreters need **no reverse engineering of their logic**. They are translated as they are.
- **Precedents [X]:**
  - pcrecomp: x86-32 PE → C, with x87 and MSVC RTTI/vtable recovery ([github.com/sp00nznet/pcrecomp](https://github.com/sp00nznet/pcrecomp)).
  - nfsu2-recompiled: a 32-bit MSVC D3D9 game lifted to about 27.7k C functions and reported playable on Android ARM64 with embedded DXVK Native ([github.com/codepdbh/nfsu2-recompiled](https://github.com/codepdbh/nfsu2-recompiled)).
  - XboxXBE-Recomp: MSVC x86 Xbox games → C++ with x87 and C++ EH ([github.com/TGP482/XboxXBE-Recomp](https://github.com/TGP482/XboxXBE-Recomp)).
  - M-HT/SR: Win32 games → ARM via LLVM ([github.com/M-HT/SR](https://github.com/M-HT/SR)).

**Evidence against, or open.**
- **Indirect calls:** about 30k indirect calls need a guest-address → host-function dispatcher, plus complete function discovery (vtables, exports, relocations) [M].
- **Exceptions:** C++ EH/SEH is pervasive. The UE `guard`/`unguard` macros give roughly 12k functions an exception frame: 23,665 `fs:` accesses, about 2 per frame [M]. pcrecomp explicitly excludes guest SEH [X].
- **Address space:** 9 game DLLs share the preferred base 0x10000000 [M]: ALAudio, D3DDrv, GlmLib, Legend, ParticleSystems, U2, U2AI, U2Dialog and UI. The bundled Ogg/Vorbis/OpenAL DLLs share it too. Each needs relocation at lift time. `.reloc` sections are present, so this is feasible.
- **x87 fidelity:** the 53-bit model is exact for the samples tested. 80-bit and denormal edge cases are not modelled [D].
- **HLE surface still to write:** D3D8 (DXVK has a D3D8 frontend since v2.4 [X]; DXVK 3.x requires Vulkan 1.4 [X]), DirectMusic **including AudioVBScript**, DirectInput8, Win32 window/messages/GDI subset, and the msvcr70/msvcp70 subset.
- **Distribution:** the generated C is a machine translation of proprietary code. It cannot be redistributed, so users would run the recompiler on their own copy, as many recomp projects require [S].
- **Maintainability:** generated code is not maintainable source [S].

**Effort.** Medium-high: about 1–3 person-years to a first playable build, given existing tooling to build on [S]. Not demonstrated at module scale.

**Performance.** Lifted code with an explicit-state, memory-array design is typically slower than original native code, but far faster than emulation. The NFSU2 precedent reports 35–51+ FPS on a Galaxy S24 Ultra [X]. Not measured here.

**Portability.** Any 64-bit target with a C compiler and the HLE layer; Android ARM64 and Linux in principle [S]. The ARM64 bit-exactness of translated code is [D].

**Maintenance.** Moderate: fixes happen at the translation, patch or HLE level.

**Verdict.**
- **As a targeted technique, an oracle and a bootstrap: CONDITIONAL GO.** The next experiment, a whole Core.dll lift running shipped bytecode, decides it.
- **As the complete, final product: CONDITIONAL GO** from a technical standpoint, with distribution and maintainability caveats.

---

## C. Runtime compatibility and binary translation (not a port)

**What.** Keep the original x86 binaries and run them through layers:
- **Windows:** a D3D8 wrapper such as dgVoodoo2, d3d8to9 or DXVK's d3d8.
- **Linux:** Wine/Proton with DXVK.
- **Android ARM64:** Winlator (Wine + Box64 + DXVK + Turnip/Zink) or Hangover/FEX.

**Evidence.**
- **This machine:** the user's last session on 2024-09-18 crashed with `CreateDevice failed (D3DERR_DEVICELOST)` while entering fullscreen on an RTX 3070 [M]. PCGamingWiki documents this class of Windows 10/11 problem and recommends d3d8to9 or a DX8 wrapper and `ReduceMouseLag=False` [X: pcgamingwiki.com/wiki/Unreal_II:_The_Awakening].
- **Linux:** ProtonDB rates the game *Silver* from 25 reports. A Wine regression in DirectMusic (bug 55790) was fixed in Wine 8.19. Some users delete the `.con` music files to start, i.e. they lose the music [X].
- **Android:** a "Winlator 7.1 – Unreal II" video exists. Device, settings and performance are unknown [X, unverified].
- **Headless engine:** the engine core runs on modern Windows without the renderer (UCC, E4) [D].

**Effort.** Low: days to weeks of configuration and testing per platform [S].

**Risks.** No control over Wine's DirectMusic or emulator bugs. Performance on phones goes through two translation layers (x86→ARM, D3D8→Vulkan). x86-32 support under ARM64 Wine (WoW64 + Box64/FEX) is still "experimental" [X].

**Performance.** Fine on desktop x86. On Android it depends on the device [S].

**Portability.** Windows and Linux now. Android plausibly. No iOS.

**Maintenance.** Minimal for us, but entirely dependent on the external projects.

**Distinction.** This is *not* a native port. The original x86 code still executes, under emulation on ARM.

**Verdict.** **GO as the immediate player-facing answer**, to be verified on hardware. It does not meet the "independently runnable implementation" objective.

---

## D. Hybrid architecture (recommended)

**What.** Combine the following:
- **Reused:** the original packages and bytecode [D].
- **Independently implemented and portable:**
  - the package loader and UnrealScript VM [D];
  - the platform layer: renderer, SDL3 input and window, OpenAL Soft, a DirectMusic subset.
- **Statically recompiled:** the original native modules, especially the proprietary ones whose behaviour is hard to re-derive.
- **Validation:** continuous differential testing against the original DLLs.

There are two orderings.

- **D-R, reimplement first.**
  - **Approach:** start from the proven VM and loader, rewrite the Engine natives, and lift only Golem and perhaps ParticleSystems.
  - **Strengths:** readable code from day one and the best eventual performance.
  - **Weaknesses:** the playable milestone sits behind a large reimplementation (226 Engine native classes, 349 Engine natives), with gameplay-feel risk.
- **D-B, recompile first. Recommended.**
  - **Approach:** lift all runtime modules into one guest address space, so every native behaviour is faithful by construction. Write the HLE platform layer once. Then **progressively replace** lifted parts with the independent components, wherever that improves portability, performance or maintainability. Candidates, in order:
    1. the renderer (D3DDrv/D3D8 → native Vulkan/GLES);
    2. audio and music;
    3. input and window;
    4. eventually Core's VM, with `uvm` and its differential tests already in place;
    5. Engine subsystems one by one.
  - **Why it wins on evidence:**
    - The hardest parts to reimplement — Golem (2.15 MB of code, undocumented format), physics and movement feel, particles and the Legend UI — are exactly the parts recompilation handles mechanically.
    - The parts that *must* be rewritten in every strategy (D3D8, DirectMusic, input, windowing) are the same in D-B, so no work is wasted.
    - Every replacement can be verified against the lifted or original version with the two oracles built here: the script-level UCC oracle (E4/E5) and the function-level DLL harness (E6).

| Criterion | A | B | C | D-B (recommended) |
|---|---|---|---|---|
| Time to first playable | Very long | Medium | Short | Medium (same as B) |
| Faithfulness of native behaviour | Must be re-derived | Exact by construction | Exact (original code) | Exact, then preserved by differential tests |
| Golem, physics, particles | Full reverse engineering | Free | Free | Free |
| Platform layer work | Full | D3D8, DMusic, DInput, Win32 HLE | None (external) | Same as B, then native renderer and audio |
| Android ARM64 | Native | Native (translated) | Emulated | Native (translated, then gradually native) |
| Distributable code | Yes | No (generated from user's copy) | n/a | Platform layer and new components yes; lifted parts no |
| Maintainability | High | Low | n/a | Rises over time |
| Demonstrated here | VM and loader | 13 functions, bit-exact | Engine runs headless | VM, loader and lifter, bit-exact on ARM64 |

**Verdict.** **CONDITIONAL GO.** The condition is the success of the first two experiments in ROADMAP.md: a whole-module lift with SEH and indirect calls, and a headless lifted-engine level simulation that matches the original.

---

## Summary table

| Strategy | Effort [S] | Main technical risk | Verdict |
|---|---|---|---|
| A Full reconstruction | 5–10+ person-years | Re-deriving Golem, physics and renderer behaviour | NO-GO as primary |
| B Static recompilation | 1–3 person-years to first playable | SEH, indirect calls, HLE breadth (DirectMusic) | CONDITIONAL GO |
| C Compatibility layers | Days to weeks | External bugs (Wine DirectMusic), emulation performance on phones | GO for players; not a port |
| D Hybrid, recompile first | B, plus incremental replacement | Same as B at first; replacements are verified one at a time | **CONDITIONAL GO (recommended)** |
