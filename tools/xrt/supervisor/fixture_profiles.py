"""Fixed disposable fixture catalog, build recipes and version-2 queue protocol.

Queue JSON selects a family and typed parameters. It never selects a program,
script, command line, environment, working directory, DLL or output path.
"""
import math
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from . import core

HOME = core.ROOT / 'out/desktop-fixtures'
CANDIDATES = core.ROOT / 'out/fixture-candidates'
SOURCES = core.ROOT / 'out/fixture-sources'
RENDERER = core.ROOT / 'experiments/xrt/tests/renderer_batch'
FROZEN = core.ROOT / 'out/recovery/renderer-evidence-20261029-03'
PROFILES = ('fast-development', 'formal-acceptance')
FAMILIES = ('collector-smoke', 'renderer-abi', 'renderer-group', 'renderer-batch-23')
KEYS = 'version id batch_id created_at expires_at objective profile family parameters candidate_id candidate_sha256 timeout_seconds'


def modules():
    # This location is sealed at startup. No import path comes from a request.
    if str(RENDERER) not in sys.path:
        sys.path.insert(0, str(RENDERER))
    import prepare_evidence as E
    import evidence_check as A
    import evidence_capture as C
    return E, A, C


def parameters(family, values, profile):
    core.require(profile in PROFILES and family in FAMILIES, 'unknown fixture profile/family')
    if family == 'renderer-batch-23':
        core.exact(values, '')
        core.require(profile == 'formal-acceptance', '23-process batch requires formal acceptance')
    elif family == 'collector-smoke':
        core.exact(values, 'arch case')
        core.require(profile == 'fast-development', 'smoke is development evidence only')
        core.require(values['arch'] in ('x86', 'x64'), 'architecture')
        core.require(values['case'] in ('normal', 'early-exit', 'linger', 'descendant'), 'smoke case')
    else:
        core.exact(values, 'group arch variant')
        core.require(profile == 'fast-development', 'focused fixtures are development evidence only')
        core.require(type(values['group']) is int and 1 <= values['group'] <= 7, 'renderer group 1..7')
        core.require(values['arch'] in ('x86', 'x64'), 'architecture')
        core.require(values['variant'] in ('native', 'translated'), 'variant')
        core.require(values['arch'] == 'x64' or values['variant'] == 'native', 'native x86/ native or translated x64 only')
    return values


def parse(data, batch, *, now=None):
    now = time.time() if now is None else now
    core.exact(data, KEYS)
    core.require(type(data['version']) is int and data['version'] == 2, 'fixture protocol version')
    core.uuid_text(data['id']); core.uuid_text(data['candidate_id'])
    core.hash_text(data['candidate_sha256'])
    core.require(data['batch_id'] == batch['id'], 'unauthorized fixture batch')
    core.require(isinstance(data['objective'], str) and 12 <= len(data['objective']) <= 1000, 'exact objective required')
    for key in ('created_at', 'expires_at'):
        core.require(type(data[key]) in (int, float) and math.isfinite(data[key]), 'finite timestamp')
    core.require(batch['started_at'] <= data['created_at'] <= now + 2, 'stale/future request')
    core.require(data['created_at'] < data['expires_at'] <= min(data['created_at'] + 300, batch['expires_at'])
                 and now < data['expires_at'], 'expired request/TTL')
    core.require(type(data['timeout_seconds']) is int and 1 <= data['timeout_seconds'] <= 60, 'per-process deadline 1..60')
    parameters(data['family'], data['parameters'], data['profile'])
    return data


def candidate_path(ident):
    core.uuid_text(ident)
    return core.project_path('out/fixture-candidates/' + ident + '/candidate.json', ['out/fixture-candidates'])


def plan(family, values, candidate=None):
    """Return only code-selected executable locations and arguments."""
    E, _, _ = modules()
    if family == 'renderer-batch-23':
        items = [dict(name='preflight-' + arch, arch=arch, group=0, variant='native') for arch in ('x86', 'x64')]
        items += [dict(name=f'{E.P.GROUPS[g]}-{a}-{v}', arch=a, group=g, variant=v)
                  for g in range(1, 8) for a, v in (('x86', 'native'), ('x64', 'native'), ('x64', 'translated'))]
        for item in items:
            item['exe'] = FROZEN / 'build' / item['name'] / 'fixture.exe'
        return items
    arch = values['arch']
    if family == 'collector-smoke':
        return [dict(name='smoke-' + arch, arch=arch, group=None, variant='native',
                     exe=candidate / 'build/smoke.exe')]
    return [dict(name=f'{E.P.GROUPS[values["group"]]}-{arch}-{values["variant"]}',
                 arch=arch, group=values['group'], variant=values['variant'], exe=candidate / 'build/fixture.exe')]


def identities(paths):
    return {str(core.independent(p)): core.sha(p) for p in sorted(set(map(Path, paths)))}


