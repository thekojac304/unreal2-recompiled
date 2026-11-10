"""Write the comprehensive handoff from final receipts. Never launches a game."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    inv=read(O/'guard-inventory.json');ci=read(O/'candidate-identity.json');b=read(O/'build.json')
    plan=read(O/'stop-mapping.json');linked=read(O/'linked-adapter-audit.json');contracts=read(O/'contracts.json')
    tests=read(O/'unit-regressions.json');live=read(O/'live-observer-validation.json');physical=read(O/'physical-availability.json')
    core.require(all(read(O/n)['passed'] for n in ('contracts.json','candidate-identity.json','linked-adapter-audit.json',
        'unit-regressions.json','final-observer-tests.json','live-observer-validation.json','debugger-validation.json','preservation-after.json')),'handoff receipts incomplete')
    docs=inv['documentation']
    specifications=[
        ('renderer-properties','Remove renderer/profile and all 53 capability equality tests',
         ['integrated_renderer.inc'],['semantic_renderer.inc','semantic_policy.h'],
         'Original Core Boolean stores retain the registration mask; D3DDrv 0696F3F9..0696F407 tests the full UseTrilinear DWORD for nonzero. Cache 06977800..069783FE consumes original values/capability clamps.',
         'Do not rewrite guest properties. Validate the resulting API arguments against live native caps. Editor flag/profile equality is removed; full editor functionality is not qualified.', ['backend','caps']),
        ('render-states','Replace captured SetRenderState tuples with semantic domains',
         ['integrated_renderer.inc','hle_d3d8_device.inc'],['semantic_renderer.inc','semantic_policy.h'],
         'D3DDrv SetRes 0696E890..0696F4E9 and cache 06977800 issue DWORD state/value calls; API uses enumerations, bitmasks, BOOL and float payloads.',
         'Known BOOL states forward every DWORD unchanged. Blend/compare/stencil/cull/fog/point states use typed domains and applicable live caps. Known backend no-op or unimplemented features stop diagnostically.', ['d3d8','backend','caps']),
        ('texture-stages','Replace sampler tuple and order restrictions',
         ['integrated_renderer.inc'],['semantic_renderer.inc','semantic_policy.h'],
         'D3DDrv 0696F3AC..0696F42E selects mip filter from the original nonzero flags. Pinned DXVK maps D3D8 texture-stage sampler states to D3D9 sampler states.',
         'Stage 0..7; documented selectors, operations, arguments, address/filter caps, finite LOD bias and live anisotropy bounds. No 238-call count/order requirement.', ['stages','caps','pinned_shader_handle_and_present_mapping']),
        ('typed-inputs','Generalize material and transform bytes',
         ['integrated_renderer.inc','hle_d3d8_device.inc'],['semantic_renderer.inc','semantic_evidence.inc'],
         'SetMaterial and SetTransform consume typed D3DMATERIAL8 and D3DMATRIX inputs; the original passes guest pointers, not a requirement for one captured matrix/material.',
         'Readable 68/64-byte guest ranges copied into host locals, finite components, nonnegative material power and valid transform IDs. Identity-matrix/material-byte equality removed; nonfinite inputs remain uncharacterized.', ['backend','memory']),
        ('null-bindings-fvf','Generalize resource unbinding and FVF values',
         ['integrated_renderer.inc'],['semantic_renderer.inc','semantic_policy.h'],
         'The original cache unbinds textures, streams and indices and sets an FVF. Pinned DXVK v3.1.1 identifies programmable handles by D3DFVF_RESERVED0 bit zero.',
         'NULL texture stage 0..7; stream/stride bounded by live caps; NULL indices preserve arbitrary BaseVertexIndex. Valid supported FVFs replace literal 2. Non-NULL resources and programmable handles still require typed ownership.', ['backend','caps','pinned_shader_handle_and_present_mapping']),
        ('gamma','Generalize the void gamma adapter and complete its evidence',
         ['integrated_renderer.inc'],['semantic_renderer.inc','semantic_evidence.inc'],
         'SetGammaRamp takes DWORD flags and a 1536-byte WORD ramp and returns VOID. Original game computes its ramp; historical bytes are measurements.',
         'Copy any readable typed ramp; flags 0/1 and advertised FULLSCREENGAMMA capability bit. CALIBRATE is an optional request, not proof of an installed calibrator or visible windowed gamma effect. Preserve EAX, stack cleanup and actual last-error. Remove captured ramp equality. Explicit stack update fixes unreachable return evidence after the historical RET macro.', ['backend','abi']),
        ('clear','Generalize Clear rectangles and target/depth/stencil arguments',
         ['hle_d3d8_device.inc'],['semantic_clear.inc'],
         'IDirect3DDevice8::Clear receives a count, typed D3DRECT array, clear flags, color, depth and stencil scalar.',
         'Overflow/readability checked dynamic host copies; valid flags/surface capabilities and depth [0,1], including -0. Fixed count=1/1540x945/depth=0/stencil=0 profile removed.', ['backend','memory']),
        ('creation','Generalize the windowed HAL creation profile',
         ['hle_d3d8_device.inc'],['semantic_create.inc','hle_d3d8_device.inc'],
         'D3DPRESENT_PARAMETERS is a mutable typed structure. Actual parent capability/type/multisample/depth-match queries determine combinations. Pinned DXVK maps UNKNOWN format to X8R8G8B8 (22) and count zero to one.',
         'Zero/native-default or live-cap-bounded dimensions; RGB formats, counts, swap and multisample combinations, noncanonical windowed/depth BOOLs; separate owned focus/window and NULL defaults. FPU-preserve HAL windowed scope, process-once policy, private pending references and output identity remain.', ['backend','caps','pinned_shader_handle_and_present_mapping']),
        ('parent-queries','Implement pointer-free native capability queries and correct error transfer',
         ['hle_d3d8.inc'],['semantic_parent.inc','hle_d3d8.inc'],
         'IDirect3D8 CheckDeviceType and CheckDeviceMultiSampleType have known pointer-free signatures; HRESULT is an actual native result. Direct3DCreate8 accepts a UINT SDK argument and returns an actual pointer or NULL.',
         'Actual query results/errors, private pending AddRef and callback scope; live adapter bounds. Remove SDK=120 host admission. Parent query outputs use page protections. RegisterSoftwareDevice and HMONITOR marshalling remain unsupported.', ['backend','com','memory']),
        ('windows','Generalize MoveWindow geometry/repaint and WM_GETICON DPI',
         ['hle_gui.c'],['hle_gui.c','hle_gui_diag.inc'],
         'Original WinDrv ResizeViewport 11104F20 and Window MoveWindow call 110018E2 use signed geometry and BOOL repaint. WM_GETICON accepts a DPI scalar and selector enum.',
         'Call real USER32 with signed arguments and arbitrary BOOL; no fixed caller, size, style/menu or DPI=96 admission. Owned same-thread HWND, typed callback messages and icon identities remain. Record full callback/MoveWindow CPU and host context.', ['move','icon_dpi','attach']),
        ('observer','Replace exact configuration/order/success assertions with evidence and ABI checks',
         ['observer.py','evidence.py','profile_gate.py'],['observer.py'],
         'Original WinDrv 11104BF5 calls SetRes with five stack arguments; D3DDrv returns RET20 to 11104BF8. Win32 UBOOL is tested for nonzero. Windows x64 defines native nonvolatile GPR/XMM/control preservation.',
         'Capture raw evidence before evaluation, check actual native entry/return and typed structures, propagate actual HRESULT/error, distinguish void calls and zero/nonzero UBOOL, permit tracked callbacks, record individual strict FPU differences. Correct initial caller/endpoint enforced. Permanent hardware readback code and production supervisor remain unchanged.', ['abi','com'])
    ]
    changes=[]
    for ident,title,oldnames,newnames,basis,replacement,keys in specifications:
        def sites(names,current):
            return [{k:r.get(k) for k in ('id','source','line','source_sha256','function','expression','condition','nearest_condition','category','action')}
                    for r in inv['guards'] if Path(r['source']).name in names and Path(r['source']).is_relative_to(RT)==current
                    and (current or Path(r['source']).is_relative_to(PRIOR/'runtime') or 'renderer_config_diagnosis' in r['source'])]
        changes.append(dict(id=ident,title=title,original_basis=basis,replacement=replacement,
            api_contracts=[docs[k] for k in keys],legacy_sites=sites(oldnames,False),current_sites=sites(newnames,True) if ident!='observer' else
            [r for r in inv['guards'] if Path(r['source'])==H/'observer.py']))
    save(O/'semantic-changes.json',dict(version=1,changes=changes,renderer_fields=inv['renderer_fields'],
        candidate_sha256=ci['sha256'],guard_inventory_sha256=core.sha(O/'guard-inventory.json'),
        note='Each group contains exact relevant source predicates, including safety predicates retained alongside semantic changes. The replacement prose describes the group; not every listed predicate was removed. Inventory IDs are source sites across both revisions.'))
    r=contracts['results'][0];unit=', '.join(f"{v['tests']} {v['name']}" for v in tests['results'])
    unbound=sorted({i['name'] for row in read(O/'windows-import-audit.json')['rows'] for i in row['imports']
                    if i['module'].lower()=='user32.dll' and not i['binding']})
    text=f'''UNREAL II - COMPREHENSIVE GUARD AUDIT AND SEMANTIC COMPATIBILITY HANDOFF
Updated 2026-10-30, America/New_York. Package name retains its 20261029 start date.

The isolated semantic runtime and non-graphical integration milestone are complete.
Physical GPU promotion is pending. No genuine game launch, SetRes completion,
Init completion, world tick or rendered scene is claimed by this refactor.
This package does not authorize a game launch or provide an automatic launch path.

1. AUDIT SCOPE AND COUNTS

guard-inventory.json contains {inv['total_guard_sites']} source guard sites:
  SAFETY_CRITICAL: {inv['categories']['SAFETY_CRITICAL']}
  SEMANTIC_COMPATIBILITY: {inv['categories']['SEMANTIC_COMPATIBILITY']}
  STRICT_DIFFERENTIAL: {inv['categories']['STRICT_DIFFERENTIAL']}
Source groups: {inv['source_groups']}.
These count old and new source sites separately, not that many distinct current
runtime restrictions. All 53 old capability equality predicates and ten renderer
field comparisons are separately searchable. Mixed old ABI/FPU assertions have
component classifications. Historical x87, complete WNDPROC equality and broader
native-x86 compatibility verdicts remain FAILED; three strict assertion sites do
not mean only three historical discrepancies exist.

The inventory covers the renderer/GUI/import source closure, old and proposed
observers, permanent-stop checks and unchanged supervisor containment boundaries.
Each row records source hash, line, exact call/predicate, enclosing if conditions,
category, disposition, safety need and original/API provenance. It enumerates
fatal/domain/require/assert sites; it is not a formal proof of every reachable
branch. semantic-changes.json maps coherent changes to exact source sites.
original-provenance.json preserves original PE/instruction and prior measurements.
windows-import-audit.json covers {sum(len(x['imports']) for x in read(O/'windows-import-audit.json')['rows'])} direct IAT callsites in original OpenWindow,
TryRenderDevice, ResizeViewport and Window MoveWindow. Relative/virtual calls use
their existing translated dispatch; static alternate branches are not execution
evidence.

2. EXACT GUARDS REMOVED, GENERALIZED AND RETAINED

Removed the integrated_renderer.inc/batch_cases.inc admission mechanism: fixed
callsite/tuple/configuration, 238-call count/order, captured material/matrix/gamma
bytes, raw renderer property equality and equality of all 53 D3DCAPS8 words.
The ten retired renderer offset/value tests are:
{chr(10).join('  '+x['offset']+' == '+hex(x['old_expected'])+' ('+x['field']['name']+')' for x in inv['renderer_fields'])}
UseTrilinear accepts the original complete-DWORD nonzero semantics; a real mask
test remains that exact mask test. No host normalization or INI forcing occurs.
The original engine still calculates/clamps values before calling the API.

SetRenderState now uses known D3D8 IDs, enums, BOOLs, float and bitmask domains
plus applicable live device caps. BOOL payloads 1,2,0x20,0x80,0x80000000 and
0xffffffff are forwarded unchanged where the state is a BOOL. Capability checks
cover blend/compare/stencil/cull/fog/point features rather than assuming all valid
syntax is supported. Known unimplemented backend features are diagnostic stops.
SetTextureStageState uses stages 0..7, known operation/argument/address/filter
domains, live filter/address/texture-op caps, finite LOD and live anisotropy.

SetMaterial copies 68 bytes with finite components and nonnegative power.
SetTransform copies 64 bytes, validates transform ID and finite matrix values;
it accepts nonidentity matrices. SetTexture supports NULL bindings on stages0..7.
SetStreamSource supports NULL buffers, live stream/stride limits and nonzero
stride; SetIndices preserves arbitrary scalar BaseVertexIndex when unbinding.
SetVertexShader accepts valid capability-supported FVFs rather than only2.
Pinned DXVK's bit-zero shader handles require owned shader objects and stop.
Unknown resource tokens are never treated as native pointers.

SetGammaRamp accepts copied 1536-byte ramps with flags 0/1 and the advertised
FULLSCREENGAMMA capability bit instead of one captured ramp. CALIBRATE requests
optional calibration; no installed calibrator or visible windowed effect is
inferred from that bit or from a void native return. It is VOID: EAX is preserved, no HRESULT
is invented. The old RET(12) macro returned from C before return evidence could
execute; the new explicit guest pop/ESP update makes phases0/1/2/3 observable.
Clear accepts dynamically copied D3DRECT arrays, validated count/size/readability,
flags and target/depth/stencil capability, color/stencil payloads and depth[0,1]
(including -0). It no longer requires one1540x945 rectangle/depth0/stencil0.

CreateDevice now validates windowed HAL combinations with actual GetDeviceCaps,
GetAdapterDisplayMode, CheckDeviceType, color/depth CheckDeviceMultiSampleType and
CheckDepthStencilMatch calls. Zero dimensions/count/format reach the native
default behavior. Explicit dimensions use conservative live texture-cap bounds.
RGB/depth formats, backbuffer counts, swap/multisample combinations, software/
hardware/mixed VP and noncanonical windowed/depth BOOLs replace a captured tuple.
Focus and presentation windows may differ; NULL focus or NULL presentation uses
an owned remaining window. Both NULL remains unsafe. Private pending references
and callback scope cover preflight as well as native creation. PP52 guest/PP56
host and device output are copied back with HWND/COM identity conversion.
The format0 preflight value22 follows the pinned backend's UNKNOWN-to-X8R8G8B8
conversion; it is not a captured display profile.

Public CheckDeviceType and CheckDeviceMultiSampleType now call their known
pointer-free native signatures and preserve real failures and last-error.
Direct3DCreate8 forwards its UINT SDK argument instead of requiring120 and
returns the native pointer/NULL. Parent query outputs check page protection;
implemented query/factory error seeds and actual last-error transfer are fixed.

MoveWindow calls actual USER32 with signed geometry and arbitrary BOOL repaint.
Fixed caller,1540x945,DPI96,style/menu constraints are removed. Owned same-thread
HWND/callback validation remains. WM_GETICON permits representable DPI scalars;
selector0..2 and typed returned-icon identity remain. Full callback and MoveWindow
CPU/host contexts are recorded in this experimental runtime.

Retained: complete argument-frame/range/protection checks, typed host copies,
live COM token/type/reference identity, private references/children/window pins,
reentrancy/final Release protections, ABI/nonvolatile/control-state preservation,
approved module hashes, sandbox/process/Job containment, watchdog, consumed
identity exclusion and permanent hardware breakpoint/readback. Renderer binding
is checked at initial SetRes entry/return; API calls validate their live COM
device instead of reconstructing a renderer from a fixed caller stack layout.
No arbitrary D3D success stubs, unsafe pointer forwarding or policy bypasses.

3. ORIGINAL/API JUSTIFICATION

Original D3DDrv SetRes0696E890..0696F4E9 and cache06977800..069783FE supply the
instruction basis; Core Boolean-store and D3D sampler-decision fragments are
executed in owned differential probes. UseTrilinear registration is0696AAA3,
consumer0696F3F9..0696F407. WinDrv11104BF5 supplies the initial SetRes call and
11104BF8 tests EAX for nonzero. Original SetRes returns RET20.
semantic-changes.json contains per-change original references and API links.
Primary references (archive pages describe individual methods, not a blanket
desktop capability promise):
  {docs['d3d8']}
  {docs['stages']}
  {docs['backend']}
  {docs['pinned_shader_handle_and_present_mapping']}
  {docs['caps']}
  {docs['move']}
  {docs['icon_dpi']}
  {docs['attach']}
  {docs['abi']}
  {docs['memory']}
  {docs['com']}
The backend is pinned DXVK3.1.1; handle/default behavior is not generalized to
arbitrary other D3D8 implementations. Unknown operations preserve evidence/stop.

4. OBSERVER AND EVIDENCE

observer.py is a separate proposal using the retained contained debugger/factory
and unchanged hardware DR reservation/readback function. Production observer,
supervisor policy, stop endpoint and global hold/ledger were not changed.
The proposal logs actual host registers,416-byte CPU, argument frames/stacks,
objects, renderer/viewport fields and native structures before evaluating them.
Four runtime checkpoints bracket entry, pre-native, actual native result and
guest return. Native entry/return capture verifies COM identity, converted
arguments, const inputs, mutable creation PP/output, HRESULT, last-error, guest
CPU preservation and native GPR/XMM/control ABI. Tracked callback nesting retains
suspended CPU. Individual strict FPU/status differences are recorded separately.
Native API failures are transferred; invalid/unsafe operations terminate;
unimplemented/unknown behavior stops diagnostically. No fabricated success or
guest behavior modification. Unreadable evidence preserves the already durable
prefix; evidence-write failures terminate before continued execution.

5. REGRESSION RESULTS AND SCOPE

All final receipts PASS:
  - {r['cases']} semantic matrix cases,3 HRESULT variants, {r['checks']} checks per x86/x64
    architecture, equal hash {r['hash']}; {r['negative_cases']} negative cases.
  - {r['creation_cases']} creation preflight variants plus {r['creation_adapter_cases']} full CreateDevice adapter
    cases: distinct/NULL HWND defaults, PP/output identity and actual failure
    teardown. These use declared COM protocol doubles, no GPU/backend.
  - Unchanged generated cache initializer: {r['integrated_cache_calls']} calls through the integrated
    adapters on one persistent COM double, one live caps query. This checks
    combined original control flow; it does not execute a game module.
  - 96 exact original Boolean-store/sampler native-x86 vs lifted cases.
  - 24 GUI comparisons (12 MoveWindow,12 WM_GETICON), native x86/x64/lifted;
    repaint0/1/32 and DPI0/48/96/120/144/192. Invalid HWND identity rejected.
  - AttachThreadInput:24 positive self-thread calls,6 negative guards; real
    Windows FALSE/error87 and keyboard-state behavior retained.
  - Registered queryclass/accessibility callbacks:2 positives,10 negative
    guards; suspended CPU preserved. ResizeViewport:8 samples per native-x86/
    generated-x64 variant, owned windows and declared virtual dependencies.
  - {unit}. The final observer's
    15 tests were rerun after its last change (final-observer-tests.json).
  - {len(live['cases'])} live observer protocol cases, including real native call/return registers,
    copied material/matrix/gamma/Clear, creation/null-focus/failure, callback
    double, CPU corruption and evidence-write failure. Zero remaining Job
    processes; no continued-after-marker file. Protocol callbacks are doubles;
    real registered GUI callbacks are covered by the separate GUI fixtures.
  - Five live exact-candidate inert mapping/hardware/failure cases plus retained
    debugger/fatal fixtures. Candidate mapped SEC_IMAGE_NO_EXECUTE; its actual
    endpoint was not executed. DR readback on main/new threads, slot overflow,
    wrong bytes and observer failure prove contained terminate-before-continue.

The live protocol fixture reserves the full4GiB guest range. A smaller fixture
allocation initially allowed unrelated native locals inside that nominal range;
the fixture was corrected while retaining the stronger observer pointer guard.
Routine failed development runs/logs remain in this package; final receipt JSONs
identify accepted final runs. One whole renderer-suite60s timeout was a harness
budget issue; the suite budget became180s, per-case limits/policies unchanged.

Previously accepted physical GPU/gamma measurements remain byte-preserved in
renderer-acceptance and renderer-gamma-integration and their retained evidence.
They do not qualify newly broadened GPU argument domains. This work ran zero
physical GPU fixtures: both saved fixture/prerequisite services are stopped;
the desktop-fixture authorization has expired. The saved prerequisite batch was
still within its expiry at the availability check, but its service was stopped.
No queue submission occurred. New physical restoration/
gamma/driver measurements are a remaining promotion gate, not a synthetic pass.

6. FRESH CANDIDATE AND VERIFIED BUILD LINEAGE

EXE: {ci['executable']}
SHA256: {ci['sha256']}
PDB SHA256: {ci['pdb_sha256']}
PE/PDB GUID: {ci['pe_pdb']['guid']}, age{ci['pe_pdb']['age']}.
279 objects: recompiled hle_gui.obj AND hle_misc.obj; reused265 generated+12
runtime objects. Source, headers, original/reused object hashes, transitive
lineage, toolchain, commands, link response, pinned dependencies and consumption
scan independently verify. No C1001/D8040 occurred in the successful build.

The inherited helper rebuilt only hle_gui.obj while claiming renderer changes.
Actual D3D8 includes belong to hle_misc.c. Initial development builds reproduced
that defect; missing semantic symbols in independent PDB verification exposed it.
The new builder compiles both units and proves /showIncludes closure. Historical
packages/verdicts remain unchanged; their source-only claims are not promoted to
proof of linked renderer behavior. Superseded development candidates remain
unlaunched and are not the handoff identity.

linked-adapter-audit.json disassembles {len(linked['wrappers'])} actual linked implementations and
checks {len(linked['hle_bindings'])} HLE table pointers against their implementation RVAs, including
Clear,Present,CreateDevice and public capability queries. Actual PDB verifies
the280-byte device record with unchanged original prefix and appended live caps.
Tests exercise the actual adapter sources; inert binary checks establish the
candidate linkage/endpoint. Neither is a claim of physical candidate execution.

7. BOUNDED INITIAL SETRES CONTINUATION READINESS

Prepared target: WinDrv guest0x11104BF8, correct initial call0x11104BF5.
Guest frame=[return,viewport,width,height,fullscreen,color_bits]; renderer inECX.
Original RET20 means ESP+24 including return. No fixed dimensions/color/fullscreen
value is imposed by the observer. Nonzero UBOOL is success; zero is preserved
and reported as initial-setres-failed. Viewport/renderer/device/stack/ABI checks
remain. The recovery caller0x0696D2CD is not this initial-call boundary.
Candidate stop RVA0x{plan['stop_rva']:08X}, bytes{plan['stop_bytes'].upper()}, host CPU register
{plan['stop_registers']['cpu']}, return register{plan['stop_registers']['return_value']}. Independent original-x86/linked-x64
CFG analysis places it before P(11104BF8)/original TEST EAX,EAX, after checked
SetRes return. Candidate instructions executed:0.

continuation-plan.json prepares a maximum60-second, fresh unconsumed, no-retry
scope with file/module pins, independent permanent hardware breakpoint/readback
on every thread, bounded Job/watchdog, complete evidence, terminate-before-
continue, verified zero remaining processes and input/gamma restoration.
The proposal does not install this stop on a game or change production policy.
ready_for_physical_qualification=true; ready_for_genuine_launch=false.
The owner must restore/re-authorize an available physical fixture service and
qualify the final semantic runtime using the existing restoring gamma guard and
collector, then separately authorize the new candidate/correct initial endpoint.
Expired authorization and consumed candidates cannot be reused. There is no
launch-once command in this new helper directory. handoff-seal.json binds the
report, source, receipts, fixture evidence, candidate, PDB and dependencies.

8. REMAINING STARTUP/SAFETY LIMITATIONS

The following can still interrupt legitimate alternate paths and are explicit
implementation/qualification limits, not newly proven game defects:
  - Fullscreen/non-HAL/pure-device/non-FPU-preserve creation; conservative
    texture-cap dimension ceiling; uncharacterized presentation/format features.
    One actual native CreateDevice per process and teardown after failure remain.
  - Non-NULL textures/vertex/index buffers, owned programmable shaders, drawing,
    reset and other unimplemented device slots. These require typed resources
    and lifetime models before progress to a first rendered3D scene.
  - Present still accepts only four NULL optional arguments. Source/destination
    RECT, HWND override and dirty-region marshalling remain to implement.
  - Nonfinite material/matrix inputs and known unimplemented render features
    (line patterns/ZVISIBLE/Phong/patch/blend modes) diagnose before native work.
  - MapWindowPoints count1..4 uses a fixed host array; larger counts require
    dynamic typed marshalling. ClipCursor non-NULL RECT/restoration needs work.
    AttachThreadInput supports only the living current self-thread pair.
  - Registered private callback0xAE selectors8/9, theme0x90 parameters0,
    WM_GETDLGCODE non-NULL MSG, WM_NCPAINT regions and unknown pointer-bearing
    messages retain their existing scope/marshalling stops. Native callbacks
    modifying guest const inputs require separate ordering characterization.
  - Unbound alternate-branch USER32 imports: {', '.join(unbound)}.
    The audit does not claim those branches execute in expected windowed startup.
  - RegisterSoftwareDevice callback and GetAdapterMonitor HMONITOR need typed
    models. Unknown/stale/freed/wrong-owner COM/handle tokens remain fatal.
  - The measured first-S_OK Present sticky x87 PE adjustment is retained only
    in its existing pinned scope. Wider strict x87/WNDPROC/native-x86 equivalence
    remains FAILED. Narrow passing tests do not erase those verdicts.

preservation-after.json verifies the complete prior diagnosis package, production
runtime/generated sources, supervisor/policy/global ledger/hold and accepted
renderer/gamma packages unchanged. Protected snapshot inputs still match A.verify.
No original installation/save writes, genuine launch, remote push or release
occurred. This was not a full new census of every installation/save file.
The remaining substantive gate is physical promotion/owner authorization;
ordinary scalar profile admission has been replaced in the prepared scope.
'''
    # Keep prose legible while retaining exact instruction names/hex payloads.
    for old,new in {
        'stages0..7':'stages 0..7','stage0..7':'stage 0..7','one1540x945':'one 1540x945',
        'count=1/1540x945':'count=1 / 1540x945','depth0/stencil0':'depth 0 / stencil 0',
        'D3DDrv SetRes0696':'D3DDrv SetRes 0696','cache0697':'cache 0697','registration is0696':'registration is 0696',
        'WinDrv11104':'WinDrv 11104','and\n11104':'and\n11104','returns RET20':'returns RET 20',
        'bytes0/1':'bytes 0/1','arguments0':'arguments 0','payloads 1,2':'payloads 1, 2',
        'only2':'only 2','fields and native':'fields and native','registers,416':'registers, 416',
        'phases0/1/2/3':'phases 0/1/2/3','1536-byte ramps with flags0/1':'1536-byte ramps with flags 0/1',
        'windowed HAL combinations':'windowed HAL combinations','format0':'format 0',
        'PP52 guest/PP56':'PP 52 guest / PP 56','requiring120':'requiring 120',
        'caller,1540x945,DPI96,style/menu':'caller, 1540x945, DPI 96, style/menu',
        'selector0..2':'selector 0..2','repaint0/1/32':'repaint 0/1/32','DPI0/48':'DPI 0/48',
        'SetRes return. Candidate instructions executed:0':'SetRes return. Candidate instructions executed: 0',
        'Five live exact-candidate':'Five live candidate','main/new':'main/new','full4GiB':'full 4 GiB',
        'renderer-suite60s':'renderer suite 60 s','budget became180s':'budget became 180 s',
        'and hle_misc.obj; reused265':'and hle_misc.obj; reused 265','age1':'age 1',
        'the280-byte':'the 280-byte','including\nClear,Present,CreateDevice':'including\nClear, Present, CreateDevice',
        'guest0x':'guest 0x','call0x':'call 0x','inECX':'in ECX','RET20 means':'RET 20 means',
        'caller0x':'caller 0x','RVA0x':'RVA 0x','bytes895F44':'bytes 895F44',
        'registerrdi':'register rdi','registerrbx':'register rbx','maximum60-second':'maximum 60-second',
        'count1..4':'count 1..4','callback0x':'callback 0x','selectors8/9':'selectors 8/9',
        'theme0x90 parameters0':'theme 0x90 parameters 0','rendered3D':'rendered 3D',
        'first3D':'first 3D','DXVK3.1.1':'DXVK 3.1.1','bit-zero':'bit-zero',
        '4GiB':'4 GiB','(12 MoveWindow,12 WM_GETICON)':'(12 MoveWindow, 12 WM_GETICON)',
        ':24 positive':': 24 positive',',6 negative':', 6 negative',':2 positives,10':': 2 positives, 10',
        ':8 samples':': 8 samples','matrix cases,3 HRESULT':'matrix cases, 3 HRESULT',
        'of full':'of full','first-S_OK':'first S_OK'
    }.items():text=text.replace(old,new)
    (O/'REPORT.txt').write_text(text,encoding='utf-8')
    print('Comprehensive report and semantic-change register written.',flush=True)

if __name__=='__main__':main()
