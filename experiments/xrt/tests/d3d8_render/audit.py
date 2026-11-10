"""Require exact guest/native returns, modeled FPU, pixels and lifetime evidence."""
import json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));from run import O,W,RT,save,sha
from audit_native import abi
def events(r,k):return [e for e in r.get('events',[])if e['kind']==k]
def observations(r,k):return [e for e in r.get('observations',r.get('rows',[]))if e['kind']==k]
def values(r):return list(map(int,next(s for s in r['stdout'].splitlines()if s.startswith('returned ')).split(' log ')[1].split()))
def guestabi(r,name):return list(map(int,next(s for s in r['stdout'].splitlines()if s.startswith(name+' ')).split()[1:]))
def main(out):
 runs=json.loads((out/'translated-results.json').read_text());native=json.loads((out/'native-results.json').read_text());assert len(native)==34
 indexed={(r['arch'],r['case'],r['arg'],r['seed'],r['variant'],r['inject']):r for r in runs};compared=0;calls=0
 for r in native:
  abi(r,0x27f)
  assert observations(r,'release')==[dict(kind='release',device=0,parent=0)]
  end=observations(r,'cleanup')[0];assert not any(end[k]for k in ['d3d8_loaded','d3d9_loaded','window_valid','foreign_callbacks'])
  assert end['callbacks'][2:4]==[0,0]
  if r['case']not in [10,11]:
   for b,c in zip(observations(r,'backbuffer')[2::2],observations(r,'window_capture')):
    assert b['rgb_fnv64']==c['rgb_fnv64'] and b['samples'][:3]==c['samples']
 # Direct project-owned PE32/x64 versus the production translated runtime.
 for case,seed in [(c,18)for c in range(8)]+[(0,s)for s in [0,0x13572468,0xffffffff]]:
  a,b,t=[indexed[(arch,case,0,seed,'production',0)]for arch in ['x86','x64','translated']]
  va,vb,vt=values(a),values(b),values(t);assert va==vb==vt,(case,seed,va,vb,vt);compared+=len(vt)
  if case==6:
   for n in ['abi_clear','abi_present']:
    an,at=guestabi(a,n),guestabi(t,n);assert an[1:]==at[1:]
    assert at[1]==0x3000027f and at[2:4]==[0,0]
    assert at[4:8]==[0x12345678,0x23456789,0x3456789a,0x456789ab]
    assert at[8]==(0x3020027f if n=='abi_present'else 0x3000027f)
    assert struct.unpack('<dd',struct.pack('<4I',*at[10:14]))==(1.5,1.0)
 for r in [r for r in runs if r['arch']=='translated']:
  creation=events(r,'d3d8_device_return');assert len(creation)==1 and creation[0]['result']==0;guest=creation[0]['device']
  ent,ret=events(r,'d3d8_render_call'),events(r,'d3d8_render_return');calls+=len(ret)
  if r['exit']==0:
   assert len(ent)==len(ret)==(16 if r['case']==5 else 4 if r['case']==7 else 2)
   for i,(e,l)in enumerate(zip(ent,ret)):
    assert e['method']==l['method']==('Present'if i%2 else'Clear')and e['this']==l['this']==guest
    assert l['result']==0 and l['last_error']==(r['seed']if i%2==0 or(i>1 and r['variant']=='observed')else 0)
    assert l['return']==l['actual_return']==e['return']and l['esp_before']==e['esp']
    assert l['esp_after']-l['esp_before']==(24 if i%2 else 32)
    assert l['mxcsr_before']&~63==l['mxcsr_after']&~63
   if r['variant']=='observed':
    ne,nl=events(r,'test_native_enter'),events(r,'test_native_leave');assert len(ne)==len(nl)==len(ret)
    for e,l in zip(ne,nl):
     assert e['method']==l['method']and e['this']==l['this']==guest and l['result']==0
     assert not any(e['seq']<v['seq']<l['seq']for v in events(r,'gui_callback'))
    preserved=events(r,'test_suspended_render_cpu');assert len(preserved)==len(ret) and all(p['all_cpu_bytes']for p in preserved)
    for b in observations(r,'backbuffer'):
     assert [b[k]for k in ['get_hr','desc_hr','lock_hr','unlock_hr','surface_release']]==[0]*5
     assert b['desc']==[22,1,1,0,5821200,0,1540,945]and b['pitch']==6160
    states=observations(r,'state');first={k:v for k,v in states[0].items()if k!='tag'};assert all({k:v for k,v in s.items()if k!='tag'}==first for s in states)
   assert events(r,'d3d8_device_cleanup')[0]['final_native_count']==0
   unload=events(r,'d3d8_unload')[0];assert not unload['d3d8_loaded']and not unload['d3d9_loaded']
  else:
   assert r['exit']==76;msg=events(r,'fatal')[0]['message'];case=r['case']
   if case in [70,71,72]:
    assert not ret and not events(r,'test_native_enter') and events(r,'d3d8_failure_containment')
    assert not events(r,'d3d8_unload')
    assert {70:'Release during native rendering',71:'reentrant rendering',72:'live D3D8 device retains'}[case]in msg
   elif case==40:assert f'unsupported slot {r["arg"]}'in msg and not ent
   elif case in range(50,58):assert 'unsupported rendering window tuple'in msg and not ent
   elif case in [27,28,29]:assert 'stale or unknown guest COM interface'in msg and not ent
   elif case in [23,24,25,26]:assert 'only four NULL arguments'in msg and len(ent)==len(ret)==1
   elif case in [22,30,34]and r['arg']!=0:assert 'invalid readable guest range'in msg and not ent
   elif case==33:assert 'unsupported rectangle bounds'in msg and not ent
   else:assert 'unsupported argument combination'in msg and not ent
 # Entire RGB images (via FNV of every RGB byte) and all queried surface fields
 # compare exactly across native x86/x64 and actual production calls observed
 # through a separate fixture executable. Window captures are separately bound.
 for case in range(8):
  t=indexed[('translated',case,0,18,'observed',0)];nc={5:12,6:0,7:14}.get(case,case)
  a,b=[next(r for r in native if r['arch']==arch and r['case']==nc and r['seed']==18)for arch in ['x86','x64']]
  ta=[v for v in observations(t,'backbuffer')if '-after-'in v['tag']]
  for expected in [a,b]:
   ea=observations(expected,'backbuffer')[1:];assert len(ea)==len(ta)
   for e,v in zip(ea,ta):assert {k:x for k,x in e.items()if k!='tag'}=={k:x for k,x in v.items()if k!='tag'}
   for e,v in zip(observations(expected,'window_capture'),observations(t,'window_capture')):assert {k:x for k,x in e.items()if k!='tag'}=={k:x for k,x in v.items()if k!='tag'}
 callback=indexed[('translated',6,0,18,'observed',1)]
 assert len([e for e in events(callback,'gui_callback')if e.get('message')==127])==8
 for n in ['abi_clear','abi_present']:assert guestabi(callback,n)[1:]==guestabi(indexed[('x86',6,0,18,'production',0)],n)[1:]
 # The ignored Count=0/non-NULL pointer is forwarded, rather than accidentally
 # converted to a full clear. Nonblack -> captured exact black is also proved.
 black=indexed[('translated',7,0,18,'observed',0)];assert [c['samples']for c in observations(black,'window_capture')]==[[0x123456]*3,[0]*3]
 code=(RT/'d3d8_device_slots.inc').read_text();assert code.count('unsupported slot ')==90
 for p,h in json.loads((out/'sources.json').read_text()).items():
  if p.startswith('experiments/xrt/runtime/'):assert sha(W/p)==h,p
 result=dict(passed=True,native_oracle_processes=len(native),native_client_processes=sum(r['arch']!='translated'for r in runs),translated_processes=sum(r['arch']=='translated'for r in runs),negative_cases=sum(r['exit']==76 for r in runs),compared_scalar_values=compared,paired_real_translated_render_calls=calls,exact_backbuffer_and_window_comparisons=True,exact_guest_abi_and_live_x87=True,first_present_x86_precision_status_modelled=True,callback_cpu_and_frames_preserved=True,reentrant_mutation_contained=True,all_90_unsupported_methods_guarded=True,real_device_loss_observed=False,genuine_graphical_game_sessions=0,fixture=str(out))
 save(out/'audit.json',result);save(O/'render-audit.json',result);print('CLEAR/PRESENT DIFFERENTIAL PASS',result,flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
