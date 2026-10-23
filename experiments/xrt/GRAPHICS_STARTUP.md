# Entry LoadMap completed; CS_Intro PostLoad completed; DirectMusic boundary — 2026-10-23 (US Eastern)

**The genuine translated Entry LoadMap now returns a non-null world.** The second LoadMap opens
`CS_Intro.un2` and completes that package's `ULevel::PostLoad`. It has **not** returned from CS_Intro
LoadMap, completed selected-world actor initialization or executed a selected-world tick.
The first remaining fatal is `ole32!CoInitialize`, called at `Engine.dll+0x18177f` from the
`DMCallRoutine → AMusicScriptEvent::execCallRoutine` path, even with `-nosound`.

Starting HEAD was clean at `ebf67d56209254e909eef1ad1b0a5f6608641215`; its parent is `0c57992`.
Both reported commits were verified and no later changes were reset. Implementation/oracles are
committed locally as `0fcd8b0`. No push was made. Public evidence:
[entry_initialization.json](results/compare/entry_initialization.json).

| Independently tracked milestone | Genuine translated evidence |
|---|---|
| Entry.un2 LoadMap entry | Yes, seq 23206 |
| Entry package PostLoad completion | Yes, paired call/return 23270/23295 |
| Entry LoadMap successful return | Yes, seq 23395, world `0x120a5000`, matching caller and ESP +20 |
| CS_Intro.un2 opening | Yes, successful file open seq 23404 within second LoadMap (23400) |
| CS_Intro package PostLoad completion | Yes, paired call/return 23926/23933, object `0x12f52800` |
| CS_Intro LoadMap successful return with non-null world | **No** |
| Selected-world actor lifecycle initialization completed | **Not established**; Entry's actor method hits cannot prove it |
| One completed selected-world simulation tick | **No**; neither UGameEngine Tick nor ULevel Tick entered |
| Actual translated D3D device / Present | **None / none** |

Engine Init has not returned. File reads, object allocation and PostLoad completion are not used as
substitutes for the missing selected-world initialization evidence. No render output is claimed.

## CRT boundary: measured bit behavior, state and regression

The preserved starting binary reproduces the original fatal at `Core.dll+17220`:
`results/raw/level/20261023-055123-c6e1372d-candidate/`.
Original instruction observers capture the actual msvcr70 floor entry, SSE2/x87 branch and appRound
return. Both dgVoodoo (`5bffb0661486-dgvoodoo`) and DXVK x86 (`4dba095f123d-dxvk`) select **SSE2**.
The first operands are `3faa000000000000` and `3fefe00000000000`, both returning positive zero;
FCW is `027f`, FSW `0120 → 3920`, MXCSR `00001fa4` unchanged. The game `-NOSSE` flag does not disable
the native CRT's SSE2 implementation. Raw x87 tags and all eight 80-bit register slots are retained.

The focused [floor/ceil oracle](tests/floor_boundary/README.md) calls the real x86 sandbox msvcr70
export through a function pointer, and the actual translated adapters through guest cdecl frames.
For **each function, 73,920 cases have zero differences** in full result bits, FCW, FSW including TOP,
condition and sticky flags, errno and surviving deeper stack values. Guest return/ESP and callee-saved
register checks also pass. Inputs include actual game operands, negative fractions, integral neighbours,
signed zeros, subnormals, large values, infinities, quiet/signalling NaNs and payloads, plus seeded random
binary64 values. No difference is masked or waived. Unmodeled control words remain explicit fatal negatives.

The implementation uses integer manipulation of IEEE binary64 bits, with **no host floor/ceil/libm call**.
It preserves negative zero, quiets SNaN while setting x87 IE, preserves NaN sign/payload, sets EDOM for
NaNs, clears C1 and preserves the other measured x87 flags. The subsequently encountered `ceil` import
at Core `171fa` has its own native comparison. Original appCeil uses operand `409fa40000000000`, which
returns unchanged, FCW `027f`, FSW `4025 → 7825`, MXCSR `00001fa5` unchanged (`6b7ef11021f4-dxvk`).

A genuine resumed run exposed FLDCW `023f`: the model retained its clear reserved bit 6, while native
hardware reads back `027f`. The expanded differential reproduced the failure before fixing
`xrt_fldcw` to set that readback bit. Both control inputs now compare exactly. Other precision/rounding
controls, unmasked exceptions, a full x87 stack and the CRT SSE2-disabled fallback are outside this oracle.

**Existing arithmetic-status differences remain visible.** Translated incoming floor FSW is `0100`,
return `3900`, versus native `0120/3920`; ceil is `4000/7800` versus `4025/7825`. Earlier general guest
x87 arithmetic does not model all exception sticky flags. The new adapters preserve their incoming
state correctly and are tested with those exact native and translated states; this does not establish
end-to-end FPU-status equivalence. Native MXCSR is observed, while guest SIMD status remains unmodeled.

## Actual encountered steps and remaining host dependency

After rounding, real Entry initialization required `GetLocalTime`; its adapter writes the eight guest
SYSTEMTIME WORDs from the actual host call. Tests check the native time interval, weekday, both canaries,
last-error preservation and stdcall cleanup. The loader now records paired PostLoad/LoadMap returns.

CS_Intro then requested, one at a time, `ParticleSystems.dll`, `Legend.dll`, `UI.dll`, `U2.dll` and
`U2Dialog.dll`. Each is lifted from the unchanged sandbox binary, hash-bound, and executes its real
DllMain successfully. The module limit is now 32 (including unloaded slots), with consistent bounds for
import counts, load lists and initialization order. The client identity check rejects overlapping client
lift ranges before compilation. One exploratory run combined relocation bases from different original
runs and failed visibly on UI/U2Dialog overlap; its binary/logs and previous UI lift remain preserved.
The corrected layout uses UI `19120000` and U2Dialog `19630000` from the same reference run.

After CS_Intro PostLoad, the missing dynamic `SubTFonts.utx` followed an error path into unsupported
`FormatMessageW`. That error boundary remains visible in `20261023-061639-93a28750-candidate`.
The driver now stages the genuine installed font package into the sandbox with hashes, matching the
established original reference. It refuses to overwrite a different existing sandbox package. This
resumes normal loading and exposes the current DirectMusic boundary; no dummy package was supplied.

