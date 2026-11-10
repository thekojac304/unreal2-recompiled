"""Real USER32, project-owned native x86/x64 and translated callback bodies."""
import sys,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
def main():
    out=O/('windows-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    source=(H.parent/'queryclass_boundary/probe.c').read_text()
    anchor='    if(msg==WM_GETOBJECT ||'
    extra='''    if(msg==WM_STYLECHANGING || msg==WM_STYLECHANGED){
        STYLESTRUCT*s=(STYLESTRUCT*)lp;
        record(0,h,msg,wp,s->styleOld,s->styleNew);
        if((msg==WM_STYLECHANGING && probe_mode==1)||(msg==WM_STYLECHANGED && probe_mode==2))s->styleNew^=(int)wp==GWL_STYLE?WS_BORDER:WS_EX_CLIENTEDGE;
        SetLastError(error);result=probe_ansi?DefWindowProcA(h,msg,wp,lp):DefWindowProcW(h,msg,wp,lp);
        record(2,h,msg,wp,s->styleOld,s->styleNew);return result;
    }
    if(msg==WM_COMMAND){record(3,h,msg,wp,lp!=0,0);SetLastError(error);}
'''
    source=source.replace(anchor,extra+anchor);(out/'probe.c').write_text(source)
    host=(H.parent/'queryclass_boundary/host.c').read_text().split('#include "driver.h"')[0]
    host=host.replace('#include "../../runtime/hle_gui.c"',f'#include "{RT.as_posix()}/hle_gui.c"').replace('#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"',f'#include "{W.as_posix()}/tools/xrt/tests/ehprobe/xrt_probe_host.c"')
    (out/'host.c').write_text(host+'\n#define GUI_TRANSLATED\n'+(H/'gui_main.inc').read_text())
    native=(H.parent/'queryclass_boundary/native.c').read_text().split('#include "driver.h"')[0]
    (out/'native.c').write_text(native+(H/'gui_main.inc').read_text())
    results=[]
    for arch in ('x86','x64'):
        d=out/arch;d.mkdir();e=h.env(arch)
        h.run(['cl','/nologo','/c','/O2','/GS-','/W4',*(['/arch:IA32'] if arch=='x86' else []),f'/Fo{d}/probe.obj',out/'probe.c'],arch+'-probe',environment=e)
        h.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{d}/viewportprobe.dll',d/'probe.obj','user32.lib','kernel32.lib'],arch+'-dll',environment=e)
        h.run(['cl','/nologo','/O1','/fp:strict','/W4',f'/Fo{d}/native.obj',f'/Fe{d}/native.exe',out/'native.c','user32.lib'],arch+'-build',environment=e)
        p=h.run([d/'native.exe',d/'viewportprobe.dll',out/'unused.json'],arch+'-run',timeout=30);results.append([json.loads(s) for s in p.stdout.splitlines()])
    gen=out/'gen';h.run([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',out/'x86/viewportprobe.dll','--out',gen],'lift')
    td=out/'translated';td.mkdir();e=h.env()
    names=['hle_kernel32.c','hle_misc.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    h.run(['cl','/nologo','/O1','/Zi','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{RT}',f'/Fo{td}/',f'/Fd{td}/compile.pdb',f'/Fe{td}/translated.exe',out/'host.c',*sorted(gen.glob('*.c')),*[RT/n for n in names],H.parent/'common/xrt_test_stubs.c','winmm.lib','advapi32.lib','ole32.lib','oleacc.lib','oleaut32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000'],'translated-build',environment=e,timeout=120)
    p=h.run([td/'translated.exe',out/'x86/viewportprobe.dll',out/'report.json'],'translated-run',timeout=30);results.append([json.loads(s) for s in p.stdout.splitlines()])
    save(out/'comparison.json',dict(results=results,equal=results[0]==results[1]==results[2]))
    assert results[0]==results[1]==results[2]
    report=read(out/'report.json');assert report['exit_code']==0 and not report['events_dropped']
    for case in ('field','identity','readonly','menu','payload','thread','control'):
        h.run([td/'translated.exe',out/'x86/viewportprobe.dll',out/(case+'.json'),case],case+'-negative',expected=76,timeout=30)
    save(O/'windows-contracts.json',dict(passed=True,root=str(out),cases=24,callback_records=sum(r['kind']=='callback' for r in results[0]),negative_cases=7,variants=3,results=results,runtime=core.tree(RT),native_x86_x64_translated_equal=True,graphics=False,genuine_launches=0))
if __name__=='__main__':main()
