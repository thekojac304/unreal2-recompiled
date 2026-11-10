"""Seal only a fully qualified proposal. Never authorize or launch a game."""
import ast
import pathlib
import shutil
import subprocess
import sys
HERE=pathlib.Path(__file__).resolve().parent
W=HERE.parents[3]
OUT=W/'out/recovery/semantic-physical-20261030-01'
O=OUT/'continuation-proposal'
sys.path.insert(0,str(O))
from common import *

def main():
    core.require(not (O/'seal.json').exists(),'preserve existing sealed proposal')
    physical=read(OUT/'physical-qualification.json')
    core.require(physical['functional_qualified'] and physical['candidate_sha256']==SHA,'physical qualification incomplete')
    for path,digest in physical['raw_evidence_files'].items():core.require(core.sha(path)==digest,'physical raw/source evidence changed')
    from identity import verify
    ci=verify();save(O/'candidate-identity.json',ci)
    for name in ('physical-qualification.json','preservation-after.json','prior-seal-verification.json'):
        shutil.copy2(OUT/name,O/name)
    core.require(read(O/'preservation-after.json')['passed'] and read(O/'prior-seal-verification.json')['passed'],'preservation incomplete')
    core.require(read(O/'debugger-validation.json')['passed'] and read(O/'debugger-validation.json')['candidate_sha256']==SHA,'hardware qualification binding')
    core.require(read(O/'observer-tests.json')['tests']==16 and read(O/'observer-tests.json')['source_sha256']==core.sha(O/'observer.py'),'observer unit binding')
    core.require(read(O/'live-observer-validation.json')['passed'] and read(O/'live-observer-validation.json')['observer_sha256']==core.sha(O/'observer.py'),'live observer binding')
    # Save the independent owner/evidence tests before sealing their receipt.
    cmd=[sys.executable,'-B','-I',str(HERE/'test_continuation.py'),'-v']
    result=subprocess.run(cmd,cwd=W,capture_output=True,timeout=60)
    (O/'owner-tests.stdout.bin').write_bytes(result.stdout);(O/'owner-tests.stderr.bin').write_bytes(result.stderr)
    core.require(result.returncode==0 and b'Ran 12 tests' in result.stderr,'owner rejection/evidence tests failed')
    save(O/'owner-tests.json',dict(passed=True,tests=12,source=str(HERE/'test_continuation.py'),source_sha256=core.sha(HERE/'test_continuation.py'),command=cmd,genuine_launches=0))
    from supervisor.service import seal_files
    from supervisor.qualify import host_files
    from supervisor import fixture_profiles
    fixture_profiles.modules()
    import graphics_backend,owner,mapping
    import gamma_guard
    # Retain the complete previously qualified launch/enforcement dependency
    # closure, but validate every byte instead of trusting the old pass label.
    old=read(W/'out/recovery/setres-initial-completion-20261029-01/seal.json')
    files=dict(old['files'])
    for path,digest in files.items():core.require(core.sha(path)==digest,'retained owner dependency changed: '+path)
    files.update({str(W/p):v for p,v in seal_files().items()})
    def class_text(path):
        source=path.read_text();return ast.get_source_segment(source,next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='DesktopGamma'))
    core.require(class_text(O/'gamma_guard.py')==class_text(HERE.parent/'renderer_prerequisites/service.py'),'restoring gamma guard changed')
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=pathlib.Path(name).absolute()
            if path.is_file() and path.is_relative_to(W):files[str(path)]=core.sha(path)
    for root in (O,H,EXE.parent,RT,W/'experiments/xrt/gen'):
        files.update({str(root/p):v for p,v in core.tree(root).items()})
    b=read(O/'build.json')
    for record in {str(O/'object-lineage.json'),*ci['transitive_object_records']}:
        files[record]=core.sha(record)
        for value in read(record).values():
            if not isinstance(value,dict) or 'command' not in value:continue
            files[value['source']]=value['source_sha256'];files.update(value.get('verified_local_headers',{}))
            output=next((a[3:] for a in value['command'] if a.startswith('/Fo')),None)
            if output:files[output]=value['object_sha256']
    files.update(ci['dependencies']);files.update(b['toolchain']);files.update(host_files())
    files.update(read(O/'resolved-hold.json')['evidence']);files.update(physical['raw_evidence_files'])
    for path,digest in files.items():core.require(core.sha(path)==digest,'final closure mismatch: '+path)
    plan=mapping.resolve()
    save(O/'seal.json',dict(passed=True,ready_for_owner_authorization=True,scope=SCOPE,candidate_sha256=SHA,pdb_sha256=PDB,
        guest_stop=GUEST,stop_rva=RVA,stop_bytes=plan['stop_bytes'],maximum_launches=1,maximum_seconds=60,retry=False,
        genuine_authorized=False,genuine_launches=0,owner_phrase=PHRASE,separate_stop_phrase=STOP_PHRASE,
        separate_owner_stop_authorization_pending=True,implementation={p.name:core.sha(p) for p in O.glob('*.py')},files=files,
        dependencies=ci['dependencies'],strict_x87='FAILED retained',strict_WNDPROC='FAILED retained',strict_native_x86='FAILED retained'))
    owner.validate_seal();owner.execution_gate()
    save(O/'seal-validation.json',dict(passed=True,files=len(files),seal_sha256=core.sha(O/'seal.json'),candidate_unconsumed=True,
        genuine_launches=0,genuine_authorized=False,production_stop_unchanged=True,ready_for_separate_owner_action=True))
    ready=read(OUT/'continuation-readiness.json');ready.update(status='READY_FOR_SEPARATE_OWNER_AUTHORIZATION',launch_package_sealed=True,physical_qualified=True,
        owner_command=f"& '{W / '.venv/Scripts/python.exe'}' -B -I '{O / 'owner.py'}' launch-once",owner_phrase=PHRASE,separate_stop_phrase=STOP_PHRASE)
    save(OUT/'continuation-readiness.json',ready)
    action=f'''BOUND INITIAL SETRES OWNER ACTION — NOT YET AUTHORIZED

Candidate SHA-256: {SHA}
One launch maximum; 60 seconds; no retry. Stop before guest 11104BF8.
Production stop 0696F292 and diagnostic hold remain unchanged.
Strict x87/WNDPROC/native-x86 compatibility remains FAILED.

On the signed-in physical desktop, stop the disposable fixture console with
Ctrl+C. Run from an ordinary PowerShell:

{ready['owner_command']}

Only if you approve this separately proposed stop scope, enter:
{STOP_PHRASE}

Then, only if you approve the single genuine test, enter:
{PHRASE}

This command does launch the genuine copied game. It was NOT executed during
qualification. Do not use historical launchers, alter the endpoint, reuse an
old grant or retry a consumed attempt. Any identity/hold/STOP/cleanup failure
requires preserving the evidence and investigation. A changed ledger or sealed
file rejects before launch. No original installation or save is modified.
'''
    (OUT/'OWNER-ACTION.txt').write_text(action,encoding='utf-8')
    with (OUT/'REPORT.txt').open('a',encoding='utf-8') as f:f.write('\nFINAL OWNER PACKAGE: sealed and independently validated. See OWNER-ACTION.txt.\nNo genuine launch authorization has been granted or consumed.\n')
    print('SEALED',len(files),'files; candidate unconsumed; separate owner authorization required; zero genuine launches',flush=True)

if __name__=='__main__':main()
