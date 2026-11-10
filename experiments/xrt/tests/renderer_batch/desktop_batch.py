"""One physical-desktop invocation; fixtures only, no game/supervisor path.

Refuses remote sessions. Stops immediately on an oracle, identity or differential
failure. Each process owns a disposable window/device. Gamma is explicitly opt-in.
"""
import argparse,ctypes,json,os,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
import prepare as P

def plan():
    return dict(order=[
        'Verify delivery/source/executable hashes and pinned DXVK pair; require physical desktop.',
        'Existing native single-state (148,1): x86, x64; exact captured CreateDevice tuple; stop on failure.',
        'Groups 1..7: native x86, native x64, translated x64 for each group; four last-error seeds, two repeated calls per case, exact readbacks and cleanup.',
        'ResizeViewport: already built x86 thiscall/x64/guest-frame protocol probes; real original/generated Win32 effects remain a separate qualification gate.',
        'Optional group 8: snapshot gamma; measure void call and full ramp readback; restore before reporting a readback/ABI assertion failure.',
        'Require x86/x64/translated agreement before any new production allowlist or combined candidate.',
        'Later genuine material return and SetRes/outer initialization need separate owner authorization and existing supervisor review; this batch never submits either.'
    ],groups=P.GROUPS,default_graphics_groups=list(range(1,8)),optional_gamma=8,
       genuine_game_execution=False,supervisor_mutation=False,
       gamma_sample='gamma=1,brightness=.5,contrast=.5; exact 1536 bytes independently verified against original x86 arithmetic',
       excluded_qualification=['real ResizeViewport/Windows callback sequence','rendered image/presentation','arbitrary caps/configuration domains','strict historical x87/WNDPROC equality'])

def verify_bundle():
    manifest=P.read(P.O/'delivery.json')
    for path,digest in manifest['files'].items():assert P.core.sha(P.W/path)==digest,('delivery integrity',path)
    for arch in ['x86','x64']:P.G.verified_pair(arch)
    return manifest

def execute(exe,args,d):
    d.mkdir();env=os.environ.copy();P.G.environment(env,d)
    r=subprocess.run([str(exe),*map(str,args)],cwd=d,env=env,capture_output=True,text=True,timeout=60)
    (d/'stdout.txt').write_text(r.stdout);(d/'stderr.txt').write_text(r.stderr)
    rows=[json.loads(s) for s in r.stdout.splitlines() if s.startswith('{')]
    P.core.atomic(d/'result.json',dict(executable=str(exe),sha256=P.core.sha(exe),args=list(map(str,args)),exit=r.returncode,rows=rows))
    assert r.returncode==0,('fixture failed; batch stopped',str(d),r.returncode)
    return rows

def audit(rows,group):
    assert rows[-1]['kind']=='summary' and rows[-1]['passed'] and rows[-1]['graphics']
    expected=sum(c['group']==group for c in P.read(P.O/'cases.json')['cases'])*8
    calls=[r for r in rows if r['kind']=='call'];readbacks=[r for r in rows if r['kind']=='readback']
    assert len(calls)==len(readbacks)==expected
    keys=['site','config','slot','a','b','c']
    cases=[c for c in P.read(P.O/'cases.json')['cases'] if c['group']==group]
    exact=[tuple(c[k] for k in keys)+(seed,) for c in cases for seed in [18,0,0x13572468,0xffffffff] for _ in range(2)]
    assert [tuple(c[k] for k in keys)+(c['seed'],) for c in calls]==exact
    assert all(r['stack_delta']==0 and r['fpu_preserved'] and (r['hr'] is None if group==8 else r['hr']==0) for r in calls)
    assert all(r['equal'] and r['hr']==0 for r in readbacks)
    assert all(c['slot']==r['slot'] for c,r in zip(calls,readbacks))
    for call in calls:
        pre=bytes.fromhex(call['pre']);post=bytes.fromhex(call['post'])
        assert len(pre)==len(post)==512 and pre[:2]==b'\x7f\x02'
        assert all(pre[a:b]==post[a:b] for a,b in [(0,5),(24,28),(32,42),(48,58)])
    if group==8:assert rows[-2]==dict(kind='gamma-restored',equal=True)
    return [(c['site'],c['config'],c['slot'],c['a'],c['b'],c['c'],c['seed'],c['error'],c['hr'],r['value'],r['extra']) for c,r in zip(calls,readbacks)]

def run(out,include_gamma):
    assert not ctypes.windll.user32.GetSystemMetrics(0x1000),'Remote session: no graphics measurement attempted'
    verify_bundle();out=out.resolve();out.mkdir()
    P.core.atomic(out/'plan.json',plan())
    # Unchanged independently prepared state fixtures establish that the exact native tuple works.
    for arch in ['x86','x64']:
        execute(P.PRIOR/'state-fixtures'/arch/'native.exe',[P.G.verified_pair(arch),148,1,18,0],out/('preflight-'+arch))
    groups=list(range(1,8))+([8] if include_gamma else [])
    results=[]
    for group in groups:
        name=P.GROUPS[group];observations=[]
        for arch,variant in [('x86','native'),('x64','native'),('x64','translated')]:
            fixture=P.O/'fixtures'/f'{name}-{arch}-{variant}'/'fixture.exe'
            args=['--physical',P.G.verified_pair(arch)]+(['--gamma-physical'] if group==8 else [])
            rows=execute(fixture,args,out/f'{name}-{arch}-{variant}')
            observations.append(audit(rows,group))
        assert observations[0]==observations[1]==observations[2],('native/translated correctness discrepancy; stopped',name)
        results.append(dict(group=group,name=name,native_gpu_differential='COMPLETED',production_accepted=False))
        P.core.atomic(out/'progress.json',results)
        print('Native/translated GPU differential complete:',name,flush=True)
    P.core.atomic(out/'result.json',dict(passed=True,groups=results,production_accepted=False,
        strict_x87='FAILED',strict_wndproc='FAILED',genuine_launches=0,
        resize_real_windows_qualification='PENDING'))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['plan','run','verify']);a.add_argument('--out',type=Path);a.add_argument('--include-gamma',action='store_true');v=a.parse_args()
    if v.action=='plan':print(json.dumps(plan(),indent=2))
    elif v.action=='verify':verify_bundle();print('Delivery hashes and pinned DXVK pairs verified; no graphics executed')
    else:
        if v.out is None:a.error('--out must name a fresh results directory')
        run(v.out,v.include_gamma)
