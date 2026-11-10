"""Write the characterization report from audited evidence; no client execution."""
import json
from pathlib import Path
from run import W,HERE,sha,write
O=W/'out/recovery/d3d8-device-20261025-01'
M=json.loads((O/'measurement.json').read_text())
dest=W/'experiments/xrt/D3D8_DEVICE_CHARACTERIZATION.md'
text='''# Native D3D8 CreateDevice characterization

2026-10-25, US Eastern. **CONDITIONAL GO for a future narrowly guarded bridge for the
captured successful tuple. General creation/retry support is NO-GO while backend failure
cleanup remains unresolved.** No production device creation or device method was implemented.
No genuine graphical client ran. This phase ends at characterization.

The pinned native x86 and x64 backends both create a real device for the captured Unreal II
parameters. A separate lifted PE32 fixture also creates real x64 devices. Success-path
identity and lifetime behavior are consistent across these tests. The important limitations
are failure-path resource growth, different last-error observations, and untested callbacks
from a genuine visible game window. No Clear or Present reached a native device.

1. Preserved checkpoint and evidence

HEAD remains `8c6220a6baadd575340fa81e51e2fa0a2af86a8c`. All previously pending work remains
byte-for-byte preserved. All additions are fixture source, evidence and this report. The
production runtime's 27 files and all 299 generated game files are unchanged. No client
executable was rebuilt. The accepted executable remains
`experiments/xrt/build/d3d8-depth-20261025-01/xrt_ucc.exe`, SHA-256
`74866a16b8e1dfd5b7feaa609c56538cd469bc4ee632c95a4cc829830c2d693a`.

The preflight preserves 586 tracked/untracked working files, staged/unstaged binary patches,
and inventories 15,375 existing build files plus 17,353 raw evidence files. The build inventory
also contains newly created device probes encountered while the inventory was running;
all genuinely earlier build/evidence files are included. Final verification checks every
inventoried file without resetting, deleting, committing or changing the index.
`out/recovery/d3d8-device-20261025-01/preflight.json` and `final-integrity.json` contain the checks.

The protected manifest is SHA-256
`3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173`:
4,122 manifest files, three protected trees and nine protected files. The pinned compiler,
SDK headers/libraries, accepted objects, DirectMusic helper and DXVK pair hashes are verified
through the accepted depth checkpoint's verification code. DirectMusic helper SHA-256 is
`a141ffe197f3eb14ed5908c946bd3cb541fdf456175b5a602b52df1b64484d22`.
No original installation or saves were accessed. Source snapshots for every completed native
build revision and translated build retain the exact source hashes recorded at build time.

| DXVK 3.1.1 binary | SHA-256 |
|---|---|
| x86 d3d8.dll | `9152ba43386e756790a66f61cdcee01b3287d156d4161c7456d816faa82fc364` |
| x86 d3d9.dll | `265888c31ca78dffa290c39cb7e50bfb02762590e41927906e46fb32f01497fa` |
| x64 d3d8.dll | `bd65cebf8ece6f80a841a16d98bdf5b76894c172b7ba344180baa17a4d00680c` |
| x64 d3d9.dll | `c126316f7478eaff1ad8087702eda5930f2400187b9c8b3592219c34f6632780` |

2. Exact native results and presentation mutation

Adapter 0, DeviceType 1, BehaviorFlags `0x42`; separate owned hidden native top-level window
used for both hFocusWindow and hDeviceWindow. The genuine guest token `0x126c` was never cast
to an HWND or reused by the oracle. Native windows belong to each probe process.

| Architecture | HRESULT | Example returned native pointer, seed 18 | Last-error |
|---|---|---|---|
| x86 | `0x00000000` | `0x138e4440` | `18 -> 0` |
| x64 | `0x00000000` | `0x23c80103380` | `18 -> 0` |

These exact examples are from the seed-18, process-repeat-0 corpus records. Pointer addresses
vary and may be reused after destruction; they are not cross-process identities. All 32 exact
calls (16/architecture) succeed across four seeds, two processes/seed and two calls/process.
Seeds 0, 18, `0x13572468`, `0xffffffff` all become 0. No HRESULT, output, enum or last-error
compatibility mapping is used.

| Presentation field | Input | Output, both architectures |
|---|---:|---:|
| BackBufferWidth | 1540 | 1540 |
| BackBufferHeight | 945 | 945 |
| BackBufferFormat | 22 | 22 |
| BackBufferCount | 1 | 1 |
| MultiSampleType | 0 | 0 |
| SwapEffect | 1 | 1 |
| hDeviceWindow | owned native HWND | same HWND |
| Windowed | 1 | 1 |
| EnableAutoDepthStencil | 1 | 1 |
| AutoDepthStencilFormat | 77 | 77 |
| Flags | 1 | 1 |
| FullScreen_RefreshRateInHz | 0 | 0 |
| FullScreen_PresentationInterval | 0 | 0 |

All raw structure bytes also match before/after for the exact tuple. Mutation cases:
BackBufferCount 0 becomes 1; BackBufferFormat 0 becomes 22. Width/height 0 remain 0 in the
caller's D3D8 structure even when internal backbuffers acquire window dimensions. Every
other tested case leaves all 13 fields unchanged, including returned failures.
Read-only presentation memory still faults on a write at offset 12 (BackBufferCount),
even for input count 1; an unchanged final value does not imply a read-only input contract.

3. Architecture differences and ABI/FPU/SSE

Native presentation sizes are **52 bytes on x86 and 56 bytes on x64**. HWND offset is 24
on both; HWND is four/eight bytes respectively. Windowed offsets are 28/32; interval offsets
48/52. Device creation-parameter sizes are 16/24 bytes. Do not memcpy the guest structure
into the host structure. All non-HWND presentation fields remain 32 bits.

The x86 method pops 28 argument bytes (this plus six explicit arguments), with the return
address making a 32-byte guest boundary delta. x64 uses RCX=this, EDX=adapter, R8D=type,
R9=focus HWND, then flags/parameters/output in stack arguments with normal shadow space.
Twenty-four native assembly snapshots cover exact success, flags `0x40`, invalid adapter and
unsupported depth. ESP/RSP deltas are zero; x86 EBP/EBX/ESI/EDI and x64 all eight nonvolatile
GPRs and XMM6..XMM15 retain their distinct seeds. The wrappers restore their own caller state.

With flags `0x42`, seeded x87 control `0x077f`, status `0x3000`, tag `0xc0`, and two live
80-bit values (pi and 1) are preserved on both architectures. Inactive x87 register storage
can change on x86; it is retained in the raw snapshots and is not treated as live state.
Without FPU_PRESERVE (flags `0x40`), control becomes `0x007f`. Successful creation and depth
failure change MXCSR `0x3f80 -> 0x3fa0` (precision sticky status); invalid adapter preserves
`0x3f80`. MXCSR control bits are retained. FPU_PRESERVE does not mean all SSE status bits
remain identical. The translated fixture verifies stack return behavior and typed pointers;
it does not establish complete translated FPU/SSE equivalence.

Fresh-process oversized dimensions (16385x1 or 1x16385) return `0x8876086a` and NULL on both
architectures. x86 last-error is 0 and x64 is 203, repeated in fresh processes for all four
seeds. In the eight-failure x86 width test, the first error is 0 and later errors are 203;
x64 errors are 203 throughout. Thus this is an observed architecture/process-state difference,
not a universal rule to synthesize. All raw values remain preserved. HRESULT and normalized
field mutation agree across the measured architecture corpus; native pointers/layouts differ.

4. COM identity, native lifetime, windows and cleanup

Device QI for IUnknown and IID_IDirect3DDevice8 returns S_OK and the same pointer, acquiring
one reference; the balancing Release returns 1. IID_IDirect3D8, IID_IDirect3DDevice9 and an
unrecognized GUID return `0x80004002` and clear the output. NULL QI output returns
`0x80004003`. Supported QI preserves error seed 18; the first logged parent-interface rejection
can change it to 0, while later rejected cases preserve 18. These are observations, not a
promise of QI last-error stability.

Initial device refcount is 1; AddRef returns 2, balanced Release 1, final Release 0.
The device retains its parent: parent AddRef with a device returns 3, balanced Release 2.
GetDirect3D returns the original parent and acquires a ref, balancing to 2. Releasing the
external parent first returns 1; GetDirect3D still works with identical parent identity and
balances to 1; releasing the device finally destroys the retained parent. No stale native
pointer was dereferenced as a test. Device final Release and independent final parent Release
return 0 in every orderly case.

GetCreationParameters reports the passed focus HWND, adapter, type and flags for the exact
tuple. A separate-window, zero-dimension test proves the presentation association through
GetBackBuffer/GetDesc: focus client size 1544x961, device-window client size 784x561, actual
backbuffer 784x561. The caller's zero dimensions remain unchanged. Focus and presentation
window mapping must therefore be independent. Exact backbuffer description is
`[22,1,1,0,5821200,0,1540,945]`; its temporary surface reference balances to 0 before device
destruction. No surface or device rendering operation was called.

Windows are owned by the current process, with recorded owner thread IDs. A worker-thread
CreateDevice using main-thread-owned windows also succeeds on both architectures, while
the main thread pumps messages. This does not establish cross-thread rendering safety.
For these hidden windowed tests there are no callbacks during CreateDevice, no foreign-thread
WndProc dispatches, and no observed WndProc subclassing. WndProc identity is unchanged after
Release. Visible windows, fullscreen, Reset, and genuine guest callbacks remain untested.

Eight repeated successful creations per architecture have stable post-release handle/thread/
USER/GDI counts after the first creation. D3D8 and D3D9 unload. Final process handle counts
remain above the pre-load baseline (driver/runtime caching is not attributed), so the evidence
supports bounded stability, not proof that every driver allocation is reclaimed before exit.

**Failed initialization has a materially different cleanup result.** Unsupported depth,
invalid format, and over-limit dimensions leave D3D9 loaded after parent Release 0 and the
oracle's balanced FreeLibrary calls. Eight repeated failures grow threads 4 -> 36 and USER
objects 4 -> 12 on both architectures, approximately four threads and one USER object per
failure. Handles also grow. In the x86 depth-71 test, factory-ready/final counts are
228/335 handles and 4/36 threads; x64 is 211/310 and 4/36. Final USER count remains 9 after
the oracle's two windows are destroyed. These processes then exit, reclaiming their resources.
No extra FreeLibrary/Release calls were guessed to conceal the result.

The pinned [DXVK D3D9 creation source](https://raw.githubusercontent.com/doitsujin/dxvk/v3.1.1/src/d3d9/d3d9_interface.cpp)
allocates a device and returns directly on InitialReset failure. That is a plausible source
explanation for the measured retained resources, not a completed root-cause fix. No DXVK
binary/source was changed. General in-process retry is not accepted by this checkpoint.

5. Negative and permissive cases

Every case below uses a separate disposable process, seed 18, with all other fields equal to
the exact tuple. `NULL` means the output storage was set to NULL. `sentinel` means the local
output remained `0xa5a5a5a5`. For NULL output pointer the local sentinel is not an output
returned by the backend. For an exception **no HRESULT returned**: raw `0xdeadbeef` is only
the probe's untouched HRESULT sentinel. AV is `0xc0000005`; those isolated processes exit
90 immediately after recording, with no claim of orderly COM teardown.

'''
text+='| Case | x86 HRESULT / last-error / output | x64 HRESULT / last-error / output |\n|---|---|---|\n'
for name,arches in M['negative'].items():
    values=[]
    for arch in ['x86','x64']:
        r=arches[arch]
        result='AV; no HRESULT'if r['exception']else f"`0x{r['hr']:08x}`"
        output='NULL'if r['output']==0 else('sentinel'if r['output']==0xa5a5a5a5 else'non-null device')
        values.append(f"{result} / {r['last_error']} / {output}")
    text+=f'| {name} | {values[0]} | {values[1]} |\n'
