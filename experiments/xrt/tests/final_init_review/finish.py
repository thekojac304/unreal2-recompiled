"""Seal the review, never authorization. No candidate/graphics execution."""
from pathlib import Path
import sys,hashlib,json,time
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import review as R
from review import O,BASE,W,P,C,core,read,save

def main():
    R.configure();b,_=R.verify()
    from reader import decode
    checks=[]
    for r in read(BASE/'record-checks.json')['completed_traces']:
        p=Path(r['path']);core.require(core.sha(p)==r['sha256'],'retained trace identity')
        rows,valid=decode(p);core.require(valid['active_invocations']==0,'unpaired invocation')
        core.require(valid==r['integrity'],'independent decode mismatch')
        checks.append(dict(path=str(p),sha256=core.sha(p),integrity=valid))
    mutations=[];root=Path(read(BASE/'record-checks.json')['root'])
    for r in read(BASE/'record-checks.json')['mutations']:
        p=root/(r['field']+'.bin');core.require(core.sha(p)==r['sha256'],'mutation pin')
        try:decode(p)
        except ValueError as e:mutations.append(dict(field=r['field'],rejection=str(e)))
        else:raise AssertionError('CRC-valid substitution accepted')
    save(O/'independent-record-review.json',dict(passed=True,completed_traces=checks,total_records=sum(r['integrity']['records'] for r in checks),semantic_substitutions_rejected=mutations,baseline_runtime_verified=True))
    for n in ('owned-checks.json','exact-objects-protocol.json','predevice.json','preservation-review.json'):
        core.require(read(O/n)['passed'] is True,'incomplete '+n)
    package=read(O/'physical-plan.json');plan=package['plan']
    for p,d in package['inputs'].items():core.require(core.sha(p)==d,'physical package stale '+p)
    core.require(core.sha(plan['executable'])==plan['sha256'],'owned host stale')
    core.require(not (O/'physical-consumed.json').exists(),'unexpected physical execution')
    env=read(O/'environment-review.json');core.require(not env['passed'] and env['processes_launched']==0,'unexpected construction environment')
    from supervisor.windows import BoundedLoop
    observer=dict(candidate_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        sources={str(p):core.sha(p) for p in [P/'composition.py',P/'observer.py',P/'prepare_candidate.py',P/'debugger_handles.py',W/'tools/xrt/supervisor/observer.py',W/'tools/xrt/supervisor/windows.py',H/'review.py']},
        isolated_loop_sha256=hashlib.sha256(BoundedLoop.experimental_run_source.encode()).hexdigest(),
        runtime={n:core.sha(C.RT/n) for n in ('monitor.c','monitor.h','monitor.asm','xrt_loader.c','hle_misc.c')},
        permanent_candidate_rvas=read(O/'candidate-observer-preparation.json')['critical_rvas'],
        physical_owned_host_sha256=plan['sha256'],physical_owned_host_pdb_sha256=plan['pdb_sha256'])
    save(O/'observer-identities.json',observer)
    policy=dict(id='final-experimental-init-review-v1',state='PROPOSED_NOT_ACTIVATED',approval=False,
        candidate_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],observer_identity_sha256=core.sha(O/'observer-identities.json'),
        limits=dict(launches=1,seconds=60,retry=False,normal_records=131072),
        endpoint=dict(guest='0x1090ED5C',host_rva='0x6a0160f',bytes='895f44',before_instruction=True),
        retained_strict_verdicts='All five reviewed categories remain FAILED. Experimental outcome never implies strict compatibility.',
        required_before_authorization=['Review complete saved owner physical evidence for this package and candidate runtime object equivalence; a relinked owned host is not the loaded candidate PE.',
            'Owner explicitly disposes each reviewed difference and the unresolved consumer risk; this review cannot approve it.',
            'Review exact genuine observer integration of the physical graphics/native-state checks; the current genuine review object still refuses run.',
            'Revalidate candidate/source/PE/PDB/dependency identities, nonconsumption, fresh sandbox and protected assets before a separately authorized single attempt.'],
        monitoring=['Four permanent hardware slots: fatal, monitor failure, Init endpoint, CreateDevice environment; all-thread and new-thread DR readbacks.',
            'Keep every existing memory/page-range, unsupported-operation, object generation/reference, HWND/callback/return and filesystem check.',
            'Keep typed native arguments/results/errors, guest CPU and probe FPU state, actual message/callback identities, and explicit abort/omission events.',
            'Evidence first at controlled critical/fatal/environment/native-exception stops. Preserve disk prefix, counters, bounded tail and pending attempt independently.',
            'HLE GetLastError invocations are recorded by the dispatcher; direct TEB reads and inline x87 instructions are not individually monitored or stopped. This limitation must be accepted explicitly or remain blocking.'],
        stop_conditions=['Identity/environment/driver/device/graphics tuple drift; extra native device attempt; unknown native procedure/module or lifetime violation.',
            'Any existing runtime fatal, unsupported operation, invalid pointer/range, bad return, callback corruption or unexpected reentry.',
            'Unexpected native HRESULT/error or FPU/CPU effect outside the specifically approved observed differences at comparable boundaries; never replace native results or repair state.',
            'Any trace gap/CRC/nesting/identity/accounting failure, unreconciled memory tail, record-capacity failure, or required missing evidence.',
            'Cancellation, watchdog or timeout; terminate Job. If no stopped-memory capture exists, classify evidence incomplete.',
            'At the exact endpoint require paired Init entry/normal return, same invocation/thread/CPU identity, reconciled fully flush-confirmed records, no active scopes/fatal/gap and no main-loop tick; terminate without continuing the instruction.'],
        interpretation='A bounded diagnostic attempt may expose unknown effects. Inline FPU/TEB consumers can execute between checkpoints; this policy does not promise a pre-consumer stop. If that guarantee is required, readiness remains blocked.',
        omissions=['Only declared resource map upload/download bytes; retain metadata and each explicit omission record.'],
        normalization=False,production_policy_changed=False,authorization_issued=False)
    save(O/'proposed-experimental-policy.json',policy)
    status=read(W/'out/desktop-fixtures/status.json')
    save(O/'fixture-service-review.json',dict(snapshot=status,snapshot_time=time.time(),batch_unexpired=time.time()<status['batch']['expires_at'],
        catalog_supports_this_observer=False,requests_submitted=0,reason='Existing fixed families use a different collector. Do not disguise the candidate, widen the catalog or reuse its authorization for this observer. Owner action stops only an idle disposable service, then runs one explicit owned prerequisite.'))
    decision=dict(status='NOT_READY',separately_authorized_bounded_init_attempt_ready=False,
        physical='OWNER_ACTION_REQUIRED',risk_disposition='REVIEWED_PROPOSED_NOT_APPROVED',
        final_observer='PASS_OWNED_AND_INERT_SCOPE; PHYSICAL_NATIVE_STATE_PENDING',
        candidate_sha256=b['binary_sha256'],candidate_pdb_sha256=b['pdb_sha256'],observer_identities=str(O/'observer-identities.json'),
        candidate_instructions_executed=0,genuine_launches=0,physical_gpu_launches=0,queue_submissions=0,
        owner_action="& 'E:\\Unreal2-Port-Investigation\\experiments\\xrt\\tests\\final_init_review\\owner_action.ps1'",
        timeout_seconds=60,policy_activated=False,production_authorization_changed=False,
        remaining=['Physical owner-desktop run and complete saved-evidence review of the exact-runtime-object gate.',
            'Explicit owner risk disposition, including unknown FPU/error consumers and native subclass effects.',
            'Physical/native-state handler integration reviewed for the actual candidate; no automatic conversion from owned qualification into genuine authorization.'])
    save(O/'readiness.json',decision)
    strict=read(O/'strict-differences-review.json')
    paragraphs=['UNREAL II FINAL EXPERIMENTAL INIT READINESS REVIEW — October 30, 2026',
        'Decision: NOT_READY for a separately authorized bounded Init attempt. No game, genuine candidate instruction, physical GPU fixture or queue request was launched by this review. Proposed policy remains unapproved and inactive.',
        'PHYSICAL PREREQUISITE: OFFLINE PREPARATION COMPLETE; OWNER ACTION REQUIRED. The actual construction desktop is rejected by the unchanged physical gate. Current fixture authorization covers fixed existing families and a different collector; it does not qualify this observer composition. No queue or production enforcement was changed.',
        'The prepared non-game host links 15 exact existing runtime/probe objects from the pinned candidate plus its unexecuted CRT pow object. No game-generated object or candidate main is linked. Candidate EXE/PDB remain unchanged and unconsumed. This tests candidate runtime code with different link addresses; it does not execute or qualify the complete loaded candidate PE.',
        'The physical action permits one native CreateDevice, windowed HAL, adapter 0, 800x600 X8R8G8B8, flags 0x22, D24S8. It checks the owner and child desktop/session, fixed presentation tuple, actual native creation parameters, native device/vtable registry, DXVK adapter LUID/vendor/device against active physical paths, actual NVIDIA ICD module, pinned backends and protected assets. Raw CPU/host/probe FPU/error data and stopped-memory traces are retained. Native strict differences are not normalized. Its endpoint terminates the owned process with a live device; normal COM cleanup is not claimed.',
        'Exact owner action, in ordinary PowerShell on the signed-in physical WinSta0/Default desktop:\n'+decision['owner_action']+'\nThis first rechecks the physical desktop, stops only an idle disposable fixture service through its existing stop command, then obtains its exclusive lock and the existing level/graphics-session locks. It launches only owned_graphics.exe. It neither launches Unreal II nor approves/activates experimental policy. A failed attempted physical run is retained and cannot retry automatically. Successful capture remains pending saved-evidence review.',
        'FINAL OBSERVER QUALIFICATION: Fresh isolated interpreters pass the five composed success/fatal/sink/environment/native-exception cases; descendant Job, watchdog/cancellation and exact candidate inert-mapping/hardware tests pass. Four critical slots are read back on all threads. The final exact-object protocol reconciles all three flush-confirmed records and stops before the owned 895f44 instruction. A separate predevice test hits the actual linked runtime d8_CreateDevice entry, captures CPU/frame/presentation and terminates before any graphics backend loads. The physical continuation of that handler remains unexecuted here.',
        'Independent reread: 17 preserved completed traces / '+str(sum(r['integrity']['records'] for r in checks))+' records pass CRC, sequence, typed identity and complete invocation accounting; all five CRC-repaired identity substitutions are rejected. Fresh evidence-first failures retain the memory tail. Prior 81 supervisor tests and 16 handle-ownership stress Jobs remain sealed historical evidence, not newly rerun claims. Failed engineering attempts remain in exclusive evidence directories.',
        'RETAINED DIFFERENCES — ALL STRICT VERDICTS FAILED:']
    for d in strict['differences']:
        paragraphs.append(d['id']+'\nReachability: '+d['reachable']+'\nKnown: '+d['known_consumers']+'\nUncertain: '+d['unknown']+'\nProposed disposition: '+d['proposal'])
    paragraphs += ['POLICY: proposed-experimental-policy.json specifies one process, 60 seconds, no retry, the 131072 record ceiling, four permanent stops, independent watchdog/Job, fresh isolated filesystem and protected-asset checks, evidence-first failure capture, full invocation reconciliation and termination before guest 0x1090ED5C. No fake native success, error replacement or CPU/FPU normalization is admitted. Resource map byte omissions remain explicit. The runtime can record GetLastError but cannot individually stop every inline x87 or direct TEB consumer. Unknown intervening consumption is a material risk requiring explicit disposition; it is not proven absent.',
        'TIME: 60 seconds remains suitable as a containment ceiling only. At 30884 records/second the normal-record ceiling corresponds to about 4.24 seconds of the owned benchmark, not an Init prediction. Real Init event volume, storage/driver/helper/debugger latency and native blocking remain unknown. Capacity or time exhaustion is failure. A watchdog kill can lose an uncaptured unflushed tail; that evidence is incomplete. No timeout increase was made.',
        'IDENTITIES\nCandidate PE SHA256: '+b['binary_sha256']+'\nCandidate PDB SHA256: '+b['pdb_sha256']+'\nCandidate endpoint: image base + 0x6a0160f; 895f44; BEFORE mov [rdi+0x44],ebx for guest 0x1090ED5C. The following call 0x10901370 and 0x1090ED61 arithmetic are excluded.\nIsolated observer loop SHA256: '+observer['isolated_loop_sha256']+'\nOwned physical fixture SHA256: '+plan['sha256']+'\nExact source/runtime/observer/backend identities: observer-identities.json and physical-plan.json.',
        'REMAINING GENUINE RISKS: native x87 occupancy/tag/precision/exception differences; changed native WNDPROC dispatch; unproved last-error/FPU consumers; opaque pointer/helper-internal/probe timing limitations; real Init operation/event volume; physical graphics/callback behavior in the actual candidate; abrupt failure without independent tail capture. The current candidate review object still refuses execution. Physical evidence, explicit risk acceptance and separately reviewed/authorized genuine integration are required. Historical strict failures and production authorization remain unchanged.']
    (O/'REPORT.txt').write_text('\n\n'.join(paragraphs)+'\n',encoding='utf-8')
    files={p.name:core.sha(p) for p in O.iterdir() if p.is_file() and p.name!='review-seal.json'}
    save(O/'review-seal.json',dict(status='NOT_READY',files=files,sources=core.tree(H),candidate_sha256=b['binary_sha256'],genuine_launches=0,approval=False,policy_activated=False))
    print('Sealed NOT_READY review; owner prerequisite prepared, strict differences retained, policy unapproved.',flush=True)

if __name__=='__main__':main()