def verify_identities(files):
    for name, expected in files.items():
        core.hash_text(expected)
        try:
            path = core.independent(name)
            if core.sha(path) != expected:
                raise core.IntegrityFailure('fixture identity changed: ' + name)
        except (OSError, core.Rejected) as error:
            raise core.IntegrityFailure('fixture identity unavailable: ' + name) from error


def validate_candidate(request):
    path = candidate_path(request['candidate_id'])
    # Hash and parse one immutable byte image; separate reads permit a manifest
    # swap between digest verification and parsing.
    with path.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    core.require(len(raw) <= 4 * 1024 * 1024, 'candidate manifest too large')
    if hashlib.sha256(raw).hexdigest() != request['candidate_sha256']:
        raise core.IntegrityFailure('fixture candidate manifest changed')
    def pairs(items):
        values = {}
        for key, value in items:
            core.require(key not in values, 'duplicate candidate key')
            values[key] = value
        return values
    candidate = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: core.require(False, 'nonfinite candidate value'))
    core.exact(candidate, 'version id family parameters files build_record')
    core.require(candidate['version'] == 1 and candidate['id'] == request['candidate_id'], 'candidate identity')
    core.require(candidate['family'] == request['family'] and candidate['parameters'] == request['parameters'], 'candidate profile binding')
    parameters(candidate['family'], candidate['parameters'], request['profile'])
    # The file inventory is checked against the fixed recipe, not merely hashed.
    expected = expected_files(candidate['family'], candidate['parameters'], path.parent)
    core.require(set(candidate['files']) == {str(p) for p in expected}, 'candidate recipe inventory')
    verify_identities(candidate['files'])
    for item in plan(candidate['family'], candidate['parameters'], path.parent):
        _, A, _ = modules()
        core.require(A.machine(item['exe']) == (0x14c if item['arch'] == 'x86' else 0x8664), 'fixture PE architecture')
        core.require(A.subsystem(item['exe']) == 2, 'fixture must have Windows subsystem')
    expected_record = None if candidate['family'] == 'renderer-batch-23' else str(path.parent / 'build/build-record.json')
    core.require(candidate['build_record'] == expected_record, 'fixed build record path')
    if expected_record:
        record = core.read_large(expected_record)
        core.require(record['recipe'] == 'desktop-fixture-v1' and record['family'] == candidate['family']
                     and record['parameters'] == candidate['parameters'], 'fixed build recipe')
        core.require(record['fp'] == '/fp:strict' and record['toolchain'], 'strict compiler provenance')
        verify_identities({**record['inputs'], **record['outputs'], **record['toolchain']})
        inputs, outputs = recipe_files(candidate['family'], candidate['parameters'], path.parent)
        core.require(set(record['inputs']) == {str(p) for p in inputs} and set(record['outputs']) == {str(p) for p in outputs}, 'build provenance inventory')
    return candidate


def recipe_files(family, values, root):
    E, _, _ = modules()
    src, b = root / 'sources', root / 'build'
    if family == 'collector-smoke':
        return ([src / n for n in ('evidence_smoke.c', 'evidence_fixture.h', 'evidence_dummy.c')],
                [b / n for n in ('smoke.exe', 'smoke.obj', 'disposable.dll', 'dummy.obj')])
    rt = src / 'runtime'
    frozen_rt = E.P.O / 'snapshots' / E.P.GROUPS[values['group']] / 'runtime'
    core.require({p.name for p in rt.iterdir()} == {p.name for p in frozen_rt.iterdir()}, 'fixed runtime source inventory')
    return ([src / n for n in ('fixture.c', 'support.inc', 'evidence_fixture.h')] +
            [E.P.O / 'fixtures' / values['arch'] / 'abi.obj', *sorted(rt.glob('*'))],
            [b / 'fixture.exe', b / 'fixture.obj'])


def formal_files():
    E, _, _ = modules()
    # Frozen deliveries remain assertions, with their original hashes intact.
    delivery = core.read_large(FROZEN / 'evidence-delivery.json')
    original = core.read_large(E.P.O / 'delivery.json')
    files = set(map(Path, delivery['files']))
    files.update(core.ROOT / p for p in original['files'])
    files.update((FROZEN / 'evidence-delivery.json', E.P.O / 'delivery.json', FROZEN / 'collector-final-validation.json'))
    return sorted(files)


def expected_files(family, values, root):
    if family == 'renderer-batch-23':
        return formal_files()
    ins, outs = recipe_files(family, values, root)
    files = ins + outs + [root / 'build/build-record.json']
    if family == 'renderer-group':
        E, _, _ = modules()
        files += [p for arch in ('x86', 'x64') for p in E.P.G.verified_pair(arch).glob('*.dll')]
    return sorted(set(files))


