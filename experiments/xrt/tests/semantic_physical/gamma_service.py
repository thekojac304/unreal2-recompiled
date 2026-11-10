"""Qualified additive semantic parser for the existing restoring gamma family.

Uses an independent service home. Original service code, qualification, grants,
ledgers, failures and genuine breakpoint remain unchanged.
"""
import argparse
import sys
import uuid
from pathlib import Path
import gamma as G
import audit_gamma as A
from recheck import HERE,OUT,WORK,core
from supervisor import development as D, fixture_collector as T, fixture_profiles as F
from supervisor.service import verify_seal
from supervisor.fixture_qualification import checked,qualification_cycles

S=G.service
S.HOME=WORK/'out/semantic-gamma-fixtures'


def runner(request,candidate,out,stop,progress,**kwargs):
    core.require(request['family']==S.FAMILY,'only restoring gamma family allowed')
    root=F.candidate_path(candidate['id']).parent;captures=out/'captures';captures.mkdir();(out/'evidence').mkdir()
    results=[];classification='fixture-complete';reason=None
    ramp=(S.P.O/'actual-gamma-ramp.bin').read_bytes()
    try:
        D.physical_gate(out,dict(family='renderer-group'),qualification=False)
        with S.DesktopGamma(out):
            for item in S.plan(S.FAMILY,{},root):
                progress();D.physical_gate(out,dict(family='renderer-group'),qualification=False)
                # The inherited aggregate record has all three PEs, but the
                # original collector requires one architecture. Derive explicit
                # per-capture metadata while retaining EVERY sealed input,
                # output and toolchain hash and the parent-record identity.
                record=core.read_large(root/'build/build-record.json')
                record.update(arch=item['arch'],aggregate_record=str(root/'build/build-record.json'),aggregate_sha256=core.sha(root/'build/build-record.json'))
                build=out/('build-'+item['name']+'.json');core.atomic(build,record)
                E,_,_=F.modules();pair=E.P.G.verified_pair(item['arch']);directory=captures/item['name']
                T.capture(item['exe'],['--physical',pair,'--gamma-physical'],directory,build_record=build,
                    backend=[pair/'d3d8.dll',pair/'d3d9.dll'],timeout=request['timeout_seconds'],stop=stop,physical=True)
                result=A.capture(directory,item,build,ramp);core.atomic(directory/'semantic-assessment.json',result);results.append(result)
            core.require(results[0]['observations']==results[1]['observations']==results[2]['observations'],'native/translated gamma discrepancy')
    except core.IntegrityFailure:raise
    except BaseException as error:
        classification='unclassified-correctness';reason=repr(error)
    finally:
        receipts=[core.read(p) for p in captures.glob('*/containment.json')]
        cleanup=len(receipts)==len(list(captures.iterdir())) and all(r['verified'] for r in receipts)
        F.verify_identities(candidate['files']);core.atomic(out/'assurance.json',dict(cleanup_verified=cleanup,integrity_verified=True))
        if not cleanup:raise core.IntegrityFailure('gamma Job cleanup unverified')
    result=dict(passed=classification=='fixture-complete',classification=classification,reason=reason,
        process_count=len(receipts),genuine_launches=0,results=results,strict_compatibility_verdict='FAILED; historical x87/WNDPROC retained',
        desktop_gamma_restoration=core.read(out/'desktop-gamma-restored.json') if (out/'desktop-gamma-restored.json').exists() else None)
    core.atomic(out/'semantic-gamma-assessment.json',result);return result


def qualify():
    out=S.HOME/('qualification-'+str(uuid.uuid4()));out.mkdir(parents=True);(out/'evidence').mkdir()
    previous=core.read_large(G.WORK/'out/desktop-prerequisites/qualification.json');verify_seal(previous)
    checked([sys.executable,'-B','-I','-m','unittest','discover','-s',str(WORK/'tools/xrt/supervisor/tests'),'-v'],out,'supervisor-tests')
    checked([sys.executable,'-B','-I','-m','unittest','discover','-s',str(F.RENDERER),'-p','test_*.py','-v'],out,'collector-tests')
    cycles=qualification_cycles(out)
    # No qualification-only flag can admit gamma on the construction desktop.
    gate_rejected=False
    try:D.physical_gate(out,dict(family='renderer-group'),qualification=True)
    except D.DesktopUnavailable:gate_rejected=True
    files=dict(previous['files'])
    for name in ('gamma_service.py','gamma.py','audit_gamma.py','audit.py','recheck.py'):
        path=HERE/name;files[path.relative_to(WORK).as_posix()]=core.sha(path)
    path=HERE.parent/'semantic_compat/common.py';files[path.relative_to(WORK).as_posix()]=core.sha(path)
    seal=dict(passed=True,files=files,host_files=previous['host_files'],evidence=str(out),cycles=cycles,
        family=S.FAMILY,genuine_launches=0,graphics_devices_created=0,construction_graphics_gate_rejected=gate_rejected,
        prior_qualification_sha256=core.sha(G.WORK/'out/desktop-prerequisites/qualification.json'))
    core.atomic(out/'qualification.json',seal);core.atomic(S.HOME/'qualification.json',seal)
    print('Semantic restoring service qualified; no GPU/game launch',out,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['qualify','serve','submit','status']);args=p.parse_args()
    if args.command=='qualify':qualify()
    elif args.command=='serve':S.runner=runner;S.serve()
    elif args.command=='status':print(D.read_status(S.HOME))
    else:
        spec=core.read(OUT/'prepared-semantic-gamma.json')
        ident=D.submit(spec['candidate_id'],'Measure exact semantic gamma flags 0/1 and configured/linear ramps with independent parent-owned restoration and native x86/x64/translated comparison',home=S.HOME)
        core.atomic(OUT/'semantic-gamma-request.json',dict(id=ident,candidate=spec['candidate_id']));print(ident)
