"""Live positive resource lifetime through the actual translated adapters."""
import sys,uuid,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode
from supervisor import fixture
from supervisor.windows import FilePins
def main():
    out=O/('resource-trace-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    prior=Path(read(O/'contracts.json')['root'])
    for n in ('retained_fixture.inc','retained_scene.inc','cases.inc','cache_generated.inc','original-data.bin','parent_query.inc'):shutil.copy2(prior/n,out/n)
    original=(H.parent/'resource_frame/resource_fixture.c').read_text()
    prefix,body=original.split('int main(void)',1)
    setup=body[body.index('{')+1:body.index(' frame(&c,2,0x4000,0x7000);')]
    setup=setup.replace('CHECK(scene_contract_main()==0);','')
    # These are fixture scopes around real adapter invocations, no method BP.
    prefix=prefix.replace('fn(c);expected.r[EAX]', 'xm_scope(c,XM_BEGIN,XM_ADAPTER,"owned.resource-adapter",0);fn(c);xm_scope(c,XM_END,XM_ADAPTER,"owned.resource-adapter",c->r[EAX]);expected.r[EAX]')
    prefix+='''
/* This dedicated oracle models native binding references explicitly; the
 * retained broad fixture models that lifetime separately in the registry. */
static HRESULT WINAPI owned_setstream(D8Device*p,DWORD stream,void*q,DWORD stride){
 Fake*old=boundv;HRESULT hr=setstream(p,stream,q,stride);CHECK(stream==0);
 if(SUCCEEDED(hr)){if(q)radd((D8Unknown*)q);if(old)rrelease((D8Unknown*)old);}
 SetLastError(host_error);return hr;
}
'''
    setup=setup.replace('vt.SetStreamSource=setstream','vt.SetStreamSource=owned_setstream')
    source=prefix+'\nint main(int argc,char**argv){'+setup+'''
 CHECK(argc==2);xm_init(argv[1]);
 frame(&c,6,0x4000,240,0,0x44,1,0x7000);run(&c,d8_device_CreateVertexBuffer,6);v=rd32(0x7000);
 frame(&c,1,v);run(&c,d8_resource_AddRef,1);CHECK(c.r[EAX]==2);
 frame(&c,5,v,0,0,0x7000,0);run(&c,d8_resource_Lock,5);q=rd32(0x7000);memset(G2H(q),0x37,240);
 frame(&c,1,v);run(&c,d8_resource_Unlock,1);CHECK(vbuf.data[239]==0x37);
 frame(&c,4,0x4000,0,v,24);run(&c,d8_device_SetStreamSource,4);
 frame(&c,1,v);run(&c,d8_resource_Release,1);frame(&c,1,v);run(&c,d8_resource_Release,1);
 CHECK(d8_resources[0].refs==0&&d8_resources[0].bindings==1&&vbuf.refs==1);
 frame(&c,4,0x4000,0,0x7000,0x7004);run(&c,d8_device_GetStreamSource,4);CHECK(rd32(0x7000)==v);
 frame(&c,4,0x4000,0,0,0);run(&c,d8_device_SetStreamSource,4);
 frame(&c,1,v);run(&c,d8_resource_Release,1);CHECK(!d8_resources[0].host&&!vbuf.refs);
 frame(&c,6,0x4000,240,0,0x44,1,0x7000);run(&c,d8_device_CreateVertexBuffer,6);b=rd32(0x7000);CHECK(b!=v);
 frame(&c,1,b);run(&c,d8_resource_Release,1);
 frame(&c,1,0x4000);run(&c,d8_device_Release,1);CHECK(!device_refs&&!d8_device.children);
 xm_close();printf("{\\"checks\\":%u,\\"operations\\":%u,\\"old_guest\\":%u,\\"new_guest\\":%u}\\n",checks,resource_cases,v,b);
 return 0;
}
'''
    (out/'fixture.c').write_text(source);env=h.env();exe=out/'fixture.exe'
    h.run(['ml64','/nologo','/c',f'/Fo{out}/monitor_asm.obj',RT/'monitor.asm'],'asm',environment=env)
    h.run(['cl','/nologo','/std:c11','/O2','/Gy','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',f'/I{RT}',f'/I{out}',f'/Fo{out}/',f'/Fe{exe}',out/'fixture.c',RT/'monitor.c',out/'monitor_asm.obj','user32.lib','/link','/OPT:REF'],'build',environment=env)
    sandbox=out/'sandbox';sandbox.mkdir();stream=sandbox/'trace.bin';probe=fixture.Probe(out,sandbox,'resource-trace')
    with FilePins() as pins:
        pins.pin(exe,core.sha(exe))
        with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
            p=probe.run([str(exe),str(stream)],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,timeout=30)
    core.require(p.returncode==0 and probe.cleanup['passed'],'resource native/translated oracle failed')
    rows,valid=decode(stream);oracle=json.loads((out/'stdout.txt').read_text().splitlines()[-1])
    created=[r for r in rows if r.event==7 and r.name==b'created']
    core.require(len(created)==2 and created[0].host==created[1].host and created[0].generation!=created[1].generation,'native address reuse/generation')
    core.require({r.name for r in rows if r.event==7}>={b'mapped',b'unlocked',b'bound',b'unbound',b'destroyed',b'addref',b'released'},'lifetime evidence missing')
    locks=[r for r in rows if r.event==3 and r.name==b'D8Buffer.Lock'];core.require(len(locks)==1 and locks[0].slot==11 and locks[0].guest==oracle['old_guest'],'typed map identity')
    save(O/'resource-trace.json',dict(passed=True,root=str(out),oracle=oracle,integrity=valid,cleanup=probe.cleanup,
        native_object_address_reused=True,distinct_receiver_generations=True,trace_enabled=True,runtime=core.tree(RT)))
    print('Live actual resource adapters / bindings / map / generation reuse PASS',flush=True)
if __name__=='__main__':main()
