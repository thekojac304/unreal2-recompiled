"""Build an independently gated owner proposal; never launches or authorizes."""
import ast
import shutil
from recheck import HERE,OUT,PRIOR,WORK,core

DEST=OUT/'continuation-proposal'
OLD=HERE.parent/'setres_initial_completion'

def main():
    for name in ('candidate-identity.json','linked-adapter-audit.json','preservation-after.json'):
        shutil.copy2(OUT/name,DEST/name)
    shutil.copy2(OUT/'identity_verifier.py',DEST/'identity.py')
    for name in ('gamma_guard.py','attach_audit.py'):shutil.copy2(OLD/name,DEST/name)
    shutil.copy2(HERE/'continuation_audit.py',DEST/'continuation_audit.py')
    (DEST/'common.py').write_text('''"""Fixed semantic initial SetRes proposal identity. No execution on import."""
from pathlib import Path
import pathlib
import sys
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
W=O.parents[3]
H=W/'experiments/xrt/tests/semantic_compat'
PRIOR=W/'out/recovery/renderer-config-diagnosis-20261029-01'
RT=W/'out/recovery/semantic-compat-20261029-01/runtime'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core
from supervisor.environment import load
def read(p):return core.read_large(p)
def save(p,v):core.atomic(p,v)
GUEST=0x11104bf8
SCOPE='semantic-initial-setres-before-11104bf8'
def identity():
    b=read(O/'build.json');return Path(b['root'])/'xrt_ucc.exe',b['binary_sha256'],b['pdb_sha256']
EXE,SHA,PDB=identity()
RVA=read(O/'stop-mapping.json')['stop_rva']
PHRASE='AUTHORIZE ONE INITIAL SETRES '+SHA[:16].upper()+' BEFORE 11104BF8 FOR 60 SECONDS'
STOP_PHRASE='AUTHORIZE INITIAL SETRES STOP BEFORE 11104BF8 FOR '+SHA[:16].upper()+' ONLY'
def legacy():
    m=load('semantic_retained_debugger',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    m.V.EXE,m.V.EXPECTED,_=identity();return m
''')
    (DEST/'mapping.py').write_text('''"""Use the sealed independently disassembled plan; never select another stop."""
from common import *
def resolve():
    p=read(O/'stop-mapping.json')
    core.require(p['passed'] and p['sha256']==SHA and p['stop_rva']==RVA and p['stop_bytes']=='895f44' and p['device_layout_verified'],'fixed verified stop plan')
    return p
''')
    source=(OLD/'owner.py').read_text()
    start=source.index('def audit(out, cap):');end=source.index('\ndef run_once():',start)
    source=source[:start]+'from continuation_audit import audit\n\n'+source[end:]
    source=source.replace("core.tree(H)==s['implementation']", "{p.name:core.sha(p) for p in O.glob('*.py')}==s['implementation']")
    source=source.replace("core.require(read(O/'source-change.json')['changed']==['xrt_loader.c'] and read(O/'paired-debugger-validation.json')['passed'],'call-aware evidence change unqualified')", "core.require(read(O/'physical-qualification.json')['functional_qualified'] and read(O/'observer-change.json')['passed'],'semantic physical/observer qualification incomplete')")
    source=source.replace("                audit(out,cap)\n                result.update(passed=True,classification='initial-setres-completion')", "                outcome=audit(out,cap)\n                result.update(passed=outcome=='initial-setres-complete',measurement_complete=True,classification=outcome)")
    source=source.replace("core.require(s['passed'] and", "core.require(s['ready_for_owner_authorization'] and not s['genuine_authorized'] and s['retry'] is False and s['guest_stop']==GUEST and s['stop_rva']==RVA and s['stop_bytes']=='895f44' and s['passed'] and")
    ast.parse(source);(DEST/'owner.py').write_text(source)
    old=core.read_large(WORK/'out/recovery/setres-initial-completion-20261029-01/resolved-hold.json')
    ledger=core.Ledger(core.HOME/'ledger.jsonl')
    baseline=core.read_large(OUT/'preservation.json')['trees'][str(core.HOME)]['ledger.jsonl']
    core.require(core.sha(ledger.path)==baseline,'production ledger changed during this qualification')
    transition=[r for r in ledger.rows if r['kind']=='operational-transition'][-1]
    core.require(transition['sequence']==92 and transition['state']=='DIAGNOSTIC HOLD' and transition['hold']['request_id']=='5790fadb-42f2-40aa-b04b-71cd7fadb390' and transition['hold']['reason']=='fatal before required stop; no continuation: renderer profile field 0x40d0 refused','unrelated latest production hold')
    for p,d in old['evidence'].items():core.require(core.sha(p)==d,'prior hold diagnosis changed')
    for name in ('semantic-changes.json','guard-inventory.json','source-change.json'):
        path=PRIOR/name;old['evidence'][str(path)]=core.sha(path)
    for name in ('HALTED.json','OWNER-ATTEMPT-CONSUMED.json','owner-5790fadb-42f2-40aa-b04b-71cd7fadb390/result.json'):
        path=WORK/'out/recovery/renderer-config-diagnosis-20261029-01'/name;old['evidence'][str(path)]=core.sha(path)
    old.update(transition=transition,ledger_sha256=baseline,candidate_sha256=core.read(DEST/'build.json')['binary_sha256'],resolution='Scoped semantic initial SetRes observation proposed after full profile guard refactor; latest sequence-92 diagnostic hold remains unchanged; separate local owner stop and launch authorization required',genuine_launches=0)
    core.atomic(DEST/'resolved-hold.json',old)
    core.atomic(DEST/'package-source.json',dict(passed=True,original_owner=str(OLD/'owner.py'),original_owner_sha256=core.sha(OLD/'owner.py'),
        changes=['exact semantic candidate/common','semantic physical and observer gates','dynamic evidence pairing without fixed call profile','zero/nonzero SetRes outcomes retained'],
        retained=['two local phrases','immutable pins','production and fixture exclusive locks','fresh copied sandbox/protected snapshot','durable prelaunch consumption','Job/watchdog','permanent stop readback','parent gamma/input restoration','stream/memory comparison','zero Job processes'],genuine_launches=0))
    print('Owner proposal written; sealed physical gate required before any authorization',flush=True)

if __name__=='__main__':main()
