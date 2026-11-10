"""Offline acceptance and integrity report; executes no fixture or owner phase."""
import difflib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run as R

W,O=R.W,R.O
load=lambda p:json.loads(p.read_text())
assert load(O/'production-final/differential.json')['passed']
assert load(O/'production-ansi/differential.json')['passed']
assert load(O/'regressions02/summary.json')['passed']
gui=R.RT/'hle_gui.c';before=O/'source-before'/gui.relative_to(W)
assert gui.read_bytes()==R.candidate(before.read_bytes().decode()).encode()
(O/'production-change.diff').write_text(''.join(difflib.unified_diff(before.read_text().splitlines(True),gui.read_text().splitlines(True),fromfile='preserved/hle_gui.c',tofile='runtime/hle_gui.c')))
R.save(O/'render-smoke/classification.json',dict(process_exit=0,post_run_assertion='FAILED: expected spontaneous DPI-96 callback was absent',passed_full_smoke=False,interpretation='successful observed Clear/Present/capture; cannot establish spontaneous DPI-96 delivery',subsequent_evidence='render-smoke-forced explicitly injects exact callback after native Present'))

diagnostics=[]
for run in load(O/'wndproc02/results.json'):
    rows=run['rows'];ptr={r['tag']:r for r in rows if r['kind']=='pointer'}
    pre=ptr['before-first-present'];post=ptr['after-first-present-immediate']
    assert pre['is_original'] and not post['is_original']
    assert pre['base']+pre['rva']==pre['pointer']
    assert post['base']+post['rva']==post['pointer']
    assert Path(post['module']).name.lower()=='opengl32.dll'
    assert pre['module_error']==post['module_error']==0
    call=next(r for r in rows if r['kind']=='present');assert call['hr']==0 and call['callbacks_during']==0
    forward=[r for r in rows if r['kind']=='forward']
    assert len(forward)==(1 if run['window_first'] else 2)
    for f in forward:
        assert f['installed_result']==f['previous_result']==0x12340037
        assert f['marker_callbacks']==2 and f['last_error']==0x5555 and f['icon_result']==f['null_result']==0
        cb=[r for r in rows if r['kind']=='callback' and r['phase']==f['tag']]
        assert [r['message'] for r in cb]==[0x8037,0x8037,0x7f,0]
        assert cb[2]['wp']==1 and cb[2]['lp']==96
    cb=[r for r in rows if r['kind']=='callback']
    destroy=next(r for r in cb if r['message']==2)
    nc=next(r for r in cb if r['message']==0x82)
    assert destroy['installed_enter']==destroy['installed_leave']==post['pointer']
    assert nc['installed_enter']==nc['installed_leave']==pre['pointer']
    if not run['window_first']:
        assert all(ptr[tag]['pointer']==post['pointer'] for tag in ['after-device-release','after-parent-release','after-backend-unload'])
    assert not any(0x100<=r['message']<=0x109 or 0x200<=r['message']<=0x20e for r in cb)
    cleanup=next(r for r in rows if r['kind']=='cleanup')
    assert cleanup['device_release']==cleanup['parent_release']==cleanup['foreign_callbacks']==0
    assert not cleanup['window_valid'] and not cleanup['d3d8_loaded'] and not cleanup['d3d9_loaded']
    diagnostics.append(dict(arch=run['arch'],window_first=run['window_first'],before=pre,after=post,previous_reachable=True,tested_forwarding_passed=True,restored_on_device_release=False if not run['window_first'] else None,restored_before_nc_destroy=True,destroy=destroy,nc_destroy=nc,first_present_callbacks=0,input_callbacks=0,cleanup=cleanup))
R.save(O/'wndproc02/audit.json',dict(passed=True,runs=diagnostics,owner='opengl32.dll entrypoint; installer call stack not measured',scope='these fixtures, both architectures and both cleanup orders; no universal subclass safety claim'))

