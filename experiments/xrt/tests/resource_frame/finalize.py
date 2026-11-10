"""Seal truthful completed and pending work; no game or fixture submission."""
import sys,re,uuid,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    b=read(O/'build.json');runtime=core.tree(RT);assert b['runtime']==runtime
    assert core.tree(Path(b['root']))==b['outputs']
    for name in ('contracts','regressions','gpu-qualification-package'):
        assert read(O/(name+'.json'))['runtime']==runtime,name
    for name in ('candidate-identity','static-audit','resource-path-audit','linked-adapters','stop-mapping','debugger-validation','preservation-after','setres-independent-audit'):
        assert read(O/(name+'.json'))['passed'],name
    package=read(O/'gpu-qualification-package.json');assert not package['executed']
    for row in package['candidates']:
        manifest=Path(row['manifest']);assert core.sha(manifest)==row['manifest_sha256']
        for name,digest in read(manifest)['files'].items():assert core.sha(name)==digest,name
    out=O/('parser-observer-tests-'+str(uuid.uuid4()));out.mkdir()
    for name in ('test_evidence','test_observer'):
        p=subprocess.run([sys.executable,'-B','-I',str(H/(name+'.py')),'-v'],capture_output=True,timeout=30)
        (out/(name+'.stdout.bin')).write_bytes(p.stdout);(out/(name+'.stderr.bin')).write_bytes(p.stderr);assert p.returncode==0
    save(O/'parser-observer-tests.json',dict(passed=True,root=str(out),tests=4,rejection_mutations=17,physical_acceptance=False))
    status=read(W/'out/desktop-fixtures/status.json');assert status['state']=='stopped'
    save(O/'fixture-availability.json',dict(status=status,status_sha256=core.sha(W/'out/desktop-fixtures/status.json'),requests_submitted=0,graphics_executed=False))
    refs={p.name:dict(sha256=core.sha(p),url='https://github.com/doitsujin/dxvk/blob/v3.1.1/src/d3d8/'+p.name.replace('native-','d3d8_').replace('device-child','device_child')) for p in O.glob('native-*') if p.suffix in ('.h','.cpp')}
    save(O/'native-source-references.json',refs)
    unsupported=[dict(slot=int(n),name=name) for n,name in re.findall(r'unsupported slot (\d+) (\w+)',(RT/'d3d8_device_slots.inc').read_text())]
    save(O/'remaining-unsupported.json',dict(device_methods=unsupported,
        shader_programs='Non-NULL vertex shader program bytecode and pixel shaders remain unsupported; NULL-function declarations now supported.',
        declaration_tokens='NOP, STREAM, REG, SKIP, exact END supported. Constants, tessellation, extension tokens and repeated stream declarations remain guarded.',
        resources='Cube/volume textures, custom render-target/depth/image surface creation, CopyRects and private-data COM interfaces remain unsupported.',
        locks='One outstanding resource map globally; 64 MiB/map, selected packed/DXT formats only. Failed native Unlock returns its actual failure then forces retained teardown state.',
        draws='FVF and declaration-only layouts supported, with owned initialized uploads for every declared stream. UP declarations require stream 0 only.',
        reset='Lost-device Reset/recreation remains unsupported; one native device attempt per process retained.',
        genuine='No game launch or genuine resource/scene evidence in this work. Physical native/translated resource validation remains pending.',
        conditional_windows=['PostMessageA/W','SetWindowLongA/W','SetMenu']))
    mapping=read(O/'stop-mapping.json');exe,sha,pdb=identity()
    save(O/'continuation-design.json',dict(prepared=True,execution_authorized=False,observer_installed=False,production_policy_changed=False,
        candidate=str(exe),sha256=sha,pdb_sha256=pdb,guest_stop=GUEST,stop_rva=mapping['stop_rva'],stop_bytes=mapping['stop_bytes'],
        observer_source=str(H/'observer.py'),observer_sha256=core.sha(H/'observer.py'),maximum_slots=4,watchdog_seconds=60,retry=False,
        boundary='After checked UGameEngine::Init return; before guest CALL at 1090ED5C. No main-loop tick admitted.',
        qualification='Owned stop handler, live DR readback, main/new threads, four-slot limit, wrong bytes, failure termination; candidate mapped SEC_IMAGE_NO_EXECUTE only.',
        pending=['Physical GPU resource qualification and unchanged collector evidence','Separate authorized composition into genuine observer; existing early-stop policy unchanged','Paired real engine Init/lifecycle evidence; no inference from fixture CPUs'],genuine_launches=0))
    contracts=read(O/'contracts.json');totals=contracts['results']['x64'][-1];di=contracts['directinput_strict_differences']
    bind=read(O/'linked-adapters.json')['bindings'];setres=read(O/'setres-independent-audit.json')
    text=f'''UNREAL II D3D8 RESOURCES AND FIRST-FRAME PREPARATION
2026-10-30. Genuine launches: ZERO. Physical GPU fixtures executed: ZERO.

Completed in a new isolated experimental runtime:
- GetRenderTarget/GetDepthStencilSurface; typed surface/texture/VB/IB identities.
- Native QueryInterface/AddRef/Release/GetDevice and typed GetContainer.
  Repeated live interfaces preserve identity; retired unbound tokens never reuse.
  Device/parent/window ownership survives device-first release and reacquisition.
  Mip surfaces preserve native container-forwarded reference counts.
- CreateTexture, GetLevelCount/Desc/SurfaceLevel, surface GetDesc, LockRect/
  UnlockRect, AddDirtyRect, LOD/priority/PreLoad/GetType, and UpdateTexture.
  Native mip descriptors/pitches determine copies; native pointers never escape.
- CreateVertexBuffer/CreateIndexBuffer, GetDesc, Lock/Unlock, non-NULL texture,
  stream/index setters and getters. Owned host copies track initialized bytes.
- DrawPrimitive/DrawIndexedPrimitive validate every used stream, full index
  extent, index16/index32 values, base/minimum/ranges, stride/layout and caps.
  Native UP calls also invalidate tracked bindings as required by the backend.
- Create/Set/Get/DeleteVertexShader for declaration-only NULL-function shaders;
  copied bounded tokens, typed shader identities, multi-stream layout validation.
- SetRenderTarget; existing scene/viewport/Clear/Present remain integrated.
  Partial native SetRenderTarget failure is not replaced with a cached success.

Static original-code findings:
The first Lock helper loads the real renderer device field +4698 before
GetRenderTarget at 0696FBCC and GetDepthStencilSurface at 0696FBFB.
31 resource-related original callsite contexts are saved, including buffer
draws and resource creation. At 0697C063, original pushes a declaration pointer,
NULL program, output handle and usage 0/0x10 into CreateVertexShader slot 75.
This directly motivated declaration-only and multi-stream support. These are
static findings, not newly observed game execution or proof of dynamic reachability.

Executed validation:
Native x86 and x64 protocol executables invoke the actual integrated adapters
against DECLARED COM DOUBLES: {totals['resource_cases']} new positive cases,
{totals['resource_negatives']} new negative cases; {totals['checks']} cumulative checks per architecture.
Retained renderer: 373 cases, 19 negatives, 195 generated cache calls, 16 creation
preflights and four device cases. Retained scene: 40 positives/17 negatives.
Checks cover full guest CPU/stack, HRESULT/last-error, callback scope/reentry,
output page changes during native calls, unreadable/overflowing ranges, stale
and wrong-type handles, padded/DXT uploads, readonly maps, native lock failures,
native Unlock failure containment, mip-parent lifetime, retired shader handles,
missing/invalid streams, malformed/nonterminated declarations and index bounds.
This is protocol/ABI/memory-safety evidence, NOT native GPU equivalence.

DirectInput doubles: 349 checks per architecture. Actual system DirectInput
x86/x64 lifecycle probes ran; inner-native result transfer passes. Two independent
Acquire invocations still differ at sample 7: native error 0, translated error 5,
HRESULT 0 on BOTH architectures. {len(di)} retained strict discrepancy records.
81 unchanged supervisor and 105 collector tests pass. Registered GUI positives
and ten guarded cases pass. Four parser/observer tests include 17 corruption cases.
Five live owned debugger cases and retained observer factory cases pass.

Independent historical genuine SetRes audit:
{setres['operation_count']} native operations paired to four debugger checkpoints each;
raw 416-byte CPUs match runtime records; EAX=1, ESP=0120D418 (entry+24),
return=11104BF8, nonvolatiles preserved. Stop occurred before its instruction;
Job cleanup left zero processes; gamma restored exactly. This was forced
teardown, not normal guest resource cleanup. No scene or frame is inferred.

Final fresh UNEXECUTED candidate:
EXE: {exe}
SHA256: {sha}
PDB SHA256: {pdb}
Recompiled actual adapter owner hle_misc.obj; 278 unchanged objects reused with
verified transitive lineage (279 total). Complete runtime/header/generated and
toolchain inventories, link inputs, independent PE/PDB GUID/age and consumption
audit pass. {len(bind)} linked adapter bindings independently verified.
No consumed candidate was reused. Intermediate candidates remain preserved.

Prepared bounded observer:
Guest 1090ED5C; host RVA {mapping['stop_rva']:08X}; bytes {mapping['stop_bytes']}.
After the checked UGameEngine::Init return, before the next guest CALL.
Full raw CPU saved before assertions; exact host bytes/register/CPU.rv required;
stop requests termination while stopped. Owned fixture main/new-thread live DR
readback, four-slot enforcement and failure cleanup pass. Candidate only mapped
SEC_IMAGE_NO_EXECUTE; no candidate instruction or genuine endpoint executed.
Observer is prepared, not installed. Active breakpoint/authorization policy unchanged.

Smallest required physical-desktop test:
One consolidated batch of THREE existing fixed-recipe fixtures, each bounded
by the existing 60-second Job/watchdog/module/desktop collector:
  native x86:     {package['candidates'][0]['candidate_id']}
  native x64:     {package['candidates'][1]['candidate_id']}
  translated x64: {package['candidates'][2]['candidate_id']}
Each covers surface identity/native refcounts, four texture mips and alias
readback, FVF then declaration-only two-stream draws, indexed16/indexed32,
render targets/viewport/scenes, guest-surface non-clear RGB readback, Present
and native cleanup. Geometry is SYNTHETIC, never a genuine Unreal II scene.
The fixture service was stopped; no start, submission or GPU execution occurred.
After a future existing-service owner startup, these manifests are ready for
the normal submit-test workflow. Preserve original collector outcomes, including
its old numerical-parser rejection of new records. gpu_evidence.py adds a strict
saved-output comparison; it never grants formal physical acceptance or waives
desktop/process/module/Job evidence. Outer ABI capture is not inner-call register capture.

Remaining blockers and limits:
Physical GPU behavior, pixels and native/translated resource equality are pending.
A genuine engine Init return and first scene remain unverified. Non-NULL shader
programs, cube/volume textures, custom surface creation/CopyRects, private-data
COM and lost-device Reset remain unsupported. Conditional Windows imports may
still stop initialization. Capacities are explicit: 4096 resource identities,
2048 declarations/256 DWORDs, one concurrent map, 64 MiB map/buffer, 256 MiB host
mirror budget, 16 streams/eight stages. Unknown/unsafe cases stop, not fake S_OK.
No live game rendering is claimed from the fixture package or protocol doubles.

Preservation:
Original installation/save verification and prior runtime/evidence, production
runtime, generated source and supervisor trees match their initial seals.
Strict x87 and WNDPROC failures remain separate FAILED gates; DirectInput
last-error differences remain separate. No policy, containment, COM or memory
protection bypass; no game launch, remote push or release.
'''
    (O/'REPORT.txt').write_text(text)
    receipts=['build','candidate-identity','object-lineage','contracts','regressions','setres-independent-audit','static-audit','resource-path-audit','linked-adapters','stop-mapping','debugger-validation','preservation-after','gpu-qualification-package','fixture-availability','continuation-design','remaining-unsupported','parser-observer-tests','native-source-references']
    save(O/'milestone.json',dict(implementation_complete=True,physical_gpu_qualified=False,genuine_scene_verified=False,genuine_launches=0,sha256=sha,pdb_sha256=pdb,
        runtime=runtime,helper_sources=core.tree(H),receipts={n:core.sha(O/(n+'.json')) for n in receipts},report_sha256=core.sha(O/'REPORT.txt'),strict_compatibility='FAILED retained'))
    print('Resource subsystem sealed:',sha,'physical/game rendering UNVERIFIED',flush=True)
if __name__=='__main__':main()
