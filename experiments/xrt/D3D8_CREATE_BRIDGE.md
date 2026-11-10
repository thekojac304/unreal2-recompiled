# Guarded production D3D8 CreateDevice bridge

2026-10-25, US Eastern. **Ready for one separately authorized, bounded game test
that stops at the next unsupported method.** This phase ran zero genuine graphical
clients and implemented no rendering method. General creation and retries remain
unsupported. Final integrity is recorded in the linked evidence below.

1. Binary and preserved checkpoint

New executable: `experiments/xrt/build/d3d8-create-20261025-02/xrt_ucc.exe`.
SHA-256: `bb567875567e67a83ca30ca79d34a05790d7744626ef8c80a6e8c5f40bb14b82`.
The first fresh build compiled all 279 objects serially, with zero warnings.
The final ownership-containment tightening rebuilt all 14 runtime
objects serially in a second fresh directory, reusing 265 hash-verified
generated objects from that full build. Generated inputs and their headers are
unchanged. Both builds are preserved. The build records commands, source hashes, object
hashes, PDB hashes, logs and warnings in
`out/recovery/d3d8-create-20261025-01/build.json` and `build-02.json`. All phase executables, objects,
PDBs and runtime/fixture sources are identified in `artifact-identities.json`.

HEAD remains `8c6220a6baadd575340fa81e51e2fa0a2af86a8c`. The accepted depth executable remains unchanged,
SHA-256 `74866a16b8e1dfd5b7feaa609c56538cd469bc4ee632c95a4cc829830c2d693a`. The preflight preserved 602
working files, the staged/unstaged binary patches, 16686 historical
build files and 17353 raw evidence files. Existing pending work was
retained; only the D3D8 bridge, GUI scope/window pins and host-only declarations
were changed in existing runtime sources. No commit, push or release was made.

2. Real native and translated creation

Native x86, native x64 and the production translated PE32 fixture all return
actual **S_OK (0), last-error 0 and a non-null owned device** for Adapter 0,
DeviceType 1, BehaviorFlags 0x42 and the exact captured 1540x945 / format 22 /
count 1 / multisample 0 / swap 1 / windowed 1 / auto-depth 1 / depth 77 /
flags 1 / refresh 0 / interval 0 tuple. Seeds 0, 18, 0x13572468 and 0xffffffff
all return native last-error 0. No HRESULT or successful pointer is synthesized.
The final corpus contains 26 native processes,
64 translated processes and 28
successful translated devices, each in its own process. The common ownership
corpus compares 350 values exactly across all three architectures;
additional seed, ABI, pointer and injected-path assertions are recorded separately.

3. COM ownership and parent lifetime

The full 97-slot guest table is audited against its named 32-bit guest stubs.
Only QueryInterface, AddRef, Release, GetDirect3D and GetCreationParameters are
enabled. All other slots are named diagnostic traps and were never invoked.
IUnknown/device QI returns the canonical guest device; rejected parent/unknown
IIDs return actual E_NOINTERFACE and NULL. NULL QI output returns actual E_POINTER.
Device AddRef/Release return actual native counts 2/1, and final Release returns 0.

Parent-first Release returns native count 1. GetDirect3D revives the same guest
parent identity with a real native acquired reference, and its balancing Release
returns 1. Stale device, destroyed parent and externally dead retained parent
calls all stop before native access. Guest reference counts remain independent
from the parent's native internal device reference. A temporary private parent
reference protects creation against parent release from a nested callback and is
balanced before return. Leaked device refs are released before outstanding parent
refs; the shutdown probe releases two of each and unloads both backend modules.

4. Guest memory and HWND marshalling

The bridge checks all 52 presentation bytes for readable/writable committed pages,
all four output bytes, overflow, guard pages and output/presentation overlap before
any native call. The final-page tests put the last presentation DWORD or final two
output bytes on read-only, no-access and guard pages, requiring the bridge's own
range diagnostic. IID reads and ownership outputs have separate guards.
Unsupported scalar tuples are rejected before DXVK entry.

Every presentation scalar is explicitly marshalled into the native 56-byte
structure and back. Focus and presentation HWNDs are resolved independently
through the existing typed GUI registry, checked for process/thread ownership,
and pinned until device destruction. Same-window, separate-window, NULL focus,
NULL presentation and both-NULL cases pass. Stale/wrong-type/unknown tokens stop
before the backend. Returned HWNDs are mapped through known identity; native HWND,
device pointer and x64 vtable bits never enter guest memory. GetCreationParameters
uses the corresponding 16-byte guest / 24-byte native conversion. Exact tuple
presentation fields are unchanged by DXVK. A clearly marked test-only mutation
hook verifies all thirteen copyback offsets, including NULL HWND.

