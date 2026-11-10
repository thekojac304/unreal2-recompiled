"""Build serially; every negative tuple gets a disposable native process."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'tools/xrt'));import graphics_backend as G
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2))
def build(out):
    assert not out.exists();out.mkdir(parents=True)
    for arch in ['x86','x64']:
        dest=out/arch;dest.mkdir();assembler='ml'if arch=='x86'else'ml64';bits='32'if arch=='x86'else'64'
        script='@echo off\ncall "C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" '+arch+' >nul || exit /b 1\n'
        script+=f'{assembler} /nologo /c /Fo"{dest}/abi.obj" "{HERE}/abi{bits}.asm" || exit /b 1\n'
        script+=f'cl /nologo /O2 /W4 /Fo"{dest}/native.obj" /Fe"{dest}/native.exe" "{HERE}/native.c" "{dest}/abi.obj" user32.lib kernel32.lib /link /INCREMENTAL:NO || exit /b 1\n'
        (dest/'build.cmd').write_text(script)
        r=subprocess.run(['cmd','/d','/c',str(dest/'build.cmd')],cwd=W,capture_output=True,text=True)
        (dest/'build.stdout.txt').write_text(r.stdout);(dest/'build.stderr.txt').write_text(r.stderr)
        print(arch,r.returncode,r.stdout[-3000:],r.stderr,flush=True);assert r.returncode==0
    write(out/'build-inputs.json',{str(p):sha(p)for p in [*HERE.glob('*.c'),*HERE.glob('*.asm'),W/'experiments/xrt/runtime/d3d8_abi.h']})
def run_case(out,arch,name,seed=18,rep=0,repetitions=1):
    case=out/f'{arch}-{name}-{seed}-{rep}';assert not case.exists();case.mkdir()
    env=os.environ.copy();settings=G.environment(env,case);cmd=[str(out/arch/'native.exe'),str(G.verified_pair(arch)),name,str(seed),str(repetitions)]
    start=time.monotonic()
    with (case/'stdout.jsonl').open('w')as stdout,(case/'stderr.txt').open('w')as stderr:
        p=subprocess.Popen(cmd,cwd=case,env=env,stdout=stdout,stderr=stderr)
        try:code=p.wait(timeout=45)
        except subprocess.TimeoutExpired:p.kill();code=p.wait();code={'watchdog_killed':code}
    rows=[json.loads(s)for s in(case/'stdout.jsonl').read_text().splitlines()if s.startswith('{')]
    result=dict(arch=arch,case=name,seed=seed,repeat_process=rep,exit=code,elapsed=time.monotonic()-start,command=cmd,environment=settings,rows=rows)
    write(case/'result.json',result)
    creates=[r for r in rows if r['kind']=='create'];print(arch,name,seed,rep,'exit',code,[(hex(r['hr']),hex(r['exception']),r['last_error'],hex(r['output']))for r in creates],flush=True)
    return result
CASES=['adapter_count','adapter_ffff','adapter_max','type_0','type_2','type_3','type_4','type_4294967295',
       'focus_null','focus_invalid','device_null','device_invalid','both_null','both_invalid','separate_window',
       'dimensions_zero','width_zero','width_over_cap','height_over_cap','depth_70','depth_71','depth_75','depth_0','depth_22','depth_4294967295',
       'format_invalid','format_unknown','count_zero','count_4','swap_zero','swap_invalid','copy_two','multisample_invalid','interval_one','refresh_windowed','flags_invalid','behavior_zero',
       'pp_null','pp_one','pp_readonly','pp_noaccess','out_null','out_one','out_readonly','out_noaccess','parent_first']
def characterize(out,smoke=False):
    runs=[]
    if smoke:
        for arch in ['x86','x64']:runs.append(run_case(out,arch,'exact',18))
        write(out/'smoke.json',runs);return
    for rep in range(2):
        for arch in ['x86','x64']:
            for seed in [0,18,0x13572468,0xffffffff]:runs.append(run_case(out,arch,'exact',seed,rep,2))
            for case in ['abi','abi_no_preserve']:runs.append(run_case(out,arch,case,18,rep,2))
    for arch in ['x86','x64']:
        for name in CASES:runs.append(run_case(out,arch,name))
        runs.append(run_case(out,arch,'repeated',18,0,8))
    write(out/'native-characterization.json',dict(runs=runs,backends={a:{n:sha(G.verified_pair(a)/n)for n in G.HASHES[a]}for a in ['x86','x64']}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build','smoke','characterize']);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    (build(a.out.resolve())if a.action=='build'else characterize(a.out.resolve(),a.action=='smoke'))
