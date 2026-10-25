# CheckDepthStencilMatch validated; one client stops at CreateDevice

2026-10-25, US Eastern. Base commit: `59847df3336e0f203b89360c01e6ff886ad35aad`.
The typed bridge forwards all five scalar arguments to the real pinned x64 DXVK method.
The genuine call at **D3DDrv.dll+0xef12**, return **0x0696ef15**, returns
**HRESULT 0x00000000, last-error 18**.
Exactly one graphical continuation ran; CreateDevice reached: **True**.
No CreateDevice or rendering implementation was added. Local commit identity is retained in
`out/recovery/d3d8-depth-20261025-01/commit.json`. Earlier unrelated pending work remains pending.

Executable: `experiments/xrt/build/d3d8-depth-20261025-01/xrt_ucc.exe`.
SHA-256: `74866a16b8e1dfd5b7feaa609c56538cd469bc4ee632c95a4cc829830c2d693a`.
Previous accepted executable remains `c892b268b6252b606aa8a591d273c846e74c0f397f0b0289468ae9548acede6c`.

## Native and translated characterization

The genuine `(Adapter=0, DeviceType=1, AdapterFormat=22, RenderTargetFormat=22,
DepthStencilFormat=77)` query returns actual `S_OK` in native x86, native x64 and
translated x86 using x64 DXVK 3.1.1. No compatibility result was synthesized.
The 53-case corpus covers both valid adapters and indices 2, 3, 65535, 2147483647,
4294967295; device types 0, 1, 2, 3, 4, 2147483647, 4294967295; depth formats,
unknown/compressed/color/depth adapter and render-target formats; and mixed combinations.

For adapter 0, device type 1, adapter/render-target format 22:

| DepthStencilFormat | Actual HRESULT |
|---:|---|
| 77 | `0x00000000` |
| 70 | `0x00000000` |
| 71 | `0x8876086a` |
| 73 | `0x8876086a` |
| 75 | `0x00000000` |
| 79 | `0x8876086a` |
| 80 | `0x00000000` |
| 82 | `0x8876086a` |
| 83 | `0x8876086a` |
| 84 | `0x8876086a` |
| 85 | `0x8876086a` |
| 0 | `0x8876086a` |
| 22 | `0x8876086a` |
| 23 | `0x8876086a` |
| 4294967295 | `0x8876086a` |

Both adapters give the same results for this corpus. Invalid adapters return actual
`0x8876086c`; unavailable combinations return `0x8876086a`. Tested render-target formats
21, 22, 23 and 24 accept depth 77. All tested DeviceType and AdapterFormat values are
accepted for the otherwise genuine tuple, including invalid enum values. The bridge
preserves this backend behavior. Native-only SEH safety probes make 1,484 calls per
architecture without an exception. This method checks invalid adapters safely, unlike
the earlier unchecked GetAdapterModeCount method; safe invalid queries reach the real
backend and retain its HRESULT.

Each of two native processes per architecture makes 2,968 seeded/repeated corpus calls
plus a distinct second-object query. Seeds 0, 18, `0x13572468` and `0xffffffff` remain
unchanged on success and failure. Results are stable across repetitions and processes.
No depth-query architecture differences occurred. Current initial and repeat enumeration
agreement: **True / True**.
The earlier initial x86 format-23 discrepancy remains preserved in preceding evidence;
these runs do not resolve its cause or establish universal enumeration equivalence.

The x86 native and translated ABI probes make 371 calls per process with zero ESP delta
and EBP/EBX/ESI/EDI seeds retained. The method pops this plus five UINTs (24 argument bytes).
Native x64 makes 371 ABI calls with zero RSP delta and all eight nonvolatile GPRs plus
XMM6..XMM15 retained. QueryInterface returns the same interface, AddRef/Release counts are
unchanged, a second factory object is distinct, native modules unload, and translated
shutdown releases two outstanding references. All sixteen guest vtable slots are audited
as typed guest stubs; no native COM pointer or guest pointer crosses the query boundary.

Each of two translated processes compares **42,501 values**, with **3,340 paired depth
queries**, 129 paired display queries, 736 paired enumerations and 33 paired mode-count
queries. All **18 negative guards** pass, including stale depth interfaces, earlier pointer
guards, unsafe mode-count indices, RegisterSoftwareDevice and CreateDevice. Both positive
traces contain 13,830 contiguous events with zero drops. Exact results are compared without
mapping HRESULTs, last-error, enum values or backend differences.

## Genuine client continuation

Run: `experiments/xrt/results/raw/level/20261025-045003-aa545f63-candidate`.
The one session uses manifest-bound isolated assets, pinned x64 DXVK D3D8/D3D9,
pinned DirectMusic IPC, both session locks and a 60-second watchdog. No reference
graphical client or retry ran. Entry/paired return sequences for the genuine depth query:
**75530 / 75532**. Guest ESP increases by 28 bytes,
including the return address, which exactly matches `0x0696ef15`.
All successful mode enumeration and display outputs still match their exact native oracle.

