# AdjustWindowRect validated; viewport creation stops at ImmAssociateContext

2026-10-24, US Eastern. AdjustWindowRect returned in the genuine translated client.
OpenWindow progressed into native window-creation callbacks, then stopped at the
unbound **IMM32!ImmAssociateContext**. Highest independently verified world milestone
remains **T2**. Init and selected-world ticks have not returned. No real D3D device,
Clear, Present or rendered frame occurred. This bounded phase is complete and stopped.

Starting HEAD: `ddb93bdca66bd94e98e84d1254767da640f953e6`. All 459 working files and both
Git patches were preserved before editing. Earlier pending changes remain unstaged.
The executable corresponds to the pinned working source, including that earlier work;
the scoped commit does not absorb the previous keyboard/observer/build experiments.

## Exact binary and build identities

New executable: `experiments/xrt/build/adjustwindowrect-20261024-01/xrt_ucc.exe`

SHA-256 `e274f465c095abe503b4373e5cb932683bf2b8c135224c41150360b70e243620`

PDB SHA-256 `cb8a18937537e7ddcfbc355ad5c8dfb0f7325a9c7b3c1c218fc2caa648f6ba24`

Accepted GetFocus executable SHA-256:
`3f2a284a8197970fac19a38b41dda4323debfa699080f220d766457cd4b405b1`

Runtime aggregate: `343572244b1334506af0d637a51d49650051c96593e8738e995939eef36b6be0`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

All 265 generated and 14 runtime objects were freshly compiled serially in a new
directory with the pinned MSVC toolchain. No historical objects/PDBs were reused.
Zero main-build warnings or compiler/linker failures. Exact source/object/executable/
PDB/toolchain identities and commands are in `out/recovery/adjustwindowrect-20261024-01/`.
277 objects retain identical code and named relocations; only hle_gui and xrt_loader
change. GetFocus, GetKeyState and SetKeyboardState function code remains identical.
79,226,692 linked generated-code bytes outside
relocation fields match their verified objects. Local helper sections retain the
same object-level coverage and linked-comparison limitation as the prior checkpoint.

## Native x86 / actual-runtime comparison

The identical project-owned x86 DLL runs natively and through the real lifter and
USER32 import adapter. **3,888 calls match exactly**: 12 styles, nine rectangles,
four BOOL menu bit patterns, three last-error sentinels and three placements.
Both WinDrv styles (`0x10cf0000` and `0x54000000`, menu 0) are covered. Negative and
nonzero origins, empty/inverted rectangles, signed integer limits, unaligned and
page-spanning buffers are included. All four output fields, return values, last-error,
surrounding bytes, stdcall cleanup and EBP/EBX/ESI/EDI preservation match.
All valid calls returned 1 and retained the supplied last-error. All 3,888 call/return
pairs are retained without dropped/truncated fixture events.

Eight deliberate invalid pointers raise seven native access violations and one guard
exception, caught by the native fixture. There is no API return/GetLastError result
for those interrupted calls. Translation stops before memory access with an explicit
unsupported diagnostic for NULL, low, uncommitted, read-only, no-access, partial,
guard and wrapping ranges. Guest SEH delivery of these pointer faults is unimplemented;
no success/error result is fabricated.

The adapter validates all 16 bytes for read/write page protection, marshals four signed
32-bit fields into a local RECT, calls actual Windows AdjustWindowRect and copies all
four fields back. No guest pointer is passed to USER32 and no host pointer enters guest
memory. No border dimensions, styles or results are fabricated. Other GUI behavior is
unchanged. Unbound imports retain their fatal behavior and now record raw x86 stack
words so the next API's arguments survive the bounded stop.

The genuine game call was additionally checked through the same native x86 DLL:
`(100,100,1640,1045) -> (92,69,1648,1053)`, style `0x10cf0000`, menu 0,
return 1, last-error 0. This is fixture validation, not another graphical client run.

## One bounded client continuation

