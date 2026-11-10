"""Final offline audit and report. Does not launch any process under investigation."""
import importlib.util, json, re, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('post_final_preservation',HERE/'preserve.py');P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    p=P.read(P.O/'preservation.json');P.check(P.W,p['consumed_evidence']);P.check(P.W,p['original_sources'])
    P.check(P.B,p['build']['outputs'])
    for archive in p['archives']:assert P.sha(P.O/archive['path'])==archive['sha256']
    assert P.tree(P.SB)==P.read(P.O/'sandbox-manifest.json')['files']
    metadata={f.relative_to(P.SB).as_posix():dict(directory=f.is_dir(),size=f.stat().st_size,mtime_ns=f.stat().st_mtime_ns,
        attributes=getattr(f.stat(),'st_file_attributes',None)) for f in sorted(P.SB.rglob('*'))}
    P.save(P.O/'sandbox-metadata.json',metadata)
    sys.path.insert(0,str(P.W/'tools/xrt'));import asset_boundary
    assert asset_boundary.verify()==p['protected_assets']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=P.W)==(P.O/'git-head.txt').read_bytes()
    assert subprocess.check_output(['git','diff','--cached','--binary'],cwd=P.W)==(P.O/'git-staged.txt').read_bytes()
    original=P.read(P.OLD/'build.json')
    assert P.tree(P.W/'experiments/xrt/runtime')==original['runtime'] and P.tree(P.W/'experiments/xrt/gen')==original['generated']
    fixture=P.read(P.O/'init-audio-characterization.json')
    parsed=[]
    for row in fixture['runs']:
        assert row['exit']==0 and not row['timeout'] and 'cleanup passed' in row['stdout']
        m=re.search(r'InitAudio return ([0-9a-f]{8}) object=(\d) elapsed_ms=(\d+)',row['stdout']);assert m and m[1]=='00000000' and m[2]=='1'
        assert 'sandbox denied' not in row['stderr']
        parsed.append(dict(case=row['case'],hresult=m[1],object=True,native_elapsed_ms=int(m[3]),wdmaud_opens=row['stderr'].count('wdmaud.drv')))
    P.save(P.O/'characterization-audit.json',dict(passed=True,runs=parsed,consumed_failure_reproduced=False,
        compatibility_fix_justified=False,production_transport_timeout_ms=10000,helper_changed=False,runtime_changed=False,
        scope='Current executor only; owner Default-desktop probe is pending',genuine_sessions=0))
    # Re-run only the focused observer suite to retain its complete test transcript
    # in the package. The initial successful console run remains in chat history.
    cmd=[P.W/'.venv/Scripts/python.exe','-B','-I','-m','unittest','discover','-s',HERE,'-p','test_observer_evidence.py','-v']
    r=subprocess.run(list(map(str,cmd)),cwd=P.W,capture_output=True,timeout=20)
    (P.O/'observer-unit.stdout.txt').write_bytes(r.stdout);(P.O/'observer-unit.stderr.txt').write_bytes(r.stderr)
    assert r.returncode==0 and b'Ran 10 tests' in r.stderr and b'\nOK' in r.stderr
    P.save(P.O/'observer-unit.json',dict(passed=True,tests=10,exit=r.returncode,source_sha256=P.sha(HERE/'observer_evidence.py')))
    assert P.read(P.O/'observer-tests.json')['passed']
    prior=P.read(P.OLD/'gui-regressions.json');assert prior['passed']
    assert P.read(P.OLD/'fixture-audit.json')['passed']
    P.save(P.O/'gui-evidence-reuse.json',dict(passed=True,reason='No GUI/runtime implementation changed; source hashes are byte-identical',
        suites=prior['suites'],dpi96=prior['dpi96'],WM_GETOBJECT_prior_fixture=True,
        current_genuine_WM_GETOBJECT_return=P.read(P.O/'diagnosis.json')['relevant_events'][0] if False else next(e for e in P.read(P.O/'diagnosis.json')['relevant_events'] if e['kind']=='gui_get_object_callback_return')))
    strict=P.read(P.OLD/'strict-failures-retained.json');assert strict['x87']=='FAILED' and strict['wndproc_equality']=='FAILED'
    P.save(P.O/'strict-failures-retained.json',strict)
    old=(P.OLD/'bounded_genuine.py').read_text();new=(P.O/'bounded_genuine.py').read_text()
    assert new.replace("sandbox_cmp/postsplash-recovery-20261028-01","sandbox_cmp/getobject-recovery-20261028-01")==old
    owner=load('post_final_owner_verify',P.O/'bounded_owner.py');owner.verify()
    load('post_final_fixture_verify',P.O/'owner_fixture.py').verify()
    assert not (P.O/'genuine-owner-run').exists() and not (P.O/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    assert not (P.O/'owner-init-audio-run').exists()
    d=P.read(P.O/'diagnosis.json')
    report=f'''Unreal II post-splash fatal diagnosis — October 28, 2026 (US Eastern)

The exact historical %s string CANNOT be recovered from the retained records.
The observer saved its pointer, but not the pointed-to bytes, before terminating
the process. No dump/TLS-memory snapshot retains that buffer. Its Win32 suffix
and precise failure reason must not be invented. This is an observer evidence
omission in addition to a real startup transport failure, not a Python error
causing the game failure.

Proved fatal location and API
  Intended runtime exit: 76, XRT_EXIT_UNSUPPORTED
  Native caller: dm_backend_invoke, EXE return RVA 0x06f1c758
  Source: experiments/xrt/runtime/dmusic_backend_pipe.inc:8
  Call: xrt_fatal(c, 76, "%s", dm_backend_connection.error)
  String pointer: {d['string_argument_address']:#x}, thread-local error field +64
  Guest PC: 0x10481869, Engine.dll+0x181869
  Instruction: FF 91 B0 00 00 00, indirect call through vtable slot 44
  API: IDirectMusicPerformance8::InitAudio
  Arguments: this=0x151a8, ppDirectMusic=NULL, ppDirectSound=0x143c6b0c,
             HWND=NULL, path=8, channels=128, flags=0x3f, params=NULL
  The guest call did not return. No InitAudio HRESULT is established for this run.

The retained helper output confirms HELLO, Loader8 and Performance8 replies,
followed by repeated wdmaud.drv opens without an InitAudio reply. The last
debugger readback-to-fatal interval is about 10.004 seconds and the transport
deadline is 10000 ms. A deadline failure is supported, but not proved as the exact
unretained string. No unimplemented InitAudio method was bypassed.

This attempt's milestones only
  WM_GETOBJECT completed through the actual guest procedure (result 0, error 127);
  the startup dialog was created. The owner's splash observation is user-reported
  visual evidence only, not a captured rendered game frame.
  Entry LoadMap returned world 0x120a5000. CS_Intro PostLoad returned on world
  0x12f52800; 268 actor callbacks returned per lifecycle stage on that world.
  CS_Intro LoadMap is still pending: neither full actor initialization nor a
  selected-world LoadMap return is claimed. Engine Init and world ticks did not
  return. Script.Init was not reached.
  Direct3DCreate8(120), adapter IDs/count, caps and DXT queries completed. No
  D3D8 CreateDevice, Clear, Present or rendered game frame is established.
  All 25,840 runtime records exactly match the stopped-memory event snapshot,
  with contiguous sequence numbers and zero drops. The permanent 0x0696f292 stop
  passed all 16 readbacks and was not reached.

Validated change and characterization
  Observer only: copy bounded raw %s bytes while the fatal debug event is pending,
  without interpreting embedded percent characters. Unreadable or unterminated
  values remain explicit evidence failures. Actual CPU/stack and instance-bound
  output logging remain. Ten focused unit tests, two live non-game fatal probes
  and the independent terminate-before-instruction hardware-stop test pass.
  Native x86 InitAudio returns S_OK / real object in 281 ms; guarded native in
  265 ms; the unchanged production x86 helper over the real x64 IPC transport in
  265 ms. All clean up normally. These local probes do not reproduce the consumed
  owner failure or establish owner Default-desktop equivalence. No audio timeout,
  ownership, successful result, native call, GUI API or renderer method changed.
  Prior 18 GUI suites, both DPI96 fixtures and WM_GETOBJECT results are reused
  within their unchanged source scope. Strict x87 and complete WNDPROC equality
  remain FAILED and separately retained, with all original assertions unchanged.

Candidate identity (not rebuilt; runtime and generated sources are unchanged)
  EXE SHA-256: {original['binary_sha256']}
  PDB SHA-256: {original['pdb_sha256']}
  Path: {P.B/'xrt_ucc.exe'}
  The exact PE/PDB stop mapping is reverified. The conditional genuine diagnostic
  uses the existing permanent stop before guest 0x0696f292, one session, a fresh
  sandbox, 60-second runtime/debugger watchdogs and no retry. It is NOT launch-ready:
  a passing owner-desktop probe and separate genuine authorization are required.
  No genuine client ran during this task. No original installation/save changed.

Next owner action — NON-GAME probe only
  & "{P.O/'owner-init-audio.cmd'}"

This single-use command verifies the owner Default-desktop environment and bound
files, then runs the same three project-owned/native IPC probes with 14-second
parent limits and the unchanged 10-second transport limit. It preserves every
result and stops on failure. It never launches a genuine game or automatically
starts the prepared diagnostic continuation. The original consumed attempt must
never be retried. Return its result/STOP for review before another genuine launch.

Preservation: complete consumed sandbox (4,123 files, including directory/file
metadata), exact 279-object build/EXE/PDB, current source, full owner evidence,
all consumed markers and protected inputs are archived and SHA-256 verified.
Full records: diagnosis.json, native-disassembly.json, preservation.json,
characterization-audit.json, observer-tests.json, conditional-continuation.json.
'''
    # Check printed addresses against the actual retained argument frame.
    assert d['guest_arguments']['this']==0x151a8 and d['guest_arguments']['ppDirectSound']==0x143c6b0c
    (P.O/'REPORT.txt').write_text(report,encoding='utf-8')
    P.save(P.O/'final-integrity.json',dict(passed=True,consumed_evidence_unchanged=len(p['consumed_evidence']),complete_sandbox_unchanged=True,
        original_source_unchanged=True,runtime_and_generated_unchanged=True,build_unchanged=True,protected_assets_verified=True,
        observer_fix_qualified=True,unit_tests=10,live_debugger_cases=2,non_game_InitAudio_probes=3,strict_failures_retained=True,
        exact_consumed_string_unavailable=True,genuine_ready=False,owner_non_game_action_ready=True,genuine_sessions_launched=0))
    P.save(P.O/'new-source-manifest.json',P.tree(HERE))
    P.save(P.O/'artifact-manifest.json',P.tree(P.O))
    print('FINAL AUDIT PASS; OWNER NON-GAME ACTION READY; NO GENUINE GAME LAUNCHED',flush=True)
if __name__=='__main__':main()
