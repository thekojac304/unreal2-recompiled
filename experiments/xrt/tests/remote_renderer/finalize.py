"""Final integrity and delivery. Does not execute the combined candidate."""
import json,re,shutil,struct,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
def main():
    import pefile
    for n in ['contract-audit.json','prepared-batch-audit.json','retained-audit.json','static-coverage.json','candidate-verification.json']:
        assert P.read(P.O/n)['passed'],n
    for c in P.read(P.OLD/'preservation.json')['consumed']:
        assert P.core.sha(P.W/c['executable'])==c['sha256']
        if c.get('pdb_sha256'):assert P.core.sha((P.W/c['executable']).with_suffix('.pdb'))==c['pdb_sha256']
    aliases=[]
    for dll,rva,entries in [('D3DDrv.dll',0x1e3e8,[(0x78,0xe890,'SetRes'),(0x88,0xca30,'UpdateGamma')]),('WinDrv.dll',0xbe10,[(0x88,0x4f20,'ResizeViewport'),(0xb0,0x49b0,'TryRenderDevice')])]:
        pe=pefile.PE(str(P.A.source()/'System'/dll))
        for offset,target,name in entries:
            address=struct.unpack('<I',pe.get_data(rva+offset,4))[0]
            assert address==pe.OPTIONAL_HEADER.ImageBase+target
            aliases.append(dict(module=dll,vtable_rva=hex(rva),offset=hex(offset),target_rva=hex(target),method=name))
    P.save('vtable-resolution.json',dict(passed=True,entries=aliases))
    P.save('development-failures.json',dict(items=[
        dict(kind='environment',artifact='state-fixtures/environment-x86 and environment-x64',
            result='CreateDevice 0x8876086c, last error 203, NULL device in both architectures',
            disposition='graphics comparisons deferred; no state call executed; no environment workaround'),
        dict(kind='fixture setup',artifact='contracts/',result='nested Present used the render-state frame and hit its argument guard first',
            repair='nested test invokes SetRenderState using the valid original frame',passing='contracts-v2/',production_changed=False),
        dict(kind='link setup',artifact='experiments/xrt/build/d3d8-remote-20261029-01/client/',
            result='LNK1104 winmm.lib because shell lacked Visual C++ library environment',
            repair='fresh client-v2 link with standard vcvarsall environment',objects_recompiled=0),
        dict(kind='offline verifier setup',result='first immediate mentioning guest marker was incorrectly selected as PC store',
            repair='verify exact subsequent cmp/jne/PC-store sequence and PE bytes 89 7e 44',integrity_failure=False),
        dict(kind='static coverage classification',artifact='static-coverage-initial.json',
            result='one unmarked LEA ESP,[ESP] at 0x06978309',
            repair='verified unreachable alignment after JMP 0x06978310; all non-padding markers match')],
        strict_failures_not_reclassified=True))
    snapshot=P.O/'development-source';shutil.copytree(P.H,snapshot,ignore=shutil.ignore_patterns('__pycache__'))
    P.save('development-source.json',dict(files=P.core.tree(snapshot),tree_sha256=P.core.digest(P.core.tree(snapshot))))
    P.verify()
    b=P.read(P.O/'build.json');v=P.read(P.O/'candidate-verification.json');plan=P.read(P.O/'initialization-plan.json')
    coverage=P.read(P.O/'static-coverage.json');old=P.read(P.OLD/'build.json')
    statechecks=[json.loads((P.O/'contracts-v2'/('run-'+a+'.stdout.txt')).read_text())['checks']for a in ['x86','x64']]
    P.save('readiness.json',dict(passed=True,remote_development_complete=True,
        new_operations_enabled=[],inherited_operations=b['qualified_operations'],
        native_graphics_148_1='DEFERRED: CreateDevice failed before target call',
        translated_graphics_148_1='DEFERRED: no valid native reference; guard retained',
        prepared_candidate=str(Path(b['root'])/'xrt_ucc.exe'),candidate=v,
        game_qualified=False,supervisor_qualified=False,execution_authorized=False,
        physical_desktop_testing_required=True,genuine_launches=0,genuine_requests=0))
    report=f'''Unreal II: remote renderer development completed within the RDP boundary
2026-10-29. Workspace E:\\Unreal2-Port-Investigation

Result
No genuine game was launched or queued. No session, RDP, console, display,
supervisor policy, authorization or breakpoint change was made. No original
installation/save was modified. The prepared material package and both consumed
candidates remain unchanged. No remote push or release occurred.

The RDP graphics limitation prevented a new native behavior qualification.
No new renderer operation is enabled. A fresh combined candidate incorporates
the independently qualified SetMaterial bridge and the existing eight states,
Clear and Present. It is unexecuted, unconsumed, not game-qualified, and not
qualified for the existing supervisor. Its semantics equal the preserved material
candidate. Freshness alone is not evidence of additional renderer progress.

Implemented/validated operations retained in the combined source
- Typed IDirect3D8 CreateDevice, guest device identity and measured ownership.
- Bounded Clear and Present with four NULL parameters.
- SetRenderState exactly (7,1),(9,2),(29,0),(26,1),(143,1),(48,0),(35,3),(136,1).
- SetMaterial, slot 42, exact 68-byte tuple, copied from readable guest memory.
The existing native measurements and translated callback/ABI/input/lifetime
evidence were rechecked on copies. There was no fresh graphics validation here.

Exact identities
Fresh combined EXE: {Path(b['root'])/'xrt_ucc.exe'}
EXE SHA-256: {v['pe_sha256']}
PDB SHA-256: {v['pdb_sha256']}
RSDS GUID: {v['rsds_guid']}; age {v['pdb_age']}.
Runtime source: {P.RT}
Canonical runtime file-map SHA-256: {v['runtime_tree_sha256']}
Canonical generated file-map SHA-256: {v['generated_tree_sha256']}
Build record: {P.O/'build.json'}
279 objects reused after byte/hash/source/header/link verification; zero compiled.
The original per-object strict-FP compile commands are retained in object-lineage.json.
Inherited build: {P.OLD/'build.json'}
Inherited build SHA-256: {P.core.sha(P.OLD/'build.json')}
Original compile-lineage SHA-256: {v['original_compile_lineage_sha256']}
Development sources: development-source/ and development-source.json.

Preserved material-only EXE SHA-256: {old['binary_sha256']}
Preserved material PDB SHA-256: {old['pdb_sha256']}
Preserved package: {P.OLD}
Its exact source, 265 generated-object reuse / 14 runtime-object compile lineage,
qualification preview and owner authorization history were not edited.
Consumed identities remain denied:
  5a9e2272d3566d72ea05b909e686e6fda5f8c76dec2b72afd6d4e5dd640b9e9c
  f1e79397aa98c133a6a25f382efca3177e0ef076aae75ca35a521a933b160e85

Complete remaining SetRes sequence (original PE + generated source)
1. SetMaterial: guest 0x0696f31d, slot 42; return 0x0696f323.
2. SetRenderState(148,1): 0x0696f336; (145,0): 0x0696f350. Both guarded.
3. Per-stage SetTextureStageState, slot 63, at 0x0696f3ac, f3d0, f3e6,
   f418, f42e; types 19,16,17,18,21. Stage bound renderer[0x41c8].
   Values depend on LOD bias, anisotropy and filtering configuration.
4. Viewport ResizeViewport: 0x0696f48d, viewport vtable+0x88. Flags include
   0x10 | bool(fullscreen), width/height. Success must return nonzero.
   Native window/default-procedure effects require physical-desktop validation.
5. Cache constructor: 0x0696f4bd -> 0x06977800, returns 0x069783fe (ret 4).
   38 ordered SetRenderState sites; only the final (29,0) and (9,2) are already
   admitted. The full tuple table, conditional state 52 and call contexts are
   in initialization-plan.json. Do not enable a whole state/value domain.
6. Cache transform batch: SetTransform slot 37, 11 Core FMatrix::Identity
   matrices (64 bytes each), types 2,3,16..23,256.
7. Cache stage batch: 15 SetTextureStageState sites per stage, types
   1,2,3,4,5,6,11,13,14,24,25,19,26,27,28; plus NULL SetTexture (slot 61).
   Address-mode inputs come from renderer[0x4650]. The cache's type-19 value
   passes through _ftol(renderer float[0x412c]); the earlier sampler loop sends
   the raw DWORD. These are separate contracts and must not be conflated.
8. SetVertexShader/FVF 2 (slot 76); NULL SetStreamSource/stride 0 (slot 83,
   streams below min(renderer[0x41f0],16)); NULL SetIndices/base 0 (slot 85).
   Cache copies/zeroes remain guest work and do not justify a GPU success stub.
9. UpdateGamma at 0x0696f4ce (renderer vtable+0x88 -> D3DDrv RVA 0xca30).
   If renderer[0x4140] has 0x20000 and the device exists, SetGammaRamp slot 18
   executes at 0x0696cb68 with flags 1 and a computed 1536-byte ramp; void result.
10. SetRes success returns EAX=1, ret 20 at 0x0696f4e9.

All {coverage['total_verified']} non-padding instruction addresses across the remaining
SetRes, complete cache, gamma, ResizeViewport, TryRenderDevice, OpenWindow,
UEngine::Init and UGameEngine::Init correspond to hash-pinned generated markers.
Original branches, failure paths, call contexts and imports are preserved in
the *.asm.txt and matching JSON files. The earlier short cache disassembly is
superseded by state-cache-complete.*. Vtable ownership was checked against the
original PE tables in vtable-resolution.json.

Remaining unsupported initialization calls
SetRenderState new tuples; SetTextureStageState; SetTransform; SetTexture;
SetVertexShader; SetStreamSource; SetIndices; conditional SetGammaRamp.
88 other device slots retain explicit unsupported guards; native readback
queries in fixtures do not create production GetRenderState/GetMaterial support.

Fresh tests completed
- Adapter source compiled and executed in native x86/x64 non-graphical harnesses:
  {statechecks[0]} + {statechecks[1]} checks. Exact supported tuples, HRESULT/error propagation,
  guest CPU/frame preservation, readonly/cross-page material inputs, unknown
  identities, all 88 slot traps, reentrancy/final Release and ownership checked.
  Host COM/GUI services are explicit test doubles; no Windows callback or DXVK
  rendering qualification is claimed by these tests.
- Prepared native states/samplers/transforms/null-bindings batches compiled x86/x64.
  Only their --abi-only self-tests ran: 24 calls total, 2/3/4 native arguments,
  stdcall stack, integer nonvolatiles, x64 XMM6..15, seeded x87 control/status/TOP/
  two live values, MXCSR, four last-error seeds and return values pass.
- Historical material audit replay: 12 native processes / 48 calls and 35
  native/translated fixture processes, including memory/identity/callback/
  ownership/rejection evidence. These are retained evidence, not fresh GPU runs.
- Complete original/generated static correspondence and vtable resolution pass.
- 279 source/object records and exact link inputs, PE/PDB identity, unconsumed
  candidate identity and full preservation/protected-input integrity pass.

Deferred tests and current environment
Session {P.read(P.O/'preservation.json')['session_id']}; SM_REMOTESESSION true.
Both pinned DXVK x86/x64 fixtures loaded the expected pair and enumerated the
NVIDIA GeForce RTX 5090. Exact CreateDevice returned 0x8876086c
(D3DERR_INVALIDCALL), last-error 203, device NULL in both processes. Neither
reached a target SetRenderState. The error's deeper cause is not established;
this does not prove a driver defect or a general RDP incompatibility.
No session/display/backend workaround, visible-window retry, alternate device
tuple or forced graphical pass was attempted. Logs and exact failed fixtures
are retained under state-fixtures/environment-x86 and environment-x64.
Fresh native/translated graphics, rendered output, actual Windows callbacks,
gamma, genuine SetRes return and outer Engine initialization remain deferred.

STRICT X87: FAILED. COMPLETE WNDPROC EQUALITY: FAILED.
STRICT NATIVE X86 COMPATIBILITY: FAILED. These remain separate, unwaived and
preserved in the original strict-failure records. Focused ABI tests do not repair
or reclassify them. No general x87 rewrite was attempted.

Ordered development batches toward the outer initialization milestones
A. On physical access, establish the unchanged native graphics fixture first.
   Measure (148,1) and (145,0), transition + all-state readbacks, repeated calls,
   four errors seeds, native x86/x64 ABI/FPU and cleanup. Only then extend exact
   allowlists in a fresh runtime and compare a translated disposable fixture.
B. Measure/implement the five sampler settings over the actual caps/configuration
   bounds as one group. Use strict per-stage/type/value guards and focused
   Clear/Present/eight-state/material/identity/reentrancy regressions afterward.
C. Validate ResizeViewport's exact flag/window callback path. Keep existing
   WNDPROC failures distinct and do not synthesize a successful resize.
D. Measure the 38 cache states in sensible scalar groups (depth/blend/alpha,
   stencil/fog, lighting/material sources). Exact new pairs only. Regress each.
E. Measure/bridge identity SetTransform as a pointer/layout group with all 64
   readable bytes copied before native entry. Validate each transform ID and
   preserve guest x87 and native control/nonvolatile state.
F. Measure cache stage settings plus NULL texture/FVF/stream/index bindings as
   related initialization batches. Keep typed resource identities, NULL semantics,
   readback, ownership and unsupported non-NULL object guards separate.
G. Characterize conditional gamma with an owned/restoring physical fixture,
   computed input bytes and void ABI. Do not widen floating-point compatibility.
H. After independent groups/regressions pass, make a NEW combined candidate and
   separately review/qualify an authorized bounded observer endpoint. No such
   endpoint or authorization change was made in this task.
I. Prove SetRes return, then its caller at WinDrv 0x11104bf8 and successful
   TryRenderDevice exit (ret 16 at 0x11104cbe), retaining the real renderer pointer
   and any conditional level-detail callback. Prove OpenWindow's frame/focus/
   gamma follow-through and ret 24 at 0x11103848. It invokes TryRenderDevice via
   viewport vtable+0xb0, not a D3D8 device slot.
J. Prove UGameEngine::Init completion (normal ret 0x1038fba9), including its
   UEngine::Init call, viewport/input/audio and map-load work after OpenWindow.
   Engine Init, selected-world tick and gameplay are not established by SetRes.

Smallest owner-desktop test when home
1. Run the already built native single-state fixture for (148,1), x86 and x64,
   using the same pinned DXVK pair, exact tuple and disposable hidden windows.
   Stop on CreateDevice failure. No game is needed for this check.
2. If valid, use prepared-batches/*/oracle.exe with the states group to collect
   the post-material/cache scalar measurements in two disposable processes.
   Compare readbacks, four error seeds, ABI/FPU and cleanup before implementation.
   Sampler/binding batches are compiled preparation and need their own readback
   audit/translated comparisons; they are not already graphics-qualified.
3. For the smallest genuine milestone, review the PRESERVED material candidate
   and its already prepared preview, then separately authorize exactly one
   bounded physical-desktop attempt stopping before guest 0x0696f323. Audit the
   SetMaterial return, zero-drop evidence and cleanup. Existing authorization
   and unused capacity are not reused. Do not execute the fresh relink under an
   old seal or advance any endpoint without separate review/qualification.

The fresh relink's offline 0x0696f323 PC-store marker is RVA
{v['offline_marker']['rva']}, bytes {v['offline_marker']['bytes']}. This is documentation;
the production permanent endpoint remains before guest 0x0696f292.

Routine fixture/link/parser repairs and all failed setup artifacts are retained
in development-failures.json. Final preserved-tree/protected-input verification:
final-integrity.json. No required owner decision was needed for this remote work.
'''
    (P.O/'REPORT.txt').write_text(report,encoding='utf-8')
    # The inventory excludes itself; subsequent delivery must not mutate these files.
    P.save('delivery-inventory.json',dict(files=P.core.tree(P.O),candidate_files=b['outputs'],
        report_sha256=P.core.sha(P.O/'REPORT.txt'),genuine_launches=0))
    print('REMOTE REPORT',P.O/'REPORT.txt',flush=True)
if __name__=='__main__':main()
