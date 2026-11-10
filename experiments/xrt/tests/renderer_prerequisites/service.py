"""Additive, fixed gamma fixture family for the persistent desktop supervisor.

Original supervisor/collector code and its running authorization are untouched.
Owner console startup is required. No genuine game family is available here.
"""
import argparse
from contextlib import ExitStack
import ctypes as C
import json
import os
from pathlib import Path
import signal
import struct
import sys
import time
import unittest
import uuid

sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import phase as P
from supervisor import core, fixture_profiles as F, development as D, fixture_collector as T
from supervisor.windows import Exclusive,FilePins
from supervisor.service import verify_seal
HOME=P.W/'out/desktop-prerequisites'
FAMILY='renderer-gamma-restoring'
ORIGINAL=(F.parameters,F.recipe_files,F.expected_files,F.plan)


def parameters(family,values,profile):
    if family!=FAMILY:return ORIGINAL[0](family,values,profile)
    core.exact(values,'')
    core.require(profile=='fast-development','prerequisites use disposable development profile')
    return values


def recipe(family,values,root):
    if family!=FAMILY:return ORIGINAL[1](family,values,root)
    src=root/'sources';out=root/'build'
    E,_,_=F.modules()
    rt=src/'runtime'
    frozen=E.P.O/'snapshots/gamma/runtime'
    core.require({p.name for p in rt.iterdir()}=={p.name for p in frozen.iterdir()},'gamma runtime inventory')
    inputs=[src/n for n in ('fixture.c','support.inc','evidence_fixture.h','actual_ramp.inc')]
    inputs+=sorted(rt.glob('*'))
    inputs += [E.P.O/'fixtures'/a/'abi.obj' for a in ('x86','x64')]
    outputs=[out/n/'fixture.exe' for n in ('x86-native','x64-native','x64-translated')]
    outputs += [out/n/'fixture.obj' for n in ('x86-native','x64-native','x64-translated')]
    return inputs,outputs


def files(family,values,root):
    if family!=FAMILY:return ORIGINAL[2](family,values,root)
    inputs,outputs=recipe(family,values,root)
    return sorted(set(inputs+outputs+[root/'build/build-record.json']+
        [p for a in ('x86','x64') for p in P.P.G.verified_pair(a).glob('*.dll')]))


def plan(family,values,candidate=None):
    if family!=FAMILY:return ORIGINAL[3](family,values,candidate)
    return [dict(name=a+'-'+v,arch=a,variant=v,group=8,exe=candidate/'build'/(a+'-'+v)/'fixture.exe')
        for a,v in [('x86','native'),('x64','native'),('x64','translated')]]


def install():
    F.FAMILIES=(*F.FAMILIES,FAMILY)
    F.parameters=parameters;F.recipe_files=recipe;F.expected_files=files;F.plan=plan


