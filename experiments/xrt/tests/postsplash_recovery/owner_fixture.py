"""One owner-desktop non-game probe. Never launches Unreal II or its runtime."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys, time, traceback
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;W=O.parents[2];RUN=O/'owner-init-audio-run'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def verify():
    for rel,h in read(O/'owner-fixture-identities.json').items():assert sha(W/rel)==h,rel
    b=read(O/'fixture-build.json');root=Path(b['root'])
    for rel,h in b['binaries'].items():assert sha(root/rel)==h,rel
    return root
def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--execute-owner-fixture',action='store_true');args=a.parse_args()
    if not args.execute_owner_fixture:a.error('Explicit owner launch only; no game is launched by this probe.')
    assert not sys.flags.optimize and not RUN.exists(),'one attempt; preserve prior results'
    b=verify();RUN.mkdir();sb=W/'sandbox_postsplash_owner_20261028_01';assert not sb.exists();sb.mkdir();(sb/'System').mkdir()
    envmod=load('post_owner_environment',W/'out/recovery/session-aware-136-20261026-01/owner.py')
    baseline=None;before=None;rows=[]
    def check(tag):
        nonlocal baseline
        d=envmod.observe();save(RUN/(tag+'-environment.json'),d);f=envmod.environment_gate(d)
        if baseline is None:baseline=f
        else:assert f==baseline,('owner environment changed',tag)
    try:
        check('initial');check('second');before=envmod.V.state();assert not before['processes']
        save(RUN/'initial-state.json',before)
        commands=[('native-unguarded',[b/'x86/native_init.exe',b/'guids.bin',sb,'0']),('native-guarded',[b/'x86/native_init.exe',b/'guids.bin',sb,'1']),
            ('ipc-production-helper',[b/'x64/ipc_init.exe',b/'dmusic_helper.exe',sb])]
        for name,cmd in commands:
            start=time.monotonic();environment=os.environ.copy()
            for k in list(environment):
                if k.startswith(('XRT_','DXVK_','VK_')) or k in ['__COMPAT_LAYER','CL','_CL_','LINK','_LINK_']:environment.pop(k)
            try:
                p=subprocess.run(list(map(str,cmd)),cwd=sb/'System',env=environment,capture_output=True,timeout=14)
                row=dict(case=name,command=list(map(str,cmd)),exit=p.returncode,timeout=False,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))
            except subprocess.TimeoutExpired as e:
                row=dict(case=name,command=list(map(str,cmd)),exit=None,timeout=True,stdout=(e.stdout or b'').decode(errors='replace'),stderr=(e.stderr or b'').decode(errors='replace'))
            row['seconds']=time.monotonic()-start;save(RUN/(name+'.json'),row);rows.append(row)
            assert row['exit']==0 and 'InitAudio return 00000000 object=1' in row['stdout'] and 'cleanup passed' in row['stdout'],('STOP native/IPC probe failed',name)
            assert 'sandbox denied' not in row['stderr']
        check('final');assert envmod.V.state()==before
        save(RUN/'result.json',dict(passed=True,runs=rows,baseline=baseline,genuine_sessions=0,
            no_runtime_or_helper_change=True,production_timeout_ms=10000,native_parent_timeout_seconds=14,
            meaning='Owner-context non-game prerequisite only. Does not establish the consumed error bytes or fix its failure. Separate genuine authorization remains required.'))
    except BaseException:
        (RUN/'STOP.txt').write_text(traceback.format_exc());raise
    finally:
        verify()
        if before is not None:save(RUN/'final-state.json',envmod.V.state())
if __name__=='__main__':main()
