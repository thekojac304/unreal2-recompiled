"""Build edited disposable renderer-group fixtures through the fixed recipe."""
import argparse
import re
from pathlib import Path
from recheck import HERE, OUT, PRIOR, core
from supervisor import fixture_profiles as F


def samples(group):
    if group == 1:
        return [[42,0,0,0,k,0] for k in (0,1)]
    if group == 2:
        return [[63,s,t,v,0,0] for s in (0,7) for t,values in ((16,(1,2)),(17,(1,2)),(18,(0,1,2)),(19,(0,0x3f000000,0xbf000000)),(21,(1,16))) for v in values] + [[63,8,16,2,0,1]]
    if group == 3:
        return [[50,s,v,0,0,0] for s in (14,27) for v in (0,1,2,32,128,0x80000000,0xffffffff)] + [[50,7,v,0,0,int(v==99)] for v in (0,1,99)] + [[50,22,v,0,0,0] for v in (1,2,3)]
    if group == 4:
        return [[37,t,0,0,k,0] for t in (2,3,16,256) for k in (0,1,2)] + [[37,999,0,0,0,1]]
    if group == 5:
        return [[63,s,t,v,0,0] for s in (0,7) for t,values in ((1,(1,2,4)),(2,(0,2,0x12)),(13,(1,2,3,4)),(24,(0,2,0x102))) for v in values]
    if group == 6:
        return [[61,s,0,0,0,int(s==8)] for s in (0,7,8)] + [[83,s,0,stride,0,int(s==16)] for s in (0,15,16) for stride in (0,64)] + [[85,0,b,0,0,0] for b in (0,12345,0xffffffff)]
    if group == 7:
        return [[76,v,0,0,0,int(v==0)] for v in (2,0x152,0x244,0)]
    raise ValueError(group)


def build(group, arch, variant, creation_config=None, clear_mode=False, parent_query_mode=False):
    OUT.mkdir(parents=True, exist_ok=True)
    values = dict(group=group, arch=arch, variant=variant)
    seed = F.build('renderer-group', values)
    workspace = F.checkout(seed)
    src = F.SOURCES / workspace / 'sources'
    runtime = src / 'runtime'
    existing = {p.name for p in runtime.iterdir()}
    originals = {}
    def expand(path, stack=()):
        core.require(path.name not in stack, 'recursive include')
        originals[str(path)] = core.sha(path)
        text = path.read_text()
        def include(m):
            name=m[1]
            if name in existing:
                return m[0]
            target=PRIOR/'runtime'/name
            core.require(target.is_file(), 'unaccounted local include '+name)
            return '\n/* Begin exact expanded '+name+' */\n'+expand(target,(*stack,path.name))+'\n/* End exact expanded '+name+' */\n'
        return re.sub(r'^#include "([^"]+)"', include, text, flags=re.M)
    for path in runtime.iterdir():
        original = PRIOR / 'runtime' / path.name
        if original.is_file():
            path.write_text(expand(original))
    (src/'fixture.c').write_bytes((HERE/'fixture.c').read_bytes())
    rows=samples(group)
    text=(HERE/'support.inc').read_text().replace('/* SAMPLE_ROWS */',
        'static const Sample samples[]={'+','.join('{'+','.join(str(x)+'u' for x in row)+'}' for row in rows)+'};')
    (src/'support.inc').write_text(text)
    if creation_config is not None:
        import creation
        fixture_text,support_text=creation.sources(creation.CONFIGS[creation_config])
        if parent_query_mode:
            parent_source=PRIOR/'runtime/semantic_parent.inc'
            originals[str(parent_source)]=core.sha(parent_source)
            support_text+='\nstatic void d8_result(CPU*c,const char*m,D8Object*p,uint32_t a,uint32_t b,HRESULT hr){(void)c;(void)m;(void)p;(void)a;(void)b;(void)hr;}\n'+parent_source.read_text()
            fixture_text=fixture_text.replace('int main(', (HERE/'parent_queries.inc').read_text()+'\nint main(')
            fixture_text=fixture_text.replace('ev_checkpoint("loaded");record_events=1;', 'ev_checkpoint("loaded");record_events=1;parent_queries();')
        (src/'fixture.c').write_text(fixture_text)
        (src/'support.inc').write_text(support_text)
    if clear_mode:
        import clear
        fixture_text,support_text=clear.sources();rows=clear.ROWS
        (src/'fixture.c').write_text(fixture_text)
        (src/'support.inc').write_text(support_text)
    ident=F.build('renderer-group', values, source_workspace=workspace)
    manifest=F.candidate_path(ident)
    receipt=dict(candidate_id=ident, parameters=values, samples=rows, manifest=str(manifest),
        manifest_sha256=core.sha(manifest), source_workspace=workspace, base_fixture=seed,
        semantic_candidate_sha256=core.read_large(PRIOR/'candidate-identity.json')['sha256'],
        adapter_sources=originals, source_exact_include_expansion=True, graphics_executed=False)
    if creation_config is not None:
        receipt.update(mode='creation',creation_config=creation_config,configuration=creation.CONFIGS[creation_config])
    if clear_mode:receipt.update(mode='clear',native_abi_scope='outer typed Clear wrapper')
    if parent_query_mode:receipt.update(mode='parent-queries')
    core.atomic(OUT/('fixture-'+ident+'.json'),receipt)
    print(ident,flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,required=True);p.add_argument('--arch',choices=['x86','x64'],required=True);p.add_argument('--variant',choices=['native','translated'],required=True)
    a=p.parse_args();build(a.group,a.arch,a.variant)
