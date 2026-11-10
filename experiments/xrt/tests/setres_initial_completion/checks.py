"""Non-game qualification receipts and scoped hold resolution; no launch call."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import json
import shutil
import subprocess
import uuid
from common import *



def tests():
    for name,args in [('controller-tests-final',['discover','-s',str(H),'-v']),
                      ('supervisor-tests',['discover','-s',str(W/'tools/xrt/supervisor/tests'),'-v'])]:
        cmd=[str(W/'.venv/Scripts/python.exe'),'-B','-I','-m','unittest',*args]
        r=subprocess.run(cmd,cwd=W,capture_output=True,timeout=60)
        (O/(name+'.stdout.bin')).write_bytes(r.stdout);(O/(name+'.stderr.bin')).write_bytes(r.stderr)
        save(O/(name+'.json'),dict(command=cmd,passed=r.returncode==0,exit=r.returncode))
        core.require(r.returncode==0,'unit tests failed: '+name+' '+r.stderr[-2000:].decode(errors='replace'))
        print(name+': '+r.stderr.decode(errors='replace').split('Ran ')[-1].strip(),flush=True)


def helper():
    from supervisor.helper_checks import qualify
    save(O/'helper-qualification.json',qualify(O))
    print('Pinned DirectMusic helper isolation positive/negative non-game qualification PASS',flush=True)


def cache():
    old=W/'out/recovery/setres-completion-20261029-01/cache-control-flow'
    root=O/'cache-control-flow';root.mkdir(exist_ok=True)
    out=root/str(uuid.uuid4());out.mkdir()
    source=(W/'experiments/xrt/gen/d3ddrv/D3DDrv_001.c').read_text()
    begin=source.index('void f_6977800(CPU* c) {');end=source.index('\n}\n',begin)+3
    generated=source[begin:end]
    core.require(generated==(old/'cache_generated.inc').read_text(),'inherited cache body differs from generated source')
    (out/'cache_generated.inc').write_text(generated)
    shutil.copy2(old/'original-data.bin',out/'original-data.bin')
    helper=load('import_cache_fixture_compiler',W/'experiments/xrt/tests/getobject_boundary/phase.py');helper.O=out;env=helper.env()
    cmd=read(old/'build.json')['command']
    cmd=[s.replace(str(old),str(out)).replace(str(W/'out/recovery/renderer-gamma-integration-20261029-01/runtime'),str(PRIOR/'runtime'))
         .replace(str(W/'experiments/xrt/tests/setres_completion/cache_fixture.c'),str(H/'cache_fixture.c')) for s in cmd]
    helper.run(cmd,'build',cwd=out,environment=env)
    r=helper.run([out/'cache.exe'],'run',cwd=out)
    rows=[json.loads(s) for s in r.stdout.splitlines()]
    from mapping import sequence
    expected=[{k:q[k] for k in ('slot','site','a','b','c')} for q in sequence() if q.get('site',0)>=0x6977800]
    core.require(len(rows)==195 and rows==read(old/'result.json')['rows']==expected,'generated cache order differs')
    result=dict(passed=True,exit=r.returncode,calls=len(rows),ordered_equal=True,rows=rows,
        generated_sha256=core.sha(out/'cache_generated.inc'),original_data_sha256=core.sha(out/'original-data.bin'),genuine_launches=0)
    save(out/'result.json',result)
    save(root/'result.json',dict(result,evidence=str(out)))
    print('195 ordered calls from the unchanged generated cache body PASS (owned non-game fixture)',flush=True)


if __name__=='__main__':globals()[sys.argv[1]]()
