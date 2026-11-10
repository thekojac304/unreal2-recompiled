"""Supplement: fnclex between every Clear/Present on one successful device."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from audit import values,guestabi,events,observations
from run import O,RT,W,save,sha
def main(out):
 runs=json.loads((out/'repeated-abi-results.json').read_text());a,b,t,observed=runs
 assert a['arch']=='x86'and b['arch']=='x64'and t['arch']=='translated'and observed['variant']=='observed'
 assert values(a)==values(t)
 for name in ['abi_clear','abi_present']:assert guestabi(a,name)[1:]==guestabi(t,name)[1:]==guestabi(observed,name)[1:]
 # Remove only the explicitly x86-only assembly status words from the x64
 # C probe; its scalar HRESULT/last-error/ownership values compare exactly.
 va,vb=values(a),values(b);assert len(va)==len(vb)==63
 slots=[3+6*i+j for i in range(8)for j in [2,5]]
 assert [v for i,v in enumerate(va)if i not in slots]==[v for i,v in enumerate(vb)if i not in slots]
 assert [va[i]for i in slots]==[0x3000027f,0x3020027f]+[0x3000027f]*14
 native=out/'native-results.json';oracle=json.loads((native if native.exists()else out.parent/'fixture-04/native-results.json').read_text())
 for r in [t,observed]:
  call=events(r,'d3d8_render_call');ret=events(r,'d3d8_render_return');assert len(call)==len(ret)==16
  for i,(c,e)in enumerate(zip(call,ret)):
   assert c['this']==e['this']and c['method']==e['method']and e['result']==0
   assert e['esp_after']-e['esp_before']==(24 if i%2 else 32)
   if i%2:assert e['guest_fsw_after']==(e['guest_fsw_before']|0x20 if i==1 else e['guest_fsw_before'])
  end=events(r,'d3d8_unload')[0];assert not end['d3d8_loaded']and not end['d3d9_loaded']
 expected=next(r for r in oracle if r['arch']=='x86'and r['case']==12 and r['seed']==18)
 assert [e['rgb_fnv64']for e in observations(expected,'window_capture')]==[e['rgb_fnv64']for e in observations(observed,'window_capture')]
 for p,h in json.loads((out/'sources.json').read_text()).items():
  if p.startswith('experiments/xrt/runtime/'):assert sha(W/p)==h
 result=dict(passed=True,processes=4,frames_per_device=8,exact_native_x86_guest_status_words=True,fnclex_between_every_method=True,native_x64_scalar_returns_exact=True,repeated_window_pixels_exact=True,paired_translated_native_calls=32,source_runtime_unchanged=True)
 save(O/'repeated-abi-audit.json',result);print('REPEATED ABI PASS',result,flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
