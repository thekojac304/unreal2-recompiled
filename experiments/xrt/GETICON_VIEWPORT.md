# Viewport icon, cursor, ownership and coordinate checkpoint

2026-10-24, US Eastern. **Stopped at the authorized limit of three additional boundaries.**
WM_GETICON, SetCursor, GetWindowThreadProcessId and MapWindowPoints pass native x86/translated comparisons.
Three genuine translated-client continuations were run. The final MapWindowPoints adapter is fixture-tested
and regression-tested; it has **not** run in a fourth genuine client continuation.

Starting HEAD: `ebdecc4398ca36ebdb89314f793defd490d7a961`. The scoped local commit is recorded in
`out/recovery/geticon-20261024-01/commit.json`; earlier keyboard, observer, CRT, build and other pending work
remains uncommitted. All 486 initial working files and both Git patches were preserved. No push.

| Boundary | Independent comparison | Genuine client evidence |
|---|---|---|
| WM_GETICON | 1,156 samples; 1,736 icon callback returns; 4,048 callback records; three explicit unsupported cases | SMALL2, SMALL and BIG each returned through nested default processing |
| SetCursor | 38 paired calls; two explicit unsupported cases | One paired return; cross-cursor token `0xfb000160`, previous token `0xfb000150` |
| GetWindowThreadProcessId | 34 paired queries; two explicit unsupported cases | One paired return, correct real owner thread/process IDs and four-byte output |
| MapWindowPoints | 627 paired calls; three explicit unsupported cases | Last observed unsupported call; final adapter not client-executed |

The icon bridge maps real NULL/non-NULL HICON results through typed borrowed identities in both directions.
Native class-icon fallback, nested queries and focus callbacks, last-error, ESP and EBP/EBX/ESI/EDI match.
An explicit large window icon can produce a distinct generated SMALL2 icon. Native lifetime evidence shows
that generated icon expires on replacement, while shared LoadIcon handles survive window destruction.
Borrowing grants no ownership or lifetime extension. Unknown/wrong-type results stop. The unmeasured
CallWindowProc WM_GETICON result path stops explicitly, preventing native handle narrowing. Only zero DPI
and the three measured selectors are supported. No fabricated NULL fallback was introduced.

SetCursor calls real USER32, returns its actual previous cursor, and preserves shared/previously unseen owned
cursor identity, NULL transitions, independent thread state, errors and ABI. Icon tokens and unknown values stop.
GetWindowThreadProcessId queries real USER32 IDs, which agree with this runtime's existing PID/TID values.
Optional, unaligned and page-crossing DWORD writes match; failed HWND queries leave output untouched,
including invalid-output addresses that are never probed on failure. Valid-window output faults remain unsupported.

MapWindowPoints marshals one through four read/write POINTs and calls USER32 once for the entire array,
preserving two-point mirrored RECT behavior, all coordinate bits and packed signed displacement. Screen,
child, ordinary and RTL window mappings, extreme coordinates, failed/dead HWNDs, guards, errors and ABI match.
Zero/greater-than-four counts, wrong-type handles and invalid point buffers remain explicit unsupported paths.
The native pointer-fault negatives are caught inside their oracle drivers; no unhandled client crash occurred.

The exact last genuine call is `MapWindowPoints(viewport=0x126c, screen=NULL, points=0x0120c6bc, count=2)`
at **WinDrv.dll+0x405d**, with POINTs **(0,0), (1540,945)**. The complete 16-byte input is independently
recoverable from retained stack words 8 through 11. It is included in the native/translated corpus.

| Independent milestone, last genuine run | Verified result |
|---|---|
| SetFocus | 1 call, 0 paired returns |
| Viewport CreateWindowEx | No paired viewport return; two earlier splash/control windows returned |
| UWindowsViewport::OpenWindow | 0 paired returns |
| UGameEngine::Init | 0 paired returns |
| UGameEngine::Tick | 0 entries, 0 paired returns |
| Selected-world ULevel::Tick | 0 paired returns |
| D3D CreateDevice / Clear / Present | 0 / 0 / 0 |

Highest verified world milestone remains **T2**: 279 paired lifecycle returns per stage across 278
selected-world actors, world `0x12f52800`, with no unpaired lifecycle calls.
There is no completed engine initialization, game D3D device, frame or selected-world tick claim.

