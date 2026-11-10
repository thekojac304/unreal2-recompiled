"""Seal the prepared non-game phase and verify live/history preservation."""
import difflib,json,shutil,sys,time
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
W,O=P.W,P.O

def main():
    # Descriptive schemas follow the separately qualified preview protocol.
    sdir=O/'enforcement/supervisor'
    for path in sdir.glob('*.json'):
        text=path.read_text().replace('renderer-init-before-0696f292','renderer-init-before-0696f323').replace('out/desktop-supervisor/candidates','out/material-preview/candidates')
        path.write_text(text)
    sys.path.insert(0,str(O/'enforcement'))
    # This interpreter already imported the active package through phase. Load the
    # preview verifier in its own interpreter; never mix authorization namespaces.
    P.R.execute([W/'.venv/Scripts/python.exe','-B',P.H/'verify.py'],O,'final-candidate-verification',timeout=60)
    p=P.read(O/'preservation.json');q=P.read(W/'out/material-preview/qualification.json');v=P.read(O/'candidate-verification.json')
    assert v['qualification_digest']==P.core.digest(q)
    for key in ['native-audit.json','translated-audit.json','regression-audit.json','prior-audit.json','live-material-observer.json']:
        assert P.read(O/key)['passed']
    assert P.core.tree(W/'experiments/xrt/runtime')==p['production_runtime']
    assert P.core.tree(W/'tools/xrt/supervisor')==p['production_enforcement']
    assert P.core.sha(W/'out/desktop-supervisor/ledger.jsonl')==p['ledger_sha256']
    assert (W/'out/desktop-supervisor/status.json').read_bytes()==(O/'preserved/status.json').read_bytes()
    assert (W/'out/desktop-supervisor/qualification.json').read_bytes()==(O/'preserved/qualification.json').read_bytes()
    for path,expected in p['trees'].items():
        path=Path(path);assert (P.core.tree(path)if path.is_dir()else P.core.sha(path))==expected
    for m in p['consumed']:
        assert P.core.sha(W/m['executable'])==m['sha256']and P.core.sha((W/m['executable']).with_suffix('.pdb'))==m['pdb_sha256']
    strict=p['strict_failures'];assert P.core.sha(strict['source'])==strict['sha256']
    d=O/'preserved/strict-originals';d.mkdir(exist_ok=True)
    for name in [strict['source'],*strict['findings']['preserved_sources']]:
        path=Path(name);shutil.copy2(path,d/path.name)
    for name,h in strict['findings']['preserved_sources'].items():assert P.core.sha(name)==h
    protected=P.A.verify();assert protected==p['protected']
    status=P.read(W/'out/desktop-supervisor/status.json');rows=P.core.Ledger(W/'out/desktop-supervisor/ledger.jsonl').rows
    used=sum(r['kind']=='launch-claimed'and r['batch_id']==status['batch']['id']for r in rows)
    assert used==2 and status['batch']['scope']=='renderer-init-before-0696f292'
    assert not list((W/'out/desktop-supervisor/requests').glob('*.json'))and not list((W/'out/desktop-supervisor/processing').glob('*.json'))
    assert not (W/'out/material-preview/ledger.jsonl').exists()
    plan=P.read(O/'debugger-plan.json');guest=P.read(O/'guest-disassembly.json')
    patches=''
    for path in sorted(sdir.rglob('*')):
        if path.is_file()and path.suffix in ['.py','.json']:
            relative=path.relative_to(sdir);original=W/'tools/xrt/supervisor'/relative
            before=original.read_text().splitlines(True)if original.exists()else[]
            patches+=''.join(difflib.unified_diff(before,path.read_text().splitlines(True),fromfile='active/'+relative.as_posix(),tofile='preview/'+relative.as_posix()))
    (O/'enforcement.patch').write_text(patches)
    shutil.copy2(W/'out/material-preview/qualification.json',O/'supervisor-qualification.json')
    P.save('strict-failures.json',dict(x87='FAILED',wndproc_equality='FAILED',strict_native_x86_compatibility='FAILED',historical_source=strict['source'],historical_source_sha256=strict['sha256'],
        copied_record='preserved/strict-failures-retained.json',
        fixture_initial_status_difference=dict(native_fsw='0x3100',translated_fsw='0x3000',method_preserves_each=True,records='fixtures-v2'),
        fninit_037f_refused=True,fninit_evidence='fixtures-v3/client-translated-production-0-0-18-0/result.json',
        final_fixture_seed='FNCLEX, FLDCW 027f, two live values, FTST; no runtime x87 change',no_waiver=True))
    P.save('fixture-development-failures.json',dict(retained=True,allocator_overlap='fixtures/client-translated-production-5-0-18-0/result.json',
        initial_status_mismatch='fixtures-v2',unsupported_fninit='fixtures-v3',
        observer_dependency_rejection='live-material-observer',
        supervisor_initial_failures='preview-home/qualification-* (syntax replacement and recovery worker/path length)',
        all_final_checks_passed=True,none_are_genuine_attempts=True))
    P.save('final-integrity.json',dict(passed=True,production_runtime_unchanged=True,production_enforcement_unchanged=True,
        successful_attempt_complete_evidence_unchanged=True,consumed_candidates_unchanged=True,production_ledger_unchanged=True,
        production_status_and_qualification_unchanged=True,protected_inputs=protected,strict_failures_separate=True,
        used_genuine_attempts=used,unused_old_capacity=3,old_batch_expired=time.time()>status['batch']['expires_at'],
        no_production_queue_item=True,preview_batch_not_started=True,preview_ledger_not_created=True,
        current_supervisor_status=status,genuine_launches=0,genuine_requests=0,
        final_qualification=q['evidence'],qualification_digest=P.core.digest(q),
        candidate=v,live_material_observer=P.read(O/'live-material-observer.json')))
    expiry=datetime.fromtimestamp(status['batch']['expires_at'],timezone.utc).isoformat()
    report=f'''Unreal II: SetMaterial development phase prepared and non-game qualified
October 29, 2026, America/New_York

No genuine game was launched, and no genuine request was submitted.
The production runtime, enforcement sources, ledger, qualification and stopped
status are byte-for-byte unchanged. The old scope still stops before 0x0696f292.
The old batch has 2/5 launches consumed and 3 unused; it expired at {expiry}.
Those unused slots were neither spent nor carried into the proposed new policy.

Next measured boundary
Call: guest 0x0696f31d = D3DDrv.dll+0xf31d, FF 91 A8 00 00 00.
Return/permanent stop: BEFORE guest 0x0696f323 = D3DDrv.dll+0xf323.
Original next instruction: mov eax,[ebp-0x14]. It must not execute.
The next SetRenderState(148,1), at guest 0x0696f336, remains unsupported.
Original PE preferred base is 0x10000000; the verified lifted base is 0x06960000.
The original bytes and generated source agree (guest-disassembly.json).

Exact new PE/PDB mapping
EXE: experiments/xrt/build/d3d8-material-20261029-01/client/xrt_ucc.exe
EXE SHA-256: {v['pe_sha256']}
PDB SHA-256: {v['pdb_sha256']}
PE RSDS and actual PDB info stream GUID: {v['rsds_guid']}, age {v['pdb_age']}.
Function: {plan['function']}; native stop RVA {v['native_stop_rva']}.
Preferred native VA: {v['native_stop_preferred_va']}; live ASLR VA = module base + RVA.
Stop bytes: 89 7e 44 (mov dword ptr [rsi+0x44],edi).
RSI is the guest CPU; EDI is 0x0696f323. The checked xrt_icall return and RV
comparison immediately precede the stop. The PC store and following guest MOV
have not executed. Live genuine installation of this mapping is untested.
Fourteen runtime objects were freshly compiled; 265 unchanged generated objects
were individually verified, with complete source/object/link lineage for all 279.
The executable is fresh and unconsumed. Both prior candidates remain consumed.

Supported operation contract
HRESULT IDirect3DDevice8::SetMaterial(const D3DMATERIAL8*), vtable slot 42.
Guest offset 0xa8; x64 native offset 0x150. Guest COM stdcall has stack words
[return, this, material]; RET_STD(2) consumes 12 bytes including the return.
Native dispatch uses the typed WINAPI function pointer and Windows x64 ABI.
Only the live device registry identity created by the measured CreateDevice is
accepted. SetRes reloads that same device field [renderer+0x4698]. The successful
old run's exact guest/native device identities are retained in prior-audit.json.

The 68-byte layout is four RGBA float vectors followed by float Power:
Diffuse=(0.5,0.5,0.5,1); Ambient=(1,1,1,1);
Specular=(0,0,0,0); Emissive=(0,0,0,0); Power=+0.
Only those exact 17 IEEE-754 words are admitted. The complete readable range is
checked across pages and copied into a typed local structure. Guest memory is
never passed to the host. Read-only input is supported and remains unchanged.
The actual pinned DXVK call returns S_OK, preserves four last-error seeds,
nonvolatile registers, controlled x87/live values and MXCSR. The readback oracle
is fixture-only: GetMaterial remains unsupported in production. Native NULL
returns D3DERR_INVALIDCALL, but NULL is outside this narrow production contract.

Guards and qualification
The staged bridge changes only three runtime files (runtime.patch). All 88 other
unsupported device traps remain; SetRenderState still admits exactly eight
previously measured tuples. COM identities, references, parent-first lifetime,
window/thread pins, memory checks, callback context, reentrancy, Release during
rendering, window destruction, process containment and ABI guards are retained.
No general x87 implementation, original installation, save, remote or release
change was made. Runtime edits exist only in this phase's staged runtime/ tree.

PASS: 12 native x86/x64 processes, 48 material calls, exact readbacks, NULL/zero
characterization, four error seeds, ABI/FPU/input/identity/cleanup checks.
PASS: 35 native/translated material fixture processes, including read-only and
guarded last-word cross-page inputs, unknown/stale/wrong-type/NULL devices,
unreadable/NULL/NaN/nonmatching material, unsupported GetMaterial, parent-first
lifetime, forced nested callbacks and fail-closed Release/reentry/destroy cases.
PASS: 37 focused regression processes: eight states across all three paths,
CreateDevice/Clear/Present, ABI cases and neighboring negative guards.
PASS: actual new production material observer branches on a disposable fixture;
native/bridge pairing, whole suspended CPU/frame/input, host ABI, hardware slot
readbacks, stream/stopped-memory equality and terminate-before-continue verified.
That fixture uses a terminal sentinel; genuine SetRes register binding is mapped
offline, not claimed live exercised. See live-material-observer.json.
PASS: all 47 supervisor tests and full non-game safety qualification, including
persistent queue, replay/consumption rejection, watchdog, child cleanup, local
stop, fatal observer, module/file pins, helper isolation and two independent
recovery iterations. Original and later stop addresses and the old scope are
rejected by the preview; all historical consumed hashes are rejected.
Qualification: {q['evidence']}
Qualification digest: {P.core.digest(q)}
All completed safety cases leave zero Job processes. The physical owner gate
must still pass in the owner's normal session.

Preservation and strict failures
The complete successful second attempt, both consumed binaries/PDBs and build
identities, earlier reports, strict records and production ledger are copied in
preserved/. Independent raw event/ABI auditing verifies CreateDevice, Clear,
Present and all eight state returns: (7,1),(9,2),(29,0),(26,1),(143,1),(48,0),
(35,3),(136,1). All 75,898 records equal stopped memory, with zero drops.
Fresh old-candidate PE/PDB resolution independently verifies the old breakpoint.

STRICT X87: FAILED. COMPLETE WNDPROC EQUALITY: FAILED.
STRICT NATIVE X86 COMPATIBILITY: FAILED. These are not waived by material tests.
The material fixture's initial FSW difference and rejected FNINIT 037f remain
recorded separately. Final fixtures explicitly seed supported 027f/live values
and FTST; they establish the material operation only. See strict-failures.json
and preserved/strict-originals/. Setup/recovery qualification failures are also
retained separately in fixture-development-failures.json.

Owner review and later authorization steps (NOT executed)
1. Review runtime.patch, enforcement.patch, candidate-verification.json,
   debugger-plan.json, the qualification above and separate strict-failure record.
2. Explicitly approve this exact candidate, the new stop BEFORE 0x0696f323,
   adoption of this separate enforcement preview and ONE new 60-second attempt.
   The current development approval does not authorize that launch.
3. After approval, use a normal physical owner PowerShell in this workspace:
   & '.\\.venv\\Scripts\\python.exe' -B '.\\out\\recovery\\d3d8-material-20261029-01\\enforcement\\owner_start.py'
   If an old supervisor is still active, stop it normally first. The saved one
   was already stopped at preservation time. owner_start requires an interactive
   console, verifies the qualification and unchanged production history, carries
   the entire production ledger forward and holds the original global exclusion
   lock for its entire life. It does not modify or resume the old batch. It asks
   for fresh local authorization of one attempt under the reviewed policy.
4. Only after that authorization, submit exactly this reviewed build from a
   second owner PowerShell:
   & '.\\.venv\\Scripts\\python.exe' -B '.\\out\\recovery\\d3d8-material-20261029-01\\enforcement\\command.py' submit-renderer --build-record 'out/recovery/d3d8-material-20261029-01/build.json' --objective 'Verify the measured SetMaterial return; stop before guest 0x0696f323'
   Submission must bind the new scope, fresh batch, candidate/source/PDB/build/
   dependency identities and permanent endpoint. No reset, consumed retry or
   carryover of the three unused old slots is permitted. Any production-history
   or sealed-source drift requires renewed review/qualification.
5. Stop after that single bounded result and inspect raw runtime/debugger pairs,
   SetMaterial identity/input/native/bridge return, permanent-stop readback,
   zero-drop stream, terminate-before-continue, cleanup and protected inputs.
   No further renderer operation, Init return, tick or gameplay is authorized.

Preparation is complete. No owner command above was run in this development task.
'''
    (O/'REPORT.txt').write_text(report)
    P.save('delivery-inventory.json',dict(phase_files=P.core.tree(O),fixture_sources=P.core.tree(P.H),
        candidate_outputs=P.core.tree(Path(P.read(O/'build.json')['root'])),preview_qualification_sha256=P.core.sha(W/'out/material-preview/qualification.json'),
        no_genuine_launch=True))
    print('FINAL PRESERVATION AND PREPARATION SEAL PASS',flush=True)

if __name__=='__main__':main()
