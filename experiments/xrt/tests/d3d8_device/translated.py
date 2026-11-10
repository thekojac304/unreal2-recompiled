"""Opt-in fixture-only import and typed device table; no runtime file is edited."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from run import W,HERE,sha,write,G
from slots import SLOTS
def execute(cmd,out,name,env=None):
    r=subprocess.run([str(x)for x in cmd],cwd=W,env=env,capture_output=True,text=True,timeout=120)
    (out/(name+'.stdout.txt')).write_text(r.stdout);(out/(name+'.stderr.txt')).write_text(r.stderr)
    write(out/(name+'.json'),dict(command=[str(x)for x in cmd],exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(name,r.returncode,r.stdout[-1500:],r.stderr[-1500:],flush=True);return r
def build(out):
    assert not out.exists();out.mkdir(parents=True);(out/'x86').mkdir();(out/'x64').mkdir()
    supported={0:'fixture_qi',1:'fixture_add',2:'fixture_release',6:'fixture_parent',9:'fixture_creation'}
    declarations=[];bindings=[]
    for slot,(name,nargs)in enumerate(SLOTS):
        fn=supported.get(slot,'fixture_unsupported_'+str(slot))
        if slot not in supported:declarations.append(f'static void {fn}(CPU*c){{fixture_object(c,ARG(0));xrt_fatal(c,76,"fixture device unsupported slot {slot} {name}");}}')
        bindings.append(f'{{"fixture.dll","FixtureDevice.{name}",{fn}}},')
    declarations+=['static const char*fixture_slot_names[97]={'+','.join('"FixtureDevice.'+n+'"'for n,_ in SLOTS)+'};']
    declarations+=['#define FIXTURE_BINDINGS \\\n'+ ' \\\n'.join(bindings+['{"fixture.dll","FixtureOpen",fixture_open},','{"fixture.dll","FixtureCreateDevice",fixture_create},'])]
    (out/'fixture_slots.inc').write_text('\n'.join(declarations)+'\n')
    original=(W/'experiments/xrt/runtime/hle_misc.c').read_text()
    copy=original.replace('const XrtHle xrt_hle_misc[] = {','#include "'+str(HERE/'fixture.inc').replace('\\','/')+'"\nconst XrtHle xrt_hle_misc[] = {\n FIXTURE_BINDINGS')
    (out/'fixture_hle_misc.c').write_text(copy)
    (out/'host.c').write_text('#include "'+str(HERE.parent/'d3d8_boundary/host.c').replace('\\','/')+'"\n')
    (out/'fixture.def').write_text('LIBRARY fixture.dll\nEXPORTS\n FixtureOpen\n FixtureCreateDevice\n')
    script='@echo off\ncall "C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" x86 >nul || exit /b 1\n'
    script+=f'lib /nologo /def:"{HERE.parent}/d3d8_boundary/d3d8.def" /machine:X86 /out:"{out}/x86/d3d8.lib" || exit /b 1\n'
    script+=f'lib /nologo /def:"{out}/fixture.def" /machine:X86 /out:"{out}/x86/fixture.lib" || exit /b 1\n'
    script+=f'cl /nologo /c /O2 /arch:IA32 /GS- /W4 /Fo"{out}/x86/probe.obj" "{HERE}/probe.c" || exit /b 1\n'
    aliases='/alternatename:__imp__Direct3DCreate8@4=__imp__Direct3DCreate8 /alternatename:__imp__FixtureOpen@0=__imp__FixtureOpen /alternatename:__imp__FixtureCreateDevice@28=__imp__FixtureCreateDevice'
    script+=f'link /nologo /DLL /NOENTRY /NODEFAULTLIB {aliases} /BASE:0x12000000 /DYNAMICBASE:NO /OUT:"{out}/x86/d3dprobe.dll" "{out}/x86/probe.obj" "{out}/x86/d3d8.lib" "{out}/x86/fixture.lib" kernel32.lib || exit /b 1\n'
    (out/'build-probe.cmd').write_text(script)
    assert execute(['cmd','/d','/c',out/'build-probe.cmd'],out,'build-probe').returncode==0
    assert execute([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',out/'x86/d3dprobe.dll','--out',out/'gen'],out,'lift').returncode==0
    base=(HERE.parent/'d3d8_boundary/build.cmd').read_text();command=next(s for s in base.splitlines()if s.startswith('cl ')).split(' > ')[0]
    command=command.replace('%OUT%',str(out)).replace('%HERE%',str(out)).replace('%RT%',str(W/'experiments/xrt/runtime'))
    command=command.replace('"'+str(W/'experiments/xrt/runtime')+'\\hle_misc.c"','"'+str(out/'fixture_hle_misc.c')+'"')
    command=command.replace('cl /nologo',f'cl /nologo /I"{out}"')
    script='@echo off\ncall "C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" x64 >nul || exit /b 1\n'+command+'\n'
    (out/'build-translated.cmd').write_text(script)
    assert execute(['cmd','/d','/c',out/'build-translated.cmd'],out,'build-translated').returncode==0
    write(out/'source-identities.json',{str(p):sha(p)for p in [*HERE.glob('*.*'),*out.glob('*.c'),out/'fixture_slots.inc',* (out/'gen').glob('*')]if p.is_file()})
def run(out):
    runs=[]
    probes=['probe_fixture','probe_fixture_parent_first','probe_fixture_leak','probe_fixture_stale','probe_fixture_clear','probe_fixture_present','probe_device_guard','probe_fixture_bad_parameters','probe_fixture_bad_output']
    for rep in range(2):
        for probe in probes:
            dest=out/f'{probe}-{rep}';dest.mkdir();env=os.environ.copy();G.environment(env,dest);env['XRT_D3D8_DIR']=str(G.verified_pair('x64'))
            report=dest/'report.json';r=execute([out/'translated.exe',out/'x86/d3dprobe.dll',report,probe],dest,'run',env)
            expected=0 if probe in ['probe_fixture','probe_fixture_parent_first','probe_fixture_leak']else 76
            assert r.returncode==expected
            data=json.loads(report.read_text());assert data['events_dropped']==0
            ev=data['events'];created=[e for e in ev if e['kind']=='fixture_create_return']
            assert all(e['esp_after']-e['esp_before']==32 and e['return']==e['actual_return']for e in created)
            if probe=='probe_device_guard':assert not created and 'CreateDevice is unmeasured'in r.stderr
            elif probe in ['probe_fixture_bad_parameters','probe_fixture_bad_output']:assert not created and 'invalid writable guest range'in r.stderr
            else:assert created and any(e['host_non_null']and e['result']==0 for e in created)
            if probe=='probe_fixture_clear':assert 'unsupported slot 36 Clear'in r.stderr
            if probe=='probe_fixture_present':assert 'unsupported slot 15 Present'in r.stderr
            if probe=='probe_fixture_stale':assert 'stale or unknown'in r.stderr
            if probe=='probe_fixture_leak':assert any(e['kind']=='fixture_device_cleanup'and e['references_released']==2 for e in ev)
            runs.append(dict(probe=probe,rep=rep,exit=r.returncode,creates=created,report=str(report),report_sha256=sha(report)))
    write(out/'results.json',dict(passed=True,runs=runs,production_CreateDevice_still_guarded=True))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build','run']);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();globals()[a.action](a.out.resolve())
