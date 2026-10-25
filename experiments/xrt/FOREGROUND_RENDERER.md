# GetForegroundWindow genuine validation and renderer approach

2026-10-24, US Eastern. **Stopped at unmeasured D3D adapter-mode enumeration.**
Three bounded genuine translated client sessions; two additional small boundaries implemented.
The remaining authorized small-boundary slot is unused because the next encountered method is outside
the permitted USER32/GDI32/IMM32/minor viewport additions. No D3D query, device creation or renderer method
was implemented in this phase. No further client continuation was run after this stop.

Starting HEAD: `68ded6ebaba7b2f726c015d64d816b0e69312212`. Local commit details: `out/recovery/foreground-renderer-20261024-01/commit.json`.
All 542 initial working files and both Git patches were preserved under
`out/recovery/foreground-renderer-20261024-01/source-preservation/`. Earlier pending keyboard,
observer, CRT and build changes remain pending. No reset, history rewrite, push or release.

## GetForegroundWindow in the real client

The exact accepted executable `experiments/xrt/build/foreground-20261024-01/xrt_ucc.exe`,
SHA-256 `95848d05ff36db52eed2ed39e275fe368fb8ab8bfc13029435b8072294b70334`,
executed GetForegroundWindow at WinDrv.dll+0x4a12. Events **74442 -> 74443** pair the actual call/return.
Guest result is **NULL**; the pinned adapter maps guest zero only from actual host NULL.
Last-error is **0 -> 0**; ESP is `0x0120d414 -> 0x0120d418`; actual return is `0x11104a18`.
Execution continued to SetForegroundWindow at WinDrv.dll+0x4a58, with actual HWND token `0x126c`.

Two later sessions additionally record host `0` -> guest `0`, round-trip identity true, at event 74444.
All three sessions contain one paired foreground query. No non-NULL foreground query result is claimed.
Nine fresh native/translated fixture calls pass; EBP/EBX/ESI/EDI and stdcall ESP are fixture checked.
Genuine traces directly record ESP and caller/return, not the saved nonvolatile-register values.

## Additional measured boundaries

| Boundary | Native/translated | Final genuine result |
|---|---|---|
| SetForegroundWindow | 12 paired supported calls; visible game style 0x10cf0000, three error seeds, repeat/transition/NULL, callbacks and ABI; wrong-type guard | Events 74446 -> 74448; token 0x126c; actual FALSE; error 0 -> 0; ESP +8; return 0x11104a5e |
| SetActiveWindow | 15 paired supported calls including borrowed previous-HWND identity/reuse; three error seeds, repeat/transition/NULL, callbacks and ABI; wrong-type guard | Events 74449 -> 74450; input and actual previous HWND both token 0x126c; error 0 -> 0; ESP +8; return 0x11104a8f |

Both adapters call real USER32 with the existing typed HWND map and callback frame. Windows decides
the result. Unknown/wrong-type/cross-thread HWND paths stay guarded. No success, activation or initialization
is fabricated. TryRenderDevice entry/return observation and optional OpenWindow/Init return stop guards
were added without modifying generated code. The two sessions with new builds enable the return and first-tick
guards. The first accepted-binary session was bounded by the verified missing USER32 imports before any return.

## Exact executables and stopping evidence

| Genuine session | Executable SHA-256 | Complete events | First stop |
|---|---|---:|---|
| foreground-passed | `95848d05ff36db52eed2ed39e275fe368fb8ab8bfc13029435b8072294b70334` | 74472 | call to import user32.dll!SetForegroundWindow, which has no host implementation |
| setforeground-passed | `05df2310967b7e7eefb20f3f8f8950aa666eca031215b261982d20a68bbbfe34` | 74477 | call to import user32.dll!SetActiveWindow, which has no host implementation |
| setactive-passed | `8a4cd0e5a65b6ae8dd74cc2e26927993d1158e119237ce0900b2b30c57bae248` | 74466 | IDirect3D8::GetAdapterModeCount is unmeasured |

Intermediate executable: `experiments/xrt/build/setforeground-20261024-01/xrt_ucc.exe`.

Final executable: `experiments/xrt/build/setactive-20261024-01/xrt_ucc.exe`

SHA-256: `8a4cd0e5a65b6ae8dd74cc2e26927993d1158e119237ce0900b2b30c57bae248`

PDB SHA-256: `9cf347ff59c835623fead5b7ae15605207cd86229e7c10884b8ec185bca64089`

Runtime aggregate: `3fd406b922689a8bd0d6414c134c3ca30e43aae44ba09830fc23292e2740fe08`

