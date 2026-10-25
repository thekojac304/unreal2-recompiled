# SetFocus measured and validated

2026-10-24, US Eastern. The minimal typed adapter calls real USER32 SetFocus and
maps the actual returned previous HWND to a stable guest token. The single
authorized translated-client continuation stopped at **WM_GETICON (0x007f), ICON_SMALL2 (wParam=2), lParam=0**.

Starting commit: `7fa848af117df6ed40d160670ed56e3ca4263857`. All 477 working files,
both Git patches, earlier builds and historical results were preserved. The tested
executable includes the pinned earlier pending keyboard, observer, build and other
sources. The scoped local commit excludes that pending work and is recorded in
`out/recovery/setfocus-20261024-01/commit.json`. No push.

## Tested identities and build

Executable: `experiments/xrt/build/setfocus-20261024-01/xrt_ucc.exe`

SHA-256: `1383e7c0e04c43fd4466afed7cc2104377e3032e69717245ff9a5c6a704665b2`

PDB SHA-256: `0d0d537e7f2b8ffb67a46a807b5867fadedc9f578289b7cbf3d50ce2dbb0160b`

Runtime aggregate: `30c3dbececa74ec88c75560e0c22df28bae40c9406e31b8b3dfe25ddac94047b`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

All 265 generated and 14 runtime objects were compiled serially into an exclusive
new directory with verified MSVC 14.51.36231. Historical objects and PDBs were not
reused. Main-build warnings: 0; failures: zero.
278 objects have identical code and named relocations to the accepted
ImmAssociateContext build; only hle_gui changes. Existing keyboard, GetFocus and
AdjustWindowRect function code remains identical. 79,226,692
linked generated-code bytes outside relocation fields match the verified objects;
the earlier local-helper coverage limitation remains. Exact commands and hashes of
sources, objects, executable, PDBs, compiler, header trees, libraries, USER32/win32u,
DXVK and the DirectMusic helper are retained in the local evidence directory.

## Native x86 versus translated results

The same project-owned x86 DLL passes 44 fully compared paired
SetFocus calls, including nested calls, plus the second thread's owned-window call.
Sibling A/B/A transitions return the previous HWND (A-to-B returns A; B-to-A returns
B). Same-window and empty-NULL calls preserve last-error. Changes with the measured
default procedures clear it. Invalid, -1 and destroyed HWNDs return NULL/error 1400
without changing actual focus. Three last-error seeds, stdcall ESP and EBP/EBX/ESI/EDI
match. Callback order, window/other-window/focus/return identity and errors match.
Both WM_NCCREATE and WM_CREATE focus changes complete their native CreateWindowEx.
A previous native stock HWND first encountered by SetFocus receives a stable token
that can be reused.

Native hidden popup activation can reenter focus handling and affect the actual
returned HWND; that exploration is preserved. The adapter does not predict a return
value. Native unattached cross-thread attempts return NULL/error 5 and leave the
worker's focus unchanged. Translation stops explicitly for cross-thread windows
and wrong-type tokens. Attached input queues and cross-thread callback/baton transfer
remain unsupported. No general input management was added. Invalid nonzero guest
HWNDs use a verified invalid host sentinel so real USER32 supplies the failure.
No host HWND bits enter guest memory.

Fixture development corrected one undefined-enum typo before the fresh client build;
its compiler diagnostic is retained. No internal compiler failure or process crash occurred.

## One bounded client continuation

Run: `experiments/xrt/results/raw/level/20261025-003606-bb210f9f-candidate`.
Exactly one translated graphical session, zero native graphical game sessions,
isolated manifest-bound assets, verified DXVK x64 and DirectMusic IPC helper,
60000-ms runtime watchdog. All 74,386 events are contiguous, with zero
dropped or truncated events. The previous writable sandbox was archived intact.

| Observation | Verified result |
|---|---|
| SetFocus | 1 calls / 0 paired returns |
| Viewport CreateWindowEx completed | False |
| UWindowsViewport::OpenWindow returned | False |
| UGameEngine::Init | 1 entries / 0 paired returns |
| Selected CS_Intro world | 0x12f52800 |
| Selected-world lifecycle | {'PreBeginPlay': 279, 'BeginPlay': 279, 'PostBeginPlay': 279}; 278 actors; no unpaired calls |
| UGameEngine::Tick | 0 entries / 0 paired returns |
| Selected ULevel::Tick | 0 entries / 0 paired returns |
| D3D CreateDevice / real device / Clear / Present | 0 / 0 / 0 / 0 |

Completion requires explicit post-call records with checked ESP and return pairing.
Window callbacks or a D3D factory alone do not establish a rendered frame.
First remaining blocker: **WM_GETICON (0x007f), ICON_SMALL2 (wParam=2), lParam=0**, caller WinDrv.dll+0x71e2 (0x111071e2). Full trace,
stack, snapshot disassembly, CPU/FPU diagnostics and cleanup evidence are preserved.
No orphan client/helper remained; StickyKeys matched before/after.

## Acceptance and integrity

SetFocus, IMM32, AdjustWindowRect, GUI/keyboard/window, class/callback, module and
GetFocus regressions pass before and after execution. Compact commandlet/VM: nine
cases pass. UnrealScript compiler: 16 compiles, 12 executions and four expected
invalid-source failures pass. Traced HelloWorld passes. Python: 158 discovered,
141 passed, 17 documented opt-in skips. The historical classprobe C4133
warning and explicit unsupported expectations remain unchanged.

Protected manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`:
all 4,122 files, three protected trees and nine protected files match before/after.
Accepted/new outputs, generated sources, runtime and pinned working files, toolchain,
dependencies, DXVK and helper identities match after execution and acceptance.
Original installation and saves were not accessed. Historical expanded CRT
(110 mismatches / 1,796 pending), six ACP932 differences and x87 limitations remain open.

Smallest next experiment: Measure native x86 versus translated WM_GETICON for ICON_SMALL2 during SetFocus activation and nested DefWindowProcW, including NULL/typed HICON returns and callback ABI; add only that measured callback boundary in a separately authorized milestone before any further client continuation.

This bounded milestone is stopped. No further API, renderer expansion, Android work,
editor expansion, unrelated refactoring or push.
[Structured checkpoint](results/compare/setfocus_world_resume.json).
Full local evidence: `out/recovery/setfocus-20261024-01/`.