smoke=load(O/'render-smoke-forced/summary.json');assert smoke['passed'] and smoke['actual_dpi96_callbacks']==1
report=load(O/'render-smoke-forced/client/report.json');ev=report['events']
idx=lambda name:next(i for i,e in enumerate(ev) if e['kind']==name and (name!='test_native_leave' or e.get('method')=='Present'))
assert idx('test_native_leave')<idx('test_exact_icon_enter')<idx('gui_get_icon_callback_return')<idx('test_exact_icon_leave')
assert not any(e['kind']=='fatal' for e in ev)
assert all(e['all_cpu_bytes'] for e in ev if e['kind']=='test_suspended_render_cpu')
observations=[json.loads(s) for s in (O/'render-smoke-forced/client/run.stdout.txt').read_text().splitlines() if s.startswith('{')]
assert next(r for r in observations if r['kind']=='window_capture')['rgb_fnv64']=='15897038bc069195'

manifest=load(O/'initial-manifest.json');changed=[];missing=[]
for name,v in manifest.items():
    p=W/name
    if not p.exists():missing.append(name)
    elif R.sha(p)!=v['sha256']:changed.append(name)
allowed={'experiments/xrt/runtime/hle_gui.c','experiments/xrt/tests/geticon_dpi96/run.py'}
assert not missing and set(n.replace('\\','/') for n in changed)<=allowed,(missing,changed)
R.save(O/'final-integrity.json',dict(passed=True,existing_files_checked=len(manifest),missing=missing,changed=changed,allowed_changes=sorted(allowed),existing_binaries_and_evidence_unchanged=True))

acceptance=dict(icon_native_translated='PASS',production_dpi96='PASS',ansi_and_unicode=True,measured_nonzero_dpi={'selector':1,'dpi':96},previous_dpi_zero_support_retained=True,unmeasured_cases='explicit exit 76',wndproc_diagnostic='PASS within measured scope',wndproc_owner='opengl32.dll',restored_before_nc_destroy=True,affected_regressions='4 PASS',observed_render_smoke='PASS with separately labelled forced DPI96 callback',strict_native_x86='FAILED, preserved',strict_original_wndproc_equality='FAILED, preserved; lifecycle now characterized',general_x87='not reopened',full_render_acceptance='INCOMPLETE; no 93-process rerun',capture_only_resumption='YES in a fresh disposable phase; strict acceptance remains blocked',genuine_game_launches=0,owner_phases_rerun=0,commits=0,pushes=0)
R.save(O/'acceptance.json',acceptance)

lines=['Unreal II — focused WM_GETICON DPI-96 compatibility fix','2026-10-27, America/New_York','',
'WM_GETICON native x86 / translated differential: PASS.',
'Production DPI-96 support: PASS. Exactly selector 1 / DPI 96 is newly supported.',
'DPI is forwarded unchanged; NULL and two typed non-NULL HICON results agree.',
'ANSI and Unicode SendMessage, direct host callbacks, three last-error seeds,',
'callback-written last-error, stdcall/return checks, nonvolatile GPR sentinels,',
'one nested callback, whole suspended CPU and 16-byte frame checks pass.',
'Each final differential has 24 guest sends + 24 host sends, 72 callback returns;',
'nine explicit negative cases trap. Prior selector 0..2 / DPI 0 support remains.',
'Unmeasured selectors and nonzero DPIs remain unsupported. No x87 code changed.','',
'Affected regressions: geticon_boundary, gui_boundary, class_boundary, setfocus_boundary PASS.',
'Existing icon suite retains 1,156 samples / 4,048 callback log records and three negatives.',
'All builds use fresh output paths. Existing fixture binaries are unchanged.','',
'WNDPROC diagnostic: native x86 and x64; no-input first-Present baseline;',
'both device-first and window-first cleanup orders. First Present returns S_OK,',
'with zero callbacks during the native call. The replacement is visible immediately',
'after Present, before readback or capture. It belongs to opengl32.dll, not a',
'DXVK module. This attributes the entrypoint; the installer call stack was not measured.','']
for r in diagnostics:
    if r['window_first']:continue
    a,b=r['before'],r['after']
    lines += [f"{r['arch']} device-first:",f" original pointer=0x{a['pointer']:x}, base=0x{a['base']:x}, RVA=0x{a['rva']:x}",f" original module={a['module']}",f" replacement pointer=0x{b['pointer']:x}, base=0x{b['base']:x}, RVA=0x{b['rva']:x}",f" replacement module={b['module']}",f" first Present end={b['ms']:.3f} ms from process timing origin",'']