Generated aggregate: `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`

First remaining blocker: **IDirect3D8::GetAdapterModeCount(adapter=0)**, guest interface `0x00015090`.
The actual indirect call is D3DDrv.dll+0xe9bd, vtable offset 0x18, return `0x0696e9c0`.
Import census records one call. Event 74454 records the boundary and event 74455 is the deliberate
unsupported-method fatal. The host method was not called and there is no paired return. The extra
generic a2..a6 words in this old guard are stack context, not arguments to this two-word COM call.
This is an adapter query on IDirect3D8, not an IDirect3DDevice8 instance or CreateDevice call.

## Highest verified milestones

| Final session | Entries | Paired returns |
|---|---:|---:|
| GetForegroundWindow | 1 | 1 |
| TryRenderDevice | 1 | 0 |
| OpenWindow | 1 | 0 |
| Engine.Init | 1 | 0 |
| Engine.Tick | 0 | 0 |
| Level.Tick | 0 | 0 |
| D3D CreateDevice / Clear / Present | 0 / 0 / 0 | 0 / 0 / 0 |

The viewport CreateWindowExW returns guest HWND `0x126c`, events 74362 -> 74440, ESP +52.
TryRenderDevice enters at event 74442 and remains pending. Its first accepted-binary session predates
the dedicated entry observer; its body execution is proven by the foreground callsite, not a separate
entry event. No OpenWindow or engine Init return, engine tick entry, selected-world tick or rendering claim.
Highest world milestone remains **T2: 279 paired lifecycle returns per stage across 278 selected-world actors**,
with zero unpaired selected-world lifecycle calls. The narrower LoadMap-only summary is retained separately.

## Build, regressions and integrity

Fresh serial recompilation used unique output directories. First new build reused 276 hash-verified
unchanged objects and rebuilt hle_gui, xrt_loader and xrt_events; final build reused 278 verified unchanged
objects and rebuilt hle_gui. All earlier objects, executables, PDBs and evidence remain in place.
Against the accepted foreground baseline, 276 object code/relocation sets remain unchanged; all
79,226,692 compared linked generated-code bytes match. No client-build warnings or internal compiler errors.
The earlier PDB limitation remains: 4,290 local helper sections have no matched public symbol.

Fresh affected capture/focus/window/class/GUI/module/IMM32/icon/cursor/coordinate fixtures pass, including
both new native/translated suites and the nine-call foreground-query fixture. Compact nine-case commandlet/VM,
UnrealScript compiler acceptance, traced commandlet and Python checks pass: **Ran 158 tests in 12.961s**.
Expected skips and the known class-fixture C4133 warning remain. No unrelated exhaustive CRT/ACP/x87 sweep.
Existing limits: **110 CRT mismatches / 1,796 pending; six ACP 932 differences; x87 status/tag,
large-input and double-rounding limitations**.

All three client traces are contiguous, untruncated and have zero dropped events. Each client has 96 successful
guest file opens, all resolved inside the isolated assets. Protected manifest
`3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`
(4,122 files, three trees, nine files), runtime/generated inputs, pinned compiler/SDK/USER32/IMM32,
DXVK x86/x64 pairs and IPC DirectMusic helper pass the before/after driver gates. Sticky and clip settings
match before/after each run; COM/DirectMusic/D3D/DirectInput cleanup is retained; no client/helper remains;
both session locks are released. Original installation and saves were not accessed.
Final preservation audit is retained in `out/recovery/foreground-renderer-20261024-01/final-integrity.json`.

Fixture development is preserved: native SetActiveWindow(NULL) invalidated an initial borrowed-window
expectation; the revised native transition passed. A copied comparison event prefix was corrected, and
an optional borrowed fixture activated a stock window outside the guest callback context, triggering the
runtime's explicit exit-76 guard. Fresh fixture _03 creates the stock window first and the guest test window
hidden, then makes measured transitions inside the adapter. All 15 calls pass. These are fixture diagnostics,
not genuine-client crashes; no protected input discrepancy occurred.

Smallest next experiment: separately authorize only a native x86 versus translated oracle for
**IDirect3D8::GetAdapterModeCount(adapter=0)** using the pinned DXVK pairs. Keep device creation and rendering
methods guarded; do not bundle enumeration, renderer implementation or a client resume into that measurement.

[Structured report](results/compare/foreground_renderer.json). Complete raw traces, commands, source snapshots,
fixture revisions, identities and cleanup: `out/recovery/foreground-renderer-20261024-01/`.
Primary USER32 contracts: [GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow),
[SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow),
[SetActiveWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setactivewindow).
