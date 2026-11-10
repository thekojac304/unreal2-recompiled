"""Native/translated registered-window OBJID_QUERYCLASSNAMEIDX oracle; no game launcher."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
W=H.parents[3]
O=W/'out/recovery/queryclass-20261029-01'
B=W/'experiments/xrt/build/queryclass-20261029-01'


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


P=load('queryclass_fixture_helpers',H/'../viewport_getobject/phase.py')
F=P.F


def setup():
    O.mkdir();B.mkdir();F.O=O;F.B=B;F.HERE=H
    old=W/'out/recovery/viewport-getobject-20261028-01'
    # Preserve exact consumed build, runtime source and existing strict failures.
    build=F.read(old/'build.json');F.check(Path(build['root']),build['outputs'])
    F.save(O/'inherited-build.json',build)
    for name in ['hle_gui.c','hle_gui_classes.inc']:
        shutil.copy2(W/'experiments/xrt/runtime'/name,O/(name+'.before'))
    shutil.copy2(old/'strict-failures-retained.json',O/'strict-failures-retained.json')
    finish_setup()


def finish_setup():
    # The broad older phase checker pins historical documentation; this phase
    # verifies protected asset inputs directly and preserves the current source.
    sys.path.insert(0,str(W/'tools/xrt'));import asset_boundary as A
    old=W/'out/recovery/viewport-getobject-20261028-01'
    F.save(O/'preservation.json',dict(prior_build_sha256=F.sha(old/'build.json'),
        runtime_before=F.tree(W/'experiments/xrt/runtime'),protected_assets=A.verify(),genuine_sessions=0))


def build():
    P.O=O;P.B=B;P.HERE=H;F.O=O;F.B=B;F.HERE=H
    P.native_build();P.translated_build()


def run(stage):
    F.O=O/stage;F.O.mkdir();F.B=B;F.HERE=H
    for arch in ['x86','x64']:
        F.run([B/arch/'native.exe',B/arch/'viewportprobe.dll',F.O/'unused.json','messages'],arch+'-messages',timeout=20)
        F.run([B/arch/'native.exe',B/arch/'viewportprobe.dll',F.O/'unused.json','accessibility'],arch+'-accessibility',timeout=20)
    F.run([B/'translated/translated.exe',B/'x86/viewportprobe.dll',F.O/'messages-report.json','messages'],
          'messages',timeout=20,expected=76 if stage=='baseline' else 0)
    if stage!='baseline':
        F.run([B/'translated/translated.exe',B/'x86/viewportprobe.dll',F.O/'accessibility-report.json','accessibility'],'accessibility',timeout=20)
        for case in ['object','wparam','upper','upperwp','nonzero','ansi','uia','mutated','message','unregistered']:
            F.run([B/'translated/translated.exe',B/'x86/viewportprobe.dll',F.O/(case+'-report.json'),case],case,timeout=20,expected=76)


def audit():
    d=O/'candidate'
    messages=[(d/(n+'.stdout.txt')).read_text() for n in ['x86-messages','x64-messages','messages']]
    assert messages[0]==messages[1]==messages[2]
    assert messages[0].count('sample ')==18 and messages[0].endswith('cleanup passed\n')
    for name in ['x86-messages','x64-messages','messages']:
        assert (d/(name+'.stderr.txt')).read_text().count('host ABI delta=0 gpr=1 xmm=1 x87=1 mxcsr=1')==18
    access=[(d/(n+'.stdout.txt')).read_text() for n in ['x86-accessibility','x64-accessibility','accessibility']]
    assert access[0]==access[1]==access[2]
    assert access[0].count('object=1')==3 and access[0].count('release 1 window_alive=1')==3
    r=F.read(d/'messages-report.json');assert r['exit_code']==0 and not r['events_dropped']
    es=r['events'];defaults=[e for e in es if e['kind']=='fixture_real_default']
    assert len(defaults)==14 and all(e['wparam64']==0 and e['result']==0 for e in defaults)
    assert {e['lparam64'] for e in defaults}=={0xfffffff4,0xfffffffffffffff4}
    assert sum(e['kind']=='fixture_suspended_cpu' and e['passed'] for e in es)==18
    assert all(e['passed'] for e in es if e['kind']=='fixture_callback_abi')
    for report in ['messages-report.json','accessibility-report.json']:
        data=F.read(d/report);assert data['exit_code']==0 and data['events_dropped']==0
    guards={}
    for case in ['object','wparam','upper','upperwp','nonzero','ansi','uia','mutated','message','unregistered']:
        data=F.read(d/(case+'-report.json'));assert data['exit_code']==76 and not data['events_dropped']
        guards[case]=next(e['message'] for e in data['events'] if e['kind']=='fatal')
    F.save(O/'fixture-audit.json',dict(passed=True,messages_per_arch=18,native_x86_x64_translated_equal=True,
        real_default_calls=14,representations=['00000000fffffff4','fffffffffffffff4'],wparam=0,
        nested_callbacks=True,host_ABI_x87_MXCSR=True,guest_callback_ABI_x87=True,suspended_CPU_equality_checks=18,
        real_accessibility_queries_per_arch=3,objects_released=True,guards=guards,genuine_sessions=0))
    print('QUERYCLASS NATIVE / TRANSLATED / REAL ACCESSIBILITY PASS')


def regressions():
    P.O=O;P.B=B;F.O=O;F.B=B
    P.dialog_regression()
    # Original OBJID_CLIENT registered-window matrix with unchanged assertions.
    reg=O/'client-regression';reg.mkdir();target=B/'client-regression';target.mkdir()
    P.O=reg;P.B=target;P.HERE=H/'../viewport_getobject';F.O=reg;F.B=target;F.HERE=P.HERE
    P.native_build();P.translated_build()
    for arch in ['x86','x64']:
        F.run([target/arch/'native.exe',target/arch/'viewportprobe.dll',reg/'unused.json','messages'],arch,timeout=20)
    F.run([target/'translated/translated.exe',target/'x86/viewportprobe.dll',reg/'report.json','messages'],'translated',timeout=20)
    # Established fixture comparison uses text: native MSVCRT emits CRLF while
    # the translated stdout adapter emits LF. Check that this is the sole delta.
    texts=[(reg/(n+'.stdout.txt')).read_bytes().replace(b'\r\n',b'\n') for n in ['x86','x64','translated']]
    assert texts[0]==texts[1]==texts[2]
    F.save(O/'regressions.json',dict(passed=True,dialog_samples=18,dialog_accessibility_queries=3,dialog_guards=4,
        original_registered_client_samples=18,original_client_unchanged=True,genuine_sessions=0))


def finish_regression_audit():
    reg=O/'client-regression'
    texts=[(reg/(n+'.stdout.txt')).read_bytes().replace(b'\r\n',b'\n') for n in ['x86','x64','translated']]
    assert texts[0]==texts[1]==texts[2]
    assert F.read(O/'dialog-regression.json')['passed']
    F.save(O/'regressions.json',dict(passed=True,dialog_samples=18,dialog_accessibility_queries=3,dialog_guards=4,
        original_registered_client_samples=18,original_client_unchanged=True,
        normalization='Only CRLF to LF, identical to the inherited text-mode comparison; all other bytes match',genuine_sessions=0))


def stream_test():
    dest=O/'stream-test';dest.mkdir();target=B/'translated-stream';target.mkdir()
    F.O=dest
    recipe=O/'initial-translated-build.json'
    if not recipe.exists():recipe=O/'translated-build.json'
    cmd=F.read(recipe)['command']
    cmd=[s.replace(str(B/'translated'),str(target)) for s in cmd]
    F.run(cmd,'build',environment=F.env(),timeout=180)
    import os
    for case in ['messages','accessibility','nonzero']:
        environment=dict(os.environ,XRT_EVENT_STREAM=str(dest/(case+'.raw.bin')))
        F.run([target/'translated.exe',B/'x86/viewportprobe.dll',dest/(case+'-report.json'),case],case,
              environment=environment,timeout=20,expected=76 if case=='nonzero' else 0)
        data=(dest/(case+'.raw.bin')).read_bytes();assert len(data)%448==0
        rows=[json.loads(data[i:i+448].split(b'\0',1)[0]) for i in range(0,len(data),448)]
        report=F.read(dest/(case+'-report.json'));assert rows==report['events'] and not report['events_dropped']
    assert (dest/'messages.stdout.txt').read_bytes()==(O/'candidate/messages.stdout.txt').read_bytes()
    F.save(O/'stream-audit.json',dict(passed=True,cases=['messages','accessibility','nonzero'],
        fixed_records_equal_complete_runtime_reports=True,ABI_x87_checks_unchanged=True,genuine_sessions=0))


def dialog_guard():
    F.O=O/'dialog-queryclass-guard';F.O.mkdir();target=B/'dialog-queryclass-guard';target.mkdir()
    cmd=F.read(O/'dialog-regression/translated-build.json')['command']
    old=str(B/'dialog-regression/translated')
    cmd=[str(H/'dialog_guard.c') if Path(s).name=='host.c' else s.replace(old,str(target)) for s in cmd]
    F.run(cmd,'build',environment=F.env(),timeout=180)
    F.run([target/'translated.exe',B/'dialog-regression/x86/getobjectprobe.dll',F.O/'report.json'],'negative',timeout=20,expected=76)
    report=F.read(F.O/'report.json');assert report['exit_code']==76 and not report['events_dropped']
    fatal=next(e for e in report['events'] if e['kind']=='fatal')
    assert 'wp=0 lp=fffffffffffffff4' in fatal['message']
    assert not any(e['kind']=='gui_get_object_callback_return' for e in report['events'])
    F.save(O/'dialog-queryclass-guard.json',dict(passed=True,exit=76,queryclass_dialog_remains_guarded=True,genuine_sessions=0))


def client_build():
    # Fresh runtime objects + explicitly verified, unchanged generated objects.
    # Reuse is recorded; this is not represented as a fresh 279-object compile.
    old=F.read(O/'inherited-build.json');previous=Path(old['root']);F.check(previous,old['outputs'])
    runtime=F.tree(W/'experiments/xrt/runtime');generated=F.tree(W/'experiments/xrt/gen')
    assert generated==old['generated']
    assert {n for n,h in runtime.items() if h!=old['runtime'].get(n)}=={'hle_gui.c','xrt_events.c'}
    target=B/'client';target.mkdir();F.O=O/'client-build';F.O.mkdir();environment=F.env()
    copied={};commands=[]
    for rel,h in old['outputs'].items():
        if rel.endswith('.obj') and not rel.startswith('obj/rt/'):
            source=previous/rel;dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            assert F.sha(dest)==h;copied[rel]=h
    for row in old['commands']:
        original=row['command']
        is_link=Path(original[0]).name.lower()=='link.exe'
        if not is_link and not any('/obj/rt/' in s.replace('\\','/') for s in original):continue
        cmd=[s.replace(str(previous),str(target)) for s in original]
        if is_link:
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
            name='link'
        else:
            obj=Path(next(s[3:] for s in cmd if s.startswith('/Fo')));obj.parent.mkdir(parents=True,exist_ok=True);assert not obj.exists();name=obj.stem
        F.run(cmd,name,cwd=W/'experiments/xrt',environment=environment,timeout=180)
        commands.append(F.read(F.O/(name+'.json')))
    outputs=F.tree(target);assert sum(n.endswith('.obj') for n in outputs)==279
    assert runtime==F.tree(W/'experiments/xrt/runtime') and generated==F.tree(W/'experiments/xrt/gen')
    F.save(O/'build.json',dict(passed=True,root=str(target),outputs=outputs,runtime=runtime,generated=generated,
        binary_sha256=F.sha(target/'xrt_ucc.exe'),pdb_sha256=F.sha(target/'xrt_ucc.pdb'),commands=commands,
        compiled_objects=279-len(copied),reused_objects=len(copied),reused_object_hashes=copied,
        inherited_build_sha256=F.sha(O/'inherited-build.json'),genuine_sessions=0))
    print('IDENTIFIED CLIENT BUILT; NEVER EXECUTED',flush=True)


if __name__=='__main__':
    import re
    args=sys.argv[1:]
    if '--phase' in args:
        index=args.index('--phase');name=args[index+1]
        assert re.fullmatch('[a-z0-9][a-z0-9-]{2,70}',name)
        O=W/'out/recovery'/name;B=W/'experiments/xrt/build'/name
        del args[index:index+2]
    assert args and args[0] in {'setup','finish_setup','build','run','audit','regressions','finish_regression_audit','stream_test','client_build','dialog_guard','all'}
    if args==['all']:
        setup();build();run('candidate');audit();regressions();stream_test();dialog_guard();client_build()
    else:globals()[args[0]](*args[1:])
