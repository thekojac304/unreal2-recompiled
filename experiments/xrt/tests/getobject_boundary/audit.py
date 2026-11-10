"""Offline acceptance and final preservation. No game or fixture launches."""
import difflib, importlib.util, json, re, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('wm_audit_phase',HERE/'phase.py');F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
O=F.O;W=F.W

def dependencies():
    source=W/'out/recovery/d3d8-clear-present-20261025-01/dependency-identities.json'
    d=F.read(source)
    for key in ['toolchain','system_inputs','libraries']:
        for path,h in d[key].items():assert F.sha(path)==h,(key,path)
    for path,entries in d['headers'].items():assert F.tree(Path(path))==entries,path
    F.save(O/'dependency-verification.json',dict(passed=True,source=str(source),sha256=F.sha(source),
        toolchain=len(d['toolchain']),system_inputs=len(d['system_inputs']),libraries=len(d['libraries']),headers=sum(len(v) for v in d['headers'].values())))
    print('PINNED COMPILER / SYSTEM / HEADER / LIBRARY INTEGRITY PASS',flush=True)

def fixture():
    d=O/'qualified-fixture';b=F.B/'qualified-fixture'
    n=(d/'x86-native.stdout.txt').read_text();x=(d/'x64-native.stdout.txt').read_text();t=(d/'positive.stdout.txt').read_text()
    assert n==x==t and t.endswith('cleanup passed\n')
    assert sum(r.startswith('sample ') for r in t.splitlines())==18
    assert sum(r.startswith('callback ') for r in t.splitlines())==45
    assert sum(r.startswith('accessible ') for r in t.splitlines())==3
    assert t.count('release 1 window_alive=1')==3
    assert 'x86 callback ABI count=27 failures=0' in (d/'x86-native.stderr.txt').read_text()
    assert 'x86 callback ABI count=27 failures=0' in (d/'positive.stderr.txt').read_text()
    for arch in ['x86','x64']:
        assert F.read(d/(arch+'-native.json'))['exit']==0
    assert F.read(d/'positive.json')['exit']==0
    assert F.sha(b/'x86/getobjectprobe.dll')==F.read(b/'gen/getobjectprobe_meta.json')['sha256']
    r=F.read(d/'report.json');assert r['exit_code']==0 and r['events_dropped']==0
    es=r['events'];callbacks=[e for e in es if e['kind']=='gui_get_object_callback_return']
    assert len(callbacks)==15 and all(e['wparam']==0xffffffff and e['object_id']==0xfffffffc and e['result']==0 for e in callbacks)
    assert sum(e['kind']=='fixture_callback_abi' and e['passed'] for e in es)==27
    for name in ['object','wparam','upper','nonzero']:
        r=F.read(d/(name+'-report.json'));assert r['exit_code']==76 and not r['events_dropped']
        fatal=next(e for e in r['events'] if e['kind']=='fatal');assert 'WM_GETOBJECT:' in fatal['message']
    # The baseline runtime's rejection, before the implementation, is retained.
    baseline=F.read(O/'baseline-rejection.json');assert baseline['exit_code']==76
    assert any(e['kind']=='fatal' and '0x3d unsupported' in e['message'] for e in baseline['events'])
    F.save(O/'fixture-audit.json',dict(passed=True,native_x86_x64_translated_text_equal=True,stdout_line_endings='Native CRLF and translated LF; decoded records compared exactly',
        samples_each=18,callback_records_each=45,real_accessibility_queries_each=3,callback_abi_checks=27,explicit_guards=4,
        returned_role=18,role_variant_type=3,returned_state=1081344,children=0,window_identity=True,actual_Release_returned_zero=True,
        default_dialog_processing=True,accessibility_provider='real Windows fallback, not guest or fixture object',events_dropped=0,
        raw_x64_object_id_representations=['0x00000000fffffffc','0xfffffffffffffffc'],genuine_sessions=0))

