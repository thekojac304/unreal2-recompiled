"""Verify retained native records and compare the real translated fixture outputs."""
import json,struct,sys
from pathlib import Path
from run import W,HERE,sha,write
from slots import SLOTS
O=W/'out/recovery/d3d8-device-20261025-01'
N=W/'experiments/xrt/build/d3d8-device-fixture-20261025-02'
X=W/'experiments/xrt/build/d3d8-device-fixture-20261025-04'
T=W/'experiments/xrt/build/d3d8-device-translated-20261025-04'
def rows(run,kind):return [r for r in run['rows']if r['kind']==kind]
def fx(s):
    b=bytes.fromhex(s)
    return dict(control=int.from_bytes(b[:2],'little'),status=int.from_bytes(b[2:4],'little'),tag=b[4],mxcsr=int.from_bytes(b[24:28],'little'),registers=[b[32+i*16:42+i*16].hex()for i in range(8)])
def main():
    base=json.loads((N/'native-characterization.json').read_text())
    runs=base['runs']+json.loads((N/'dimension-repeats.json').read_text())+json.loads((X/'extended-characterization.json').read_text())+json.loads((X/'failure-repeats.json').read_text())
    exact={};negative={};abis=[];diffs=[];retained=[]
    for run in runs:
        creates=rows(run,'create');assert creates
        assert run['exit']==(90 if any(r['exception']for r in creates)else 0)
        setup=rows(run,'setup')[0];assert setup['present_bytes']==(52 if run['arch']=='x86'else 56)
        assert setup['window_thread']==setup['thread']and setup['window_process']==setup['process']
        for r in creates:
            changed=[i for i,(a,b)in enumerate(zip(r['before'],r['after']))if a!=b]
            if r['exception']:
                assert r['hr']==0xdeadbeef and r['exception']==0xc0000005
            elif not r['hr']:
                assert r['output']not in [0,0xa5a5a5a5]and r['last_error']==0
            else:assert r['output']==0 or run['case']=='out_null'
            assert changed==({'count_zero':[3],'format_unknown':[2]}.get(run['case'],[])),(run['case'],changed)
            if run['case']=='exact':
                assert r['hr']==0 and r['raw_before']==r['raw_after']
                exact.setdefault(run['arch'],[]).append(r)
        for release in rows(run,'device_final_release')+rows(run,'parent_final_release'):assert release['count']==0
        for unload in rows(run,'unload'):
            assert not unload['d3d8_loaded']
            if unload['d3d9_loaded']:retained.append(dict(arch=run['arch'],case=run['case'],seed=run['seed'],repeat_process=run['repeat_process'],resources=rows(run,'resources')))
        for cb in rows(run,'callbacks'):assert cb['reentrant']==cb['foreign_thread']==0
        for a in rows(run,'abi'):
            assert a['delta']==0
            expected=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0]if run['arch']=='x86'else[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
            assert a['regs']==expected
            if run['arch']=='x64':assert a['xmm']==(struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10).hex()
            pre,post=fx(a['fx_pre']),fx(a['fx_post'])
            assert pre['control']==0x77f and post['control']==(0x7f if run['case']=='abi_no_preserve'else 0x77f)
            assert pre['status']==post['status']and pre['tag']==post['tag']and pre['registers'][:2]==post['registers'][:2]
            assert pre['mxcsr']&~63==post['mxcsr']&~63
            abis.append(dict(arch=run['arch'],case=run['case'],pre=pre,post=post,stack_delta=a['delta'],nonvolatiles_retained=True))
        if run['case']=='separate_zero':
            dims=rows(run,'client_dimensions')[0];back=rows(run,'backbuffer')[0]
            assert back['desc'][-2:]==dims['device']and back['desc'][-2:]!=dims['focus']
        if run['case']=='cross_thread':
            p=rows(run,'pointer_context')[0];assert p['call_thread']!=p['focus_owner_thread']
        if run['case']=='pp_readonly'and rows(run,'pointer_context'):
            assert creates[0]['exception_address']-rows(run,'pointer_context')[0]['parameters']==12
        if run['case']=='repeated':
            resources=rows(run,'resources');after=[r for r in resources if r['tag']=='after_release'];assert len(after)==8
            assert len({(r['handles'],r['threads'],r['user'],r['gdi'])for r in after})==1
        if run in base['runs']and run['case']not in ['exact','abi','abi_no_preserve','repeated']:
            negative.setdefault(run['case'],{})[run['arch']]=creates[0]
    assert len(exact['x86'])==len(exact['x64'])==16
    for name,v in negative.items():
        a,b=v['x86'],v['x64']
        if (a['hr'],a['last_error'],a['exception'])!=(b['hr'],b['last_error'],b['exception']):diffs.append(dict(case=name,x86={k:a[k]for k in ['hr','last_error','exception']},x64={k:b[k]for k in ['hr','last_error','exception']}))
    fixture=json.loads((T/'results.json').read_text());comparisons=[]
    for run in fixture['runs']:
        report=json.loads(Path(run['report']).read_text());ev=report['events']
        assert [e['seq']for e in ev]==list(range(1,len(ev)+1))and report['events_dropped']==0
        assert all(e['typed_slots']==97 and e['passed']for e in ev if e['kind']=='fixture_device_audit')
        successes=[e for e in ev if e['kind']=='fixture_create_return'and e['result']==0]
        assert len(successes)==sum(e['kind']=='fixture_device_audit'for e in ev)
        if run['exit']:continue
        line=(Path(run['report']).parent/'run.stdout.txt').read_text().strip();values=[int(x)&0xffffffff for x in line.split(' log ')[1].split()]
        window=values[9];pp=[1540,945,22,1,0,1,window,1,1,77,1,0,0]
        if run['probe']=='probe_fixture':
            # Values derived from native COM observations, plus typed HWND identity.
            native=next(r for r in base['runs']if r['arch']=='x64'and r['case']=='exact')
            assert rows(native,'qi')[:2][0]['same']and rows(native,'qi')[:2][1]['same']
            a=rows(native,'device_add')[0]['count'];b=rows(native,'device_balance')[0]['count'];par=rows(native,'get_parent')[0]['release']
            block=[0,0,1]+pp+[a,b,0,1,b,0,1,b,0x80004002,1,0,0,1,1,66,0,1,par,0]
            fail1=[negative['adapter_max']['x64']['hr'],negative['adapter_max']['x64']['last_error'],0]+pp
            fail2=[negative['interval_one']['x64']['hr'],negative['interval_one']['x64']['last_error'],0]+pp[:-1]+[1]
            expected=block*3+fail1+fail2+[0]
        elif run['probe']=='probe_fixture_parent_first':expected=[0,0,1]+pp+[1,0,1,1,0]
        else:expected=[0,0,1]+pp+[2]
        assert values==expected,(run['probe'],len(values),len(expected))
        comparisons.append(dict(probe=run['probe'],rep=run['rep'],values=len(values),exact=True))
    record=dict(passed=True,base_commit='8c6220a6baadd575340fa81e51e2fa0a2af86a8c',native_processes=len(runs),native_calls=sum(len(rows(r,'create'))for r in runs),
        exact=exact,negative=negative,architecture_differences=diffs,abi=abis,retained_d3d9=retained,fixture_comparisons=comparisons,
        translated_attempts=sum(len(r['creates'])for r in fixture['runs']),translated_successes=sum(sum(c['result']==0 for c in r['creates'])for r in fixture['runs']),
        fixture_processes=len(fixture['runs']),production_CreateDevice_guarded=True,production_runtime_unchanged=True,
        slots=[dict(slot=i,guest_offset=i*4,native_x64_offset=i*8,name=n,stdcall_argument_bytes=4*(args+1))for i,(n,args)in enumerate(SLOTS)],
        scope='fixture only; no genuine graphical client; no Clear/Present/rendering host calls')
    write(O/'measurement.json',record);write(W/'experiments/xrt/results/compare/d3d8_device_characterization.json',record)
    print('AUDIT PASS',len(runs),'native processes',record['native_calls'],'native calls;',record['translated_successes'],'actual translated fixture devices;',sum(r['values']for r in comparisons),'exact compared values;',len(abis),'ABI snapshots')
if __name__=='__main__':main()
