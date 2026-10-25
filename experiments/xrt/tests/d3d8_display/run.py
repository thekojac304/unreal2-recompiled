"""Pinned native oracle, explicit pointer characterization and exact differential."""
import argparse,importlib.util,json,os,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3]
s=importlib.util.spec_from_file_location('enum_fixture',HERE.parent/'d3d8_enum/run.py')
E=importlib.util.module_from_spec(s);s.loader.exec_module(E);E.HERE=HERE
D=E.D;D.HERE=HERE
COMMON=E.COMMON+['probe_display'];ABI=E.ABI+['probe_display_abi']
def build_native(out):
    assert not out.exists();out.mkdir(parents=True)
    script=(HERE.parent/'d3d8_boundary/build_native.cmd').read_text()
    script=script.replace('set OUT=experiments\\xrt\\build\\d3d8_boundary','set OUT='+str(out)).replace('set HERE=experiments\\xrt\\tests\\d3d8_boundary','set HERE='+str(HERE))
    script=script.replace('cd /d "%~dp0\\..\\..\\..\\.."','cd /d "'+str(W)+'"')
    script=script.replace('"%HERE%\\d3d8.def"','"'+str(HERE.parent/'d3d8_boundary/d3d8.def')+'"').replace('"%OUT%\\%1\\probe.obj" "%OUT%\\%1\\d3d8.lib" ||','"%OUT%\\%1\\probe.obj" "%OUT%\\%1\\d3d8.lib" kernel32.lib ||')
    script=script.replace('set MACHINE=%1','set FIXTURE_ARCH=\nset ABI_OBJ=\nif "%1"=="x86" set FIXTURE_ARCH=/arch:IA32\nif "%1"=="x64" set ABI_OBJ="%OUT%\\x64\\abi64.obj"\nif "%1"=="x64" ml64 /nologo /c /Fo"%OUT%\\x64\\abi64.obj" "%HERE%\\abi64.asm" || exit /b 1\nset MACHINE=%1').replace('cl /nologo /c /O2','cl /nologo /c /O2 %FIXTURE_ARCH%')
    script=script.replace('"%HERE%\\native.c" ||','"%HERE%\\native.c" %ABI_OBJ% ||')
    (out/'build-native.cmd').write_text(script)
    r=D.run(['cmd','/d','/c',out/'build-native.cmd'],out,os.environ.copy(),'build-native')
    assert r['exit']==0 and not re.search(r'\b(?:C1001|D8040)\b',r['stdout']+r['stderr']),r
    D.write(out/'native-inputs.json',{str(p):D.sha(p)for root in [HERE,HERE.parent/'d3d8_enum',HERE.parent/'d3d8_modes',HERE.parent/'d3d8_boundary']for p in root.glob('*')if p.is_file()})
def display_records(v):
    assert v[:5]==[16,0,4,8,12];n=v[5];assert 0<n<=8
    assert v[6:10]==[0,1,3,2]
    end=10+(n+5)*16*17
    rows=[v[i:i+17]for i in range(10,end,17)]
    assert len(v)==end+19 and v[end:end+3]==[1,1,1] and v[-2:]==[0,0]
    return n,rows,v[end:]
