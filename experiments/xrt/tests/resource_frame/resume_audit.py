"""Read-only readiness verification. No service startup, submission or game launch."""
import datetime
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from supervisor import fixture_profiles as F
from supervisor.development import read_status
from supervisor.service import verify_seal


def main():
    out = W / 'out/recovery' / ('resource-gpu-readiness-' + str(uuid.uuid4()))
    out.mkdir()
    package = read(O / 'gpu-qualification-package.json')
    assert core.tree(RT) == package['runtime']
    results = []
    for row in package['candidates']:
        request = dict(candidate_id=row['candidate_id'], candidate_sha256=row['manifest_sha256'],
                       family='renderer-group', parameters=row['parameters'], profile='fast-development')
        candidate = F.validate_candidate(request)
        F.verify_identities(row['adapter_sources'])
        plan = F.plan(candidate['family'], candidate['parameters'], F.candidate_path(candidate['id']).parent)
        results.append(dict(candidate_id=candidate['id'], parameters=candidate['parameters'],
                            manifest=str(F.candidate_path(candidate['id'])), manifest_sha256=row['manifest_sha256'],
                            executable=str(plan[0]['exe']), executable_sha256=core.sha(plan[0]['exe']),
                            inventory_files=len(candidate['files']), verified=True))
    assert [r['parameters'] for r in results] == [dict(group=1, arch=a, variant=v)
        for a, v in [('x86', 'native'), ('x64', 'native'), ('x64', 'translated')]]
    seal = read(F.HOME / 'qualification.json')
    assert seal['passed'] is True
    verify_seal(seal)
    status = read_status()
    ledger = core.Ledger(F.HOME / 'ledger.jsonl')
    authorizations = [r for r in ledger.rows if r['kind'] == 'fixture-batch-authorized'
                      and r['batch']['id'] == status['batch']['id']]
    assert len(authorizations) == 1 and authorizations[0]['owner_console'] is True
    now = time.time()
    pending = {name: sorted(p.name for p in (F.HOME / name).glob('*.json'))
               for name in ('requests', 'processing')}
    latches = {name: (F.HOME / name).exists() for name in ('STOP', 'HALTED.json')}
    identity_module = load('readiness_identity', H.parent / 'renderer_config_diagnosis/identity.py')
    identity_module.O = O
    identity_module.RT = RT
    identity_module.EXE, identity_module.SHA, identity_module.PDB = identity()
    verified = identity_module.verify()
    save(out / 'candidate-identity.json', verified)
    preservation = read(O / 'preservation.json')
    assert all(core.tree(Path(p)) == tree for p, tree in preservation['trees'].items())
    assert A.verify() == preservation['protected']
    mapping = read(O / 'stop-mapping.json')
    design = read(O / 'continuation-design.json')
    assert mapping['sha256'] == identity_module.SHA == design['sha256']
    assert mapping['guest_stop'] == design['guest_stop'] == GUEST
    assert mapping['stop_rva'] == design['stop_rva'] and mapping['stop_bytes'] == design['stop_bytes']
    assert core.sha(design['observer_source']) == design['observer_sha256']
    assert not design['observer_installed'] and not design['execution_authorized']
    contracts = read(O / 'contracts.json')
    result = dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  passed=True, fixtures=results, service=status,
                  qualification_seal_verified=True, qualification_sha256=core.sha(F.HOME / 'qualification.json'),
                  ledger_verified=True, ledger_rows=len(ledger.rows), authorization_record=authorizations[0],
                  authorization_expired=now >= status['batch']['expires_at'],
                  authorization_expires_utc=datetime.datetime.fromtimestamp(status['batch']['expires_at'], datetime.timezone.utc).isoformat(),
                  pending=pending, latches=latches, preservation_verified=True,
                  continuation=design, directinput_strict_differences=contracts['directinput_strict_differences'],
                  strict_x87='FAILED retained separately', wndproc='FAILED retained separately',
                  requests_submitted=0, gpu_executions=0, genuine_launches=0,
                  owner_action_required=status['state']=='stopped' or now >= status['batch']['expires_at'])
    save(out / 'readiness.json', result)
    print(out, flush=True)
    print('All three fixture recipes, complete provenance, qualification seal, ledger, candidate identity and preservation PASS', flush=True)
    print('Service:', status['state'], 'authorization expired:', result['authorization_expired'], 'pending:', pending, 'latches:', latches, flush=True)


if __name__ == '__main__':
    main()
