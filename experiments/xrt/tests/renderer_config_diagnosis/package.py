"""Reviewable same-boundary owner package; no policy/breakpoint expansion or launch."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def gates():
    for name in ['raw-entry-verification.json','object-layout-verification.json','original-pe-analysis.json','field-sources.json',
        'boolean-characterization.json','runtime-guard-validation.json','source-change.json','candidate-identity.json','stop-mapping.json',
        'observer-tests.json','supervisor-tests.json','field-debugger-validation.json','debugger-validation.json']:
        core.require(read(O/name)['passed'],'required gate failed: '+name)
    original=core.tree(LAST/'runtime');fresh=core.tree(RT)
    core.require([n for n in original if original[n]!=fresh[n]]==['integrated_renderer.inc'],'unrelated runtime change')
    core.require(core.sha(RT/'batch_cases.inc')==core.sha(LAST/'runtime/batch_cases.inc'),'native tuple allowlist changed')
    before=read(PRIOR/'configuration-profile.json');after=read(O/'configuration-profile.json')
    core.require([k for k,v in before['fields'].items() if after['fields'][k]!=v]==['0x40d0'] and after['fields']['0x40d0']==32,'profile change scope')
    core.require(after['caps']==before['caps'] and after['calls']==before['calls'] and after['total_calls']==before['total_calls'],'D3D profile changed')
    from mapping import sequence
    core.require(len(sequence())==240 and sum(q['slot']>0 for q in sequence())==239,'238 configured calls plus material/resize inventory')
    core.require((H/'profile_sequence.py').read_text()==(H.parent/'setres_initial_completion/profile_sequence.py').read_text(),'ordered renderer profile changed')
    core.require(read(O/'stop-mapping.json')['guest_stop']==read(LAST/'stop-mapping.json')['guest_stop']==GUEST,'stop scope expansion')


def package():
    gates();core.require(not (H/'owner.py').exists(),'retain owner package')
    s=(H.parent/'setres_initial_completion/owner.py').read_text()
    s=s.replace("read(O/'source-change.json')['changed']==['xrt_loader.c'] and read(O/'paired-debugger-validation.json')['passed']", "read(O/'source-change.json')['changed']==['integrated_renderer.inc'] and read(O/'field-debugger-validation.json')['passed'] and read(O/'boolean-characterization.json')['passed']")
    s=s.replace("This separate local milestone proposes a stop before initial WinDrv 11104BF8. The production supervisor endpoint remains unchanged.","This new candidate uses the same initial WinDrv 11104BF8 stop. No breakpoint or production policy is expanded.")
    s=s.replace("'safety-integrity-failure' if isinstance(e,core.IntegrityFailure) else 'unclassified-correctness-failure'","classify_failure(e)")
    at=s.index('def validate_seal():')
    s=s[:at]+'''def classify_failure(error):
    if isinstance(error,core.IntegrityFailure):return 'safety-integrity-failure'
    if isinstance(error,core.Rejected) and str(error).startswith('renderer configuration diagnostic stop:'):
        return 'diagnostic-configuration-stop'
    return 'unclassified-correctness-failure'


'''+s[at:]
    (H/'owner.py').write_text(s)
    resolved_hold()
    print('Same-boundary one-shot owner source prepared after gates; no game authorization or execution.',flush=True)


def resolved_hold():
    ledger=core.Ledger(core.HOME/'ledger.jsonl');transition=[r for r in ledger.rows if r['kind']=='operational-transition'][-1]
    core.require(transition['sequence']==88 and transition['hold']['request_id']=='bfa1bae0-044b-42bc-aa73-30d1894c2a33' and transition['state']=='DIAGNOSTIC HOLD','changed/unrelated diagnosed hold')
    paths=[LAST/'HALTED.json',LAST/'OWNER-ATTEMPT-CONSUMED.json',ATTEMPT/'result.json',O/'renderer-fields.json',O/'source-change.json',
        O/'boolean-characterization.json',O/'runtime-guard-validation.json',O/'field-debugger-validation.json',O/'build.json',O/'object-lineage.json',O/'stop-mapping.json']
    if (O/'resolved-hold.json').exists():
        import shutil,uuid
        history=O/'receipt-history';history.mkdir(exist_ok=True)
        shutil.copy2(O/'resolved-hold.json',history/(str(uuid.uuid4())+'.json'))
    save(O/'resolved-hold.json',dict(passed=True,transition=transition,ledger_sha256=core.sha(ledger.path),hold_preserved=True,candidate_sha256=SHA,guest_stop=GUEST,
         evidence={str(p):core.sha(p) for p in paths},resolution='Measured exact raw UseTrilinear 0x20 profile; complete per-field observer evidence; same existing initial return stop; no global hold reset',genuine_launches=0))


if __name__=='__main__':
    if sys.argv[1:]==['refresh-receipt']:resolved_hold()
    else:
        core.require(not sys.argv[1:],'package subcommand');package()
