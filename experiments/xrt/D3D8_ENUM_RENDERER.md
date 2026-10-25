# D3D8 enumeration validated; bounded client stops at GetAdapterDisplayMode

2026-10-24, US Eastern. Starting HEAD: `1f00c5b2af57efbfd3996733aff98842a8d7007c`.
The measured typed `IDirect3D8::EnumAdapterModes` bridge is implemented and fixture validated.
Exactly one translated graphical client completed the 152-mode list, then stopped at the next
unsupported method. No device or rendering implementation was added. Local commit identity is
recorded in `out/recovery/d3d8-enum-20261024-01/commit.json`; unrelated earlier pending work remains.

New executable: `experiments/xrt/build/d3d8-enum-20261024-01/xrt_ucc.exe`.
SHA-256: `005edc05d720fbc1dbd5ff900716044701eb13a6b010c3c57526636e137657e5`.
The prior fixture-tested executable retains SHA-256
`4cfbbee3037882ff07d2e730acf9b39445a90359e58c018a333f0d5ca2518d00`.

The bridge resolves the existing guest COM object, checks actual backend adapter and mode counts,
and calls the actual pinned DXVK enumeration method, including its measured safe invalid-index
paths. Invalid adapters never reach DXVK's unchecked mode-count method. Four DWORD fields are
marshalled explicitly at offsets 0/4/8/12; failed calls leave guest output untouched. The full
16-byte guest range is checked for overflow, commitment and writable protection before the host
call uses its separate local structure. Actual HRESULT and last-error are retained. NULL output
remains an explicit unsupported stop. Guest vtables, object identity and ownership are unchanged;
no native pointer is written into guest memory. Stdcall removes this plus three arguments.

| Native fixture process | Adapter 0 count | Adapter 1 count | Formats per adapter |
|---|---:|---:|---|
| First x86 | 304 | 304 | 152 format 22 + 152 format 23 |
| First x64 | 152 | 152 | 152 format 22 |
| Repeat x86 | 152 | 152 | 152 format 22 |
| Repeat x64 | 152 | 152 | 152 format 22 |
| Two translated x64 processes | 152 | 152 | 152 format 22 |

The **complete initial x86/translated enumeration comparison differs**. It remains an unresolved
backend finding; neither counts nor modes are normalized. Complete repeat-native x86/x64 and
translated mode lists compare exactly, with no filtered-mode acceptance rule. Each translated
process matches **7,342 values**, including all 945 existing COM/query values against native x64;
the complete mode lists and x86 COM ABI also match repeat native x86 exactly. The native audit
covers **3,504 enumeration calls**. Each translated process records **736 paired enumeration
calls**, **33 paired mode-count calls**, 24 seeded enumeration ABI calls and eight seeded count
ABI calls. ESP delta is zero and EBP/EBX/ESI/EDI retain
`12345678/23456789/3456789a/456789ab`. Both adapters, complete lists twice, mode 0, last valid mode,
invalid modes/adapters, all output words, canaries, COM identity and lifetime are covered.
Three native last-error seeds (0, `0x13572468`, `0xffffffff`) remain unchanged on success and failure.
Invalid indices return actual `0x8876086c` and preserve all sixteen `0xa5` output bytes. Thirteen
negative guards pass, including stale interfaces, invalid count indices, NULL, uncommitted/wrapping
output ranges, RegisterSoftwareDevice and CreateDevice. Cleanup releases two outstanding fixture
references; the guest-pointer audit checks all sixteen typed vtable slots. Each positive translated
trace has 3,266 contiguous, untruncated events and zero drops.

The one genuine run is `experiments/xrt/results/raw/level/20261025-033603-9f7d9bd2-candidate`.
It uses independently copied manifest-bound assets, the pinned x64 DXVK D3D8/D3D9 pair, the pinned
DirectMusic IPC helper, both session locks and a 60-second runtime watchdog. No reference graphical
client or retry was executed.

| Genuine boundary | Calls | Paired returns | Actual result |
|---|---:|---:|---|
| GetAdapterModeCount | 154 | 154 | Adapter 0 returns 152 every time |
| EnumAdapterModes | 152 | 152 | Modes 0..151, HRESULT 0, last-error 18 |
| TryRenderDevice | 1 | 0 | Entered; blocked inside renderer initialization |
| OpenWindow | 1 | 0 | No return |
| UGameEngine::Init | 1 | 0 | No return |
| UGameEngine::Tick | 0 | 0 | No entry or completed tick |
| Selected-world ULevel::Tick | 0 | 0 | No entry or completed tick |
| D3D CreateDevice | 0 | 0 | Not reached |

