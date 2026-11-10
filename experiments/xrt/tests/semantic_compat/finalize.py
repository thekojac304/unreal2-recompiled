"""Final receipts and preservation. No game/GPU launch or queue submission."""
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def tests():
    out=O/('final-tests-'+str(uuid.uuid4()));out.mkdir();results=[]
    for name,path in [('semantic-observer',H),('supervisor',W/'tools/xrt/supervisor/tests'),('renderer-collector',H.parent/'renderer_batch')]:
        cmd=[W/'.venv/Scripts/python.exe','-B','-I','-m','unittest','discover','-s',path,'-v']
        start=time.monotonic()
        try:p=subprocess.run(list(map(str,cmd)),cwd=W,capture_output=True,timeout=180)
        except subprocess.TimeoutExpired as error:
            (out/(name+'.stdout.bin')).write_bytes(error.stdout or b'');(out/(name+'.stderr.bin')).write_bytes(error.stderr or b'')
            save(out/(name+'.json'),dict(passed=False,timeout=True,seconds=time.monotonic()-start,command=list(map(str,cmd))))
            raise
        (out/(name+'.stdout.bin')).write_bytes(p.stdout);(out/(name+'.stderr.bin')).write_bytes(p.stderr)
        count=re.search(rb'Ran (\d+) tests?',p.stderr)
        result=dict(name=name,command=list(map(str,cmd)),passed=p.returncode==0,tests=int(count[1]) if count else None,exit=p.returncode,seconds=time.monotonic()-start)
        save(out/(name+'.json'),result);core.require(result['passed'],name+' tests failed: '+p.stderr[-2000:].decode(errors='replace'));results.append(result)
        save(O/'unit-regressions-partial.json',dict(passed=False,complete=False,root=str(out),results=results))
        print(name,result['tests'],'PASS',flush=True)
    save(O/'unit-regressions.json',dict(passed=True,root=str(out),results=results,runtime=core.tree(RT)))

def preservation():
    before=read(O/'preservation.json');results={}
    for path,expected in before['trees'].items():
        actual=core.tree(Path(path));core.require(actual==expected,'preserved historical/source/enforcement tree changed: '+path)
        results[path]=dict(passed=True,files=len(actual),digest=core.digest(actual))
        print('Preserved',path,flush=True)
    core.require(A.verify()==before['protected'],'protected snapshot inputs changed')
    save(O/'preservation-after.json',dict(passed=True,trees=results,protected_snapshot_inputs_match=True,
        original_installation_or_saves_written=False,genuine_launches=0,supervisor_policy_changed=False,strict_verdicts_changed=False))
    services={}
    for name in ('desktop-fixtures','desktop-prerequisites'):
        path=W/'out'/name/'status.json';data=read(path)
        services[name]=dict(path=str(path),sha256=core.sha(path),saved_status=data,
            saved_authorization_expired=data['batch']['expires_at']<time.time(),available=data.get('state')!='stopped' and data['batch']['expires_at']>time.time())
    save(O/'physical-availability.json',dict(observed_at=time.time(),services=services,submitted=False,physical_fixtures_run=0))

def observer_tests():
    out=O/('final-observer-tests-'+str(uuid.uuid4()));out.mkdir()
    cmd=[W/'.venv/Scripts/python.exe','-B','-I','-m','unittest','discover','-s',H,'-v']
    p=subprocess.run(list(map(str,cmd)),cwd=W,capture_output=True,timeout=60)
    (out/'stdout.bin').write_bytes(p.stdout);(out/'stderr.bin').write_bytes(p.stderr)
    count=re.search(rb'Ran (\d+) tests?',p.stderr)
    result=dict(passed=p.returncode==0,root=str(out),tests=int(count[1]) if count else None,
        observer_sha256=core.sha(H/'observer.py'),command=list(map(str,cmd)),exit=p.returncode)
    save(O/'final-observer-tests.json',result);core.require(result['passed'],'final observer tests failed')
    print('Final observer:',result['tests'],'PASS',flush=True)

