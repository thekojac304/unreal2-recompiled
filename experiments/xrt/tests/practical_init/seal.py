"""Explicit experimental policy self-review and evidence-bound NOT_READY decision."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from observer import require_genuine_readiness

def main():
    before=read(O/'preservation.json');changed=[]
    for root,tree in before['trees'].items():
        if core.tree(Path(root))!=tree:changed.append(root)
    for path,digest in before['state'].items():
        p=Path(path)
        if (core.sha(p) if p.exists() else None)!=digest:changed.append(path)
    protected=A.verify();core.require(protected==before['protected'] and not changed,'preservation failed '+str(changed))
    save(O/'preservation-after.json',dict(passed=True,changed=changed,protected=protected,genuine_launches=0,
        production_policy_changed=False,production_supervisor_source_changed=False))
    b=read(O/'build.json');m=read(O/'stop-mapping.json');ident=read(O/'candidate-identity.json')
    core.require(core.tree(RT)==b['runtime'] and core.tree(Path(b['root']))==b['outputs'],'candidate/runtime changed')
    core.require(b['binary_sha256']==m['sha256']==ident['sha256'],'candidate identity disagreement')
    names=['live.json','profiles.json','contracts.json','windows-contracts.json','gui-trace.json','resource-trace.json',
        'dinput-trace.json','guest-threads.json','exceptions.json','dmusic.json','ipc.json','audio.json',
        'composition.json','containment.json','debugger-validation.json','candidate-identity.json','monitor-linked.json',
        'linked-adapters.json','qualification.json','record-checks.json','supervisor-tests.json','performance.json',
        'source-reproduction.json','handle-ownership.json','candidate-observer-preparation.json','final-checks.json']
    receipts={}
    for name in names:
        r=read(O/name);core.require(r.get('passed') is True,'qualification failed '+name)
        if 'runtime' in r:core.require(r['runtime']==b['runtime'],'qualification runtime mismatch '+name)
        receipts[name]=core.sha(O/name)
    audio=read(O/'audio.json');core.require(audio['tool_callback_qualified'] and audio['script_callback_qualified'],'focused music incomplete')
    strict=dict(status='FAILED_RETAINED',waived=False,
        x87=dict(status='FAILED',source=str(FINISHED/'REPORT.txt'),source_sha256=core.sha(FINISHED/'REPORT.txt')),
        wndproc=dict(status='FAILED',source=str(W/'out/recovery/semantic-compat-20261029-01/REPORT.txt'),
            source_sha256=core.sha(W/'out/recovery/semantic-compat-20261029-01/REPORT.txt')),
        directinput=dict(status='FAILED',samples=read(O/'dinput-trace.json')['retained_strict_differences'],
            actual_inner_transfer='PASS',independent_native_invocation_equality='FAILED'))
    save(O/'strict-failures.json',strict)
    profiles=dict(version=1,forensic=dict(selection='unset or forensic',record_profile='xrt.monitor.v3.forensic',
        per_record_write_through=True,flush_every_record=True,omitted_categories=[],
        comprehensive_evidence_requirements='Retained; historical forensic coverage gaps and strict failures remain failures.'),
        experimental_development=dict(selection='development',record_profile='xrt.monitor.v3.development',
            batch_records=256,tail_capacity_records=4096,tail_capacity_bytes=7602176,
            omitted_categories=['resource.map.download bytes','resource.map.upload bytes'],
            omission_evidence='OPEN category mask 3 and per-event OMITTED record with category and requested byte count.',
            retained=['global sequence/CRC chain','invocation/parent/thread nesting','typed native identities/arguments',
                'actual HRESULT/return/last-error','guest CPU and probe x87/SSE/MXCSR state',
                'resource generation/ref/binding/map metadata','callback/guest EH/ExitThread scopes',
                'fatal/unsupported boundaries and all existing runtime safety checks'],
            exclusions_shared_with_forensic=['uncontracted pointer contents','helper-internal machine API probes',
                'exact volatile machine registers at every actual API entry/RET','AVX upper state (non-AVX candidate)']),
        persistence=dict(recorded='accepted into bounded memory tail',written='whole batch WriteFile completed',
            committed='FlushFileBuffers succeeded; conservative Windows persistence boundary',
            memory_tail='not durable in the guest sink; independent stopped copy fsync is separate evidence',
            abrupt_loss='Uncaptured tail/unknown final counter is incomplete evidence and cannot be accepted.',
            power_loss_tested=False),runtime=b['runtime'])
    save(O/'monitoring-profiles.json',profiles)
    # This is a candidate-specific proposal, not a modification of production
    # policy and not a launch authorization. No exhaustive full-domain gate.
    policy=dict(id='experimental-init-return-v1',state='PROPOSED_NOT_ACTIVATED',profile='development',
        candidate_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        endpoint=dict(guest='0x1090ED5C',host_rva=hex(m['stop_rva']),bytes=m['stop_bytes'],
            instruction='mov dword ptr [rdi+0x44], ebx',before_instruction=True,caller_return_check=True),
        limits=dict(launches=1,timeout_seconds=60,retry=False,normal_records=131072,terminal_failure_sentinel_records=1),
        permanent_hardware_slots=['xrt_fatal','xm_failure','candidate Init-return endpoint','candidate CreateDevice/environment gate'],
        require_all_thread_readbacks=True,require_job_before_first_continue=True,independent_watchdog=True,
        failure_action='Capture stopped host/raw runtime tail when available, preserve all raw failures, terminate Job before continuing; never accept missing required records.',
        endpoint_acceptance=['candidate/PE/PDB/source/stop pins match','independent counters reconcile every accepted record',
            'all accepted records through paired Init return are flush-confirmed','CRC, invocation, nesting and typed identity checks pass',
            'no active invocation or fatal/gap record','all retained memory/COM/filesystem/callback/FPU/runtime checks pass',
            'owner desktop/environment/CreateDevice graphics gates pass','separate experimental compatibility disposition approved',
            'candidate-specific experimental observer reviewed and authorized','terminate without executing endpoint store or next guest call'],
        omitted_evidence_policy=str(O/'monitoring-profiles.json'),
        non_goals=['full-domain payload forensics','whole-engine completion','main-loop tick','playback expansion'],
        forbidden=['consumed candidate retry','original installation/save writes','fake native success','arbitrary pointer forwarding',
            'runtime safety or unsupported-method bypass','production policy replacement','remote push/release'],
        owner_authorization_issued=False)
    save(O/'experimental-init-return-policy.json',policy)
    blockers=[
        dict(id='OWNER_ENVIRONMENT_AND_GRAPHICS',
            remaining='Retained environment gate rejects CodexSandboxDesktop. Qualify the exact candidate CreateDevice/environment/graphics-state gate on the owner desktop with the isolated observer; inert mapping and owned doubles are not physical candidate execution.',
            bounded_next_work='A separately reviewed non-game owner environment/graphics prerequisite; no genuine launcher issued.'),
        dict(id='STRICT_DIFFERENCE_DISPOSITION',
            remaining='Historical strict x87/WNDPROC and independent DirectInput differences remain FAILED. The proposed experimental Init policy has no approved disposition for their reached FPU/error consumers.',
            bounded_next_work='Explicit experimental risk/acceptance review of these existing differences; never rename the historical verdicts.')]
    review=dict(review_type='Explicit Codex technical self-review; not independent owner approval',
        policy_sha256=core.sha(O/'experimental-init-return-policy.json'),decision='NOT_READY',
        source_scope='Known UGameEngine.Init preparation; no exhaustive whole-engine payload requirement',
        passed=['bounded recorder and accurate durability accounting','profile separation and explicit omissions',
            'native/translated InitAudio, tool callbacks, Script.Init and real empty-routine error',
            'GUI, DirectInput, D3D8 CreateDevice/resource contracts and ownership fixtures',
            'independent probe CPU/FPU/error capture','CRC-valid semantic substitution rejection',
            'all-thread DR/readback, Job/watchdog, evidence-first failure and endpoint owned/inert checks',
            'experimental debug-handle correction: 1536 rapid worker exits','production and historical preservation'],
        blockers=blockers,owner_review='NOT_REQUESTED_WHILE_BLOCKED',approval=False)
    save(O/'policy-review.json',review)
    ready=dict(status='NOT_READY',genuine_init_return_ready=False,genuine_init_return_observed=False,
        experimental_policy_review='TECHNICAL_SELF_REVIEW_NOT_READY',focused_owned_init_qualification=True,
        candidate_observer_prepared=True,candidate_containment_qualified=False,owner_authorization=False,owner_authorization_procedure_issued=False,
        candidate=ident['executable'],candidate_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        guest_stop='0x1090ED5C',stop_rva=hex(m['stop_rva']),stop_bytes=m['stop_bytes'],
        candidate_instructions_executed=0,genuine_launches=0,queued_launches=0,consumed_candidates_retried=0,
        production_policy_changed=False,strict_compatibility='FAILED retained',blockers=blockers,
        qualification_receipts=receipts,policy_sha256=review['policy_sha256'],review_sha256=core.sha(O/'policy-review.json'))
    try:require_genuine_readiness(ready)
    except ValueError as e:ready['activation_rejection']=str(e)
    else:raise AssertionError('incomplete experimental readiness accepted')
    save(O/'readiness.json',ready)
    perf=read(O/'performance.json');records=read(O/'record-checks.json');live=read(O/'live.json')
    baseline=read(FINISHED/'live.json')
    save(O/'failure-comparison.json',dict(passed=True,
        baseline=dict(source=str(FINISHED/'live.json'),sha256=core.sha(FINISHED/'live.json'),
            provenance='Retained historical qualification of the exact synchronous baseline, not rerun or relabeled.',
            cases=[r for r in baseline['results'] if 'failure' in r['case']],detection='at every record write/flush'),
        development=dict(source=str(O/'live.json'),sha256=core.sha(O/'live.json'),
            cases=[r for r in live['results'] if r['case'] in ('debugger-write-failure','buffer-exhaustion','flush-failure','partial-write','record-limit','unflushed-stop')],
            detection='at next 256-record batch or forced checkpoint; memory tail remains uncommitted until successful flush'),
        termination='all live fault captures terminate before continuing; failed/torn or missing-close disk streams are never accepted'))
    timed='\n'.join(f"  {r['variant']} / {r['profile']}: {r['iterations']} sequences, {r['records']} records, {r['seconds']:.6f} s" for r in perf['results'])
    report=f'''Unreal II practical development tracing and Init readiness

Decision: NOT_READY for a genuine Init-return attempt. Preparation complete;
no genuine game/candidate instruction launched, queued or retried. No owner
authorization procedure is issued while the two narrow review gates below remain.

Performance and architecture
Matched median improvement: {perf['matched_median_speedup']:.2f}x.
Forensic baseline: {perf['baseline_median_records_per_second']:.1f} records/second.
Development: {perf['development_median_records_per_second']:.1f} records/second.
Timing excludes setup (two initial records) and includes final flush/close.
All matched runs contain the same events/payloads; this improvement comes from
batching, independently of resource-byte omission. Each measured native failure,
last-error, callback and critical FPU-status oracle still passes.
{timed}
These are owned non-game workloads, not a genuine Init event-count/time prediction.
The unchanged 60-second watchdog and 131072-normal-record bound can stop an
oversized genuine workload; bounded failure is not Init-return success.

Forensic: unchanged comprehensive captured categories and per-record write-through
plus successful FlushFileBuffers. Historical strict evidence requirements remain.
Development: 256-record flush batches, 4096-record/7602176-byte bounded memory tail,
CRC chaining, monotonic global sequence and invocation/parent/thread identities.
OPEN/CLOSE/FATAL/GAP/explicit checkpoints/Init return force flush. Separate accepted,
written and flush-confirmed counters prevent file visibility being called durable.
Only resource map upload/download bytes are omitted, each with explicit category
and requested-byte count; binding/map/ownership metadata stays. Existing safety
adapters are byte-identical. There is no record overwrite, sampling or drop mode.
Unflushed tail records are NOT durable in the guest file. Independent stopped
capture copies/fsyncs the disk prefix, tail, pending attempt and counters separately.
Power-loss/storage firmware is untested; flush success is the Windows contract.
Abrupt failure without an independent tail capture is explicitly incomplete.

Qualification
13 owned suites PASS, plus 81 unchanged supervisor tests and 16 handle-stress Jobs.
{len(records['completed_traces'])} final completed traces / {sum(r['integrity']['records'] for r in records['completed_traces'])} records
pass independent CRC, sequence, typed identity and invocation accounting checks.
Actual x86/x64/translated GUI oracles, 14 DirectInput transfer samples, real
DirectMusic COM, real InitAudio (8/128/63), {audio['tool_callbacks']} real nested helper-to-guest tool
callbacks, real Script.Init and empty CallRoutine HRESULT 0x8878121b match native
x86 event/results oracles. No named script routine or playback was enabled.
D3D8 CreateDevice and resource/surface/map/reference operations retain the 15331
checks per architecture, plus trace-enabled ownership/generation/binding fixtures.
These D3D8 fixtures use owned COM doubles, not a physical candidate GPU run.
Full guest CPU, probe GPR/x87/SSE/MXCSR/error and nondefault-FPU comparisons pass;
probe state is not exact volatile native API-entry/RET state. Guest EH and worker
ExitThread preserve abort records. Known strict differences are still FAILED.

Broken writes, simulated partial writes/flush failure, buffer exhaustion, record
ceiling, invalid spans/nesting/profiles and fatal/unsupported boundaries stop.
Memory tails are independently preserved at controlled failure stops; corrupt,
truncated, gapped, duplicated, missing-close and CRC-valid identity/omission
substitutions are rejected. Failure details and failed development attempts stay
in exclusive UUID directories; none are relabeled as successful genuine evidence.

Containment
Hardware stop verified before guest 0x1090ED5C using exact inert candidate mapping
and a live identical owned instruction. Four critical slots and all-thread/new-
thread DR readbacks, Job assignment before resume, descendant termination,
watchdog/cancellation and no endpoint continuation pass. Environment rejection,
native exception, fatal and monitor failure copy raw tail evidence before kill.
Actual candidate endpoint execution remains deliberately untested.

A retained debugger bug was exposed by a Python invalid-semaphore crash. Windows
auto-closes original debug-event thread/process handles on continued EXIT events;
the old loop also closed them manually. The isolated correction owns duplicates
and leaves original handles to Windows. It passed 1536 rapid worker exits in 16
Jobs and the focused suite rerun. Production source/policy remain unchanged.
See handle-ownership.json, debugger_handles.py and Microsoft's API contract:
https://learn.microsoft.com/windows/win32/api/debugapi/nf-debugapi-continuedebugevent

Candidate (fresh, unconsumed)
{ident['executable']}
PE SHA256: {b['binary_sha256']}
PDB SHA256: {b['pdb_sha256']}
281 verified objects: 265 generated reused, 15 fresh runtime, one assembly probe.
Only monitor.c and monitor.h differ from the preserved finished runtime.
Stop: loaded image base + {hex(m['stop_rva'])}; bytes {m['stop_bytes']}.
Stop BEFORE mov dword ptr [rdi+0x44], ebx; RDI=CPU, EBX=0x1090ED5C and CPU.rv
has passed the caller return check. The next guest CALL 0x10901370 is not admitted.

Separate experimental policy
experimental-init-return-policy.json is candidate-specific, technically self-
reviewed in policy-review.json, PROPOSED_NOT_ACTIVATED, and explicitly NOT_READY.
This is not independent owner approval. Historical x87/WNDPROC/DirectInput
failures remain FAILED in strict-failures.json. DirectInput sample 7 retains
native last-error 0 versus translated 5 with equal actual inner native transfer.
The actual candidate observer is PE/PDB/symbol-bound to four distinct critical slots
and shares the qualified owned handlers and isolated handle correction. Its review
object rejects run and rejects the unqualified environment; no activation API is
issued. The production renderer policy/endpoint/authorization/consumed state is unchanged.
No exhaustive payload inventory or unrelated whole-engine expansion is required.

Smallest remaining blockers
'''+''.join(f"{i}. {x['id']}: {x['remaining']}\n   Next: {x['bounded_next_work']}\n" for i,x in enumerate(blockers,1))+'''
Preservation: original installation/save identities, prior evidence, consumed
candidates and production runtime/supervisor/state match the initial pins.
No remote push or release. Genuine Init-return remains unobserved and NOT_READY.
'''
    (O/'REPORT.txt').write_text(report)
    save(O/'source-identity.json',dict(passed=True,source_root=str(H),files=core.tree(H),runtime=core.tree(RT)))
    manifest={p.relative_to(O).as_posix():core.sha(p) for p in O.iterdir() if p.is_file() and p.name!='seal.json'}
    save(O/'seal.json',dict(passed=True,status='NOT_READY',files=manifest,production_policy_changed=False,genuine_launches=0))
    print(f'Sealed practical tracing: {perf["matched_median_speedup"]:.2f}x matched median; genuine Init-return NOT_READY',flush=True)

if __name__=='__main__':main()
