import json
import sys
from pathlib import Path
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    out=O/('contracts-'+str(uuid.uuid4()));out.mkdir()
    calls=read(PRIOR/'configuration-profile.json')['calls']
    caps=read(PRIOR/'configuration-profile.json')['caps']['caps']
    rows=[[c['slot'],c['a'],c['b'],c['c']] for c in calls]
    rows += [[42,0,0,0],[50,7,1,0],[50,9,2,0],[50,29,0,0],[50,26,1,0],[50,143,1,0],[50,48,0,0],[50,35,3,0],[50,136,1,0]]
    rows += [[18,0,0,0],[18,1,0,0],[36,0,1,0],[36,2,1,0x3f800000],[36,2,3,0x3f000000],[36,2,7,0]]
    rows += [[36,2,3,0x80000000]]
    rows += [[63,stage,s,v] for stage in range(8) for s,values in [(16,[1,2,3]),(17,[1,2,3]),(18,[0,1,2]),(19,[0,0x3f000000,0xbf000000]),(21,[1,2,16])] for v in values]
    # Exercise all noncanonical property Boolean representations through the
    # actual original decision fragments in the retained native/lifted oracle.
    cases='static const unsigned cases[][4]={'+','.join('{'+','.join(map(str,r))+'}' for r in rows)+'};\n'
    cases+='static const DWORD measured_caps[53]={'+','.join(str(v)+'u' for v in caps)+'};\n'
    (out/'cases.inc').write_text(cases)
    source=(W/'experiments/xrt/gen/d3ddrv/D3DDrv_001.c').read_text();begin=source.index('void f_6977800(CPU* c) {');end=source.index('\n}\n',begin)+3
    original=W/'out/recovery/setres-completion-20261029-01/cache-control-flow'
    assert source[begin:end]==(original/'cache_generated.inc').read_text()
    (out/'cache_generated.inc').write_text(source[begin:end])
    import shutil
    shutil.copy2(original/'original-data.bin',out/'original-data.bin')
    parent_source=(RT/'hle_d3d8.inc').read_text();pbegin=parent_source.index('static void d8_GetDeviceCaps(CPU*c) {');pend=parent_source.index('\n}',pbegin)+2
    (out/'parent_query.inc').write_text(parent_source[pbegin:pend])
    (out/'parent_query.inc').write_text(parent_source[pbegin:pend]+'\n#include "semantic_parent.inc"\n')
    helper=load('semantic_contract_build',H.parent/'getobject_boundary/phase.py');helper.O=out
    results=[]
    for arch in ('x86','x64'):
        e=helper.env(arch);d=out/arch;d.mkdir()
        helper.run(['cl','/nologo','/O1','/Gy','/fp:strict','/W4','/wd4100','/wd4102','/wd4505','/D_CRT_SECURE_NO_WARNINGS',f'/I{RT}',f'/I{out}',f'/Fo{d}/fixture.obj',f'/Fe{d}/fixture.exe',H/'fixture.c','user32.lib','/link','/OPT:REF'],arch+'-build',environment=e)
        p=helper.run([d/'fixture.exe'],arch+'-run',cwd=out,timeout=30)
        results.append(json.loads(p.stdout.splitlines()[-1]))
    assert results[0]==results[1]
    save(O/'contracts.json',dict(passed=True,root=str(out),results=results,architecture_equality=True,native_gpu=False,genuine_launches=0,
        runtime=core.tree(RT),fixture_source_sha256=core.sha(H/'fixture.c')))
    print('Integrated x86/x64 semantic protocol contracts equal:',results[0],flush=True)
if __name__=='__main__':main()
