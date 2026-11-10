"""Run affected suites and acceptance against the fresh production binary."""
import argparse,os,re,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import preserve as P
W,O,F=P.W,P.O,P.F;H=W/'sandbox_d3d8_create_20261025_02';B=W/'experiments/xrt/build/d3d8-create-20261025-02'
def prepare():
    b=F.read(O/'harness.json')
    # This old probe has NULL presentation/output and now has a precise pointer
    # diagnostic, while continuing to reject before the backend. Preserve the
    # original suite source; adapt only this independent copied harness.
    p=H/'experiments/xrt/tests/d3d8_enum/run.py'
    text=p.read_text();assert "'CreateDevice is unmeasured'"in text
    p.write_text(text.replace("'CreateDevice is unmeasured'","'D3D8 device: invalid writable guest range'"))
    b['files'][p.relative_to(H).as_posix()]=P.sha(p)
    for arch in ['x86','x64']:
        for n in F.P.G.HASHES[arch]:
            import shutil
            src=F.P.G.verified_pair(arch)/n;rel=src.relative_to(W);dest=H/rel
            dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();shutil.copy2(src,dest)
            assert P.sha(dest)==P.sha(src);b['files'][rel.as_posix()]=P.sha(dest)
    P.save('harness.json',b)
def main(phase):
    recpath=O/('regressions-'+phase+'-02.json');assert not recpath.exists()
    assert F.read(O/'build-02.json')['status']=='PASS'
    env=dict(os.environ,XRT_BINARY=str(B/'xrt_ucc.exe'),XRT_ASSET_MANIFEST=str(F.P.A.DEFAULT_MANIFEST),
        XRT_COMPARE_DIR=str(H/'experiments/xrt/results/compare/create-device'),PYTHONDONTWRITEBYTECODE='1',TMP=str(H/'tmp'),TEMP=str(H/'tmp'))
    for k in ['XRT_DMUSIC_BACKEND','XRT_DMUSIC_HELPER','CL','_CL_','LINK','_LINK_']:env.pop(k,None)
    py=str(H/'.venv/Scripts/python.exe')
    def python(*a):return [py,'-B','-I',*a]
    if phase=='affected':
        names=['setforeground_boundary','setactive_boundary','setcapture_boundary','foreground_boundary','window_ae_boundary','clipcursor_boundary','mapwindowpoints_boundary','window_ids_boundary','setcursor_boundary','geticon_boundary','setfocus_boundary','immassociatecontext_boundary','adjustwindowrect_boundary','gui_boundary','class_boundary','module_boundary','focus_boundary','input_boundary']
        suites=[(n,['cmd','/d','/c','experiments\\xrt\\tests\\'+n+'\\build.cmd'])for n in names]
        suites.append(('com',['cmd','/d','/c','experiments\\xrt\\tests\\directmusic_boundary\\build_com.cmd']))
    elif phase=='d3d8':
        dest=H/'experiments/xrt/build/d3d8-create-regression'
        suites=[('d3d8-'+action,python('experiments/xrt/tests/d3d8_depth/run.py',action,'--out',str(dest)))for action in ['build_native','characterize','build_translated','compare']]
    else:
        assert phase=='acceptance'
        suites=[('tracer-build',['cmd','/d','/c','experiments\\xrt\\tracer\\build.cmd']),
            ('commandlet-vm',python('tools/xrt/run_xrt.py','hellofull','hello_noargs','hellonew','hellofull_nosse','simple','arraytest','hello','badclass','vmprobe')),
            ('unrealscript-compiler',python('tools/xrt/compile_xrt.py')),
            ('traced-vm',python('tools/xrt/run_xrt.py','vmprobe','--trace')),
            ('traced-hello',python('tools/xrt/run_xrt.py','hellofull','--trace')),
            ('python',python('-m','unittest','discover','-s','tools/xrt/tests','-v'))]
    rec=dict(phase=phase,passed=False,runs=[])
    for name,cmd in suites:
        F.P.check(H,F.read(O/'harness.json')['files'])
        print('START',name,flush=True);log=O/('regression-'+name+'-02.log');start=time.monotonic();runenv=dict(env)
        if name=='python':runenv['XRT_FULL']='1'
        with log.open('wb')as f:r=subprocess.run(cmd,cwd=H,env=runenv,stdout=f,stderr=subprocess.STDOUT,timeout=1500)
        text=log.read_text(errors='replace');row=dict(name=name,command=cmd,cwd=str(H),exit=r.returncode,seconds=time.monotonic()-start,log=str(log),log_sha256=P.sha(log),warnings=re.findall(r'^.*warning [A-Z]+\d+.*$',text,re.M))
        row['passed']=r.returncode==0 and not re.search(r'\b(?:C1001|D8040)\b',text)
        rec['runs'].append(row);P.save(recpath.name,rec);print('RESULT',name,r.returncode,round(row['seconds'],2),flush=True)
        assert row['passed'],('STOP regression',name,text[-4000:])
    rec['passed']=True;P.save(recpath.name,rec)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('phase',choices=['prepare','affected','d3d8','acceptance']);v=a.parse_args();prepare()if v.phase=='prepare'else main(v.phase)