def package():
    b=read(O/'build.json');plan=read(O/'stop-mapping.json');ci=read(O/'candidate-identity.json')
    core.require(b['binary_sha256']==ci['sha256']==plan['sha256'],'final candidate identity binding')
    core.require(read(O/'live-observer-validation.json')['passed'] and read(O/'debugger-validation.json')['passed'],'live observer/hardware qualification incomplete')
    core.require(read(O/'unit-regressions.json')['passed'] and read(O/'preservation-after.json')['passed'],'regression/preservation incomplete')
    core.require(core.tree(RT)==b['runtime']==read(O/'contracts.json')['runtime']==read(O/'unit-regressions.json')['runtime'],'final-source regression binding')
    core.require(read(O/'live-observer-validation.json')['observer_sha256']==read(O/'final-observer-tests.json')['observer_sha256']==core.sha(H/'observer.py'),'final observer receipt binding')
    core.require(read(O/'debugger-validation.json')['candidate_sha256']==ci['sha256'],'final hardware mapping receipt binding')
    summary=dict(version=1,prepared=True,genuine_authorized=False,genuine_launches=0,gameplay_verified=False,
        candidate=dict(executable=str(Path(b['root'])/'xrt_ucc.exe'),sha256=b['binary_sha256'],pdb_sha256=b['pdb_sha256'],compiled_objects=2,reused_objects=277,total_objects=279),
        guest_stop='0x11104bf8',stop_rva=plan['stop_rva'],stop_bytes=plan['stop_bytes'],stop_registers=plan['stop_registers'],
        correct_caller='WinDrv 11104BF5; frame=[return,viewport,width,height,fullscreen,color_bits], renderer in ECX, RET20 / ESP+24',
        maximum_seconds=60,retry=False,endpoint_installed_on_game=False,production_supervisor_unchanged=True,
        required_safeguards=['fresh unconsumed candidate and sandbox','independent permanent hardware breakpoint/readback on all threads',
            'bounded Job with independent watchdog and terminate-before-continue','pinned files/modules and process isolation',
            'complete runtime/debugger/native/CPU/FPU/callback evidence','verified zero remaining Job processes and input/gamma restoration'],
        non_graphical_qualified=True,broader_physical_GPU_domains_qualified=False,ready_for_genuine_launch=False,
        prerequisites=['Owner starts/re-authorizes an available physical desktop fixture supervisor; both saved services stopped and the desktop-fixture authorization expired',
            'Qualify the final semantic adapters on physical GPU with the retained restoring gamma guard and accepted evidence collector',
            'Review and separately authorize the new candidate and initial SetRes stop scope; do not reuse any consumed identity or expired authorization'],
        strict_failures=dict(x87='FAILED retained',WNDPROC_equality='FAILED retained',native_x86_compatibility='FAILED retained'))
    save(O/'continuation-plan.json',summary)
    files={str(p):core.sha(p) for p in H.glob('*') if p.is_file()}
    files.update({str(RT/n):v for n,v in core.tree(RT).items()})
    for name in ('build.json','object-lineage.json','candidate-identity.json','linked-adapter-audit.json','stop-mapping.json','guard-inventory.json','windows-import-audit.json',
                 'contracts.json','boolean-differential.json','gui-differential.json','attach-regressions.json','registered-regressions.json','resize-regressions.json',
                 'unit-regressions.json','final-observer-tests.json','live-observer-validation.json','debugger-validation.json','preservation.json','preservation-after.json','continuation-plan.json',
                 'physical-availability.json','original-provenance.json','source-change.json','semantic-changes.json','status-updates.json','REPORT.txt'):
        files[str(O/name)]=core.sha(O/name)
    for path in read(O/'status-updates.json'):files[path]=core.sha(path)
    for name in ('contracts.json','boolean-differential.json','gui-differential.json','attach-regressions.json','registered-regressions.json','resize-regressions.json',
                 'unit-regressions.json','final-observer-tests.json','live-observer-validation.json','debugger-validation.json'):
        receipt=read(O/name);root=Path(receipt.get('root',receipt.get('evidence','')))
        core.require(root.is_relative_to(O),'unexpected evidence root')
        files.update({str(root/n):v for n,v in core.tree(root).items()})
    files.update(ci['dependencies']);files.update(b['toolchain'])
    for name in ('xrt_ucc.exe','xrt_ucc.pdb'):files[str(Path(b['root'])/name)]=core.sha(Path(b['root'])/name)
    save(O/'handoff-seal.json',dict(passed=True,files=files,candidate_sha256=b['binary_sha256'],genuine_authorized=False,
        ready_for_physical_qualification=True,ready_for_genuine_launch=False,physical_promotion_pending=True))
    print('Handoff prepared; physical promotion pending; no genuine launch authorized or performed.',flush=True)

if __name__=='__main__':
    assert sys.argv[1:] in (['tests'],['observer_tests'],['preservation'],['package']);globals()[sys.argv[1]]()
