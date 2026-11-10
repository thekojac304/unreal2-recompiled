"""Owned workloads only. Genuine timeout policy is read-only."""
import sys,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode
from supervisor import fixture
from supervisor.windows import FilePins

def main():
    out=O/('performance-'+str(uuid.uuid4()));out.mkdir();h=helper(out);env=h.env();results=[]
    stress='--stress' in sys.argv
    for variant,rt in ([('current',RT)] if stress else [('baseline',BASELINE/'runtime'),('current',RT)]):
        d=out/variant;d.mkdir();exe=d/'bench.exe'
        h.run(['ml64','/nologo','/c',f'/Fo{d}/monitor_asm.obj',rt/'monitor.asm'],variant+'-asm',environment=env)
        h.run(['cl','/nologo','/std:c11','/O2','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',f'/I{rt}',f'/Fo{d}/',f'/Fe{exe}',H/'benchmark.c',rt/'monitor.c',d/'monitor_asm.obj','user32.lib'],variant+'-build',environment=env)
        for case,n,direct in ([('trace-1000',1000,0),('trace-1500',1500,0)] if stress else [('direct',2000,1),('instrumented-off',2000,0),('trace-100',100,0),('trace-300',300,0)]):
            q=d/case;q.mkdir();sb=q/'sandbox';sb.mkdir();stream=sb/'trace.bin';probe=fixture.Probe(q,sb,case)
            arg='off' if 'trace' not in case else str(stream)
            with FilePins() as pins:
                pins.pin(exe,core.sha(exe))
                with (q/'stdout.txt').open('xb') as stdout,(q/'stderr.txt').open('xb') as stderr:
                    try:p=probe.run([str(exe),arg,str(n),str(direct)],cwd=sb,env=fixture.environment(sb),stdout=stdout,stderr=stderr,timeout=60)
                    except TimeoutError as e:
                        core.require(stress and probe.cleanup['passed'] and probe.cleanup['watchdog'],'unexpected benchmark timeout')
                        from reader import Record
                        import ctypes as C
                        row=dict(variant=variant,case=case,iterations=n,completed=False,seconds=probe.cleanup['seconds'],
                            error=str(e),cleanup=probe.cleanup,root=str(q),bytes=stream.stat().st_size,
                            whole_records_in_file=stream.stat().st_size//C.sizeof(Record),record_size=C.sizeof(Record),
                            integrity='Incomplete watchdog prefix; no independent post-kill committed counter, not accepted as a complete trace.')
                        results.append(row);print(variant,case,'WATCHDOG',row['seconds'],row['whole_records_in_file'],flush=True)
                        continue
            core.require(p.returncode==0 and probe.cleanup['passed'],'performance fixture '+case)
            row=json.loads((q/'stdout.txt').read_text().splitlines()[-1]);row.update(variant=variant,case=case,completed=True,cleanup=probe.cleanup,root=str(q))
            if stream.exists():
                rows,valid=decode(stream);row.update(integrity=valid,bytes=stream.stat().st_size,records_per_iteration=(len(rows)-3)/n,
                    measured_iterations_per_60_seconds=60*n/row['seconds'])
                native=[r for r in rows if r.event==3 and r.name==b'D8Device.CreateTexture']
                core.require(len(native)==n and all(r.error==0xaabbccdd and r.result&0xffffffff==0x80004005 for r in native),'actual native error/result')
                core.require(sum(r.event==2 and r.domain==3 for r in rows)==2*n,'callback coverage')
            results.append(row);print(variant,case,round(row['seconds'],6),row['records'],flush=True)
    save(O/('performance-stress.json' if stress else 'performance.json'),dict(passed=True,root=str(out),results=results,runtime=core.tree(RT),
        baseline_runtime=core.tree(BASELINE/'runtime'),genuine_timeout_seconds=60,timeout_policy_changed=False,
        owned_fixture_timeout_seconds=60,
        native_state='FXSAVE captured inside the native double before RET, compared with the wrapper result; XmRecord.context remains probe state.',
        limitations=['Owned window message nesting and deterministic COM doubles; no genuine engine instruction or physical GPU executed.',
                    'Extrapolation excludes genuine engine work and trace capacity; it cannot prove that genuine Init fits 60 seconds.']))

if __name__=='__main__':main()
