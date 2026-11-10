"""Seal development evidence and a single deferred physical batch. No launcher."""
import sys,re,subprocess,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from supervisor import fixture_profiles as F
def main():
    runtime=core.tree(RT)
    receipts={n:read(O/(n+'.json')) for n in ('contracts','windows-contracts','regressions','build','candidate-identity','linked-adapters','stop-mapping','debugger-validation','static-audit','initialization-path','setres-independent-audit','preservation-after')}
    assert all(r['passed'] for r in receipts.values())
    for n in ('contracts','windows-contracts','regressions','build'):assert receipts[n]['runtime']==runtime
    assert receipts['linked-adapters']['source']==runtime and len(receipts['linked-adapters']['bindings'])==60
    exe,sha,pdb=identity();assert core.sha(exe)==sha==receipts['candidate-identity']['sha256']
    package=read(O/'gpu-qualification-package.json');assert package['runtime']==runtime and not package['executed']
    prepared=[]
    for row in package['candidates']:
        c=F.validate_candidate(dict(candidate_id=row['candidate_id'],candidate_sha256=row['manifest_sha256'],family='renderer-group',parameters=row['parameters'],profile='fast-development'))
        F.verify_identities(row['adapter_sources']);plan=F.plan(c['family'],c['parameters'],F.candidate_path(c['id']).parent)
        prepared.append(dict(candidate_id=c['id'],parameters=c['parameters'],manifest=row['manifest'],manifest_sha256=row['manifest_sha256'],executable=str(plan[0]['exe']),sha256=core.sha(plan[0]['exe']),verified=True))
    assert len(prepared)==3
    unitroot=O/('evidence-tests-'+str(uuid.uuid4()));unitroot.mkdir();tests=[]
    for script in (H/'test_evidence.py',H/'test_observer.py',H.parent/'resource_frame/test_evidence.py'):
        p=subprocess.run([sys.executable,'-B','-I',str(script),'-v'],cwd=W,capture_output=True,timeout=30)
        name=script.parent.name+'-'+script.stem;(unitroot/(name+'.stdout.txt')).write_bytes(p.stdout);(unitroot/(name+'.stderr.txt')).write_bytes(p.stderr)
        assert p.returncode==0,p.stderr
        tests.append(dict(script=str(script),sha256=core.sha(script),tests=int(re.search(rb'Ran (\d+) tests',p.stderr)[1]),passed=True))
    save(O/'evidence-tests.json',dict(passed=True,root=str(unitroot),tests=tests,synthetic_only=True))
    unsupported=read(PRIOR/'remaining-unsupported.json')
    unsupported['device_methods']=[r for r in unsupported['device_methods'] if r['slot'] not in (16,25,26,27,28,30)]
    unsupported['resources']='Cube/volume textures and resource private-data methods remain unsupported. Surface creation/copy/readback now implemented; physical acceptance pending.'
    unsupported['conditional_windows']=dict(implemented=['SetWindowLongA/W style and exstyle with mutable STYLECHANGING/read-only STYLECHANGED','SetMenu(NULL)','PostMessageA/W WM_COMMAND and zero-payload WM_NULL/WM_CLOSE to owned same-thread HWNDs'],guarded=['Window procedure/userdata/extra/pointer-valued SetWindowLong fields','non-NULL menus','thread/broadcast/foreign HWNDs and asynchronous pointer payloads'])
    unsupported['surface_capacities']='16384 per dimension and 16M pixels per created surface; 256 CopyRects rectangles; inherited map/memory/resource capacities retained.'
    unsupported['physical']='All GPU operations in this extension remain physically unqualified. GetFrontBuffer physical fixture tests only NULL-destination error; successful front capture remains unqualified.'
    save(O/'remaining-unsupported.json',unsupported)
    save(O/'physical-batch.json',dict(prepared=True,executed=False,submitted=False,candidates=prepared,
        scope=['retained texture/mip/VB/IB/FVF/declaration/scene/readback/Present matrix','backbuffer identity and native refs','custom render target/depth/image surface ownership','target switch, Clear and restore viewport','whole and rectangle surface copies, exact copied pixels','GetFrontBuffer(NULL) native failure; no desktop capture','ABI and cleanup'],
        compare_command=[str(W/'.venv/Scripts/python.exe'),'-B','-I',str(H/'gpu_evidence.py'),'<native-x86-stdout>','<native-x64-stdout>','<translated-x64-stdout>'],
        conditions=['Use existing owner-authorized physical fixture collector for exactly these three immutable candidates.','Preserve strict collector failures, module/desktop/process/Job evidence and raw outputs.','No service startup, authorization, queueing or remote-console mechanism is supplied here.','No genuine game execution is part of this batch.'],
        formal_physical_acceptance=False,supervisor_authorization_changed=False))
    proof=W/'out/recovery/remote-console-proof-20261030-01';startup=W/'out/recovery/remote-fixture-startup-20261030-01'
    save(O/'closed-console-proof.json',dict(status='closed unsuccessful by owner: Computer Use application-identity mismatch',retry=False,workaround=False,startup_investigation_resumed=False,preserved={str(p):core.tree(p) for p in (proof,startup)}))
    totals=receipts['contracts']['results']['x64'][-1];windows=receipts['windows-contracts']
    text=f'''UNREAL II SURFACE TRANSFER AND CONDITIONAL WINDOW TRANSITIONS
Development milestone complete. 2026-10-30.
Genuine launches: ZERO. Physical GPU fixture executions: ZERO. Supervisor authorization unchanged.

IMPLEMENTATION
Isolated runtime: {RT}
Six new D3D8 methods: GetBackBuffer, CreateRenderTarget, CreateDepthStencilSurface,
CreateImageSurface, CopyRects and GetFrontBuffer. Surface objects use the existing
typed COM registry, native reference ownership and copied-lock transport. Failed
creation/getter calls preserve untouched output values separately from native NULL.
CopyRects snapshots bounded arrays after validating every guest page; native calls
receive private copies. Reentry, stale/type-confused handles, outstanding maps,
overflow/capacity violations and callback output-protection changes are guarded.

Five conditional USER32 imports: SetWindowLongA/W (style/exstyle), SetMenu(NULL),
PostMessageA/W (owned-window scalar/command payloads). STYLESTRUCT stays eight bytes
across native x86/x64 and guest code; changes flow through real default processing.
STYLECHANGED mutation and pointer-valued fields/payloads remain guarded. Menu objects,
subclassing, thread/broadcast and foreign-window messaging are not implemented.

ORIGINAL PATHS AND ENGINE INITIALIZATION
Original depth-surface creation at 0697B5D7 loads renderer field +4698 and invokes
slot 26 inside a resource-cache retry loop. Original GetBackBuffer at 0696D619 belongs
to ReadPixels, not a proven first-frame path. Surface copy/standalone targets complete
the resource subsystem; no genuine callsite for those operations is asserted here.
The static audit retains 44 slot-offset candidate contexts, marking only four as
confirmed device callsites in this extension; collisions remain explicitly unresolved.
Nine conditional Windows import sites are mapped to the new implementations.
Thirteen original exported-body ranges retain all generated instruction markers.

The preserved SetRes audit independently pairs 250 operations, EAX=1, raw CPU state,
hard stop at 11104BF8 and contained cleanup. The Init tail still executes original
virtual calls and InitAudio at 1038FB33. No engine branch/audio/renderer bypass was
added. Init return and a genuine frame remain unverified. Offline endpoint remains
before guest 1090ED5C; active supervisor stop policy was not changed.

EXECUTED VALIDATION
x86/x64 actual adapters with declared COM doubles: {totals['checks']} cumulative checks
per architecture, including 36 new surface positives and 11 new rejection cases.
These are protocol/ABI/memory-safety tests, not native GPU evidence.
Real USER32: {windows['cases']} operations and {windows['callback_records']} callback records agree
across native x86, native x64 and translated bodies; seven negative guards pass.
Full suspended guest CPU and x86 callback nonvolatile/FPU checks pass.
Supervisor 81 and collector 105 tests pass. Registered-window/accessibility fixtures
and ten existing rejection cases pass unchanged. Evidence/observer tests are sealed.
Real DirectInput transfers still pass; independent-call last-error differences remain
in contracts.json. Historical strict x87 and complete WNDPROC failures remain FAILED.

CANDIDATE
{exe}
SHA256 {sha}
PDB SHA256 {pdb}
All 279 objects have verified transitive lineage: 2 rebuilt runtime objects,
277 verified reused objects. PE/PDB, toolchain, dependencies and nonconsumption pass.
All 60 checked HLE bindings resolve to implementation symbols. The Init-return mapping
and owned non-game hardware/cleanup tests pass with candidate mapped NO_EXECUTE;
no candidate instruction or entry point was executed.

DEFERRED PHYSICAL BATCH
physical-batch.json identifies exactly three compiled immutable fixtures: native x86,
native x64 and translated x64. They combine the prior resource/draw/Present matrix
with surface creation, target/depth switch, copied rectangles, pixel readback and
cleanup. No submission or startup was attempted. GetFrontBuffer tests NULL failure
only; successful front capture is explicitly unqualified. The supplementary parser
checks sequence, raw ABI, CPU, output, pixels and cleanup but cannot confer acceptance.

PRESERVATION AND NEXT WORK
Prior resource runtime/candidates/evidence, production runtime/generated code,
supervisor source, installation/saves and consumed SetRes evidence verify unchanged.
The remote physical-console proof is CLOSED UNSUCCESSFUL due to application-identity
mismatch. Both its proof and subsequent startup-investigation evidence are preserved;
no retry, workaround, remote startup work or authorization change occurred.
Remaining domains include cube/volume textures, programmed shaders, additional state
methods and lost-device Reset. See remaining-unsupported.json. This milestone does
not assert full first-frame compatibility or physical acceptance.
'''
    (O/'REPORT.txt').write_text(text)
    save(O/'milestone.json',dict(passed=True,development_milestone='surface transfer and conditional window transition subsystem',candidate_sha256=sha,execution_authorized=False,genuine_launches=0,gpu_executions=0,physical_batch_prepared=True,strict_compatibility='FAILED retained',runtime=runtime,tests_source=core.tree(H),receipts={n:core.sha(O/(n+'.json')) for n in receipts},report_sha256=core.sha(O/'REPORT.txt')))
    print('SEALED',sha,'three physical fixtures prepared; no game/GPU execution',flush=True)
if __name__=='__main__':main()