lines += ['The previous procedure remains directly callable through CallWindowProc.',
'The installed procedure forwards a diagnostic scalar message, WM_GETICON(1,96)',
'and WM_NULL, including expected return values and seeded last-error. These',
'checks pass after Present and after device release. No input or foreign-thread',
'callbacks occurred. The replacement persists after device/parent release and',
'DXVK unload. WM_DESTROY still sees the replacement; WM_NCDESTROY sees the',
'original installed on both entry and exit, in all four runs. Restoration is',
'therefore observed before the original WM_NCDESTROY callback. Backend unload',
'and COM releases finish, then the window is invalid. This characterizes the',
'tested lifecycle; it does not prove arbitrary-message or universal safety.','',
'Observed translated render smoke: PASS in a fresh executable using preserved',
'observed objects, with the new GUI object and an explicitly labelled test-only',
'WM_GETICON(1,96) send after native Present leaves and before capture. The callback',
'returns, suspended CPU and 24-byte Present frame remain intact, Clear/Present',
'pair and return S_OK, PrintWindow completes with expected black RGB hash',
'15897038bc069195, and cleanup exits 0. No production renderer source changed.',
'The unforced smoke also exits 0 and captures output, but delivers no spontaneous',
'DPI96 callback; its post-run expected-callback assertion remains failed. It is',
'not used as evidence of natural DPI96 delivery.','',
'Strict x87 verdict: FAILED and unchanged. The preserved assessment identifies',
'15 distinct native x86 first-Present PE failures: FSW 3000 remains 3000 while',
'the original assertion requires 3020. Historical native-versus-translated PE',
'discrepancy and prior CreateDevice/general x87 uncertainties remain unresolved.',
'This task did not rerun or investigate them. The original WNDPROC equality',
'assertion also remains FAILED: lifecycle characterization does not rewrite it.',
'Full translated render acceptance remains INCOMPLETE.','',
'Capture resumption: YES for fresh disposable capture-only diagnostics. The',
'specific DPI96 blocker is resolved and the tested WNDPROC forwarding/restoration',
'is established. This is not strict renderer acceptance or genuine-game eligibility.',
'No consumed owner phase or complete 93-process matrix ran. No game, Android',
'work, renderer expansion, unrelated refactoring, commit or push occurred.','',
'Preservation: initial-manifest.json binds 3,071 existing files; final-integrity.json',
'rechecks them. Only hle_gui.c and this task\'s new run.py changed among those',
'files. Original sources are copied in source-before/. Original line endings',
'are preserved; production-change.diff contains exactly the three changed lines.',
'All old binaries, evidence, failed captures and strict audits remain unchanged.',
'Also retained: candidate host-test overread failure (exit 74), isolated regression',
'comparison path SyntaxError, and the unforced smoke post-run assertion failure.',
'Their corrected/new runs use separate directories and do not replace failures.','',
'Raw records: production-final/, production-ansi/, regressions02/, wndproc02/,',
'render-smoke-forced/. Exact pointers, module/base/RVA, callback arguments,',
'timing, stdout/stderr, build commands, source/output identities and audits are',
'stored there. acceptance.json separates focused success from strict failures.']
(O/'REPORT.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(acceptance,indent=2))
