"""Build three consolidated disposable candidates; never submit or execute."""
import sys,re,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from supervisor import fixture_profiles as F

def main():
    receipts=[]
    for arch,variant in [('x86','native'),('x64','native'),('x64','translated')]:
        values=dict(group=1,arch=arch,variant=variant);seed=F.build('renderer-group',values);workspace=F.checkout(seed)
        src=F.SOURCES/workspace/'sources';runtime=src/'runtime';existing={p.name for p in runtime.iterdir()};sources={}
        def expand(path,stack=()):
            assert path.name not in stack;sources[str(path)]=core.sha(path)
            def include(m):
                name=m[1]
                if name in existing:return m[0]
                target=RT/name;assert target.is_file(),name
                return '\n'+expand(target,(*stack,path.name))+'\n'
            return re.sub(r'^#include "([^"]+)"',include,path.read_text(),flags=re.M)
        for p in runtime.iterdir():
            if (RT/p.name).is_file():p.write_text(expand(RT/p.name))
        support=(H.parent/'semantic_physical/support.inc').read_text().replace('/* SAMPLE_ROWS */','static const Sample samples[]={{50,14,1,0,0,0}};')
        (src/'support.inc').write_text(support)
        fixture=(H.parent/'semantic_physical/fixture.c').read_text()
        fixture=fixture.replace('int main(', (H/'gpu_scene.inc').read_text()+'\nint main(')
        fixture=fixture.replace('1,1,75,0,0,0};HRESULT hr;','1,1,75,1,0,0};HRESULT hr;')
        old='for(i=0;i<sizeof samples/sizeof samples[0];i++){sample=&samples[i];for(j=0;j<4;j++){invoke(i,seeds[j]);count++;}}'
        assert old in fixture;fixture=fixture.replace(old,'scene_matrix();count=16;')
        (src/'fixture.c').write_text(fixture)
        ident=F.build('renderer-group',values,source_workspace=workspace);manifest=F.candidate_path(ident)
        receipts.append(dict(candidate_id=ident,parameters=values,source_workspace=workspace,manifest=str(manifest),manifest_sha256=core.sha(manifest),adapter_sources=sources,graphics_executed=False))
        print('Prepared GPU fixture',arch,variant,ident,flush=True)
    save(O/'gpu-qualification-package.json',dict(prepared=True,executed=False,candidates=receipts,runtime=core.tree(RT),
        scope=['TestCooperativeLevel','Begin/EndScene including duplicate failures','viewport round trip','triangle UP','indexed UP 16/32 with nonzero minimum','non-clear backbuffer RGB hashes','stream/index unbinding','Present','owned cleanup','raw outer ABI and guest CPU'],
        pending=['physical service owner startup','execute all three fixtures under existing Job/watchdog/module collector','independent evidence audit; retain historical collector parser failures','formal GPU acceptance before genuine continuation'],
        production_policy_changed=False,genuine_launches=0))
if __name__=='__main__':main()
