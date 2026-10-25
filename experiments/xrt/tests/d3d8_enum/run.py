"""Fresh serial native oracle and exact translated EnumAdapterModes differential."""
import argparse,importlib.util,json,os,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;W=HERE.parents[3]
s=importlib.util.spec_from_file_location('mode_fixture',HERE.parent/'d3d8_modes/run.py')
D=importlib.util.module_from_spec(s);s.loader.exec_module(D);D.HERE=HERE
COMMON=['probe_queries','probe_lifetime','probe_formats','probe_errors','probe_guards','probe_modes','probe_enumeration','probe_enum_last_error','probe_leak']
ABI=['probe_count_abi','probe_enum_abi','probe_enum_full_abi']
def build_native(out):
    assert not out.exists();out.mkdir(parents=True)
    script=(HERE.parent/'d3d8_boundary/build_native.cmd').read_text()
    script=script.replace('set OUT=experiments\\xrt\\build\\d3d8_boundary','set OUT='+str(out)).replace('set HERE=experiments\\xrt\\tests\\d3d8_boundary','set HERE='+str(HERE))
    script=script.replace('cd /d "%~dp0\\..\\..\\..\\.."','cd /d "'+str(W)+'"')
    script=script.replace('"%HERE%\\d3d8.def"','"'+str(HERE.parent/'d3d8_boundary/d3d8.def')+'"').replace('"%OUT%\\%1\\probe.obj" "%OUT%\\%1\\d3d8.lib" ||','"%OUT%\\%1\\probe.obj" "%OUT%\\%1\\d3d8.lib" kernel32.lib ||')
    script=script.replace('set MACHINE=%1','set FIXTURE_ARCH=\nif "%1"=="x86" set FIXTURE_ARCH=/arch:IA32\nset MACHINE=%1').replace('cl /nologo /c /O2','cl /nologo /c /O2 %FIXTURE_ARCH%')
    (out/'build-native.cmd').write_text(script)
    r=D.run(['cmd','/d','/c',out/'build-native.cmd'],out,os.environ.copy(),'build-native')
    assert r['exit']==0 and not re.search(r'\b(?:C1001|D8040)\b',r['stdout']+r['stderr']),r
    D.write(out/'native-inputs.json',{str(p):D.sha(p)for root in [HERE,HERE.parent/'d3d8_modes',HERE.parent/'d3d8_boundary']for p in root.glob('*')if p.is_file()})
def characterize(out):
    rows={}
    for rep in range(2):
        for arch in ['x86','x64']:
            case=out/f'native-{arch}-{rep}';case.mkdir();env=os.environ.copy();D.G.environment(env,case)
            probes=COMMON+(ABI if arch=='x86'else [])
            r=D.run([out/arch/'native.exe',D.G.verified_pair(arch),out/arch/'d3dprobe.dll',*probes],case,env,'run')
            assert r['exit']==0 and set(D.parse(r['stdout']))==set(probes),r
            rows[f'{arch}-{rep}']=r
    decoded={k:D.parse(r['stdout'])for k,r in rows.items()}
    D.write(out/'native-characterization.json',dict(runs=rows,decoded=decoded,
        first_process_enumeration_identical=decoded['x86-0']['probe_enumeration']==decoded['x64-0']['probe_enumeration'],
        repeat_enumeration_identical=decoded['x86-1']['probe_enumeration']==decoded['x64-1']['probe_enumeration'],
        backends={a:{n:D.sha(D.G.verified_pair(a)/n)for n in D.G.HASHES[a]}for a in ['x86','x64']}))
    # Actual observed last-error values, with no mapping or normalization.
    for k,v in decoded.items():
        log=v['probe_enum_last_error'];assert log[:2]==[0,1] and log[-2:]==[1,0]
        records=[log[i:i+11]for i in range(2,len(log)-2,11)]
        print(k,'count',v['probe_modes'][3],'last-error seed/result pairs',sorted({(r[2],r[4])for r in records}),flush=True)
    print('NATIVE COMPLETE; exact first/repeat enumeration comparisons recorded',flush=True)