def characterize(out):
    runs={};decoded={};pointer={}
    for rep in range(2):
        for arch in ['x86','x64']:
            case=out/f'native-{arch}-{rep}';case.mkdir();env=os.environ.copy();D.G.environment(env,case)
            probes=COMMON+(ABI if arch=='x86'else [])
            r=D.run([out/arch/'native.exe',D.G.verified_pair(arch),out/arch/'d3dprobe.dll',*probes],case,env,'run')
            assert r['exit']==0 and set(D.parse(r['stdout']))==set(probes),r
            key=f'{arch}-{rep}';runs[key]=r;decoded[key]=D.parse(r['stdout'])
            n,rows,tail=display_records(decoded[key]['probe_display'])
            for a,repeat,seed,hr,error,*rest in rows:
                assert seed==error and rest[4:]==[0xa5a5a5a5]*8
                assert hr==(0 if a<n else 0x8876086c)
                if hr:assert rest[:4]==[0xa5a5a5a5]*4
            print(key,'display modes',sorted({tuple(r[5:9])for r in rows if not r[3]}),'invalid HRESULT/output/last-error/canaries verified',flush=True)
    for arch in ['x86','x64']:
        case=out/f'native-pointers-{arch}';case.mkdir();env=os.environ.copy();D.G.environment(env,case)
        r=D.run([out/arch/'native.exe',D.G.verified_pair(arch),out/arch/'d3dprobe.dll','--pointers-and-abi'],case,env,'run')
        assert r['exit']==0,r;pointer[arch]=r
        if arch=='x64':
            logs=[line for line in r['stdout'].splitlines()if line.startswith('abi64 ')]
            assert len(logs)==(decoded['x64-1']['probe_display'][5]+2)*4
            gprs=[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
            expected=[0]+[v for g in gprs for v in [g&0xffffffff,g>>32]]+[0x12345678,0x23456789,0x3456789a,0x456789ab]*10
            for line in logs:
                values=[int(v)for v in line.split(' log ')[1].split(' output')[0].split()]
                assert values[1:]==expected,line
    D.write(out/'native-characterization.json',dict(runs=runs,decoded=decoded,pointer_runs=pointer,
        display_exact_x86_x64=decoded['x86-1']['probe_display']==decoded['x64-1']['probe_display'],
        display_process_repeat={a:decoded[a+'-0']['probe_display']==decoded[a+'-1']['probe_display']for a in ['x86','x64']},
        first_process_enumeration_identical=decoded['x86-0']['probe_enumeration']==decoded['x64-0']['probe_enumeration'],
        repeat_enumeration_identical=decoded['x86-1']['probe_enumeration']==decoded['x64-1']['probe_enumeration'],
        backends={a:{n:D.sha(D.G.verified_pair(a)/n)for n in D.G.HASHES[a]}for a in ['x86','x64']}))
    print('NATIVE CHARACTERIZATION PASS; actual architecture differences retained',flush=True)
def compare(out):
    # Run the entire retained enumeration/COM differential and its negative guards.
    E.COMMON=COMMON;E.ABI=ABI
    if not(out/'results.json').exists():E.compare(out)
    baseline=json.loads((out/'results.json').read_text());results=[]
    native=json.loads((out/'native-characterization.json').read_text());expected=native['decoded']['x64-1']
    for rep in range(2):
        values=D.parse((out/f'translated-{rep}/run.stdout.txt').read_text())
        assert values['probe_display']==expected['probe_display']
        assert values['probe_display']==native['decoded']['x86-1']['probe_display'],'display architecture difference: stop for review'
        abi=values['probe_display_abi'];assert abi[-1]==0
        assert all(abi[i+2]==18 and abi[i+3:i+8]==[0,0x12345678,0x23456789,0x3456789a,0x456789ab]for i in range(0,len(abi)-1,12))
        report=json.loads((out/f'translated-{rep}/report.json').read_text());ev=report['events']
        sys.path.insert(0,str(W/'tools/xrt'));import world_tick_checkpoint as T
        calls=[e for e in ev if e['kind']=='d3d8_display_call'];returns=[e for e in ev if e['kind']=='d3d8_display_return'];pairs=T.paired(calls,returns,16)
        assert len(calls)==len(returns)==len(pairs)==(len(abi)-1)//12+(expected['probe_display'][5]+5)*16+1
        results.append(dict(paired_display_calls=len(pairs),abi_calls=(len(abi)-1)//12,exact_x86=True,exact_x64=True))
    case=out/'display-negative';case.mkdir();env=os.environ.copy();D.G.environment(env,case);env['XRT_D3D8_DIR']=str(D.G.verified_pair('x64'))
    for p,msg in [('probe_display_null','NULL output is unsupported'),('probe_display_bad_range','invalid guest range'),('probe_display_wrap','invalid guest range'),('probe_display_stale','stale or unknown')]:
        r=D.run([out/'translated.exe',out/'x86/d3dprobe.dll',case/(p+'-report.json'),p],case,env,p)
        assert r['exit']==76 and msg in r['stderr'],r
        report=json.loads((case/(p+'-report.json')).read_text());assert report['events_dropped']==0
        assert not any(e['kind']=='d3d8_display_call'for e in report['events'])
        baseline['negative'][p]=dict(exit=r['exit'],diagnostic=msg,report_sha256=D.sha(case/(p+'-report.json')))
    baseline.update(display_positive=results,runtime={str(f.relative_to(W/'experiments/xrt/runtime')):D.sha(f)for f in(W/'experiments/xrt/runtime').iterdir()if f.is_file()})
    D.write(out/'results.json',baseline);print('DISPLAY DIFFERENTIAL PASS',results,'negative guards',len(baseline['negative']),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build_native','characterize','build_translated','compare']);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    (D.build_translated if a.action=='build_translated'else globals()[a.action])(a.out.resolve())
