"""Compare the identical PE32 client lifted on x64 to native x64 host results.
Native x86's driver-name difference is retained in the native matrix, never patched.
"""
import json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_matrix import WS,BUILD,DX,sha
out=BUILD
backend=DX/'x64'
assert sha(backend/'d3d8.dll')=='bd65cebf8ece6f80a841a16d98bdf5b76894c172b7ba344180baa17a4d00680c'
assert sha(backend/'d3d9.dll')=='c126316f7478eaff1ad8087702eda5930f2400187b9c8b3592219c34f6632780'
(out/'dxvk.conf').write_text('')
env=dict(os.environ,XRT_D3D8_DIR=str(backend),DXVK_CONFIG='',DXVK_CONFIG_FILE=str(out/'dxvk.conf'),DXVK_LOG_PATH=str(out),DXVK_SHADER_CACHE='0')
probes=['probe_queries','probe_lifetime','probe_formats','probe_errors','probe_guards','probe_leak']
runs=[]
for cmd in [[str(out/'x64/native.exe'),str(backend/'d3d8.dll'),str(out/'x64/d3dprobe.dll'),*probes],
            [str(out/'translated.exe'),str(out/'x86/d3dprobe.dll'),str(out/'report.json'),*probes]]:
    r=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,timeout=30)
    runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
ok=all(r['exit']==0 and all(f'{p} returned 0 log ' in r['stdout'] for p in probes) for r in runs) and runs[0]['stdout']==runs[1]['stdout']
report=json.loads((out/'report.json').read_text())
ok=ok and any(e['kind']=='d3d8_cleanup' and e['references_released']==2 for e in report['events'])
for probe,message in [('probe_stale','stale or unknown guest COM interface'),('probe_unmeasured','IDirect3D8::RegisterSoftwareDevice is unmeasured')]:
    cmd=[str(out/'translated.exe'),str(out/'x86/d3dprobe.dll'),str(out/(probe+'.json')),probe]
    r=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,timeout=30)
    runs.append(dict(command=cmd,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    ok=ok and r.returncode==76 and message in r.stderr
(out/'results.json').write_text(json.dumps(dict(passed=ok,runs=runs,backend_files={p.name:sha(p)for p in backend.glob('d3d[89].dll')}),indent=2))
print('PASS' if ok else 'FAIL',[(r['exit'],len(r['stdout'].split()))for r in runs])
sys.exit(0 if ok else 1)
