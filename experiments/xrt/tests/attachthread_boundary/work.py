"""Disposable non-game import characterization and an isolated runtime patch."""
from pathlib import Path
import difflib
import json
import shutil
import sys
import uuid
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[4]
H=Path(__file__).resolve().parent
O=W/'out/recovery/attachthread-setres-20261029-01'
OLD=W/'out/recovery/renderer-gamma-integration-20261029-01'
RT=O/'runtime'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core
from supervisor.environment import load


def stage():
    core.require((O/'preservation.json').is_file(),'preserve first')
    shutil.copytree(OLD/'runtime',RT)
    p=RT/'hle_gui.c';before=p.read_text();text=before
    anchor='static void hle_GetFocus(CPU* c)'
    core.require(text.count(anchor)==1,'GUI insertion anchor')
    text=text.replace(anchor,(H/'bridge.inc').read_text()+'\n'+anchor)
    anchor='{"user32.dll", "GetFocus", hle_GetFocus},'
    core.require(text.count(anchor)==1,'import table anchor')
    text=text.replace(anchor,'{"user32.dll", "AttachThreadInput", hle_AttachThreadInput},\n                              '+anchor)
    p.write_text(text)
    (O/'runtime.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='consumed/hle_gui.c',tofile='fresh/hle_gui.c')))
    core.atomic(O/'integration-source.json',dict(passed=True,runtime=core.tree(RT),changed_files=['hle_gui.c'],
        narrow_scope='current living self-thread pair only; real AttachThreadInput BOOL/error; no pointer arguments',genuine_launches=0))
    print('Staged one guarded USER32 import; production and renderer sources unchanged',flush=True)


def fixtures():
    out=O/('fixtures-'+str(uuid.uuid4()));out.mkdir()
    f=load('attach_fixture_tools',H.parent/'getobject_boundary/phase.py');f.O=out
    x86=out/'x86';x86.mkdir();e=f.env('x86')
    f.run(['cl','/nologo','/c','/O2','/GS-','/W4',f'/Fo{x86}/',H/'probe.c'],'x86-probe',environment=e)
    dll=x86/'attachprobe.dll'
    f.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000',f'/OUT:{dll}',x86/'probe.obj','user32.lib','kernel32.lib'],'x86-dll',environment=e)
    f.run(['cl','/nologo','/O1','/W4',f'/Fo{x86}/',f'/Fe{x86}/native.exe',H/'native.c','user32.lib'],'x86-host',environment=e)
    for mode in ('noqueue','queue','unknown','zero','different'):
        f.run([x86/'native.exe',dll,mode],'native-'+mode,timeout=20)
    gen=out/'gen'
    f.run([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',dll,'--out',gen],'lift')
    d=out/'translated';d.mkdir();e=f.env()
    names=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    cmd=['cl','/nologo','/O1','/Zi','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW',f'/I{RT}',f'/Fo{d}/',f'/Fd{d}/compile.pdb',f'/Fe{d}/translated.exe',H/'host.c',*sorted(gen.glob('*.c')),*[RT/n for n in names],H/'../common/xrt_test_stubs.c','winmm.lib','advapi32.lib','ole32.lib','oleacc.lib','oleaut32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000']
    f.run(cmd,'translated-build',environment=e,timeout=180)
    cases=[]
    for mode in ('noqueue','queue','unknown','zero','different','mismatch','expired','no-thread'):
        positive=mode in ('noqueue','queue');report=out/(mode+'-report.json')
        f.run([d/'translated.exe',dll,mode,report],'translated-'+mode,expected=0 if positive else 76,timeout=20)
        data=core.read_large(report);core.require(data['events_dropped']==0,'dropped events')
        calls=[x for x in data['events'] if x['kind']=='gui_attach_thread_input_call']
        returns=[x for x in data['events'] if x['kind']=='gui_attach_thread_input_return']
        if positive:
            core.require((out/('translated-'+mode+'.stdout.txt')).read_bytes()==(out/('native-'+mode+'.stdout.txt')).read_bytes(),'native/translated mismatch')
            core.require(len(calls)==len(returns)==12,'paired call count')
            for a,b in zip(calls,returns):
                core.require(b['result']==0 and b['last_error']==87 and b['esp_before']==a['esp'] and b['esp_after']==a['esp']+16 and b['actual_return']==a['return'],'native failure/stdcall semantics')
        else:
            core.require(len(calls)==1 and not returns and any(x['kind']=='fatal' and 'self-thread pair' in x['message'] for x in data['events']),'guard did not stop before USER32')
        cases.append(dict(mode=mode,passed=True,positive=positive,calls=len(calls),returns=len(returns)))
    core.atomic(out/'result.json',dict(passed=True,cases=cases,positive_calls=24,negative_guards=6,actual_x86_bytes_lifted=True,genuine_launches=0))
    core.atomic(O/'fixture-validation.json',dict(passed=True,root=str(out),result=core.read_large(out/'result.json'),
        sources={str(p):core.sha(p) for p in [H/'probe.c',H/'native.c',H/'host.c',H/'driver.h',H/'bridge.inc']},runtime=core.tree(RT)))
    print('Actual x86/native and lifted import ABI, error and keyboard-state comparisons PASS; six guards PASS',flush=True)


def regressions():
    p=load('attach_gui_regressions',H.parent/'renderer_prerequisites/phase.py')
    p.O=O;p.RT=RT
    for name in ('configuration-profile.json','resize-local.json','physical-gamma-audit.json','actual-gamma-ramp.bin','actual-gamma-input.json'):
        shutil.copy2(OLD/name,O/name)
    p.regressions();p.gui()
    core.atomic(O/'focused-regressions.json',dict(passed=True,gui=core.read_large(O/'gui-regressions.json'),
        registered_callbacks=core.read_large(O/'focused-gui-regressions.json'),
        renderer_sources_identical={n:core.sha(RT/n)==core.sha(OLD/'runtime'/n) for n in core.tree(RT) if n!='hle_gui.c'},genuine_launches=0))


def build():
    core.require(core.read_large(O/'fixture-validation.json')['passed'] and core.read_large(O/'focused-regressions.json')['passed'],'focused acceptance incomplete')
    before=core.read_large(OLD/'build.json');previous=Path(before['root'])
    core.require(core.tree(previous)==before['outputs'] and core.tree(W/'experiments/xrt/gen')==before['generated'],'prior object/generated identity')
    target=W/'experiments/xrt/build/attachthread-setres-20261029-01'/str(uuid.uuid4());target.mkdir(parents=True)
    helper=load('attach_candidate_tools',H.parent/'getobject_boundary/phase.py');helper.O=O/'client-build';helper.O.mkdir();env=helper.env()
    origin=core.read_large(OLD/'object-lineage.json');lineage={};copied={};commands=[]
    for rel,row in origin.items():
        if rel=='obj/rt/hle_gui.obj':continue
        core.require(core.sha(previous/rel)==row['object_sha256'] and core.sha(row['source'])==row['source_sha256'],'inherited object/source')
        for name,digest in row.get('verified_local_headers',{}).items():core.require(core.sha(name)==digest,'inherited header')
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest)
        copied[rel]=core.sha(dest)
        lineage[rel]=dict(row,reused=True,reused_in_this_candidate=True,inherited_from=str(OLD/'object-lineage.json'))
    for row in before['commands']:
        cmd=row['command'];link=Path(cmd[0]).name.lower()=='link.exe'
        if not link and not any('hle_gui.obj' in s for s in cmd):continue
        cmd=[s.replace(str(previous),str(target)).replace(str(OLD/'runtime'),str(RT)) for s in cmd]
        if link:
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)));name='link'
        else:
            obj=Path(next(s[3:] for s in cmd if s.startswith('/Fo')));obj.parent.mkdir(parents=True,exist_ok=True);name='hle_gui'
        helper.run(cmd,name,cwd=W/'experiments/xrt',environment=env,timeout=180)
        commands.append(core.read(helper.O/(name+'.json')))
        if not link:
            source=RT/'hle_gui.c'
            headers={str(RT/n):core.sha(RT/n) for n in core.tree(RT) if n.endswith(('.h','.inc'))}
            lineage['obj/rt/hle_gui.obj']=dict(source=str(source),source_sha256=core.sha(source),object_sha256=core.sha(obj),command=cmd,
                reused=False,reused_in_this_candidate=False,verified_local_headers=headers)
    core.require(len(copied)==278 and len(lineage)==279,'object census')
    core.atomic(O/'object-lineage.json',lineage)
    core.atomic(O/'build.json',dict(passed=True,root=str(target),outputs=core.tree(target),runtime_root=str(RT),runtime=core.tree(RT),generated=before['generated'],
        binary_sha256=core.sha(target/'xrt_ucc.exe'),pdb_sha256=core.sha(target/'xrt_ucc.pdb'),compiled_objects=1,reused_objects=278,reused_object_hashes=copied,
        commands=commands,inherited_build=str(OLD/'build.json'),inherited_build_sha256=core.sha(OLD/'build.json'),toolchain=before['toolchain'],
        gamma_profile=before['gamma_profile'],configuration_caps_profile_bound=True,gamma_qualified=True,genuine_launches=0,execution_authorized=False))
    print('Fresh unexecuted candidate linked from one corrected GUI object and 278 verified inherited objects',flush=True)


if __name__=='__main__':globals()[sys.argv[1]]()