class DesktopGamma:
    """Parent owns restoration even after child failure, cancellation or watchdog."""
    def __init__(self,out):self.out=out;self.dcs=[]
    def __enter__(self):
        from ctypes import wintypes as W
        g=C.WinDLL('gdi32',use_last_error=True);self.g=g
        g.CreateDCW.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p];g.CreateDCW.restype=W.HDC
        for name in ('GetDeviceGammaRamp','SetDeviceGammaRamp'):
            f=getattr(g,name);f.argtypes=[W.HDC,C.c_void_p];f.restype=W.BOOL
        g.DeleteDC.argtypes=[W.HDC];g.DeleteDC.restype=W.BOOL
        # The qualified physical snapshot supplies every active source display.
        E,A,collector=F.modules();snap=collector.Collector().snapshot(os.getpid(),self.out/'gamma-owner-before.json')
        A.environment(snap,physical=True)
        try:
            for name in sorted({p['gdi_name'] for p in snap['paths']}):
                dc=g.CreateDCW('DISPLAY',name,None,None);core.require(dc,'gamma display DC unavailable')
                data=C.create_string_buffer(1536)
                if not g.GetDeviceGammaRamp(dc,data):g.DeleteDC(dc);raise RuntimeError('cannot save original desktop gamma')
                raw=data.raw
                self.dcs.append((name,dc,raw))
                words=struct.unpack('<768H',raw)
                core.require(any(words),'original desktop gamma is entirely zero')
                core.require(all(words[c*256]<words[c*256+255] and
                    all(words[c*256+i]<=words[c*256+i+1] for i in range(255)) for c in range(3)),
                    'original desktop gamma failed monotonic/range validation')
                # Repeat acquisition validates that the saved bytes are stable.
                check=C.create_string_buffer(1536)
                if not g.GetDeviceGammaRamp(dc,check) or check.raw!=raw:
                    raise RuntimeError('original desktop gamma unstable')
            core.require(self.dcs,'no active displays to protect')
            core.atomic(self.out/'desktop-gamma-saved.json',dict(displays=[dict(name=n,bytes=b.hex()) for n,d,b in self.dcs]))
        except BaseException:
            for n,d,b in self.dcs:g.DeleteDC(d)
            raise
        return self
    def __exit__(self,*_):
        rows=[]
        for name,dc,raw in self.dcs:
            before=C.create_string_buffer(1536);read=bool(self.g.GetDeviceGammaRamp(dc,before))
            saved=C.create_string_buffer(raw);ok=bool(self.g.SetDeviceGammaRamp(dc,saved))
            after=C.create_string_buffer(1536);got=bool(self.g.GetDeviceGammaRamp(dc,after))
            rows.append(dict(name=name,before_read=read,before=before.raw.hex(),set_original=ok,
                             after_read=got,after=after.raw.hex(),equal=ok and got and after.raw==raw))
            self.g.DeleteDC(dc)
        core.atomic(self.out/'desktop-gamma-restored.json',dict(passed=all(r['equal'] for r in rows),displays=rows))
        if not rows or not all(r['equal'] for r in rows):raise core.IntegrityFailure('desktop gamma restoration unverified')


