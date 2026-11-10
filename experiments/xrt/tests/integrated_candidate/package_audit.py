"""Independently audit immutable physical fixture recipes and exact adapter expansion."""
import sys,re,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from gpu_source import source
from supervisor import fixture_profiles as F
from supervisor.development import read_status
from supervisor.service import verify_seal

def validate(row):
    request=dict(candidate_id=row['candidate_id'],candidate_sha256=row['manifest_sha256'],family='renderer-group',
                 parameters=row['parameters'],profile='fast-development')
    return F.validate_candidate(request)

def main():
    package=read(O/'gpu-qualification-package.json');assert package['runtime']==core.tree(RT)
    results=[]
    for row in package['candidates']:
        candidate=validate(row);F.verify_identities(row['adapter_sources'])
        root=F.candidate_path(candidate['id']).parent;src=root/'sources';runtime=src/'runtime'
        existing={p.name for p in runtime.iterdir()}
        def expand(path,stack=()):
            assert path.name not in stack
            def include(match):
                name=match[1]
                if name in existing:return match[0]
                return '\n'+expand(RT/name,(*stack,path.name))+'\n'
            return re.sub(r'^#include "([^"]+)"',include,path.read_text(),flags=re.M)
        checked=[]
        for p in runtime.iterdir():
            if (RT/p.name).is_file():
                assert p.read_text()==expand(RT/p.name),p
                checked.append(p.name)
        fixture=(src/'fixture.c').read_text()
        assert source() in fixture
        assert '1,1,75,1,0,0};HRESULT hr;' in fixture and 'resource_matrix();count=gcalls;' in fixture
        assert 'pixel=0xff300000|(y<<8)|x' in fixture
        assert 'VirtualAlloc(NULL,0x800000,' in fixture
        assert 'GetFrontBuffer(dev,(D8Surface*)ga[1])' in fixture
        assert 'rcall(30,2,dev,U(0))' in fixture
        exe=root/'build/fixture.exe'
        results.append(dict(candidate_id=candidate['id'],parameters=candidate['parameters'],manifest=str(F.candidate_path(candidate['id'])),
            manifest_sha256=row['manifest_sha256'],executable=str(exe),sha256=core.sha(exe),
            adapter_expansions_verified=checked,build_record=candidate['build_record'],verified=True))
    assert [r['parameters'] for r in results]==[dict(group=1,arch=a,variant=v) for a,v in (('x86','native'),('x64','native'),('x64','translated'))]
    seal=read(F.HOME/'qualification.json');verify_seal(seal)
    ledger=core.Ledger(F.HOME/'ledger.jsonl');status=read_status()
    save(O/'physical-package-audit.json',dict(passed=True,candidates=results,
        qualification_seal_verified=True,qualification_sha256=core.sha(F.HOME/'qualification.json'),
        authorization_ledger_sha256=core.sha(ledger.path),authorization_ledger_rows=len(ledger.rows),status=status,
        grant_expired=time.time()>=status['batch']['expires_at'],
        pending={n:sorted(p.name for p in (F.HOME/n).glob('*.json')) for n in ('requests','processing')},
        latches={n:(F.HOME/n).exists() for n in ('STOP','HALTED.json')},
        collector_schema_mismatch='Certain: legacy group_observations expects ownership/create/call kinds; these fixtures emit semantic/resource/transfer kinds. Preserve its verdict.',
        requests_submitted=0,physical_executions=0,genuine_launches=0))
    print('Three immutable fixture recipes, expanded adapter sources, objects, toolchains, seal and ledger PASS',flush=True)

if __name__=='__main__':main()