No new guest COM method was added. The existing typed guest COM and **DXVK 3.1.1 x64 D3D8/D3D9**
backend remain intact; CreateDevice is still explicitly unsupported and uncalled. The 18 measured
dgVoodoo/DXVK caps differences are preserved in the preceding D3D8 comparison.

The [native DirectMusic dependency probe](tests/directmusic_boundary/README.md) extracts the exact
CLSID/IID pairs from Engine.dll's data. CoInitialize returns S_OK then S_FALSE on both architectures.
Loader8 creation succeeds on both. **Performance8 succeeds on x86 but returns `80040154`
(REGDB_E_CLASSNOTREG), NULL output, on x64.** All successful native references are released and both
apartment initializations balanced; no audio device, InitAudio or playback is invoked. This is a measured
architecture difference, **not a compatibility pass**. Original instruction observations at `15300b5237d8-dxvk`
confirm S_OK for its actual CoInitialize and both game factory calls.

The smallest next experiment is to measure the original Performance8 initialization/script methods and
identify a usable x64 implementation or a bounded x86 COM bridge, then implement measured apartment
ownership and typed guest interfaces. Simply returning S_OK, omitting the music script, or presenting
the x64 factory failure as equivalent to the original's success would not resolve this boundary.

## Final runnable case and acceptance

Final binary: `build/entry-floor-final/xrt_ucc.exe`, SHA-256
`910e1d1c0900dbe2a6cf306526c453c5190ef8a3475527f8f2ed2aea1b6f640c`.
Every runtime/client translation unit was compiled freshly without warnings; unchanged baseline generated
objects were verified against `fresh-20261023-015722-b7ee8987`. `client-identity.json` binds sources,
lifts, objects and binary. Both final runs have **24,135 events, zero dropped events**, the same milestone
sequence above and the same fatal (24132), followed by real D3D8/DirectInput releases and StickyKeys restoration:

- `results/raw/level/20261023-062210-ecf6c9db-candidate/`
- `results/raw/level/20261023-062406-fa48fecc-candidate/`

```powershell
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\entry-floor-final\xrt_ucc.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --d3d8-backend dxvk --package Textures/SubTFonts.utx --timeout-ms 45000
cmd /d /c experiments\xrt\tests\floor_boundary\build.cmd
.venv/Scripts/python -I experiments/xrt/tests/floor_boundary/compare.py
.venv/Scripts/python -I experiments/xrt/tests/floor_boundary/compare.py --function ceil
```

Fresh full original references `542dc90f477d-dgvoodoo` and `e3188707f1d2-dxvk` both complete CS_Intro
initialization: 268 of each actor lifecycle event, four returned selected-world ticks, one successful
game device creation and three successful normal Presents. Both observer traces are complete without
drops. The established SubTFonts/U2Player_A/HUD_Fonts/UI_Fonts reference staging is unchanged.

Final validation: nine commandlet/VM cases PASS (`20261023-062221-add36d09`); compiler PASS
(`20261023-062221-5d4877f2`, 16 compiles including four expected invalid-source failures, 12 execution
comparisons); traced VMProbe PASS (`20261023-062406-a7feacea`); Python **149 tests OK, 17 expected skips**.
DirectInput/COM, D3D8/COM, GUI, class, module, binary FILE, startup/memory and EH (six positives/two explicit
negatives) suites pass. Gate-F CRT: **51,536 cases, zero mismatches**. Current sine table: all 16,384 floats
match; the existing two double-only edge differences remain visible. Earlier lock-colliding Python and
relocation-overlap experiments are excluded; serial final checks pass. Existing fixture compiler warnings
remain in component logs; the final client build has none.

Immutable oracle binaries, comparison logs and hash manifest: `results/raw/floor-checkpoint-20261023/`.
Full expanded CRT baseline remains **110 mismatches / 1,796 pending**, not exhaustively rerun; fresh
`fopen.0` still differs. Fresh ACP 932 retains six differences. No expectation was weakened.
Read-only final census matches all **4,757** preceding installation files with zero additional differences;
Save metadata matches. The [unresolved Ogg CRC/PCM discrepancy](INSTALLATION_INTEGRITY.md) is preserved
without repair or a clean-install claim. No original-install or save writes were made.

---

# Historical D3D8 creation and queries / translated LoadMap entry — 2026-10-23 (US Eastern)

**The translated D3D8 creation/query boundary works through DXVK 3.1.1 x64.**
The real client obtains a guest COM object, enumerates two adapters, obtains both identifiers and HAL
caps, and passes its DXT1/3/5 format queries. It then enters genuine `UGameEngine::LoadMap`
(`Engine.dll+0x90f00`) from `UGameEngine::Init`, opens `Entry.un2`, and reaches
`ULevel::PostLoad → UModel::BuildRenderData`. The first remaining failure is the unimplemented
`msvcr70.dll!floor` import at `Core.dll+0x17220`, returning to `+0x17226` inside `appRound`.

**No translated CreateDevice call or device exists at this checkpoint.** Engine Init and LoadMap have
not returned; CS_Intro, selected-world initialization, ticks, Presents and pixels remain unreached.
The experiment stops at this newly observed CRT boundary. No large renderer, capability override,
initialization bypass or Android implementation was added.

Starting HEAD was clean at `4c2b7452b0320bd28b3115ca984f2e8f09267202`; `8076749` was its parent.
Source/oracles are committed locally as `0c57992`. No push was made. Prior checkpoints remain intact.
Structured evidence, full caps and all differences: [d3d8_initialization.json](results/compare/d3d8_initialization.json).

## Backend selection from actual artifacts and executions

