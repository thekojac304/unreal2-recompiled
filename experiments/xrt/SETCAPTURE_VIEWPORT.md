# SetCapture and viewport creation checkpoint

2026-10-24, US Eastern. **Stopped at the limit of three additional implemented boundaries.**
SetCapture, ClipCursor(NULL), callback 0x00ae (8,0), and GetForegroundWindow pass native x86/translated fixtures.
Three genuine client continuations were run. The final GetForegroundWindow adapter is fixture/regression-tested;
it has **not** run in a fourth genuine client. The next blocker after that adapter is unknown.

Starting HEAD: `734b8c22360af3d120a6c78dd9b43078ddc9580f`. Scoped local commit identity is retained in
`out/recovery/setcapture-20261024-01/commit.json`. All 512 initial working files and both Git patches were preserved.
Earlier pending keyboard, observer, CRT and build work remains uncommitted. No push or release.

| Boundary | Differential result | Genuine client result |
|---|---|---|
| SetCapture | 55 supported paired calls; two explicit unsupported cases | NULL returned NULL, last-error 0 -> 0; call/return 74403 -> 74404 |
| ClipCursor(NULL) | Six paired calls; original clip restored; non-NULL guarded | Returned 1, last-error 0 -> 0; 74405 -> 74406 |
| Window callback 0xae (8,0) | 24 A/W callback/default-procedure returns; two argument guards | One callback returned 0, last-error 0; event 74435 |
| GetForegroundWindow | Nine calls, actual NULL results, errors and ABI match | Encountered but final adapter not client-executed |

SetCapture calls real USER32 and returns its actual previous HWND through typed guest tokens.
Its exact genuine return address is `0x111041bc`, with ESP `0x0120c6a8 -> 0x0120c6b0`.
No native HWND enters guest memory and no capture state is fabricated. NULL is sent to SetCapture itself.
Native tests cover A/B/A, same HWND (including its real WM_CAPTURECHANGED), NULL/ReleaseCapture interaction,
invalid/destroyed handles, three error seeds, creation, borrowed identity and callback reentrancy.
Wrong-type native mutex and guest-token cases are retained. Native unattached foreign-window attempts
leave both queues unchanged; translation explicitly stops before cross-thread capture.

ClipCursor supports only NULL. It calls USER32 once; no guest RECT path is inferred.
Callback 0xae supports only the observed scalar tuple through the existing guest/default procedure frame.
There is no new drawing implementation. GetForegroundWindow calls USER32 and uses the existing borrowed
window-token mapping. Its fixture observed NULL; non-NULL query coverage is not claimed.
The capture/focus suites separately exercise that shared mapping with real borrowed HWNDs.

| Last genuine milestone | Entries | Paired returns |
|---|---:|---:|
| SetCapture | 1 | 1 |
| SetFocus | 1 | 1 |
| Viewport CreateWindowExW | 1 | 1 |
| UWindowsViewport::OpenWindow | 1 | 0 |
| UGameEngine::Init | 1 | 0 |
| UGameEngine::Tick | 0 | 0 |
| Selected-world ULevel::Tick | 0 | 0 |
| D3D CreateDevice / Clear / Present | 0 / 0 / 0 | 0 / 0 / 0 |

Viewport CreateWindowExW returned guest HWND `0x126c`: events 74360 -> 74438,
ESP `0x0120cfd0 -> 0x0120d004` (52 bytes), actual return `0x11011112`.
Two earlier splash/control returns are kept separate. SetFocus paired at 74368 -> 74426.
Highest verified world milestone remains **T2**: 279 paired lifecycle returns per stage across
278 actors in selected CS_Intro world `0x12f52800`, with no unpaired lifecycle calls.
There is no Init, OpenWindow, engine-tick or selected-world-tick completion claim.

Last actually encountered blocker: **USER32!GetForegroundWindow**, no arguments, at
WinDrv.dll+0x4a12 (`UWindowsViewport::TryRenderDevice`), expected return `0x11104a18`.
This is an encounter, not a D3D device call. The factory and adapter queries are not a device.

