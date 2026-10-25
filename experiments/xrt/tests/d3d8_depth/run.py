"""Fresh serial depth oracle, exact differential and retained D3D8 regressions."""
import argparse,importlib.util,json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3]
s=importlib.util.spec_from_file_location('display_fixture',HERE.parent/'d3d8_display/run.py')
E=importlib.util.module_from_spec(s);s.loader.exec_module(E)
E.HERE=HERE;E.E.HERE=HERE;D=E.D;D.HERE=HERE
COMMON=E.COMMON+['probe_depth'];ABI=E.ABI+['probe_depth_abi']

def build_native(out):
    E.build_native(out)
    roots=[HERE,HERE.parent/'d3d8_display',HERE.parent/'d3d8_enum',HERE.parent/'d3d8_modes',HERE.parent/'d3d8_boundary']
    D.write(out/'native-inputs.json',{str(p):D.sha(p)for root in roots for p in root.iterdir()if p.is_file()})

def records(v):
    n,count=v[:2];end=6+(n+5)*count*8*10
    assert v[2:6]==[0,1,3,2] and len(v)==end+7 and v[end:end+3]==[1,1,1] and v[-2:]==[0,0]
    rows=[v[i:i+10]for i in range(6,end,10)]
    assert all(row[3]==row[5]for row in rows),'last-error changed'
    return n,count,rows,v[end:]

def characterize(out):
    runs={};decoded={};safety={}
    for arch in ['x86','x64']:
        case=out/f'safety-{arch}';case.mkdir();env=os.environ.copy();D.G.environment(env,case)
        r=D.run([out/arch/'native.exe',D.G.verified_pair(arch),out/arch/'d3dprobe.dll','--depth-safety-abi'],case,env,'run')
        assert r['exit']==0,r
        rows=[[int(x)for x in line.split()[1:]]for line in r['stdout'].splitlines()if line.startswith('safety ')]
        assert rows and all(row[2]==row[4] and row[5]==0 for row in rows),'native exception or last-error change: stop'
        if arch=='x64':
            gprs=[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
            expected=[0]+[v for g in gprs for v in [g&0xffffffff,g>>32]]+[0x12345678,0x23456789,0x3456789a,0x456789ab]*10
            logs=[line for line in r['stdout'].splitlines()if line.startswith('abi64 ')]
            assert len(logs)*4==len(rows)
            for line in logs:
                a,k,error=map(int,line.split(' log ')[0].split()[1:]);v=list(map(int,line.split(' log ')[1].split()))
                assert error==18 and v[1:]==expected,line
                assert v[0]==next(row[3]for row in rows if row[:3]==[a,k,18])
        safety[arch]=dict(rows=rows,run=r)
        print('SAFE NATIVE',arch,len(rows),'no exception; seeded error preserved',flush=True)
    for rep in range(2):
        for arch in ['x86','x64']:
            case=out/f'native-{arch}-{rep}';case.mkdir();env=os.environ.copy();D.G.environment(env,case)
            probes=COMMON+(ABI if arch=='x86'else [])
            r=D.run([out/arch/'native.exe',D.G.verified_pair(arch),out/arch/'d3dprobe.dll',*probes],case,env,'run')
            assert r['exit']==0 and set(D.parse(r['stdout']))==set(probes),r
            key=f'{arch}-{rep}';runs[key]=r;decoded[key]=D.parse(r['stdout'])
            n,count,rows,tail=records(decoded[key]['probe_depth'])
            if arch=='x86':
                v=decoded[key]['probe_depth_abi'];assert len(v)==(n+5)*count*9+1 and v[-1]==0
                assert all(v[i+3]==18 and v[i+4:i+9]==[0,0x12345678,0x23456789,0x3456789a,0x456789ab]for i in range(0,len(v)-1,9))
            print(key,'genuine HRESULT',hex(rows[0][4]),'cases',count,'calls',len(rows),'stable last-error',flush=True)
    for arch in ['x86','x64']:assert decoded[arch+'-0']['probe_depth']==decoded[arch+'-1']['probe_depth']
    D.write(out/'native-characterization.json',dict(runs=runs,decoded=decoded,safety=safety,
        depth_exact_x86_x64=decoded['x86-1']['probe_depth']==decoded['x64-1']['probe_depth'],
        first_process_enumeration_identical=decoded['x86-0']['probe_enumeration']==decoded['x64-0']['probe_enumeration'],
        repeat_enumeration_identical=decoded['x86-1']['probe_enumeration']==decoded['x64-1']['probe_enumeration'],
        backends={a:{n:D.sha(D.G.verified_pair(a)/n)for n in D.G.HASHES[a]}for a in ['x86','x64']}))
    print('NATIVE CHARACTERIZATION PASS; actual architecture differences retained',flush=True)

def compare(out):
    E.COMMON=COMMON;E.ABI=ABI;E.compare(out)
    baseline=json.loads((out/'results.json').read_text());native=json.loads((out/'native-characterization.json').read_text());results=[]
    for rep in range(2):
        values=D.parse((out/f'translated-{rep}/run.stdout.txt').read_text());n,count,rows,tail=records(values['probe_depth'])
        assert values['probe_depth']==native['decoded']['x64-1']['probe_depth']
        assert values['probe_depth']==native['decoded']['x86-1']['probe_depth'],'backend difference retained: stop'
        v=values['probe_depth_abi'];assert v==native['decoded']['x86-1']['probe_depth_abi']
        report=json.loads((out/f'translated-{rep}/report.json').read_text());ev=report['events']
        sys.path.insert(0,str(W/'tools/xrt'));import world_tick_checkpoint as T
        calls=[e for e in ev if e['kind']=='d3d8_depth_call'];returns=[e for e in ev if e['kind']=='d3d8_depth_return'];pairs=T.paired(calls,returns,28)
        assert len(calls)==len(returns)==len(pairs)==len(rows)+(len(v)-1)//9+1
        assert all(c['adapter_format']==r['adapter_format'] and c['render_target_format']==r['render_target_format'] and c['depth_stencil_format']==r['depth_stencil_format'] and c['type']==r['type']for c,r in pairs)
        results.append(dict(paired_depth_calls=len(pairs),abi_calls=(len(v)-1)//9,exact_x86=True,exact_x64=True))
    case=out/'depth-negative';case.mkdir();env=os.environ.copy();D.G.environment(env,case);env['XRT_D3D8_DIR']=str(D.G.verified_pair('x64'))
    r=D.run([out/'translated.exe',out/'x86/d3dprobe.dll',case/'stale-report.json','probe_depth_stale'],case,env,'stale')
    assert r['exit']==76 and 'stale or unknown'in r['stderr'],r
    report=json.loads((case/'stale-report.json').read_text());assert report['events_dropped']==0 and not any(e['kind']=='d3d8_depth_call'for e in report['events'])
    baseline['negative']['probe_depth_stale']=dict(exit=r['exit'],report_sha256=D.sha(case/'stale-report.json'))
    baseline.update(depth_positive=results,runtime={str(f.relative_to(W/'experiments/xrt/runtime')):D.sha(f)for f in(W/'experiments/xrt/runtime').iterdir()if f.is_file()})
    D.write(out/'results.json',baseline);print('DEPTH DIFFERENTIAL PASS',results,'negative guards',len(baseline['negative']),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build_native','characterize','build_translated','compare']);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    (D.build_translated if a.action=='build_translated'else globals()[a.action])(a.out.resolve())
