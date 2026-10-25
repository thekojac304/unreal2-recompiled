# GetAdapterDisplayMode validated; one bounded client stops at CheckDepthStencilMatch

2026-10-24 phase, US Eastern. Starting commit: `610f9ef63b24274ad4441225dafc69d10f570a37`.
The measured typed `IDirect3D8::GetAdapterDisplayMode` bridge is implemented and validated.
One translated graphical client passed the genuine boundary and stopped at **CheckDepthStencilMatch**
at **D3DDrv.dll+0xef12**. CreateDevice reached: **False**.
No device or rendering implementation was added. The local commit is recorded in
`out/recovery/d3d8-display-20261024-01/commit.json`; the earlier unrelated pending changes remain pending.

Executable: `experiments/xrt/build/d3d8-display-20261024-01/xrt_ucc.exe`.
SHA-256: `c892b268b6252b606aa8a591d273c846e74c0f397f0b0289468ae9548acede6c`.
Previous accepted executable remains
`005edc05d720fbc1dbd5ff900716044701eb13a6b010c3c57526636e137657e5`.

## Native and translated comparison

| Backend / execution | Adapter 0: Width, Height, RefreshRate, Format | Adapter 1 | HRESULT | Last-error seeds |
|---|---|---|---|---|
| Native x86 DXVK 3.1.1, two processes | 2560, 1440, 240, 22 | Same | 0 | All retained |
| Native x64 DXVK 3.1.1, two processes | 2560, 1440, 240, 22 | Same | 0 | All retained |
| Translated x86 guest / x64 DXVK, two processes | 2560, 1440, 240, 22 | Same | 0 | All retained |

The actual sixteen bytes are `000a0000 a0050000 f0000000 16000000`, in little-endian
DWORD order, with offsets 0/4/8/12. Each native process makes sixteen seeded/repeated calls
per adapter/index and an independent second-object call. Seeds 0, 18, `0x13572468`, and
`0xffffffff` remain unchanged. Invalid indices 2, 3, `0xffff`, `0x7fffffff`, `0xffffffff`
return actual `0x8876086c` and preserve all sixteen `0xa5` bytes plus the 32 adjacent canary
bytes. Results are stable within and across processes. No display-mode architecture
differences were observed.

The native-only pointer oracle measures 100 calls per architecture, with safely caught write
access violations for valid adapters and NULL, address 1, PAGE_NOACCESS, PAGE_READONLY and
an eight-byte range crossing into PAGE_NOACCESS. Invalid adapters return `0x8876086c` even
with those pointers. All seeds and observed buffers are preserved; both architectures agree.
An access violation has no completed HRESULT: the `deadbeef` record is only a sentinel.
Those invalid pointer combinations remain explicit translated unsupported stops. The bridge
does not synthesize guest access violations or claim to emulate invalid-adapter/invalid-pointer
precedence.

The x86 native and translated ABI probes verify sixteen calls/process with zero ESP delta,
this-plus-two-argument stdcall cleanup, and EBP/EBX/ESI/EDI seeds
`12345678/23456789/3456789a/456789ab`. The native x64 wrapper verifies sixteen calls with
zero RSP delta, all eight nonvolatile GPRs and XMM6..XMM15 preserved. QueryInterface identity,
AddRef/Release, distinct factory objects, native unload, translated cleanup of two outstanding
references and all sixteen guest COM vtable slots pass.

Each translated process compares **9,468 values**, with **129 paired display-mode calls**,
**736 paired enumerations** and **33 paired mode-count calls**. All **17 negative guards**
pass, including stale interfaces, NULL/uncommitted/wrapping output, unsafe mode-count adapter
indices, RegisterSoftwareDevice and CreateDevice. Both 3,796-event positive traces are complete
and have zero drops. The existing initial x86 enumeration difference reappeared: it exposes
format 23 as well as format 22. Full repeat-native enumeration and translated lists compare
exactly. The initial difference is retained without normalization or an unconditional claim
that x86 and x64 enumeration always agree.

## Implementation

The existing typed object registry resolves the guest interface. Actual GetAdapterCount validates
the adapter index; the measured safe GetAdapterDisplayMode method itself returns invalid-index
failures. The existing full-range guard checks all sixteen guest bytes for overflow, commitment
and writable protection before the backend call. A separate local D8Mode receives the actual
x64 result, with four explicit DWORD reads/writes. Actual HRESULT, all output fields and guest
last-error are retained. No native COM pointer reaches guest memory. All earlier enumeration,
COM identity/ownership and CreateDevice guards are unchanged.

## Genuine client result

Run: `experiments/xrt/results/raw/level/20261025-041622-7e0bcde5-candidate`.
The single session uses manifest-bound isolated assets, pinned x64 DXVK D3D8/D3D9,
pinned DirectMusic IPC, both session locks and a 60-second runtime watchdog.
There was no graphical reference run or retry.