Selected: official [DXVK 3.1.1](https://github.com/doitsujin/dxvk/releases/tag/v3.1.1), Windows PE32+
`x64/d3d8.dll` plus the **matching DXVK** `x64/d3d9.dll`, over the system Vulkan loader and AMD GPU.
Both binaries are PE machine `0x8664`; D3D8 exports `Direct3DCreate8` and imports D3D9. Native loader
paths and DXVK logs verify the pair, Vulkan loader and actual adapter, rather than inferring a backend
from filenames. The runtime also records both actual loaded module paths. The driver verifies both
binary hashes/architectures before execution and supplies an empty local config with shader caching
disabled. It makes no changes to global DLL search, drivers, registry, graphics settings or the install.

| Actual implementation | Factory / initial query behavior | Selection consequence |
|---|---|---|
| Windows SysWOW64 D3D8, x86 | Factory and identifiers succeed; HAL caps `8876086a` | Reproduces the known host D3D8 failure |
| Windows System32 D3D8, x64 | File absent on this host; explicit load fails with error 126 | No native host implementation available there |
| crosire d3d8to9 1.16.0, official x86 binary | Factory/identifiers succeed; HAL caps `8876086a`; actual system D3D9 loaded | This measured path is unsuitable here; no claim that source cannot be built for x64 |
| dgVoodoo2 2.87.5, x86 D3D8/D3D11 | Initial queries and original game device/Presents succeed | Preserved reference; its official archive has **only D3D9** under MS/x64 |
| DXVK 3.1.1, x86 and x64 D3D8/D3D9 | Factory, identifiers and HAL caps succeed in both; matching DXVK D3D9 and Vulkan loaded | Selected for the translated host boundary |

The dgVoodoo archive's x64 D3D9 binary is itself audited: machine `0x8664`, `Direct3DCreate9` and
`Direct3DCreate9Ex` exports, **no Direct3DCreate8**. Neither it nor an x86 D3D8 binary is silently
substituted for an x64 D3D8 interface. See raw `dgvoodoo-x64-interface-audit.json`.

Pinned SHA-256:

- Official DXVK archive: `40565b4a724aadc4433fa4e010b4b23916d9b1f1baeee64e17186db94f54e608`
  (matches the official release-asset digest).
- x64 D3D8: `bd65cebf8ece6f80a841a16d98bdf5b76894c172b7ba344180baa17a4d00680c`.
- x64 D3D9: `c126316f7478eaff1ad8087702eda5930f2400187b9c8b3592219c34f6632780`.
- x86 D3D8: `9152ba43386e756790a66f61cdcee01b3287d156d4161c7456d816faa82fc364`.
- x86 D3D9: `265888c31ca78dffa290c39cb7e50bfb02762590e41927906e46fb32f01497fa`.

## Measured calls, ABI and legitimate differences

The focused project-owned oracle is compiled as x86 and x64; the identical PE32 fixture is also lifted
and executed by the real x64 runtime. Native instruction observers confirm the actual game arguments:

1. D3DDrv `d8a1`: `Direct3DCreate8(120)`; do not substitute the modern header's SDK macro (220).
2. `d8d6`: `GetAdapterCount()` returns 2.
3. `d96b`: `GetAdapterIdentifier(adapter=0, then 1, flags=2, output)` returns S_OK.
4. `dab4`: `GetDeviceCaps(adapter=0, deviceType=1/HAL, output)` returns S_OK.
5. `dd94/ddc0/ddec`: `CheckDeviceFormat(0, HAL, X8R8G8B8=22, usage=0, TEXTURE=3,
   DXT1/DXT3/DXT5)` returns S_OK for each.

All **53 caps DWORDs are identical between native DXVK x86 and x64**. The only meaningful identifier
differences are `aticfx32.dll` versus `aticfx64.dll` in Driver; both full raw outputs remain preserved.
There are **18 caps-word differences between dgVoodoo and DXVK**, including CursorCaps, DevCaps,
PrimitiveMiscCaps, texture volume/repeat/aspect limits, guard bands, FVFCaps, TextureOpCaps, vertex
blend/point/index/primitive limits and MaxStreamStride. Both report hardware rasterization and the
same shader versions; they are different implementations with different limits. The public JSON
lists every differing word and both values. No caps bits or limits are copied from dgVoodoo into DXVK.

`hle_com.inc` shares guest memory validation, vtable allocation and IUnknown identity with DirectInput.
Each D3D8 object has a 4-byte guest vtable pointer; all sixteen slots contain guest adapters or named
fatal traps. Typed `D8Interface*` host objects and owned reference counts live only in their separate
table. QueryInterface supports the measured IDirect3D8/IUnknown identity and real failed IIDs; AddRef,
Release, independent objects, stale tombstones and shutdown ownership are exercised. Six positive
probes have **945 identical logged values** against native x64, including two outstanding references
released at shutdown. Two deliberate stale/unimplemented-method probes retain fatal diagnostics.

The identifier's 1,068 guest bytes correspond to the meaningful fields of a 1,072-byte x64 host
structure. Its extra tail padding is never copied to the guest. Caps are 212 pointer-free bytes in
both ABIs. Canary tests preserve adjacent guest words; invalid-adapter tests compare actual HRESULTs
and every output byte. Output storage is initialized from the caller before host queries, preserving
backend error behavior. Every remaining interface method, including CreateDevice, is explicitly
unsupported until observed and measured. No host HWND, COM pointer or vtable enters guest memory.

## Execution and regression evidence

Final build: `build/d3d8-final-checked/xrt_ucc.exe`; its binary/source/object identities are in the
public JSON and `client-identity.json`. Binary SHA-256:
`751c6b8701bbde5dd8ef4693e518f7de9e459cb10da27ef5c481f935af1c9e90`.
All runtime/client sources were freshly compiled without
warnings, and reused generated objects were checked against the unchanged accepted full checkpoint.
Two final runs (`20261023-054132-3e55d09f-candidate`, `20261023-054153-7a282de1-candidate`) each have
**23,274 events and zero dropped events**, matching queries and the same first fatal.

The LoadMap call is seq 23207, with engine caller `+0x8f664`; Entry opens at seq 23270 and the fatal is
23271. There is no LoadMap-return event. Cleanup releases one D3D8 reference and the existing DirectInput
reference and restores StickyKeys successfully. Opening Entry does not establish CS_Intro initialization.

Fresh original comparisons use the same isolated content and exact dgVoodoo config:
`4966768d31be-dgvoodoo` and `10ed5e4816cd-dxvk`. Both complete selected CS_Intro initialization with
268 of each actor lifecycle event, **four returned selected-world ticks**, game CreateDevice S_OK and
three normal Presents S_OK. Traces are complete with no dropped records. This measures original-client
compatibility despite caps differences; it makes no translated device or visual-content claim.

Final oracle copies, raw logs and hash manifest: `results/raw/d3d8-checkpoint-20261023/`.
The native matrix is `results/raw/d3d8-native/20c46e4fc67b/`. DirectInput, GUI, class, module, binary FILE,
exception and startup/memory regressions pass. Python: **149 tests, 17 expected skips**. Commandlet/VM
and compiler acceptance identities are recorded in the public JSON, including checks on the final binary.
The final nine-case invocation is `20261023-054132-b297c1b1`; final compiler invocation is
`20261023-054133-02d92c01` (16 compiles including four expected invalid-source failures, 12 execution
cross-checks). Component regressions tested the shared COM change; the final D3D8 padding adjustment
was followed by the D3D8 oracle/canaries and these final-binary acceptance runs.
The expanded CRT baseline remains 110 mismatches / 1,796 pending (not rerun exhaustively); focused
fopen.0 still differs, and fresh ACP 932 comparison retains six differences. Expectations are unchanged.
Read-only census finds all 4,757 installation files unchanged, no added/removed files, and matching
Save metadata. The prior Ogg discrepancy remains unresolved.

Two early native-matrix attempts failed during fixture development and are excluded from acceptance;
their raw output is retained. A concurrent client attempt was rejected by the existing session lock
before sandbox mutation; only completed, serialized client runs are used above.

```powershell
cmd /d /c experiments\xrt\tests\d3d8_boundary\build.cmd
.venv/Scripts/python -I experiments/xrt/tests/d3d8_boundary/native_matrix.py
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\d3d8-final-checked\xrt_ucc.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --d3d8-backend dxvk --timeout-ms 45000
```

The next bounded experiment is a focused x86 msvcr70 versus translated `floor` oracle for the observed
appRound operand and x87/CRT state, then resume unchanged engine initialization. Device creation and
later graphics methods must still advance one observed call at a time. The typed COM boundary leaves
backend replacement possible, but Windows DXVK DLLs are not an Android backend; no Android work began.

---

# DirectInput / Windows-client initialization checkpoint — 2026-10-23 (US Eastern)

**Translated D3 is reached: `UWindowsClient::Init` returns to its real engine caller.**
The first remaining fatal boundary is `d3d8.dll!Direct3DCreate8` at
`D3DDrv.dll+0x1c6b0`, called from `+0xd8a1` inside `UD3DRenderDevice::Init`.
`UGameEngine::Init` has not completed; genuine LoadMap and selected-world ticks remain unreached.
No rendering implementation, initialization bypass, Android, animation replacement or editor expansion was added.

Starting HEAD was clean at `051e73536b462126bb9e50436d0b6bec5ef1457c`, on
`codex/level-initialization`. Runtime and fixture changes are committed locally as `8076749`.
No push was made. Earlier binaries, evidence and the original installation/saves remain preserved.
Public comparison: [directinput_initialization.json](results/compare/directinput_initialization.json).

| Milestone | Translated result |
|---|---|
| D1: DirectInput8Create completes with measured native behavior | **Yes**, real host `S_OK`, guest object returned |
| D2: required initial DirectInput setup finishes | **Yes**, within UWindowsClient Init; later viewport/device setup is unexecuted |
| D3: UWindowsClient::Init returns | **Yes**, paired call/return with matching object, thread and engine caller |
| D4: UGameEngine::Init completes | No; nested renderer initialization reaches the native D3D8 dependency |
| D5: genuine UGameEngine::LoadMap entered | No |
| D6: CS_Intro.un2 opened through LoadMap | No |

## Measured COM and HINSTANCE boundary

The same project-owned PE32 DLL is run natively and through the actual lifter/runtime.
Four positive probes have **50 identical logged values**: 29 creation/COM, 7 independent-object lifetime,
2 outstanding-reference cleanup, and 12 A/W StickyKeys values. Four deliberate translated negatives retain
explicit diagnostics: stale interface, an unimplemented method, successful but unmodelled ANSI QueryInterface,
and aggregation. The final executable/report/fixture identities are pinned in
`results/raw/input-checkpoint-20261023/oracles/`; rebuilding the fixture cannot replace that evidence.

- Actual implemented operations are `DirectInput8Create`, `IDirectInput8W::QueryInterface`, `AddRef` and
  `Release`. QueryInterface supports the measured W/IUnknown identity and returns actual host failures for
  missing IIDs. Each successful host reference is owned and released. Guest objects contain a 32-bit guest
  vtable address; all eleven slots contain guest adapter/trap addresses. Typed host `IDirectInput8W*` values
  stay in a separate ownership table. Non-recycled guest tombstones diagnose stale calls. Shutdown releases
  outstanding references; the leak fixture confirms two releases and the client confirms one.
- Native creation measures version `0x0800`, IID `bf798031-483a-4da2-aa99-5d64ed369700`, NULL outer and
  the owning module's HINSTANCE. Other versions, NULL HINSTANCE and missing IID failures/output clearing also
  match. A fresh original-client trace at WinDrv `184b/1850` confirms Window HINSTANCE `0x11000000`, version
  `0800`, NULL outer, `S_OK`, and 20 bytes of argument cleanup. The IID bytes are verified against the loaded PE.
- Host HINSTANCE conversion is explicit: validate the guest module base/generation, retain that provenance,
  then pass the real EXE HINSTANCE containing the translated code. The x64 probe measures that a resource-only
  PE32 module handle fails DirectInput with `E_INVALIDARG`; normal x64 loading of PE32 fails with error 193.
  No PE32 code is executed by the host. This establishes the observed factory/COM behavior, **not** equivalence
  of original-module certification or path-specific compatibility behavior. See Microsoft's
  [DirectInput8Create HINSTANCE contract](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee416756(v=vs.85)).
- The actual client has called only the factory before its renderer boundary. It has not reached CreateDevice,
  EnumDevices, capabilities, cooperative level, or DirectInput callbacks. Those paths are not fabricated or
  speculatively implemented. All remaining IDirectInput8W slots retain individually named fatal diagnostics.
- Encountered prerequisites use real Windows calls: two-DWORD A/W StickyKeys get/set, GetDC/ReleaseDC for
  represented windows (including the desktop-window token), and GetDeviceCaps `BITSPIXEL` (32 on this host).
  StickyKeys changes are session-only and restore the captured host state on normal/fatal/timeout stops;
  both final client reports confirm successful restoration. Timeout cleanup avoids concurrent COM Release.
  Borrowed callback DCs cannot be released as acquired DCs. The class oracle now compares 472 values.

## Exact execution evidence

Final binary: `build/input-final/xrt_ucc.exe`, SHA-256
`ea02a6cf324087ba9d5ebd3db956daec72a3c48cdcb6dbbaab6f45799a2d0c34`.
Its `client-identity.json` binds all freshly compiled runtime/client objects and checks the reused generated
objects against the preserved full checkpoint. `xrt.h` and generated code are unchanged; the client build
has no compiler warnings.

Both final invocations have **23,123 events, zero dropped events**, and the same first remaining fatal:

- `results/raw/level/20261023-051602-15c5e746-candidate/`
- `results/raw/level/20261023-051827-026be1e1-candidate/`

In each, factory event 23081 returns a guest object with `S_OK`. UWindowsClient Init call/return events
23077/23084 share object/thread, return to `Engine.dll+0x8f5a3`, and adjust ESP by eight bytes (return plus
one argument). The original trace matches the same caller and its genuine WinDrv RET at `1939`.
The final fatal is seq 23121, followed by successful StickyKeys restoration and one owned COM release.
Engine `90f00` has not executed. No map-open or world-execution milestone is inferred from Golem file reads.

Earlier runtime steps were resumed and recorded separately: factory bridge → SystemParametersInfoW at
WinDrv `18d4` (`20261023-050800-cc94c422`); StickyKeys → GetDC at D3DDrv `d872`
(`20261023-050933-cc70d490`); window DC → GetDeviceCaps at `d87b`
(`20261023-051123-9b7b89da`); BITSPIXEL → Direct3DCreate8 (`20261023-051302-5ecdd625`).

```powershell
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\input-final\xrt_ucc.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --timeout-ms 45000
cmd /d /c experiments\xrt\tests\input_boundary\build.cmd
```

## Reference, regressions and next experiment

The established original reference `d1f7f7ddff9e-dgvoodoo` is preserved. Fresh run
`results/raw/graphics-startup/bfa5306f66a4-dgvoodoo/` again completes CS_Intro initialization with 268 of each
actor lifecycle event, **four returned selected-world ticks and three successful game Presents**.
It is complete, with no dropped events or exceptions. No new pixel-content or interactive-play claim is made.

Final validation logs and immutable fixture copies are in `results/raw/input-checkpoint-20261023/`:

- Input/COM, GUI, class, module, exception (six positives/two negatives), binary FILE and startup/memory
  oracles PASS. Input includes four deliberate unsupported cases. Existing fixture compiler warnings remain
  visible in logs; the final client build has none.
- Nine commandlet/VM cases PASS: `20261023-051719-9d331505`.
- Traced VMProbe PASS: `20261023-051853-8bd8f28f`.
- Compiler PASS: `20261023-051622-6a84c58e`, 16 compiles including four expected invalid-source failures,
  and 12 execution comparisons. Python: **149 tests OK, 17 expected skips**.
- Existing expanded CRT baseline remains **110 mismatches / 1,796 pending**; the focused fopen.0 reproducer
  freshly still differs. Fresh ACP 932 comparison retains **six differences**. No expectations were weakened.
- Read-only census compares all 4,757 installation files with the preceding audit: zero additional differences;
  Save entry metadata matches. The [unexplained Ogg finding](INSTALLATION_INTEGRITY.md) remains unresolved.

The smallest next experiment toward a translated world tick is a focused **native x86 versus x64
Direct3DCreate8 / immediate adapter-capability fixture**, identifying a host implementation that can preserve
the established dgVoodoo reference before writing a guest COM renderer bridge. The existing x86 wrapper cannot
be loaded into the x64 translated process. This checkpoint stops at that dependency; it does not return a
fabricated D3D object or skip render-device initialization to reach LoadMap.

---

# Historical class registration / engine initialization checkpoint — 2026-10-23 (US Eastern)

**Translated G4 is reached.** The real Unreal2.exe client enters `UGameEngine::Init`
(`Engine.dll+0x8f460`), executes Golem workspace file initialization, and enters
`UWindowsClient::Init` (`WinDrv.dll+0x17c0`). The first remaining blocker is
`dinput8.dll!DirectInput8Create`, called at `WinDrv.dll+0x184b` through its `+0x7bac` import thunk.
The translated client has not entered LoadMap or executed a selected-world tick.

Starting HEAD was clean at `27d1fa1dfff56c4e9cbbccb3cf40dee3fcfdb843`, on
`codex/level-initialization`. Both reported commits were present; no subsequent work was reset.
Runtime changes are committed as `66dc5d2` and `7b5ce8b`. No remote push, renderer adapter,
Android, adaptive audio, animation implementation or editor feature was added.

| Gate | Original reference | Translated final binary |
|---|---|---|
| G4: UGameEngine::Init entered | Yes, native event at the same Engine RVA | **Yes**, actual lifted function hit `8f460`; also WinDrv Init hit `17c0` |
| G5: genuine LoadMap entered | Yes | No; Engine `90f00` has not executed |
| G6: CS_Intro opened inside LoadMap | Yes, paired native file-open events | No |
| G7: LoadMap returns a non-null selected world | Yes, matched entry/return and selected world | No |
| G8: selected-world actor lifecycle completes | Yes, 268 PreBeginPlay/BeginPlay/PostBeginPlay events each | No |
| G9: selected-world Tick returns to its caller | Yes, four completed ticks | No |

Public identities and comparisons: `results/compare/class_initialization.json`.
The earlier original evidence and `results/compare/level_initialization.json` remain intact.

## Exact translated evidence

Final build: `build/class-init-final/xrt_ucc.exe`, SHA-256
`31ac96a685798b4c351b0e7619aaea3cd09d4922e5a915937381b0064e11744a`.
`client-identity.json` binds every newly compiled runtime/client object to its source and verifies
the unchanged generated objects against the preserved full checkpoint. `xrt.h` and generated code
are unchanged. The complete runtime tree, including the new class-marshalling include, matches
the build identity. The final client build has no compiler warnings.

Two final invocations reproduce the same DirectInput blocker with **23,080 recorded events, zero
dropped events**, G4/Windows-client Init entered, and G5 unreached:

- `results/raw/level/20261023-043932-5b948cd4-candidate/`
- `results/raw/level/20261023-043941-b56b1873-candidate/`

Each reads 2,185,122 actual binary file bytes through the measured FILE bridge. These are workspace
and mesh initialization reads, not a map-open or world-initialization milestone. Engine function hits,
the actual loaded PE identities, API events, registers, callback history and the WinDrv return address
are retained. Native and translated paths execute the same Engine input and Init RVA; no equality of
heap addresses, clocks or world state is claimed at this boundary.

```powershell
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\class-init-final\xrt_ucc.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --timeout-ms 45000
cmd /d /c experiments\xrt\tests\class_boundary\build.cmd
cmd /d /c experiments\xrt\tests\file_boundary\build.cmd
```

Use a new client build directory for further changes; preserve this identified final binary.

## Class, callback and startup comparison

The same project-owned PE32 fixture executes natively and through the real lifter/runtime.
Six positive probes produce **464 identical logged values**, and five deliberate unsupported
cases retain their fatal diagnostics. Final fixture binaries, reports and comparisons are pinned
under `results/raw/class-initialization-final-20261023/oracles/`; later fixture rebuilds cannot
overwrite that evidence.

- `GetClassInfoExA/W`, `RegisterClassExA/W`, `UnregisterClassA/W`, `CallWindowProcA/W` use real USER32
  classes/procedures. The 48-byte guest WNDCLASSEX is marshalled field by field. Native GetClassInfoEx
  returns a class atom in its BOOL result and leaves the input cbSize unchanged, including the measured
  cbSize=4 query. Duplicate registration, missing class, wrong module, invalid registration size, and
  unregister-with-live-windows errors match (1410, 1411, 87, 1412).
- All thirteen engine-queried controls are compared: LISTBOX, BUTTON, SysTabControl32, STATIC,
  SysListView32, EDIT, RICHEDIT, COMBOBOX, tooltips_class32, SCROLLBAR, SysTreeView32,
  msctls_trackbar32 and msctls_progress32. The seven controls with a 4-byte x86 / 8-byte host
  pointer slot have an explicit measured layout conversion. Superclass registration validates the
  queried structure's provenance and retains sufficient host storage; querying it returns guest sizes.
  Unmeasured system classes/layouts fail explicitly.
- Each registered guest class has a static host thunk, guest procedure VA, owning module and mapping
  generation. Real host/system and A/W-conversion WNDPROCs receive non-recycled prior-procedure IDs.
  CallWindowProc validates those mappings and executes the real procedure. An ANSI class queried
  through the W API correctly has a different prior-procedure identity. Unloaded/reloaded provider
  identities, invalid guest callbacks and unsupported pointer messages are deliberate negative cases.
  No host WNDPROC or host vtable pointer enters guest memory.
- Real A/W CreateWindowEx, CREATESTRUCT marshalling, DefWindowProc, scalar GetWindowLong, IsWindow,
  ShowWindow, desktop/client rectangles, child creation and WM_PARENTNOTIFY execute through the
  established nested guest callback bridge. CREATESTRUCT carries the original guest creation parameter;
  unmodelled field mutations fail explicitly. WINDOWPOS, MINMAXINFO and NCCALCSIZE mutations are
  synchronized before and after default/prior-procedure calls.
- Shared A/W icon/cursor resources, CreateBitmap, solid/pattern brushes and stock fonts retain typed
  ownership. WM_SETFONT/WM_GETFONT preserve font identity; WM_SETTEXT and text length reach real controls.
  A/W SetProp/GetProp/RemoveProp store opaque guest values in owned host boxes, with no host-pointer
  truncation. Unsupported messages, menus, subclass-pointer indices, brush callback results and layouts
  remain diagnostics. This is a measured startup subset, not full USER32 or callback exception support.
- Additional encountered launcher/WinDrv prerequisites use real Windows operations: A/W mutex creation,
  system/Windows directories, drive type, GlobalAddAtom and related atom lookup/release, plus
  GetModuleFileNameW. Atom references owned by this guest are released at normal exit and handled fatal
  stops. The module oracle now has **50 matching values plus three deliberate negatives**, including W
  filename success/error/truncation behavior. The public JSON lists all 48 added API bindings.

Binary fread and read-only binary fseek are separately checked against the actual msvcr70 DLL:
two positive probes have **188 identical values**, including actual bytes, item counts, buffer offsets,
counts, flags, capacity, EOF, seek origins and invalid-seek errno/last-error values. The measured CRT
temporarily reduces the next fill to 512 bytes after seeking, then restores the normal 4096-byte size.
Text/update/write-only reads, large/overflow transfers and invalid streams remain unsupported diagnostics.
Existing fopen/fclose initial/closed-FILE discrepancies remain visible; this oracle does not classify
those known failures as fixed.

## Preserved original reference and bounded capture

Preferred reference remains `results/raw/graphics-startup/d1f7f7ddff9e-dgvoodoo/`. Three fresh bounded runs
(`c2738819c688`, `7106dd80afc7`, `675a513ad94c`, each with `-dgvoodoo`) reproduce completed CS_Intro
initialization, four returned selected-world ticks, game CreateDevice S_OK and three normal Presents S_OK.
Every final trace is complete without dropped events or exceptions. The pinned dgVoodoo2 2.87.5 x86
DLL/configuration and four staged package dependencies are unchanged. No native renderer investigation
or configuration changes were needed.

**No valid game-pixel capture is claimed.** Two manually inspected window-DC captures contained
stale/unrelated application content. Window ownership checks alone did not establish a D3D image.
A final DPI-aware composed-desktop client crop, after DwmFlush and PID/visibility checks, failed with
Win32 error 5 (`675a513ad94c-dgvoodoo/host-output.txt`); it produced no BMP. The optional
`graphics_reference.py --capture-client --stop-after-present 3` records this separately from the trace.
An isolated tracer build was used while acceptance tracers were active. Capture failure does not
invalidate the already established world/tick/Present evidence. Visual scene content and interaction
remain unverified.

## Final acceptance, integrity and next step

- Nine commandlet/VM cases PASS: `20261023-043953-d321c5cc`.
- Traced VMProbe PASS: `20261023-044339-3dbf9d0b`.
- Compiler PASS: `20261023-043953-a1791a3c` (16 compiles, including four expected invalid-source failures;
  12 execution cross-checks).
- Existing GUI (53 values), module, exception (six positives/two negatives), startup/memory and new
  class/file oracles PASS. Python: **149 tests OK, 17 expected skips**.
- Expanded CRT baseline remains **110 mismatches / 1,796 pending**; the fopen.0 reproducer freshly
  still differs, exit 1. Fresh ACP 932 comparison still has **six differences**, exit 1. No expectations
  were weakened and no exhaustive numerical corpus was repeated.
- Read-only installation census: 4,757 files match the preceding audit, with no additional difference;
  Save entry census matches. The previously unexplained Ogg difference is **not resolved**. Its changed
  compressed-data byte fails one Ogg page CRC and changes decoded PCM. Details and reproduction are
  separate in [INSTALLATION_INTEGRITY.md](INSTALLATION_INTEGRITY.md), outside porting acceptance.

The smallest next step is a focused native-x86/translated **DirectInput8Create / IDirectInput8W** oracle.
The observed call requests version `0x0800`, IID `bf798031-483a-4da2-aa99-5d64ed369700`, NULL outer, and
the Window module's HINSTANCE. Measure the real HRESULT and module-identity requirement, then implement
an owned host COM interface behind a guest object/vtable with real QueryInterface/AddRef/Release.
Advance only the next observed method, preserving data layouts and callback identity. Do not insert
host COM pointers into the guest output slot, invent a DirectInput failure, or bypass input initialization.
The D3D8 ABI and genuine LoadMap path remain subsequent prerequisites to a translated real game frame.

---

# Historical level initialization checkpoint — 2026-10-22 (US Eastern)

Starting Git state was clean at `280b25e8f4e8b8c81bf55413e9d50e920cac005b`. The earlier checkpoint and
all raw runs remain preserved. No pushes, renderer rewrite, Android, audio implementation, editor features,
or animation work were added.

| Question | Verified result |
|---|---|
| Original CS_Intro level initialization completed? | **Yes.** Matched genuine LoadMap call/return, non-null selected ULevel, 268 PreBeginPlay/BeginPlay/PostBeginPlay callbacks each inside that call. |
| Original selected world executed? | **Yes.** Four ticks on that exact returned ULevel, observed through RET and return to the engine caller. |
| Game itself created/presented graphics? | **Yes.** Original D3D8 CreateDevice S_OK, initial Present S_OK, then three normal game Present calls S_OK through dgVoodoo/D3D11. |
| Visible scene or interactive play verified? | **No.** This is world execution and API presentation evidence; no pixel capture, visual-content check or input test was performed. |
| Translated UGameEngine::Init / LoadMap entered? | **No / no.** It now passes SHELL32 module lookup, both GetProcAddress calls and RICHED32 loading, then fails explicitly at GetClassInfoExW. |

## Original evidence and exact reproduction

Preferred raw run: `experiments/xrt/results/raw/graphics-startup/d1f7f7ddff9e-dgvoodoo/`.
It has a complete trace, zero dropped events and zero dropped exceptions. The controlled stop is the third
normal game Present return (`event_limit`, debuggee code `0xe0000001`), not a natural process exit.

- LoadMap entry seq 111; successful selected-map file open seq 112/113; matched LoadMap return seq 1040,
  selected world `0x0ff52800`. Return shares thread, ESP and caller with entry. Entry-world callbacks/ticks
  are distinguished from selected-world events.
- Selected-world tick seq 12327 → RET 12334 → caller 12335, followed by three further completed selected-world
  ticks. The tick's ECX is the exact selected LoadMap return value. Its caller is Engine.dll+93c1e.
- Game CreateDevice call/return seq 12322/12323 returns S_OK. Normal game Present returns at seq 12341,
  12358 and 12368 return S_OK. These are original D3DDrv call sites, not the standalone device probe.
- D3DDrv+f0ce is IDirect3D8::CreateDevice (seven stack arguments including this, vtable +3c);
  D3DDrv+f17f is the **initial IDirect3DDevice8::Present**, following Clear at +f165. The latter was
  initially labelled CreateDevice.3 in exploratory traces; the final driver and evidence correct that label.
  Normal Present is +b387/+b38a. An alternate branch uses +b3c8/+b3cb.

`tools/xrt/world_evidence.py` reproduces these correlations. Its seven counterexample tests reject a map open
without LoadMap return, Entry-only ticks, a tick without return to its caller, failed map calls, dropped records,
and HRESULTs without the observed game call.

Installed singleplayer content was copied into each fresh sandbox (no links). The missing dynamic packages
were `Textures/SubTFonts.utx`, then `Sounds/U2Player_A.uax`, then `Textures/HUD_Fonts.utx` and
`Textures/UI_Fonts.utx`; the latter two are named by shipped HUD scripts/localization. Source/destination
hashes are in each meta.json and in `results/compare/level_initialization.json`. The previously verified
x86 dgVoodoo2 2.87.5 DLL and exact `86d97ac3...` configuration were retained.

From the workspace root in PowerShell:

```powershell
.venv/Scripts/python -I tools/xrt/graphics_reference.py dgvoodoo --package Textures/SubTFonts.utx --package Sounds/U2Player_A.uax --package Textures/HUD_Fonts.utx --package Textures/UI_Fonts.utx --stop-after-present 3 --timeout-ms 30000
.venv/Scripts/python -I tools/xrt/world_evidence.py experiments/xrt/results/raw/graphics-startup/d1f7f7ddff9e-dgvoodoo/trace.json
```

The first font-only run `0812ccc13ba8-dgvoodoo` exhausted the tracer's 128-module capacity and produced no
complete trace; it is excluded. The tracer now retains 512 module records and 32768 exception records and
reports exception overflow explicitly. Final run retains all **11011** first-chance exceptions, including
32 missing-UISounds exceptions and many UI enum/render-target lookups. These remain visible despite the
successful level/tick/device milestones. No audio behavior was implemented. The 30-second exploratory
`f54e61270742-dgvoodoo` run reached repeated ticks/presents but its old exception table saturated; use the final
bounded run for complete evidence.

## Translated module boundary

Preferred raw run: `experiments/xrt/results/raw/level/20261023-034922-fdde6c7f-candidate/`.
Final binary/build identity: `experiments/xrt/build/level-init-handoff/{xrt_ucc.exe,client-identity.json}`.
The build freshly compiles every runtime/client source and verifies reused generated objects from the preserved
full checkpoint `fresh-20261023-015722-b7ee8987`. Source, object, lift and binary hashes are recorded.

- SHELL32 comes from actual guest PE import membership, independent of incidental host DLL loads. Guest
  system HMODULEs are typed tokens backed by owned real x64 loader references, with separate guest import and
  LoadLibrary counts. GetModuleHandleA/W borrows identity without incrementing the guest load count.
- System32-only host loads are allowlisted. WOW64 PE32 images are mapped solely as non-executable metadata;
  named/ordinal export existence comes from those x86 tables and must have a matching host named export.
  Guest GetProcAddress returns guest adapter/trap stubs; host code pointers never enter guest state.
- Real unadapted exports may be retrieved, but calling them remains an explicit import failure. Stubs are
  invalidated for calls when the last guest reference is released. FreeLibrary releases owned host/resource
  mappings and tokens at zero references. Invalid releases match the measured Windows error 126.
- Translated images retain their existing guest bases, exports and DllMain/refcount behavior. Unloaded images
  no longer match handles, and explicit module paths must match the loaded image's full path.
- Remaining limits fail visibly: unsupported system-module backings, host-only/transitive membership queries,
  unnamed ordinal exports, dynamic system data exports, and freeing a borrowed static import without a dynamic
  reference. This is the measured startup subset, not a complete Windows loader or GUI implementation.

The final client records: SHELL32 handle seq 211, Shell_NotifyIconW guest stub seq 212,
SHGetSpecialFolderPathW guest stub seq 213, RICHED32 load seq 215. Neither shell function was called.
Seq 216 is the exact remaining blocker:

```text
USER32!GetClassInfoExW
Window.dll+0xc3b3, WControl::RegisterWindowClass+0x63
```

The existing real splash and nested translated callback path still completes. The next class-query result
contains a WNDPROC and handles: copying the host WNDCLASSEXW structure into guest memory would violate pointer
separation. The smallest translated experiment is an x86/translated oracle for this observed class query,
then typed prior-WNDPROC identity and CallWindowProc/class registration as actually reached.

```powershell
$env:XRT_BINARY = 'E:\Unreal2-Port-Investigation\experiments\xrt\build\level-init-handoff\xrt_ucc.exe'
.venv/Scripts/python -I tools/xrt/level_probe.py candidate --timeout-ms 45000
cmd /d /c experiments\xrt\tests\module_boundary\build.cmd
```

The module oracle executes the same project-owned x86 DLL natively and lifted, with identical 38-value logs
and zero failures. It covers case/extension aliases, NULL/A/W lookup, full paths and wrong paths, absent modules,
exact-case/missing/data exports, callable adapted exports, filenames, two A/W RichEdit load references,
borrowed lookup and unload/error behavior. Three deliberate negatives preserve unadapted export calls,
stale export calls and unmodelled transitive identities as explicit failures.

## Validation, preservation and next experiment

Public identities and run links: `results/compare/level_initialization.json`. The first final build passes all
nine registered commandlet/VM cases (`20261023-034435-936744b5`) and a full compiler invocation
(`20261023-034436-0db4f5a4`, 16 compiles + 12 execution cross-checks). The subsequent handoff build repeats these
checks after the explicit transitive-membership guard; its exact invocation IDs are in the public JSON.
GUI, client startup/memory and exception oracles pass; exception scope is six positives plus two deliberate
negative cases. Python suite: 142 tests, 17 expected skips, plus seven new evidence tests. Earlier results remain
preserved. Existing CRT discrepancies are unchanged; no CRT implementation was modified.

**Install audit is not a clean PASS.** Relative to the prior full checkpoint snapshot, 4757 files compare with
one unexplained one-byte difference in `singleplayer/Music/M03_fite_loop2.ogg`: offset 489527 is now `0x2e`,
checkpoint sandbox byte `0x6e`; size and recorded mtime match. Checkpoint SHA-256 is
`b6261e7e09ca82b48361702d09ea6d24c7d24a85b4073dd1ff1920f1317318bb`; current source hash is
`6518e44f945853bf935bd674dbc84b9d9a8310beea1bb7262cf240dfd10fa2bf`. Repeated reads agree. There was no full
install snapshot at this turn's start, so its timing/cause is unestablished. No writes to that file or the install
were issued, and original/sandbox files have distinct identities and one hard link each. Both are preserved;
the installation was not repaired. Save-junction metadata matches the checkpoint. Raw audit and byte-offset
record remain under results/raw/level-init-install-*.json.

The original is now the reference for a running CS_Intro world. A bounded visual/input capture and staging the
observed UISounds content would further characterize that scene; neither is needed to claim the measured tick
or API Present. For recompilation, advance the measured class-registration boundary toward UGameEngine::Init
before any renderer adapter. No interactive gameplay or translated world execution is claimed.

---

# Prior graphics-startup checkpoint — historical at 280b25e

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
