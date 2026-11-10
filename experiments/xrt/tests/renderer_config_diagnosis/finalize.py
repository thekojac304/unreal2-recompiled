"""Report and seal the investigated correction. Never launches or authorizes a game."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def run():
    core.require(not (O/'seal.json').exists(),'retain existing seal')
    from package import gates
    gates()
    from investigate import verify
    verify()
    b=read(O/'build.json');plan=read(O/'stop-mapping.json');table=read(O/'renderer-fields.json')
    generated=(W/'experiments/xrt/gen/d3ddrv/D3DDrv_000.c').read_text();start=generated.index('void f_696e890(CPU* c) {');end=generated.index('\n}\n',start)+3
    body=generated[start:end]
    core.require('wr32((uint32_t)(c->r[3] + 0x40d0u)' not in body and '0x40d0u),' not in body,'inspect possible SetRes field write')
    save(O/'diagnosis.json',dict(passed=True,classification='incorrect-profile-assumption-canonical-Boolean',
        root_cause='Hardcoded raw UseTrilinear=1 conflates enabled Boolean semantics with actual stored DWORD. Genuine entry stores 0x20; original consumes it as true.',
        demonstrated_entry_difference=dict(offset='0x40d0',width=4,expected=1,observed=32,source='UseTrilinear=True; original Core Boolean mask store and D3D nonzero consumer'),
        semantic_configuration_change=False,initialization_timing='Difference already present before SetRes prologue; original SetRes has no direct normalization-to-1 store at 0x40d0',
        exact_failed_time_value=None,failed_time_limit=table['evidence_limit'],
        game_or_renderer_defect_established=False,strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained',
        next_candidate_sha256=SHA,next_guest_stop=GUEST,native_allowlist_changed=False,genuine_launches=0))
    report=f'''Unreal II renderer configuration mismatch — investigated correction, preparation only

Conclusion and classification
The demonstrated error is a profile assumption: renderer+40D0 is UseTrilinear,
and enabled does not imply a stored DWORD equal to 1. The genuine raw entry
dump contains 20 00 00 00 (32), while the original profile generator hardcodes
1 at renderer_prerequisites/phase.py:95. Original Core ImportText ORs a Boolean
property's mask into a DWORD; original D3DDrv tests this DWORD for nonzero.
The original property registration names UseTrilinear and supplies offset 40D0.
The unchanged INI says UseTrilinear=True. No semantic configuration difference
or game/renderer implementation defect is established. A prior fixture seeded
synthetic objects from the same expected profile, so it did not independently
establish the genuine raw Boolean representation.

Exact recovered values — measured SetRes ENTRY, all DWORD widths 4
Offset    Expected    Observed     Expectation/provenance
40D0      00000001    00000020     UseTrilinear canonical-true assumption (wrong)
40D4      00000001    00000001     original mipmap capability branch, RVA DF4B
4124      00000001    00000001     INI LevelOfAnisotropy=1
412C      BF000000    BF000000     INI DefaultTexMipBias=-0.500000, float32 bits
41A0      00000010    00000010     measured D3DCAPS8 word27 at renderer+4134
41C8      00000008    00000008     measured caps word37
41CC      00000008    00000008     measured caps word38
41F0      00000010    00000010     measured caps word47, original clamp to16
4650      00000001    00000001     original NVIDIA vendor branch, RVA E472
0060      00000000    00000000     stencil-disabled profile, INI UseStencil=False
All ten expectations are literal fields in the old profile; the independent
configuration/capability/init sources supporting each are in field-sources.json.
The raw bytes, values, exact source path/hash and generator line are retained
per field in renderer-fields.json. Original expectations were not overwritten.

Evidence limits and timing
These ten exact observed values come from the complete renderer dump at SetRes
entry, before its guest prologue. The old aggregate check at the later material
boundary did NOT dump its field reads. Its first short-circuit term proves
40D0 was not 1 then; its exact later DWORD was not saved. Other non-caps fields
were not read after that failure. Four caps fields are additionally known to
match at failure because the preceding complete 53-word caps assertion passed.
No later field snapshot is fabricated from the earlier one. The demonstrated
canonical-Boolean expectation was already wrong at entry; there is no direct
normalization-to-1 store in the original SetRes body. The live UBoolProperty
object/mask itself was not captured, so its complete dynamic mask assignment
history is not claimed as measured evidence.

Identity, x86 widths and translation
Renderer receiver: 12E00000; viewport: 142D8600. The viewport's +5C field points
to that renderer. The original renderer vtable slot +78 resolves from preferred
1000E890 to translated SetRes 0696E890. The later saved SetRes frame local at
EBP-14 independently contains 12E00000 (offset192 in its raw stack snapshot).
Original instructions read DWORD fields; generated rd32 and observer u32 use
the same 4-byte little-endian values. Guest memory is addressed as 64-bit
xrt_g + uint32 guest address + offset. No wrong receiver, frame interpretation
or field-width evidence is found. The old log did not save the numeric xrt_g
host base; that numeric mapping cannot retrospectively be reported as measured.
The new observer explicitly logs full host/guest field addresses and tests high
guest addresses without host-pointer narrowing.

Actual SetRes frame, independently saved by runtime AND debugger
[11104BF8, 142D8600, 00000604, 000003B1, 00000000, 00000020]
The complete 416-byte CPU and 24-byte frame compare byte-for-byte across those
two saved sources. The runtime boundary is entry id1 at original site11104BF5;
there is no paired SetRes return record in this consumed run.

Latest genuinely completed milestone
SetRes guest instructions DID execute. Actual CreateDevice completed, followed
by Clear, Present, and eight SetRenderState calls. The last is (136,1), native
HRESULT 0 and last-error0, with its checked guest return at 0696F292. The saved
events end with that paired state return. A retained native/bridge/CPU/FPU audit
on independent evidence copies passes for these operations.
The observer next stopped at the SetMaterial bridge entry, guest site0696F31D,
before the bridge body or native SetMaterial call. No SetMaterial, configured
238-call sequence, ResizeViewport or initial SetRes completion is claimed.
Termination-before-continue and Job cleanup left zero processes. No new genuine
game launch occurred during this investigation.

Independent characterization and precise correction
12 disposable native-x86/lifted comparisons execute exact original Boolean-store
and sampler-decision instruction fragments embedded in an OWNED DLL. Mask1,
mask32 and mask128, enabled/disabled and mipmap combinations compare identically.
False cases clear a previously set mask. Raw32 plus mipmaps=1 selects the SAME
already measured sampler MIPFILTER tuple value2 as canonical true1. These tests
execute neither the original game EXE nor original game DLLs, and create no D3D
device. Existing independent native D3D tuple measurements remain applicable;
no new native method or tuple is admitted.
The revised exact profile changes ONLY fields[40D0] from 1 to32. It does not
normalize arbitrary nonzero values. The isolated runtime guard makes the same
one-literal correction; raw1,2,64 and0 remain rejected in x86/x64 guard fixtures.
The 237 base tuples plus gamma retain the exact 238-call runtime profile. The
batch_cases.inc bytes and all ordered call/return/profile logic are unchanged.
No guest field, original INI, installation or save is changed to satisfy checks.

Evidence-first observer improvement
At each profile boundary, raw CPU/frame and object/caller identities are saved
first. Every required field and all53 caps words get individual durable records
with expected/observed/raw bytes, widths, 64-bit host and guest addresses, read
errors and expectation provenance. Renderer, viewport/device binding and vtable
are recorded. All reads finish before aggregate evaluation; one failing field
cannot hide later fields. Multiple mismatches are reported individually.
Invalid bases, unreadable pages and unknown configurations stop diagnostically.
Evidence-write failures also stop before native work or resumption. There is no
automatic acceptance, guest-memory write, configuration forcing or native D3D8
allowlist broadening. The owner reports such failures as diagnostic stops and
still consumes the attempt, preserves its hold and never retries it.

Validation and fresh candidate
21 observer/owner tests pass, including multiple simultaneous mismatches, invalid
bases, unreadable fields, vtable identity, high-address translation, evidence-write
failures and the complete 239-operation+resize controller sequence.
81 production supervisor tests pass. 6 live debugger field/negative cases prove
complete field capture or preserved write-failure prefix, terminate-before-
continue and verified cleanup. 5 live exact-candidate-mapping/hardware cases
plus retained factory/fatal tests pass; the candidate is mapped NO_EXECUTE and
its instructions/entrypoint are never run. Native/lifted characterization and
exact x86/x64 guard contracts pass as described above.

Fresh candidate: {EXE}
EXE SHA-256: {SHA}
PDB SHA-256: {PDB}
One hle_gui.obj is recompiled because it includes the corrected profile guard;
278 verified objects are reused. All279 object/source/header/transitive records,
strict compile/link commands, dependencies and PE/PDB identity verify. This is
a source-justified correction, not an identity-only rebuild. The consumed
3ca2c42a... executable remains consumed and was never retried.
Same proposed guest stop11104BF8; exact candidate RVA {plan['stop_rva']:08X},
bytes {plan['stop_bytes'].upper()}, before P(11104BF8)/TEST EAX,EAX. No supervisor
breakpoint or policy expansion occurred. Fresh candidate instructions executed:0.

Preservation, risks and readiness
The original failed result/assertion, complete attempt/debugger/runtime records,
candidate/PDB, complete sandbox, global ledger and source state are preserved
with content inventories; complete attempt and selected identity evidence also
have independent copies. Installation/saves, prior packages, production sources,
policy and breakpoint behavior verify unchanged. Global hold remains sequence88.
Strict x87, WNDPROC and native-x86 compatibility failures remain FAILED, separately
retained under preserved/strict-failures. Narrow owned fixture results do not
pass those broad compatibility gates.
The real later field values, remaining native operations, callbacks, driver
effects and SetRes return remain genuine compatibility risks until a new bounded
attempt measures them. Unknown values must stop. The missing failing-time field
reads are not reconstructed as measured. No push or release occurred.

The same-boundary one-shot owner continuation is prepared only if
seal-validation.json says passed. No launch is authorized by preparation. The
owner must separately authorize the existing stop scope and the new candidate,
with a 60-second maximum, fresh sandbox, file/module pins, exclusive locks,
independent watchdog, permanent stop, Job cleanup and input/gamma restoration.
Ordinary local owner console, only after checking the verified seal:
& '{W / '.venv/Scripts/python.exe'}' -B -I '{H / 'owner.py'}' launch-once
The two new local phrases printed by that console are:
{STOP_PHRASE}
{PHRASE}
Neither phrase, owner command, queue submission nor genuine launch was used
during preparation. Any changed ledger/evidence, STOP, consumed identity or
different endpoint rejects the action. No automatic retry or global hold reset.
'''
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    from supervisor.service import seal_files
    from supervisor.qualify import host_files
    from supervisor import fixture_profiles
    fixture_profiles.modules()
    import owner,graphics_backend
    files={str(W/p):v for p,v in seal_files().items()}
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            path=pathlib.Path(path).absolute()
            if path.is_file() and path.is_relative_to(W):files[str(path)]=core.sha(path)
    for root in [H,O,EXE.parent,RT,W/'experiments/xrt/gen']:
        files.update({str(root/p):v for p,v in core.tree(root).items()})
    ci=read(O/'candidate-identity.json')
    for record in {str(O/'object-lineage.json'),*ci['transitive_object_records']}:
        files[record]=core.sha(record)
        for value in read(record).values():
            if not isinstance(value,dict) or 'command' not in value:continue
            files[value['source']]=value['source_sha256'];files.update(value.get('verified_local_headers',{}))
            obj=next((s[3:] for s in value['command'] if s.startswith('/Fo')),None)
            if obj:files[obj]=value['object_sha256']
    files.update(ci['dependencies']);files.update(b['toolchain']);files.update(host_files())
    for p,v in read(O/'resolved-hold.json')['evidence'].items():files[p]=v
    for name in ['configuration-profile.json','physical-gamma-audit.json','actual-gamma-ramp.bin']:
        files[str(PRIOR/name)]=core.sha(PRIOR/name)
    save(O/'seal.json',dict(passed=True,scope=SCOPE,candidate_sha256=SHA,pdb_sha256=PDB,guest_stop=GUEST,stop_rva=RVA,stop_bytes=plan['stop_bytes'],
        maximum_launches=1,maximum_seconds=60,retry=False,genuine_authorized=False,genuine_launches=0,owner_phrase=PHRASE,separate_stop_phrase=STOP_PHRASE,
        implementation=core.tree(H),files=files,dependencies=ci['dependencies'],strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained'))
    owner.validate_seal();owner.execution_gate()
    save(O/'seal-validation.json',dict(passed=True,files=len(files),seal_sha256=core.sha(O/'seal.json'),candidate_unconsumed=True,
        ready_for_separate_owner_action=True,genuine_launches=0,genuine_authorized=False,production_policy_breakpoints_unchanged=True,
        local_owner_authorization_pending=True))
    print('DIAGNOSIS AND CORRECTION SEALED. Same-boundary fresh owner continuation prepared; zero genuine launches.',flush=True)


if __name__=='__main__':run()