| Genuine continuation | Binary SHA-256 | Complete events | Next observed stop |
|---|---|---:|---|
| WM_GETICON | `16831d0bd1cb45f95fbab96b6a12458297bd6c1cf5a7de9d130a60b3b7ed6e67` | 74418 | SetCursor, WinDrv+0x3965 |
| SetCursor | `beefef48a22ee32f85012d88f626abb56387f1f2cc7d225bdb38f97f3e364107` | 74423 | GetWindowThreadProcessId, WinDrv+0x607e |
| Window owner IDs | `be3d417caf417b81634b265ad54d4b92155057eeab19073b737e8de916a2fd16` | 74425 | MapWindowPoints, WinDrv+0x405d |

Every run retains the full ordered trace with **zero dropped/truncated events**, paired ABI evidence,
raw arguments, cleanup, source/binary identities and unchanged protected-input gates. No native game reference
was run, and neither the original installation nor saves was accessed. Sticky settings were restored and no
client or DirectMusic helper remained. The final map adapter's next genuine blocker is **unknown**.

Final fixture/regression executable: `experiments/xrt/build/mappoints-20261024-01/xrt_ucc.exe`

SHA-256: `22158edc85c5bcfcdeffc6aafc80ff63a4a79555bde0d8abc158a4cbea0aa7c2`

PDB SHA-256: `a7dc176d8957aa0dceeb6506d99317dac77b0a9003c901e867b2200409f8ec0c`

Last genuine-client executable: `experiments/xrt/build/windowids-20261024-01/xrt_ucc.exe`

SHA-256: `be3d417caf417b81634b265ad54d4b92155057eeab19073b737e8de916a2fd16`

Runtime aggregate: `5ccc65cadcd0aef3e4788065e0f9952bf1bdadeb2f6cd8d048b4ee0c0562fda5`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

The initial 279 objects were built fresh and serially in geticon-20261024-01. Later unique directories
reuse only hash-verified unchanged objects and serially rebuild affected runtime units. All checkpoints remain.
Final code comparison: 277 objects unchanged from SetFocus; only hle_gui and the opt-in tick stop differ.
All 79,226,692 compared linked generated-code bytes match; prior keyboard/focus function code matches.
The existing local-helper coverage limit remains: 4,290 code sections lack a matched public PDB symbol.
Client-build warnings/internal compiler failures: zero. The affected class fixture retains its known C4133 warning.
Fixture development corrected a missing driver GDI link library and parent-before-child cleanup; those initial
diagnostics remain preserved. The latter was a fixture cleanup assertion, resolved before differential comparison.

Final affected GUI/window/focus/class/module checks pass. Compact nine-case commandlet/VM, compiler acceptance,
traced commandlet and Python checks pass (158 tests, 17 expected skips); exact commands,
results and scopes are in the structured report.
The first-tick stop is separately tested against the actual runtime: enabled stops before the next event;
absent/disabled continues. This synthetic stop test is not world evidence.

Protected manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`: 4,122 files, three protected trees and nine
protected files verified. Accepted binary/objects, generated inputs, MSVC/SDK headers/libraries, USER32/IMM32,
DXVK x86/x64 pairs and the pinned DirectMusic helper retain their identities. Existing CRT **110 mismatches /
1,796 pending**, **six ACP 932 differences**, and x87 status/tag/large-input/double-rounding limits remain visible.
These unrelated CRT/ACP/x87 suites were not broadened in this phase.

The remaining gate is owner-authorized client confirmation of the final MapWindowPoints adapter. The smallest
next experiment is one bounded continuation using the final binary, recording its paired return and stopping at
the next genuine boundary, D3D device creation or first paired selected-world tick. No further API implementation
is included in this completed authorization. No renderer, Android, editor, remote push or release work occurred.

Evidence: `out/recovery/geticon-20261024-01/`, the three `*-passed/` source/run snapshots, final-runtime-source/,
all raw level run directories, and [structured results](results/compare/geticon_viewport.json).
Primary API references: [WM_GETICON](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-geticon),
[SetCursor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setcursor),
[GetWindowThreadProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowthreadprocessid),
[MapWindowPoints](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapwindowpoints).
