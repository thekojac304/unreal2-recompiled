"""Independent saved-evidence and live PID audit; never starts an owner process."""
import sys,ctypes as C,subprocess,time
from ctypes import wintypes as T
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare import W,H,O,core,F,load,verify_seal,A

def absent(pid,creation=None):
    from supervisor.windows import api,K,Close
    C.set_last_error(0)
    p=api(K,'OpenProcess',[T.DWORD,T.BOOL,T.DWORD],T.HANDLE)(0x1000,False,pid)
    if not p:
        error=C.get_last_error();core.require(error==87,'cannot prove process absent: '+str(error));return dict(pid=pid,absent=True)
    try:
        times=[T.FILETIME() for _ in range(4)]
        core.require(api(K,'GetProcessTimes',[T.HANDLE,*([C.POINTER(T.FILETIME)]*4)])(p,*[C.byref(t) for t in times]),'process times')
        actual=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        core.require(creation is not None and actual!=creation,'original process remains present')
        return dict(pid=pid,absent=True,pid_reused=True,current_creation=actual)
    finally:Close(p)

def verify_build():
    import pefile
    b=core.read_large(O/'build.json');core.require(core.tree(O/'build')==b['outputs'],'build changed')
    for name in ('common.h','observation.c','launcher.c'):
        core.require(core.sha(H/name)==b['source'][name],'compiled source changed')
    core.require(core.sha(b['collector'])==b['collector_sha256'],'collector changed')
    forbidden={'CreateProcessAsUserW','CreateProcessWithTokenW','CreateProcessWithLogonW','DuplicateToken','DuplicateTokenEx','ImpersonateLoggedOnUser','SetThreadToken','SetTokenInformation','AdjustTokenPrivileges','SwitchDesktop','SetThreadDesktop','SetProcessWindowStation','ChangeDisplaySettingsExW','SetDisplayConfig','WTSConnectSessionW','ShellExecuteW','WinExec'}
    rows=[]
    for name,subsystem in [('launcher',2),('observation',3)]:
        with pefile.PE(str(O/'build'/(name+'.exe'))) as pe:
            names={i.name.decode() for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports if i.name}
            core.require(pe.FILE_HEADER.Machine==0x8664 and pe.OPTIONAL_HEADER.Subsystem==subsystem,'PE target')
            core.require(not names&forbidden,'forbidden import')
            core.require(('CreateProcessW' in names)==(name=='launcher'),'child process creation capability')
            rows.append(dict(name=name,sha256=core.sha(O/'build'/(name+'.exe')),imports=sorted(names),subsystem=subsystem))
    return rows

def refusal():
    builds=verify_build();exe=O/'build/launcher.exe'
    for args,expected in [(['unexpected'],2),([],23)]:
        p=subprocess.run([str(exe),*args],cwd=W,timeout=10)
        core.require(p.returncode==expected,'sandbox refusal/argument rejection')
    row=core.read(O/'sandbox-refusal.json')
    core.require(row['child_created'] is False and not (O/'run').exists(),'sandbox created physical child')
    core.atomic(O/'sandbox-validation.json',dict(passed=True,argument_rejection_exit=2,owner_identity_refusal_exit=23,child_created=False,identities=builds,observed=row))
    print('Native argument rejection and sandbox-owner rejection PASS; no child created',flush=True)

