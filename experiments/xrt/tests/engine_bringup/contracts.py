import sys,uuid,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    out=O/('contracts-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    old=Path(read(PRIOR/'contracts.json')['root'])
    for name in ('cases.inc','cache_generated.inc','original-data.bin','parent_query.inc'):shutil.copy2(old/name,out/name)
    results={}
    for arch in ('x86','x64'):
        env=h.env(arch);d=out/arch;d.mkdir()
        for fixture in ('dinput','scene'):
            tag=arch+'-'+fixture
            h.run(['cl','/nologo','/O1','/Gy','/fp:strict','/W4','/wd4100','/wd4102','/wd4505','/D_CRT_SECURE_NO_WARNINGS',f'/I{RT}',f'/I{out}',f'/Fo{d}/{fixture}.obj',f'/Fe{d}/{fixture}.exe',H/(fixture+'_fixture.c'),'user32.lib','dinput8.lib','dxguid.lib','/link','/OPT:REF'],tag+'-build',environment=env)
            p=h.run([d/(fixture+'.exe')],tag+'-run',cwd=out,timeout=30)
            results[tag]=[json.loads(line) for line in p.stdout.splitlines() if line.startswith(b'{')]
            if fixture=='dinput':
                p=h.run([d/(fixture+'.exe'),'--native'],tag+'-native',cwd=out,timeout=30)
                results[tag+'-native']=[json.loads(line) for line in p.stdout.splitlines() if line.startswith(b'{')]
    assert results['x86-scene']==results['x64-scene'] and results['x86-dinput']==results['x64-dinput']
    native_differences=[dict(arch=arch,sample=row) for arch in ('x86','x64') for row in results[arch+'-dinput-native'] if row.get('independent_invocations_equal') is False]
    cross_arch=[dict(x86=a,x64=b) for a,b in zip(results['x86-dinput-native'],results['x64-dinput-native']) if a!=b]
    save(O/'contracts.json',dict(passed=True,root=str(out),results=results,runtime=core.tree(RT),sources={str(p):core.sha(p) for p in H.glob('*fixture.c')},graphics=False,genuine_launches=0,native_independent_differences=native_differences,cross_arch_native_differences=cross_arch,strict_native_equality=not native_differences and not cross_arch))
    print('Both architectures PASS',results['x64-dinput'],results['x64-scene'],flush=True)
if __name__=='__main__':main()