| Boundary | Calls | Paired returns |
|---|---:|---:|
| d3d8_mode_count | 154 | 154 |
| d3d8_enum | 152 | 152 |
| d3d8_display | 1 | 1 |
| d3d8_depth | 1 | 1 |
| viewport_try_render | 1 | 0 |
| viewport_open | 1 | 0 |
| engine_init | 1 | 0 |
| engine_tick | 0 | 0 |
| level_tick | 0 | 0 |

Selected-world completed ticks: **0**.
Selected actor lifecycle paired returns: `{'PreBeginPlay': 279, 'BeginPlay': 279, 'PostBeginPlay': 279}`
across 278 actors.
The first remaining blocker is retained exactly:

```json
{
  "seq": 75533,
  "thread": 0,
  "kind": "d3d8_unimplemented",
  "method": "CreateDevice",
  "this": 86160,
  "adapter": 0,
  "type": 1,
  "window": 4716,
  "flags": 66,
  "parameters": 316688028,
  "output": 316688024,
  "caller": 110555345,
  "return_address": "0x0696f0d1",
  "callsite": "D3DDrv.dll+0xf0ce"
}
```

CreateDevice captured parameters, if reached (guest x86 structure, thirteen DWORDs):

```json
[
  {
    "entry": {
      "seq": 75533,
      "thread": 0,
      "kind": "d3d8_unimplemented",
      "method": "CreateDevice",
      "this": 86160,
      "adapter": 0,
      "type": 1,
      "window": 4716,
      "flags": 66,
      "parameters": 316688028,
      "output": 316688024,
      "caller": 110555345,
      "return_address": "0x0696f0d1",
      "callsite": "D3DDrv.dll+0xf0ce"
    },
    "return_address": "0x0696f0d1",
    "callsite": "D3DDrv.dll+0xf0ce",
    "raw_guest_dwords": [
      1540,
      945,
      22,
      1,
      0,
      1,
      4716,
      1,
      1,
      77,
      1,
      0,
      0
    ],
    "fields": {
      "BackBufferWidth": 1540,
      "BackBufferHeight": 945,
      "BackBufferFormat": 22,
      "BackBufferCount": 1,
      "MultiSampleType": 0,
      "SwapEffect": 1,
      "hDeviceWindow_guest": 4716,
      "Windowed": 1,
      "EnableAutoDepthStencil": 1,
      "AutoDepthStencilFormat": 77,
      "Flags": 1,
      "FullScreen_RefreshRateInHz": 0,
      "FullScreen_PresentationInterval": 0
    }
  }
]
```

The device guard records arguments and stops before any native device creation.
No IDirect3DDevice8 methods, Clear, Present or other rendering operations were implemented.

## Build, regressions and integrity

A fresh serial build compiles all **279 objects**, with zero reused objects, into a unique
directory. Complete source, generated-code, object, PDB, executable, compiler/SDK and
dependency hashes are preserved in `out/recovery/d3d8-depth-20261025-01/`.
The pinned compiler/linker use MSVC **14.51.36231**. Client warnings: **0**.
Native and translated fixture builds succeed without compiler failures.

All seventeen affected GUI/window regression suites, the nine-case compact commandlet/VM
comparison, four UnrealScript compiler variants, traced hello and Python acceptance pass.
Python: **Ran 158 tests in 10.579s; OK (skipped=17)**. The preceding class-fixture warning and expected skips remain.
The post-client D3D8 acceptance again matches all 42,501 values and passes all 18 negative
guards, in a fresh evidence directory, without another graphical session.
Known limits remain **110 CRT mismatches / 1,796 pending**, **six ACP 932 differences**,
and x87 status/tag, large-input and double-rounding limitations.

Final integrity verifies 577 earlier working files,
14554 earlier build files, 17344
earlier raw files, previous evidence, protected manifest, DXVK pairs and DirectMusic helper.
The original installation and saves were not accessed. The runtime aggregate is
`e12c652ad0d63b21da799beded78adee46adfbb561b7344b811d55aab9cdf56a`; the unchanged generated aggregate is
`93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062`. The client trace contains
75547 contiguous events with zero drops; all 133 audited
fixture/acceptance traces are complete. All 96 successful
guest file opens resolve in the isolated sandbox. Sticky/clip state is restored, both
locks are released and no client or helper process remains.

Smallest recommended next experiment: **Fixture-only native x86/x64 CreateDevice characterization with owned native windows, adapter 0, type 1, behavior flags 0x42, and the captured 1540x945 windowed format-22 / depth-format-77 presentation. Reproduce all thirteen fields, resolving the window independently. Measure HRESULT, last-error 18, structure mutation, output ownership, ABI/FPU state, failure paths and device cleanup before considering a typed device-creation bridge. Rendering methods remain unsupported.**

[Structured report](results/compare/d3d8_depth_renderer.json).
Full artifact hashes: `out/recovery/d3d8-depth-20261025-01/phase-artifacts.json`.
No Android, editor expansion, remote push or release occurred. This phase stops after reporting.
