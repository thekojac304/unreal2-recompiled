"""Seal a measured NOT_READY milestone; no launch or policy activation API."""
import sys,uuid,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from observer import require_genuine_readiness

def main():
    p=read(O/'preservation.json');changed=[]
    for root,tree in p['trees'].items():
        if core.tree(Path(root))!=tree:changed.append(root)
    for name,digest in p['state'].items():
        q=Path(name)
        if (core.sha(q) if q.exists() else None)!=digest:changed.append(name)
    protected=A.verify();core.require(protected==p['protected'],'protected installation/save identity changed')
    baseline=read(BASELINE/'build.json');baseline_exe=Path(baseline['root'])/'xrt_ucc.exe'
    core.require(core.sha(baseline_exe)==baseline['binary_sha256']=='75530d04d139539a6ae8f51eee49c5b6b7770fad9c99b2536867ccdb0fc2a8cb','baseline candidate changed')
    core.require(core.sha(baseline_exe.with_suffix('.pdb'))==baseline['pdb_sha256'],'baseline PDB changed')
    save(O/'preservation-after.json',dict(passed=not changed,changed=changed,protected=protected,genuine_launches=0,production_policy_changed=False))
    core.require(not changed,'historical evidence / production state changed: '+str(changed))
    b=read(O/'build.json');m=read(O/'stop-mapping.json');ident=read(O/'candidate-identity.json')
    exe=Path(b['root'])/'xrt_ucc.exe'
    core.require(core.tree(exe.parent)==b['outputs'] and core.tree(RT)==b['runtime'],'final build input/output identity')
    core.require(b['binary_sha256']==ident['sha256']==m['sha256']==core.sha(exe),'final PE identity')
    names=['live.json','contracts.json','windows-contracts.json','gui-trace.json','resource-trace.json','dinput-trace.json',
           'guest-threads.json','exceptions.json','dmusic.json','ipc.json','composition.json','containment.json',
           'debugger-validation.json','candidate-identity.json','monitor-linked.json','linked-adapters.json',
           'qualification.json','record-checks.json','supervisor-tests.json','performance.json','performance-stress.json',
           'sdk-prototypes.json','source-reproduction.json']
    receipts={}
    for name in names:
        r=read(O/name);core.require(r.get('passed') is True,'qualification '+name)
        if 'runtime' in r:core.require(r['runtime']==b['runtime'],'qualification runtime differs: '+name)
        if 'sha256' in r and name not in ('sdk-prototypes.json',):core.require(r['sha256']==b['binary_sha256'],'qualification candidate differs: '+name)
        receipts[name]=core.sha(O/name)
    core.require(read(O/'source-reproduction.json')['source_templates']==core.tree(H),'source templates changed after independent reproduction')
    # Retain actual compiler-reported SDK and CRT input identities as well as
    # the transitive local source/object chains verified by verify.py.
    headers={};logs={}
    for row in read(O/'object-lineage.json').values():
        if not row.get('compile_receipt'):continue
        log=Path(row['compile_receipt']).with_suffix('.stdout.txt');logs[str(log)]=core.sha(log)
        for line in log.read_text().splitlines():
            if 'including file:' in line:
                header=Path(line.split('including file:',1)[1].strip());headers[str(header)]=core.sha(header)
    save(O/'compiler-header-identity.json',dict(passed=True,headers=headers,compiler_logs=logs))
    c=read(O/'coverage.json');core.require(c['runtime']==b['runtime'] and not c['complete'],'coverage/runtime closure')
    perf=read(O/'performance.json');stress=read(O/'performance-stress.json');environment=read(O/'environment-check.json')
    limits=[r for r in stress['results'] if not r['completed']]
    proposed=120
    ready=dict(status='NOT_READY',complete_typed_coverage=False,production_monitor_qualified=False,
        strict_compatibility='FAILED retained',owner_authorization=False,genuine_launches=0,queued_launches=0,
        candidate=str(exe),candidate_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],
        stop_rva=hex(m['stop_rva']),stop_bytes=m['stop_bytes'],guest_stop='0x1090ED5C',
        retained_constraints=dict(launches=1,timeout_seconds=60,retry=False,stop_before_next_guest_instruction=True),
        timeout_proposal=dict(seconds=proposed,activated=False,separate_review_required=True,
            rationale='Review a bounded 120-second ceiling only after payload/helper/state/environment gaps close. Owned workloads show the 60-second budget is not qualified; a higher ceiling alone is not readiness.'),
        production_policy_changed=False,breakpoint_design_activated=False,owned_four_slot_composition_passed=True,
        critical_breakpoint_design=['xrt_fatal','xm_failure','verified Init-return endpoint','CreateDevice/environment gate'],
        current_environment_gate_passed=environment['passed'],blockers=c['blocking_requirements'],qualification_receipts=receipts)
    if not environment['passed']:ready['blockers'].append('Current retained desktop/environment gate rejects the sandbox desktop; physical topology alone is insufficient. See environment-check.json.')
    try:require_genuine_readiness(ready)
    except ValueError as e:ready['constructor_rejection']=str(e)
    else:raise AssertionError('incomplete package accepted for genuine execution')
    save(O/'readiness.json',ready)
    samples=[r for r in perf['results'] if r['case']=='trace-300']
    timing='\n'.join(f"  {r['variant']}: {r['iterations']} sequences, {r['records']} records, {r['seconds']:.6f} s, {1000*r['seconds']/(r['records']-3):.3f} ms/record" for r in samples)
    stress_text='\n'.join(f"  {r['case']}: "+(f"completed {r['records']} records in {r['seconds']:.6f} s" if r['completed'] else f"watchdog contained after {r['seconds']:.3f} s; {r['whole_records_in_file']} whole file records; incomplete prefix, no complete integrity claim") for r in stress['results'])
    records=read(O/'record-checks.json');trace_count=len(records['completed_traces']);record_count=sum(r['integrity']['records'] for r in records['completed_traces'])
    report=f'''Unreal II initialization monitoring milestone — NOT READY

No genuine game launched, queued or retried. Production supervisor, breakpoint policy,
authorization state, historical evidence and original installation/saves are preserved.

Closed / implemented:
- {c['wrapped_com_sites']}/{c['native_com_sites']} inventoried host COM sites wrapped; {c['supported_typed_descriptors']} typed COM descriptors.
- {c['windows_signatures']} SDK-checked Windows signatures at {c['windows_sites']} sites ({c['windows_native_sites']} native, {c['windows_probe_support_sites']} diagnostic-support sites).
- Actual GUI returns and compiler-converted values; DirectInput nested format/GUID/data payloads.
- Seven former DirectMusic host COM gaps and paired bounded host IPC frames.
- Resource binding location/offset and release/cleanup observations; map bytes up to 16 KiB.
- Version-2 aborted invocation records for actual guest EH and worker ExitThread;
  generated landing-pad ABI unchanged. Unknown/oversized/invalid operations fail closed.
- Owned composition with the production debugger factory, four permanent critical slots,
  all-thread DR readbacks, independent Job/watchdog and evidence-first failure capture.

Live validation:
- All 11 final owned monitoring/oracle/containment suites PASS; 81 supervisor tests PASS.
- {trace_count} positive completed traces, {record_count} records: no outstanding invocation IDs.
- Native x86/x64/translated GUI oracles agree; 114 callback scopes in 5,938 records.
- Six actual guest EH probes match native x86; 17 explicit aborted scopes. Worker
  ExitThread adds two explicit aborts; four guest CPU threads match the native oracle.
- Real native DirectMusic Loader8 COM/apartment lifecycle and real guarded helper IPC PASS.
- Owned resource/surface/scene, generation reuse, binding and byte-map transport PASS.
- Native-double precision-status and CreateTexture last-error transfer PASS. Complete
  guest CPU/probe state and last-error comparisons PASS. These do not waive native-x86 differences.
- Sink failure preserves pending evidence; malformed streams and CRC-valid receiver,
  interface, generation and slot substitutions are rejected.
- Retained broad adapter contracts: 15,331 checks per architecture; deliberately
  longjmp-reset negative doubles run with the sink disabled, independently of live traces.

Measured strict durable tracing:
{timing}
{stress_text}
CRC recording now uses an equivalent table, independently checked by zlib. End-to-end
throughput did not materially improve: synchronous durable file writes dominate.
The genuine event count and engine work remain unknown. The 60-second watchdog is
unchanged and not qualified for genuine Init. A {proposed}-second bounded ceiling is a
separate review proposal, not an activated change or a guarantee of sufficient time.

Final candidate: {exe}
PE SHA256: {b['binary_sha256']}
PDB SHA256: {b['pdb_sha256']}
281 verified objects: 265 inherited generated, 15 fresh runtime, one assembly probe.
Independent regeneration exactly matches the compiled runtime. PE/PDB identity,
compiler inputs, transitive source/object lineage, 60 linked adapters and monitoring
symbols are independently verified.
Stop: loaded image base + {hex(m['stop_rva'])}; bytes {m['stop_bytes']}.
Instruction: mov dword ptr [rdi+0x44], ebx. RDI is CPU; EBX and checked CPU.rv are
0x1090ED5C. Stop BEFORE that store and the next guest CALL to 0x10901370.
Actual candidate was mapped SEC_IMAGE_NO_EXECUTE only; no candidate instruction executed.

Remaining Init-relevant gates:
'''+''.join('- '+s+'\n' for s in ready['blockers'])+f'''
Current retained environment gate: {'PASS' if environment['passed'] else 'REJECTED'}.
Protected asset verification: {protected['files']} files; preservation PASS.

Genuine Init-return execution: NOT READY. No owner authorization procedure or launch
command is issued. Readiness rejection: {ready['constructor_rejection']}.
'''
    (O/'REPORT.txt').write_text(report)
    summary=f'''# Initialization monitoring milestone qualified; genuine Init NOT READY

2026-10-30. All 145 inventoried host COM sites and 95 SDK-checked Windows
signatures are instrumented. Owned validation passes for nested callbacks,
real DirectMusic COM/IPC, resource maps/lifetimes, guest EH/ExitThread and
production-debugger composition. Instrumentation inventory is not full live coverage.
All 11 monitoring/containment suites and 81 supervisor tests pass. The genuine
60-second throughput budget and remaining Init coverage/environment gates do not.

Candidate `{b['binary_sha256']}`; checked stop at loaded base +
`{hex(m['stop_rva'])}`, bytes `89 5F 44`, before guest `0x1090ED5C`.
No genuine game launched/queued/retried; prior failures, production policy and
protected installation/save assets remain unchanged.

[Report](out/recovery/init-runtime-finish-20261030-01/REPORT.txt),
[readiness](out/recovery/init-runtime-finish-20261030-01/readiness.json),
[reproduction](experiments/xrt/tests/init_runtime_finish/README.md).

---

'''
    for target in [W/'CURRENT_STATUS.md',W/'experiments/xrt/CURRENT_STATUS.md']:
        prefix=summary if target.parent==W else summary.replace('](out/','](../../out/').replace('](experiments/xrt/tests/','](tests/')
        old=target.read_text()
        if old.startswith('# Initialization monitoring milestone qualified; genuine Init NOT READY'):old=old.split('\n---\n\n',1)[1]
        target.write_text(prefix+old)
    serial=str(uuid.uuid4());snapshot=O/('sealed-inputs-'+serial);snapshot.mkdir()
    shutil.copytree(H,snapshot/'sources',ignore=shutil.ignore_patterns('__pycache__'));shutil.copytree(RT,snapshot/'runtime')
    core.require(core.tree(snapshot/'sources')==core.tree(H) and core.tree(snapshot/'runtime')==b['runtime'],'seal snapshots')
    save(O/('seal-'+serial+'.json'),dict(passed=True,status='NOT_READY',sources=core.tree(H),runtime=b['runtime'],
        source_snapshot=str(snapshot/'sources'),runtime_snapshot=str(snapshot/'runtime'),
        current_receipts={q.name:core.sha(q) for q in O.iterdir() if q.is_file() and q.suffix in ('.json','.txt') and not q.name.startswith('seal-')},
        candidate_sha256=b['binary_sha256'],genuine_launches=0))
    print('Final preservation, evidence and source/object closure PASS; sealed NOT_READY',flush=True)

if __name__=='__main__':main()
