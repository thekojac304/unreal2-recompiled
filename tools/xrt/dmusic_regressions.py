"""Serialize existing acceptance suites against an explicitly identified client.

No game installation is launched or changed. Native fixture/oracle and translated
executions remain sequential. Logs and identities go into a new evidence folder.
"""
import argparse, hashlib, json, os, subprocess, sys, time, uuid
from pathlib import Path

WS=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS / "tools/xrt"))
import asset_boundary as A
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary',type=Path,required=True)
    a=ap.parse_args();binary=a.binary.resolve()
    out=WS/'experiments/xrt/results/raw/directmusic'/('regressions-'+uuid.uuid4().hex[:12]);out.mkdir(parents=True)
    env=os.environ.copy();env['XRT_BINARY']=str(binary)
    env.pop('XRT_DMUSIC_BACKEND',None);env.pop('XRT_DMUSIC_HELPER',None)
    py=str(WS/'.venv/Scripts/python.exe')
    suites=[(name,['cmd','/d','/c',f'experiments\\xrt\\tests\\{name}\\build.cmd']) for name in
            ['input_boundary','d3d8_boundary','gui_boundary','class_boundary','module_boundary','file_boundary','client_startup']]
    suites += [('com',['cmd','/d','/c','experiments\\xrt\\tests\\directmusic_boundary\\build_com.cmd']),
               ('exceptions',['cmd','/d','/c','tools\\xrt\\tests\\ehprobe\\build_and_run.cmd']),
               ('crt-build',['cmd','/d','/c','tools\\xrt\\tests\\crt_gatef\\build.cmd']),
               ('crt',[py,'-I','tools/xrt/tests/crt_gatef/compare.py','--json',str(out/'crt.json')]),
               ('commandlet-vm',[py,'-I','tools/xrt/run_xrt.py','hellofull','hello_noargs','hellonew','hellofull_nosse','simple','arraytest','hello','badclass','vmprobe']),
               ('compiler',[py,'-I','tools/xrt/compile_xrt.py']),
               ('traced-vm',[py,'-I','tools/xrt/run_xrt.py','vmprobe','--trace']),
               ('python',[py,'-I','-m','unittest','discover','-s','tools/xrt/tests','-v'])]
    suites.insert(0, ("ipc", [py,"-I","experiments/xrt/tests/directmusic_boundary/compare_ipc.py"]))
    results=[]
    for name,cmd in suites:
        before=A.verify()
        start=time.monotonic()
        with (out/(name+'.txt')).open('w',encoding='utf-8') as log:
            try:
                p=subprocess.run(cmd,cwd=WS,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
                code=p.returncode
            except subprocess.TimeoutExpired: code='timeout'
        after=A.verify()
        if after != before:
            raise RuntimeError('asset manifest changed during experiment')
        results.append(dict(name=name,command=cmd,exit=code,seconds=time.monotonic()-start,integrity_before=before,integrity_after=after))
        (out/'result.json').write_text(json.dumps(dict(passed=all(r['exit']==0 for r in results),complete=False,
            binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),runs=results),indent=2))
        print(name,code,round(results[-1]['seconds'],2),flush=True)
        if code != 0:
            print("stopping at first regression failure",out,flush=True)
            return 1
    record=json.loads((out/'result.json').read_text());record['complete']=True
    (out/'result.json').write_text(json.dumps(record,indent=2));print(out,flush=True)
    return 0 if record['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
