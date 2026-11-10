"""Exact comparisons and containment assertions; exit 76 alone is never a pass."""
import argparse,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import W,RT,HERE,sha,save
def lines(r):
    a=r['stdout'].splitlines()
    return list(map(int,a[0].split(' log ')[1].split())),list(map(int,a[1].split()[1:]))
def events(r,name):return [e for e in r.get('events',[])if e['kind']==name]
def main(out):
    runs=json.loads((out/'results.json').read_text())['runs'];comparisons=[];created=0;negative=0
    indexed={(r['arch'],r['case'],r['arg'],r['seed'],r['inject']):r for r in runs}
    for r in runs:
        if r['arch']=='translated':
            calls=events(r,'d3d8_device_call');returns=events(r,'d3d8_device_return');assert len(calls)<=1
            for e in returns:
                assert e['esp_after']-e['esp_before']==32 and e['return']==e['actual_return']
            created+=sum(e['result']==0 for e in returns)
            if r['exit']==0:
                assert len(returns)==len(calls)==1 and returns[0]['result']==0 and returns[0]['host_non_null']
                audit=events(r,'d3d8_device_audit');assert len(audit)==1 and audit[0]['typed_slots']==97 and audit[0]['passed']
                assert audit[0]['object']==returns[0]['device'] and 0x10000<=audit[0]['vtable']<0x300000
                for m in events(r,'d3d8_device_mxcsr'):assert m['before']&~63==m['after']&~63
                dc=events(r,'d3d8_device_cleanup')[0];pc=events(r,'d3d8_cleanup')[0]
                assert dc['seq']<pc['seq']<events(r,'d3d8_unload')[0]['seq']
                assert not events(r,'d3d8_unload')[0]['d3d8_loaded'] and not events(r,'d3d8_unload')[0]['d3d9_loaded']
                if r['case']==9:assert dc['references_released']==2 and dc['final_native_count']==0 and pc['references_released']==2
            else:
                negative+=1;message=events(r,'fatal')[0]['message'];case=r['case']
                if r['inject']==2:
                    assert len(returns)==1 and returns[0]['result']==0x8876086a and returns[0]['last_error']==203 and returns[0]['device']==0 and not returns[0]['host_non_null']
                    assert len(events(r,'test_backend_injection'))==1 and len(events(r,'d3d8_failure_containment'))==1
                    assert not events(r,'d3d8_unload') and not events(r,'d3d8_cleanup')
                    assert 'process teardown required' in message
                elif r['inject']in [5,6]:
                    assert len(returns)==1 and returns[0]['result']==0
                    assert ('unmodelled successful QI identity' if r['inject']==5 else 'parent identity changed')in message
                    assert events(r,'d3d8_failure_containment') and not events(r,'d3d8_unload') and not events(r,'d3d8_cleanup')
                elif case==12:
                    assert 'one native attempt' in message and len(calls)==1 and not returns
                    assert len(events(r,'d3d8_failure_containment'))==1
                elif case in [7,8,35]:assert 'stale or unknown guest COM interface' in message and len(returns)==1
                elif case==10:assert 'live D3D8 device retains' in message and len(returns)==1
                elif case==11:assert 'one native attempt' in message and len(returns)==1
                elif case==20:assert 'unsupported captured tuple' in message and not calls
                elif case in [21,22,23,24]:assert 'HWND token' in message and not calls
                elif case==31:assert 'overlapping' in message and not calls
                elif case in [25,26,27,29]:
                    assert 'D3D8 device: invalid writable guest range' in message and not calls
                    if case in [27,29]:assert events(r,'test_pointer_layout')
                elif case in [32,33,34]:assert 'D3D8 device: invalid writable guest range' in message and len(returns)==1
                else:raise AssertionError(r)
    for case in [0,1,2,3,4,5,6,9]:
        a,b,t=[indexed[(arch,case,0,18,0)]for arch in ['x86','x64','translated']]
        va,aa=lines(a);vb,ab=lines(b);vt,at=lines(t)
        assert va==vb==vt,(case,va,vb,vt)
        if case==6:
            assert aa[1:]==at[1:]
            assert at[1]==at[8]==0x3000027f and at[2:4]==[0,0]
            assert at[4:8]==[0x12345678,0x23456789,0x3456789a,0x456789ab]
            assert struct.unpack('<dd',struct.pack('<4I',*at[10:14]))==(1.5,1.0)
        comparisons.append(dict(case=case,values=len(vt),native_x86=True,native_x64=True,translated=True))
    for seed in [0,0x13572468,0xffffffff]:
        v=[lines(indexed[(arch,0,0,seed,0)])[0]for arch in ['x86','x64','translated']]
        assert v[0]==v[1]==v[2] and v[0][:3]==[0,0,1]
    for case in [6,13]:
        r=indexed[('translated',case,0,18,1)];v,a=lines(r)
        assert v[:4]==[1,1,1,1] and v[4+(case==13):8+(case==13)]==[1,1,1,1]
        assert v[8+(case==13):12+(case==13)]==[0,0,1,4]
        assert a[1:]==lines(indexed[('translated',6,0,18,0)])[1][1:]
        begin=events(r,'d3d8_device_call')[0]['seq'];end=events(r,'d3d8_device_return')[0]['seq']
        assert sum(begin<e['seq']<end and e.get('message')==127 for e in events(r,'gui_callback'))==4
        assert events(r,'test_suspended_cpu')[0]['all_registers_x87_flags']
        assert events(r,'test_suspended_cpu_after_native')[0]['all_registers_x87_flags']
    r=indexed[('translated',6,0,18,4)];m=events(r,'d3d8_device_mxcsr')[0];assert m['before']==0x3f80 and m['after']==0x3fa0
    r=indexed[('translated',0,0,18,3)];v,a=lines(r)
    assert v[4:18]==[101,102,103,104,105,106,0,1,108,109,110,111,112,113] and events(r,'test_mutation_injection')
    for path,h in json.loads((out/'sources.json').read_text()).items():
        if path.startswith('experiments/xrt/runtime/'):assert sha(W/path)==h,path
    native_abi=json.loads((out/'native-abi.json').read_text())
    for r in native_abi:
        d=r['data'];assert d['stack_delta']==0
        pre,post=bytes.fromhex(d['pre']),bytes.fromhex(d['post'])
        assert pre[:5]==post[:5] and int.from_bytes(pre[:2],'little')==0x77f
        assert pre[32:42]==post[32:42] and pre[48:58]==post[48:58]
        assert int.from_bytes(pre[24:28],'little')==0x3f80 and int.from_bytes(post[24:28],'little')==0x3fa0
        if r['arch']=='x86':assert d['regs']==[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0]
        else:
            assert d['regs']==[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
            assert bytes.fromhex(d['xmm'])==struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10
        if r['depth']==77:assert d['hr']==0 and d['last_error']==0 and d['non_null'] and d['device_release']==d['parent_release']==0 and not d['d3d8_loaded'] and not d['d3d9_loaded']
        else:assert d['hr']==0x8876086a and d['last_error']==203 and not d['non_null'] and d['modules_retained'] and d['attempts']==1
    result=dict(passed=True,native_processes=sum(r['arch']!='translated'for r in runs)+len(native_abi),translated_processes=sum(r['arch']=='translated'for r in runs),
        translated_successful_creations=created,guard_and_failure_cases=negative,comparisons=comparisons,compared_values=sum(r['values']for r in comparisons),
        callback_context_and_parent_revival=True,live_x87_and_abi=True,mxcsr_precision_status_preserved=True,all_97_guest_slots=True,
        pointer_guards=True,shutdown_order=True,one_real_backend_failure_injected=True,all_scalar_copyback_injected=True,
        fixture=str(out),scope='production boundary; test-only injection clearly separated; zero graphical game clients; no rendering methods')
    save(out/'audit.json',result);save(W/'out/recovery/d3d8-create-20261025-01/measurement-02.json',result)
    print('AUDIT PASS',result,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
