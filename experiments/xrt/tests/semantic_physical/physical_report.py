"""Reconcile physical evidence, keeping functional and strict results separate."""
import collections
import shutil
import time
from pathlib import Path
from recheck import OUT,PRIOR,WORK,core

VARIANTS={('x86','native'),('x64','native'),('x64','translated')}

def main():
    groups=collections.defaultdict(dict);all_receipts={};extra=[]
    for prefix in ('audit-','creation-audit-'):
        for path in sorted(OUT.glob(prefix+'*.json'),key=lambda p:p.stat().st_mtime):
            d=core.read_large(path);core.require(d['passed'],'physical audit failed')
            mode=d.get('mode','creation' if prefix=='creation-audit-' else 'scalar')
            key=(mode,d.get('creation_config',d['parameters']['group']))
            variant=(d['parameters']['arch'],d['parameters']['variant'])
            if variant in groups[key]:extra.append(groups[key][variant][0])
            groups[key][variant]=(str(path),d);all_receipts[str(path)]=core.sha(path)
    core.require(len(groups)==17,'7 scalar + Clear + 8 creation + parent-query groups')
    differences=[];guards=[];strict=[];requests=[];counts=collections.Counter();selected=[]
    for (mode,group),variants in groups.items():
        core.require(set(variants)==VARIANTS,'three variants required')
        native=variants[('x86','native')][1]
        def obs(d):return d['observations'] if mode in ('scalar','clear') else d['queries'] if mode=='parent-queries' else [d['observation']]
        baseline=obs(native);counts[mode]+=len(baseline)
        for variant,(path,d) in variants.items():
            selected.append(path);requests.append(d['historical_service_verdict'])
            strict.extend(dict(receipt=path,variant=variant,group=[mode,group],difference=e) for e in d['strict_differences'])
            core.require(len(obs(d))==len(baseline),'matched sample count')
            for i,(a,b) in enumerate(zip(baseline,obs(d))):
                if b.get('rejected'):
                    guards.append(dict(receipt=path,group=[mode,group],sample=b['sample'],seed=b['seed'],native_hresult=a['hr'],native_last_error=a['error'],translated='guard rejection; no native call'))
                elif a!=b:differences.append(dict(group=[mode,group],variant=variant,index=i,native=a,observed=b))
    core.require(not differences,'functional comparison discrepancy')
    core.require(dict(counts)==dict(scalar=408,clear=24,creation=8,**{'parent-queries':24}),'sample coverage changed')
    gamma_path=OUT/'semantic-gamma-v2-request.json';gamma=None;gamma_response=None
    if gamma_path.exists():
        req=core.read(gamma_path);response=WORK/'out/semantic-gamma-fixtures-v2/responses'/(req['id']+'.json')
        if response.exists():
            gamma_response=core.read_large(response);directory=Path(gamma_response['evidence'])
            gamma=core.read_large(directory/'semantic-gamma-assessment.json')
            core.require(gamma['passed'] and gamma['process_count']==3 and gamma['desktop_gamma_restoration']['passed'],'gamma qualification/restoration incomplete')
            core.require(len(gamma['results'])==3 and all(r['passed'] and len(r['observations'])==16 for r in gamma['results']),'complete gamma matrix')
            core.require(gamma['results'][0]['observations']==gamma['results'][1]['observations']==gamma['results'][2]['observations'],'gamma native comparison')
            for i,r in enumerate(gamma['results']):strict.extend(dict(group=['gamma',i],difference=e) for e in r['strict_differences'])
            counts['gamma']=16
    files=dict(all_receipts)
    # Bind every raw capture/request/build receipt, including duplicates. Failed
    # schema receipts remain failed and are never rewritten by this report.
    responses=requests+[core.read_large(p)['historical_service_verdict'] for p in map(Path,extra)]
    for response in responses+([gamma_response] if gamma_response else []):
        root=Path(response['evidence'])
        files.update({str(root/n):v for n,v in core.tree(root).items()})
        request=core.read(root/'request.json');candidate=WORK/'out/desktop-fixtures/candidates'/request['candidate_id']/'candidate.json'
        if not candidate.exists():
            from supervisor.fixture_profiles import candidate_path
            candidate=candidate_path(request['candidate_id'])
        manifest=core.read_large(candidate)
        for path,digest in manifest['files'].items():core.require(core.sha(path)==digest,'physical fixture source/build changed');files[path]=digest
        files[str(candidate)]=core.sha(candidate)
    first=WORK/'out/semantic-gamma-fixtures/evidence/0bc41610-5bfd-4184-a150-6df4188c635a'
    files.update({str(first/n):v for n,v in core.tree(first).items()})
    p=OUT/'gamma-first-capture-independent-audit.json';files[str(p)]=core.sha(p)
    if gamma:
        p=OUT/'gamma-independent-audit.json';independent=core.read_large(p)
        core.require(independent['passed'] and independent['request']==gamma_response['id'],'independent gamma audit binding')
        files[str(p)]=core.sha(p)
    ci=core.read_large(OUT/'candidate-identity.json')
    result=dict(functional_qualified=gamma is not None,status='QUALIFIED_FOR_BOUNDED_OBSERVATION' if gamma else 'PENDING_REPAIRED_GAMMA_SERVICE',
        candidate_sha256=ci['sha256'],observed_at=time.time(),physical_gpu='NVIDIA GeForce RTX 5090',backend='pinned DXVK 3.1.1',
        variants=sorted(VARIANTS),comparison_triples=dict(counts),selected_receipts=selected,extra_receipts=extra,all_receipts=all_receipts,
        functional_differences=differences,invalid_domain_rejections=guards,strict_differences=strict,
        strict_compatibility='FAILED; retained x87/WNDPROC/native-x86 failures and newly measured FPU status/control differences',
        gamma_response=gamma_response,raw_evidence_files=files,genuine_launches=0,production_accepted=False,
        old_formal_collector='Strict historical sample parser rejected the new schemas; all original failed responses remain failed. This is an independent semantic functional qualification.',
        limitations=['Sampled domains, not exhaustive arbitrary D3D8 input coverage','Owned USER32 callbacks occurred; no callback during a measured native call; production registered guest WNDPROC not physically qualified',
            'Creation/Clear/public-query ABI envelopes cover typed wrappers; native HRESULT/error and semantic CPU/COM are additionally checked',
            'Gamma is windowed backend readback; no visible/fullscreen effect inferred','Prior Present/factory/strict-x87/WNDPROC measurements retain only their original documented scope',
            'No gameplay, arbitrary resources, drawing, reset/lost-device, fullscreen or game cleanup qualification'])
    core.atomic(OUT/'physical-qualification.json',result)
    archive=OUT/'historical-checkpoints';archive.mkdir(exist_ok=True)
    for name in ('REPORT.txt','continuation-readiness.json','pending-physical-matrix.json','checkpoint-seal.json'):
        if (OUT/name).exists() and not (archive/name).exists():shutil.copy2(OUT/name,archive/name)
    ready=dict(status=result['status'],candidate=ci['executable'],candidate_sha256=ci['sha256'],physical_qualified=result['functional_qualified'],launch_package_sealed=False,
        proposed_initial_call='0x11104BF5',proposed_stop='0x11104BF8',maximum_launches=1,maximum_seconds=60,retry=False,genuine_authorized=False,genuine_launches=0,
        production_stop='0x0696F292 unchanged',strict_compatibility='FAILED retained',remaining=[] if gamma else ['Restart locally into qualified gamma_service_v2.py and complete three-variant gamma comparison'])
    core.atomic(OUT/'continuation-readiness.json',ready)
    text=f'''UNREAL II — SEMANTIC PHYSICAL QUALIFICATION
Status: {result['status']}

Candidate: {ci['executable']}
SHA-256: {ci['sha256']}
PDB: {ci['pdb_sha256']}
PE/PDB GUID {ci['pe_pdb']['guid']}, age {ci['pe_pdb']['age']}.
279 independently verified objects: 265 generated and 12 runtime reused;
hle_gui and the D3D-owning hle_misc rebuilt. All 14 linked adapter bindings pass.
No runtime source correction or replacement candidate was needed.

ACTUAL PHYSICAL RESULTS
NVIDIA GeForce RTX 5090; pinned DXVK 3.1.1. Actual native x86, native x64,
and translated source-exact semantic adapters compared on the physical desktop.
- Scalar/material/transform/state/resource/FVF: 408 triples / 1224 calls.
- Clear: 24 triples / 72 calls, including actual target-pixel readback.
- CreateDevice: 8 configurations x 3 variants; normalized PP, HRESULT,
  last-error, CPU, ownership and cleanup match. Extra baseline runs retained.
- Public capability queries: 24 triples / 72 calls, including native failures.
- Gamma: {'16 triples / 48 calls PASS; device and both desktop ramps restored exactly.' if gamma else 'first native x86 capture: 16 calls functionally pass; strict MXCSR precision status fails. Device and both desktop ramps restored exactly. Remaining full three-variant comparison requires the repaired service.'}
No functional differences for admitted matched samples. 36 translated invalid-
domain rejections across scalar/Clear samples are preserved separately.
Native accepts stage-8 filtering, transform 999, ZENABLE 99, FVF 0, Clear flags 8
and depth 1.5 with S_OK; semantic guards reject those unsupported domains.
Native invalid texture stage 8 and stream 16 return 0x8876086C; translated guards
stop before native dispatch. These differences are not hidden as equality.

STRICT FAILURES AND LIMITS
Strict x87/WNDPROC/native-x86 compatibility remains FAILED. Native x86 creation
changes x87 CW 027F -> 067F; FSW/MXCSR status differences are recorded by sample.
Gamma {'all 48 matched calls change' if gamma else 'first capture changes'} MXCSR 3F80 -> 3FA0 with controls intact. Its original
service failure is retained; the repaired parser records strict FAILED apart
from functional equality. Historical formal-parser schema failures remain failed.
All selected captures verify zero remaining Job processes and final COM refs,
window/module cleanup, raw ABI and CPU/readback evidence within each fixture's
scope. Callback counts cover owned USER32 windows; active native-call callbacks
were zero. The production registered guest WNDPROC remains separately unqualified.
Creation/Clear/public-query ABI is the outer typed envelope, not an inner raw-call
measurement. Windowed gamma readback proves no fullscreen/visible ramp behavior.
Prior factory/Present evidence is reused only for its original scope. No gameplay,
arbitrary resource/draw, reset/lost-device or fullscreen qualification is claimed.

INITIAL SETRES PROPOSAL
Evidence-first observer: 16 tests, 12 live owned protocol cases, five inert
candidate hardware-stop cases and retained production-factory fixtures pass.
Proposed observer additionally rejects void-gamma guest EAX corruption. The
original sealed observer and candidate remain unchanged. No value-profile gate
was restored. Independent proposed owner/raw-evidence rejection tests pass.
Target: before guest 11104BF8 (call 11104BF5); one attempt, 60 seconds, no retry.
Separate local stop-scope and launch authorization is mandatory. The latest
production diagnostic hold (sequence 92) and production stop 0696F292 remain.
The proposal cannot launch without a final physical qualification seal.

No genuine game launch, candidate instruction execution, original-install/save
modification, production breakpoint change, remote push or release occurred.
All 630 prior sealed semantic files and protected source/history/assets reverify.
Raw hashes and selected receipts: physical-qualification.json.
'''
    (OUT/'REPORT.txt').write_text(text,encoding='utf-8')
    print(result['status'],dict(counts),'raw/source files',len(files),'strict rows',len(strict),flush=True)

if __name__=='__main__':main()
