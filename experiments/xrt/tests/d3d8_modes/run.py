"""Serial build and bounded native/actual-runtime display-mode characterization."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
W=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'tools/xrt'))
import graphics_backend as G
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2))
def parse(s):
    return {line.split()[0]:[int(v)&0xffffffff for v in line.split(' log ')[1].split()]
            for line in s.splitlines() if ' returned 0 log' in line}
def run(cmd,out,env,name):
    r=subprocess.run([str(c)for c in cmd],cwd=out,env=env,capture_output=True,text=True,timeout=120)
    (out/(name+'.stdout.txt')).write_text(r.stdout);(out/(name+'.stderr.txt')).write_text(r.stderr)
    row=dict(command=[str(c)for c in cmd],exit=r.returncode,stdout=r.stdout,stderr=r.stderr)
    write(out/(name+'.json'),row);return row
def build_native(out):
    assert not out.exists(),'fresh serial output required';out.mkdir(parents=True)
    original=(HERE.parent/'d3d8_boundary/build_native.cmd').read_text()
    script=original.replace('set OUT=experiments\\xrt\\build\\d3d8_boundary','set OUT='+str(out)).replace('set HERE=experiments\\xrt\\tests\\d3d8_boundary','set HERE='+str(HERE))
    script=script.replace('cd /d "%~dp0\\..\\..\\..\\.."','cd /d "'+str(W)+'"')
    script=script.replace('"%HERE%\\d3d8.def"','"'+str(HERE.parent/'d3d8_boundary/d3d8.def')+'"')
    (out/'build-native.cmd').write_text(script)
    row=run(['cmd','/d','/c',out/'build-native.cmd'],out,os.environ.copy(),'build-native')
    assert row['exit']==0, row
    assert not re.search(r'\b(?:C1001|D8040)\b',row['stdout']+row['stderr'])
    write(out/'native-inputs.json',{str(p):sha(p)for p in [*HERE.glob('*.c'),HERE.parent/'d3d8_boundary/probe.c',W/'experiments/xrt/runtime/d3d8_abi.h']})
def characterize(out):
    rows={}
    common=['probe_queries','probe_lifetime','probe_formats','probe_errors','probe_guards','probe_modes','probe_enumeration','probe_leak']
    for rep in range(2):
        for arch in ['x86','x64']:
            case=out/f'native-{arch}-{rep}';case.mkdir();env=os.environ.copy();G.environment(env,case)
            probes=common+(['probe_count_abi','probe_enum_abi']if arch=='x86'else[])
            row=run([out/arch/'native.exe',G.verified_pair(arch),out/arch/'d3dprobe.dll',*probes],case,env,'run')
            assert row['exit']==0,(arch,row);assert all(p in parse(row['stdout'])for p in probes)
            rows[f'{arch}-{rep}']=row
    p={k:parse(r['stdout'])for k,r in rows.items()}
    summary=dict(passed=True,runs=rows,mode_counts_identical=p['x86-0']['probe_modes']==p['x64-0']['probe_modes'],
        enumeration_identical=p['x86-0']['probe_enumeration']==p['x64-0']['probe_enumeration'],decoded=p,
        process_repeat_identical={a:p[a+'-0']==p[a+'-1']for a in ['x86','x64']},
        binaries={str(f.relative_to(out)):sha(f)for arch in ['x86','x64']for f in (out/arch).iterdir()if f.is_file()},
        backends={arch:{n:sha(G.verified_pair(arch)/n)for n in G.HASHES[arch]}for arch in ['x86','x64']})
    write(out/'native-characterization.json',summary)
    print('NATIVE PASS; count/enumeration identical:',summary['mode_counts_identical'],summary['enumeration_identical'])
    print('mode log',p['x86-0']['probe_modes']);print('enum layout / initial values',p['x86-0']['probe_enumeration'][:40])
def build_translated(out):
    assert (out/'native-characterization.json').is_file();assert not(out/'gen').exists()
    row=run([W/'.venv/Scripts/python.exe','-I',W/'tools/xrt/xlift.py',out/'x86/d3dprobe.dll','--out',out/'gen'],out,os.environ.copy(),'lift')
    assert row['exit']==0,row
    source=(HERE.parent/'d3d8_boundary/build.cmd').read_text();command=next(s for s in source.splitlines()if s.startswith('cl '))
    command=command.split(' > ')[0].replace('%OUT%',str(out)).replace('%HERE%',str(HERE)).replace('%RT%',str(W/'experiments/xrt/runtime'))
    script='@echo off\ncall "C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" x64 >nul || exit /b 1\n'+command+'\n'
    (out/'build-translated.cmd').write_text(script)
    row=run(['cmd','/d','/c',out/'build-translated.cmd'],out,os.environ.copy(),'build-translated')
    assert row['exit']==0,row
    assert not re.search(r'\b(?:C1001|D8040)\b',row['stdout']+row['stderr'])
def regression(out):
    """Existing production-supported COM/query probes, independent of mode support."""
    native=json.loads((out/'native-characterization.json').read_text())
    probes=['probe_queries','probe_lifetime','probe_formats','probe_errors','probe_guards','probe_leak']
    case=out/'baseline-regression';case.mkdir();env=os.environ.copy();G.environment(env,case);env['XRT_D3D8_DIR']=str(G.verified_pair('x64'))
    row=run([out/'translated.exe',out/'x86/d3dprobe.dll',case/'report.json',*probes],case,env,'run')
    assert row['exit']==0,row
    values=parse(row['stdout']);expected=native['decoded']['x64-0']
    assert all(values[p]==expected[p]for p in probes)
    report=json.loads((case/'report.json').read_text())
    assert any(e['kind']=='d3d8_cleanup'and e['references_released']==2 for e in report['events'])
    assert any(e['kind']=='d3d8_guest_pointer_audit'and e['passed'] for e in report['events'])
    negatives={}
    for p,msg in [('probe_stale','stale or unknown guest COM interface'),('probe_unmeasured','RegisterSoftwareDevice is unmeasured'),('probe_enum_guard','EnumAdapterModes is unmeasured'),('probe_device_guard','CreateDevice is unmeasured')]:
        r=run([out/'translated.exe',out/'x86/d3dprobe.dll',case/(p+'.json'),p],case,env,p)
        assert r['exit']==76 and msg in r['stderr'],r;negatives[p]=r
    write(out/'baseline-regression.json',dict(passed=True,compared_values=sum(map(len,values.values())),positive=row,negative=negatives,cleanup_references=2,pointer_audit=True))
    print('EXISTING COM/QUERY REGRESSION PASS',sum(map(len,values.values())),'values, cleanup, typed pointer audit and four negative guards')
def compare(out):
    native=json.loads((out/'native-characterization.json').read_text());probes=['probe_queries','probe_lifetime','probe_formats','probe_errors','probe_guards','probe_modes','probe_count_abi','probe_leak']
    case=out/'translated-final';case.mkdir();env=os.environ.copy();G.environment(env,case);env['XRT_D3D8_DIR']=str(G.verified_pair('x64'))
    row=run([out/'translated.exe',out/'x86/d3dprobe.dll',case/'report.json',*probes],case,env,'run')
    assert row['exit']==0,row
    values=parse(row['stdout']);x64=native['decoded']['x64-1'];x86=native['decoded']['x86-1']
    assert all(values[p]==(x86 if p=='probe_count_abi'else x64)[p] for p in probes),'differential mismatch'
    assert values['probe_modes']==x86['probe_modes'],'native x86 / translated mode-count mismatch'
    abi=values['probe_count_abi'];assert all(abi[i+2:i+7]==[0,0x12345678,0x23456789,0x3456789a,0x456789ab]for i in range(0,len(abi)-1,7))
    report=json.loads((case/'report.json').read_text());events=report['events']
    assert any(e['kind']=='d3d8_cleanup'and e['references_released']==2 for e in events)
    assert any(e['kind']=='d3d8_guest_pointer_audit'and e['passed']for e in events)
    negatives={}
    for p,msg in [('probe_stale','stale or unknown guest COM interface'),('probe_mode_stale','stale or unknown guest COM interface'),('probe_unmeasured','RegisterSoftwareDevice is unmeasured'),('probe_enum_guard','EnumAdapterModes is unmeasured'),('probe_device_guard','CreateDevice is unmeasured'),
                  *[(p,'unchecked native access refused')for p in ['probe_invalid_count','probe_invalid_next','probe_invalid_ffff','probe_invalid_7fffffff','probe_invalid_ffffffff']]]:
        r=run([out/'translated.exe',out/'x86/d3dprobe.dll',case/(p+'-report.json'),p],case,env,p)
        assert r['exit']==76 and msg in r['stderr'],r;negatives[p]=r
        if p.startswith('probe_invalid_'):
            guard=json.loads((case/(p+'-report.json')).read_text())['events']
            assert any(e['kind']=='d3d8_invalid_adapter'and not e['native_mode_count_called'] for e in guard)
            assert not any(e.get('method')=='GetAdapterModeCount'and e['kind']=='d3d8'for e in guard)
    write(out/'results.json',dict(passed=True,positive=row,negative=negatives,compared_values=sum(map(len,values.values())),
        count_abi_calls=(len(abi)-1)//7,cleanup_references=2,events_recorded=report['events_recorded'],
        outputs={str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.is_file()and f.suffix in ['.obj','.exe','.dll','.pdb']},
        runtime={str(f.relative_to(W/'experiments/xrt/runtime')):sha(f)for f in (W/'experiments/xrt/runtime').iterdir()if f.is_file()}))
    print('DIFFERENTIAL PASS',sum(map(len,values.values())),'values;',len(negatives),'negative guards; ABI and cleanup pass')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build_native','characterize','build_translated','regression','compare']);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    globals()[a.action](a.out.resolve())
