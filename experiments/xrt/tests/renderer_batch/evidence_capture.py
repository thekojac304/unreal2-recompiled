"""Windows collector transport. This module does not choose or run GPU tests."""
import ctypes as C
from ctypes import wintypes as T
import json, os, struct, subprocess, time, uuid
from pathlib import Path
import prepare_evidence as E
from module_identity import WindowsProcess, collect, IdentityIncomplete, error_record
P=E.P

def read(path):return P.core.read_large(path)
def save(path,value):P.core.atomic(path,value)
def now():
    stamp=T.FILETIME()
    C.WinDLL('kernel32').GetSystemTimePreciseAsFileTime(C.byref(stamp))
    return (stamp.dwHighDateTime<<32)|stamp.dwLowDateTime

class Collector:
    def __init__(self):
        self.lib=C.CDLL(str(E.O/'build/collector.dll'))
        signatures={
            'ev_snapshot':([C.c_uint32,C.c_wchar_p],C.c_int),
            'ev_spawn':([C.c_wchar_p,C.c_wchar_p,C.c_void_p,*([C.c_wchar_p]*4)],C.c_void_p),
            'ev_pid':([C.c_void_p],C.c_uint32),'ev_resume':([C.c_void_p],C.c_uint32),
            'ev_wait':([C.c_void_p,C.c_uint32],C.c_uint32),
            'ev_release':([C.c_void_p],C.c_int),'ev_abort':([C.c_void_p],C.c_int),
            'ev_job':([C.c_void_p,C.c_wchar_p],C.c_int),
            'ev_finish':([C.c_void_p,C.c_wchar_p,C.c_uint32],C.c_int),
            'ev_close':([C.c_void_p],None)}
        for name,(args,result) in signatures.items():
            f=getattr(self.lib,name);f.argtypes=args;f.restype=result

    def snapshot(self,pid,path,*,pre_resume=False):
        raw=path.with_name(path.stem+'.raw.json')
        assert not raw.exists() and not path.exists(),'snapshot evidence must be fresh'
        assert self.lib.ev_snapshot(pid,str(raw))==0,('snapshot API failed',pid,raw)
        s=read(raw)
        try:
            started=now()
            with WindowsProcess(pid,s['creation_filetime']) as provider:
                s['modules'],s['module_identity']=collect(provider,s['modules'],pre_resume=pre_resume)
            s['module_identity'].update(start_filetime=started,finish_filetime=now())
            s['modules_complete']=s['module_identity']['complete']
            s['image_sha256']=P.core.sha(Path(s['image']))
        except (OSError,IdentityIncomplete) as error:
            s['identity_error']=error_record(error)
            s['module_identity']=dict(schema=1,complete=False,status='unresolved',
                creation_filetime=s['creation_filetime'],start_filetime=started,finish_filetime=now(),
                unresolved=[error_record(error)],rounds=[],unloaded=[])
            s['modules_complete']=False
            for m in s['modules']:m['identity_status']='unresolved'
            save(path,s);raise
        save(path,s)
        receipt=s['module_identity']
        if not receipt['complete'] and not (pre_resume and receipt['status']=='pre-resume-loader-unavailable'):
            raise IdentityIncomplete('unresolved loaded-module identity; see '+str(path))
        return s

    def capture(self,exe,args,d,*,build_record=None,backend=None,extra_env=None,timeout_ms=60000,physical=False):
        from evidence_check import environment
        d=d.resolve();d.mkdir();exe=exe.resolve();command=[str(exe),*map(str,args)]
        env=os.environ.copy()
        for key in list(env):
            if key.upper().startswith(('DXVK_','VK_')):del env[key]
        effective=P.G.environment(env,d)
        token=uuid.uuid4().hex
        env.update(XRT_EVIDENCE_DIR=str(d),XRT_EVIDENCE_READY='Local\\XrtEvidenceReady-'+token,XRT_EVIDENCE_GATE='Local\\XrtEvidenceGate-'+token)
        if extra_env:env.update(extra_env)
        environment_block=C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items(),key=lambda kv:kv[0].upper()))+'\0\0')
        owner=self.snapshot(os.getpid(),d/'owner-before.json');environment(owner,physical=physical)
        record=dict(schema=2,command=command,command_line=subprocess.list2cmdline(command),cwd=str(d),
            executable_sha256=P.core.sha(exe),build_record=str(build_record) if build_record else None,
            build_record_sha256=P.core.sha(build_record) if build_record else None,
            backend={str(p):P.core.sha(p) for p in (backend or [])},dxvk_environment=effective,
            owner_pid=os.getpid(),owner_sid=owner['owner_sid'],start_filetime=now(),physical=physical,
            fixture_stdout='stdout.txt',runtime_events='runtime-events.jsonl',runtime_stream_origin='instrumented fixture services; not full production runtime telemetry',
            event_loss_policy='synchronous writes counted; no queue-drop instrumentation; dropped_event_count must remain null',forced_cleanup=False)
        save(d/'process.json',record)
        (d/'runtime-events.jsonl').touch()
        child=self.lib.ev_spawn(record['command_line'],str(d),C.cast(environment_block,C.c_void_p),str(d/'stdout.txt'),str(d/'stderr.txt'),env['XRT_EVIDENCE_READY'],env['XRT_EVIDENCE_GATE'])
        assert child,'CreateProcess/job assignment failed; no child resumed'
        try:
            pid=self.lib.ev_pid(child);record['pid']=pid;save(d/'process.json',record)
            self.snapshot(pid,d/'suspended.json',pre_resume=True)
            assert self.lib.ev_job(child,str(d/'suspended-job.json'))==0
            assert self.lib.ev_resume(child)!=0xffffffff,'ResumeThread failed'
            for phase in ['loaded','cleaned']:
                status=self.lib.ev_wait(child,timeout_ms)
                assert status==0,('missing child checkpoint',phase,status)
                receipt=read(d/(phase+'-self.json'))
                assert receipt['phase']==phase and receipt['pid']==pid,('checkpoint identity',phase)
                snapshot=self.snapshot(pid,d/(phase+'-environment.json'));environment(snapshot,physical=physical)
                assert self.lib.ev_job(child,str(d/(phase+'-job.json')))==0
                assert self.lib.ev_release(child),'checkpoint release failed'
            assert self.lib.ev_finish(child,str(d/'exit.json'),timeout_ms)==0
            exit=read(d/'exit.json')
            assert exit['wait']==0 and exit['active_processes']==0,'child/tree did not exit'
            record['finish_filetime']=now();save(d/'process.json',record)
            self.snapshot(os.getpid(),d/'owner-after.json')
            assert exit['exit']==0,('fixture exit failure',exit['exit'])
        except BaseException as error:
            record.update(forced_cleanup=True,failure=str(error),finish_filetime=now());save(d/'process.json',record)
            self.lib.ev_abort(child)
            self.lib.ev_finish(child,str(d/'failure-exit.json'),5000)
            raise
        finally:self.lib.ev_close(child)
        return [P.core.loads(line) for line in (d/'stdout.txt').read_bytes().splitlines()]
