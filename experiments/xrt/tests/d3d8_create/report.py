"""Produce the reviewable production checkpoint after every acceptance gate."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import preserve as P
W,O,F=P.W,P.O,P.F;B=W/'experiments/xrt/build/d3d8-create-20261025-02';T=W/'experiments/xrt/build/d3d8-create-fixture-20261025-06'
def main():
    b=F.read(O/'build-02.json');m=F.read(O/'measurement-02.json');assert b['status']=='PASS' and m['passed']
    regressions={k:F.read(O/f'regressions-{k}-02.json')for k in ['affected','d3d8','acceptance']};assert all(r['passed']for r in regressions.values())
    assert all(P.tree(W/p)==h for p,h in b['sources'].items())
    F.P.check(B,b['outputs']);before=F.read(O/'preflight.json')
    binary=(B/'xrt_ucc.exe').read_bytes()
    assert not any(s in binary for s in [b'XRT_CREATE_TEST',b'test_backend_injection',b'test_mutation_injection',b'FixtureCreateDevice'])
    python_log=(O/'regression-python-02.log').read_text(errors='replace')
    python_count=int(re.search(r'Ran (\d+) tests',python_log)[1]);assert 'OK (skipped=17)'in python_log
    outputs={}
    for root in [B,W/'experiments/xrt/build/d3d8-create-20261025-01',*sorted((W/'experiments/xrt/build').glob('d3d8-create-fixture-20261025-*')),
                 W/'sandbox_d3d8_create_20261025_01/experiments/xrt/build',W/'sandbox_d3d8_create_20261025_02/experiments/xrt/build']:
        for p in root.rglob('*'):
            if p.is_file()and p.suffix in ['.exe','.dll','.obj','.pdb','.ilk']:outputs[p.relative_to(W).as_posix()]=P.sha(p)
    artifacts=dict(outputs=outputs,production_sources=P.tree(W/'experiments/xrt/runtime'),fixture_sources=P.tree(W/'experiments/xrt/tests/d3d8_create'),generated=b['sources']['experiments/xrt/gen'],
        binary_sha256=b['binary_sha256'],test_injection_absent_from_production=True,backends={a:{n:P.sha(F.P.G.verified_pair(a)/n)for n in F.P.G.HASHES[a]}for a in ['x86','x64']})
    P.save('artifact-identities.json',artifacts)
    text=f'''# Guarded production D3D8 CreateDevice bridge

2026-10-25, US Eastern. **Ready for one separately authorized, bounded game test
that stops at the next unsupported method.** This phase ran zero genuine graphical
clients and implemented no rendering method. General creation and retries remain
unsupported. Final integrity is recorded in the linked evidence below.

1. Binary and preserved checkpoint

New executable: `experiments/xrt/build/d3d8-create-20261025-02/xrt_ucc.exe`.
SHA-256: `{b['binary_sha256']}`.
The first fresh build compiled all 279 objects serially, with zero warnings.
The final ownership-containment tightening rebuilt all {b['compiled_objects']} runtime
objects serially in a second fresh directory, reusing {b['reused_objects']} hash-verified
generated objects from that full build. Generated inputs and their headers are
unchanged. Both builds are preserved. The build records commands, source hashes, object
hashes, PDB hashes, logs and warnings in
`out/recovery/d3d8-create-20261025-01/build.json` and `build-02.json`. All phase executables, objects,
PDBs and runtime/fixture sources are identified in `artifact-identities.json`.

HEAD remains `{before['head']}`. The accepted depth executable remains unchanged,
SHA-256 `{before['accepted_sha256']}`. The preflight preserved {len(before['working'])}
working files, the staged/unstaged binary patches, {len(before['builds'])} historical
build files and {len(before['raw'])} raw evidence files. Existing pending work was
retained; only the D3D8 bridge, GUI scope/window pins and host-only declarations
were changed in existing runtime sources. No commit, push or release was made.

2. Real native and translated creation

Native x86, native x64 and the production translated PE32 fixture all return
actual **S_OK (0), last-error 0 and a non-null owned device** for Adapter 0,
DeviceType 1, BehaviorFlags 0x42 and the exact captured 1540x945 / format 22 /
count 1 / multisample 0 / swap 1 / windowed 1 / auto-depth 1 / depth 77 /
flags 1 / refresh 0 / interval 0 tuple. Seeds 0, 18, 0x13572468 and 0xffffffff
all return native last-error 0. No HRESULT or successful pointer is synthesized.
The final corpus contains {m['native_processes']} native processes,
{m['translated_processes']} translated processes and {m['translated_successful_creations']}
successful translated devices, each in its own process. The common ownership
corpus compares {m['compared_values']} values exactly across all three architectures;
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

All {sum(len(r['runs'])for r in regressions.values())} regression stages pass:
the cumulative D3D8 query/mode/enum/display/depth differential, COM,
DirectInput, GUI/window/focus/capture/callback suites, nine commandlet/VM cases,
full UnrealScript compiler acceptance, traced VMProbe, traced hellofull and the full Python suite.
Python reports **{python_count} tests OK, with 17 expected skips**.
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
`{before['assets']['manifest_sha256']}` covers {before['assets']['files']} files,
{before['assets']['protected_trees']} protected trees and {before['assets']['protected_files']}
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
'''
    (W/'experiments/xrt/D3D8_CREATE_BRIDGE.md').write_text(text)
    status=W/'experiments/xrt/CURRENT_STATUS.md'
    original=(O/'source-preservation/experiments/xrt/CURRENT_STATUS.md').read_bytes()
    prefix='# Production CreateDevice bridge validated; graphical execution not run\n\n2026-10-25, US Eastern. Exact captured CreateDevice tuple creates real DXVK devices through\nthe production typed bridge. Ownership, parent revival, guest/window marshalling, callback,\nABI/FPU, single-attempt failure containment and affected regressions pass. All rendering slots\nremain diagnostic traps. Ready for one separately authorized bounded game test; none ran here.\n\nExecutable SHA-256: `'+b['binary_sha256']+'`.\n[Full checkpoint](D3D8_CREATE_BRIDGE.md). Earlier pending work and evidence are preserved.\n\n---\n\n'
    status.write_bytes(prefix.encode()+original);assert status.read_bytes().endswith(original)
    result=dict(passed=True,binary=str(B/'xrt_ucc.exe'),binary_sha256=b['binary_sha256'],measurement=m,regressions=regressions,
        artifact_manifest=str(O/'artifact-identities.json'),genuine_graphical_clients=0,rendering_methods_implemented=[],original_installation_or_saves_accessed=False,
        ready_for_one_bounded_game_test=True,next_static_boundary=dict(method='Clear',callsite='D3DDrv.dll+0xf165',arguments=[0,0,1,0,0,0],then='Present at +0xf17f (four NULL arguments)'))
    P.save('acceptance.json',result)
    (W/'experiments/xrt/results/compare/d3d8_create_bridge.json').write_text(json.dumps(result,indent=2))
    print('REPORT WRITTEN',b['binary_sha256'],flush=True)
if __name__=='__main__':main()
