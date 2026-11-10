"""Fresh local owner authorization for exactly one fixed SetRes completion attempt.

No queue, retry, alternate executable, argument or endpoint is accepted.
"""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from contextlib import ExitStack
import json
import os
import signal
import shutil
import time
import traceback
import uuid
from common import *
from supervisor.windows import Exclusive,FilePins
from supervisor.environment import Desktop,ordinary_user
from supervisor.fixture import environment


def classify_failure(error):
    if isinstance(error,core.IntegrityFailure):return 'safety-integrity-failure'
    if isinstance(error,core.Rejected) and str(error).startswith('renderer configuration diagnostic stop:'):
        return 'diagnostic-configuration-stop'
    return 'unclassified-correctness-failure'


def validate_seal():
    s=read(O/'seal.json')
    core.require(s['passed'] and s['scope']==SCOPE and s['candidate_sha256']==SHA and s['maximum_launches']==1 and s['maximum_seconds']==60,'milestone qualification/scope')
    for path,digest in s['files'].items():
        core.require(core.sha(core.independent(path))==digest,'sealed file changed: '+path)
    core.require(core.tree(H)==s['implementation'],'milestone source inventory changed')
    core.require(read(O/'debugger-validation.json')['passed'] and read(O/'preservation-after.json')['passed'],'qualification incomplete')
    core.require(not (O/'OWNER-ATTEMPT-CONSUMED.json').exists(),'this milestone has already consumed its attempt')
    return s


def execution_gate():
    core.require(not (core.HOME/'HALTED.json').exists() and not (core.HOME/'STOP').exists() and not (O/'STOP').exists(),'existing safety/local stop remains active')
    core.require(not list((core.HOME/'processing').glob('*.json')),'interrupted production request requires investigation')
    ledger=core.Ledger(core.HOME/'ledger.jsonl');resolved=read(O/'resolved-hold.json')
    core.require(core.sha(ledger.path)==resolved['ledger_sha256'],'ledger changed since scoped diagnosis; prepare again')
    transitions=[r for r in ledger.rows if r['kind']=='operational-transition']
    core.require(transitions and transitions[-1]==resolved['transition'],'unrelated or changed hold; no reset')
    core.require(resolved['candidate_sha256']==SHA and resolved['guest_stop']==GUEST and resolved['hold_preserved'],'wrong scoped resolution')
    for path,digest in resolved['evidence'].items():core.require(core.sha(path)==digest,'scoped resolution evidence changed')
    core.require(read(O/'source-change.json')['changed']==['integrated_renderer.inc'] and read(O/'field-debugger-validation.json')['passed'] and read(O/'boolean-characterization.json')['passed'],'call-aware evidence change unqualified')
    from identity import consumed
    consumed()
    return ledger


from attach_audit import audit as audit_attach


