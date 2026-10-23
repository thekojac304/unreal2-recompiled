# Graphics startup checkpoint — 2026-10-22 (US Eastern)

The original passes its former HAL-capability barrier with **dgVoodoo2 2.87.5 x86 over D3D11** and opens
`CS_Intro.un2` inside its genuine `UGameEngine::LoadMap` path. The translated client completes splash loading,
including the real host dialog and translated callbacks. It stops in the subsequent Window.dll constructor at
`KERNEL32!GetModuleHandleW`, before `UGameEngine::Init`.

| Milestone | Result and scope |
|---|---|
| G0 | PASS, native API probe and original client HAL caps with dgVoodoo2 |
| G1 | PASS, standalone x86 probe: windowed 320x240 device, Clear and Present, both adapters |
| G2 | PASS, original passes the former D3D8 HAL failure and enters LoadMap |
| G3 | PASS, translated splash bitmap/dialog/callback/display path returns to launcher initialization |
| G4 | OPEN, translated UGameEngine::Init not reached |
| G5 | OPEN, both paths do not yet reach comparable map loading |
| G6 | PASS **original only**, selected map opened after LoadMap entry; no completed level/world/frame claim |

The game itself has not been shown to create/present a D3D device. The standalone clear frame is only a device
milestone. The original stops during CS_Intro initialization at `Cast of NULL to Font failed`, following missing
`SubTFonts` package exceptions. Observed Entry actor events and CS_Intro PostLoad do not establish a completed
selected-level initialization, simulation tick, or world rendering.

## Exact graphics reference

All wrappers came from official releases; downloads, original assets, generated C, binaries and raw traces remain
in ignored directories. No original-install files, drivers, registry, global settings or desktop modes were changed.

