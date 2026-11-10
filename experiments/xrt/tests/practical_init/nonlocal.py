"""Actual translated EH and explicit guest ExitThread, native x86 oracles."""
import sys,uuid,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from reader import decode
from supervisor import fixture
from supervisor.windows import FilePins


def build_host(out,dll,module):
    h=helper(out);env=h.env();gen=out/'gen'
    h.run([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',dll,'--out',gen],'lift')
    src=(W/'tools/xrt/tests/ehprobe/xrt_probe_host.c').read_text().replace('xrt_mod_ehprobe','xrt_mod_'+module)
    src=src.replace('xrt_fatal(c, XRT_EXIT_UNSUPPORTED, "test harness: unexpected DLL thread notification %u", reason);',
        'if(reason!=2&&reason!=3)xrt_fatal(c,76,"unexpected notification");')
    src=src.replace('    xrt_events_init();','    xm_init(getenv("XRT_MONITOR_STREAM"));\n    xrt_events_init();')
    src=src.replace('    xrt_cleanup_atoms();','''    xrt_baton_release();
    for(i=1;i<xrt_thread_count();i++){XrtThread*child=xrt_thread_get(i);DWORD start=GetTickCount();
      while(child->state!=2 && GetTickCount()-start<10000)Sleep(1);
      if(child->state!=2)return 19;}
    xrt_baton_acquire();
    xm_scope(c,XM_BEGIN,XM_ADAPTER,"owned.cleanup",0);
    xrt_cleanup_atoms();
    xm_scope(c,XM_END,XM_ADAPTER,"owned.cleanup",0);''')
    src=src.replace('    xrt_report_write(0, "exited");','    xrt_report_write(0, "exited");xm_close();')
    (out/'host.c').write_text(src);td=out/'translated';td.mkdir()
    h.run(['ml64','/nologo','/c',f'/Fo{td}/monitor_asm.obj',RT/'monitor.asm'],'asm',environment=env)
    names=['hle_kernel32.c','hle_misc.c','hle_msvcr70.c','hle_gui.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c','monitor.c']
    exe=td/'translated.exe'
    h.run(['cl','/nologo','/std:c11','/O2','/Zi','/fp:strict','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{RT}',f'/Fo{td}/',f'/Fd{td}/compile.pdb',f'/Fe{exe}',out/'host.c',*sorted(gen.glob('*.c')),*[RT/n for n in names],H.parent/'common/xrt_test_stubs.c',td/'monitor_asm.obj','winmm.lib','advapi32.lib','ole32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000'],'translated-build',environment=env,timeout=120)
    return exe


def run(out,case,cmd,allowed=(),expected=0,trace=False,extra_env=None):
    d=out/case;d.mkdir();sb=d/'sandbox';sb.mkdir();probe=fixture.Probe(d,sb,case)
    probe.allowed_modules=[str(cmd[0]),*map(str,allowed)];env=fixture.environment(sb)
    if trace:env['XRT_MONITOR_STREAM']=str(d/'trace.bin')
    env.update(extra_env or {})
    with FilePins() as pins:
        for p in [cmd[0],*allowed]:pins.pin(p,core.sha(p))
        with (d/'stdout.txt').open('xb') as stdout,(d/'stderr.txt').open('xb') as stderr:
            p=probe.run(list(map(str,cmd)),cwd=sb,env=env,stdout=stdout,stderr=stderr,timeout=60)
    core.require(p.returncode==expected and probe.cleanup['passed'],case+' failed '+str(p.returncode))
    return d,(d/'stdout.txt').read_text(),probe.cleanup


def eh():
    out=O/('exceptions-'+str(uuid.uuid4()));out.mkdir();h=helper(out)
    dll=out/'ehprobe.dll';shutil.copy2(W/'experiments/xrt/build/ehprobe/ehprobe.dll',dll)
    crt=out/'msvcr70.dll';shutil.copy2(W/'sandbox_cmp/ehprobe/System/msvcr70.dll',crt)
    native=out/'native.exe';h.run(['cl','/nologo','/O2',f'/Fo{out}/native.obj',f'/Fe{native}',W/'tools/xrt/tests/ehprobe/native_host.c'],'native-build',environment=h.env('x86'))
    translated=build_host(out,dll,'ehprobe')
    positive=['probe_cleanup','probe_rethrow','probe_nested','probe_enclosing','probe_loop','probe_rethrow_callee']
    _,a,_=run(out,'native',[native,out,dll,*positive],[dll,crt])
    d,b,cleanup=run(out,'translated-run',[translated,dll,out/'report.json',*positive],trace=True)
    core.require(a==b,'native/translated EH event order')
    rows,valid=decode(d/'trace.bin');core.require(valid['aborted_invocations']>0,'no actual nonlocal scopes')
    negatives=[]
    for name in ['probe_neg_unhandled','probe_neg_catch_by_value']:
        q,_,cl=run(out,name,[translated,dll,out/(name+'.json'),name],expected=76,trace=True)
        try:decode(q/'trace.bin')
        except ValueError as e:negatives.append(dict(case=name,rejection=str(e),cleanup=cl))
        else:raise AssertionError('fatal EH stream falsely complete')
    save(O/'exceptions.json',dict(passed=True,root=str(out),oracle=a,integrity=valid,negative=negatives,cleanup=cleanup,runtime=core.tree(RT),generated_pad_abi_changed=False))
    print('Actual translated EH / native x86 event order / nonlocal scope cleanup PASS',flush=True)


def dmusic():
    out=O/('dmusic-'+str(uuid.uuid4()));out.mkdir();h=helper(out);e32=h.env('x86')
    dll=out/'comprobe.dll'
    h.run(['cl','/nologo','/c','/O2','/GS-',f'/Fo{out}/comprobe.obj',H.parent/'directmusic_boundary/comprobe.c'],'probe',environment=e32)
    h.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{dll}',out/'comprobe.obj','kernel32.lib','ole32.lib','uuid.lib'],'dll',environment=e32)
    native=out/'native.exe';h.run(['cl','/nologo','/O2',f'/Fo{out}/native.obj',f'/Fe{native}',W/'tools/xrt/tests/ehprobe/native_host.c'],'native-build',environment=e32)
    translated=build_host(out,dll,'comprobe');results=[]
    for name in ['probe_sta','probe_mta','probe_loader','probe_uninitialized','probe_cleanup','probe_worker']:
        _,a,_=run(out,name+'-native',[native,out,dll,name],[dll])
        d,b,cleanup=run(out,name+'-translated',[translated,dll,out/(name+'.json'),name],trace=True)
        core.require(a==b and name+' returned 0 log ' in b,'native/translated DirectMusic '+name)
        rows,valid=decode(d/'trace.bin')
        native_rows=[r for r in rows if r.domain==2 and r.name.startswith(b'DmLoader8.')]
        core.require(all(r.interface_id==5 and r.slot in (0,1,2) and r.generation>0 for r in native_rows),'DirectMusic receiver identity')
        results.append(dict(case=name,oracle=a,integrity=valid,native_records=len(native_rows),cleanup=cleanup))
    negatives=[]
    for name in ['probe_stale','probe_unsupported','probe_unbalanced','probe_wrong_thread']:
        d,_,cleanup=run(out,name,[translated,dll,out/(name+'.json'),name],expected=76,trace=True)
        try:decode(d/'trace.bin')
        except ValueError as e:negatives.append(dict(case=name,rejection=str(e),cleanup=cleanup))
        else:raise AssertionError('fatal DirectMusic stream falsely complete')
    save(O/'dmusic.json',dict(passed=True,root=str(out),results=results,negatives=negatives,runtime=core.tree(RT),ipc_live_qualified=False))
    print('Actual DirectMusic COM / apartment lifecycle / native x86 oracles PASS',flush=True)


def ipc():
    # Real installed x86 DirectMusic behind the existing guarded helper. This
    # does not qualify all helper COM methods or InitAudio/script callbacks.
    out=O/('ipc-'+str(uuid.uuid4()));out.mkdir()
    data=out/'sandbox-data';data.mkdir();(data/'System').mkdir();(data/'Music').mkdir()
    dll=data/'comprobe.dll';shutil.copy2(W/'experiments/xrt/build/directmusic_com/comprobe.dll',dll)
    helper_exe=W/'experiments/xrt/build/dmusic-ipc/dmusic_helper.exe'
    translated=build_host(out,dll,'comprobe')
    results=[]
    for name in ['probe_loader','probe_cleanup']:
        d,output,cleanup=run(out,name,[translated,dll,out/(name+'.json'),name],allowed=[helper_exe],trace=True,
            extra_env={'XRT_DMUSIC_BACKEND':'ipc','XRT_DMUSIC_HELPER':str(helper_exe)})
        core.require(name+' returned 0 log ' in output,'real IPC guest oracle')
        rows,valid=decode(d/'trace.bin')
        core.require(any(r.name==b'DirectMusic.IPC.connect' and r.event==3 and r.result==1 for r in rows),'actual IPC connect')
        core.require(any(r.name==b'DirectMusic.IPC.exchange' and r.event==3 and r.result==1 for r in rows),'actual IPC exchange')
        core.require({r.name for r in rows}>={b'DirectMusic.IPC.request',b'DirectMusic.IPC.response'},'request/response frame evidence')
        results.append(dict(case=name,oracle=output,integrity=valid,cleanup=cleanup))
    save(O/'ipc.json',dict(passed=True,root=str(out),results=results,runtime=core.tree(RT),helper_sha256=core.sha(helper_exe),
        helper_native_com_trace_qualified=False,script_audio_callback_qualified=False))
    print('Real guarded DirectMusic helper / actual IPC frame pairs / Job cleanup PASS',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
