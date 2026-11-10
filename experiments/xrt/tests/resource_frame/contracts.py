import sys,uuid,shutil,json,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    out=O/('contracts-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    old=Path(read(PRIOR/'contracts.json')['root'])
    for n in ('cases.inc','cache_generated.inc','original-data.bin','parent_query.inc'):shutil.copy2(old/n,out/n)
    s=(H.parent/'semantic_compat/fixture.c').read_text()
    s=s.replace('CHECK(s==97);owned_slots=n;','if(s!=97){unsigned v=resource_bump;resource_bump+=4*s;for(i=0;i<s;i++)wr32(v+4*i,0x9000+4*i);return v;}owned_slots=n;')
    s=s.replace('static const char**owned_slots;','static unsigned resource_bump=0x12000;\nstatic const char**owned_slots;')
    s=s.replace('memset(G2H(0x11000),0,size);return 0x11000;','{unsigned p=resource_bump;resource_bump+=4;CHECK(resource_bump<0x1f000);memset(G2H(p),0,size);return p;}')
    (out/'retained_fixture.inc').write_text(s)
    s=(H.parent/'engine_bringup/scene_fixture.c').read_text().replace('#include "../semantic_compat/fixture.c"','#include "retained_fixture.inc"')
    s=s.replace('int main(void){','int scene_contract_main(void){')
    (out/'retained_scene.inc').write_text(s)
    result={}
    for arch in ('x86','x64'):
        d=out/arch;d.mkdir();env=h.env(arch)
        h.run(['cl','/nologo','/O1','/Gy','/fp:strict','/W4','/wd4100','/wd4102','/wd4505','/D_CRT_SECURE_NO_WARNINGS',f'/I{RT}',f'/I{out}',f'/Fo{d}/resource.obj',f'/Fe{d}/resource.exe',H/'resource_fixture.c','user32.lib','/link','/OPT:REF'],arch+'-build',environment=env)
        p=h.run([d/'resource.exe'],arch+'-run',cwd=out,timeout=40)
        result[arch]=[json.loads(line) for line in p.stdout.splitlines() if line.startswith(b'{')]
        h.run(['cl','/nologo','/O1','/Gy','/fp:strict','/W4','/wd4100','/wd4102','/wd4505','/D_CRT_SECURE_NO_WARNINGS',f'/I{RT}',f'/Fo{d}/dinput.obj',f'/Fe{d}/dinput.exe',H.parent/'engine_bringup/dinput_fixture.c','user32.lib','dinput8.lib','dxguid.lib','/link','/OPT:REF'],arch+'-dinput-build',environment=env)
        for mode,args in [('doubles',[]),('native',['--native'])]:
            p=h.run([d/'dinput.exe',*args],arch+'-dinput-'+mode,cwd=out,timeout=30)
            result[arch+'-dinput-'+mode]=[json.loads(line) for line in p.stdout.splitlines() if line.startswith(b'{')]
    assert result['x86']==result['x64']
    differences=[dict(arch=arch,sample=row) for arch in ('x86','x64') for row in result[arch+'-dinput-native'] if row.get('independent_invocations_equal') is False]
    save(O/'contracts.json',dict(passed=True,root=str(out),results=result,runtime=core.tree(RT),source=core.sha(H/'resource_fixture.c'),graphics=False,native_gpu=False,genuine_launches=0,directinput_strict_differences=differences))
    print(result['x64'],flush=True)
if __name__=='__main__':main()
