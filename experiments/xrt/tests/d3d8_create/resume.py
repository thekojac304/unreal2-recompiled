"""Verify the post-crash checkpoint, then rerun only interrupted acceptance work."""
import json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import preserve as P
W,O,F=P.W,P.O,P.F
R=O/'resume-20261025-01'
def integrity():
    assert not R.exists();R.mkdir()
    oldsave=P.save
    P.save=lambda n,v:(R/n).write_text(json.dumps(v,indent=2))
    try:P.final()
    finally:P.save=oldsave
    for record in ['build.json','build-02.json']:
        b=F.read(O/record);assert b['status']=='PASS'
        root=W/'experiments/xrt/build'/('d3d8-create-20261025-01'if record=='build.json'else'd3d8-create-20261025-02')
        F.P.check(root,b['outputs'])
        if record=='build-02.json':assert all(P.tree(W/p)==h for p,h in b['sources'].items())
    T=W/'experiments/xrt/build/d3d8-create-fixture-20261025-05'
    F.P.check(T,F.read(T/'outputs.json'))
    for phase in ['d3d8','affected']:
        rec=F.read(O/f'regressions-{phase}-02.json');assert rec['passed']
        assert all(P.sha(r['log'])==r['log_sha256']for r in rec['runs'])
    rec=F.read(O/'regressions-acceptance-02.json')
    assert [r['name']for r in rec['runs']]==['tracer-build','commandlet-vm']
    assert all(r['passed']and P.sha(r['log'])==r['log_sha256']for r in rec['runs'])
    F.P.check(W/'sandbox_d3d8_create_20261025_02',F.read(O/'harness.json')['files'])
    (R/'integrity.json').write_text(json.dumps(dict(passed=True,binary_sha256=F.read(O/'build-02.json')['binary_sha256'],
        sources_and_generated_verified=True,both_production_builds_verified=True,fixture_outputs_verified=True,
        completed_regression_logs_verified=True,protected_assets_verified=True,interrupted_stage='unrealscript-compiler'),indent=2))
    print('POST-CRASH INTEGRITY PASS',flush=True)
def smoke():
    import shutil
    assert F.read(R/'integrity.json')['passed']
    T=W/'experiments/xrt/build/d3d8-create-fixture-20261025-06'
    shutil.copy2(O/'measurement-02.json',R/'precrash-measurement.json')
    for name,driver,args in [('build','run.py',['build','--out',str(T)]),('run','run.py',['run','--out',str(T)]),('audit','audit.py',['--out',str(T)])]:
        log=R/('fixture-'+name+'.log');assert not log.exists()
        print('POST-CRASH FIXTURE',name,flush=True)
        with log.open('wb')as f:r=subprocess.run([sys.executable,'-B','-I',str(HERE/driver),*args],cwd=W,stdout=f,stderr=subprocess.STDOUT)
        assert r.returncode==0,(name,log.read_text(errors='replace')[-5000:])
    result=F.read(T/'audit.json');result['postcrash']=True
    (R/'smoke.json').write_text(json.dumps(result,indent=2))
    print('POST-CRASH DEVICE/COM/ABI/CALLBACK/CONTAINMENT PASS',flush=True)
def acceptance():
    import regressions as G
    rec=F.read(O/'regressions-acceptance-02.json')
    assert (R/'integrity.json').exists()and F.read(R/'smoke.json')['passed']
    env=dict(os.environ,XRT_BINARY=str(G.B/'xrt_ucc.exe'),XRT_ASSET_MANIFEST=str(F.P.A.DEFAULT_MANIFEST),
        XRT_COMPARE_DIR=str(G.H/'experiments/xrt/results/compare/create-device'),PYTHONDONTWRITEBYTECODE='1',TMP=str(G.H/'tmp'),TEMP=str(G.H/'tmp'))
    for k in ['XRT_DMUSIC_BACKEND','XRT_DMUSIC_HELPER','CL','_CL_','LINK','_LINK_']:env.pop(k,None)
    py=str(G.H/'.venv/Scripts/python.exe')
    steps=[('unrealscript-compiler',[py,'-B','-I','tools/xrt/compile_xrt.py']),
        ('traced-vm',[py,'-B','-I','tools/xrt/run_xrt.py','vmprobe','--trace']),
        ('traced-hello',[py,'-B','-I','tools/xrt/run_xrt.py','hellofull','--trace']),
        ('python',[py,'-B','-I','-m','unittest','discover','-s','tools/xrt/tests','-v'])]
    import time,re,shutil
    shutil.copy2(O/'regressions-acceptance-02.json',R/'interrupted-acceptance.json')
    for name,cmd in steps:
        log=R/('regression-'+name+'.log');assert not log.exists();start=time.monotonic();runenv=dict(env)
        if name=='python':runenv['XRT_FULL']='1'
        print('START',name,flush=True)
        with log.open('wb')as f:r=subprocess.run(cmd,cwd=G.H,env=runenv,stdout=f,stderr=subprocess.STDOUT,timeout=1500)
        txt=log.read_text(errors='replace');assert r.returncode==0 and not re.search(r'\b(?:C1001|D8040)\b',txt),(name,txt[-5000:])
        row=dict(name=name,command=cmd,cwd=str(G.H),exit=r.returncode,seconds=time.monotonic()-start,log=str(log),log_sha256=P.sha(log),warnings=re.findall(r'^.*warning [A-Z]+\d+.*$',txt,re.M),passed=True)
        rec['runs'].append(row);P.save('regressions-acceptance-02.json',rec);print('PASS',name,flush=True)
    rec['passed']=True;P.save('regressions-acceptance-02.json',rec)
    shutil.copy2(R/'regression-python.log',O/'regression-python-02.log')
    print('POST-CRASH ACCEPTANCE PASS',flush=True)
def finish():
    smoke();acceptance()
    for name,driver,args in [('report','report.py',[]),('final-integrity','preserve.py',['final'])]:
        print('START',name,flush=True);log=R/(name+'.log');assert not log.exists()
        with log.open('wb')as f:r=subprocess.run([sys.executable,'-B','-I',str(HERE/driver),*args],cwd=W,stdout=f,stderr=subprocess.STDOUT)
        assert r.returncode==0,(name,log.read_text(errors='replace')[-5000:])
        print('PASS',name,flush=True)
    print('ALL AUTHORIZED WORK COMPLETE AFTER CRASH RECOVERY',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