def audit(out, cap):
    from retained_audit import audit as retained_audit
    retained_audit(out)
    rows=cap.rows
    core.require(cap.terminated_while_stopped and cap.cleanup['passed'],'termination/containment not verified')
    core.require((out/'hard-stop.json').exists() and not any(r['kind']=='fatal_entry' for r in rows),'SetRes completion not reached')
    events=read(out/'runtime-events.json')['events']
    attach_count=audit_attach(events)['pairs']
    import evidence
    evidence.runtime_pair(events,next(r for r in rows if r['kind']=='setres_entry_raw'),next(r for r in rows if r['kind']=='initial_setres_return_raw'))
    core.require(not any(e['kind'] in ('engine_tick_call','level_tick_call') for e in events),'world execution entered')
    calls=[r for r in rows if r['kind']=='profile_entry'];nr=[r for r in rows if r['kind']=='profile_native_return'];br=[r for r in rows if r['kind']=='profile_bridge_return']
    core.require(len(calls)==len(nr)==len(br)==239,'entire configured+material sequence missing')
    for a,b,c in zip(calls,nr,br):
        core.require(a['index_in_profile']==b['index_in_profile']==c['index_in_profile'],'paired renderer evidence order')
    gamma=[e for e in events if e['kind']=='d3d8_gamma_return']
    core.require(len(gamma)==1,'one actual gamma return event required')
    g=gamma[0];ge=next(r for r in calls if r['expected']['slot']==18)
    gn=next(r for r in rows if r['kind']=='profile_native_entry' and r['method']=='SetGammaRamp')
    gr=next(r for r in nr if r['method']=='SetGammaRamp')
    core.require(g['eax_before']==g['eax_after']==ge['cpu']['registers']['eax'] and
                 g['esp_after']==g['esp_before']+16 and g['last_error']==gr['last_error'] and
                 g['mxcsr_before']==gn['host']['mxcsr'] and g['mxcsr_after']==gr['host']['mxcsr'],'runtime/native gamma evidence discrepancy')
    material=[e for e in events if e['kind']=='d3d8_material_return']
    core.require(len(material)==1 and material[0]['result']==nr[0]['hresult']==0 and material[0]['last_error']==nr[0]['last_error'],'runtime/native material evidence discrepancy')
    for name,count in [('native_return',1),('bridge_return',1),('render_native_return',2),('render_bridge_return',2),('state_bridge_return',8),('resize_return',1)]:
        core.require(len([r for r in rows if r['kind']==name])==count,'retained sequence incomplete: '+name)
    save(out/'milestone-audit.json',dict(passed=True,configured_calls=238,material_calls=1,CreateDevice=1,Clear=1,Present=1,initial_states=8,
        actual_HRESULT_last_error_paired=True,gamma_is_void=True,ResizeViewport=1,SetRes_eax=1,SetRes_ret20=True,
        endpoint='before guest 11104BF8',AttachThreadInput_pairs=attach_count,strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained',gameplay_verified=False))


def run_once():
    core.require(os.name=='nt' and not sys.flags.optimize and sys.stdin.isatty(),'ordinary local owner console with assertions required')
    ordinary_user();s=validate_seal()
    # Reuse both existing exclusive locks; a currently running fixture/genuine
    # supervisor must be stopped locally. Neither authorization is inherited.
    with Exclusive(core.HOME/'supervisor.lock'),Exclusive(W/'out/desktop-fixtures/supervisor.lock'),FilePins() as pins:
        ledger=execution_gate()
        for path,digest in s['files'].items():pins.pin(path,digest)
        from identity import verify
        from mapping import resolve
        from observer import construct
        from gamma_guard import DesktopGamma
        verify();plan=resolve()
        ident=str(uuid.uuid4());out=O/('owner-'+ident);out.mkdir()
        sandbox=W/'sandbox_cmp'/('setres-'+ident)
        core.require(not sandbox.exists(),'exclusive fresh sandbox required')
        desktop=Desktop();desktop.check(out,'first');desktop.check(out,'second')
        print('Fixed candidate:',SHA,'; endpoint before guest 11104BF8; one launch; 60 seconds; no retry.',flush=True)
        print('Strict x87, full WNDPROC and native-x86 compatibility remain FAILED.',flush=True)
        print('This new candidate uses the same initial WinDrv 11104BF8 stop. No breakpoint or production policy is expanded.',flush=True)
        print('Separately authorize this hardware-stop scope by typing: '+STOP_PHRASE,flush=True)
        core.require(input().strip()==STOP_PHRASE,'separate owner stop authorization not accepted')
        stop_authorized_at=time.time()
        print('Type exactly: '+PHRASE,flush=True)
        core.require(input().strip()==PHRASE,'fresh endpoint authorization not accepted')
        core.require(time.time()-stop_authorized_at<=300,'separate stop authorization expired')
        expiry=time.time()+300
        auth=dict(id=ident,started_at=time.time(),expires_at=expiry,genuine_limit=1,maximum_seconds=60,scope=SCOPE,retry=False,
                  candidate_sha256=SHA,guest_stop=GUEST,stop_rva=RVA,owner_console=True,phrase=PHRASE,endpoint_authorization=dict(phrase=STOP_PHRASE,time=stop_authorized_at,guest_stop=GUEST,stop_rva=RVA,candidate_sha256=SHA))
        save(out/'authorization.json',auth)
        dependencies=[pathlib.Path(p) for p in s['dependencies']]
        cap,l=construct(out,plan,lambda tag:desktop.check(out,tag),dependencies)
        A,R=l.D.Assets,l.D.R
        import graphics_backend as G
        protected=A.verify();A.check_writable(sandbox)
        shutil.copytree(A.source(),sandbox)
        before=A.inventory(sandbox)
        env=environment(sandbox);G.environment(env,out)
        helper=next(p for p in dependencies if p.name=='dmusic_helper.exe')
        env.update(XRT_BINARY=str(EXE),XRT_DMUSIC_BACKEND='ipc',XRT_DMUSIC_HELPER=str(helper),XRT_ASSET_MANIFEST=str(A.DEFAULT_MANIFEST),
                   XRT_STOP_FIRST_LEVEL_TICK='1',XRT_EVENT_STREAM=str(out/'runtime-stream.raw.bin'),XRT_D3D8_DIR=str(G.verified_pair('x64')))
        cmd=[str(EXE),'--guest',str(sandbox/'System/Unreal2.exe'),'--log',str(out/'xrt.log'),'--report',str(out/'runtime-report.json'),
             '--run-id',ident,'--timeout-ms','60000','--','CS_Intro.un2','-windowed','-nosound','-NOMMX','-NOSSE']
        save(out/'launch-profile.json',dict(command=cmd,cwd=str(sandbox/'System'),environment=env,authorization=auth,sandbox_before=before,protected=protected))
        save(out/'debugger-plan.json',plan)
        input_before=dict(state=desktop.owner.V.state(),physical_clip=desktop.expected['clip'])
        cleanup_dir=out/'input-cleanup';cleanup_dir.mkdir()
        cancelled=False
        def cancel(*_):
            nonlocal cancelled
            cancelled=True
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,cancel)
        if hasattr(signal,'SIGBREAK'):signal.signal(signal.SIGBREAK,cancel)
        def stop():return cancelled or (O/'STOP').exists() or (core.HOME/'STOP').exists()
        result=dict(passed=False,classification='unclassified-correctness-failure',retry=False)
        attempted=False
        try:
            with R.CaseLock('level'),R.CaseLock('graphics-client-session'),DesktopGamma(out):
                core.require(not l.V.P.processes(),'existing game/helper process')
                desktop.check(out,'before-launch')
                core.require(time.time()<expiry and not stop(),'authorization expired/stopped')
                # Reserve durably before CreateProcess. Both the old ledger and
                # this exclusive one-shot marker survive failure or interruption.
                ledger=execution_gate()
                ledger.append('setres-owner-authorized',batch=auth,seal_sha256=core.sha(O/'seal.json'))
                with (O/'OWNER-ATTEMPT-CONSUMED.json').open('x') as f:
                    json.dump(auth,f,indent=2);f.flush();os.fsync(f.fileno())
                ledger.claim(dict(id=ident),dict(kind='genuine',sha256=SHA),auth)
                attempted=True
                with (out/'stdout.bin').open('xb') as stdout,(out/'stderr.bin').open('xb') as stderr:
                    cap.run(cmd,cwd=sandbox/'System',env=env,stdout=stdout,stderr=stderr,timeout=60,stop=stop)
                audit(out,cap)
                result.update(passed=True,classification='initial-setres-completion')
        except BaseException as e:
            result.update(error=str(e),traceback=traceback.format_exc(),classification=classify_failure(e))
        finally:
            save(out/'cleanup.json',getattr(cap,'cleanup',dict(passed=False,launch_started=False)))
            desktop.owner.RUN=cleanup_dir
            try:
                desktop.owner.restore_and_check(input_before)
                core.require(A.verify()==protected,'protected assets changed')
                after=A.inventory(sandbox);A.check_run_inputs(before,after);save(out/'sandbox-after.json',after)
                for path,digest in s['files'].items():core.require(core.sha(path)==digest,'post-run sealed identity changed')
                stream=out/'runtime-stream.raw.bin'
                if stream.exists():
                    raw=stream.read_bytes();core.require(len(raw)%448==0,'partial committed stream')
                    events=[json.loads(raw[i:i+448].split(b'\0',1)[0]) for i in range(0,len(raw),448)]
                    core.require([e['seq'] for e in events]==list(range(1,len(events)+1)) and not any(e.get('truncated') for e in events),'runtime stream gaps/truncation')
                    snapshot=out/'runtime-events.raw.bin'
                    if snapshot.exists():core.require(snapshot.read_bytes()==raw,'stream/stopped-memory mismatch')
                    save(out/'runtime-stream-summary.json',dict(committed_records=len(events),stopped_memory_equal=snapshot.exists()))
                if result['passed']:
                    core.require(stream.exists() and (out/'runtime-events.raw.bin').exists(),'complete stopped stream required')
                desktop.check(out,'after-cleanup')
                core.require(getattr(cap,'cleanup',{}).get('passed') is True,'cleanup unverified')
            except BaseException as e:result.update(passed=False,classification='safety-integrity-failure',cleanup_error=str(e))
            result.update(genuine_launches=int(attempted),strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained',gameplay_verified=False)
            save(out/'result.json',result)
            if attempted:
                ledger.append('setres-attempt-result',request_id=ident,evidence=str(out),result=result)
                if not result['passed']:
                    ledger.append('operational-transition',state='SAFETY HALT' if result['classification']=='safety-integrity-failure' else 'DIAGNOSTIC HOLD',
                                  hold=dict(scope=SCOPE,reason=result.get('cleanup_error',result.get('error','failed milestone')),recoverable=False,request_id=ident))
                    save(O/'HALTED.json',result)
        print(json.dumps(dict(result=result,evidence=str(out)),indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['--help']:
        print('owner.py launch-once: requires separate local stop-scope authorization and a fresh one-shot launch phrase; one fixed candidate, at most 60 seconds.')
    else:
        core.require(sys.argv[1:]==['launch-once'],'only the exact launch-once owner command is accepted')
        run_once()
