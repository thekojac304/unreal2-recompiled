# Roadmap: hybrid, recompile-first (D-B)

Every milestone has a pass/fail test that can be checked objectively. The "oracles" are the two harnesses built in this investigation:
- **Script/engine-level:** commandlets compiled and run by the original sandboxed `UCC.exe` (E4/E5).
- **Function-level:** an x86 harness that loads the original DLLs and calls their exports (E6).

## Phase 0: feasibility (done, 2026-10-22)

| Milestone | Test | Status |
|---|---|---|
| Package tables decoded | 0 unaccounted bytes over 534 packages | ✅ E1 |
| Script objects and bytecode decoded | 35,411 / 35,411 exact; jump-target invariant holds | ✅ E2 |
| Native interface specified | Opcode, cast and native tables recovered from machine code and cross-checked with script | ✅ E3 |
| Original engine usable as an oracle | Original compiler and VM run our code headless | ✅ E4 |
| Independent VM | 74 / 74 lines identical on Windows x64, Linux x64 and Linux ARM64 | ✅ E5 |
| Bit-exact x86→C translation | 102,000 / 102,000 identical on 3 targets | ✅ E6 |
| Tooling and content survey | UELib tested; 253 native payload classes mapped | ✅ E7 |

## Phase 1: the next three experiments, which validate or invalidate D-B (about 2–4 months [S])

### X1. Whole-module recompilation of Core.dll and UCC.exe

**Scope.** Extend `tools/lift`:
- **Indirect calls:** a guest-VA → function dispatch table built from exports, relocation-referenced code pointers and `.rdata` vtable scans.
- **Jump tables.**
- **Guest SEH:** model the `fs:[0]` chain. A first version may trap on the first throw.
- **Relocation:** relocate DLLs to non-overlapping bases.
- **HLE shims** for the msvcr70 and KERNEL32 subset Core imports (51 + 38 functions), and WINMM, ADVAPI32, USER32, SHELL32 and ole32 stubs.

**Pass when.** The lifted `UCC` + lifted `Core` run `HelloWorld`, `SimpleCommandlet`, `ArrayTest` and `VMProbe`, and the **74 / 74 output lines are identical** to the original, on Windows x64 *and* Linux ARM64. Also report the number of lifted functions, the coverage left uncovered, and the runtime relative to `uvm`.

**Fail** (invalidates B at scale) **if.** SEH or dispatch cannot be made correct without per-function manual work across more than about 5% of functions.

### X2. Headless level simulation diff: lifted Engine + GlmLib + game modules versus the original

**Scope.** Write a deterministic UnrealScript commandlet, compiled with the original `ucc make` as in E4, that:
1. loads a real map (`TutA.un2`, then `M01A.un2`);
2. spawns the player pawn (a Golem mesh);
3. ticks the level for N frames at a fixed delta time with scripted input;
4. dumps a per-frame digest of actor transforms, physics state, AI state and animation channel/frame for Golem meshes.

Run it in the original engine (sandbox UCC, x86) and in the lifted engine (x64 and ARM64).

**Pass when.**
- Digests are identical for at least 600 frames on x64.
- On ARM64 they are identical, or any drift is bounded and explained by x87 transcendental differences (R1), with the divergence quantified.

**This proves.** Engine, physics, Golem animation and AI run faithfully as translated code, without reverse engineering their logic.

### X3. Platform-layer smoke test: first rendered frame on desktop and on an ARM64 device

**Scope.**
- **Windows baseline, cheap, run first:** the original `Unreal2.exe` with a D3D8 wrapper (DXVK d3d8, d3d8to9 or dgVoodoo2) in windowed and fullscreen modes. This confirms the D3DERR_DEVICELOST failure goes away and captures reference screenshots and frame times. This also settles strategy C for Windows.
- **Lifted client:**
  - D3D8 imports handled by HLE (DXVK-native D3D8 frontend, or a minimal custom D3D8 → Vulkan/GLES layer);
  - SDL3 for window and input;
  - OpenAL Soft;
  - DirectMusic stubbed (silent).
  - Render the first frame of `M01A` on Windows/Linux x64 and on a real ARM64 Android device (Adreno or Mali Vulkan).

**Pass when.**
- The rendered frame matches the reference screenshot (perceptual diff below a threshold that is fixed in advance).
- The ARM64 device reaches at least 30 FPS at 720p on the first map.

## Phase 2: playable desktop build (Windows x64 + Linux x64) via D-B

| Milestone | Pass/fail test |
|---|---|
| All runtime modules lifted and linked | Every function reachable from `UGameEngine::Init` and `Tick` is lifted; the trap counter stays at 0 through a full session |
| Win32/D3D8/DInput HLE complete | The main menu works with keyboard, mouse and controller (SDL3) at modern resolutions, without D3DERR_DEVICELOST |
| DirectMusic subset | The 8 containers parse. Segment, wave-track and script transitions play. The PCM output of each documented music state matches recordings from the original under a wrapper (correlation threshold) |
| Save compatibility | Original `.usa` saves load. Saves written by the port load in the original engine (sandbox) |
| Campaign regression suite | Scripted playthroughs (demo or bot input) of every map reach their end triggers; per-map digest diffs against the original stay within a tolerance |

## Phase 3: Android ARM64

| Milestone | Pass/fail test |
|---|---|
| APK with user-supplied data import (no game files shipped) | Installs and imports a GOG copy; no proprietary bytes inside the APK |
| Vulkan 1.1–1.3 path | Runs on at least two GPU families (Adreno, Mali) |
| Input | Touch overlay and controller; the campaign can be completed on a controller |
| Performance | ≥ 30 FPS (target 60) at 720p in the three heaviest maps on a mid-range 2024 SoC; sustained 30 minutes without thermal collapse below 25 FPS |

## Phase 4: progressive replacement (maintainability and performance)

Replace lifted parts with independent implementations, each gated by its oracle:

| Order | Replacement | Gate |
|---|---|---|
| 1 | Native renderer replacing D3D8 HLE and D3DDrv | Screenshot diffs per map |
| 2 | Native audio and music | PCM correlation |
| 3 | `uvm` replacing Core's VM, with the 723 natives completed | The E5 suite plus the X2 digests |
| 4 | Engine subsystems one at a time: navigation, movement, collision | X2 digests |

**Progress metric:** the percentage of executed instructions that come from lifted code (lower is better). It is reported per release.

## Phase 5 (optional): independent engine

Phase 5 is strategy A reached incrementally. It begins only once lifted code is a minority of runtime, and it is the only stage at which a fully distributable engine exists.

## Decision gates

- **After X1:**
  - If whole-module lifting with SEH and dispatch fails, fall back to **D-R**: the proven VM and loader plus reimplemented natives, lifting only leaf-heavy libraries.
  - Players use strategy C meanwhile.
- **After X2:**
  - If Golem or physics diverge beyond explanation, reverse engineering of Golem moves up before Phase 2.
- **After X3:**
  - If ARM64 performance is below 20 FPS on a mid-range device, profile the lifted code: dispatch overhead, the memory-array design and x87 emulation.
  - Then consider replacing hot modules natively earlier (Phase 4 items 1 and 4).