Run: `experiments/xrt/results/raw/level/20261024-232919-09836e96-candidate`.
Exactly one translated graphical session, zero native graphical game sessions, existing
session locks, verified DXVK/DirectMusic IPC configuration and 60000-ms runtime watchdog.
Controlled exit 75. All **74,390 events** are contiguous, complete and untruncated;
zero dropped. The prior writable sandbox was archived intact before preparation.

| Observation | Independently verified result |
|---|---|
| Selected CS_Intro world | 0x12f52800, identified by paired LoadMap return |
| All observed selected-world lifecycle | 279 paired calls/returns per stage, 278 distinct actors, none unpaired |
| AdjustWindowRect | call 74354 / input 74355 / return 74356 |
| AdjustWindowRect stack | ESP 0x0120d44c -> 0x0120d45c; return 0x11103556 |
| OpenWindow progress | Passed AdjustWindowRect; entered native window-creation callbacks |
| OpenWindow / CreateWindowEx completion | Neither returned before the nested callback fatal |
| UGameEngine::Init | One entry, zero paired returns |
| UGameEngine::Tick / selected ULevel::Tick | Zero entries and zero paired returns |
| D3D CreateDevice / Clear / Present | Zero / zero / zero; no real device |

Callback messages include WM_GETMINMAXINFO, WM_NCCREATE, WM_NCCALCSIZE, WM_CREATE and
WM_SETTEXT. The stop occurs inside UWindowsViewport::ViewportWndProc during this
creation sequence, while OpenWindow remains on the stack. These callbacks establish
viewport progress, not completed creation or rendered frames. Existing DXVK factory,
adapter/capability/format queries are not device creation.

First remaining blocker: **IMM32!ImmAssociateContext**, fatal event 74379.
Thunk `0x11109ed6` (`WinDrv.dll+0x9ed6`), IAT `0x1110b2ac`, actual caller
`0x11105d59` in ViewportWndProc, expected return `0x11105d5e`, ESP `0x0120cb68`.
Exact arguments: **HWND guest token `0x0000126c`, HIMC NULL `0x00000000`**.
Seventeen raw stack words, snapshot disassembly, CPU/FPU/stack diagnostics and the
complete trace are retained locally. ImmAssociateContext was not implemented.

Cleanup released five DirectMusic tracked references, balanced one COM apartment and
released the D3D/DirectInput references. StickyKeys flags matched 510 before/after.
No orphan client/helper or unexpected process crash was observed.

## Acceptance and integrity

AdjustWindowRect, GUI/keyboard/window, class/callback, module and GetFocus regressions:
PASS. Compact commandlet/VM: all nine cases PASS against fresh native snapshot
references. UnrealScript compiler: 16 compiles, 12 executions and four expected
invalid-source failures PASS. Traced HelloWorld: PASS. Python: 158 discovered,
141 passed, 17 documented opt-in E2E skips, with XRT_FULL=1. The known classprobe
C4133 warning remains in its regression log; it is unrelated and unchanged.
No compiler failure, C1001, D8040 or unexpected crash occurred in this phase.

Protected manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`:
all 4,122 files, three protected trees and nine protected files match before/after.
Accepted/new executable/object/PDB identities, helper, both DXVK pairs, generated code
and pinned sources match after execution and acceptance. Original installation and
saves were not accessed. Existing expanded CRT findings (110 mismatches / 1,796
pending), six ACP932 differences and x87 limitations remain open; they are not
requalified here. No hardware-stability conclusion is drawn.

Smallest recommended next experiment: separately authorize native/translated
`ImmAssociateContext(hwnd,NULL)` with an owned window, typed HWND/HIMC ownership,
native context detach/restore, last-error and stdcall ABI measurement. No broader
IME expansion is established. Stop here; no further client session, renderer work,
Android implementation, push or release.

[Structured checkpoint](results/compare/adjustwindowrect_world_resume.json).
Full local evidence: `out/recovery/adjustwindowrect-20261024-01/`.
