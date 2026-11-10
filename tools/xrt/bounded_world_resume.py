"""One identified client run, with protected-input gates and paired world evidence."""
import argparse, collections, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import asset_boundary as A
import run_xrt as R
import world_tick_checkpoint as W
WS=Path(R.WS)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--oracle',type=Path,required=True)
    a=ap.parse_args();out=a.out.resolve();build=a.build.resolve()
    assert json.loads(a.oracle.read_text())['passed'],'tolower differential must pass first'
    out.mkdir(parents=True,exist_ok=False)
    ident=json.loads((build/'client-identity.json').read_text());binary=build/'xrt_ucc.exe'
    assert R.file_identity(binary)==ident['binary']
    assert R.tree_digest(str(WS/'experiments/xrt/runtime'))==ident['runtime']
    assert R.tree_digest(str(WS/'experiments/xrt/gen'))==ident['generated']
    before=A.verify()
    helper=WS/'experiments/xrt/results/raw/directmusic/ipc-3fb42bf9e393/dmusic_helper.exe'
    assert A.sha(helper)=='a141ffe197f3eb14ed5908c946bd3cb541fdf456175b5a602b52df1b64484d22'
    env=dict(os.environ,XRT_BINARY=str(binary),XRT_DMUSIC_BACKEND='ipc',XRT_DMUSIC_HELPER=str(helper),
             XRT_ASSET_MANIFEST=str(A.DEFAULT_MANIFEST))
    driver=[sys.executable,'-I',str(WS/'tools/xrt/level_probe.py')]
    sb=WS/'sandbox_cmp/first-world'
    if sb.exists(): A.archive(sb)
    with (out/'prepare.txt').open('wb') as f:
        subprocess.run(driver+['prepare'],cwd=WS,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
    roots=set((WS/'experiments/xrt/results/raw/level').glob('*-candidate'))
    start=time.monotonic()
    cmd=driver+['candidate','--d3d8-backend','dxvk','--timeout-ms','60000']
    with (out/'driver.txt').open('wb') as f:
        p=subprocess.run(cmd,cwd=WS,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
    after=A.verify();assert before==after
    assert R.file_identity(binary)==ident['binary']
    assert R.tree_digest(str(WS/'experiments/xrt/runtime'))==ident['runtime']
    new=set((WS/'experiments/xrt/results/raw/level').glob('*-candidate'))-roots;assert len(new)==1
    root=new.pop();meta=json.loads((root/'meta.json').read_text());report=json.loads((root/'report.json').read_text())
    result=W.candidate(meta,report)
    world=result['selected_map']['world'] if result['selected_map'] else None
    calls=[e for e in report['events'] if e['kind']=='actor_lifecycle_call' and e['world']==world]
    returns=[e for e in report['events'] if e['kind']=='actor_lifecycle_return' and e['world']==world]
    pairs=W.paired(calls,returns,4);paired={c['seq'] for c,r in pairs}
    result.update(binary=ident['binary'],client_identity_sha256=A.sha(build/'client-identity.json'),
        run=str(root.relative_to(WS)),command=cmd,exit_code=p.returncode,seconds=time.monotonic()-start,
        protected_before=before,protected_after=after,events_recorded=report['events_recorded'],events_dropped=report['events_dropped'],
        all_selected_lifecycle=dict(calls=dict(collections.Counter(c['stage'] for c in calls)),
            returns=dict(collections.Counter(c['stage'] for c,r in pairs)),unpaired=[c for c in calls if c['seq'] not in paired]),
        engine_init_entries=sum(e['kind']=='engine_init_call' for e in report['events']),
        engine_init_returns=len(W.paired([e for e in report['events'] if e['kind']=='engine_init_call'],
            [e for e in report['events'] if e['kind']=='engine_init_return'],4)),
        d3d_events=[e for e in report['events'] if e['kind'].startswith('d3d8')],
        d3d_imports={k:v for k,v in report['imports'].items() if k.startswith('xrt.com!D8.')},
        cleanup=[e for e in report['events'] if 'cleanup' in e['kind']])
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['binary','run','exit_code','milestones','engine_init_returns',
        'engine_tick_entries','completed_engine_ticks','completed_selected_world_ticks','all_selected_lifecycle','first_fatal']},indent=2),flush=True)
    return 0 if result['observer_valid'] else 1
if __name__=='__main__':sys.exit(main())
