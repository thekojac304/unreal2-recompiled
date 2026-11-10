"""Owned native x86 and translated multithread guest fixture under Jobs."""
import sys,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode
from supervisor import fixture
from supervisor.windows import FilePins
def main():
    out=O/('guest-threads-'+str(uuid.uuid4()));out.mkdir();h=helper(out);e32=h.env('x86');e64=h.env()
    h.run(['cl','/nologo','/c','/O1','/GS-','/arch:IA32',f'/Fo{out}/probe.obj',H/'threadprobe.c'],'probe',environment=e32)
    dll=out/'threadprobe.dll'
    h.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{dll}',out/'probe.obj','kernel32.lib'],'dll',environment=e32)
    (out/'native.c').write_text('''#include <windows.h>
#include <stdio.h>
int main(int argc,char**argv){HMODULE m=LoadLibraryA(argv[1]);int(*f)(void);DWORD*log;int r;
if(!m)return 2;f=(void*)GetProcAddress(m,"thread_run");log=(void*)GetProcAddress(m,"probe_log");
if(!f||!log)return 3;r=f();printf("thread_run returned %d log %d %d %d\\n",r,log[0],log[1],log[2]);return r==3?0:4;}
''')
    h.run(['cl','/nologo','/O1',f'/Fo{out}/native.obj',f'/Fe{out}/native.exe',out/'native.c'],'native-build',environment=e32)
    gen=out/'gen';h.run([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',dll,'--out',gen],'lift')
    src=(W/'tools/xrt/tests/ehprobe/xrt_probe_host.c').read_text().replace('xrt_mod_ehprobe','xrt_mod_threadprobe')
    src=src.replace('xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: unexpected DLL thread notification %u", reason);',
        '/* Owned /NOENTRY module has no DllMain. */\n    if(reason!=2&&reason!=3)xrt_fatal(c,76,"unexpected notification");')
    src=src.replace('    xrt_events_init();','    xm_init(getenv("XRT_MONITOR_STREAM"));\n    xrt_events_init();')
    src=src.replace('    xrt_cleanup_atoms();','''    xrt_baton_release();
    for(i=1;i<xrt_thread_count();i++){XrtThread*child=xrt_thread_get(i);DWORD start=GetTickCount();
        /* Guest already closed its public HANDLE; wait on runtime's volatile
         * state, published after callback completion and COM cleanup. */
        while(child->state!=2 && GetTickCount()-start<10000)Sleep(1);
        if(child->state!=2)return 19;}
    xrt_cleanup_atoms();''')
    src=src.replace('    xrt_report_write(0, "exited");','    xrt_report_write(0, "exited");xm_close();')
    (out/'host.c').write_text(src);td=out/'translated';td.mkdir()
    h.run(['ml64','/nologo','/c',f'/Fo{td}/monitor_asm.obj',RT/'monitor.asm'],'asm',environment=e64)
    names=['hle_kernel32.c','hle_misc.c','hle_msvcr70.c','hle_gui.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c','monitor.c']
    h.run(['cl','/nologo','/std:c11','/O2','/Zi','/fp:strict','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{RT}',f'/Fo{td}/',f'/Fd{td}/compile.pdb',f'/Fe{td}/translated.exe',out/'host.c',*sorted(gen.glob('*.c')),*[RT/n for n in names],H.parent/'common/xrt_test_stubs.c',td/'monitor_asm.obj','winmm.lib','advapi32.lib','ole32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000'],'translated-build',environment=e64,timeout=120)
    results=[]
    for variant,cmd in [('native',[out/'native.exe',dll]),('translated',[td/'translated.exe',dll,out/'report.json','thread_run'])]:
        d=out/variant if variant=='native' else out/'translated-run';d.mkdir();sandbox=d/'sandbox';sandbox.mkdir()
        probe=fixture.Probe(d,sandbox,variant);probe.allowed_modules=[str(cmd[0]),str(dll)]
        env=fixture.environment(sandbox);env['XRT_MONITOR_STREAM']=str(d/'trace.bin')
        with FilePins() as pins:
            pins.pin(cmd[0],core.sha(cmd[0]));pins.pin(dll,core.sha(dll))
            with (d/'stdout.txt').open('xb') as stdout,(d/'stderr.txt').open('xb') as stderr:
                p=probe.run(list(map(str,cmd)),cwd=sandbox,env=env,stdout=stdout,stderr=stderr,timeout=30)
        core.require(p.returncode==0 and probe.cleanup['passed'],'owned '+variant+' fixture failed')
        results.append((d/'stdout.txt').read_text().strip())
    core.require(results[0]==results[1]=='thread_run returned 3 log 48 49 50','native/translated oracle')
    rows,valid=decode(out/'translated-run/trace.bin')
    cpus={r.thread for r in rows if r.cpu_size};core.require(len(cpus)==4,'four actual guest CPU threads')
    core.require(valid['aborted_invocations']==2,'ExitThread must abort import and guest callback scopes')
    save(O/'guest-threads.json',dict(passed=True,root=str(out),oracles=results,integrity=valid,guest_threads=len(cpus),
        actual_runtime_thread_create=True,cooperative_guest_baton_preserved=True,runtime=core.tree(RT)))
    print('Four actual translated guest threads / native x86 oracle PASS',flush=True)
if __name__=='__main__':main()
