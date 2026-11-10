"""Acceptance from raw disposable-fixture records. No game entry point."""
import difflib,re,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import phase as P
O,W,B=P.O,P.W,P.B
def main():
    d=O/'oracle';texts=[(d/(n+'.stdout.txt')).read_text() for n in ['x86-messages','x64-messages','positive']]
    assert texts[0]==texts[1]==texts[2]
    t=texts[0];assert t.endswith('cleanup passed\n')
    assert t.count('sample ')==18 and t.count('callback ')==40
    assert t.count('hwnd=1')==40 and 'hwnd=0' not in t
    assert 'focus identity=1 error=00000000 nested=2 result=0 nested_error=00000000' in t
    assert t.count('result=0 error=00001234')==14 and t.count('result=0 error=00005678')==4
    for n in ['x86-messages','x64-messages','positive']:
        e=(d/(n+'.stderr.txt')).read_text();assert e.count('host ABI delta=0 gpr=1 xmm=1 x87=1 mxcsr=1')==18
    r=P.read(d/'positive-report.json');assert r['exit_code']==0 and not r['events_dropped']
    es=r['events'];callbacks=[e for e in es if e['kind']=='gui_get_object_callback_return']
    assert len(callbacks)==14 and all(e['wparam']==0xffffffff and e['object_id']==0xfffffffc and e['result']==0 for e in callbacks)
    assert sum(e['kind']=='fixture_suspended_cpu' for e in es)==18
    assert sum(e['kind']=='fixture_callback_abi' for e in es)==42
    assert 'x86 callback ABI count=42 failures=0' in (d/'positive.stderr.txt').read_text()
    native=[(d/(n+'-native.stdout.txt')).read_text() for n in ['x86','x64']]
    assert native[0]==native[1];assert native[0].count('object=1')==3 and native[0].count('release 1 window_alive=1')==3
    assert native[0].count('role=00000000,3,10 state=00000000,3,1081344 children=00000000,0 window=00000000,1')==3
    guards={}
    for case in ['object','wparam','upper','upperwp','nonzero','ansi','accessibility','queryclass','uia','mutated','message','unregistered']:
        r=P.read(d/(case+'-report.json'));assert r['exit_code']==76 and not r['events_dropped']
        fatal=next(e for e in r['events'] if e['kind']=='fatal');guards[case]=fatal['message']
        if case not in ['nonzero','mutated']:assert not any(e['kind']=='gui_get_object_callback_return' for e in r['events']) or case=='accessibility'
    assert 'wp=0 lp=fffffffffffffff4' in guards['accessibility'] and guards['accessibility']==guards['queryclass']
    access=P.read(d/'accessibility-report.json')['events'];assert len([e for e in access if e['kind']=='gui_get_object_callback_return'])==1
    assert 'nonzero registered WNDPROC' in guards['nonzero']
    assert 'no validated callback frame' in guards['mutated']
    assert 'pointer message 0xd' in guards['message']
    assert P.read(O/'qualified/baseline-report.json')['exit_code']==76
    observed=P.read(O/'observed/positive-report.json');assert observed['exit_code']==0 and not observed['events_dropped']
    assert (O/'observed/positive.stdout.txt').read_text()==t
    defaults=[e for e in observed['events'] if e['kind']=='fixture_real_default'];assert len(defaults)==14
    assert all(e['result']==0 and e['wparam64']==0xffffffff for e in defaults)
    assert {e['lparam64'] for e in defaults}=={0xfffffffc,0xfffffffffffffffc}
    patches=[]
    for name in ['hle_gui.c','hle_gui_classes.inc']:
        before=(O/'source-before/experiments/xrt/runtime'/name).read_text();after=(W/'experiments/xrt/runtime'/name).read_text()
        patches.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=name+' before',tofile=name+' after'))
    (O/'implementation.patch').write_text(''.join(patches))
    P.save(O/'fixture-audit.json',dict(passed=True,message_samples_per_arch=18,callback_records_per_arch=40,
        native_x86_x64_translated_equal=True,host_ABI_checks_each=18,guest_callback_ABI_FPU_checks=42,suspended_CPU_full_equality_checks=18,
        focus_nested_requests=2,focus_nesting='Host test-only WH_CBT hook injects requests inside real SetFocus; OS spontaneous request not claimed',
        default_windows_calls_observed=14,last_error_seeds=[0x1234,0x5678],HWND_identity=True,
        object_id_representations=['0x00000000fffffffc','0xfffffffffffffffc'],
        native_accessibility=dict(queries_each=3,S_OK=True,real_IAccessible=True,role=10,state=1081344,children=0,HWND_identity=True,released=True),
        translated_accessibility='OBJID_CLIENT callback/default return 0, then intentionally stop at preserved OBJID_QUERYCLASSNAMEIDX guard during real AccessibleObjectFromWindow; no successful acquisition claimed',
        guards=guards,dialog_protocol_separate=True,events_dropped=0,genuine_sessions=0))
    print('REGISTERED WINDOW / REAL DEFAULT / ABI / FPU / FOCUS / ACCESSIBILITY GUARDS PASS')
if __name__=='__main__':main()
