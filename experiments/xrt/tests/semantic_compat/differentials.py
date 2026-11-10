"""Native/lifted owned Boolean instructions and real USER32 differentials."""
import json
import shutil
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def boolean():
    out=O/('boolean-'+str(uuid.uuid4()));out.mkdir()
    old=H.parent/'renderer_config_diagnosis';prior=Path(read(PRIOR/'boolean-characterization.json')['evidence'])
    shutil.copy2(prior/'original_fragments.inc',out/'original_fragments.inc')
    for name in ('probe.c','native.c','host.c'):shutil.copy2(old/name,out/name)
    (out/'driver.h').write_text('''static int drive(void){
      static const DWORD masks[]={1,2,32,128,0x80000000,0xffffffff},mips[]={0,1,32,0x80000000};
      unsigned i,j,k,l;DWORD seed,wanted;
      for(i=0;i<6;i++)for(j=0;j<2;j++)for(k=0;k<4;k++)for(l=0;l<2;l++){
        seed=l?0x10000000:0;if(!j)seed|=masks[i];wanted=j?(seed|masks[i]):(seed&~masks[i]);
        put(cfg_mask,masks[i]);put(cfg_enable,j);put(cfg_mips,mips[k]);put(cfg_word,seed);call_probe();
        if(get(cfg_word,0)!=wanted || get(cfg_filter,0)!=(mips[k]?(wanted?2u:1u):0u))return 7;
        printf("%lu %lu %lu %lu %lu\\n",masks[i],seed,mips[k],get(cfg_word,0),get(cfg_filter,0));
      }return 0;}
''')
    helper=load('semantic_boolean_build',H.parent/'getobject_boundary/phase.py');helper.O=out;e=helper.env('x86');d=out/'x86';d.mkdir()
    helper.run(['cl','/nologo','/c','/O2','/GS-','/W4',f'/I{out}',f'/Fo{d}/probe.obj',out/'probe.c'],'probe',environment=e)
    helper.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{d}/cfgprobe.dll',d/'probe.obj'],'dll',environment=e)
    helper.run(['cl','/nologo','/O1','/W4',f'/Fo{d}/native.obj',f'/Fe{d}/native.exe',out/'native.c'],'native-build',environment=e)
    native=helper.run([d/'native.exe',d/'cfgprobe.dll'],'native',cwd=out)
    gen=out/'gen';helper.run([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',d/'cfgprobe.dll','--out',gen],'lift')
    td=out/'translated';td.mkdir();e=helper.env();names=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    helper.run(['cl','/nologo','/O1','/Zi','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{RT}',f'/Fo{td}/',f'/Fd{td}/compile.pdb',f'/Fe{td}/translated.exe',out/'host.c',*sorted(gen.glob('*.c')),*[RT/n for n in names],H.parent/'common/xrt_test_stubs.c','winmm.lib','advapi32.lib','ole32.lib','oleacc.lib','oleaut32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000'],'translated-build',environment=e,timeout=120)
    translated=helper.run([td/'translated.exe',d/'cfgprobe.dll',out/'report.json'],'translated',cwd=out)
    assert native.stdout==translated.stdout and len(native.stdout.splitlines())==96
    save(O/'boolean-differential.json',dict(passed=True,root=str(out),cases=96,original_instruction_bytes=True,native_lifted_equal=True,genuine_launches=0))

def gui():
    out=O/('gui-'+str(uuid.uuid4()));out.mkdir();old=W/'experiments/xrt/build/queryclass-20261029-01'
    helper=load('semantic_gui_build',H.parent/'getobject_boundary/phase.py');helper.O=out
    host=(H.parent/'queryclass_boundary/host.c').read_text();host=host[:host.index('#include "driver.h"')]
    host=host.replace('#include "../../runtime/hle_gui.c"',f'#include "{RT.as_posix()}/hle_gui.c"')
    host=host.replace('#include "../../../../tools/xrt/tests/ehprobe/xrt_probe_host.c"',f'#include "{W.as_posix()}/tools/xrt/tests/ehprobe/xrt_probe_host.c"')
    (out/'host.c').write_text(host+'\n#define GUI_TRANSLATED\n'+(H/'gui_main.inc').read_text())
    (out/'native.c').write_text('''#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
static HMODULE mod;static HWND make(const char*p,const char*r,int a){typedef UINT_PTR(*Fn)(void);(void)r;(void)a;mod=LoadLibraryA(p);return mod?(HWND)((Fn)GetProcAddress(mod,"probe_make"))():NULL;}
static BOOL destroy(HWND h){typedef BOOL(*Fn)(void);(void)h;return ((Fn)GetProcAddress(mod,"probe_destroy"))();}
static void finish(void){FreeLibrary(mod);}
'''+(H/'gui_main.inc').read_text())
    rows=[]
    for arch in ('x86','x64'):
        d=out/arch;d.mkdir();e=helper.env(arch)
        helper.run(['cl','/nologo','/O1','/fp:strict','/W3',f'/Fo{d}/native.obj',f'/Fe{d}/native.exe',out/'native.c','user32.lib'],arch+'-build',environment=e)
        p=helper.run([d/'native.exe',old/arch/'viewportprobe.dll',out/'unused.json'],arch+'-run',timeout=30);rows.append([json.loads(s) for s in p.stdout.splitlines()])
    td=out/'translated';td.mkdir();e=helper.env()
    cmd=read(W/'out/recovery/queryclass-20261029-01/initial-translated-build.json')['command']
    cmd=[str(out/'host.c') if Path(s).name=='host.c' else s.replace(str(old/'translated'),str(td)).replace(str(W/'experiments/xrt/runtime'),str(RT)) for s in cmd]
    cmd=[s.replace(str(old/'translated').replace('\\','/'),str(td).replace('\\','/')) for s in cmd]
    helper.run(cmd,'translated-build',environment=e,timeout=120)
    p=helper.run([td/'translated.exe',old/'x86/viewportprobe.dll',out/'report.json'],'translated-run',timeout=30);rows.append([json.loads(s) for s in p.stdout.splitlines()])
    assert rows[0]==rows[1]==rows[2]
    report=read(out/'report.json');assert report['exit_code']==0 and not report['events_dropped']
    helper.run([td/'translated.exe',old/'x86/viewportprobe.dll',out/'negative-report.json','identity'],'identity-negative',timeout=30,expected=76)
    save(O/'gui-differential.json',dict(passed=True,root=str(out),cases=24,move_cases=12,icon_cases=12,variants=3,native_x86_x64_lifted_equal=True,rows=rows[0],invalid_identity_rejected=True,registered_callbacks=True,full_suspended_cpu=True,genuine_launches=0))

if __name__=='__main__':
    assert sys.argv[1:] in (['boolean'],['gui']);globals()[sys.argv[1]]()
