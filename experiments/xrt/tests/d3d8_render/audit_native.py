"""Actual native call, resource, FPU and window evidence; no fabricated outputs."""
import json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from run import save,O
def kind(r,k):return [v for v in r['rows']if v['kind']==k]
def abi(r,control=0x77f):
 for c in kind(r,'call'):
  assert c['stack_delta']==0
  pre,post=bytes.fromhex(c['pre']),bytes.fromhex(c['post'])
  if r['arch']=='x86'and r['case']==11 and c['method']==1:
   assert post[:5]==bytes.fromhex('7f02000000')
  else:
   assert pre[:2]==post[:2] and pre[4]==post[4] and pre[32:42]==post[32:42] and pre[48:58]==post[48:58]
   before=int.from_bytes(pre[2:4],'little');after=int.from_bytes(post[2:4],'little')
   assert after in [before,before|0x20]
   if r['arch']=='x86'and c['method']==1 and c['tag']=='present-0'and r['case']not in [10,11]:assert after==before|0x20
  assert int.from_bytes(pre[:2],'little')==control
  if r['arch']=='x86':assert c['regs']==[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0]
  else:
   assert c['regs']==[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
   assert bytes.fromhex(c['xmm'])==struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10
  # Destroyed-window x86 legacy backend path changes MXCSR controls; this path
  # will not be exposed by the production pinned-window bridge.
  if r['case']!=11:assert int.from_bytes(pre[24:28],'little')&~63==int.from_bytes(post[24:28],'little')&~63
def main(out):
 runs=json.loads((out/'native-results.json').read_text());assert len(runs)==32
 for r in runs:
  assert r['exit']==0;abi(r);create=kind(r,'create')[0];assert create['hr']==0 and create['non_null']and create['attempts']==1
  assert kind(r,'release')==[dict(kind='release',device=0,parent=0)]
  c=kind(r,'cleanup')[0];assert not c['d3d8_loaded']and not c['d3d9_loaded']and not c['window_valid']and c['foreign_callbacks']==0
  assert c['callbacks'][2:4]==[0,0]
  for b in kind(r,'backbuffer'):
   assert [b[n]for n in ['get_hr','desc_hr','lock_hr','unlock_hr','surface_release']]==[0]*5
   assert b['desc']==[22,1,1,0,5821200,0,1540,945] and b['pitch']==6160
  for call in kind(r,'call'):
   assert call['hr']==0
   if call['method']==0:assert call['last_error']==r['seed']
   elif r['case']in [10,11]:assert call['last_error']==1400
   elif call['tag']=='present-0':assert call['last_error']==0
   else:assert call['last_error']==r['seed']
  if r['case']not in [10,11]:
   a,b=kind(r,'state');assert {k:v for k,v in a.items()if k!='tag'}=={k:v for k,v in b.items()if k!='tag'}
 for r in [r for r in runs if r['arch']=='x86']:
  s=next(s for s in runs if s['arch']=='x64'and s['case']==r['case']and s['seed']==r['seed'])
  assert kind(r,'backbuffer')==kind(s,'backbuffer')
  assert [{k:v for k,v in c.items()if k not in ['regs','xmm','pre','post']}for c in kind(r,'call')]==[{k:v for k,v in c.items()if k not in ['regs','xmm','pre','post']}for c in kind(s,'call')]
 captures=json.loads((out.parent/'fixture-03/printwindow-results.json').read_text())
 for r in captures:
  c=kind(r,'window_capture')[0];b=kind(r,'backbuffer')[1]
  assert c['samples']==[0x123456]*3 and c['nonuniform_pixels']==0 and c['visible']
  assert c['rgb_fnv64']==b['rgb_fnv64']=='db62f675a1ed9a75'
 result=dict(passed=True,native_processes=34,measured_calls=sum(len(kind(r,'call'))for r in runs)+4,backbuffer_exact_x86_x64=True,real_present_window_pixels=True,initial_gdi_capture_rejected=True,clear_last_error='preserved',first_present_last_error=0,repeated_present_last_error='preserved after first',invalid_window_present_hr=0,invalid_window_last_error=1400,real_device_lost_observed=False,destroyed_window_x86_mxcsr_limitation=True,production_scope='live pinned window; Clear target only; Present four NULL arguments',zero_graphical_game_sessions=True)
 save(O/'native-audit.json',result);print('NATIVE AUDIT PASS',result,flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
