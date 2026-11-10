"""Preserve inputs and build fixed native observation executables; never owner-launch."""
import sys, json, subprocess, shutil
from pathlib import Path
W=Path(__file__).resolve().parents[4]
H=Path(__file__).resolve().parent
O=W/'out/recovery/remote-console-proof-20261030-01'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core,fixture_profiles as F
from supervisor.environment import load
from supervisor.service import verify_seal
import asset_boundary as A

def preserve():
    O.mkdir()
    m=load('proof_environment',W/'out/recovery/session-aware-136-20261026-01/preflight.py')
    d=m.observe();core.atomic(O/'desktop-before.json',d)
    prior=core.read_large(W/'out/recovery/remote-fixture-startup-20261030-01/inspection.json')
    owner=next(r for r in prior['processes'] if r['exe'].lower()=='explorer.exe')['token']
    core.require(d['session']==d['active_console_session']==owner['session'],'same existing console session required')
    verify_seal(core.read_large(F.HOME/'qualification.json'))
    roots=[W/'tools/xrt/supervisor',F.HOME,W/'out/desktop-supervisor',W/'experiments/xrt/runtime',W/'out/recovery/resource-frame-20261030-01/runtime']
    core.atomic(O/'preservation.json',dict(trees={str(p):core.tree(p) for p in roots},assets=A.verify(),physical=m.E.fingerprint(d),owner=owner))
    print('Preserved supervisor homes/seals, runtime, assets and physical desktop',flush=True)

def build():
    data=core.read_large(O/'preservation.json');b=O/'build';b.mkdir()
    helper=load('proof_compile',W/'experiments/xrt/tests/getobject_boundary/phase.py');helper.O=O
    env=helper.env();cl=shutil.which('cl.exe',path=env.get('Path',env.get('PATH')))
    collector=W/'out/recovery/renderer-evidence-20261029-03/build/collector.dll'
    assert collector.is_file()
    def wide(p):return 'L'+json.dumps(str(p).replace('\\','/'))
    owner=data['owner'];hi,lo=[int(x,16) for x in owner['authentication_id'].split(':')]
    config='\n'.join([f'#define ROOT {wide(O)}',f'#define CHILD {wide(b/"observation.exe")}',
        f'#define COLLECTOR {wide(collector)}',f'#define OWNER_SID L"{owner["user"]}"',
        f'#define OWNER_AUTH_HI {hi}u',f'#define OWNER_AUTH_LO {lo}u',f'#define OWNER_SESSION {owner["session"]}u',
        f'#define COLLECTOR_SHA "{core.sha(collector)}"'])+'\n'
    (b/'config.h').write_text(config)
    runs=[]
    for name,source,subsystem in [('observation','observation.c','CONSOLE'),('launcher','launcher.c','WINDOWS')]:
        if name=='launcher':(b/'config.h').write_text(config+f'#define CHILD_SHA "{core.sha(b/"observation.exe")}"\n')
        shutil.copy2(b/'config.h',b/('config-'+name+'.h'))
        command=[cl,'/nologo','/W4','/WX','/wd4505','/O2','/MT','/DUNICODE','/D_UNICODE','/D_CRT_SECURE_NO_WARNINGS',
            '/I'+str(b),'/I'+str(H),'/Fo'+str(b/(name+'.obj')),'/Fe'+str(b/(name+'.exe')),str(H/source),
            'advapi32.lib','user32.lib','bcrypt.lib','/link','/SUBSYSTEM:'+subsystem,'/INCREMENTAL:NO','/DYNAMICBASE','/NXCOMPAT']
        p=subprocess.run(command,cwd=b,env=env,capture_output=True,timeout=60)
        (O/(name+'-build.stdout')).write_bytes(p.stdout);(O/(name+'-build.stderr')).write_bytes(p.stderr)
        runs.append(dict(command=command,exit=p.returncode))
        core.atomic(O/'build-progress.json',runs)
        assert p.returncode==0,(p.stdout+p.stderr).decode(errors='replace')
    core.atomic(O/'build.json',dict(source=core.tree(H),outputs=core.tree(b),commands=runs,cl_sha256=core.sha(cl),collector=str(collector),collector_sha256=core.sha(collector),owner=owner,
        executable=str(b/'launcher.exe'),sha256=core.sha(b/'launcher.exe'),child_sha256=core.sha(b/'observation.exe'),owner_launches=0))
    print('Built fixed native launcher and observation child',core.sha(b/'launcher.exe'),flush=True)

if __name__=='__main__':
    assert len(sys.argv)==2 and sys.argv[1] in ('preserve','build')
    globals()[sys.argv[1]]()
