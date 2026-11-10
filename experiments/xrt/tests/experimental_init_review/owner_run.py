"""Explicit owner console only. This file is prepared, never invoked by review."""
from pathlib import Path
import sys,uuid,time,os
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
from physical_audit import W,O,F,P,core,read,save,digest,require,A
sys.path.insert(0,str(H.parent/'final_init_review'))
from launch_adapter import prepare
from supervisor.environment import Desktop
from supervisor.windows import Exclusive,FilePins

def authorize(typed,expected,console):
    require(console and typed==expected,'separate physical-console authorization absent')

def verify_seal():
    seal=read(O/'execution-review-seal.json')
    for p,d in seal['files'].items():require(digest(p)==d,'reviewed execution input changed: '+p)
    for p,d in seal['host_files'].items():require(digest(p)==d,'qualified host dependency changed: '+p)
    identity=read(O/'observer-identity.json');policy=read(O/'experimental-policy.json')
    require(identity['sources']==core.tree(H) and digest(O/'observer-identity.json')==policy['observer_identity_sha256'],'policy/observer/source binding')
    require(seal['host_files']==identity['qualified_host_files'],'qualified host inventory dropped or changed')
    require(identity['supervisor_inventory']==core.tree(W/'tools/xrt/supervisor') and identity['practical_observer_inventory']==core.tree(P),'observer module inventory changed')
    baseline=read(W/'out/recovery/practical-init-20261031-01/build.json')
    require(core.tree(W/'experiments/xrt/gen')==baseline['generated'],'generated source inventory changed')
    require(all(seal['files'].get(p)==d for p,d in identity['retained_execution_inputs'].items()),'execution manifest dropped a reviewed input')
    expected='AUTHORIZE ONE EXPERIMENTAL INIT '+policy['candidate_sha256']+' POLICY '+digest(O/'experimental-policy.json')+' OBSERVER '+digest(O/'observer-identity.json')+' 60 SECONDS NO RETRY BEFORE 1090ED5C'
    require(read(O/'owner-authorization.json')['console_phrase']==expected,'console policy/observer binding')
    require(read(O/'readiness.json')['technical_readiness']=='READY_FOR_SEPARATE_OWNER_AUTHORIZATION','technical readiness not passed')
    import review as prepared
    prepared.verify()
    return seal

def owner_run():
    # Always obtain fresh physical observations. Never reuse old batch authority.
    seal=verify_seal();desktop=Desktop();control=O/'owner-control';control.mkdir(exist_ok=True)
    pre=control/('preflight-'+str(uuid.uuid4()));pre.mkdir()
    desktop.check(pre,'first');desktop.check(pre,'second')
    policy=read(O/'experimental-policy.json');procedure=read(O/'owner-authorization.json')
    print('One genuine Init attempt, 60 seconds, no retry. Historical strict failures remain FAILED.')
    print('This accepts only the exact unresolved risks in experimental-policy.json, SHA256 '+digest(O/'experimental-policy.json'))
    print('Stop: BEFORE guest 0x1090ED5C. No gameplay, normalization, policy replacement or retry.')
    print('Type exactly: '+procedure['console_phrase'],flush=True)
    authorize(input(),procedure['console_phrase'],sys.stdin.isatty())
    # No reservation, queue publication or candidate launch occurs before above.
    with Exclusive(core.HOME/'supervisor.lock'):
        require(not (core.HOME/'HALTED.json').exists() and not (core.HOME/'STOP').exists(),'existing genuine halt/stop requires owner review; never cleared here')
        require(not list((core.HOME/'processing').glob('*.json')),'existing interrupted genuine request')
        state=read(core.HOME/'operational-state.json');require(state['state']=='RUNNING','existing genuine diagnostic/safety hold')
        require(not (control/'CONSUMED.json').exists(),'this one-attempt authorization was already consumed')
        seal=verify_seal();ident=read(F/'candidate-identity.json');plan=read(O/'candidate-plan.json')
        ledger=core.Ledger(core.HOME/'ledger.jsonl')
        require(not any(r['kind']=='launch-claimed' and r.get('sha256')==ident['sha256'] for r in ledger.rows),'candidate previously consumed')
        ident_id=str(uuid.uuid4());out=O/('genuine-'+ident_id);out.mkdir();sandbox=W/'sandbox_cmp'/('experimental-init-'+ident_id);sandbox.mkdir()
        stop=lambda:(control/'STOP').exists() or (core.HOME/'STOP').exists()
        require(not stop(),'local stop present')
        request=dict(id=ident_id,expires_at=time.time()+300,timeout_seconds=60,expected_stop=dict(kind='permanent-stop'))
        batch=dict(id=str(uuid.uuid4()),genuine_limit=1)
        manifest=dict(kind='genuine',sha256=ident['sha256'],pdb_sha256=ident['pdb_sha256'],executable=str(Path(ident['executable']).relative_to(W)),dependencies=[str(Path(p).relative_to(W)) for p in ident['dependencies']])
        helper=[p for p in ident['dependencies'] if Path(p).suffix.lower()=='.exe'];require(len(helper)==1,'one pinned DirectMusic helper')
        runtime_seal=dict(helper=dict(path=str(Path(helper[0]).relative_to(W))))
        with FilePins() as pins:
            for p,d in {**seal['files'],**ident['dependencies'],ident['executable']:ident['sha256'],str(Path(ident['executable']).with_suffix('.pdb')):ident['pdb_sha256']}.items():pins.pin(Path(p),d)
            import common
            legacy=common.legacy()
            require(not legacy.V.P.processes(),'another game/helper process exists')
            desktop.check(out,'before-reservation')
            # This shared ledger reservation prevents any later production retry
            # of the exact SHA, even if preparation/launch subsequently fails.
            ledger.claim(request,manifest,batch)
            save(control/'CONSUMED.json',dict(candidate_sha256=ident['sha256'],evidence=str(out),retry=False))
            save(out/'owner-authorization.json',dict(policy_sha256=digest(O/'experimental-policy.json'),observer_seal_sha256=digest(O/'execution-review-seal.json'),phrase=procedure['console_phrase'],launches=1,timeout_seconds=60,retry=False,production_policy_changed=False))
            run,source,diff=prepare();(out/'isolated-launch.py.txt').write_bytes(source.encode('utf-8'))
            try:
                result=run(manifest,request,out,sandbox,stop,desktop,runtime_seal)
                save(out/'result.json',result)
            except BaseException as e:
                save(out/'execution-error.json',dict(error=repr(e),retry=False))
                raise
    print('Bounded attempt ended. Preserve all evidence for independent audit; no retry.',out,flush=True)

if __name__=='__main__':owner_run()
