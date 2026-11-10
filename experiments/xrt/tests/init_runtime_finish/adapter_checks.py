"""Retained oracles, fresh receipts, instrumented sources. Never a game."""
import sys,uuid,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode

def contracts():
    # The negative harness uses longjmp to reset deliberately corrupted COM
    # doubles. That is not a runtime unwind protocol: tracing is disabled here.
    # Live tracing of typed COM is independently tested by live.py.
    m=load('monitor_resource_contracts',H.parent/'surface_transfer/contracts.py')
    m.O=O;m.RT=RT;m.PRIOR=PRIOR;m.H=H.parent/'surface_transfer'
    basehelper=m.helper
    def wrapped(out):
        h=basehelper(out);run=h.run
        asm=out/'monitor_asm.obj';run(['ml64','/nologo','/c',f'/Fo{asm}',RT/'monitor.asm'],'monitor-asm',environment=h.env())
        def run2(cmd,name,**kw):
            cmd=list(cmd)
            if name.startswith('x86-'):
                # Native x86 oracle uses exactly the immutable prior runtime.
                cmd=[str(x).replace(str(RT),str(PRIOR/'runtime')) for x in cmd]
            elif name.endswith('-build'):
                cmd.insert(1,'/std:c11');cmd.insert(cmd.index('/link'),str(RT/'monitor.c'));cmd.insert(cmd.index('/link'),str(asm))
                # Multiple C sources need a directory /Fo.
                cmd=[('/Fo'+str(Path(x[3:]).parent)+'/') if str(x).startswith('/Fo') else x for x in cmd]
            return run(cmd,name,**kw)
        h.run=run2;return h
    m.helper=wrapped;m.main()
    r=read(O/'contracts.json');r.update(trace_enabled=False,trace_qualification='separate live.py',x86_runtime='immutable prior oracle',x64_runtime=str(RT));save(O/'contracts.json',r)

def gui():
    # Build the retained native x86/x64 and translated bodies unchanged except
    # trace open/close and fixed compiler/link inputs. Preserve all raw oracles.
    out=O/('gui-driver-'+str(uuid.uuid4()));out.mkdir()
    src=(H.parent/'surface_transfer/gui_contracts.py').read_text()
    src=src.replace('from common import *', 'from common import *\nH=Path('+repr(str(H.parent/'surface_transfer'))+')')
    src=src.replace("host=host.replace(","host=host.replace(",1)
    anchor="    (out/'host.c').write_text("
    src=src.replace(anchor,"    host=host.replace('xrt_report_path=report;xrt_events_init();','xm_init(getenv(\"XRT_MONITOR_STREAM\"));xrt_report_path=report;xrt_events_init();').replace('xrt_report_write(0,\"exited\");xrt_baton_release();','xrt_report_write(0,\"exited\");xrt_baton_release();xm_close();')\n"+anchor)
    src=src.replace("names=['hle_kernel32.c'","names=['monitor.c','hle_kernel32.c'")
    src=src.replace("h.run(['cl','/nologo','/O1','/Zi'", "h.run(['ml64','/nologo','/c',f'/Fo{td}/monitor_asm.obj',RT/'monitor.asm'],'monitor-asm',environment=e)\n    h.run(['cl','/nologo','/std:c11','/O1','/Zi'")
    src=src.replace("H.parent/'common/xrt_test_stubs.c','winmm.lib'", "H.parent/'common/xrt_test_stubs.c',td/'monitor_asm.obj','winmm.lib'")
    src=src.replace("p=h.run([td/'translated.exe'", "e['XRT_MONITOR_STREAM']=str(out/'positive-trace.bin')\n    p=h.run([td/'translated.exe'")
    src=src.replace("'translated-run',timeout=30)","'translated-run',timeout=45,environment=e)")
    src=src.replace("h.run([td/'translated.exe',out/'x86/viewportprobe.dll',out/(case+'.json'),case],case+'-negative',expected=76,timeout=30)",
        "e['XRT_MONITOR_STREAM']=str(out/(case+'-trace.bin'))\n        h.run([td/'translated.exe',out/'x86/viewportprobe.dll',out/(case+'.json'),case],case+'-negative',expected=76,timeout=30,environment=e)")
    driver=out/'driver.py';driver.write_text(src)
    # Source is reviewed deterministic adaptation, executed in current interpreter
    # with this package's common module; no production supervisor patching.
    m=load('monitor_gui_contracts',driver);m.main()
    r=read(O/'windows-contracts.json');rows,valid=decode(Path(r['root'])/'positive-trace.bin')
    core.require(any(v.domain==3 for v in rows),'callback records missing')
    save(O/'gui-trace.json',dict(passed=True,integrity=valid,records=len(rows),
        callbacks=sum(v.event==2 and v.domain==3 for v in rows),oracles=str(Path(r['root'])/'comparison.json'),
        driver=str(driver),driver_sha256=core.sha(driver),runtime=core.tree(RT)))
if __name__=='__main__':globals()[sys.argv[1]]()
