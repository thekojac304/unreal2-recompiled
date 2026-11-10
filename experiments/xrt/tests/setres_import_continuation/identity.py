"""Independent disk/source/object/link checks. Never executes the candidate."""
import json
import pathlib
import re
import struct
import uuid
from common import *


def consumed():
    ledger = core.Ledger(core.HOME / 'ledger.jsonl')
    core.require(not any(r.get('sha256') == SHA and r['kind'] == 'launch-claimed' for r in ledger.rows), 'candidate already consumed')
    # Earlier one-shot launchers predate the global supervisor ledger.
    names = ('*CONSUMED*.json', '*consumed*.json', '*single-session-attempt*.json', '*launch.json')
    checked = {}
    for pattern in names:
        for p in (W / 'out').rglob(pattern):
            if p.is_relative_to(O):
                continue
            text = p.read_text(errors='replace')
            core.require(SHA not in text, 'candidate found in historical consumption/launch evidence: ' + str(p))
            checked[str(p)] = core.sha(p)
    return dict(ledger_rows=len(ledger.rows), ledger_sha256=core.sha(ledger.path), historical_records=checked, unconsumed=True)


def pdb_identity():
    import pefile
    with pefile.PE(str(EXE)) as pe:
        entries = [pe.get_data(e.struct.AddressOfRawData, e.struct.SizeOfData) for e in pe.DIRECTORY_ENTRY_DEBUG]
        rsds = [v for v in entries if v[:4] == b'RSDS']
        core.require(len(rsds) == 1, 'one RSDS record required')
        guid, age = uuid.UUID(bytes_le=rsds[0][4:20]), struct.unpack_from('<I', rsds[0], 20)[0]
        core.require(str(guid) == 'fbde2d67-a9a2-49cc-adfd-ad45c625a31f' and age == 1, 'PE debug identity')
        machine = pe.FILE_HEADER.Machine
    raw = EXE.with_suffix('.pdb').read_bytes()
    block, _, _, directory_size, _, block_map = struct.unpack_from('<6I', raw, 32)
    n = (directory_size + block - 1) // block
    blocks = struct.unpack_from('<' + 'I' * n, raw, block_map * block)
    directory = b''.join(raw[b*block:(b+1)*block] for b in blocks)[:directory_size]
    count = struct.unpack_from('<I', directory)[0]
    sizes = struct.unpack_from('<' + 'I'*count, directory, 4)
    offset = 4 + 4*count
    stream1 = None
    for i, size in enumerate(sizes):
        n = 0 if size == 0xffffffff else (size+block-1)//block
        ids = struct.unpack_from('<'+'I'*n, directory, offset); offset += 4*n
        if i == 1:
            stream1 = b''.join(raw[b*block:(b+1)*block] for b in ids)[:size]
    core.require(stream1 and uuid.UUID(bytes_le=stream1[12:28]) == guid and struct.unpack_from('<I', stream1, 8)[0] == age, 'PDB stream-1 GUID/age mismatch')
    return dict(guid=str(guid), age=age, machine=machine, independently_parsed=True)


def verify():
    b = read(PRIOR / 'build.json'); lines = read(PRIOR / 'object-lineage.json')
    core.require(core.sha(EXE) == b['binary_sha256'] == SHA and core.sha(EXE.with_suffix('.pdb')) == b['pdb_sha256'] == PDB, 'candidate hashes')
    core.require(b['passed'] and pathlib.Path(b['root']) == EXE.parent, 'build identity')
    for folder, root in [('outputs', EXE.parent), ('runtime', pathlib.Path(b['runtime_root'])), ('generated', W/'experiments/xrt/gen')]:
        core.require(core.tree(root) == b[folder], 'complete inventory changed: '+folder)
    objects = {p for p in b['outputs'] if p.endswith('.obj')}
    core.require(set(lines) == objects and len(objects) == 279, 'complete 279 object lineage')
    reused = 0
    inherited_records=set()
    def chain(obj,v,seen=frozenset()):
        for name,digest in v.get('verified_local_headers',{}).items():core.require(core.sha(name)==digest,'transitive header changed')
        command=v['command']
        output=next((s[3:] for s in command if s.startswith('/Fo')),None)
        core.require(output and pathlib.Path(output).is_file() and core.sha(output)==v['object_sha256'],'original compile output object missing/changed')
        inherited=v.get('inherited_from')
        if inherited:
            core.require(inherited not in seen,'cyclic object lineage')
            parent=read(inherited)[obj];inherited_records.add(inherited)
            core.require(parent['source_sha256']==v['source_sha256'] and parent['object_sha256']==v['object_sha256'],'transitive lineage mismatch')
            chain(obj,parent,seen|{inherited})
    for obj, v in lines.items():
        core.require(core.sha(EXE.parent / obj) == v['object_sha256'] == b['outputs'][obj], 'object identity')
        core.require(core.sha(core.independent(v['source'])) == v['source_sha256'], 'object source identity')
        for name, digest in v.get('verified_local_headers', {}).items():
            core.require(core.sha(core.independent(name)) == digest, 'header identity')
        core.require('/fp:strict' in v['command'] and '/c' in v['command'], 'strict compile command absent')
        if v.get('reused_in_this_candidate'):
            reused += 1
            prior = read(v['inherited_from'])
            core.require(prior[obj]['object_sha256'] == v['object_sha256'] and prior[obj]['source_sha256'] == v['source_sha256'], 'inherited object chain')
        chain(obj,v)
    core.require(reused == 278 and len(objects)-reused == 1, 'object counts')
    rsp = (EXE.parent/'link-objects.rsp').read_text()
    inputs = [pathlib.Path(s) for s in re.findall(r'"([^"]+\.obj)"', rsp)]
    if not inputs:
        inputs = [pathlib.Path(s.strip().strip('"')) for s in rsp.splitlines() if s.strip()]
    core.require(len(inputs) == 279 and {p.relative_to(EXE.parent).as_posix() for p in inputs} == objects, 'exact link inputs')
    core.require(core.sha(b['inherited_build']) == b['inherited_build_sha256'], 'inherited build record changed')
    for name, digest in b['toolchain'].items():
        core.require(core.sha(name) == digest, 'compiler/linker identity')
    core.require(all(c['exit'] == 0 for c in b['commands']) and len(b['commands']) == 2, 'serial build commands')
    dependencies = read(W/'out/recovery/renderer-gamma-integration-20261029-01/candidate-verification.json')['dependencies']
    for name, digest in dependencies.items():
        core.require(core.sha(core.independent(name)) == digest, 'pinned dependency changed')
    gamma = read(W/'out/recovery/renderer-gamma-integration-20261029-01/physical-gamma-abi-audit.json')
    core.require(gamma['functional_gamma_qualified'] and gamma['inner_raw_native_abi_captured'] and gamma['physical_calls'] == 24, 'gamma qualification absent')
    core.require(core.sha(W/'out/recovery/renderer-gamma-integration-20261029-01/physical-gamma-audit.json') == b['gamma_profile'], 'gamma qualification identity')
    return dict(passed=True, executable=str(EXE), sha256=SHA, pdb_sha256=PDB, pe_pdb=pdb_identity(),
                objects=279, reused_generated_objects=265, reused_runtime_objects=13, compiled_runtime_objects=1,
                transitive_object_records={p:core.sha(p) for p in sorted(inherited_records)},
                build_record_sha256=core.sha(PRIOR/'build.json'), object_lineage_sha256=core.sha(PRIOR/'object-lineage.json'),
                dependencies=dependencies, consumption=consumed(), toolchain=b['toolchain'], genuine_launches=0)
