# D3D8 adapter mode count: measured, guarded and built

2026-10-24, US Eastern. Starting HEAD remains `1f00c5b2af57efbfd3996733aff98842a8d7007c`.
Only `IDirect3D8::GetAdapterModeCount` gained production support. Valid indices forward to the actual
pinned x64 DXVK backend. The owner's subsequent Option 1 instruction authorizes an explicit stop for
invalid indices, checked against the backend's actual `GetAdapterCount`, before its unchecked mode-count
method is called. No count is fabricated or normalized. No genuine graphical client was executed.

The last genuine checkpoint is still `build/setactive-20261024-01/xrt_ucc.exe`, SHA-256
`8a4cd0e5a65b6ae8dd74cc2e26927993d1158e119237ce0900b2b30c57bae248`, stopped at
D3DDrv.dll+0xe9bd, guest interface `0x00015090`, slot `0x18`, expected return `0x0696e9c0`.
This phase has no genuine return from that callsite, no device creation, tick or rendered frame.

## Exact native comparison

All factories used SDK **120**. Each native process reported **two adapters**. Explicitly loaded official
DXVK 3.1.1 x86/x64 D3D8/D3D9 pairs were hash- and PE-architecture verified. Configuration files were empty;
no system D3D8, d3d8to9 or dgVoodoo result was substituted. DXVK logs identify AMD Radeon RX 7900 XT,
AMD proprietary driver 2.0.416. Identifiers retain `aticfx32.dll` versus `aticfx64.dll`; remaining identifier
payload bytes and all 53 capability words match across architectures.

| Final fixture process | Adapter 0 count | Adapter 1 count | Native enumeration per adapter |
|---|---:|---:|---|
| x86 first process | 304 | 304 | 152 format 22 + 152 format 23 |
| x64 first process | 152 | 152 | 152 format 22 |
| x86 repeat process | 152 | 152 | 152 format 22 |
| x64 repeat process | 152 | 152 | 152 format 22 |
| Translated x64, two processes | 152 | 152 | Production enumeration unsupported |

This first-process x86 variation also occurred in the preceding fixture revision. Its cause was not
established. The complete 152-mode format-22 sequence is identical in all four native runs; the first
x86 process additionally enumerates 152 format-23 modes. Counts are stable across eight repeated query
rounds inside each process, through QueryInterface identity, and across separate factory objects.
Do not turn either observed count into a constant or claim unconditional architecture equivalence.
The final native x86 repeat and both x64 runs match exactly for mode-count and enumeration logs.

## Invalid indices and the owner-approved boundary

Before discovering the unchecked access, the first native x86 fixture recorded these UINT values
in eight repeated rounds. They are evidence of undefined reads, **not compatibility expectations**:

| Invalid adapter | Observed UINT |
|---|---|
| 2 (actual adapter count) | `0xdeb2a4ef` |
| 3 | `0x80002f72` |
| `0xffff` | `0x00000000` |
| `0x7fffffff` | `0x88002e00` |
| `0xffffffff` | `0x88002e00` |

