"""Serial continuation after the full build; stop on any failed acceptance gate."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3]
O=W/'out/recovery/d3d8-create-20261025-01';T=W/'experiments/xrt/build/d3d8-create-fixture-20261025-05'
def main():
    deadline=time.monotonic()+1800
    while True:
        try:b=json.loads((O/'build-02.json').read_text())
        except json.JSONDecodeError:b={}
        if b.get('status')=='PASS':break
        if b.get('commands')and b['commands'][-1]['exit']!=0:raise RuntimeError('production build failed')
        assert time.monotonic()<deadline,'full build wait exceeded'
        time.sleep(10)
    print('FULL BUILD VERIFIED; start final serial fixture and regressions',flush=True)
    steps=[('prepare-harness','prepare_regressions.py',[]),('prepare-guards','regressions.py',['prepare']),('fixture-build','run.py',['build','--out',str(T)]),('fixture-run','run.py',['run','--out',str(T)]),('fixture-audit','audit.py',['--out',str(T)]),
        ('d3d8','regressions.py',['d3d8']),('affected','regressions.py',['affected']),('acceptance','regressions.py',['acceptance']),
        ('report','report.py',[]),('final-integrity','preserve.py',['final'])]
    if len(sys.argv)>1:steps=steps[[s[0]for s in steps].index(sys.argv[1]):]
    for name,driver,args in steps:
        print('START',name,flush=True);log=O/('completion02-'+name+'.log')
        if log.exists():log=O/('completion02-'+name+'-retry.log')
        assert not log.exists()
        with log.open('wb')as f:r=subprocess.run([sys.executable,'-B','-I',str(HERE/driver),*args],cwd=W,stdout=f,stderr=subprocess.STDOUT)
        print('END',name,r.returncode,flush=True)
        if r.returncode:
            print(log.read_text(errors='replace')[-5000:],flush=True);sys.exit(r.returncode)
    print('ALL AUTHORIZED WORK COMPLETE',flush=True)
if __name__=='__main__':main()
