"""Read-only gates for the October 28 owner continuation; no game launch path."""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[4]
PRIOR = W / 'out/recovery/postsplash-recovery-20261028-01'
GETOBJECT = W / 'out/recovery/getobject-recovery-20261028-01'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def files(root):
    return sorted(p for p in Path(root).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts)


def tree(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): sha(p) for p in files(root)}


def check(root, entries):
    for rel, expected in entries.items():
        assert sha(Path(root) / rel) == expected, ('hash mismatch', str(root), rel)


def owner_evidence():
    """Recompute the owner gates from raw records, not just result.passed."""
    check(PRIOR, read(PRIOR / 'artifact-manifest.json'))
    check(W, read(PRIOR / 'owner-fixture-identities.json'))
    fixture = read(PRIOR / 'owner-fixture-build.json')
    check(fixture['root'], fixture['binaries'])
    run = PRIOR / 'owner-init-audio-run'
    assert not (run / 'STOP.txt').exists()
    result = read(run / 'result.json')
    assert result['passed'] and result['genuine_sessions'] == 0
    assert result['production_timeout_ms'] == 10000
    assert result['native_parent_timeout_seconds'] == 14
    assert result['no_runtime_or_helper_change']
    assert len(result['runs']) == 3
    expected_cases = ['native-unguarded', 'native-guarded', 'ipc-production-helper']
    parsed = []
    for row, name, elapsed in zip(result['runs'], expected_cases, [265, 250, 250]):
        assert row == read(run / (name + '.json'))
        assert row['case'] == name and row['exit'] == 0 and not row['timeout']
        assert 0 < row['seconds'] < 14
        assert 'InitAudio enter path=8 channels=128 flags=63' in row['stdout']
        match = re.search(r'InitAudio return ([0-9a-f]{8}) object=(\d) elapsed_ms=(\d+)', row['stdout'])
        assert match and match[1] == '00000000' and match[2] == '1'
        assert int(match[3]) == elapsed and 'cleanup passed' in row['stdout']
        assert 'sandbox denied' not in row['stderr'].lower()
        assert Path(row['command'][0]).is_relative_to(Path(fixture['root']))
        parsed.append(dict(case=name, hresult=match[1], real_object=True, elapsed_ms=elapsed, exit=0))
    ipc = result['runs'][2]
    sequence = re.findall(r'DirectMusic IPC seq (\d+) op (\d+) id (\d+) status (\d+) result ([0-9a-f]+) out (\d+) type (\d+)', ipc['stderr'])
    assert [int(r[0]) for r in sequence] == list(range(1, 7))
    assert sequence[3] == ('4', '6', '2', '0', '00000000', '3', '3')
    assert sequence[4][1] == '19' and sequence[5][1] == '20'
    pinned = read(PRIOR / 'pinned-inputs.json')
    helper = pinned['inputs']['helper']
    assert sha(ipc['command'][1]) == helper['sha256'] == sha(helper['path'])
    env = load('continuation_owner_environment', W / 'out/recovery/session-aware-136-20261026-01/owner.py')
    fingerprints = []
    for name in ['initial', 'second', 'final']:
        raw = read(run / (name + '-environment.json'))
        fingerprints.append(env.environment_gate(raw))
    assert fingerprints[0] == fingerprints[1] == fingerprints[2] == result['baseline']
    initial = read(run / 'initial-state.json')
    final = read(run / 'final-state.json')
    assert initial == final and not final['processes']
    return dict(passed=True, runs=parsed, production_ipc_sequence_4_verified=True,
                helper_matches_pinned=True, production_timeout_ms=10000,
                environment_observations=3, environment_gate='A-candidate / owner WinSta0 Default / physical NVIDIA DisplayPort',
                baseline=fingerprints[0], cleanup=final, genuine_sessions=0)


def inputs():
    evidence = owner_evidence()
    preservation = read(PRIOR / 'preservation.json')
    assert preservation['passed']
    check(W, preservation['consumed_evidence'])
    check(W, read(PRIOR / 'current-sources.json'))
    build = read(PRIOR / 'build.json')
    assert build['passed'] and build['compiled_objects'] == 279 and build['reused_objects'] == 0
    check(build['root'], build['outputs'])
    assert tree(W / 'experiments/xrt/runtime') == build['runtime']
    assert tree(W / 'experiments/xrt/gen') == build['generated']
    assert sha(Path(build['root']) / 'xrt_ucc.exe') == build['binary_sha256']
    assert sha(Path(build['root']) / 'xrt_ucc.pdb') == build['pdb_sha256']
    for archive in preservation['archives']:
        assert sha(PRIOR / archive['path']) == archive['sha256']
    sandbox = read(PRIOR / 'sandbox-manifest.json')
    assert tree(sandbox['root']) == sandbox['files']
    metadata = {p.relative_to(Path(sandbox['root'])).as_posix():
                dict(directory=p.is_dir(), size=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns,
                     attributes=getattr(p.stat(), 'st_file_attributes', None))
                for p in sorted(Path(sandbox['root']).rglob('*'))}
    assert metadata == read(PRIOR / 'sandbox-metadata.json')
    for name in ['getobject-recovery-20261028-01', 'renderer-init-preparation-20261027-01']:
        assert (W / 'out/recovery' / name / 'GENUINE-ATTEMPT-CONSUMED.json').exists()
    sys.path.insert(0, str(W / 'tools/xrt'))
    import asset_boundary as assets
    import graphics_backend as graphics
    protected = assets.verify()
    assert protected == preservation['protected_assets']
    pinned = read(PRIOR / 'pinned-inputs.json')
    for path, expected in pinned['pinned_driver_files'].items():
        assert sha(path) == expected, path
    backend = {}
    for arch in ['x86', 'x64']:
        root = graphics.verified_pair(arch)
        backend[arch] = dict(root=str(root), hashes=graphics.HASHES[arch])
    assert backend == pinned['inputs']['backend']
    helper = pinned['inputs']['helper']
    assert sha(helper['path']) == helper['sha256']
    strict = read(PRIOR / 'strict-failures-retained.json')
    assert strict['x87'] == strict['wndproc_equality'] == 'FAILED'
    assert strict['original_assertions_unchanged'] and sha(strict['source']) == strict['sha256']
    for path, expected in strict['findings']['preserved_sources'].items():
        assert sha(path) == expected, path
    return dict(passed=True, assets=protected, helper=helper, backend=backend,
                binary_sha256=build['binary_sha256'], pdb_sha256=build['pdb_sha256'],
                owner_evidence=evidence, strict_x87='FAILED; retained separately',
                strict_wndproc_equality='FAILED; retained separately', genuine_sessions=0)


if __name__ == '__main__':
    verified = inputs()
    print(json.dumps({k: v for k, v in verified.items() if k != 'owner_evidence'}, indent=2))
    print('OWNER EVIDENCE / CANDIDATE / PROTECTED INPUTS PASS; NO GAME LAUNCHED')
