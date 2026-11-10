"""Create the owner launcher only after non-game qualification gates pass."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def gates():
    names=['candidate-identity.json','stop-mapping.json','offline-construction.json','source-change.json',
        'instrumentation-validation.json','debugger-validation.json','paired-debugger-validation.json',
        'native-x86-abi-validation.json','controller-tests-final.json','supervisor-tests.json',
        'helper-qualification.json','cache-control-flow/result.json']
    for name in names:core.require(read(O/name).get('passed') is True,'required gate failed: '+name)
    source=read(O/'source-change.json');core.require(source['runtime']==core.tree(RT),'staged source changed')
    before=core.tree(PRIOR/'runtime');after=core.tree(RT)
    core.require([k for k,v in before.items() if after[k]!=v]==['xrt_loader.c'],'runtime method/profile changes forbidden')
    core.require(set(after)-set(before)=={'setres_evidence.inc'},'unrelated source addition')
    frozen=(H/'profile_sequence.py').read_text()
    old=(W/'experiments/xrt/tests/setres_import_continuation/mapping.py').read_text()
    core.require(frozen==old[old.index('def sequence():'):],'238 profile order/tuple logic changed')
    from mapping import sequence
    calls=sequence();core.require(len(calls)==240 and sum(q['slot']>0 for q in calls)==239,'profile/material/resize count')
    save(O/'owner-package-eligibility.json',dict(passed=True,gates=names,configured_calls=238,
         renderer_sources_identical=True,profile_logic_identical=True,genuine_launches=0))


def owner():
    gates();core.require(not (H/'owner.py').exists(),'preserve existing owner source')
    s=(W/'experiments/xrt/tests/setres_import_continuation/owner.py').read_text()
    start=s.index('def execution_gate():');end=s.index('\ndef audit(out, cap):',start)
    replacement='''def execution_gate():
    core.require(not (core.HOME/'HALTED.json').exists() and not (core.HOME/'STOP').exists() and not (O/'STOP').exists(),'existing safety/local stop remains active')
    core.require(not list((core.HOME/'processing').glob('*.json')),'interrupted production request requires investigation')
    ledger=core.Ledger(core.HOME/'ledger.jsonl');resolved=read(O/'resolved-hold.json')
    core.require(core.sha(ledger.path)==resolved['ledger_sha256'],'ledger changed since scoped diagnosis; prepare again')
    transitions=[r for r in ledger.rows if r['kind']=='operational-transition']
    core.require(transitions and transitions[-1]==resolved['transition'],'unrelated or changed hold; no reset')
    core.require(resolved['candidate_sha256']==SHA and resolved['guest_stop']==GUEST and resolved['hold_preserved'],'wrong scoped resolution')
    for path,digest in resolved['evidence'].items():core.require(core.sha(path)==digest,'scoped resolution evidence changed')
    core.require(read(O/'source-change.json')['changed']==['xrt_loader.c'] and read(O/'paired-debugger-validation.json')['passed'],'call-aware evidence change unqualified')
    from identity import consumed
    consumed()
    return ledger


from attach_audit import audit as audit_attach

'''
    s=s[:start]+replacement+s[end:]
    s=s.replace("attach_count=audit_attach(events)","attach_count=audit_attach(events)['pairs']\n    import evidence\n    evidence.runtime_pair(events,next(r for r in rows if r['kind']=='setres_entry_raw'),next(r for r in rows if r['kind']=='initial_setres_return_raw'))")
    s=s.replace('0x0696D2CD','0x11104BF8').replace('0x0696d2cd','0x11104bf8').replace('0696D2CD','11104BF8')
    s=s.replace("'setres-completion'","'initial-setres-completion'")
    anchor="print('Type exactly: '+PHRASE,flush=True)"
    core.require(s.count(anchor)==1,'separate stop authorization insertion')
    s=s.replace(anchor,"""print('This separate local milestone proposes a stop before initial WinDrv 11104BF8. The production supervisor endpoint remains unchanged.',flush=True)
        print('Separately authorize this hardware-stop scope by typing: '+STOP_PHRASE,flush=True)
        core.require(input().strip()==STOP_PHRASE,'separate owner stop authorization not accepted')
        stop_authorized_at=time.time()
        print('Type exactly: '+PHRASE,flush=True)""")
    s=s.replace('owner_console=True,phrase=PHRASE)','owner_console=True,phrase=PHRASE,endpoint_authorization=dict(phrase=STOP_PHRASE,time=stop_authorized_at,guest_stop=GUEST,stop_rva=RVA,candidate_sha256=SHA))')
    s=s.replace("core.require(input().strip()==PHRASE,'fresh endpoint authorization not accepted')", "core.require(input().strip()==PHRASE,'fresh endpoint authorization not accepted')\n        core.require(time.time()-stop_authorized_at<=300,'separate stop authorization expired')")
    s=s.replace("print('owner.py launch-once: requires the fresh exact local owner phrase; launches one fixed candidate for at most 60 seconds.')", "print('owner.py launch-once: requires separate local stop-scope authorization and a fresh one-shot launch phrase; one fixed candidate, at most 60 seconds.')")
    (H/'owner.py').write_text(s)
    resolved_hold()
    print('One-shot owner source created after qualification gates; diagnosed hold and consumed identities retained.',flush=True)


def resolved_hold():
    core.require(read(O/'paired-debugger-validation.json')['passed'] and read(O/'instrumentation-validation.json')['passed'],'evidence qualification incomplete')
    ledger=core.Ledger(core.HOME/'ledger.jsonl');transition=[r for r in ledger.rows if r['kind']=='operational-transition'][-1]
    core.require(transition['sequence']==84 and transition['state']=='DIAGNOSTIC HOLD' and transition['hold']['request_id']=='fa3b112f-189a-422b-ac3c-ea197a910de6','not the diagnosed consumed attempt hold')
    files=[OLD/'HALTED.json',OLD/'OWNER-ATTEMPT-CONSUMED.json',OLD/'owner-fa3b112f-189a-422b-ac3c-ea197a910de6/result.json',
        DIAG/'diagnosis.json',O/'source-change.json',O/'instrumentation-validation.json',O/'paired-debugger-validation.json',O/'stop-mapping.json',O/'build.json',O/'object-lineage.json']
    if (O/'resolved-hold.json').exists():
        import shutil,uuid
        history=O/'resolved-hold-history';history.mkdir(exist_ok=True)
        shutil.copy2(O/'resolved-hold.json',history/(str(uuid.uuid4())+'.json'))
    save(O/'resolved-hold.json',dict(passed=True,transition=transition,ledger_sha256=core.sha(ledger.path),hold_preserved=True,candidate_sha256=SHA,guest_stop=GUEST,
         evidence={str(p):core.sha(p) for p in files},resolution='Fresh evidence-only source change; call-aware initial return qualified with owned fixtures; separate owner stop/launch authorization pending',genuine_launches=0))


if __name__=='__main__':
    if sys.argv[1:]==['refresh-hold']:resolved_hold()
    else:
        core.require(not sys.argv[1:],'owner preparation subcommand')
        owner()
