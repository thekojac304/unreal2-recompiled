"""Combined read-only audits and independently isolated Python regression suites."""
import sys,uuid,subprocess,re,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    out=O/('offline-'+str(uuid.uuid4()));out.mkdir();results=[]
    scripts=[H/n for n in ('static_audit.py','path_audit.py','initialization_audit.py','control_flow.py')]
    scripts += [H.parent/d/n for d in ('engine_bringup','resource_frame','surface_transfer','integrated_candidate')
                for n in ('test_evidence.py','test_observer.py') if (H.parent/d/n).exists()]
    scripts += [H/'test_continuation.py',H/'test_acceptance.py']
    for script in scripts:
        name=script.parent.name+'-'+script.stem;cmd=[sys.executable,'-B','-I',str(script)]
        if script.name.startswith('test_'):cmd+=['-v']
        start=time.monotonic();p=subprocess.run(cmd,cwd=W,capture_output=True,timeout=120)
        (out/(name+'.stdout.bin')).write_bytes(p.stdout);(out/(name+'.stderr.bin')).write_bytes(p.stderr)
        n=re.search(rb'Ran (\d+) tests?',p.stderr)
        row=dict(name=name,passed=p.returncode==0,tests=int(n[1]) if n else None,seconds=time.monotonic()-start,command=cmd)
        save(out/(name+'.json'),row);results.append(row)
        assert row['passed'],p.stderr.decode(errors='replace')[-2500:]
        print(name,row['tests'],'PASS',flush=True)
    save(O/'offline-checks.json',dict(passed=True,root=str(out),results=results,genuine_launches=0))

if __name__=='__main__':main()