| Configuration | Version / PE architecture | Loaded implementation | Probe / original result |
|---|---|---|---|
| Windows D3D8 | 10.0.26100.9278 / x86 `0x14c` | SysWOW64/d3d8.dll | Both adapters HAL `8876086a`; original stops at same caps query |
| [crosire/d3d8to9](https://github.com/crosire/d3d8to9/releases/tag/v1.16.0) | 1.16.0 / x86 `0x14c` | sandbox d3d8.dll, system d3d9.dll | Both adapters HAL `8876086a`; original stops at same caps query |
| [dgVoodoo2](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.5) | 2.87.5 / x86 `0x14c` | sandbox D3D8.dll, system d3d11.dll | Both adapters HAL, CreateDevice, Clear, Present `00000000`; original enters LoadMap |

SHA-256 (full, not abbreviated):

- Windows SysWOW64/d3d8.dll: `d61d6c890592e992804fb5a1ed5fc2ce3413177c9ee67f9babaf1d4955884bb4`.
- d3d8to9 d3d8.dll: `122928cfe225c25d30decf7184a5d37e490cecf3b58256ba3206c7e1853f8ab8`.
  Download digest matched the GitHub release-asset digest.
- dgVoodoo2 release zip: `5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850`.
  Download digest matched the GitHub release-asset digest.
- Extracted dgVoodoo2 MS/x86/D3D8.dll: `d03e2562178db1fcf3493fc0a0b23a465e35c55d73adb3ec095be866cd662704`.
  File version 4.8.2.134; product version 2.8.7.5; description identifies 2.87.5 Direct3D8.
- Effective dgVoodoo.conf: `86d97ac3a5b94990cc7b664970dd7185449fc7cc32f817e469d70651ce78ab89`.

Use the complete shipped dgVoodoo.conf with exactly three local overrides: `OutputAPI = d3d11_fl11_0`,
`FullScreenMode = false`, `CaptureMouse = false`. No dgVoodoo control-panel or global configuration was used.
The retained exact working setup is `sandbox_cmp/graphics-client/0e97fce51f5a-dgvoodoo/System/`; the smaller
API-probe setup is `sandbox_cmp/graphics-probes/dgvoodoo/`. `tools/xrt/graphics_reference.py` reproduces the
configuration from the official archive, checks the pinned DLL hash and x86 machine type, and refuses an existing
sandbox destination. Each invocation copies all staged content, restores pristine config/Golem.u, and records
input hashes and writes. Game arguments stay `CS_Intro.un2 -windowed -nosound -NOMMX -NOSSE`.

The probe enumerates two AMD Radeon RX 7900 XT outputs. System/D3D9 descriptions report vendor/device 1002/744c;
dgVoodoo reports its own DX API adapter and complete D3DCAPS8 words. Raw probe logs retain adapter modes and all
53 capability DWORDs, plus every HRESULT. Device creation uses HAL with software vertex processing, one X8R8G8B8
back buffer, discard swap effect, no depth buffer, no multisampling, and windowed presentation.
`8876086a` is D3DERR_NOTAVAILABLE; this experiment localizes failure to the system D3D8/D3D9 capability path.
It does not diagnose the vendor driver's internal cause. dgVoodoo's D3D11 path supplies a measured working alternative.

A 32-bit wrapper is **not** loaded into the translated 64-bit host. A future translated D3D adapter requires a
compatible host ABI, or a separately designed process bridge; no renderer implementation was added here.

## Translated GUI boundary and tests

`runtime/hle_gui.c` adds real host adapters for:

- USER32: GetDC, ReleaseDC, CreateDialogParamA/W, GetDlgItem, GetSystemMetrics, SetWindowPos,
  SendMessageA/W (observed STM_SETIMAGE/IMAGE_BITMAP only), UpdateWindow, DestroyWindow, GetWindowRect.
- GDI32: CreateDIBitmap, DeleteObject, GetDIBits (pixel validation).
- COMCTL32: InitCommonControls, including ordinal #17 (checked against the host's named export).

Guest handles are typed table tokens; host handles/pointers never enter guest structures. Acquired desktop DCs
retain owner/thread provenance; borrowed callback DCs cannot be released as acquired ones. Bitmaps use actual GDI
storage and deletion. Dialog templates come from resource-only mappings of the x86 guest image; the host never
executes that image. Dialog/child tokens survive until destruction. Dialog fonts are borrowed tokens owned by
the dialog's lifetime. Failed resource mapping returns immediately with the host error.

The callback bridge runs translated x86 DLGPROC code via xrt_call_guest, with a copied suspended CPU and guest
stack scratch. It supports nested callbacks, synchronizes last-error state, marshals WINDOWPOS, MINMAXINFO and
NCCALCSIZE_PARAMS (including embedded handles/pointers), and copies writable fields back. HWND/HDC/HFONT parameters
are translated. The zero-argument theme destruction notification 0x90 was measured and is accepted only with both
arguments zero. Unsupported messages, regions, returned brushes, pointer layouts, replacement-image ownership,
and unimplemented APIs fail explicitly. This is a measured splash/dialog subset, not general USER32/GDI support.
C++ exception propagation across host callback frames remains unsupported by the existing EH design.

`experiments/xrt/tests/gui_boundary/build.cmd` compiles a project-owned x86 DLL and resource, then lifts that exact
DLL and runs it with the real 64-bit runtime (no simulated callback). Native and translated logs match and return 0:

- Actual 2x2 bitmap creation and all 12 non-padding BGR bytes read back identically.
- Both A/W dialog creation, child lookup and absent child, metrics, real positioning and update.
- Init LPARAM arrives unchanged; a callback reenters SetWindowPos during WM_INITDIALOG.
- WINDOWPOS callback changes width 80 to 81; GetWindowRect confirms the host applied it.
- ReleaseDC, DestroyWindow, DeleteObject and their invalid second operations match.
- Missing A/W dialog resource returns NULL and error 1814.

## Evidence and regression scope

Raw results under `experiments/xrt/results/raw/graphics-startup/`:

- `0e97fce51f5a-dgvoodoo`: final driver and exact working reference; complete, zero dropped events. HAL caps S_OK;
  LoadMap entered twice. FileReader.open sequence 111 names `..\Maps\CS_Intro.un2`; immediately following
  FileReader.CreateFileW.return sequence 112 on the same thread returns a valid handle (`00000df4`).
- `e2c9936344d7-d3d8to9`, `a93e67f77825-system`: controlled milestone/file-observer runs; both retain the HAL failure,
  with intended DLL paths confirmed by loader events. No LoadMap entry.
- `dgvoodoo-d3d11-windowed-probe.txt`, `d3d8to9-probe.txt`, `system-probe.txt`: native API outcomes.

The translated final-build run and regression invocation IDs are recorded in
`results/compare/graphics_startup.json`; registers, stack/history and events remain in raw/level.
Build `build/graphics-startup-final-checkpoint/` recompiles all client/runtime sources in a fresh directory and
reuses only the SHA-checked full checkpoint's unchanged generated object set. Its client-identity.json binds
runtime sources, generated sources, baseline objects, binary and all newly compiled objects. It has no compiler
warnings. Earlier baseline directories and the original clean HEAD `15a34f4` are preserved.

Validation: GUI oracle PASS; existing client-startup tests PASS; C++ exception oracle 6 positives + 2 deliberate
negatives PASS; Python unit suite 142 tests, 17 expected skips; nine registered commandlet/VM cases PASS in 27 runs,
then 9 runs on the subsequent clean client build. Two full compiler invocations each pass 16 compiles and 12
execution cross-checks. Final resource-error guard changes receive the focused GUI oracle and final-client smoke
checks; they do not change CRT, compiler, guest instruction or exception implementations. Exact build/run identities
and scopes are in the public JSON.

An exploratory original/translated overlap hit Unreal II's real single-instance check; that candidate run
`20261023-030816-c5178740` is excluded. All client drivers now take the same graphics-client-session lock before
restoring or staging input. A regression proves a held lock cannot restore the shared config. Broad launcher-import
instrumentation also induced early original AVs (`a1351913536a`, `9be58b54dbde`, `472bea40dda3`); those runs are
excluded from capability/game comparisons. Final native observers use only explicit instruction breakpoints, with
no import census. Earlier short Core-import census deadlines likewise do not establish client outcomes.

Existing CRT file I/O, enumeration, heap and FILE-layout discrepancies remain visible at the prior checkpoint;
none was hidden or broadly rewritten. No Android, music, Golem-animation or editor-feature work was added.

## Smallest next steps

1. Translated: implement GetModuleHandleW with real module identity/lifetime rules for Window.dll's observed
   SHELL32 lookup, then its GetProcAddress and RICHED32 loading boundary. Do not invent an absent module or pass
   a 32-bit guest module/function pointer into the 64-bit Windows loader. Continue one observed failure at a time
   toward UGameEngine::Init; class/font/window initialization may require further adapters.
2. Original: add the dynamically referenced SubTFonts dependency to a new isolated sandbox from the legitimate
   installation, then repeat the same working dgVoodoo config and genuine LoadMap command. Observe completion
   before claiming CS_Intro world initialization. Device creation/presentation by the actual client still requires
   direct observers after its missing-font blocker is cleared.
