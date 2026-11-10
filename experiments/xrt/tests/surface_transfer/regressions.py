import sys,uuid,subprocess,re,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    out=O/('regressions-'+str(uuid.uuid4()));out.mkdir();results=[]
    for name,path in [('supervisor',W/'tools/xrt/supervisor/tests'),('renderer-collector',H.parent/'renderer_batch')]:
        cmd=[sys.executable,'-B','-I','-m','unittest','discover','-s',str(path),'-v'];start=time.monotonic()
        p=subprocess.run(cmd,cwd=W,capture_output=True,timeout=180)
        (out/(name+'.stdout.bin')).write_bytes(p.stdout);(out/(name+'.stderr.bin')).write_bytes(p.stderr)
        n=re.search(rb'Ran (\d+) tests?',p.stderr);row=dict(name=name,passed=p.returncode==0,tests=int(n[1]) if n else None,seconds=time.monotonic()-start,command=cmd)
        results.append(row);save(out/(name+'.json'),row);assert row['passed'],p.stderr[-3000:]
        print(name,row['tests'],'PASS',flush=True)
    m=load('bringup_gui_regressions',H.parent/'renderer_prerequisites/phase.py');m.O=out/'gui';m.O.mkdir();m.RT=RT;m.regressions()
    results.append(dict(name='registered-GUI',receipt=read(m.O/'focused-gui-regressions.json')))
    save(O/'regressions.json',dict(passed=True,root=str(out),results=results,runtime=core.tree(RT),genuine_launches=0))
if __name__=='__main__':main()
