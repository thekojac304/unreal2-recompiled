"""Assert actual x86/x64 and translated evidence; never infer success from entry."""
import argparse,json,re,struct
from pathlib import Path
def read(p):return json.loads(Path(p).read_text())
def rows(r,k):return [v for v in r['rows']if v['kind']==k]
def native(out,state,value):
 runs=read(out/'native-results.json');assert len(runs)==18
 for r in runs:
  assert rows(r,'create')[0]['hr']==0 and rows(r,'create')[0]['device']
  assert rows(r,'cleanup')==[dict(kind='cleanup',device_release=0,parent_release=0,window_valid=False,d3d8_loaded=False,d3d9_loaded=False,callbacks=0,foreign_callbacks=0)]
  assert rows(r,'identity')==[dict(kind='identity',parent_hr=0,same_parent=True,add=2,balance=1,parent_release=2,creation_hr=0,same_window=True,flags=66)]
  calls=rows(r,'call');states=rows(r,'state');assert len(calls)==4 and len(states)==5
  for c in calls:
   assert c['hr']==0 and c['last_error']==r['seed'] and c['delta']==0
   a,b=bytes.fromhex(c['pre']),bytes.fromhex(c['post'])
   assert a[:5]==b[:5] and a[24:28]==b[24:28]
   assert a[32:42]==b[32:42]and a[48:58]==b[48:58]
   assert int.from_bytes(a[:2],'little')==0x27f and int.from_bytes(a[24:28],'little')==0x3f80
   if r['arch']=='x86':assert c['regs']==[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0]
   else:
    assert c['regs']==[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
    assert bytes.fromhex(c['xmm'])==struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10
  assert all(s['values']==states[1]['values']for s in states[1:])
  changes=[i for i in range(256)if states[0]['values'][i]!=states[1]['values'][i]]
  assert all(i==r['state']for i in changes),changes
  if r['state']==state:assert states[1]['values'][state]==[0,r['value']]
  if r['prime']:
   assert states[0]['values'][state]==[0,value^1] and changes==[state]
 for r in runs[:9]:
  s=next(s for s in runs if s['arch']=='x64'and all(s[k]==r[k]for k in ['state','value','prime','seed']))
  assert rows(r,'state')==rows(s,'state')
 result=dict(passed=True,state=state,value=value,native_processes=len(runs),native_calls=72,hresult=0,last_error='preserved for all four seeds',all_256_readbacks_equal_x86_x64=True,real_transition_from=value^1,real_transition_to=value,stdcall_stack_and_nonvolatile=True,x87_control_status_top_live_values_preserved=True,mxcsr_preserved=True,x64_xmm6_to_xmm15_preserved=True,callbacks_during_set=0,cleanup_verified=True,invalid_state_examples='0 and 255 return S_OK with no readback change; alternate/max values retained for measured state')
 (out/'native-audit.json').write_text(json.dumps(result,indent=2));print('NATIVE DIFFERENTIAL PASS',state,value,flush=True)
def log(r):return list(map(int,re.search(r'returned 0 log([^\n]*)',r['stdout'])[1].split()))
def abi(r):return list(map(int,re.search(r'abi_clear([^\n]*)',r['stdout'])[1].split()))
def translated(out,state,value):
 assert read(out/'native-audit.json')['passed'];runs=read(out/'translated-results.json');assert len(runs)==31
 indexed={(r['arch'],r['state'],r['value'],r['seed'],r['variant'],r['inject']):r for r in runs}
 for seed in [18,0,0x13572468,0xffffffff]:
  group=[r for r in runs if r['state']==state and r['value']==value and r['seed']==seed and r['variant']=='production']
  assert len(group)==3;assert len({tuple(log(r))for r in group})==1,[log(r)for r in group]
  x86=next(r for r in group if r['arch']=='x86');tr=next(r for r in group if r['arch']=='translated');assert abi(x86)[1:]==abi(tr)[1:],(abi(x86),abi(tr))
  a=abi(tr);assert a[2:8]==[0,0,0x12345678,0x23456789,0x3456789a,0x456789ab]and a[1]==a[8]
 for r in runs:
  if r['arch']!='translated':continue
  ev=r['events'];calls=[e for e in ev if e['kind']=='d3d8_state_call'];rets=[e for e in ev if e['kind']=='d3d8_state_return']
  if r['exit']==0:
   assert len(calls)==len(rets)==4
   for c,e in zip(calls,rets):
    assert c['state']==state and c['value']==value and e['result']==0 and e['last_error']==r['seed']
    assert c['this']==e['this'] and e['esp_before']==c['esp'] and e['return']==c['return']
    assert e['esp_after']==e['esp_before']+16 and e['return']==e['actual_return']and e['mxcsr_before']==e['mxcsr_after']
   if r['variant']=='observed':
    assert len([e for e in ev if e['kind']=='test_suspended_state_cpu'])==4
    native_run=next(x for x in read(out/'native-results.json')if x['arch']=='x86'and x['state']==state and x['value']==value and x['prime']==1)
    expected=rows(native_run,'state');actual=[x for x in r['observations']if x['kind']=='state']
    assert [actual[i]['values']for i in [0,1,3,5,7]]==[x['values']for x in expected]
    enters=[e['seq']for e in ev if e['kind']=='test_native_enter'];leaves=[e['seq']for e in ev if e['kind']=='test_native_leave']
    assert len(enters)==len(leaves)==4
    assert not[e for e in ev if 'callback'in e['kind']and any(a<e['seq']<b for a,b in zip(enters,leaves))]
    if r['inject']:assert log(r)[-13]==16,log(r)
   cleanup=[e for e in ev if e['kind']=='d3d8_device_cleanup'];unload=[e for e in ev if e['kind']=='d3d8_unload']
   assert len(cleanup)==len(unload)==1 and cleanup[0]['final_native_count']==0
   assert not unload[0]['d3d8_loaded'] and not unload[0]['d3d9_loaded']
  else:
   assert r['exit']==76 and not rets
   assert not[e for e in ev if e['kind']=='test_native_enter']
   fatal=next(e for e in ev if e['kind']=='fatal')['message'];case=r['state']
   if case in [250,251,254,256]:
    assert 'stale or unknown guest COM interface' in fatal and not calls
    if r['variant']=='observed':
     entry=[e for e in ev if e['kind']=='test_state_adapter_entry'];assert len(entry)==1
     assert entry[0]['state']==7 and entry[0]['value']==1
     if case==250:assert entry[0]['this']==1
     if case==256:assert entry[0]['this']==0
     creation=next(e for e in ev if e['kind']=='d3d8_device_return')
     if case==251:assert entry[0]['this']==creation['device']
     if case==254:assert entry[0]['this']!=creation['device']
   elif case==252:assert 'unsupported slot 51 GetRenderState' in fatal and not calls
   elif case in [70,71,72]:
    assert {70:'Release during native rendering',71:'reentrant rendering',72:'live D3D8 device retains'}[case] in fatal
    assert [e for e in ev if e['kind']=='d3d8_failure_containment'] and not[e for e in ev if e['kind']=='d3d8_unload']
   else:assert f'unsupported state={r["state"]} value={r["value"]}' in fatal and not calls
   if case not in [70,71,72]:
    assert next(e for e in ev if e['kind']=='d3d8_device_cleanup')['final_native_count']==0
    unload=next(e for e in ev if e['kind']=='d3d8_unload');assert not unload['d3d8_loaded']and not unload['d3d9_loaded']
 parent_first=indexed[('translated',253,0,18,'production',0)]
 assert parent_first['exit']==0 and len([e for e in parent_first['events']if e['kind']=='d3d8_state_return'])==4
 code=(out/'source-snapshot/runtime/d3d8_device_slots.inc').read_text();assert code.count('unsupported slot ')==89
 assert not re.search(r'static void d8_device_GetRenderState[^\n]*\bRET_STD\b',code)
 result=dict(passed=True,state=state,value=value,fixture_processes=len(runs),native_x86_x64_translated_logs_equal=True,guest_stdcall_and_x87_equal_native_x86=True,observed_256_state_readbacks_equal=True,suspended_cpu_and_frame_unchanged=True,forced_nested_callbacks_verified=True,reentrancy_and_release_and_window_destruction_refused=True,production_GetRenderState_unsupported=True,unknown_stale_wrong_type_and_null_identity_refused=True,invalid_this_adapter_entry_observed=True,no_native_call_on_guard_failure=True,parent_first_lifetime_verified=True,normal_cleanup_verified=True,fatal_reentrant_backend_retained_until_process_exit=True,only_production_combination=[7,1])
 (out/'audit.json').write_text(json.dumps(result,indent=2));print('TRANSLATED DIFFERENTIAL PASS',state,value,flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['native','translated']);a.add_argument('--out',type=Path,required=True);a.add_argument('--state',type=int,default=7);a.add_argument('--value',type=int,default=1);v=a.parse_args();globals()[v.action](v.out.resolve(),v.state,v.value)