def validate(directory,item,build):
    E,A,_=F.modules();pair=P.P.G.verified_pair(item['arch'])
    rows,snapshot,events=A.process(directory,physical=True,expected_exe=item['exe'],
        expected_args=['--physical',pair,'--gamma-physical'],expected_build=build,
        expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
    A.adapter(rows,snapshot,directory,item['arch'])
    inp=A.one(rows,'gamma-input');saved=A.one(rows,'gamma-saved');restored=A.one(rows,'gamma-restored')
    A.need(inp['bytes']==(P.O/'actual-gamma-ramp.bin').read_bytes().hex(),'actual configuration gamma bytes')
    A.need(saved['bytes']==restored['bytes'] and restored['equal'] is True,'device gamma restoration')
    calls=[r for r in rows if r['kind']=='call'];reads=[r for r in rows if r['kind']=='readback']
    A.need(len(calls)==len(reads)==8,'eight gamma void calls/readbacks')
    for call,read,seed in zip(calls,reads,[18,18,0,0,0x13572468,0x13572468,0xffffffff,0xffffffff]):
        A.abi(call,item['arch'])
        A.need(call['slot']==18 and call['a']==1 and call['seed']==call['error']==seed and call['hr'] is None,'gamma void ABI/error')
        A.need(read['equal'] is True and read['slot']==18,'gamma input readback')
    summary=A.one(rows,'summary');A.need(summary['passed'] and summary['calls']==8,'gamma final summary')
    A.need(len(events)==(16 if item['variant']=='translated' else 0),'gamma translated event count')
    return [(r['seed'],r['error'],r['hr']) for r in calls]


def runner(request,candidate,out,stop,progress,**kwargs):
    core.require(request['family']==FAMILY,'this extension executes only restoring gamma fixtures')
    E,A,_=F.modules();root=F.candidate_path(candidate['id']).parent;captures=out/'captures';captures.mkdir()
    (out/'evidence').mkdir()
    observations=[];classification='fixture-complete';reason=None
    try:
        # Original gate, transport, mapped-module collector, Job and watchdog.
        D.physical_gate(out,dict(family='renderer-group'),qualification=False)
        with DesktopGamma(out):
            for item in plan(FAMILY,{},root):
                progress();D.physical_gate(out,dict(family='renderer-group'),qualification=False)
                pair=P.P.G.verified_pair(item['arch']);d=captures/item['name']
                T.capture(item['exe'],['--physical',pair,'--gamma-physical'],d,
                    build_record=root/'build/build-record.json',backend=[pair/'d3d8.dll',pair/'d3d9.dll'],
                    timeout=request['timeout_seconds'],stop=stop,physical=True)
                observations.append(validate(d,item,root/'build/build-record.json'))
            A.need(observations[0]==observations[1]==observations[2],'gamma native/translated differential')
    except core.IntegrityFailure:raise
    except BaseException as error:classification='collector-implementation-error';reason=str(error)
    finally:
        receipts=[core.read(p) for p in captures.glob('*/containment.json')]
        cleanup=len(receipts)==len(list(captures.iterdir())) and all(r['verified'] for r in receipts)
        F.verify_identities(candidate['files'])
        core.atomic(out/'assurance.json',dict(cleanup_verified=cleanup,integrity_verified=True))
        if not cleanup:raise core.IntegrityFailure('gamma fixture cleanup unverified')
    return dict(passed=classification=='fixture-complete',classification=classification,reason=reason,
                process_count=len(receipts),graphics_devices_created=len(receipts),genuine_launches=0,
                desktop_gamma_restoration=core.read(out/'desktop-gamma-restored.json'))


def build():
    E,_,_=F.modules();ident=str(uuid.uuid4());root=F.CANDIDATES/ident;src=root/'sources';b=root/'build'
    src.mkdir(parents=True);b.mkdir()
    for name in ('fixture.c','support.inc','evidence_fixture.h'): (src/name).write_bytes((F.FROZEN/'sources'/name).read_bytes())
    import shutil
    shutil.copytree(E.P.O/'snapshots/gamma/runtime',src/'runtime')
    raw=(P.O/'actual-gamma-ramp.bin').read_bytes()
    (src/'actual_ramp.inc').write_text('static const BYTE actual_ramp[1536]={'+','.join(map(str,raw))+'};\n')
    f=src/'fixture.c';t=f.read_text().replace('#include "evidence_fixture.h"','#include "evidence_fixture.h"\n#include "actual_ramp.inc"')
    t=t.replace('for(i=0;i<768;i++)words[i]=(WORD)((i%256)*257);','memcpy(batch_ramp,actual_ramp,1536);')
    t=t.replace('if(BATCH_GROUP==8)fixture_device->vt->GetGammaRamp(fixture_device,&saved);',
        'if(BATCH_GROUP==8){fixture_device->vt->GetGammaRamp(fixture_device,&saved);printf("{\\"kind\\":\\"gamma-saved\\",\\"bytes\\":");bytes((BYTE*)&saved,1536);puts("}");printf("{\\"kind\\":\\"gamma-input\\",\\"bytes\\":");bytes((BYTE*)batch_ramp,1536);puts("}");}')
    t=t.replace('printf("{\\"kind\\":\\"gamma-restored\\",\\"equal\\":%s}\\n",equal?"true":"false");',
        'printf("{\\"kind\\":\\"gamma-restored\\",\\"equal\\":%s,\\"bytes\\":",equal?"true":"false");bytes((BYTE*)&restored,1536);puts("}");')
    f.write_text(t)
    rows=[];tools=[]
    for item in plan(FAMILY,{},root):
        d=item['exe'].parent;d.mkdir();arch=item['arch'];abi=E.P.O/'fixtures'/arch/'abi.obj'
        E.P.R.script(d,'build',arch,f'cl /nologo /O1 /Gy /fp:strict /W3 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_TRANSLATED={int(item["variant"]=="translated")} /DBATCH_GROUP=8 /I"{src}/runtime" /Fo"{d}/fixture.obj" /Fe"{d}/fixture.exe" "{src}/fixture.c" "{abi}" user32.lib /link /OPT:REF /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1')
        E.P.R.script(d,'toolchain',arch,'where cl\nwhere link')
        tools += [Path(s) for s in (d/'toolchain.stdout.txt').read_text().splitlines() if s.strip()]
        r=E.P.R.execute([d/'fixture.exe','--contract-only'],d,'contract',timeout=30)
        summary=json.loads(r.stdout.splitlines()[-1]);core.require(summary['passed'] and not summary['graphics'],'gamma non-graphics contract')
        rows.append(dict(item={k:str(v) for k,v in item.items()},contract=summary))
    ins,outs=recipe(FAMILY,{},root)
    core.atomic(b/'build-record.json',dict(recipe='desktop-fixture-v1',family=FAMILY,parameters={},
        fp='/fp:strict',toolchain=F.identities(tools+[Path(E.P.R.VC)]),inputs=F.identities(ins),outputs=F.identities(outs),rows=rows))
    core.atomic(root/'candidate.json',dict(version=1,id=ident,family=FAMILY,parameters={},
        files=F.identities(files(FAMILY,{},root)),build_record=str(b/'build-record.json')))
    core.atomic(P.O/'prepared-gamma-candidate.json',dict(candidate=ident,path=str(root/'candidate.json'),
        manifest_sha256=core.sha(root/'candidate.json'),submitted=False,graphics_executed=False))
    print(ident)


def qualify():
    from supervisor.fixture_qualification import checked,project_seal,qualification_cycles
    from supervisor.qualify import host_files
    out=HOME/('qualification-'+str(uuid.uuid4()));out.mkdir(parents=True)
    (out/'evidence').mkdir()
    # Unchanged service safety tests and original collector tests run independently.
    checked([sys.executable,'-B','-I','-m','unittest','discover','-s',str(P.W/'tools/xrt/supervisor/tests'),'-v'],out,'supervisor-tests')
    checked([sys.executable,'-B','-I','-m','unittest','discover','-s',str(F.RENDERER),'-p','test_*.py','-v'],out,'collector-tests')
    checked([sys.executable,'-B','-I','-m','unittest','discover','-s',str(H),'-p','test_*.py','-v'],out,'prerequisite-tests')
    cycles=qualification_cycles(out)
    # The graphics gate is mandatory even during qualification; no gamma runs.
    try:D.physical_gate(out,dict(family='renderer-group'),qualification=True)
    except D.DesktopUnavailable:pass
    files=project_seal()
    for p in H.glob('*'):
        if p.is_file():files[p.relative_to(P.W).as_posix()]=core.sha(p)
    seal=dict(passed=True,files=files,host_files=host_files(),evidence=str(out),cycles=cycles,
        family=FAMILY,graphics_devices_created=0,genuine_launches=0,original_service_unchanged=True)
    core.atomic(out/'qualification.json',seal);core.atomic(HOME/'qualification.json',seal)
    print('QUALIFIED; zero graphics/genuine launches',out)


def serve():
    from supervisor.environment import ordinary_user
    ordinary_user();core.require(sys.stdin.isatty(),'local owner console required')
    # Hold the original service lock as well, so two desktop test services cannot
    # dispatch concurrently. No original state or authorization is modified.
    with Exclusive(F.HOME/'supervisor.lock'),Exclusive(HOME/'supervisor.lock'):
        seal=core.read_large(HOME/'qualification.json');verify_seal(seal)
        service=D.FixtureService(HOME,runner=runner)
        core.require(not service.halted and not service.stop(),'preserved hold/STOP requires owner review')
        with FilePins() as pins:
            for n,h in {**{str(P.W/k):v for k,v in seal['files'].items()},**seal['host_files']}.items():pins.pin(Path(n),h)
            service.bind_seal(seal);D.physical_gate(HOME,dict(family='renderer-group'))
            print('Restoring gamma fixtures only; zero genuine launches. Type: AUTHORIZE RESTORING GAMMA FIXTURES')
            core.require(input().strip()=='AUTHORIZE RESTORING GAMMA FIXTURES','owner authorization absent')
            service.ledger.append('fixture-batch-authorized',batch=service.batch,owner_console=True,qualification_sha256=core.digest(seal))
            def shutdown(*_):service.shutdown=True
            for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGBREAK):signal.signal(sig,shutdown)
            service.serve()


if __name__=='__main__':
    install()
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['build','qualify','serve','submit','status']);args=parser.parse_args()
    if args.command=='submit':
        p=core.read(P.O/'prepared-gamma-candidate.json')
        print(D.submit(p['candidate'],'Measure configured Unreal II gamma input and void ABI with independent desktop/device ramp restoration; no genuine launch',home=HOME))
    elif args.command=='status':print(json.dumps(D.read_status(HOME),indent=2))
    else:globals()[args.command]()
