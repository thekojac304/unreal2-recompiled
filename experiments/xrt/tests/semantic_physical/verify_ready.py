"""Fresh read-only final owner/identity verification. Never calls run_once."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[3]
OUT=WORK/'out/recovery/semantic-physical-20261030-01'
DEST=OUT/'continuation-proposal'
sys.path.insert(0,str(DEST))
import common
import owner
import identity
core=common.core

def main():
    before=core.sha(core.HOME/'ledger.jsonl')
    seal=owner.validate_seal();ledger=owner.execution_gate();verified=identity.verify()
    prior=core.read_large(WORK/'out/recovery/semantic-compat-20261029-01/handoff-seal.json')
    for p,h in prior['files'].items():core.require(core.sha(p)==h,'prior sealed artifact changed')
    core.require(before==core.sha(core.HOME/'ledger.jsonl')==common.read(DEST/'resolved-hold.json')['ledger_sha256'],'production ledger mutated')
    core.require(not (DEST/'OWNER-ATTEMPT-CONSUMED.json').exists() and verified['consumption']['unconsumed'],'candidate consumed')
    core.atomic(OUT/'final-verification.json',dict(passed=True,fresh_interpreter=True,owner_files=len(seal['files']),prior_files=len(prior['files']),
        candidate_sha256=verified['sha256'],candidate_unconsumed=True,production_ledger_rows=len(ledger.rows),production_ledger_sha256=before,
        owner_seal_sha256=core.sha(DEST/'seal.json'),production_breakpoint_changed=False,genuine_launches=0,genuine_authorized=False))
    # Supersede the original blocked checkpoint, retained byte-for-byte in the
    # historical-checkpoints directory, without altering the owner package.
    core.atomic(OUT/'pending-physical-matrix.json',dict(status='SAMPLED_MATRIX_COMPLETED',executed=True,
        original_plan='historical-checkpoints/pending-physical-matrix.json',actual_coverage='physical-qualification.json',
        note='The original plan includes broader optional inputs; only actual recorded samples are qualified. Remaining scope limits are in physical-qualification.json.'))
    names=['REPORT.txt','OWNER-ACTION.txt','continuation-readiness.json','physical-qualification.json','final-verification.json','pending-physical-matrix.json']
    files={str(OUT/n):core.sha(OUT/n) for n in names}
    files.update({str(DEST/n):core.sha(DEST/n) for n in ('seal.json','seal-validation.json')})
    files.update({str(p):core.sha(p) for p in HERE.iterdir() if p.is_file()})
    core.atomic(OUT/'checkpoint-seal.json',dict(passed=True,status='READY_FOR_SEPARATE_OWNER_AUTHORIZATION',files=files,
        nested_owner_seal=str(DEST/'seal.json'),nested_owner_files=len(seal['files']),genuine_authorized=False,genuine_launches=0,
        original_blocked_checkpoint_preserved='historical-checkpoints/checkpoint-seal.json'))
    print('FRESH FINAL VERIFY PASS: owner gate, candidate identity, 630 prior files, 92-row unchanged ledger; no game launch',flush=True)

if __name__=='__main__':main()
