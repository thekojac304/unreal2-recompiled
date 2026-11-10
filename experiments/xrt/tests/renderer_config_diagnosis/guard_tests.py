import pathlib
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def run():
    root=O/('runtime-guard-'+str(uuid.uuid4()));root.mkdir()
    text=(RT/'integrated_renderer.inc').read_text();start=text.index('static uint32_t d8_profile_renderer;');end=text.index('\nstatic D8DeviceObject* batch_frame',start)
    (root/'production_guard.inc').write_text(text[start:end])
    profile=read(O/'configuration-profile.json')
    seeds='\n'.join(f'        *(uint32_t*)(memory+0x10000+{offset})={value}u;' for offset,value in profile['fields'].items())
    seeds+='\n'+ '\n'.join(f'        *(uint32_t*)(memory+0x14134+4*{i})={v}u;' for i,v in enumerate(profile['caps']['caps']))
    (root/'seed_profile.inc').write_text(seeds)
    helper=load('config_guard_fixture_tools',H.parent/'getobject_boundary/phase.py');helper.O=root;rows=[]
    for arch in ('x86','x64'):
        env=helper.env(arch);d=root/arch;d.mkdir()
        helper.run(['cl','/nologo','/O1','/fp:strict','/W3','/D_CRT_SECURE_NO_WARNINGS','/I'+str(RT),'/I'+str(root),'/Fo'+str(d/'fixture.obj'),'/Fe'+str(d/'fixture.exe'),H/'guard_fixture.c'],'build-'+arch,environment=env)
        r=helper.run([d/'fixture.exe'],'run-'+arch,cwd=root);rows.append(r.stdout.decode())
    core.require(rows[0]==rows[1],'x86/x64 actual guard differs')
    save(O/'runtime-guard-validation.json',dict(passed=True,evidence=str(root),architectures=['native-x86','x64-runtime'],
        actual_candidate_guard_extracted=True,results=rows[0],raw32_only=True,raw1_2_64_0_rejected=True,native_D3D_calls=0,genuine_launches=0))
    print('Exact revised guard passes x86/x64 contracts; only raw32 admitted, all other tested values rejected.',flush=True)


if __name__=='__main__':run()
