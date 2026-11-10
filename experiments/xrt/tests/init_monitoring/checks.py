"""Isolated regressions; does not build or run a GPU fixture or game."""
import sys,uuid,subprocess,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    root=O/('checks-'+str(uuid.uuid4()));root.mkdir();results=[]
    commands=[('composition',[str(H/'test_composition.py')])]
    commands += [(name,['-m','unittest','discover','-s',str(path),'-v']) for name,path in (
        ('supervisor',W/'tools/xrt/supervisor/tests'),('collector',H.parent/'renderer_batch'))]
    commands += [(name,[str(path),'-v']) for name,path in (
        ('retained-semantic',H.parent/'semantic_compat/test_observer.py'),
        ('retained-init',H.parent/'integrated_candidate/test_continuation.py'),
        ('retained-endpoint',H.parent/'integrated_candidate/test_observer.py'))]
    # Import tests only. verify.py's __main__ also rewrites historical receipts.
    commands.append(('strict-functional-risks',['-m','unittest','discover','-s',
                     str(H.parent/'functional_assessment'),'-p','verify.py','-v']))
    for name,args in commands:
        command=[sys.executable,'-B','-I',*args]
        p=subprocess.run(command,cwd=W,capture_output=True,timeout=180)
        (root/(name+'.stdout.bin')).write_bytes(p.stdout);(root/(name+'.stderr.bin')).write_bytes(p.stderr)
        n=re.search(rb'Ran (\d+) tests?',p.stderr)
        row=dict(name=name,command=command,passed=p.returncode==0,tests=int(n[1]) if n else None)
        results.append(row);save(root/(name+'.json'),row)
        core.require(row['passed'],name+': '+p.stderr.decode(errors='replace')[-2000:])
        print(name,row['tests'],'PASS',flush=True)
    save(O/'regression-validation.json',dict(passed=True,root=str(root),results=results,
        tests=sum(r['tests'] or 0 for r in results),genuine_launches=0,physical_launches=0))

if __name__=='__main__':main()
