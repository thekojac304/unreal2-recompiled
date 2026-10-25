# ImmAssociateContext measured and validated

2026-10-24, US Eastern. Real host IMM32 returned through the typed adapter in the
genuine translated client. The one authorized graphical continuation stopped at
**user32.dll!SetFocus**. No further API was implemented.

Starting commit: `d325d87c8c52a8ab8a4da5d2cf94cd78bf5ef944`. All 468 working files, both
Git patches, previous builds and evidence were preserved. Earlier pending keyboard,
world-observer and build changes remain unstaged. The tested executable corresponds
to the pinned complete working tree, including that earlier work. The final scoped
local commit identity is recorded in `out/recovery/immassociatecontext-20261024-01/commit.json`.

## Exact tested identities

Executable: `experiments/xrt/build/immassociatecontext-20261024-01/xrt_ucc.exe`

SHA-256: `511f6016b1bd18f271a3df9ff08d1389fddcd6ca599905c29d82716d45f39b3d`

PDB SHA-256: `3f780df5575a97f01ce6c8babb357a2f733b30b22a6fb78ebdd80b2c43de22df`

Runtime aggregate: `844a74bd5ff180ae79da8a2ad27697ed2bc8946721008b9b5edfc27bc3e09d5e`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

265 generated and 14 runtime objects were freshly compiled serially with verified
MSVC 14.51.36231. No historical objects/PDBs were reused. Main-build warnings:
0; failures: zero. 277 object code/relocation
identities remain unchanged; only hle_gui and xrt_loader change. SetKeyboardState,
GetKeyState, GetFocus and AdjustWindowRect retain identical function code.
79,226,692 linked generated-code bytes outside
relocation fields match their verified objects. The earlier local-helper coverage
limitation remains. Exact source/object/PDB/executable/toolchain/SDK IMM32 library
and Windows IMM32 hashes and commands are retained in the local evidence directory.

## Native x86 versus translated IMM32

The identical project-owned x86 DLL passes 56 calls across two OS/guest threads:
existing non-NULL contexts, detach, repeated detach, previous-HIMC identity,
restoration, same-context reassociation, shared thread default contexts, custom
contexts and default-context survival after window destruction. Result identity,
actual association, three last-error seeds, stdcall ESP and EBP/EBX/ESI/EDI match.

Twelve NULL/arbitrary-invalid/-1/destroyed HWND calls also match. NULL HWND preserves
last-error; nonzero invalid/destroyed HWNDs return NULL and error 1400. Association
changes clear last-error in this measurement, whereas repeated detach/same-context
association preserve the seed. Results are supplied by real IMM32.

Six isolated cases retain native evidence and stop explicitly in translation:
unknown/wrong-type HIMC, foreign-window detach/reassociation, foreign-thread HIMC,
and a context after its owning thread exits. Native foreign-window detach succeeds
and changes the association; this remains deliberately unsupported. The fixture's
one-shot cross-thread calls avoid an invalid reference/restore/repeat assumption.

No native HWND/HIMC bits enter guest memory. Borrowed typed contexts belong to a
stable guest/OS thread, survive individual window destruction, and are never destroyed
by the bridge. Guest context creation/destruction, external host mutation, general
IME functionality and cross-thread associations remain unsupported.

## Single bounded client continuation

Run: `experiments/xrt/results/raw/level/20261025-000405-21ca7cb1-candidate`.
Exactly one translated graphical session, zero native graphical game sessions,
isolated verified assets, DXVK and DirectMusic IPC, 60000-ms runtime watchdog.
All 74,396 events are complete and contiguous; none dropped/truncated.
The previous writable sandbox was archived intact before preparation.

| Observation | Verified result |
|---|---|
| ImmAssociateContext | 1 paired returns; last result token 0x1270, last-error 0 |
| Native viewport CreateWindowEx completed | False |
| UWindowsViewport::OpenWindow returned | False |
| UGameEngine::Init | 1 entries / 0 paired returns |
| Selected CS_Intro world | 0x12f52800 |
| Selected-world lifecycle | {'PreBeginPlay': 279, 'BeginPlay': 279, 'PostBeginPlay': 279}; 278 actors; no unpaired calls |
| UGameEngine::Tick | 0 entries / 0 paired returns |
| Selected ULevel::Tick | 0 entries / 0 paired returns |
| D3D CreateDevice / real device / Clear / Present | 0 / 0 / 0 / 0 |

Creation/OpenWindow conclusions use explicit post-call records and checked ESP and
return pairs. Callback entries alone do not establish completion. First remaining
blocker: **user32.dll!SetFocus**, caller WinDrv.dll+0x5d75 (0x11105d75). Full local stack, snapshot
disassembly, CPU/FPU diagnostics, traces and cleanup are preserved. No orphan
client/helper remained. StickyKeys matched before/after. No unexpected crash occurred.

## Acceptance and integrity

IMM32, AdjustWindowRect, GUI/keyboard/window, class/callback, module and GetFocus
regressions pass before and after the client session. Compact commandlet/VM: nine
cases pass. UnrealScript compiler: 16 compiles, 12 executions and four expected
invalid-source failures pass. Traced HelloWorld passes. Python: 158 discovered,
141 passed, 17 documented opt-in E2E skips. The historical classprobe
C4133 warning and existing explicit unsupported test expectations are unchanged.

Manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`:
all 4,122 files, three protected trees and nine protected files match before/after.
Accepted/new executable/object/PDB identities, helper, both DXVK pairs, generated
code and pinned sources match after execution and acceptance. Original installation
and saves were not accessed. Expanded CRT (110 mismatches / 1,796 pending), six
ACP932 differences and existing x87 limitations remain open.

Smallest recommended next experiment: Measure native x86 versus translated SetFocus on owned windows, including previous-focus identity, NULL/invalid/destroyed HWNDs, last-error, thread ownership, stdcall ABI and reentrant creation callbacks. Add only the measured typed HWND adapter in a separately authorized milestone, then perform one bounded continuation. No renderer expansion.

This bounded phase is stopped. No renderer expansion, Android work, editor features,
unrelated refactoring or push. [Structured checkpoint](results/compare/immassociatecontext_world_resume.json).
Full local evidence: `out/recovery/immassociatecontext-20261024-01/`.
