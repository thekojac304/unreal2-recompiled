"""Preserve old evidence and seal an explicitly incomplete readiness assessment."""
import sys,json,uuid,shutil
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
    protected=A.verify();core.require(protected==p['protected'],'installation/save snapshot changed')
    preservation=dict(passed=not changed,changed=changed,protected=protected,genuine_launches=0,production_policy_changed=False)
    save(O/'preservation-after.json',preservation);core.require(not changed,'preservation failure '+str(changed))
    b=read(O/'build.json');identity=read(O/'candidate-identity.json');mapping=read(O/'stop-mapping.json')
    core.require(identity['sha256']==b['binary_sha256']==mapping['sha256']==core.sha(Path(b['root'])/'xrt_ucc.exe'),'final candidate identity')
    core.require(core.tree(RT)==b['runtime'],'runtime changed after build')
    names=['live.json','contracts.json','windows-contracts.json','gui-trace.json','resource-trace.json','dinput-trace.json',
           'guest-threads.json','containment.json','debugger-validation.json','candidate-identity.json','monitor-linked.json','linked-adapters.json']
    receipts={}
    for name in names:
        row=read(O/name);core.require(row.get('passed') is True,'qualification '+name)
        if 'runtime' in row:core.require(row['runtime']==b['runtime'],'qualification used other runtime: '+name)
        if 'sha256' in row:core.require(row['sha256']==b['binary_sha256'],'qualification used other candidate: '+name)
        receipts[name]=core.sha(O/name)
    # Capture all actual compiler-reported headers, including SDK/CRT, as a
    # read-only supplemental identity. Reused objects retain historical chains.
    headers={};compiler_logs={}
    for obj,row in read(O/'object-lineage.json').items():
        if not row.get('compile_receipt'):continue
        log=Path(row['compile_receipt']).with_suffix('.stdout.txt');compiler_logs[str(log)]=core.sha(log)
        for line in log.read_text().splitlines():
            if 'including file:' in line:
                header=Path(line.split('including file:',1)[1].strip());headers[str(header)]=core.sha(header)
    save(O/'compiler-header-identity.json',dict(passed=True,headers=headers,compiler_logs=compiler_logs,
        note='Current file identities bound to actual compiler include records; immutable historical generated-object chains are verified separately.'))
    coverage=read(O/'coverage.json');core.require(coverage['runtime']==b['runtime'] and not coverage['complete'],'coverage ledger')
    readiness=dict(status='NOT_READY',complete_typed_coverage=False,production_monitor_qualified=False,
        strict_compatibility='FAILED retained',owner_authorization=False,genuine_launches=0,queued_launches=0,
        candidate_sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],candidate=str(Path(b['root'])/'xrt_ucc.exe'),
        guest_stop='0x1090ED5C',stop_rva=hex(mapping['stop_rva']),stop_bytes=mapping['stop_bytes'],
        proposed_constraints=dict(launches=1,timeout_seconds=60,retry=False,stop_before_next_guest_instruction=True),
        production_policy_changed=False,critical_breakpoint_design=['xrt_fatal','xm_failure','Init-return endpoint','CreateDevice environment gate'],
        routine_native_callback_hardware_slots=0,breakpoint_design_activated=False,
        blockers=coverage['blocking_requirements'],qualification_receipts=receipts)
    try:require_genuine_readiness(readiness)
    except ValueError as e:readiness['constructor_rejection']=str(e)
    else:raise AssertionError('incomplete monitoring admitted genuine readiness')
    save(O/'readiness.json',readiness)
    report=f'''Scalable runtime monitoring: implemented experimental foundation; genuine NOT READY

No genuine game was launched, queued or retried. No production policy or breakpoint expansion.
138 of 145 native COM sites wrapped; 123 compiler-checked interface/method descriptors.
Two typed factory boundaries; common import, callback, fatal and Init scopes.
Per-thread invocations, global sequence, bounded typed evidence, FPU/error preservation,
fail-closed sink and strict independent stopped-stream collector.

Live qualification passes: nested callbacks/native calls, four real translated guest
threads against native x86, resource generation/binding/map/destruction, DirectInput
inner-transfer oracle, real GUI native x86/x64/translated comparison, nondefault FPU,
write failure, malformed streams, watchdog/Job descendants and owned exact stop.
Strict compatibility failures remain retained. No physical GPU test was repeated.

Candidate: {readiness['candidate']}
SHA256: {b['binary_sha256']}
PDB SHA256: {b['pdb_sha256']}
281 objects: 265 inherited generated, 15 freshly compiled runtime, one assembly probe.
60 retained linked adapter identities; common monitor symbols resolved.
Endpoint: image base + {hex(mapping['stop_rva'])}, bytes {mapping['stop_bytes']},
before guest 0x1090ED5C. Candidate mapped SEC_IMAGE_NO_EXECUTE only.

Readiness: NOT_READY. Full typed Windows/GUI natives, dynamic payloads, nonlocal exits,
cleanup/binding identities, actual guest error/FPU consumers and production integration
remain unqualified. See coverage.json for the complete gap inventory.
Future constraints remain one launch, 60 seconds, no retry, terminate before next guest
instruction, after separate qualification/review and authorization. No launch command.

Architecture, coverage matrix and reproduction:
experiments/xrt/tests/runtime_monitoring/README.md
Preservation of prior evidence, production state, installation and saves: PASS.
'''
    (O/'REPORT.txt').write_text(report)
    summary=f'''# Common runtime monitoring implemented; genuine continuation NOT READY

2026-10-30. A fresh experimental runtime now traces common imports, native COM
entry/return, callbacks, resource lifetime and Init boundaries without routine
method hardware breakpoints. It wraps 138 D3D8/DirectInput native COM sites with
123 typed interface/method descriptors. Live owned tests pass for nesting,
four actual guest threads, resource generation/binding/maps, DirectInput, GUI,
FPU/error preservation, evidence failures and unchanged Job/watchdog containment.

The 281-object candidate is `{b['binary_sha256']}`. Its verified Init stop is
guest `0x1090ED5C`, host RVA `{hex(mapping['stop_rva'])}`, bytes `89 5F 44`.
No genuine candidate instruction executed. Production supervisor/runtime sources,
authorization, prior evidence, installation and saves are preserved.

Readiness remains **NOT_READY**: full typed Windows/GUI native coverage, dynamic
payloads, nonlocal exits, cleanup identities, guest state consumers and production
observer integration remain incomplete. Strict historical failures remain FAILED.
One-launch/60-second/no-retry constraints are retained; no launch command is issued.

[Architecture and coverage](experiments/xrt/tests/runtime_monitoring/README.md),
[qualification report](out/recovery/runtime-monitoring-20261030-01/REPORT.txt),
[readiness](out/recovery/runtime-monitoring-20261030-01/readiness.json).

---

'''
    for target in (W/'CURRENT_STATUS.md',W/'experiments/xrt/CURRENT_STATUS.md'):
        old=target.read_text();heading='# Common runtime monitoring implemented; genuine continuation NOT READY'
        if old.startswith(heading):old=old.split('\n---\n\n',1)[1]
        prefix=summary if target.parent==W else summary.replace('](experiments/xrt/tests/','](tests/').replace('](out/','](../../out/')
        target.write_text(prefix+old)
    serial=str(uuid.uuid4());snapshot=O/('sealed-inputs-'+serial);snapshot.mkdir()
    shutil.copytree(H,snapshot/'sources',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(RT,snapshot/'runtime')
    core.require(core.tree(snapshot/'sources')==core.tree(H) and core.tree(snapshot/'runtime')==core.tree(RT),'seal snapshots')
    seal=O/('seal-'+serial+'.json')
    save(seal,dict(passed=True,status='NOT_READY',sources=core.tree(H),runtime=core.tree(RT),
        source_snapshot=str(snapshot/'sources'),runtime_snapshot=str(snapshot/'runtime'),
        current_receipts={p.name:core.sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ('.json','.txt') and not p.name.startswith('seal-')},
        candidate_sha256=b['binary_sha256'],genuine_launches=0))
    print('Preservation PASS; monitoring subsystem sealed NOT_READY:',seal,flush=True)
if __name__=='__main__':main()
