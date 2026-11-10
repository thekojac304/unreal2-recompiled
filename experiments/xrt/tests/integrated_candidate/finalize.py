"""Seal the integrated handoff only after every required non-GPU receipt passes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    names=('candidate-identity','contracts','windows-contracts','regressions','offline-checks',
           'stop-mapping','linked-adapters','control-flow','setres-independent-audit',
           'debugger-validation','composed-validation','construction-validation',
           'physical-package-audit','preservation-after')
    receipts={n:read(O/(n+'.json')) for n in names}
    assert all(r['passed'] for r in receipts.values())
    exe,sha,pdb=identity();runtime=core.tree(RT)
    assert all(receipts[n]['runtime']==runtime for n in ('contracts','regressions'))
    assert core.sha(exe)==sha and core.sha(exe.with_suffix('.pdb'))==pdb
    assert receipts['stop-mapping']['sha256']==receipts['linked-adapters']['sha256']==sha
    mapping=receipts['stop-mapping'];package=receipts['physical-package-audit']
    for name in ('continuation.py','observer.py','hardware_fixture.py','composed_fixture.c','composed_fixture.asm','stop_fixture.asm','qualify_composed.py'):
        assert receipts['composed-validation']['source'][name]==core.sha(H/name),name
    for name,digest in receipts['construction-validation']['observer_sources'].items():assert core.sha(name)==digest
    candidates=package['candidates'];assert len(candidates)==3
    batch=dict(prepared=True,submitted=False,executed=False,candidates=candidates,
        candidate_sha256=sha,process_count=3,per_process_timeout_seconds=60,
        profile='fast-development',formal_physical_acceptance=False,
        compare_command=[str(W/'.venv/Scripts/python.exe'),'-B','-I',str(H/'acceptance.py'),
                         '<native-x86-capture-directory>','<native-x64-capture-directory>','<translated-x64-capture-directory>'],
        conditions=['Owner physical console fixture authorization required; current service stopped/grant expired.',
                    'Exactly these three immutable fixtures, serial execution, no automatic retries.',
                    'Preserve raw evidence and legacy numerical-schema failures; supplemental audit cannot override them.',
                    'Stop on containment/integrity/environment failure. Genuine code is excluded.'],
        authorization_changed=False)
    save(O/'physical-batch.json',batch)
    continuation=dict(prepared=True,execution_authorized=False,observer_installed=False,
        candidate=str(exe),sha256=sha,pdb_sha256=pdb,guest_stop=GUEST,
        stop_rva=mapping['stop_rva'],stop_bytes=mapping['stop_bytes'],entry_rva=mapping['entry_rva'],
        mapping_file=str(O/'stop-mapping.json'),mapping_sha256=core.sha(O/'stop-mapping.json'),
        observer_sources={str(H/n):core.sha(H/n) for n in ('continuation.py','observer.py','hardware_fixture.py','common.py')},
        maximum_genuine_sessions=1,watchdog_seconds=60,retry=False,maximum_hardware_slots=4,
        boundary='After paired UGameEngine::Init normal return at 1038FBA9; before guest 1090ED5C CALL 10901370.',
        require_no_tick_events=True,require_terminated_before_continue=True,game_scene_claim=False,
        prerequisites=['Review physical package results and all retained strict failures.',
                       'Separate owner authorization for this exact candidate, staged composition and endpoint.',
                       'Activate the scoped observer through the existing owner-controlled supervisor path only.',
                       'Reverify identities/nonconsumption, FilePins, module allowlist, protected assets, fresh sandbox, Job, watchdog, environment and gamma cleanup.'],
        on_failure='Capture the first boundary/fatal or timeout, terminate/verify cleanup, retain evidence; no fix-and-relaunch loop.',
        active_supervisor_changed=False,genuine_launches=0)
    save(O/'continuation-design.json',continuation)
    tests=sum(r['tests'] or 0 for r in receipts['offline-checks']['results'])
    report=f'''UNREAL II INTEGRATED EXPERIMENTAL CANDIDATE — 2026-10-30

Prepared handoff complete. No genuine game or physical GPU fixture was executed.
No supervisor authorization, policy, service state, original asset or save changed.
The unsuccessful remote-console proof remains closed; no workaround was attempted.

CANDIDATE
{exe}
SHA256 {sha}
PDB SHA256 {pdb}
The completed surface-transfer executable is adopted unchanged. No runtime change,
relink or speculative D3D8 extension was warranted. All 279 object lineages,
headers, toolchain/dependency pins, PE/PDB identity, unconsumed status and 60 linked
adapter bindings independently verify. Reusing these exact bytes avoids creating
a second candidate with no demonstrated game fix.

AUDIT FINDINGS AND CONCRETE FIXES
1. Actual observer construction failed on its historical 40-byte D3D registry
   assertion. The staged instance now uses the exact 280-byte PDB layout, checks
   all field offsets and preserves full registry evidence. Actual construction
   succeeds without creating a process. Active supervisor source is untouched.
2. The old endpoint handler checked an address/CPU.rv but did not independently
   pair Init entry. The staged composition captures entry CPU/caller, verifies
   same host thread/CPU, engine object, ESP+4, nonvolatile guest registers,
   original caller/RET PCs, complete runtime call/return pair and no tick/fatal.
   Missing/corrupt evidence terminates while stopped. Four permanent hardware
   slots cover Init entry/return, fatal and pre-CreateDevice environment checking.
3. Uniform surface-copy pixels could not detect an ignored destination offset.
   Revised immutable fixtures use coordinate-dependent pixels and exact expected
   destination values; synthetic no-op and wrong-offset mutations are rejected.
   The parser also rejects absent resource outputs and an incorrect mip count.
4. The original InitAudio audit's next-export range included neighboring code.
   Original normal bodies end at InitAudio RET 10383A31 and Init RET 1038FBA9.
   ParseParam at 103839A1 reads UTF-16 nosound; JNE 103839AC skips construction.
   This preserves original control flow and does not erase earlier DirectMusic.
5. The existing physical collector's numerical schema is definitely incompatible
   with semantic/resource/transfer records. It remains unchanged. A separate
   read-only supplemental audit retains its failed verdict and reruns its exact
   process/desktop/module/GPU-ICD/Job/cleanup checks before three-way comparison.
   No parser result can confer formal acceptance or authorize genuine execution.

ORIGINAL ENGINE CONTROL FLOW
UGameEngine UObject vtable 10509B90 +74 resolves to original Init 1038F460.
OpenWindow call 1038FB16 returns at 1038FB1C; virtual +FC at 1038FB2B and
InitAudio 1038FB33 precede optional audio viewport association and destructors.
The linked stop RVA {mapping['stop_rva']:#x}, bytes {mapping['stop_bytes']}, is after the checked
Init return and before the guest 1090ED5C instruction. The original runtime emits
the Init return event inside xrt_icall before reaching that stop.
No additional definite game-startup blocker was established. Slot-offset matches
alone do not prove COM interface or first-frame reachability. Runtime changes: NONE.
Unknown conditional paths, callbacks and future unsupported methods remain open.

EXECUTED NON-GRAPHICAL VALIDATION
15331 cumulative resource/surface/scene checks on each of native x86 and x64.
DirectInput doubles and actual system result transfer pass; the independent
Acquire last-error 0 versus 5 discrepancy remains on both architectures.
Real USER32 native x86/native x64/translated differential: 24 operations,
56 callbacks, seven new rejection cases. Registered GUI/accessibility plus ten
existing rejection cases pass. Supervisor 81 and collector 105 tests pass.
{tests} isolated Python evidence/observer tests pass, including paired CPU corruption,
absent physical evidence, resource-output and rectangle-offset rejection.
Original PE/generated marker audits and historical SetRes 250-operation audit pass.
Owned non-game debugger tests pass: mapped candidate NO_EXECUTE, live DR readback,
new threads, four-slot limit, wrong bytes, observer-failure cleanup. Exact staged
composition passes success and three contained failure paths on owned protocol
code. The real candidate observer factory constructs with zero processes created.
Intermediate import-path, fixture-helper and obsolete-layout failures were resolved;
final isolated/fixed checks pass. Genuine endpoint execution remains unverified.

PHYSICAL GPU BATCH
physical-batch.json contains exactly three compiled immutable candidates.
Fixture recipes, executable/object/toolchain identities and recursive adapter
source expansion against the tested runtime verify. Scope: textures/mips, surface
ownership, VB/IB upload, FVF/declaration two-stream draws, index16/index32,
scene boundaries, render target/depth/viewport, Present, patterned rectangle
copies/readback, ABI and cleanup. Geometry is synthetic. ABI is outer-wrapper.
GetFrontBuffer only measures NULL-output failure; successful capture is unqualified.
The service is stopped, grant expired, no pending requests or safety latches.
Owner physical-console startup and fixture-only authorization remain prerequisites.
This focused three-process package is not the historical formal 23-process batch.

SEPARATELY AUTHORIZED GENUINE CONTINUATION
continuation-design.json pins the exact candidate, mapping and observer sources.
One future genuine session, 60-second limit, no retries, stop before 1090ED5C,
terminate while stopped, no main-loop tick admission. Physical review and separate
owner authorization precede activation. No runnable bypass/queue request is created.
First fatal/missing import/timeout stops the experiment; no repair-and-relaunch loop.

PRESERVED LIMITS
Physical acceptance, genuine completed Init and a genuine scene remain unverified.
Strict x87/full WNDPROC failures and independent DirectInput differences remain.
Prior runtime/candidates/evidence, production/generated code, original assets/saves,
both supervisor authorization trees and the closed remote-console evidence verify
unchanged. See OWNER-HANDOFF.txt for the two concrete future experiments.
'''
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    commands=[]
    for row in candidates:
        objective='Integrated resource/surface candidate: '+row['parameters']['arch']+' '+row['parameters']['variant']+'; synthetic GPU fixture only'
        commands.append(f'.venv/Scripts/python.exe -B -I tools/xrt/desktop_supervisor.py submit-test --candidate {row["candidate_id"]} --timeout 60 --objective "{objective}"')
    handoff='''TWO SEPARATE FUTURE EXPERIMENTS — PREPARATION ONLY

1. PHYSICAL GPU FIXTURES (no genuine code)
Owner starts the existing service from their physical local console, from
E:\\Unreal2-Port-Investigation, and completes its fixture-only authorization:
  .venv/Scripts/python.exe -B -I tools/xrt/desktop_supervisor.py serve-fixtures
No remote startup mechanism is supplied or authorized.
After identity recheck with package_audit.py, submit exactly these three fixtures
serially within that owner-authorized batch. These commands have NOT been run:

'''+ '\n'.join(commands)+'''

Retain each request ID, response, full capture directory and failed collector
numerical verdict. The old schema will reject the new records. Do not call the
historical submit-acceptance command. Do not retry a failed candidate automatically.
Run the read-only acceptance.py with the three captures/<fixture-name> directories
in native x86, native x64, translated x64 order. It checks actual physical-process,
backend/ICD, desktop, Job and cleanup evidence before raw comparison. Its result
is supplemental, never a replacement for a failed collector verdict. Review all
results and strict discrepancies before any genuine authorization decision.

2. ONE GENUINE INIT-RETURN CONTINUATION (separate owner authorization required)
The proposed approval scope is the exact SHA256 in continuation-design.json,
one fresh sandbox/session, unchanged original Init and -nosound profile, original
DirectMusic IPC dependency, 60 seconds, no retry, and termination before guest
1090ED5C. Main-loop ticks are excluded. No approval or launch occurred here.

After physical evidence review, the separately authorized integration can select
continuation.construct(out, pinned_mapping, environment_check, allowed_modules)
through the existing owner-controlled supervisor path. It retains BoundedLoop,
module checks, fatal evidence, Job/watchdog, FilePins and termination-before-continue.
The active scope/policy must not be silently reused for this later endpoint.
Reverify all identities, nonconsumption, assets/saves and environment; claim the
single authorized attempt durably. Require raw entry/endpoint CPU, exact event
pair, hard-stop.json, no tick events, zero remaining Job processes and desktop/gamma
restoration. First fatal or timeout is a terminal experiment result, not permission
to implement another adapter and retry. Preserve all evidence, including failures.
'''
    (O/'OWNER-HANDOFF.txt').write_text(handoff,encoding='utf-8')
    save(O/'milestone.json',dict(passed=True,scope='integrated experimental handoff',candidate_sha256=sha,
        runtime=runtime,tests_source=core.tree(H),receipts={n:core.sha(O/(n+'.json')) for n in names},
        deliverables={n:core.sha(O/n) for n in ('REPORT.txt','OWNER-HANDOFF.txt','physical-batch.json','continuation-design.json')},
        genuine_launches=0,physical_executions=0,runtime_modified=False,execution_authorized=False,
        formal_physical_acceptance=False,strict_compatibility='FAILED retained'))
    print('SEALED integrated candidate',sha,'with separate physical and genuine proposals',flush=True)

if __name__=='__main__':main()
