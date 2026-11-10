"""Run owned fixtures for the exact dispatcher evidence implementation."""
import json
import pathlib
import shutil
import subprocess
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def run():
    out=O/('instrumentation-'+str(uuid.uuid4()));out.mkdir()
    helper=load('setres_instrumentation_build',H.parent/'getobject_boundary/phase.py');helper.O=out;env=helper.env()
    body=(H/'icall.inc').read_text().strip()
    core.require(body in (RT/'xrt_loader.c').read_text(),'fixture wrapper differs from candidate source')
    (out/'icall_fixture.inc').write_text(body+'\n')
    cl=shutil.which('cl.exe',path=env.get('Path',env.get('PATH')))
    cmd=[cl,'/nologo','/O2','/Zi','/fp:strict','/D_CRT_SECURE_NO_WARNINGS','/I'+str(RT),'/I'+str(out),
         '/Fo'+str(out/'fixture.obj'),'/Fd'+str(out/'fixture.pdb'),'/Fe'+str(out/'fixture.exe'),str(H/'instrumentation_fixture.c')]
    helper.run(cmd,'build',cwd=out,environment=env)
    cases=[]
    for mode in range(5):
        r=helper.run([out/'fixture.exe',str(mode)],'case-'+str(mode),cwd=out)
        rows=[json.loads(s) for s in r.stdout.splitlines()];expected=rows[-1]
        boundaries=[q for q in rows if q['kind']=='setres_boundary']
        core.require(len(boundaries)==(0 if mode==2 else 4 if mode==4 else 2),'boundary pair count')
        for phase in ('entry','return'):
            if mode==2:continue
            chunks=[q for q in rows if q['kind']=='setres_raw' and q['id']==boundaries[0]['id'] and q['area']=='cpu' and q['phase']==phase]
            core.require([q['offset'] for q in chunks]==[0,128,256,384] and all(q['size']==416 for q in chunks),'complete CPU raw chunks')
            raw=''.join(q['hex'] for q in chunks)
            core.require(raw==expected['before' if phase=='entry' else 'after'],'CPU evidence differs from independently published bytes')
        frames=[q for q in rows if q['kind']=='setres_raw' and q['area']=='frame']
        core.require((not frames) if mode in (2,3) else all(q['hex']==expected['frame'] for q in frames),'raw frame evidence')
        core.require(mode!=3 or len([q for q in rows if q['kind']=='setres_unreadable_frame'])==2,'unreadable frame not recorded')
        core.require(expected['last_error']==87,'evidence changed host last-error')
        cases.append(dict(mode=mode,passed=True,boundaries=boundaries))
    save(O/'instrumentation-validation.json',dict(passed=True,evidence=str(out),cases=cases,actual_candidate_wrapper_compiled=True,
         complete_cpu_frame_verified=True,host_last_error_preserved=True,non_game=True,genuine_launches=0,
         sources={str(p):core.sha(p) for p in (H/'instrumentation_fixture.c',H/'icall.inc',RT/'setres_evidence.inc',RT/'xrt_loader.c')}))
    print('5 exact-instrumentation fixture cases PASS, including nesting, unknown module and unreadable frame.',flush=True)


if __name__=='__main__':run()