The pinned [DXVK source](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_interface.h#L47-L49)
directly indexes `m_adapterModeCounts[Adapter]` without a bounds check. Further native invalid-index
mode-count calls, including x64, were deliberately excluded. Production calls actual `GetAdapterCount`
and exits 76 with an invalid-adapter diagnostic when `adapter >= count`. All five indices pass this
negative test; their traces record `native_mode_count_called:false` and no successful mode-count result.
GetAdapterModeCount returns UINT in EAX, not an HRESULT.

## Native EnumAdapterModes characterization only

The final fixture audited **3,120 native enumeration calls**, plus **eight native x86 enumeration ABI
calls**. Each complete valid mode list was enumerated twice. Every supported index returned HRESULT 0;
mode `count`, mode `0xffffffff`, and adapters 2, `0xffff`, `0xffffffff` returned `0x8876086c`
(D3DERR_INVALIDCALL). Invalid calls left all 16 output bytes at `0xa5` and preserved both adjacent canaries.
NULL output pointers were not measured. The native implementation's bounds checks are visible in
[DXVK 3.1.1](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/d3d8_interface.cpp#L84-L96).

| D3DDISPLAYMODE field | Byte offset | Size |
|---|---:|---:|
| Width | 0 | 4 |
| Height | 4 | 4 |
| RefreshRate | 8 | 4 |
| Format | 12 | 4 |

Both architectures have a 16-byte pointer-free structure. Mode 0 is `(640,480,240,22)` in all final runs.
Format values measured were 22 (X8R8G8B8) and, in the first x86 process, 23 (R5G6B5). All individual modes,
HRESULTs, canaries and repeated lists are retained in the structured measurement and raw fixture logs.
Production EnumAdapterModes remains an explicit unsupported-method stop.

## Differential and ownership regression

The exact project-owned PE32 DLL runs natively on x86 and, lifted without patching, through the actual
x64 runtime. Its source is also compiled natively for x64. Two translated processes each compare
**1,046 values exactly**, including the existing **945** factory/adapter/capability/format/ownership values.
Mode-count logs match the final native x86 and x64 results exactly; count ABI logs match native x86 exactly.
Each translated process makes 27 valid mode-count calls, including eight seeded ABI calls. EAX contains
the native UINT, stdcall removes this+adapter, the seeded frame's ESP delta is zero, and EBP/EBX/ESI/EDI
remain `12345678/23456789/3456789a/456789ab`. Native enumeration separately preserves the same frame and
registers for four-argument COM calls. No successful translated enumeration ABI is claimed.

QueryInterface preserves IUnknown/IDirect3D8 identity; separate factories stay distinct; AddRef/Release
counts match native; normal final Release returns 0. Runtime shutdown releases two deliberately outstanding
references. Native cleanup also releases its outstanding references to zero and explicitly unloads both
D3D modules. Ten translated negative cases pass: stale interface, stale mode-count interface,
RegisterSoftwareDevice, EnumAdapterModes, CreateDevice, and five invalid adapter indices.

The fixture audits the guest object's four-byte vtable pointer and all sixteen four-byte entries against
the exact typed guest stubs. Observed guest vtable is `0x00013000`; audited objects include `0x00013058`
and `0x00013064`. No host COM pointer or x64 vtable is written into those guest objects. Each positive trace
has 233 events and zero dropped events. No production COM ownership mechanism changed.

## Fresh build and identities

New client executable: `experiments/xrt/build/d3d8-modes-20261024-01/xrt_ucc.exe`.
It was **built but never executed**. A fresh serial directory recompiles only hle_misc (which includes
hle_d3d8.inc) and links 278 exact hash-verified unchanged objects. All 279 objects, prior binaries and PDBs
remain preserved. Compiler and link complete without warnings or internal errors.

| Input/output | SHA-256 |
|---|---|
| New executable | `4cfbbee3037882ff07d2e730acf9b39445a90359e58c018a333f0d5ca2518d00` |
| Linked xrt_ucc.pdb | `7e7a9a7b323a185ee22ce3bab551ac30696f02a25558a4083c458271622a6aa0` |
| Recompiled hle_misc.obj | `042903e93b99e98bf4f6b2ddc816068ac4a560ae2f4d6e0874e026555693879e` |
| Compiler vc140.pdb | `84469ba217a86c6f86e1e8f959ba1ee44652a7352853dec0426c1bd9f34798d5` |
| hle_d3d8.inc | `a3d9401ffe6a0b750d5772e2b4000df35655864307f2f6f1d228f01dce0a65f5` |
| Runtime aggregate, 27 files | `89c23462f70bd850e7f16dd464b742466666bf9b31c360e8daf1da4076005083` |
| Generated aggregate, 299 files, unchanged | `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062` |
| Final PE32 fixture DLL | `a45ebc4ef3c425dce014fa795274b1a5ded09bf5924b3da62f4f54f6047bba52` |
| Final native x64 fixture DLL | `9c8ea874efbea2d8d69db759e4c0a3b294d898accc8e1ee01081e98acff477aa` |
| Final translated fixture executable | `fe99c005770deea4d2b70ff3265680675449e83e108ce5e2ea6c604a188e6333` |

Pinned DXVK files, x86 D3D8/D3D9 respectively:
`9152ba43386e756790a66f61cdcee01b3287d156d4161c7456d816faa82fc364`,
`265888c31ca78dffa290c39cb7e50bfb02762590e41927906e46fb32f01497fa`.
Pinned x64 D3D8/D3D9 respectively:
`bd65cebf8ece6f80a841a16d98bdf5b76894c172b7ba344180baa17a4d00680c`,
`c126316f7478eaff1ad8087702eda5930f2400187b9c8b3592219c34f6632780`.
DirectMusic helper remains
`a141ffe197f3eb14ed5908c946bd3cb541fdf456175b5a602b52df1b64484d22`.

Preservation and before/after gates cover all earlier pending work, previous build/raw evidence, Git
history, runtime/generated sources, compiler/SDK headers/libraries, DXVK pairs, helper and protected assets.
Protected manifest remains `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`
(4,122 files, three protected trees, nine protected files). Original installation and saves were not accessed.
The final integrity result is in `out/recovery/d3d8-modes-20261024-01/final-integrity.json`.

Fixture development is retained: revision 01 returned its explicit log-capacity code before enumeration;
the enlarged log accommodates complete lists. A comparison-driver report filename collision caused a
Python KeyError after the positive differential had passed; distinct report/log filenames fixed it and
a fresh comparison passed. Neither event was a compiler failure, native crash or integrity discrepancy.
Earlier partial results are preserved. No remote push, release, Android work or renderer expansion.

## Remaining boundary and smallest next experiment

Production RegisterSoftwareDevice, EnumAdapterModes, GetAdapterDisplayMode, CheckDeviceType,
CheckDeviceMultiSampleType, CheckDepthStencilMatch, GetAdapterMonitor and CreateDevice remain unsupported.
All IDirect3DDevice8 methods remain unsupported; no device instance exists. This phase does not change
the accepted genuine-client milestone or prove the next executed guest callsite.

The smallest next experiment is a separately authorized fixture-only typed EnumAdapterModes bridge for
adapter 0, mode 0, last valid mode and invalid mode, comparing all sixteen bytes, HRESULT, canaries and
stdcall ABI against this oracle. Keep CreateDevice guarded. A genuine continuation and device creation
would require later authorization.

Evidence: `out/recovery/d3d8-modes-20261024-01/{preflight,measurement,build,final-integrity}.json`,
`experiments/xrt/build/d3d8-modes-fixture-20261024-03/`, and
`experiments/xrt/results/compare/d3d8_adapter_modes.json`. Complete serial commands and binary/source/object
identities accompany those files. The fixture driver accepts `build_native`, `characterize`,
`build_translated`, `compare` and a fresh `--out` directory; characterization preserves cross-process
differences, and the differential requires exact valid-adapter results.
