"""Seal preparation/review only. Never prompts, reserves, activates or launches."""
from pathlib import Path
import sys,json,hashlib
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
from physical_audit import *
from launch_adapter import prepare
from supervisor.windows import BoundedLoop

def main():
    O.mkdir(exist_ok=True)
    physical=read(O/'physical-audit.json');qualification=read(O/'observer-qualification.json')
    require(physical['passed'] and qualification['passed'],'prerequisite qualification')
    require(qualification['sources']==core.tree(H) and qualification['runtime']==core.tree(RT),'qualified source/runtime drift')
    q=Path(physical['evidence']);require(manifest(q)==physical['input_manifest'],'physical evidence changed')
    candidate=read(F/'candidate-identity.json');require(candidate['sha256']=='a63ed6204a5f459bfba16feff019d5aecb0b42165dabc8b9477907d2369f06d7','exact candidate')
    plan=qualification['inactive_candidate']['plan'];save(O/'candidate-plan.json',plan)
    _,source,diff=prepare();require(hashlib.sha256(source.encode()).hexdigest()==qualification['launch_profile_source_sha256'],'qualified launch profile drift')
    (O/'isolated-launch-profile.txt').write_bytes(source.encode('utf-8'));(O/'launch-profile.diff').write_bytes(diff.encode('utf-8'))
    base=W/'out/recovery/practical-init-20261031-01';preserved=read(base/'preservation.json')
    for root,tree in preserved['trees'].items():require(core.tree(Path(root))==tree,'preserved production/source tree '+root)
    for name,d in preserved['state'].items():
        p=Path(name);require((digest(p) if p.exists() else None)==d,'preserved production state '+name)
    require(A.verify()==preserved['protected'],'protected assets')
    prod_before=core.tree(core.HOME)
    ledger=core.Ledger(core.HOME/'ledger.jsonl')
    require(not any(r['kind']=='launch-claimed' and r.get('sha256')==candidate['sha256'] for r in ledger.rows),'candidate consumed')
    require(not (core.HOME/'HALTED.json').exists() and not (core.HOME/'STOP').exists(),'genuine safety halt/stop remains blocking')
    require(read(core.HOME/'operational-state.json')['state']=='RUNNING' and not list((core.HOME/'processing').glob('*.json')),'genuine hold/interrupted request')
    historical=read(core.HOME/'qualification.json');host_files=historical['host_files'];source_deltas=[]
    for p,d in host_files.items():require(digest(p)==d,'qualified host changed '+p)
    retained_inputs=dict(read(F/'physical-plan.json')['inputs']);retained_inputs.update(read(F/'physical-plan.json')['dependencies'])
    for rel,d in historical['files'].items():
        p=W/rel
        if digest(p)!=d:source_deltas.append(rel)
        else:retained_inputs[str(p)]=d
    require(source_deltas==['tools/xrt/desktop_supervisor.py'],'unreviewed used supervisor dependency change')
    # The old CLI was extended for disposable fixtures before this task. This
    # isolated workflow never invokes it; every used historical module matches.
    retained_inputs[sys.executable]=digest(sys.executable)
    retained_inputs.update({str(H/n):d for n,d in core.tree(H).items()})
    retained_inputs[str(F/'candidate-identity.json')]=digest(F/'candidate-identity.json')
    retained_inputs[str(base/'seal.json')]=digest(base/'seal.json')
    retained_inputs[str(base/'object-lineage.json')]=digest(base/'object-lineage.json')
    for n,d in read(base/'seal.json')['files'].items():retained_inputs[str(base/n)]=d
    retained_inputs[candidate['executable']]=candidate['sha256'];retained_inputs[str(Path(candidate['executable']).with_suffix('.pdb'))]=candidate['pdb_sha256']
    identity=dict(candidate_sha256=candidate['sha256'],pdb_sha256=candidate['pdb_sha256'],plan_sha256=digest(O/'candidate-plan.json'),
        sources=core.tree(H),retained_observer=read(F/'observer-identities.json'),
        retained_execution_inputs=retained_inputs,qualified_host_files=host_files,unused_historical_cli_delta=source_deltas,
        supervisor_inventory=core.tree(W/'tools/xrt/supervisor'),practical_observer_inventory=core.tree(P),
        isolated_loop_sha256=hashlib.sha256(BoundedLoop.experimental_run_source.encode()).hexdigest(),
        isolated_launch_source_sha256=qualification['launch_profile_source_sha256'],physical_audit_sha256=digest(O/'physical-audit.json'),
        qualification_sha256=digest(O/'observer-qualification.json'),profile='development',endpoint='before 0x1090ED5C',seconds=60,retry=False)
    save(O/'observer-identity.json',identity)
    risks=read(F/'strict-differences-review.json')['differences']
    policy=dict(id='experimental-init-unresolved-risk-v2',state='PREPARED_REVIEWED_NOT_ACTIVATED',
        owner_approval=dict(preparation_and_review=True,experimental_policy_accepted=False,genuine_launch_authorized=False,breakpoint_activation_authorized=False,
            interpretation='The latest owner instruction authorizes preparation/review only. Explicit local console acceptance of this exact sealed policy is still required.'),
        candidate_sha256=candidate['sha256'],pdb_sha256=candidate['pdb_sha256'],observer_identity_sha256=digest(O/'observer-identity.json'),
        scope=dict(processes=1,seconds=60,retry=False,guest_endpoint='0x1090ED5C',host_rva='0x6a0160f',bytes='895f44',before_instruction=True,normal_records=131072,record_bytes=1904,tail_records=4096,tail_bytes=7798784),
        acceptance_basis='A single bounded diagnostic Init-return observation. Strict native-x86 equivalence is not required for this separately scoped experiment. No strict failure is relabeled PASS.',
        unresolved_risks=risks,
        risk_disposition=[
          'Historical x87 double/80-bit/tag/exception/status and native occupancy effects remain unresolved; no claim that all affected values are dead or all consumers absent.',
          'Native WNDPROC subclass identity changes, including the retained system opengl32.dll change after first Present, remain observable unresolved behavior; keep typed procedure identity, callback restoration and module protections.',
          'Acquire and CreateTexture last-error differences between independent native-x86 and translated/native-x64 invocations are retained risks. Do not force guest error to zero, a fixture seed, or a historical x86 result. Compare actual inner native result/error with its own adapter transfer.',
          'Documented sticky precision-status changes remain observations. Do not clear/restore status to manufacture equality. Existing runtime FPU control/unsupported-instruction checks stay active.',
          'HLE GetLastError and typed calls are recorded. Inline x87 and direct TEB consumers can execute between checkpoints; this experiment explicitly carries that unproved consequence risk and does not promise a pre-consumer stop.'],
        protections_unchanged=['memory commitment/full page-range and pointer checks','guest/host address separation','COM receiver/generation/reference/binding/ownership checks',
            'HWND/thread/module ownership and callback/return checks','filesystem sandbox/input manifests and DirectMusic helper disk guard','exact binary/PDB/source/dependency FilePins and module allowlist',
            'four permanent critical hardware stops and all-thread/new-thread DR readbacks','independent watchdog, Job assignment before continuation and descendant kill-on-close',
            'fresh isolated sandbox; original installation/save and prior evidence protected','global durable one-shot SHA reservation and local one-attempt consumed record'],
        stop_conditions=['Any retained fatal/unsupported/safety check, invalid span/handle/object/return, unqualified reentry or module identity.',
            'Owner environment/driver/display drift, non-windowed/non-HAL/non-adapter-zero request, missing FPU-preserve flag or second device creation attempt.',
            'Actual native result/error transfer disagreement; do not substitute independent-architecture outputs. Native failure HRESULTs remain native results and existing failure paths stay active.',
            'Trace CRC/sequence/nesting/receiver identity failure, unaccounted omission/abort/tail, record exhaustion or missing independent runtime timeline.',
            'Any engine/level main-loop tick before the endpoint; mismatch in Init object/CPU/thread/stack/nonvolatiles/caller/RET pairing.',
            'At success, require all accepted records flush-confirmed, zero active scopes, no fatal/gap, exact native device identity and stream/stopped-memory agreement; terminate before the endpoint store.',
            '60-second deadline, owner Ctrl+C or local STOP: kill Job, preserve partial evidence, classify missing tail capture incomplete, never retry.'],
        monitoring_limits=['Probe context is not exact volatile API entry/RET state.','Typed unknown pointer contents and helper-internal native APIs remain declared evidence limits.',
            'Development omits only resource map download/upload bytes, with per-event omission records and retained metadata.','No async writer, drop mode, record overwrite, fabricated native success or CPU/FPU/error normalization.'],
        time_budget_review='60 seconds is retained solely as a containment ceiling. Physical fixture was 3.205 seconds; owned trace throughput does not predict real Init event volume, loading/driver/helper latency or completion. The 131072-record ceiling may fire earlier.',
        technical_review='RECOMMENDED_FOR_EXPLICIT_OWNER_REVIEW_AS_A_BOUNDED_RISK_EXPERIMENT',strict_verdicts='ALL_DOCUMENTED_STRICT_FAILURES_REMAIN_FAILED',
        policy_activated=False,production_policy_changed=False)
    save(O/'experimental-policy.json',policy)
    phrase='AUTHORIZE ONE EXPERIMENTAL INIT '+candidate['sha256']+' POLICY '+digest(O/'experimental-policy.json')+' OBSERVER '+digest(O/'observer-identity.json')+' 60 SECONDS NO RETRY BEFORE 1090ED5C'
    command="& 'E:\\Unreal2-Port-Investigation\\.venv\\Scripts\\python.exe' -B -I 'E:\\Unreal2-Port-Investigation\\experiments\\xrt\\tests\\experimental_init_review\\owner_run.py'"
    save(O/'owner-authorization.json',dict(state='PROCEDURE_PREPARED_NOT_AUTHORIZED',command=command,console_phrase=phrase,
        steps=['Review REPORT.txt, experimental-policy.json and observer-identity.json.','From ordinary PowerShell on physical WinSta0/Default, run the exact command.','Only if you accept this exact scoped risk policy and authorize the one genuine attempt, paste the exact local console phrase.'],
        effect='The local phrase accepts this policy and authorizes one 60-second genuine attempt through the isolated profile. It does not replace production supervisor policy or authorize any retry/gameplay.',
        cancellation='Ctrl+C or create out/recovery/experimental-init-policy-review-20261030-01/owner-control/STOP. Existing genuine STOP/HALTED/hold is also respected, never cleared.',
        consumption='Immediately before the attempt the existing shared genuine SHA ledger is durably reserved, plus an isolated CONSUMED receipt. Any later failure leaves it consumed.',
        current_authorization=False))
    readiness=dict(technical_readiness='READY_FOR_SEPARATE_OWNER_AUTHORIZATION',execution_authorized=False,policy_activated=False,
        candidate_sha256=candidate['sha256'],pdb_sha256=candidate['pdb_sha256'],physical_prerequisite='PASS_SCOPED_NON_GAME_EXACT_RUNTIME_OBJECTS',
        observer='QUALIFIED_OWNED_PROTOCOL_AND_SAVED_PHYSICAL_STATE; EXACT_CANDIDATE_CONSTRUCTED_INACTIVE',strict_equivalence='FAILED_NOT_REQUIRED_BY_PROPOSED_EXPERIMENT',
        residual_risks='Explicit in experimental-policy.json; not proven harmless.',seconds=60,retry=False,genuine_launches=0,breakpoints_activated_on_candidate=False,
        required_next='Separate owner review and exact physical-console authorization procedure. This chat has not supplied that authorization.',
        owner_procedure=str(O/'OWNER_AUTHORIZATION.txt'),production_policy_changed=False)
    save(O/'readiness.json',readiness)
    (O/'OWNER_AUTHORIZATION.txt').write_text('Prepared procedure only — NOT AUTHORIZED\n\nReview experimental-policy.json and observer-identity.json first.\n\nOn the signed-in physical Windows desktop, ordinary PowerShell:\n'+command+'\n\nOnly if accepting the exact risks and authorizing the one genuine attempt, paste at that local prompt:\n'+phrase+'\n\nDo not run this during preparation. No genuine launch or activation occurred in this review.\n',encoding='utf-8')
    report='''FINAL EXPERIMENTAL INIT POLICY AND PHYSICAL EVIDENCE REVIEW — October 30, 2026

Decision: READY FOR SEPARATE OWNER AUTHORIZATION, under the proposed bounded experimental policy. NOT AUTHORIZED OR ACTIVATED. The latest user message approves preparation/review only. No genuine process or candidate instruction was launched. Production supervisor policy and authorization remain unchanged.

Physical prerequisite independently PASSED within its measured scope. The owner already ran the sealed non-game host on physical WinSta0/Default: one native adapter-zero windowed HAL CreateDevice, RTX 5090 (10DE:2B85), LUID 00000000:00011ad5 matching active physical display paths, pinned DXVK pair and actual NVIDIA Vulkan ICD. Full source/object/PE/PDB/loaded-module identities and protected assets recheck. Run duration 3.205 seconds; terminated while stopped; zero remaining Job processes. No normal native-device/window cleanup is inferred from this termination.

112 raw records reconcile, with 41 native entries/returns and zero active endpoint scopes. The early capture preserves 16 unflushed records independently; the endpoint confirms all 112 flushed. 164 hardware readbacks cover 18 threads; every new thread was read back before continuation. Native CreateDevice returned HRESULT 0 and last-error 0; the guest adapter retained that actual error. Native probe FCW 027F, FSW 0000 and MXCSR 1FA0 were preserved at the measured CreateDevice probes. The already-set precision-status bit was not cleared. These are owned fixture observations, not genuine Init or strict equivalence.

The physical host links the exact existing candidate runtime objects; no game-generated object or candidate main is linked. This proves the scoped physical gate/code prerequisite, not complete loaded-candidate execution. Only its 800x600 / flags 0x22 / D24S8 tuple was measured. Different genuine tuples remain subject to the unchanged live capability/format/HWND/page checks in the candidate.

The earlier candidate review plan omitted xrt_g, events/event_seq and d8_device capture symbols. A new inactive PE/PDB-bound plan resolves them independently. The new staged observer verifies the actual recorded Init BEGIN/END plus independent runtime timeline: object, same invocation/host thread/CPU, caller/RET sites, ESP+4, preserved guest nonvolatiles, no main-loop tick, fully flushed primary trace and exact stream/stopped-memory equality. It retains all four permanent critical stops. Native device identity and actual CreateDevice/Acquire/CreateTexture result/error transfer are checked without independent-x86 equality or normalization.

New live tests use owned code with exact runtime objects and the real xrt_world_enter/return protocol, no game function. Success terminates before the identical owned endpoint store. Tick, nonvolatile corruption and missing-return cases reject with evidence-first Job termination. The new graphics-entry handler is also exercised on the sealed owned predevice host and stops before loading a backend. Saved actual physical device/transfer checks pass; corrupt identities, native result/error transfers, counters, tails and pending bytes are rejected. The actual candidate review object's run method still refuses; no hardware register was changed on a candidate process. Failed engineering checks are retained in exclusive directories.

The separately scoped policy carries the documented x87/80-bit/tag/status/occupancy uncertainty, native WNDPROC subclass behavior and independent Acquire/CreateTexture error differences as unresolved risks. It does not demand strict native-x86 equivalence. Historical strict verdicts remain FAILED. Inline x87/direct TEB consumers may execute between monitoring checkpoints: their consequences are unproved, and there is no promised pre-consumer stop. Existing unsupported/FPU-control and all memory, COM, callback, filesystem, module and containment guards remain mandatory. No native results, guest errors or CPU/FPU state are silently corrected.

The owner execution path is an isolated, explicit adaptation of the existing genuine workflow. launch-profile.diff records every change: candidate/endpoint/composition selection, development monitor sink, scoped experimental acceptance and treating every earlier fatal/unsupported stop as a failed Init observation. The command, fresh sandbox copy, verified assets/helper/backend, memory/runtime safeguards, module allowlist, Job/watchdog, cursor/accessibility cleanup and input/stream reconciliation stay in the retained workflow. No production file is patched. The console predicate and one-shot ledger rejection checks pass in test-only state. Neither the adapter nor owner_run.py has been invoked for a genuine attempt.

60 seconds stays unchanged. It is a containment ceiling, not a demonstrated real Init completion budget. Event capacity (131072 normal records), real operation volume, loading/driver/helper latency, missed consumer effects and abrupt tail loss remain risks. Timeout/capacity/missing capture means failure, never success or retry. Runtime record size is independently measured as 1904 bytes and the 4096-record memory tail is 7,798,784 bytes; this corrects older prose counts without changing the binary schema or any records.

Review experimental-policy.json, observer-identity.json and the preserved strict differences. OWNER_AUTHORIZATION.txt gives the exact separate owner-console procedure. Running it and pasting its policy/observer-bound phrase is the future authorization step, not something approved by this chat. It reserves the candidate SHA in the shared append-only genuine ledger before any launch, so even preparation/launch failure cannot be retried. It respects existing STOP/HALTED/holds and uses the same Job/watchdog and input cleanup. It never installs or changes production policy.
'''
    report+='\nCandidate SHA256: '+candidate['sha256']+'\nPDB SHA256: '+candidate['pdb_sha256']+'\nObserver identity SHA256: '+digest(O/'observer-identity.json')+'\nPolicy SHA256: '+digest(O/'experimental-policy.json')+'\nEndpoint: image base + 0x6a0160f, bytes 895f44, BEFORE guest 0x1090ED5C.\n'
    (O/'REPORT.txt').write_text(report,encoding='utf-8')
    require(core.tree(core.HOME)==prod_before,'production state changed during review')
    save(O/'preservation.json',dict(passed=True,production_home=prod_before,production_policy_changed=False,protected=A.verify(),prior_review_seal_sha256=digest(F/'review-seal.json'),genuine_launches=0))
    inputs=dict(retained_inputs)
    for name in ('experimental-policy.json','observer-identity.json','candidate-plan.json','readiness.json','owner-authorization.json','observer-qualification.json','physical-audit.json'):
        inputs[str(O/name)]=digest(O/name)
    inputs[candidate['executable']]=candidate['sha256'];inputs[str(Path(candidate['executable']).with_suffix('.pdb'))]=candidate['pdb_sha256']
    save(O/'execution-review-seal.json',dict(files=inputs,host_files=host_files,technical_readiness=readiness['technical_readiness'],genuine_launches=0,policy_activated=False,production_policy_changed=False))
    print('Technical readiness PASS; separate policy/one-attempt local owner authorization procedure sealed. No genuine launch or activation.',flush=True)

if __name__=='__main__':main()
