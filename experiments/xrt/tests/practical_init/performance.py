"""Matched owned benchmark including the final durable checkpoint, no game."""
import sys,uuid,json,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode
from supervisor.windows import FilePins

def main():
    out=O/('performance-'+str(uuid.uuid4()));out.mkdir();h=helper(out);env=h.env();results=[]
    src=(H/'benchmark.c').read_text().replace('QueryPerformanceCounter(&end);CHECK(DestroyWindow', 'CHECK(DestroyWindow')
    src=src.replace('if(xm_enabled())xm_close();','if(xm_enabled())xm_close();QueryPerformanceCounter(&end);')
    (out/'benchmark.c').write_text(src)
    for variant,rt in [('baseline',FINISHED/'runtime'),('current',RT)]:
        d=out/variant;d.mkdir();exe=d/'bench.exe'
        h.run(['ml64','/nologo','/c',f'/Fo{d}/monitor_asm.obj',rt/'monitor.asm'],variant+'-asm',environment=env)
        h.run(['cl','/nologo','/std:c11','/O2','/fp:strict','/D_CRT_SECURE_NO_WARNINGS',f'/I{rt}',f'/Fo{d}/',f'/Fe{exe}',out/'benchmark.c',rt/'monitor.c',d/'monitor_asm.obj','user32.lib'],variant+'-build',environment=env)
        cases=[('forensic',100,i) for i in range(3)] if variant=='baseline' else [('forensic',100,0)]+[('development',100,i) for i in range(3)]+[('development',1500,0),('development',6000,0)]
        for profile,n,rep in cases:
            q=d/f'{profile}-{n}-{rep}';q.mkdir();sb=q/'sandbox';sb.mkdir();stream=sb/'trace.bin';probe=fixture.Probe(q,sb,'matched-benchmark')
            envrun=fixture.environment(sb);envrun['XRT_MONITOR_PROFILE']=profile
            with FilePins() as pins:
                pins.pin(exe,core.sha(exe))
                with (q/'stdout.txt').open('xb') as stdout,(q/'stderr.txt').open('xb') as stderr:
                    p=probe.run([str(exe),str(stream),str(n),'0'],cwd=sb,env=envrun,stdout=stdout,stderr=stderr,timeout=60)
            core.require(p.returncode==0 and probe.cleanup['passed'],'benchmark contained completion')
            row=json.loads((q/'stdout.txt').read_text().splitlines()[-1]);rows,valid=decode(stream)
            core.require(row['records']==len(rows) and valid['active_invocations']==0,'closed accounting')
            native=[r for r in rows if r.event==3 and r.name==b'D8Device.CreateTexture']
            core.require(len(native)==n and all(r.error==0xaabbccdd and r.result&0xffffffff==0x80004005 for r in native),'actual error/result')
            core.require(sum(r.event==2 and r.domain==3 for r in rows)==2*n,'nested callback coverage')
            row.update(variant=variant,profile=profile,repeat=rep,integrity=valid,root=str(q),cleanup=probe.cleanup,timed_records=len(rows)-2,records_per_second=(len(rows)-2)/row['seconds'])
            results.append(row);print(variant,profile,n,round(row['seconds'],5),len(rows),flush=True)
    baseline=statistics.median(r['records_per_second'] for r in results if r['variant']=='baseline')
    current=statistics.median(r['records_per_second'] for r in results if r['profile']=='development' and r['iterations']==100)
    save(O/'performance.json',dict(passed=True,root=str(out),results=results,matched_median_speedup=current/baseline,
        baseline_median_records_per_second=baseline,development_median_records_per_second=current,
        runtime=core.tree(RT),includes_final_flush=True,setup_records_excluded_from_timer=2,timeout_seconds=60,genuine_launches=0,
        caveats=['Owned nested USER32 messages and deterministic COM doubles; no real Init event count or engine-time prediction.',
                 'FlushFileBuffers completion is the OS persistence contract; physical power-loss/storage firmware behavior is not tested.']))

if __name__=='__main__':main()
