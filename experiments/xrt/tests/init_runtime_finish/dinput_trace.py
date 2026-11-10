"""Actual lifecycle adapters + native DirectInput oracle with monitoring on."""
import sys,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode
from supervisor import fixture
from supervisor.windows import FilePins
def main():
    out=O/('dinput-trace-'+str(uuid.uuid4()));out.mkdir();h=helper(out);env=h.env()
    s=(H.parent/'engine_bringup/dinput_fixture.c').read_text()
    s=s.replace('if(argc==2&&!strcmp(argv[1],"--native"))return native_differential();',
        'if(argc==2){int rc;xm_init(argv[1]);rc=native_differential();xm_close();return rc;}')
    (out/'fixture.c').write_text(s);exe=out/'fixture.exe'
    h.run(['ml64','/nologo','/c',f'/Fo{out}/monitor_asm.obj',RT/'monitor.asm'],'asm',environment=env)
    h.run(['cl','/nologo','/std:c11','/O2','/Gy','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',f'/I{RT}',f'/Fo{out}/',f'/Fe{exe}',out/'fixture.c',RT/'monitor.c',out/'monitor_asm.obj','user32.lib','dinput8.lib','dxguid.lib','/link','/OPT:REF'],'build',environment=env)
    sandbox=out/'sandbox';sandbox.mkdir();stream=sandbox/'trace.bin';probe=fixture.Probe(out,sandbox,'dinput')
    with FilePins() as pins:
        pins.pin(exe,core.sha(exe))
        with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
            p=probe.run([str(exe),str(stream)],cwd=sandbox,env=fixture.environment(sandbox),stdout=stdout,stderr=stderr,timeout=30)
    core.require(p.returncode==0 and probe.cleanup['passed'],'DirectInput oracle failed')
    rows,valid=decode(stream);oracles=[json.loads(s) for s in (out/'stdout.txt').read_text().splitlines()]
    native=[r for r in rows if r.event==3 and r.domain==2 and r.slot in (7,8,13)]
    core.require(len(native)==14,'lifecycle native coverage')
    for r,o in zip(native,oracles):
        core.require(r.interface_id==4 and r.guest==0x5000 and r.generation==1,'typed receiver')
        core.require(r.slot==o['slot'] and r.result&0xffffffff==o['translated_hresult'] and r.error==o['translated_last_error'],'actual native transfer')
    save(O/'dinput-trace.json',dict(passed=True,root=str(out),samples=14,integrity=valid,oracles=oracles,
        retained_strict_differences=[r for r in oracles if r.get('independent_invocations_equal') is False],
        trace_enabled=True,cleanup=probe.cleanup,runtime=core.tree(RT)))
    print('Actual DirectInput adapters / 14 native inner-transfer oracles PASS; strict differences retained',flush=True)
if __name__=='__main__':main()