The original count call at **D3DDrv.dll+0xe9bd**, guest interface `0x00015090`, returns to
`0x0696e9c0` with 152 (entry/return sequence 74452/74454). The other 153 count checks execute at
`+0xea03`. All 152 enumeration calls execute at **+0xea22**, return to `0x0696ea25`, and write
the measured 16-byte output at `0x0120d388`. Every genuine mode matches the exact native x64 list:
mode 0 is `(640,480,240,22)` and mode 151 is `(2560,1440,48,22)`. The full per-call results and
paired stack/return evidence are indexed in the structured report.

The first remaining blocker is **IDirect3D8::GetAdapterDisplayMode(adapter=0, output=0x0120d3c8)**,
called at **D3DDrv.dll+0xec82**, return `0x0696ec85`, interface `0x00015090`. It stops explicitly
with exit 76 before its backend method is called. The highest world milestone remains T2:
279 paired returns for each lifecycle stage across 278 selected-world actors; T3..T6 remain false.
CreateDevice, IDirect3DDevice8 methods, Clear, Present and rendering commands remain unsupported.

The fresh serial build recompiles hle_misc and links 278 hash-verified unchanged objects; all 279
objects, previous PDBs and executables are retained. The client and final fixture builds have no
warnings or internal compiler errors. Complete source/generated/object/output hashes, compiler/SDK
headers and libraries, backend/helper dependencies, exact commands and environment are in
`out/recovery/d3d8-enum-20261024-01/{preflight,build}.json` and `phase-artifacts.json`.

| Output/input | SHA-256 |
|---|---|
| Linked PDB | `02ae42ea071d4548e85480cb17d4f0087f0497389e9eff4783de4c23a12372ab` |
| hle_misc.obj | `5df0706d04d9f3f2c45d598820d7df11ff72a24088c7c91b76460f8e4c821ff7` |
| Compiler PDB | `868725200f8a1e122c134902a1b7d6f039a5a0d07e6f54db6a9729530f438d15` |
| hle_d3d8.inc | `1c409326f12356d154bab732b661694974e3eb38d7d77d8185819625a5173dc2` |
| Runtime aggregate (27 files) | `63cb9d8f46c2e75caeaa5c1f41e7b1f92e35130a4a1d658636ca72898f78ee3c` |
| Generated aggregate (299 files) | `93046d39786d3f4be894370e86a5fed0a26fbc3001e18ae36c12d15686336062` |

All **17 affected GUI/window suites**, the **nine-case compact commandlet/VM** comparison,
all four UnrealScript compiler variants, traced hello and Python checks pass:
**Ran 158 tests in 11.085s; OK (skipped=17)**. The existing class-fixture C4133 warning and expected skips remain.
Existing limitations are retained: **110 CRT mismatches / 1,796 pending**, **six ACP 932
differences**, and x87 status/tag, large-input and double-rounding limits. No unrelated exhaustive
sweep was repeated.

Final integrity verifies 13,277 earlier build files, 17,326
earlier raw files, all 564 previous working files and previous phase evidence.
Protected manifest `3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`
(4,122 files, three trees, nine protected files), both DXVK pairs, the DirectMusic helper,
compiler/SDK inputs, generated files and old/new executable identities remain intact. The genuine
trace has **75,534 contiguous, untruncated events and zero drops**; all 109 audited
fixture/acceptance traces also have zero drops. All 96 successful guest file opens resolve
inside the isolated assets. Sticky/clip state is restored, COM/DirectMusic/D3D/DirectInput cleanup
is retained, no client/helper remains and both session locks are released. Original installation
and saves were not accessed. No Android work, remote push or release occurred.

Fixture development is preserved: v01 stopped before compilation because kernel32.lib was
accidentally added to the import-library command; v02 hit the explicit no-SSE guest guard at a
compiler-generated movaps. The corrected command and established x86 `/arch:IA32` policy produce
the passing fresh v03 fixture. Exact v02 source hashes and all earlier outputs are retained.
Neither case was an unexplained compiler failure, native crash or protected-input change.

Smallest next experiment: separately authorize a **fixture-only GetAdapterDisplayMode** oracle
for the actual adapter 0, non-NULL 16-byte output and last-error seed 18. Compare native x86/x64
and translated fields, HRESULT, canaries, failures and COM ABI while keeping CreateDevice guarded.
This bounded phase is complete; no further genuine continuation is authorized here.

[Structured report](results/compare/d3d8_enum_renderer.json). Full evidence and hashes:
`out/recovery/d3d8-enum-20261024-01/`.
