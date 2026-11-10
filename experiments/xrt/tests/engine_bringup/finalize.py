"""Seal a substantial non-game milestone; no launch or policy mutation."""
import sys,re,uuid,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    build=read(O/'build.json');exe,sha,pdb=identity();runtime=core.tree(RT)
    assert runtime==build['runtime']
    assert core.tree(Path(build['root']))==build['outputs']
    for name in ('contracts','regressions','gpu-qualification-package'):
        assert read(O/(name+'.json'))['runtime']==runtime
    for name in ('candidate-identity','static-audit','linked-adapters','stop-mapping','debugger-validation','preservation-after','setres-independent-audit'):
        result=read(O/(name+'.json'))
        # Independent identity verifier uses verified rather than passed.
        assert result.get('passed',result.get('verified',False)),(name,result.keys())
    package=read(O/'gpu-qualification-package.json')
    for candidate in package['candidates']:
        manifest=Path(candidate['manifest']);assert core.sha(manifest)==candidate['manifest_sha256']
        for path,digest in read(manifest)['files'].items():assert core.sha(path)==digest,path
    tests=O/('evidence-tests-'+str(uuid.uuid4()));tests.mkdir()
    proc=subprocess.run([sys.executable,'-B','-I',str(H/'test_evidence.py'),'-v'],capture_output=True,timeout=30)
    (tests/'stdout.bin').write_bytes(proc.stdout);(tests/'stderr.bin').write_bytes(proc.stderr)
    assert proc.returncode==0
    save(O/'evidence-tests.json',dict(passed=True,tests=6,mutation_cases=14,missing_duplicate_cases=2,
        root=str(tests),scope='synthetic parser tests; no physical acceptance'))
    unsupported=[dict(slot=int(n),name=name) for n,name in re.findall(
        r'unsupported slot (\d+) (\w+)',(RT/'d3d8_device_slots.inc').read_text())]
    save(O/'remaining-unsupported.json',dict(device_methods=unsupported,
        resource_bindings='Non-NULL textures, streams and indices require a typed resource registry; existing guards retained.',
        shaders='Programmable shader handles remain unsupported; UP scope is safely representable FVF input.',
        first_lock_dependencies=[dict(site='0x0696FBCC',slot=32,name='GetRenderTarget'),dict(site='0x0696FBFB',slot=33,name='GetDepthStencilSurface')],
        windows_conditional=['PostMessageA/W in UpdateWindowFrame','SetWindowLongA/W in OpenWindow/ResizeViewport','SetMenu in ResizeViewport'],
        reset='Device-loss SetRes/Reset recovery is not implemented; one-attempt guard retained.'))
    mapping=read(O/'stop-mapping.json')
    save(O/'continuation-design.json',dict(prepared=True,execution_authorized=False,genuine_launches=0,
        candidate=str(exe),sha256=sha,pdb_sha256=pdb,guest_stop=GUEST,stop_rva=mapping['stop_rva'],stop_bytes=mapping['stop_bytes'],
        boundary='UGameEngine::Init checked return; before guest CALL at 0x1090ED5C; no main-loop tick admitted',
        observer_installed=False,production_policy_changed=False,
        raw_capture=['Synchronous existing runtime event stream before assertions','Full 416-byte CPU and guest frame at permanent endpoint',
            'Owned HWND/renderer/device/selected-world identities from read-only debugger memory','Four D3D semantic checkpoints and lifecycle entries',
            'Exact native module and candidate PE/PDB hashes'],
        milestones=['TryRenderDevice paired return','OpenWindow paired return','UGameEngine::Init paired return',
            'Engine/selected-world tick attempts and paired returns recorded but outside this main-loop bound','Scene API attempts and native results; never infer pixels from success'],
        prior_base_engine_init='UEngine::Init precedes initial SetRes; no false post-SetRes milestone',
        permanent_hardware=True,maximum_slots=4,watchdog_seconds=60,retry=False,
        integration_requirements=['Integrate separately reviewed read-only observer without changing active supervisor authorization or breakpoint policy',
            'Require live DR readback on every thread and terminate while stopped on mismatch',
            'Reconcile legacy XRT_STOP_VIEWPORT_INIT early-stop configuration under separate continuation review; this task did not alter it',
            'Resolve conditional Windows/resource blockers as required by actual path; retain fatal stops for unknown pointer APIs',
            'Complete physical fixture/module/desktop/Job acceptance and preserve strict failed verdicts',
            'Obtain separate owner authorization for this exact fresh candidate only']))
    contracts=read(O/'contracts.json');audit=read(O/'setres-independent-audit.json')
    report=f"""UNREAL II ENGINE BRING-UP -- NON-GAME IMPLEMENTATION MILESTONE
2026-10-30. Genuine launches in this work: ZERO.

Completed: DirectInput lifecycle, scene boundaries, viewport marshalling and
copied UP draw operations. Built, tested and linked in an isolated experimental
runtime. This is a substantial subsystem milestone, not visible gameplay or
formal physical GPU acceptance. No production runtime or supervisor changes.

1. INDEPENDENT INITIAL SETRES AUDIT
Source: {EVIDENCE}
Consumed candidate c99072118b849d9aeef71e0389ea2e0b8bf86c35709f01fa61cab79d6bbec63c
was inspected only, never retried. Paired 250 native operations against four
debugger checkpoints each, native HRESULT/last-error and ABI observations.
Raw 416-byte entry/return CPUs match runtime chunks. EAX=1, ESP=0x0120D418
(entry+24), rv=0x11104BF8; integer nonvolatiles preserved.
Viewport: {audit['viewport']}. Object/identity checks all pass.
Permanent stop was hit before its instruction executed. Job cleanup left zero
processes, kill-on-close enabled. Original display gamma byte equality verified.
This was forced process teardown, not normal guest COM/resource cleanup.
Initialization Clear/Present is not a game scene, selected-world tick or gameplay.
See setres-independent-audit.json and historical-milestones/milestones.json.

2. IMPLEMENTED COMPATIBILITY
DirectInput Acquire, Unacquire and SetCooperativeLevel use real typed COM calls,
actual HRESULT/last-error, full readable frames and existing object identities.
Non-NULL HWNDs must be owned, same-thread, live top-level windows. Pins survive
failed association changes and transfer only on success; final Release/cleanup
unpins. Callback scopes and reentrant-operation guards remain. Invalid known
scalar combinations reach native DirectInput; unknown flags remain unsupported.

D3D8 TestCooperativeLevel, BeginScene, EndScene, SetViewport, GetViewport,
DrawPrimitiveUP and DrawIndexedPrimitiveUP are bound in the candidate.
Viewport is a copied 24-byte structure; getter preserves actual native output
including partial failure writes. Safe bounds/scalars remain native decisions.
UP drawing validates topology/count arithmetic, native caps, FVF/stride, complete
page protections and index range. Native code receives private host copies,
never guest pointers. Indexed16/32 with nonzero minimum is covered.
64 MiB staging capacity per block is explicit. Buffer/shader/resource guards remain.
No fabricated S_OK, scene state or successful rendering.

3. STATIC OUTER INIT / FIRST-FRAME FINDINGS
Thirteen original PE function ranges are paired with unchanged generated source,
with zero missing instruction markers after explicit data/alignment exclusions.
UEngine::Init at 0x10384010 is called at 0x1038F4C7 BEFORE initial SetRes.
OpenWindow tail includes DirectInput cooperative setup, renderer UpdateGamma,
UpdateWindowFrame and SetActiveWindow; return 0x11103848 RET 24.
UGameEngine::Init OpenWindow call returns at 0x1038FB1C, followed by detail mode,
InitAudio and audio viewport association, then return 0x1038FBA9.
InitAudio has a -nosound gate; it does not erase earlier genuine DirectMusic work.
Conditional missing PostMessageA/W, SetWindowLongA/W and SetMenu remain guarded.
TryRenderDevice returns with RET 16. These are static findings, not newly observed
genuine execution.

First Lock at 0x0696D260 checks cooperative state and invokes BeginScene.
Its helper immediately needs GetRenderTarget at 0x0696FBCC and
GetDepthStencilSurface at 0x0696FBFB, both still unsupported.
Texture creation/upload/mips, surfaces, vertex/index buffers, non-NULL bindings,
buffer-backed DrawPrimitive/DrawIndexedPrimitive and programmable shaders remain
unimplemented. Resource ownership is the next coherent subsystem. No first-frame
or completed engine-init claim is made. See remaining-unsupported.json.

4. EXECUTED NON-GPU VALIDATION
x86 and x64: existing renderer suite 13,805 checks, 373 cases, 19 negatives,
195 generated cache calls, 16 creation preflights and four CreateDevice cases.
New scene tests: 40 positive / 17 negative cases; cumulative 14,216 checks
per architecture. Covers full CPU/stack, HRESULT/last-error, copied memory,
read-only inputs, fault boundaries, FVF/caps/stride/index failures and reentry.
Getter output protection is rechecked after native callbacks; the fixture
changes protection during the native call and verifies a safe stop before copy.
DirectInput doubles: 46 positive / six negative / 349 checks per architecture.
Real system DirectInput: 14 sequential lifecycle samples per architecture with
hidden owned windows and nonexclusive input. Exact inner-native result transfer
passes. Independent Acquire invocation sample 7 differs in last-error (0 vs 5)
on BOTH architectures, HRESULT 0. This remains a strict equality FAILURE;
it was not normalized. Cross-architecture raw sample comparison is equal.
81 unchanged supervisor tests and 105 renderer collector tests pass.
Registered GUI fixture: two positives / ten guard cases pass.
Six offline evidence tests include 14 mutation and two missing/duplicate cases.
Milestone pairing on historical evidence finds consistent events and correctly
does not claim Init completion or a tick.

5. FRESH UNEXECUTED CANDIDATE AND CONTAINMENT
EXE: {exe}
SHA256: {sha}
PDB SHA256: {pdb}
One new hle_misc.obj compilation (actual D3D and DirectInput owner), 278 verified
unchanged objects reused; all 279 have independent source/object lineage.
Full runtime/header closure, compiler/linker identity, PE/PDB GUID/age, ten new
HLE bindings and nonconsumption verified. Candidate instructions executed: ZERO.
Exact proposed next stop: guest 0x1090ED5C, host RVA 0x{mapping['stop_rva']:X},
bytes {mapping['stop_bytes']}, before MOV [RDI+44h],EBX after checked Init return.
The next guest CALL has not executed. Main-loop tick is outside this bound.
Five non-game debugger cases pass: owned stop, four-slot limit, overflow refusal,
observer failure and wrong-byte refusal. Main/new-thread live DR readback,
termination-before-continue and Job cleanup verified. Candidate mapped with
SEC_IMAGE_NO_EXECUTE only. Retained observer factory tests also pass.
This does NOT test a live genuine Init endpoint or install an observer.

6. CONSOLIDATED PHYSICAL GPU PACKAGE -- PREPARED, NOT RUN
Three immutable fixture candidates compiled successfully:
  x86 native     {package['candidates'][0]['candidate_id']}
  x64 native     {package['candidates'][1]['candidate_id']}
  x64 translated {package['candidates'][2]['candidate_id']}
They cover viewport round trip, scene ordering/duplicate errors, three real
triangle draw modes (UP, indexed16, indexed32), stream/index unbinding, lockable
800x600 backbuffer readback, non-clear pixel count/RGB hash, Present and cleanup.
Raw outer-wrapper ABI/FPU and full guest CPU are captured. Typed inner-native
calls are tested by contracts; these raw physical measurements are explicitly
outer-wrapper ABI, not independent inner-call register capture.
gpu_evidence.py compares saved outputs and rejects missing/mismatching results.
It never grants physical acceptance or overrides the existing collector.
Later qualification must retain process/desktop/session/GPU/backend/module
identity, watchdog/Job and historical collector errors. Old parser failures for
new records must remain evidence; new supplementary analysis is additive.
The stopped GPU fixture services were not started and no fixture was submitted.

7. BOUNDARY AND REMAINING ACTIONS
Stopping at this coherent, compiled and non-game-qualified milestone is allowed
by the requested scope. Full resource rendering exceeds this milestone.
Physical rendering requires owner startup of existing fixture services and
execution/acceptance of the three prepared fixtures. Genuine continuation also
requires separate observer integration/review and explicit owner authorization
for the exact candidate above. This task does not request or imply that grant.
continuation-design.json records milestone capture, permanent stop, four-slot
budget, watchdog, no-retry and integration requirements. Existing early-stop
configuration has not been silently changed. Init return itself remains
unqualified, and the missing resource/conditional Windows paths still stop.

8. PRESERVATION / STRICT STATUS
Original installation/saves verification and exact prior runtime/evidence,
production runtime, generated source and supervisor trees all pass preservation.
Historical x87, WNDPROC and strict native-x86 FAILED verdicts remain FAILED.
No game, owner authorization, supervisor policy, remote push or release occurred.
No memory/COM/filesystem protection was weakened.

Reproduction entry points live in experiments/xrt/tests/engine_bringup/README.md.
Receipts and failures are retained alongside this report; milestone.json seals
the implementation, current candidate and accepted non-game evidence.
"""
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    receipts=['build','object-lineage','candidate-identity','source-change','contracts','regressions','setres-independent-audit',
        'static-audit','linked-adapters','stop-mapping','debugger-validation','gpu-qualification-package','continuation-design',
        'remaining-unsupported','preservation','preservation-after','evidence-tests']
    save(O/'milestone.json',dict(completed='DirectInput lifecycle + scenes/viewports + safely copied UP draws',
        status='NON-GAME MILESTONE COMPLETE; PHYSICAL GPU AND GENUINE CONTINUATION NOT QUALIFIED',
        candidate_sha256=sha,genuine_launches=0,execution_authorized=False,physical_gpu_executed=False,
        historical_strict_status='FAILED unchanged',directinput_independent_strict_equal=contracts['strict_native_equality'],
        runtime=runtime,implementation=core.tree(H),report_sha256=core.sha(O/'REPORT.txt'),
        evidence={name+'.json':core.sha(O/(name+'.json')) for name in receipts}))
    print('Milestone sealed:',sha,flush=True)

if __name__=='__main__':main()
