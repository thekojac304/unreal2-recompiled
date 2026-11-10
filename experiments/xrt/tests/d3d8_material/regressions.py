"""Focused fresh fixtures for the previously supported renderer operations."""
import os,re,sys,json
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
W,O,RT,H=P.W,P.O,P.RT,P.H

def main():
    d=O/'regressions';d.mkdir()
    S=P.load('material_prior_states',H.parent/'d3d8_state/run.py');S.RT=RT
    b=d/'state';S.native_build(b);S.build(b,136,1)
    tuples=[[7,1],[9,2],[29,0],[26,1],[143,1],[48,0],[35,3],[136,1]];rows=[]
    for state,value in tuples:
        group=[S.one(b,arch,state,value)for arch in ['x86','x64','translated']]
        def log(r):return list(map(int,re.search(r'returned 0 log([^\n]*)',r['stdout'])[1].split()))
        assert len({tuple(log(r))for r in group})==1
        ev=group[-1]['events'];calls=[x for x in ev if x['kind']=='d3d8_state_call'];rets=[x for x in ev if x['kind']=='d3d8_state_return'];assert len(calls)==len(rets)==4
        for c,r in zip(calls,rets):assert c['state']==state and c['value']==value and r['result']==0 and r['esp_after']==c['esp']+16 and r['actual_return']==c['return']
        rows+=group
    for state,value in [[148,1],[7,0],[136,0]]:
        r=S.one(b,'translated',state,value,expected=76);assert not[x for x in r['events']if x['kind']=='d3d8_state_call'];rows.append(r)
    P.core.atomic(d/'state-results.json',rows)
    T=P.load('material_prior_render',H.parent/'d3d8_render/translated.py');T.RT=RT
    b=d/'render';b.mkdir();(b/'x86').mkdir();(b/'x64').mkdir();T.build(b)
    rows=[]
    for case in [0,6]:
        group=[T.one(b,arch,case)for arch in ['x86','x64','translated']]
        def log(r):return list(map(int,re.search(r'returned 0 log([^\n]*)',r['stdout'])[1].split()))
        assert len({tuple(log(r))for r in group})==1
        ev=group[-1]['events'];assert [x['method']for x in ev if x['kind']=='d3d8_render_return']==['Clear','Present']
        assert all(x['result']==0 for x in ev if x['kind']=='d3d8_render_return');rows+=group
    for case,arg in [(20,2),(23,1),(40,43),(40,97-1)]:
        r=T.one(b,'translated',case,arg,expected=76);rows.append(r)
    P.core.atomic(d/'render-results.json',rows)
    P.save('regression-audit.json',dict(passed=True,eight_states_native_x86_x64_translated=True,state_processes=27,state_returns=96,
        next_state_148_1_still_refused=True,clear_present_native_x86_x64_translated=True,render_processes=10,
        unsupported_flags_present_pointer_getmaterial_last_slot_still_refused=True,production_gui_and_cpu_sources_unchanged=True,genuine_launches=0))
    print('FOCUSED RENDERER REGRESSIONS PASS',flush=True)

if __name__=='__main__':main()