def evidence():
    verify_build();r=O/'run'
    owner=core.read_large(O/'preservation.json')['owner'];child=core.read(r/'child.json');parent=core.read(r/'parent-child-identity.json');launcher=core.read(r/'launcher.json');done=core.read(r/'child-complete.json');result=core.read(r/'result.json')
    for record in (child,parent,launcher):
        core.require(record['sid']==owner['user'] and record['authentication_id']==owner['authentication_id'] and record['session']==owner['session'] and record['elevated']==record['restricted']==0,'owner identity mismatch')
    core.require(child['pid']==parent['pid']==done['pid']==result['child_pid'],'child pid mismatch')
    core.require(child['station']=='WinSta0' and child['desktop']==child['input_desktop']=='Default','desktop mismatch')
    core.require(child['stdin_isatty']!=0 and child['console_modes_ok']==[1,1,1] and child['console_process_count']==1 and child['console_window']!=0,'real console required')
    core.require(result['launcher_result']==result['exit_code']==result['active_job_processes']==result['terminated_job_processes']==0 and result['total_job_processes']==1 and result['kill_on_close'] and result['active_process_limit']==1,'clean job exit required')
    core.require(done['normal_return'] and 1500<=done['elapsed_ms']<15000 and result['elapsed_ms']<20000,'bounded lifetime')
    _,checks,_=F.modules();snapshot=core.read_large(r/'environment.raw.json')
    core.require(snapshot['pid']==child['pid'] and snapshot['owner_sid']==owner['user'] and snapshot['creation_filetime']==parent['creation_filetime'],'collector identity mismatch')
    build=core.read_large(O/'build.json')
    core.require(Path(snapshot['image']).resolve()==(O/'build/observation.exe').resolve(),'unexpected child executable')
    snapshot['image_sha256']=core.sha(snapshot['image'])
    core.require(snapshot['image_sha256']==build['child_sha256'],'child image changed')
    checks.environment(snapshot,physical=True)
    # Independent process inspection after completion; accounting proves no
    # concurrent descendants were admitted into this non-breakaway one-process Job.
    cleanup=[absent(child['pid'],parent['creation_filetime']),absent(launcher['pid'])]
    inventory=load('proof_process_inventory',W/'out/recovery/windisc-display-20261025-01/inventory.py')
    entry=inventory.PE();entry.size=C.sizeof(entry)
    handle=inventory.fn(inventory.K,'CreateToolhelp32Snapshot',[T.DWORD,T.DWORD],T.HANDLE)(2,0)
    rows=[]
    try:
        ok=inventory.fn(inventory.K,'Process32FirstW',[T.HANDLE,C.POINTER(inventory.PE)])(handle,C.byref(entry))
        core.require(ok,'independent process enumeration failed')
        while ok:
            rows.append(dict(pid=entry.pid,parent=entry.parent,image=entry.exe))
            ok=inventory.fn(inventory.K,'Process32NextW',[T.HANDLE,C.POINTER(inventory.PE)])(handle,C.byref(entry))
    finally:inventory.fn(inventory.K,'CloseHandle',[T.HANDLE])(handle)
    descendants=[row for row in rows if row['parent'] in (child['pid'],launcher['pid'])]
    core.require(not descendants,'remaining descendants or reused PID require investigation')
    core.atomic(O/'independent-audit.json',dict(passed=True,physical_gate_accepted=True,cleanup=cleanup,child=child,result=result,normal_exit_verified=True,descendants_admitted=0,live_descendant_scan=descendants,gpu_devices_created=0,service_starts=0,files=core.tree(r)))
    print('Owner physical console, unchanged production gate, normal exit and no descendants PASS',flush=True)

def preservation():
    p=core.read_large(O/'preservation.json');m=load('proof_final_environment',W/'out/recovery/session-aware-136-20261026-01/preflight.py');d=m.observe()
    core.atomic(O/'desktop-after.json',d)
    changed=[name for name,tree in p['trees'].items() if core.tree(Path(name))!=tree]
    protected=A.verify();physical=m.E.fingerprint(d)
    result=dict(passed=not changed and protected==p['assets'] and physical==p['physical'],changed_trees=changed,assets_unchanged=protected==p['assets'],physical_desktop_unchanged=physical==p['physical'])
    verify_seal(core.read_large(F.HOME/'qualification.json'));core.atomic(O/'preservation-after.json',result)
    core.require(result['passed'],'preservation mismatch');print('Protected state and physical configuration unchanged',flush=True)

if __name__=='__main__':
    core.require(len(sys.argv)==2 and sys.argv[1] in ('refusal','evidence','preservation'),'fixed audit operation required')
    globals()[sys.argv[1]]()
