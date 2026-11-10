"""Actual new material observer branches on a disposable translated fixture.

Only initialization and terminal-sentinel selection are fixture adapters.
Material entry/native entry/native return/bridge return/update are production.
"""
import ctypes as C
from ctypes import wintypes as T
import json,os,sys,uuid
from pathlib import Path
from types import MethodType
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[4];O=W/'out/recovery/d3d8-material-20261029-01'
sys.path.insert(0,str(O/'enforcement'))
from supervisor import core,observer_checks,fixture

def main():
    out=O/('live-material-observer-'+uuid.uuid4().hex[:8]);out.mkdir()
    exe=O/'fixtures-v4/production/translated.exe';dll=O/'fixtures-v4/x86/d3dprobe.dll'
    capture,plan,checks=observer_checks.prepare(out,exe,stop_symbol='xrt_report_write')
    baseline=core.read_large(O/'fixtures-v4/client-translated-production-0-0-18-0/result.json')
    entries=[e for e in baseline['events']if e['kind']=='d3d8_material_call'];assert len(entries)==4
    plan['guest_stop']=entries[0]['return']
    d=C.WinDLL('dbghelp',use_last_error=True)
    from supervisor.environment import load
    legacy=load('material_live_helpers',Path(observer_checks.__file__).with_name('bounded_material.py'));api=legacy.D.api
    h=api(legacy.D.K,'GetCurrentProcess',[],T.HANDLE)();api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    assert api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False)
    base=api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0)
    s=legacy.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
    assert api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(legacy.D.Symbol)])(h,b'd8_device_SetMaterial',C.byref(s))
    capture.syms['d8_device_SetMaterial']=dict(rva=s.Address-base,size=s.Size)
    assert api(d,'SymCleanup',[T.HANDLE])(h)
    original_hit=capture.hit
    def on_create(self,ev):
        assert self.mem(self.base+plan['stop_rva'],len(bytes.fromhex(plan['stop_bytes'])))==bytes.fromhex(plan['stop_bytes'])
        self.breakpoints={self.sym('d8_device_SetMaterial'):'material_entry',self.sym('xrt_fatal'):'fatal_entry'}
    def hit(self,tag,ctx,tid):
        if tag!='hard_stop_0696f323':return original_hit(tag,ctx,tid)
        assert len([r for r in self.rows if r['kind']=='material_bridge_return'])==1
        self.snapshot_events();self.log('fixture_terminal_stop',instruction_executed=False,production_genuine_stop_registers_not_claimed=True)
        self.stop_requested=True
    capture.on_create=MethodType(on_create,capture);capture.hit=MethodType(hit,capture)
    sandbox=out/'sandbox';sandbox.mkdir();env=fixture.environment(sandbox);env['XRT_EVENT_STREAM']=str(out/'stream.raw.bin')
    sys.path.insert(0,str(W/'tools/xrt'));import graphics_backend as G
    G.environment(env,out);env['XRT_D3D8_DIR']=str(G.verified_pair('x64'))
    capture.allowed_modules += [G.verified_pair('x64')/name for name in G.HASHES['x64']]
    with (out/'stdout.bin').open('xb')as stdout,(out/'stderr.bin').open('xb')as stderr:
        capture.run([str(exe),str(dll),str(out/'FORBIDDEN-report.json'),'0','0','18','0'],cwd=sandbox,env=env,stdout=stdout,stderr=stderr,timeout=15)
    assert capture.terminated_while_stopped and capture.cleanup['passed']and capture.cleanup['remaining_job_processes']==0
    assert not(out/'FORBIDDEN-report.json').exists()
    assert(out/'runtime-events.raw.bin').read_bytes()==(out/'stream.raw.bin').read_bytes()
    def ds(k):return [r for r in capture.rows if r['kind']==k]
    assert all(len(ds(k))==1 for k in ['material_entry','material_native_entry','material_native_return','material_bridge_return'])
    a,b=ds('material_entry')[0],ds('material_bridge_return')[0]
    assert a['cpu']['x87']==b['cpu']['x87']and a['cpu']['flags']==b['cpu']['flags']
    assert b['cpu']['rv']==entries[0]['return']and b['cpu']['registers']['esp']==a['cpu']['registers']['esp']+12
    assert all(a['cpu']['registers'][k]==b['cpu']['registers'][k]for k in ['ebx','ebp','esi','edi'])
    assert ds('material_native_return')[0]['hresult']==b['cpu']['registers']['eax']==0
    assert ds('breakpoints_readback')and all(r['permanent_stop_present']for r in ds('breakpoints_readback'))
    core.atomic(out/'result.json',dict(passed=True,actual_production_material_observer_branches=True,permanent_breakpoint_readbacks=len(ds('breakpoints_readback')),
        guest_native_frames_material_cpu_preserved=True,abi_and_identity_verified=True,terminate_before_continue=True,cleanup=capture.cleanup,
        stream_stopped_memory_equal=True,fixture_terminal_sentinel_only=True,genuine_launches=0))
    core.atomic(O/'live-material-observer.json',dict(passed=True,evidence=str(out),result=core.read(out/'result.json')))
    print('LIVE PRODUCTION MATERIAL OBSERVER PASS',flush=True)

if __name__=='__main__':main()
