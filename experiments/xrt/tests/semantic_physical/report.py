"""Record a blocked qualification honestly; no submit or launch capability."""
import json
import time
from pathlib import Path
from recheck import OUT, PRIOR, HERE, WORK, core


def main():
    identity = core.read_large(OUT / 'candidate-identity.json')
    mapping = core.read_large(OUT / 'stop-mapping.json')
    linked = core.read_large(OUT / 'linked-adapter-audit.json')
    observer = core.read_large(OUT / 'live-observer-validation.json')
    hardware = core.read_large(OUT / 'debugger-validation.json')
    tests = core.read_large(OUT / 'final-observer-tests.json')
    preservation = core.read_large(OUT / 'preservation-after.json')
    for receipt in (identity, mapping, linked, observer, hardware, tests, preservation):
        core.require(receipt['passed'], 'non-graphical prerequisite failed')
    core.require(identity['sha256'] == mapping['sha256'] == linked['sha256'] == hardware['candidate_sha256'], 'candidate binding')
    states = {}
    for name in ('desktop-fixtures', 'desktop-prerequisites'):
        path = WORK / 'out' / name / 'status.json'
        value = core.read(path)
        states[name] = dict(state=value['state'], expired=value['batch']['expires_at'] <= time.time(),
                            batch=value['batch'], status_sha256=core.sha(path))
    # This report describes this blocked session only. A running service requires
    # returning to actual qualification, never emitting a stale blocked verdict.
    core.require(all(s['state'] == 'stopped' and s['expired'] for s in states.values()), 'service availability changed; resume qualification')
    matrix = [
        dict(domain='CreateDevice', valid=['zero dimensions/count/format defaults', '640x480 and 800x600', 'software/hardware/mixed VP with FPU preserve', 'windowed/depth BOOL 1 and 32', 'distinct focus/presentation HWND; one NULL HWND', 'live-supported color/depth/MSAA combinations'],
             invalid=['conflicting VP flags', 'invalid swap/count/MSAA combination', 'unsupported live color/depth combination', 'both HWNDs NULL (translated guard only)'],
             evidence=['native HRESULT and last-error', 'raw PP before/after and output pointer/token', 'preflight query sequence', 'window pins, pending refs, CPU/native ABI', 'one actual creation per process; failure teardown']),
        dict(domain='Render/texture-stage states', valid=['BOOL 0, 1, 2, 32, 128, 0x80000000, 0xffffffff', 'live-supported blend/compare/stencil/cull/fog', 'stages 0 and 7; point/linear/anisotropic filters within live caps', 'finite positive/negative LOD bias; anisotropy 1 and supported maximum'],
             invalid=['unknown enum', 'stage 8', 'known capability-absent operation'],
             evidence=['unmodified input scalars', 'actual result/error', 'GetRenderState/GetTextureStageState readback', 'persistent device state and references']),
        dict(domain='Material/transform/null resources/FVF', valid=['finite nonidentity matrix', 'finite material and power 0/8', 'NULL textures at stages 0/7', 'NULL stream with nonzero stride within caps', 'NULL indices with nonzero BaseVertexIndex', 'FVF 0x152 and 0x244 if supported'],
             invalid=['nonfinite matrix/material (translated guard only)', 'unknown resource token (translated guard only)', 'out-of-range stream/stage', 'unowned shader handle (translated guard only)'],
             evidence=['typed copies and unchanged input bytes', 'typed native readback', 'CPU, native GPR/XMM/FPU controls and separately recorded status', 'COM final releases']),
        dict(domain='Clear and gamma', valid=['0 and 2 rectangles', 'target/depth/stencil combinations supported by created surfaces', 'depth -0, 0.5, 1', 'copied ramps with flags 0 and 1'],
             invalid=['invalid Clear flags/depth/count range', 'unreadable guest array (translated guard only)'],
             evidence=['Clear result/error and target readback where implemented', 'gamma has no HRESULT; preserve EAX', 'GetGammaRamp bytes', 'parent-owned desktop ramp save/restore/reread on every outcome']),
        dict(domain='Parent factory/queries and callbacks', valid=['SDK 120 and measured alternate SDK behavior', 'CheckDeviceType and CheckDeviceMultiSampleType supported and unsupported tuples', 'real owned-window callbacks during creation and cleanup'],
             invalid=['safe invalid query enums', 'stale COM/window identity (translated guard only)'],
             evidence=['real NULL/failure and last-error propagation', 'callback nesting and suspended CPU', 'paired event stream', 'zero Job processes, windows and final COM refs'])
    ]
    core.atomic(OUT / 'pending-physical-matrix.json', dict(prepared_at=time.time(), executed=False,
        variants=['native x86', 'native x64', 'translated x64 actual semantic adapters'],
        runtime_admission='semantic domains and live caps; this sample matrix is not an admission allowlist',
        invalid_pointer_rule='Never send fabricated host pointers to native COM; invalid guest tokens/ranges test translated guards only',
        cases=matrix, collector_work_remaining='Add and qualify broader evidence parsing/family support; the historical formal collector intentionally retains its original samples. Gamma requires the restoring service.'))
    plan = dict(version=1, status='BLOCKED_PHYSICAL_QUALIFICATION', launch_package_sealed=False,
        candidate=identity['executable'], candidate_sha256=identity['sha256'], unconsumed=identity['consumption']['unconsumed'],
        proposed_initial_call='0x11104BF5', proposed_stop='0x11104BF8', stop_rva=mapping['stop_rva'], stop_bytes=mapping['stop_bytes'],
        maximum_launches=1, maximum_seconds=60, retry=False, genuine_authorized=False, genuine_launches=0,
        production_stop='0x0696F292 unchanged', physical_fixtures_run=0, physical_qualified=False,
        owner_requirements=['Start/re-authorize the physical fixture service locally; no game authorization.',
            'After broadened physical qualification passes, separately approve this candidate and the one-shot initial SetRes stop scope.',
            'Use only a newly sealed semantic continuation launcher after its owner gate and containment are qualified; historical launchers bind different candidates/profiles.'],
        strict_failures=dict(x87='FAILED retained', WNDPROC='FAILED retained', native_x86='FAILED retained'))
    core.atomic(OUT / 'continuation-readiness.json', plan)
    text = f'''UNREAL II SEMANTIC PHYSICAL QUALIFICATION - BLOCKED CHECKPOINT
2026-10-30 America/New_York

Physical GPU result: NOT RUN / NOT QUALIFIED. Both saved physical services are
stopped and their four-hour grants have expired. Zero graphics fixture requests
were submitted by this task. Zero genuine launches; zero candidate instructions.
The required local owner startup was requested; no response has been received.

Fresh verified candidate: {identity['executable']}
SHA-256: {identity['sha256']}
PDB SHA-256: {identity['pdb_sha256']}
PE/PDB GUID: {identity['pe_pdb']['guid']}, age {identity['pe_pdb']['age']}.
279 objects: 265 reused generated, 12 reused runtime, two rebuilt runtime units
(hle_gui.obj and D3D-owning hle_misc.obj). Actual linked implementations and all
{len(linked['hle_bindings'])} HLE table bindings independently reverified. Full source/header/object/
link/PE/PDB/toolchain/dependency inventory and consumption checks pass.
No actual runtime correction was identified; no replacement candidate built.

Fresh non-game qualification:
- All 630 prior sealed files match their existing seal.
- 15 final observer tests PASS: actual error transfer protocol, noncanonical
  BOOL, CPU/native ABI corruption, callback nesting, evidence-first failures,
  correct initial caller and separate nonzero success/zero failure outcomes.
- 12 live owned protocol cases PASS: scalar/native failure/material/matrix/
  gamma/Clear/callback/creation/null-focus/creation failure/CPU corruption/
  evidence-write failure. These are COM doubles, not physical GPU evidence.
- Five owned hardware/mapping cases PASS, plus retained production-observer
  fixtures. Candidate mapped SEC_IMAGE_NO_EXECUTE; main/new-thread hardware
  readback, reserved-slot overflow, wrong-byte and observer-failure handling
  terminate before continuation. Every fresh fixture cleanup reports zero
  remaining Job processes. Normal guest cleanup is not inferred from a kill.
- Proposed endpoint RVA 0x{mapping['stop_rva']:08X}, bytes {mapping['stop_bytes']};
  verified before guest 0x11104BF8, after initial call at 0x11104BF5 and RET20.
  This qualifies owned fixtures and inert mapping, not a hit in the real game.

The preserved earlier 373-case x86/x64 adapter contracts and GUI regressions
retain their original scope. Previously measured renderer/gamma GPU data is
byte-preserved and is not promoted to broader semantic GPU coverage. No new
native-x86/native-x64/translated physical comparison, physical HRESULT/error,
readback, FPU, callback, COM or gamma-restoration verdict is available.
No new GPU compatibility discrepancy has been established without those runs.
Historical strict x87, full WNDPROC equality and native-x86 failures remain FAILED.

Collector coverage finding: the ordinary service admits its fixed families;
formal group_observations still validates the old cases.json and fixed ordered
stream. The gamma extension admits only its restoring gamma family. Rerunning
those old samples cannot certify the newly broadened runtime. The pending matrix
records representative valid/invalid domains and evidence requirements. Broader
fixture/family/parser implementation and qualification remain pending; no
assertions were weakened or replaced with inferred passes.

Preservation freshly PASS: production runtime/generated sources, complete
supervisor code and production home (including ledger/hold), prior diagnosis,
accepted renderer and gamma packages, and protected snapshot input hashes.
No original installation/save modification, remote push or release.

Owner action now (ordinary PowerShell on the signed-in physical desktop):
  Set-Location 'E:\\Unreal2-Port-Investigation'
  & '.\\.venv\\Scripts\\python.exe' -B -I '.\\tools\\xrt\\desktop_supervisor.py' serve-fixtures
At its local console enter:
  AUTHORIZE DISPOSABLE FIXTURES FAST AND FORMAL
Leave the console open and report that it is waiting. This grants no game launch.
The console requirement comes from FIXTURE_SERVICE.md and development.serve;
this task cannot substitute a saved/expired grant or use another desktop.

Genuine SetRes action: NONE READY NOW. Physical qualification must pass first.
Then the owner must separately authorize exactly this unconsumed candidate,
one attempt of at most 60 seconds, no retry, and the independent permanent stop
before guest 0x11104BF8. Production's 0x0696F292 stop remains unchanged. The
single genuine continuation package has NOT been sealed or declared ready.
Do not invoke historical owner.py launchers: they bind other candidate/profile
identities, and are not a launch path for this semantic candidate.

Remaining risks: broader native backend behavior and live-cap rejection paths;
physical invalid-domain results; creation defaults and PP mutation; real callback
ordering; fresh CPU/FPU/COM/readback and gamma/input restoration evidence;
unimplemented typed resources, drawing/reset and non-default Present arguments;
separate local owner authorization and qualified semantic one-shot launcher.
'''
    (OUT / 'REPORT.txt').write_text(text, encoding='utf-8')
    files = {str(p): core.sha(p) for p in HERE.glob('*.py')}
    files.update({str(OUT / n): h for n, h in core.tree(OUT).items() if n != 'checkpoint-seal.json'})
    core.atomic(OUT / 'checkpoint-seal.json', dict(passed=True, qualification_complete=False,
        physical_qualified=False, genuine_authorized=False, candidate_sha256=identity['sha256'], files=files))
    print(OUT / 'REPORT.txt')


if __name__ == '__main__':
    main()
