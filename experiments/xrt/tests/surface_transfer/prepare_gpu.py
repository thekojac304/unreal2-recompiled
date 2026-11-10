"""Frozen native x86/x64 and translated x64 fixtures; never submits/executes."""
import sys,re,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from supervisor import fixture_profiles as F
from gpu_source import source as gpu_source
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
        support=support.replace('<=0x20000','<=0x800000')
        support=support.replace('static uint32_t com_vtable(const char**n,unsigned s){(void)n;(void)s;abort();}', '''static unsigned gpu_bump=0x10000,gpu_map;
uint32_t xrt_rt_alloc(uint32_t n,uint32_t align){unsigned p=(gpu_bump+align-1)&~(align-1);gpu_bump=p+n;CHECK(gpu_bump<0x20000);return p;}
static uint32_t com_vtable(const char**names,unsigned n){unsigned p=xrt_rt_alloc(n*4,4),i;(void)names;for(i=0;i<n;i++)wr32(p+4*i,0x9000+4*i);return p;}
uint32_t xrt_virtual_alloc(CPU*c,uint32_t n){DWORD old;(void)c;CHECK(!gpu_map&&n<=0x600000);CHECK(VirtualProtect(G2H(0x200000),0x600000,PAGE_READWRITE,&old));gpu_map=1;return 0x200000;}
int xrt_virtual_free(CPU*c,uint32_t p){DWORD old;(void)c;CHECK(gpu_map&&p==0x200000);CHECK(VirtualProtect(G2H(p),0x600000,PAGE_NOACCESS,&old));gpu_map=0;return 1;}''')
        (src/'support.inc').write_text(support)
        fixture=(H.parent/'semantic_physical/fixture.c').read_text()
        fixture=fixture.replace('int main(', gpu_source()+'\nint main(')
        fixture=fixture.replace('1,1,75,0,0,0};HRESULT hr;','1,1,75,1,0,0};HRESULT hr;').replace('VirtualAlloc(NULL,0x20000,','VirtualAlloc(NULL,0x800000,')
        old='for(i=0;i<sizeof samples/sizeof samples[0];i++){sample=&samples[i];for(j=0;j<4;j++){invoke(i,seeds[j]);count++;}}'
        assert old in fixture;fixture=fixture.replace(old,'resource_matrix();count=gcalls;')
        (src/'fixture.c').write_text(fixture)
        ident=F.build('renderer-group',values,source_workspace=workspace);manifest=F.candidate_path(ident)
        receipts.append(dict(candidate_id=ident,parameters=values,source_workspace=workspace,manifest=str(manifest),manifest_sha256=core.sha(manifest),adapter_sources=sources,graphics_executed=False))
        print('Prepared resource GPU fixture',arch,variant,ident,flush=True)
    save(O/'gpu-qualification-package.json',dict(prepared=True,executed=False,candidates=receipts,runtime=core.tree(RT),scope=['surface identity/refcount/device','texture mips and aliased surface readback','texture binding','VB/IB uploads','buffer draws/index16/index32','render targets and viewport','scene boundaries','guest surface pixel readback','Present','cleanup','outer ABI/guest CPU'],pending=['physical fixture service stopped','three fixtures under existing collector/Job/watchdog','separate saved evidence comparison; historical collector failures remain'],production_policy_changed=False,genuine_launches=0))
if __name__=='__main__':main()