def verify_formal():
    E, _, _ = modules()
    E.D.verify_bundle()
    delivery = core.read_large(FROZEN / 'evidence-delivery.json')
    verify_identities(delivery['files'])
    repair = core.read_large(FROZEN / 'collector-final-validation.json')
    core.require(repair['passed'] is True and repair['full_suite']['tests'] == 105, 'repaired collector qualification')
    verify_identities(repair['final_source_hashes'])
    # The old preservation helper seals the entire old supervisor and its home.
    # This task explicitly changes enforcement. Its replacement is the current
    # qualification seal, while every renderer/runtime/asset assertion stays exact.
    preservation = core.read_large(FROZEN / 'preservation.json')
    for name, files in preservation['trees'].items():
        if Path(name) in (core.ROOT / 'tools/xrt/supervisor', core.HOME):
            continue
        if core.tree(Path(name)) != files:
            raise core.IntegrityFailure('formal preserved tree changed: ' + name)
    core.require(E.P.A.verify() == preservation['protected'], 'protected asset integrity')


def checkout(ident):
    previous = candidate_path(ident).parent
    old = core.read_large(previous / 'candidate.json')
    core.require(old['family'] != 'renderer-batch-23', 'formal delivery cannot be edited')
    new_id = str(uuid.uuid4()); root = SOURCES / new_id
    core.independent(root); root.mkdir(parents=True)
    shutil.copytree(core.independent(previous / 'sources'), root / 'sources')
    core.atomic(root / 'recipe.json', dict(family=old['family'], parameters=old['parameters'], parent_candidate=ident))
    return new_id


def build(family, values, *, source_workspace=None):
    profile = 'formal-acceptance' if family == 'renderer-batch-23' else 'fast-development'
    parameters(family, values, profile)
    E, _, _ = modules()
    ident = str(uuid.uuid4()); root = CANDIDATES / ident
    core.independent(root); root.mkdir(parents=True)
    try:
        if family == 'renderer-batch-23':
            verify_formal()
            record = None
        else:
            src, b = root / 'sources', root / 'build'; src.mkdir(); b.mkdir()
            names = ('evidence_smoke.c', 'evidence_fixture.h', 'evidence_dummy.c') if family == 'collector-smoke' else ('fixture.c', 'support.inc', 'evidence_fixture.h')
            previous = None
            if source_workspace:
                core.uuid_text(source_workspace)
                recipe = core.project_path('out/fixture-sources/' + source_workspace + '/recipe.json', ['out/fixture-sources'])
                previous = recipe.parent
            if previous:
                old = core.read_large(previous / 'recipe.json')
                core.require(old['family'] == family and old['parameters'] == values, 'rebuild family/parameters must match')
            for name in names:
                origin = previous / 'sources' / name if previous else (RENDERER / name if family == 'collector-smoke' else FROZEN / 'sources' / name)
                shutil.copy2(core.independent(origin), src / name)
            # Uses the established fixed per-architecture compiler recipe.
            arch = values['arch']
            if family == 'collector-smoke':
                command = (f'cl /nologo /LD /O1 /W3 /Fo"{b}/dummy.obj" /Fe"{b}/disposable.dll" "{src}/evidence_dummy.c" /link /IMPLIB:"{b}/dummy.lib" || exit /b 1\n'
                           f'cl /nologo /O1 /fp:strict /W3 /D_CRT_SECURE_NO_WARNINGS /Fo"{b}/smoke.obj" /Fe"{b}/smoke.exe" "{src}/evidence_smoke.c" user32.lib /link /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1')
            else:
                frozen_rt = E.P.O / 'snapshots' / E.P.GROUPS[values['group']] / 'runtime'
                rt = src / 'runtime'; rt.mkdir()
                for frozen in frozen_rt.glob('*'):
                    origin = previous / 'sources/runtime' / frozen.name if previous else frozen
                    shutil.copy2(core.independent(origin), rt / frozen.name)
                abi = E.P.O / 'fixtures' / arch / 'abi.obj'
                command = f'cl /nologo /O1 /Gy /fp:strict /W4 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_TRANSLATED={int(values["variant"] == "translated")} /DBATCH_GROUP={values["group"]} /I"{rt}" /Fo"{b}/fixture.obj" /Fe"{b}/fixture.exe" "{src}/fixture.c" "{abi}" kernel32.lib user32.lib /link /OPT:REF /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup || exit /b 1'
            E.P.R.script(b, 'build', arch, command)
            E.P.R.script(b, 'toolchain', arch, 'where cl\nwhere link')
            tools = [Path(s) for s in (b / 'toolchain.stdout.txt').read_text().splitlines() if s.strip()]
            core.require(len(tools) >= 2 and all(p.is_file() for p in tools), 'fixed compiler identities')
            inputs, outputs = recipe_files(family, values, root)
            record = b / 'build-record.json'
            core.atomic(record, dict(recipe='desktop-fixture-v1', family=family, parameters=values, arch=arch,
                        fp='/fp:strict', inputs=identities(inputs), outputs=identities(outputs),
                        toolchain=identities([*tools, Path(E.P.R.VC)]), command=command))
        candidate = dict(version=1, id=ident, family=family, parameters=values,
                         files=identities(expected_files(family, values, root)), build_record=str(record) if record else None)
        core.atomic(root / 'candidate.json', candidate)
        return ident
    except BaseException as error:
        core.atomic(root / 'BUILD-FAILED.json', dict(reason=str(error), preserved=True))
        raise