text+='''
Invalid adapter cases are adapter-count (2), 65535 and UINT_MAX. Types 0, 2, 4 and UINT_MAX
are accepted; type 3 fails. HWND cases vary focus and presentation HWND independently;
invalid is native value 1, with no external window accessed. Successful creation with an
invalid/NULL HWND establishes only creation behavior: no subsequent Present was attempted.
Over-cap dimensions are bounded 16385x1 or 1x16385, avoiding unbounded allocations.
NULL/read-only/no-access/value-1 pointer cases preserve actual mutation and exceptions.
Read-only PP faults at PP+12, output becomes NULL first. Bad output pointers fault on their
first write. NULL PP returns INVALIDCALL and clears a valid output. No windowed/fullscreen
toggle, real external window, GPU hang, or huge allocation stress case was used.

6. Real translated fixture and typed boundary design

Final translated fixture: `experiments/xrt/build/d3d8-device-translated-20261025-04/translated.exe`,
SHA-256 `227e545ec7be98710487e99980112009ef42641734ab09085b945ffdf8c20f01`.
The lifted fixture uses the production Direct3DCreate8 factory/query implementation, then
calls the separate `fixture.dll!FixtureCreateDevice` entry. A generated copy of hle_misc.c
in the fixture build includes the prototype; no runtime source file was edited. The genuine
game cannot reach this import or the fixture-only device vtable.

Eighteen final fixture processes make 28 actual CreateDevice attempts, including 20 successful
devices, and compare 352 result/structure/identity/lifetime values. Only HWND token identity
and pointer non-nullness are compared across pointer domains; actual HRESULTs and last-error
remain exact. Each successful object has all 97 guest vtable entries audited against its
named guest stub. All guest CreateDevice returns have a 32-byte ESP delta and the exact return
address. Fatal probes separately verify stale device, Clear, Present, bad PP, bad output and
the unchanged production CreateDevice guard. All final reports have contiguous events and
zero drops. Outstanding fixture device refs are released before factory cleanup; the leak
probe releases two device refs. Parent-first release and GetDirect3D revival preserve identity.

Earlier fixture attempts are retained: revision 01 has a linker failure for missing _fltused;
revision 02 created devices but an inherited audit tried to read an absent fixture export
after return. The harness was corrected to use the proper base host. Revision 03 passed;
revision 04 adds explicit slot-audit evidence and two pointer guards. No production workaround
or lifter change was made for those harness issues.

Proposed minimal production bridge, **design only**:

- Validate a typed parent object, four writable guest output bytes, and all 52 read/write
  guest presentation bytes, including wraparound, page protection and guard-page checks.
  Handle NULL according to measured native results through the backend; invalid non-null
  guest addresses remain diagnostic stops, not native dereferences or invented HRESULTs.
- Resolve focus and presentation HWND tokens separately through XH_WINDOW, preserving NULL.
  Check liveness/ownership and current guest/native thread mapping. Never cast the DWORD
  token or substitute the fixture window for guest `0x126c`.
- Marshal every scalar into a local native 56-byte structure; use a local native 8-byte
  device output. Seed host last-error from guest immediately before the call, capture it
  immediately after, and preserve measured structure mutations on both success and failure.
  Translate any returned HWND through the identity map; never copy native pointer bits.
- Pre-reserve wrapper/table capacity before host creation; adopt exactly its returned native
  reference on success. Allocate a guest object with a 32-bit vtable pointer and all 97 typed
  stubs. Use a distinct device ownership registry, with guest refcount, host pointer, parent
  identity and tombstones/generations. Roll back any adopted reference if publication fails.
- Forward QI/AddRef/Release to the native interface. On supported successful QI reuse the guest
  identity and add one tracked ref. A new successful native interface requires explicit typed
  support; do not expose it as this device. A final guest Release tombstones that guest object.
- Keep parent identity discoverable while a child retains it, even when the parent's external
  guest refs reach zero. GetDirect3D must adopt its actual returned native reference and revive
  the same guest parent identity. The existing factory registry alone needs this extension;
  it must not infer parent lifetime solely from external guest refs or double-release the
  backend's internal parent reference.
- Release exposed resource refs, then devices, parent guest refs, owned windows/tokens, and
  module references in an order that leaves windows/backend code alive during destruction.
  Unsupported methods identify interface, slot, name, caller and arguments and terminate.
  Clear/Present/rendering remain unsupported until a later measured implementation.
- Establish a scoped GUI callback CPU context around native calls before using a genuine
  guest-backed window. Restore any prior context on exit; do not publish a half-constructed
  device. Hidden-window absence of callbacks cannot justify disabling the existing callback
  machinery or allowing concurrent unmodelled guest reentry. Cross-thread native success does
  not justify moving device calls away from the guest window's owning thread in the first bridge.
- Preserve guest CPU/FPU state independently of host floating-point work. Native SSE sticky
  status must not be copied blindly into the guest. Add a translated ABI/FPU fixture before
  promoting the prototype; the present translated test does not prove that full contract.
- On a backend initialization failure, retain exact HRESULT/output/mutation/error, stop the
  bounded experiment and tear down the process. Do not retry or unload code still retained by
  the backend. General retry requires resolving or containing the measured resource growth.

7. Exact public device vtable

The public interface has 97 slots: 388 guest bytes, 776 native x64 bytes. The object stores
its vtable pointer at offset zero. Every x86 argument occupies a four-byte word, including
float and interface pointers. Argument bytes below include this, excluding the return address.
AddRef/Release/GetAvailableTextureMem return ULONG/UINT; ShowCursor returns BOOL;
SetCursorPosition/SetGammaRamp/GetGammaRamp return void; other slots return HRESULT.
The ordering was checked against the primary
[mingw-w64 D3D8 interface declaration](https://raw.githubusercontent.com/mingw-w64/mingw-w64/master/mingw-w64-headers/include/d3d8.h).

'''
text+='| Slot | Guest offset | x64 offset | Method | x86 argument bytes |\n|---:|---:|---:|---|---:|\n'
for s in M['slots']:text+=f"| {s['slot']} | {s['guest_offset']} | {s['native_x64_offset']} | {s['name']} | {s['stdcall_argument_bytes']} |\n"
text+='''
8. Required initial methods and distance to first Clear/Present

The unchanged generated game code gives a specific static prediction, not a new execution
milestone. After CreateDevice returns S_OK, D3DDrv.dll+0xf165 calls device slot 36 (Clear),
and +0xf17f calls slot 15 (Present). The first Clear has Count=0, pRects=NULL, Flags=1,
Color=0, Z bit pattern 0, Stencil=0. Present passes four NULL/zero arguments. Slot 50
(SetRenderState, offset 0xc8) follows at +0xf196. These calls were inspected in the existing
generated source and were never executed in this phase.

The minimum first experiment needs the typed creation/lifetime foundation (QI/AddRef/Release,
parent identity and shutdown), measured Clear and Present, plus safe HWND/callback behavior.
GetDirect3D and GetCreationParameters are useful initial ownership/query support already
prototyped only in the fixture; GetDeviceCaps/GetDisplayMode remain typed query work if the
genuine client calls them. SetRenderState is needed to progress after the initial presentation.
Do not promise that this set completes renderer initialization: resource interfaces, textures,
buffers, state, shaders and drawing remain outside this checkpoint.

Engineering estimate: approximately **3–5 focused work sessions** to implement and validate
the constrained creation bridge, add translated ABI/callback tests, characterize/bridge the
two initial rendering methods, and attempt one later explicitly authorized bounded client
continuation. This is an estimate to reach a first Clear/Present attempt, not a first useful
rendered game frame. The backend failure cleanup fix/containment and any new game boundary
can add unbounded work; a full renderer estimate is not supported by this evidence.

9. Recommendation and stopping point

**CONDITIONAL GO** for the captured successful path, with typed ownership, full pointer/window
marshalling, callback/FPU validation, and one-attempt process containment on backend failure.
**General CreateDevice and in-process retries remain NO-GO** pending the measured failure
resource-growth issue. Neither source inspection nor the fixture is approval to enable
production CreateDevice in this phase.

The characterization audit passes 154 native processes / 238 calls (excluding the two initial
smoke calls), 24 native ABI snapshots, 18 final translated fixture processes, and 352 exact
compared values. Earlier successful fixture runs, failed builds and harness failures remain
preserved. No production methods, Clear/Present host calls, graphical client continuation,
Android changes, remote push or release occurred.

Primary evidence: `out/recovery/d3d8-device-20261025-01/measurement.json`,
`experiments/xrt/results/compare/d3d8_device_characterization.json`,
native corpus under `experiments/xrt/build/d3d8-device-fixture-20261025-02/`,
extended/failure-repetition corpus under `experiments/xrt/build/d3d8-device-fixture-20261025-04/`,
and final fixture reports under `experiments/xrt/build/d3d8-device-translated-20261025-04/`.
Commands, environments, raw fields, actual output pointers, FX snapshots, return counts,
resource samples, DXVK logs and exceptions are retained per process.
'''
dest.write_text(text)
print(dest)