def finalize():
    p=F.read(O/'preservation.json')
    F.check(F.OLD,p['diagnosis_artifacts']);F.check(W,p['consumed_evidence'])
    sb=p['consumed_sandbox'];assert F.tree(Path(sb['root']))==sb['files']
    original=F.read(O/'source-before.json')
    allowed=['experiments/xrt/runtime/hle_gui.c','experiments/xrt/tests/getobject_boundary/phase.py']
    F.check(W,{rel:h for rel,h in original.items() if rel not in allowed})
    changed=[rel for rel,h in original.items() if F.sha(W/rel)!=h];assert set(changed)==set(allowed),changed
    prior_sources=F.read(F.PREP/'preserved-manifest.json')
    F.check(W,{rel:h for rel,h in prior_sources.items() if rel not in ['experiments/xrt/runtime/hle_gui.c','experiments/xrt/CURRENT_STATUS.md']})
    assert (W/'experiments/xrt/CURRENT_STATUS.md').read_bytes().endswith((F.PREP/'source-before/experiments/xrt/CURRENT_STATUS.md').read_bytes())
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W).decode().strip()==(F.OLD/'git-head.txt').read_text().strip()
    assert subprocess.check_output(['git','diff','--cached','--binary'],cwd=W)==(F.OLD/'git-staged.txt').read_bytes()
    for name,args in [('head',['rev-parse','HEAD']),('status',['status','--porcelain=v1','-uall']),('unstaged',['diff','--binary'])]:
        (O/('git-'+name+'-final.txt')).write_bytes(subprocess.check_output(['git',*args],cwd=W))
    F.check(W/'experiments/xrt/build/renderer-init-preparation-20261027-01',F.read(F.PREP/'build.json')['outputs'])
    before=(O/'source-before/experiments/xrt/runtime/hle_gui.c').read_text();after=(W/'experiments/xrt/runtime/hle_gui.c').read_text()
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='hle_gui.c at phase start',tofile='hle_gui.c candidate'))
    assert sum(line.startswith('+') and not line.startswith('+++') for line in diff.splitlines())==21
    assert not any(line.startswith('-') and not line.startswith('---') for line in diff.splitlines())
    (O/'implementation.patch').write_text(diff)
    fixture()
    assert F.read(O/'gui-regressions.json')['passed'] and F.read(O/'observer-qualified.json')['passed']
    build=F.read(O/'build.json');F.check(Path(build['root']),build['outputs'])
    assert F.tree(W/'experiments/xrt/runtime')==build['runtime'] and F.tree(W/'experiments/xrt/gen')==build['generated']
    assert build['compiled_objects']==279 and build['reused_objects']==0
    compiler=Path(build['commands'][0]['command'][0])
    assert F.sha(compiler)==F.read(F.PREP/'candidate-lineage-preparation.json')['compiler_sha256']
    assert F.read(O/'dependency-verification.json')['passed']
    rsp=Path(build['root'])/'link-objects.rsp';objects=[Path(x.strip('"')) for x in rsp.read_text().splitlines() if x.strip()]
    assert len(objects)==len(set(objects))==279 and all(f.is_relative_to(Path(build['root'])/'obj') and f.is_file() for f in objects)
    sys.path.insert(0,str(W/'tools/xrt'));import asset_boundary
    assert asset_boundary.verify()==p['protected_assets']
    prior=W/'out/recovery/renderer-init-owner-acceptance-20261028-01'
    F.check(F.PREP,F.read(prior/'preserved-owner-evidence.json'))
    F.check(prior,F.read(prior/'artifact-manifest.json'))
    strict=W/'out/recovery/owner-color-verified-20261027-01/strict-limitations.json'
    failed=F.read(strict);assert failed['strict_compatibility']=='FAILED'
    F.save(O/'strict-failures-retained.json',dict(x87='FAILED',wndproc_equality='FAILED',original_assertions_unchanged=True,source=str(strict),sha256=F.sha(strict),findings=failed))
    # Verification only: this entry point has no execution effect.
    owner=F.load('wm_final_owner_verification',O/'bounded_owner.py');owner.verify()
    assert F.read(O/'continuation-prepared.json')['passed']
    assert not (O/'genuine-owner-run').exists() and not (O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    F.save(O/'final-integrity.json',dict(passed=True,consumed_evidence_unchanged=len(p['consumed_evidence']),consumed_diagnosis_unchanged=True,
        consumed_sandbox_unchanged=True,prior_build_unchanged=True,protected_assets_verified=True,earlier_pending_work_preserved=True,
        production_change='hle_gui.c only; 21 added lines',fresh_compiled_objects=279,reused_objects=0,link_response_verified=True,
        strict_failures_retained_separately=True,genuine_sessions=0,prepared=True))
    report=f'''Unreal II WM_GETOBJECT startup recovery — October 28, 2026 (US Eastern)

Prepared for the next owner-launched bounded continuation. No genuine game ran.
The consumed October 28 session, complete sandbox, executable/PDB, raw evidence,
diagnosis archives and previous owner acceptance remain unchanged.

Native x86, native x64 and translated x86 fixture records agree exactly after
stdout CRLF/LF decoding: 18 sends/default-processing samples and 45 callback
records per side. Both zero-extended and sign-extended x64 OBJID_CLIENT forms
reach the guest as fffffffc. wParam remains 00000000ffffffff. The genuine-style
dialog procedure really executes and returns FALSE. SendMessageW and DefDlgProcW
then return Windows' actual zero; DefWindowProcW's direct baseline also returns
zero. Seeded last-error 1234 is retained; callback-written 5678 is retained.
The nested WM_GETTEXTLENGTH call returns the real caption length 17 at depth 2.

Three actual AccessibleObjectFromWindow calls per side return S_OK and real
Windows IAccessible objects: VT_I4 role 18 (dialog), state 1081344, zero children,
matching HWND. Actual Release returns zero; HWND stays alive until DestroyWindow.
The first accessibility call clears last-error to zero; later calls preserve
1234 or callback-written 5678 identically on all sides. No object, success or
marshalling result is invented. Native x86 and translated callbacks pass 27 ABI
checks; translated callback stack, nonvolatile and x87 state checks pass.

Production change: 21 added lines in hle_gui.c, in two blocks. Only the measured
Unicode dialog WM_GETOBJECT tuple is admitted, using the existing guest callback
and Windows dialog manager. Unsupported object IDs/wParam/upper bits and nonzero
guest callback results remain fatal (four negative cases pass). SendMessage's
guest API whitelist is unchanged. No renderer or x87 implementation changed.

The instance-bound observer correction is integrated into the fresh package.
Two live non-game debugger tests recover early fatal arguments, CPU, every
available guest-stack word up to 40, and the exact instance output directory,
then terminate before the fatal body. Seven unit tests pass, including all six
original assertions and a new stack-top bound test. The independent execute
breakpoint test passes with readbacks and termination before its instruction.
The final genuine observer is constructed offline with the correction installed;
all prior strict checks and the permanent 0x0696f292 algorithm are retained.

Regressions: 18 affected GUI/dialog/class/callback/input/module suites pass;
both ANSI and Unicode DPI96 comparisons and all 18 DPI negatives pass. No renderer
matrix, genuine game or unrelated hardware/x87 investigation was rerun. Earlier
strict x87 and complete WNDPROC equality remain FAILED, separately preserved.

Client: {Path(build['root'])/'xrt_ucc.exe'}
SHA-256: {build['binary_sha256']}
PDB SHA-256: {build['pdb_sha256']}
All 279 objects compiled serially and linked fresh; zero object reuse. Source,
generated units, compiler, link paths/objects, protected assets and pinned helper/
backend identities verify. No C1001/D8040 occurred. Exact fresh PE/PDB disassembly
maps the required stop before guest 0x0696f292; no execution beyond it is permitted.

Routine fixture repairs are preserved: initial compiler-environment setup;
get_accName reaching existing guarded WM_GETTEXT (name querying removed from this
focused fixture); a stack-top observer read; a wrong fixture/lift pairing rejected
by the unchanged hash guard (each actual pair verified against its own metadata);
and a DPI output directory outside its disposable workspace. No mismatch in the
measured final native/translated behavior or protected-input integrity was found.

Next owner command, from the owner's normal desktop:
& "{O/'owner-genuine-getobject.cmd'}"

It revalidates pinned inputs, source/build/package hashes and owner environment,
creates a fresh sandbox, and allows one session with a 60-second watchdog and no
automatic retry. It logs early fatals to that new session, reserves the permanent
hardware stop before guest 0x0696f292, and retains all strict x87/WNDPROC failures.
After any failure or stop, preserve the attempt; do not reuse the consumed tree.
Preparation stops here. No engine/world/renderer milestone is advanced.
'''
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    F.save(O/'artifact-manifest.json',F.tree(O))
    print('FINAL PRESERVATION AND PREPARATION PASS; NO GAME LAUNCHED',flush=True)
if __name__=='__main__':dependencies() if len(sys.argv)>1 and sys.argv[1]=='dependencies' else finalize()