| Genuine continuation | Binary SHA-256 | Complete events | Next observed stop |
|---|---|---:|---|
| setcapture-passed | `447606877a1117e7c37f8ba88b4b6310d8676bf78f1e5449e06417eed4a2a123` | 74433 | call to import user32.dll!ClipCursor, which has no host implementation |
| clipcursor-passed | `540b786d775d7a72f0390375fde234df89f120e4c0c288e6f1e495ee95a5bea6` | 74445 | dialog callback message 0xae unsupported |
| windowae-passed | `7683cb18fbf55dac4f1e276ade1188217677d73dbd6681a7b986f5ce5593d1d3` | 74468 | call to import user32.dll!GetForegroundWindow, which has no host implementation |

Final fixture/regression executable: `experiments\xrt\build\foreground-20261024-01\xrt_ucc.exe`

SHA-256: `95848d05ff36db52eed2ed39e275fe368fb8ab8bfc13029435b8072294b70334`

PDB SHA-256: `1d05918b8d988e7db46410b2a824524463dfa50dad72e5a68e1b7513d93c28da`

Last genuine-client executable: `experiments\xrt\build\windowae-20261024-01\xrt_ucc.exe`

SHA-256: `7683cb18fbf55dac4f1e276ade1188217677d73dbd6681a7b986f5ce5593d1d3`

Runtime aggregate: `6c2637aa4c34a69bdfa90cd50551f482e0848f9c39d90a8c86d26cd6403ffb8c`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

The first build compiled all 279 objects fresh and serially. Three later unique directories
reused only hash-verified unchanged objects and serially recompiled hle_gui. All checkpoints remain.
Final comparison: 278 unchanged objects, all 79,226,692 compared linked generated-code bytes match.
Client-build warnings and internal compiler failures: zero. The earlier PDB limitation remains:
4,290 local-helper code sections lack a matched public symbol. The class fixture retains its known C4133 warning.

All affected capture, GUI/window/focus/class/module, icon/cursor/coordinate and IMM32 regressions pass.
Final compact nine-case commandlet/VM, compiler acceptance, traced commandlet and Python checks pass
(Ran 158 tests in 10.887s; expected skips retained). No unrelated exhaustive CRT/ACP/x87 sweep was added.
Existing limits remain: **110 CRT mismatches / 1,796 pending**, **six ACP 932 differences**,
and x87 status/tag, large-input and double-rounding limitations.

Every client run retained full contiguous traces with zero dropped/truncated events, arguments,
paired ABI evidence, cleanup and exact source/binary identities. All successful guest file opens
resolve inside isolated assets. Original installation and saves were not accessed. Sticky settings
were restored; measured clip settings were unchanged after cleanup; no client/helper remained and both
session locks were released. Every protected-input gate before/after every client passed.
Manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`: 4,122 files, three protected trees and nine protected files.
Prior binaries/objects/evidence, runtime/generated inputs, USER32/IMM32, compiler/SDK inputs,
DXVK x86/x64 pairs and DirectMusic helper retain their pinned identities.

Fixture development evidence remains: expired identity normalization corrected in a fresh capture fixture;
GetCursorPos denied/error 5 and DPI-scaled metric assumptions removed from the clip oracle;
native message delivery replaced the unencountered guest-send test path; an ordinary C2488 fixture
prototype diagnostic was corrected in a fresh directory. These were fixture diagnostics, not client crashes
or internal compiler failures. No non-NULL clip, restricted region or broader theme protocol is claimed.

Detailed evidence and cleanup: `out/recovery/setcapture-20261024-01/`, its three run/source snapshots,
the four build directories and [structured report](results/compare/setcapture_viewport.json).
Primary contracts: [SetCapture](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setcapture),
[ReleaseCapture](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-releasecapture),
[WM_CAPTURECHANGED](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-capturechanged),
[ClipCursor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clipcursor),
[GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow).
