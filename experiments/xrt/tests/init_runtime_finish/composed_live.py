"""Actual production debugger construction; owned code and runtime trace only."""
import sys,uuid,ctypes as C,json
from ctypes import wintypes as T
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from supervisor import fixture
from supervisor.windows import FilePins
from composition import construct


def resolve(exe,names):
    l=legacy();api=l.D.api;d=C.WinDLL('dbghelp',use_last_error=True);h=api(l.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    core.require(api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False),'symbols init')
    symbols={}
    try:
        base=api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0)
        core.require(base,'symbols load')
        for name in names:
            s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            core.require(api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,name.encode(),C.byref(s)),'symbol '+name)
            symbols[name]=dict(rva=s.Address-base,size=s.Size)
    finally:api(d,'SymCleanup',[T.HANDLE])(h)
    return symbols


if __name__=='__main__':
    # Importlib is required because `nonlocal` is a Python keyword.
    import pefile
    n=load('owned_nonlocal_builder',H/'nonlocal.py')
    out=O/('composed-'+str(uuid.uuid4()));out.mkdir();h=helper(out);env=h.env()
    dll=W/'experiments/xrt/build/directmusic_com/comprobe.dll'
    exe=n.build_host(out,dll,'comprobe');src=(out/'host.c').read_text()
    src=src.replace('int main(int argc, char** argv) {','''extern void owned_invoke(void*,unsigned);
__declspec(noinline) void owned_gate(CPU*c){static volatile unsigned count;count++;(void)c;}
int main(int argc, char** argv) {''')
    src=src.replace('    for (i = 3; i < argc; i++) {','''    xrt_event("owned_composition_start","\\\"owned\\\":true");
    xm_scope(c,XM_BEGIN,XM_ADAPTER,"UGameEngine.Init",0x1098f460);
    owned_gate(c);
    if(getenv("OWNED_FATAL"))xrt_fatal(c,76,"owned composed fatal");
    if(getenv("OWNED_SINK_FAILURE")){extern void xm_qualification_break_sink(void);xm_qualification_break_sink();xm_scope(c,XM_DATA,0,"owned sink failure",0);}
    for (i = 3; i < argc; i++) {''')
    src=src.replace('    xrt_report_write(0, "exited");xm_close();','''    xm_scope(c,XM_END,XM_ADAPTER,"UGameEngine.Init",c->r[EAX]);
    c->rv=0x1090ed5c;owned_invoke(c,0x1090ed5c);
    ExitProcess(92);''')
    (out/'host.c').write_text(src)
    td=out/'composed-build';td.mkdir();asm=H.parent/'integrated_candidate/stop_fixture.asm'
    h.run(['ml64','/nologo','/c','/Zi',f'/Fo{td}/stop.obj',asm],'stop-asm',environment=env)
    h.run(['ml64','/nologo','/c','/Zi',f'/Fo{td}/monitor_asm.obj',RT/'monitor.asm'],'monitor-asm',environment=env)
    # Reuse the exact fully translated fixture compile recipe with fresh outputs.
    recipe=read(out/'translated-build.json')['command'];old=out/'translated';exe=td/'translated.exe'
    recipe=[str(x).replace(str(old),str(td)) for x in recipe]
    recipe.insert(1,'/DXM_QUALIFICATION');recipe.insert(recipe.index('/link'),str(td/'stop.obj'))
    h.run(recipe,'composed-build',environment=env,timeout=120)
    symbols=resolve(exe,['xrt_fatal','xm_failure','xm_pending','xm_committed','owned_gate','owned_stop','events','event_seq','xrt_g'])
    with pefile.PE(str(exe)) as pe:core.require(pe.get_data(symbols['owned_stop']['rva'],3)==b'\x89\x5f\x44','owned exact stop bytes')
    plan=dict(owned_fixture=True,executable=str(exe),sha256=core.sha(exe),symbols=symbols,stop_rva=symbols['owned_stop']['rva'],stop_bytes='895f44')
    results=[]
    for case in ['success','fatal','sink-failure','environment-failure']:
        q=out/case;q.mkdir();sb=q/'sandbox';sb.mkdir();stream=q/'trace.bin';checks=[]
        def environment(tag):
            checks.append(tag)
            if case=='environment-failure' and tag=='before-CreateDevice':raise core.Rejected('owned environment change')
        cap=construct(q,plan,stream,environment);error=None;envrun=fixture.environment(sb);envrun['XRT_MONITOR_STREAM']=str(stream)
        if case=='fatal':envrun['OWNED_FATAL']='1'
        if case=='sink-failure':envrun['OWNED_SINK_FAILURE']='1'
        with FilePins() as pins:
            pins.pin(exe,core.sha(exe));pins.pin(exe.with_suffix('.pdb'),core.sha(exe.with_suffix('.pdb')))
            try:
                with (q/'stdout.txt').open('xb') as stdout,(q/'stderr.txt').open('xb') as stderr:
                    cap.run([str(exe),str(dll),str(q/'report.json'),'probe_worker'],cwd=sb,env=envrun,stdout=stdout,stderr=stderr,timeout=60)
            except (RuntimeError,ValueError) as e:error=str(e)
        core.require(cap.cleanup['passed'] and any(r['kind']=='terminated_before_continue' for r in cap.rows),'composed containment')
        core.require((case=='success' and error is None and cap.terminated_while_stopped) or (case!='success' and error),'composed result '+case+str(error))
        readbacks=[r for r in cap.rows if r['kind']=='composed_all_thread_readback']
        core.require(readbacks and all(len(r['dr'])==4 for r in readbacks),'four critical slots')
        if case=='success':core.require(len({r['tid'] for r in readbacks})>=2,'new guest thread not armed')
        results.append(dict(case=case,error=error,environment_checks=checks,cleanup=cap.cleanup,readbacks=len(readbacks),threads=len({r['tid'] for r in readbacks})))
    save(O/'composition.json',dict(passed=True,root=str(out),results=results,runtime=core.tree(RT),production_factory=True,
        production_policy_changed=False,genuine_activated=False,owned_plan=plan,
        remaining='Actual candidate environment gate and all native differential consumers are not yet qualified for genuine activation.'))
    print('Production debugger + runtime collector / four critical slots / all-thread readback / evidence-first failures PASS',flush=True)