5. Callbacks, ABI and FPU/SSE

Native creation runs inside a scoped guest callback context. Four injected nested
WM_GETICON callbacks see NULL device output; the whole suspended CPU (registers,
flags, modeled x87 state) and 32-byte call frame are unchanged. Parent release
during the callback also passes, and reentrant creation is rejected. These are
controlled callbacks inside a real backend call boundary; hidden-window DXVK did
not independently generate creation callbacks. Visible game callbacks remain for
the future bounded game test.

Translated x86 assembly verifies a 32-byte CreateDevice boundary delta, zero
wrapper ESP delta, retained EBP/EBX/ESI/EDI, control word 027f, status/TOP 3000 and
two live exact values (1.5 and 1.0), including nested callbacks. Fresh native
x86/x64 assembly checks all nonvolatile GPRs, x64 XMM6..XMM15 and live 80-bit x87
state under control word 077f, on success and a single depth failure per process.
The translated seeded boundary observes MXCSR **3f80 -> 3fa0**, matching the native
precision sticky bit while retaining control bits. General x87 precision/status
limitations remain; guest SIMD instructions remain outside the CPU policy. No
translated FPU claim is inferred solely from the native oracle.

6. Failure containment

A process-wide atomic guard permits at most one native attempt, including nested
and post-success calls. A separate test-only build changes native depth to 71
after the production guard, then invokes actual DXVK once. It returns exact
HRESULT **8876086a**, last-error **203**, NULL output and the native presentation
bytes. The runtime records these values, stops with exit 76, retains both modules
and outstanding resources, and relies on process teardown. No retry occurs.
Fresh native x86/x64 depth-71 processes confirm that result and also retain their
modules until exit. Prior resource-growth characterization remains preserved.
Injected code is absent from the production executable.
Unexpected native QI or parent outputs that acquire an unmodelled reference also
retain backend modules until process exit. Separate test hooks acquire a real
native QI/GetDirect3D reference and force the identity rejection; neither path
unloads code beneath that outstanding reference.

7. Regressions and integrity

All 29 regression stages pass:
the cumulative D3D8 query/mode/enum/display/depth differential, COM,
DirectInput, GUI/window/focus/capture/callback suites, nine commandlet/VM cases,
full UnrealScript compiler acceptance, traced VMProbe, traced hellofull and the full Python suite.
Python reports **158 tests OK, with 17 expected skips**.
The copied historical D3D8 negative probe expects the new NULL-range diagnostic;
all other comparison rules remain exact. Earlier baselines and limitations remain
unchanged. Detailed logs and commands are in `regressions-*.json`.

A system crash interrupted the second compiler acceptance invocation. After the
owner requested resumption, source/generated, both builds, all fixture outputs,
completed regression logs, pinned dependencies and protected assets were verified
again. The entire focused native/translated device corpus was rerun after reboot,
then compiler, traced VM/hellofull and Python acceptance completed afresh. Partial
compiler evidence remains preserved. The native outstanding-reference fixture now
also explicitly retains its modules until process teardown. Recovery evidence is
under `resume-20261025-01/`.
The cause of the system crash remains undetermined. These checks establish
artifact integrity and the measured bridge behavior; hardware stability is not
established by this checkpoint.

All 299 generated game files retain their original hashes. Protected manifest
`3e1807c3c1d3c2881e3353ab46d8f571654e19d10b7ded41b88304c71e172173` covers 4122 files,
3 protected trees and 9
protected files. Compiler/SDK, accepted outputs, DirectMusic helper and pinned
DXVK pairs are verified before and after. No original installation or saves were
accessed. See `final-integrity.json` for the complete historical preservation check.

8. Readiness and smallest next experiment

Production CreateDevice is ready for one separately authorized bounded graphical
continuation, stopping at the next named unsupported device method. This is a
creation/ownership checkpoint, with no rendered frame or genuine game success
claimed. No graphical game execution was performed here.

Static inspection of the unchanged lift predicts the next device calls:
Clear at **D3DDrv.dll+0xf165** (Count=0, rects=NULL, Flags=1, Color=0, Z=0.0,
Stencil=0), then Present at **+0xf17f** with four NULL arguments. These are static
inferences, not newly executed game evidence. The smallest next experiment is
one bounded CreateDevice-to-Clear-stop game capture, followed by an isolated
native x86/x64 and translated fixture characterization of exactly that Clear and
Present sequence. Rendering implementation requires a later phase. No Clear,
Present, SetRenderState or other rendering method was implemented or called.

Primary evidence: `out/recovery/d3d8-create-20261025-01/` and
`experiments/xrt/build/d3d8-create-fixture-20261025-06/`.