The actual adapter-0 call at **D3DDrv.dll+0xec82**, interface `0x00015090`,
writes `0x0120d3c8` and returns to **0x0696ec85**. Entry and paired
return sequences: **75524/75527**.
HRESULT is **0x00000000**, last-error **18**,
and output is **Width=2560, Height=1440, RefreshRate=240, Format=22**.
Guest ESP increases by sixteen bytes; the actual return address matches the expected return.
All successful client enumeration outputs still match the exact measured native x64 list.

| Boundary | Calls | Paired returns |
|---|---:|---:|
| d3d8_mode_count | 154 | 154 |
| d3d8_enum | 152 | 152 |
| d3d8_display | 1 | 1 |
| viewport_try_render | 1 | 0 |
| viewport_open | 1 | 0 |
| engine_init | 1 | 0 |
| engine_tick | 0 | 0 |
| level_tick | 0 | 0 |

Highest verified selected-world milestone remains **T2**: the complete observed actor lifecycle,
with {'PreBeginPlay': 279, 'BeginPlay': 279, 'PostBeginPlay': 279} paired stage returns across
278 distinct actors. Engine Init, OpenWindow and
TryRenderDevice have no completed return. Engine Tick and selected-world ULevel::Tick have
no entry or return. No device or rendered frame exists. The exact first remaining blocker and
all guest arguments are retained in the structured client audit:

`{"a1": 0, "a2": 1, "a3": 22, "a4": 22, "a5": 77, "a6": 110617576, "arguments": {"Adapter": 0, "AdapterFormat": 22, "DepthStencilFormat": 77, "DeviceType": 1, "RenderTargetFormat": 22}, "callsite": "D3DDrv.dll+0xef12", "kind": "d3d8_unimplemented", "method": "CheckDepthStencilMatch", "return_address": "0x0696ef15", "seq": 75530, "thread": 0}`

The labelled arguments follow the typed method signature; the generic raw event also retains
an adjacent stack word in a6, which is not a sixth CheckDepthStencilMatch argument.

## Build, regressions and integrity

The fresh serial build compiles all **279 objects** and links into a unique directory; no
historical objects or PDBs are reused or overwritten. Complete compile/link commands, source
hashes, pinned compiler/SDK headers/libraries, DXVK pairs, helper, environment and output hashes
are in `out/recovery/d3d8-display-20261024-01/{preflight,build}.json`. Client warnings: 0.
Final native and translated fixture builds have no warnings or internal compiler errors.

All seventeen affected GUI/window suites, the nine-case compact commandlet/VM comparison,
all four UnrealScript compiler variants, traced hello and Python checks pass:
**Ran 158 tests in 11.174s; OK (skipped=17)**. The pre-existing class-fixture warning and expected skips
remain. Known limits remain **110 CRT mismatches / 1,796 pending**, **six ACP 932 differences**,
and x87 status/tag, large-input and double-rounding limits.

Final integrity verifies 13,791 earlier build files,
17,335 earlier raw files, 570
previous working files, earlier phase evidence, the protected manifest and all pinned inputs.
Old and new executable identities match. Runtime aggregate:
`13d82fcc5d88f13073c26e9df9922c2c1de27312554ec01880630775983079e8`; generated aggregate:
`93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`. The genuine trace records
**75,542 contiguous events with zero drops**; all 113 audited
fixture/acceptance traces have zero drops. All 96 successful
guest file opens resolve within isolated assets. Sticky/clip state is restored, cleanup is
retained, no client/helper remains and both locks are released. Original installation and
saves were not accessed. No remote push, release, Android work or unrelated refactoring occurred.

Fixture development is retained: v01 had a Windows macro-name collision; v02 needed an explicit
MASM XMM operand size. Both source snapshots/build outputs remain. A Python driver initially
used the same filename for a negative report and its command record; that one expected-stop
report was overwritten by its command record, which remains under display-negative-driver-error.
The corrected negative driver writes separate files and all four display guards pass. Positive
differential outputs were already exact and were preserved. There was no unexpected native
crash, translated result mismatch, internal compiler failure or protected-input change.

Smallest next experiment: **Fixture-only native x86/x64 and translated characterization of CheckDepthStencilMatch with {"Adapter": 0, "AdapterFormat": 22, "DepthStencilFormat": 77, "DeviceType": 1, "RenderTargetFormat": 22}, including HRESULT, last-error 18, invalid inputs and COM ABI. Keep CreateDevice and rendering guarded.**
This authorized phase is complete and stops after reporting.

[Structured report](results/compare/d3d8_display_renderer.json).
Full hashes and evidence: `out/recovery/d3d8-display-20261024-01/phase-artifacts.json`.