def compare(out):
    n=json.loads((out/'native-characterization.json').read_text());expected=n['decoded']['x64-1'];x86=n['decoded']['x86-1']
    results=[]
    for rep in range(2):
        case=out/f'translated-{rep}';case.mkdir();env=os.environ.copy();D.G.environment(env,case);env['XRT_D3D8_DIR']=str(D.G.verified_pair('x64'))
        probes=COMMON+ABI
        r=D.run([out/'translated.exe',out/'x86/d3dprobe.dll',case/'report.json',*probes],case,env,'run');assert r['exit']==0,r
        values=D.parse(r['stdout']);assert set(values)==set(probes)
        for p in probes:
            assert values[p]==(x86 if p in ABI else expected)[p],('EXACT differential mismatch',p)
        for p in ['probe_modes','probe_enumeration','probe_enum_last_error',*ABI]:
            assert values[p]==x86[p],('EXACT x86/translated mismatch',p)
        for p,stride,offset in [('probe_count_abi',7,2),('probe_enum_abi',10,1),('probe_enum_full_abi',14,3)]:
            a=values[p];assert a[-1]==0
            assert all(a[i+offset:i+offset+5]==[0,0x12345678,0x23456789,0x3456789a,0x456789ab]for i in range(0,len(a)-1,stride)),p
        report=json.loads((case/'report.json').read_text());ev=report['events']
        assert report['events_dropped']==0 and report['events_recorded']==len(ev)
        assert [e['seq']for e in ev]==list(range(1,len(ev)+1)) and not any(e.get('truncated')for e in ev)
        assert any(e['kind']=='d3d8_cleanup'and e['references_released']==2 for e in ev)
        assert any(e['kind']=='d3d8_guest_pointer_audit'and e['passed']for e in ev)
        sys.path.insert(0,str(W/'tools/xrt'));import world_tick_checkpoint as T
        pairs={}
        for prefix,popped in [('d3d8_mode_count',12),('d3d8_enum',20)]:
            calls=[e for e in ev if e['kind']==prefix+'_call'];returns=[e for e in ev if e['kind']==prefix+'_return']
            paired=T.paired(calls,returns,popped);assert len(calls)==len(returns)==len(paired)
            pairs[prefix]=len(paired)
        results.append(dict(compared_values=sum(map(len,values.values())),events=len(ev),events_dropped=0,paired=pairs,report_sha256=D.sha(case/'report.json')))
    case=out/'negative';case.mkdir();env=os.environ.copy();D.G.environment(env,case);env['XRT_D3D8_DIR']=str(D.G.verified_pair('x64'))
    negatives={}
    for p,msg in [('probe_stale','stale or unknown'),('probe_mode_stale','stale or unknown'),('probe_enum_stale','stale or unknown'),('probe_unmeasured','RegisterSoftwareDevice is unmeasured'),('probe_device_guard','CreateDevice is unmeasured'),('probe_enum_null','NULL output is unmeasured'),('probe_enum_bad_range','invalid guest range'),('probe_enum_wrap','invalid guest range'),
        *[(p,'unchecked native access refused')for p in ['probe_invalid_count','probe_invalid_next','probe_invalid_ffff','probe_invalid_7fffffff','probe_invalid_ffffffff']]]:
        r=D.run([out/'translated.exe',out/'x86/d3dprobe.dll',case/(p+'-report.json'),p],case,env,p)
        assert r['exit']==76 and msg in r['stderr'],r
        report=json.loads((case/(p+'-report.json')).read_text());assert report['events_dropped']==0
        if p in ['probe_enum_null','probe_enum_bad_range','probe_enum_wrap']:
            assert not any(e['kind']=='d3d8_enum_call'for e in report['events'])
        negatives[p]=dict(exit=r['exit'],diagnostic=msg,report_sha256=D.sha(case/(p+'-report.json')))
    D.write(out/'results.json',dict(passed=True,positive=results,negative=negatives,
        first_process_x86_x64_exact=n['first_process_enumeration_identical'],repeat_x86_x64_exact=n['repeat_enumeration_identical'],
        outputs={str(f.relative_to(out)):D.sha(f)for f in out.rglob('*')if f.is_file()and f.suffix in ['.obj','.exe','.dll','.pdb']},
        runtime={str(f.relative_to(W/'experiments/xrt/runtime')):D.sha(f)for f in (W/'experiments/xrt/runtime').iterdir()if f.is_file()}))
    print('EXACT DIFFERENTIAL PASS',results,'negative guards',len(negatives),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build_native','characterize','build_translated','compare']);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    (D.build_translated if a.action=='build_translated'else globals()[a.action])(a.out.resolve())
