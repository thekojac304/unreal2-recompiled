"""Live non-game debugger qualification of instance-bound early fatal capture."""
import ctypes as C
from ctypes import wintypes as T
import importlib.util, json, os, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('wm_phase',HERE/'phase.py');F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
S=F.W/'out/recovery/session-aware-136-20261026-01'
sys.path.insert(0,str(S))
from debugger_loop import Loop,D,verify_armed
Evidence=F.load('wm_instance_evidence',HERE/'observer_evidence.py')

def symbols(exe,names):
    d=C.WinDLL('dbghelp',use_last_error=True);api=D.api
    h=api(D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    assert api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False)
    base=api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0)
    assert base
    result={}
    try:
        find=api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(D.Symbol)])
        for name in names:
            sym=D.Symbol();sym.SizeOfStruct=88;sym.MaxNameLen=1023
            assert find(h,name.encode(),C.byref(sym)) and sym.Address,name
            result[name]=dict(rva=sym.Address-base,size=sym.Size)
    finally:assert api(d,'SymCleanup',[T.HANDLE])(h)
    return result

def run():
    out=F.O/'debugger-tests-final';out.mkdir()
    oldlog=F.W/'out/recovery/d3d8-scalar-init-20261025-01/debug-observations.jsonl';oldhash=F.sha(oldlog)
    results=[]
    for case in ['original-three-arguments','current-guard']:
        dest=out/case;dest.mkdir()
        exe=F.B/('translated/translated.exe' if case=='original-three-arguments' else 'qualified-fixture/translated/translated.exe')
        dll=F.B/('x86/getobjectprobe.dll' if case=='original-three-arguments' else 'qualified-fixture/x86/getobjectprobe.dll')
        meta=exe.parent.parent/'gen/getobjectprobe_meta.json'
        assert F.sha(dll)==F.read(meta)['sha256'], 'fixture/lift pair must match before debugger launch'
        syms=symbols(exe,['xrt_fatal','xrt_g','events','event_seq','xrt_report_write'])
        class Probe(Loop,D.Capture):
            def on_create(self,ev):
                # Permanent independent execute stop remains installed alongside
                # fatal capture for every thread and every continue.
                self.breakpoints={self.sym('xrt_fatal'):'fatal_entry',self.sym('xrt_report_write'):'forbidden-report-body'}
            def update(self,ctx,resume=False):
                ctx.arm(list(self.breakpoints),resume)
                actual=D.Context(ctx.thread)
                dr=[C.c_uint64.from_address(actual.ptr+72+8*i).value for i in range(4)]
                assert dr[:2]==list(self.breakpoints) and dr[2:]==[0,0]
                assert C.c_uint64.from_address(actual.ptr+112).value&0xffff00ff==5
                self.log('permanent_stop_readback',addresses=dr,verified=True)
            def hit(self,tag,ctx,tid):
                raise AssertionError('strict delegated hit: '+tag)
            def snapshot_events(self):
                n=self.u64(self.sym('event_seq'));assert 0<n<262144
                data=self.mem(self.u64(self.sym('events')),n*448)
                rows=[json.loads(data[i*448:(i+1)*448].split(b'\0',1)[0]) for i in range(n)]
                assert [r['seq'] for r in rows]==list(range(1,n+1))
                F.save(dest/'events.json',rows)
        probe=Evidence.install(Probe(syms),dest)
        cmd=[str(exe),str(dll),str(dest/'forbidden-report.json')]
        if case=='current-guard':cmd+=['object']
        stopped=False
        with (dest/'host-output.txt').open('wb') as stream:
            try:
                probe.run(cmd,cwd=F.W,env=os.environ.copy(),stdout=stream,stderr=subprocess.STDOUT,timeout=15)
            except RuntimeError as e:
                assert 'fatal before required stop; no continuation:' in str(e);stopped=True
        assert stopped and probe.cpu is None and not (dest/'forbidden-report.json').exists()
        fatal=next(r for r in probe.rows if r['kind']=='fatal_entry')
        expected=dict(message=61,wp=0xffffffff,lp=0xfffffffc if case=='original-three-arguments' else 0xfffffffe)
        assert fatal['decoded_arguments']==expected and fatal['code']==76
        assert fatal['cpu']['pc'] and len(fatal['guest_stack'])==fatal['guest_stack_bounds']['captured_words'] and not fatal['diagnostic_read_errors']
        assert fatal['guest_stack_bounds']['captured_words']==min(40,(fatal['guest_stack_bounds']['high']-fatal['guest_stack_bounds']['esp'])//4)
        assert not fatal['runtime_fatal_body_executed'] and Path(fatal['output_directory'])==dest.resolve()
        assert probe.process_obj.poll() is not None and F.sha(oldlog)==oldhash
        if case=='original-three-arguments':assert fatal['raw_integer_arguments']==[61,0xffffffff,0xfffffffc]
        F.save(dest/'result.json',dict(passed=True,fatal=fatal,process_exit=probe.process_obj.returncode,permanent_stop_preserved=True,game_executed=False))
        results.append(dict(case=case,passed=True))
    # Exercise the original terminate-before-instruction hardware-stop test.
    test=F.load('wm_hardware_selftest',S/'debugger_selftest.py').run(out/'hard-stop')
    assert test['passed'] and test['terminated_before_continue']
    F.save(F.O/'observer-qualified.json',dict(passed=True,live_early_fatal_cases=results,hardware_stop=test,instance_bound_directory=True,
        historical_log_unchanged=F.sha(oldlog)==oldhash,genuine_sessions=0))
    print('LIVE OBSERVER + PERMANENT HARDWARE STOP PASS',flush=True)
if __name__=='__main__':run()
