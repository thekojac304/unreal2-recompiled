"""Unchanged initial CreateDevice/render/eight-state assertions, copied before the old endpoint-specific audit."""
import sys
import json
from common import W,legacy
E=legacy().E
PAIRS=[[7,1],[9,2],[29,0],[26,1],[143,1],[48,0],[35,3],[136,1]]

def audit(out):
    sys.path.insert(0,str(W/'tools/xrt'))
    import world_tick_checkpoint as T
    debug=[json.loads(s) for s in (out/'debug-observations.jsonl').read_text().splitlines()]
    events=E.read(out/'runtime-events.json')['events']
    def ds(kind):return [d for d in debug if d['kind']==kind]
    def es(kind):return [d for d in events if d['kind']==kind]
    create=T.paired(es('d3d8_device_call'),es('d3d8_device_return'),32)
    assert len(create)==len(ds('native_entry'))==len(ds('native_return'))==len(ds('bridge_return'))==1
    assert create[0][1]['result']==ds('native_return')[0]['hresult']==ds('bridge_return')[0]['cpu']['registers']['eax']==0
    device=ds('bridge_return')[0]['objects']
    assert create[0][1]['device']==device['guest'] and ds('native_return')[0]['native_device']==device['host']
    assert ds('native_return')[0]['suspended_cpu_unchanged'] and ds('native_return')[0]['guest_frame_unchanged']
    calls=[]
    for method,pop in [('Clear',32),('Present',24)]:
        pairs=T.paired([e for e in es('d3d8_render_call') if e['method']==method],
                       [e for e in es('d3d8_render_return') if e['method']==method],pop)
        ne=[d for d in ds('render_native_entry') if d['method']==method]
        nr=[d for d in ds('render_native_return') if d['method']==method]
        br=[d for d in ds('render_bridge_return') if d['method']==method]
        assert len(pairs)==len(ne)==len(nr)==len(br)==1
        c,r=pairs[0];n=nr[0];b=br[0]
        assert r['result']==n['hresult']==b['cpu']['registers']['eax']==0
        assert r['last_error']==n['last_error'] and n['suspended_cpu_unchanged'] and n['guest_frame_unchanged']
        assert ne[0]['arguments']['device']==b['objects']['host']==device['host']
        assert c['this']==r['this']==b['objects']['guest']==device['guest']
        entry=ds('render_'+method+'_entry')[0]['cpu'];after=b['cpu']
        assert entry['flags']==after['flags']
        assert all(entry['registers'][n]==after['registers'][n] for n in ['ebx','ebp','esi','edi'])
        assert after['registers']['esp']==entry['registers']['esp']+pop and after['rv']==r['actual_return']==c['return']
        assert all(entry['x87'][n]==after['x87'][n] for n in ['register_bits','values','top','fcw'])
        assert after['x87']['fsw']==entry['x87']['fsw']|(0x20 if method=='Present' else 0)
        assert all(ne[0]['host']['registers'][reg]==n['host']['registers'][reg] for reg in ['rbx','rbp','rsi','rdi','r12','r13','r14','r15'])
        assert bytes.fromhex(ne[0]['host']['fxsave'])[256:416]==bytes.fromhex(n['host']['fxsave'])[256:416]
        calls.append(dict(method=method,hresult=n['hresult'],last_error=n['last_error'],call=c,returned=r))
    pairs=T.paired(es('d3d8_state_call'),es('d3d8_state_return'),16)
    assert len(pairs)==len(ds('state_entry'))==len(ds('state_native_entry'))==len(ds('state_native_return'))==len(ds('state_bridge_return'))==8
    assert [[c['state'],c['value']] for c,r in pairs]==PAIRS
    for i,(c,r) in enumerate(pairs):
        entry,native,returned,bridge=[ds(kind)[i] for kind in ['state_entry','state_native_entry','state_native_return','state_bridge_return']]
        a,b=entry['cpu'],bridge['cpu']
        assert r['result']==returned['hresult']==b['registers']['eax']==0 and r['last_error']==returned['last_error']
        assert a['x87']==b['x87'] and a['flags']==b['flags']
        assert all(a['registers'][n]==b['registers'][n] for n in ['ebx','ebp','esi','edi'])
        assert b['registers']['esp']==a['registers']['esp']+16 and b['rv']==r['actual_return']==c['return']
        assert returned['suspended_cpu_unchanged'] and returned['guest_frame_unchanged']
        assert native['arguments']==dict(device=device['host'],state=c['state'],value=c['value'])
        assert entry['objects']['guest']==bridge['objects']['guest']==device['guest']
        assert entry['objects']['host']==bridge['objects']['host']==device['host']
        assert all(native['host']['registers'][n]==returned['host']['registers'][n] for n in ['rbx','rbp','rsi','rdi','r12','r13','r14','r15'])
        assert bytes.fromhex(native['host']['fxsave'])[256:416]==bytes.fromhex(returned['host']['fxsave'])[256:416]
        assert native['host']['mxcsr']==returned['host']['mxcsr']
        calls.append(dict(method='SetRenderState',state=c['state'],value=c['value'],hresult=returned['hresult'],last_error=returned['last_error'],call=c,returned=r))
    E.save(out/'retained-initialization-audit.json',dict(passed=True,device_identity=device,calls=calls,strict_native_x86_compatibility='FAILED retained'))
