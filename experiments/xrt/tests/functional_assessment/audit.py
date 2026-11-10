"""Offline resource assessment. Never launches, submits, grants, or edits history."""
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[4]
H = W / 'experiments/xrt/tests/integrated_candidate'
P = W / 'out/recovery/physical-integrated-20261030-01'
I = W / 'out/recovery/integrated-candidate-20261030-01'
RT = W / 'out/recovery/surface-transfer-20261030-01/runtime'
OUT = W / 'out/recovery/resource-functional-assessment-20261030-01'
sys.path.insert(0, str(H))
from common import core
from package_audit import validate
from supervisor import fixture_profiles as F
import gpu_evidence as E


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def state(raw):
    return dict(cw=struct.unpack_from('<H', raw, 0)[0],
                sw=struct.unpack_from('<H', raw, 2)[0], tag=raw[4],
                top=(struct.unpack_from('<H', raw, 2)[0] >> 11) & 7,
                mxcsr=struct.unpack_from('<I', raw, 24)[0],
                live_st=[raw[32:42].hex(), raw[48:58].hex()])


def call_audit(row, arch, translated):
    """Independent checks; strict failure recorded, never patched or bypassed."""
    a, b = [bytes.fromhex(row[k]) for k in ('pre', 'post')]
    require(len(a) == len(b) == 512, 'FXSAVE length')
    sa, sb = state(a), state(b)
    require(sa['cw'] == sb['cw'] == 0x27f, 'x87 control changed')
    require(sa['sw'] == 0x3000 and sb['sw'] in (0x3000, 0x3020), 'x87 status outside observed scope')
    require(sa['tag'] == sb['tag'] == 0xc0 and sa['top'] == sb['top'] == 6, 'x87 stack validity')
    require(sa['live_st'] == sb['live_st'], 'live x87 values changed')
    require(sa['mxcsr'] == 0x3f80 and sb['mxcsr'] in (0x3f80, 0x3fa0), 'MXCSR outside observed scope')
    regs = [0x12345678, 0x23456789, 0x3456789a, 0x456789ab, 0, 0, 0, 0] if arch == 'x86' else [
        0x1111111112345678, 0x2222222223456789, 0x333333333456789a, 0x44444444456789ab,
        0x5555555556789abc, 0x666666666789abcd, 0x77777777789abcde, 0x8888888889abcdef]
    require(row['regs'] == regs and row['stack_delta'] == 0, 'outer GPR/stack')
    xmm = bytes(160)
    if arch != 'x86':
        xmm = struct.pack('<4I', 0x12345678, 0x23456789, 0x3456789a, 0x456789ab) * 10
    require(bytes.fromhex(row['xmm']) == xmm, 'outer XMM')
    before, after = [bytes.fromhex(row[k]) for k in ('cpu_before', 'cpu_after')]
    require(len(before) == len(after) == (408 if arch == 'x86' else 416), 'architecture CPU size')
    expected = bytearray(before)
    if translated:
        struct.pack_into('<I', expected, 0, row['hr'])
        struct.pack_into('<I', expected, 16, struct.unpack_from('<I', before, 16)[0] + 4 * (row['nargs'] + 1))
        struct.pack_into('<I', expected, 64, 0x98765432)
    require(after == expected, 'full guest CPU transfer')
    require(type(row['hr']) is int and 0 <= row['hr'] <= 0xffffffff, 'HRESULT encoding')
    require(type(row['last_error']) is int and 0 <= row['last_error'] <= 0xffffffff, 'last-error encoding')
    require(type(row['nonnull']) is bool, 'output encoding')
    strict_error = None
    try:
        E.base.abi(row, arch)
    except E.base.Invalid as error:
        strict_error = str(error)
    require(bool(strict_error) == (sa != sb), 'unexpected strict ABI failure')
    return dict(before=sa, after=sb, strict_error=strict_error,
                guest_fcw=struct.unpack_from('<H', before, 140)[0],
                guest_fsw=struct.unpack_from('<H', before, 142)[0],
                guest_top=struct.unpack_from('<I', before, 136)[0])


def physical():
    history = read(P / 'submissions.json')
    package = read(I / 'gpu-qualification-package.json')
    collector, checker, _ = F.modules()
    reports, sequences, files = [], [], {}
    for item, spec in zip(history, package['candidates']):
        response = item['response']; root = Path(response['evidence'])
        require(read(root / 'result.json') == response == read(F.HOME / 'responses' / (item['request_id'] + '.json')), 'historical result binding')
        for name, digest in read(root / 'evidence-index.json').items():
            require(sha(root / name) == digest, 'historical evidence hash: ' + name)
            files[str(root / name)] = digest
        candidate = validate(spec)
        cr = F.candidate_path(candidate['id']).parent
        plan = F.plan('renderer-group', spec['parameters'], cr)[0]
        pair = collector.P.G.verified_pair(plan['arch'])
        capture = next((root / 'captures').iterdir())
        rs, snapshot, events = checker.process(capture, physical=True, expected_exe=plan['exe'],
            expected_args=['--physical', pair], expected_build=Path(candidate['build_record']),
            expected_backend=[pair / 'd3d8.dll', pair / 'd3d9.dll'])
        adapter = checker.adapter(rs, snapshot, capture, plan['arch'])
        rows = E.read_rows(capture / 'stdout.txt')
        calls = [r for r in rows if r['kind'] in ('resource-call', 'transfer-call')]
        resources = [r for r in calls if r['kind'] == 'resource-call']
        transfers = [r for r in calls if r['kind'] == 'transfer-call']
        require(len(calls) == 114 and [r['slot'] for r in resources] == E.prior.SLOTS, 'resource sequence')
        require([(r['slot'], r['nargs']) for r in transfers] == E.TRANSFER, 'transfer sequence')
        require([r['kind'] for r in calls] == ['resource-call'] * (len(resources)-11) + ['transfer-call'] * len(transfers) + ['resource-call'] * 11, 'interleaving')
        for j, r in enumerate(resources):
            require(r['nargs'] == E.prior.nargs(j, r['slot']), 'resource arity')
            require(0 <= r['hr'] < 0x80000000, 'resource result')
            if r['slot'] in (20, 23, 24, 32, 33, 300, 303, 315):
                require(r['nonnull'], 'owned output missing')
            if r['slot'] == 313:
                require(r['hr'] == 4, 'mip levels')
        for r in transfers:
            require(0 <= r['hr'] < 0x80000000 if r['slot'] == 302 else r['hr'] == (0x8876086c if r['slot'] == 30 else 0), 'transfer result')
            if r['slot'] in (16, 25, 26, 27):
                require(r['nonnull'], 'surface missing')
        observations = [dict(index_1based=j+1, kind=r['kind'], slot=r['slot'], **call_audit(r, plan['arch'], plan['variant']=='translated')) for j,r in enumerate(calls)]
        failures = [r for r in observations if r['strict_error']]
        require(len(failures) == 7, 'strict difference count')
        require([(r['kind'], r['slot']) for r in failures] == [('resource-call',36),('resource-call',70),('resource-call',15),('resource-call',36),('resource-call',36),('transfer-call',26),('transfer-call',36)], 'strict difference operation scope')
        create = E.base.one(rows, 'semantic-create'); own = E.base.one(rows, 'semantic-ownership')
        require(create == dict(kind='semantic-create', hr=0, width=800, height=600), 'create')
        require(own['same_parent'] and own['same_window'] and own['parent_hr']==own['creation_hr']==0 and own['add']==own['balance']+1 and own['flags']==66, 'ownership')
        pixels = [r for r in rows if r['kind']=='resource-pixels']
        require(pixels == [dict(kind='resource-pixels',mode=m,changed=20100,hash=2064490405) for m in range(3)], 'draw pixels')
        copy = E.base.one(rows, 'transfer-pixels')
        require(copy['pixels']==64 and copy['hash']==E.expected_copy_hash()==458408325, 'copy pixels')
        clean = E.base.one(rows, 'semantic-cleanup')
        require(clean['device_release']==clean['parent_release']==0 and clean['active_callbacks']==0, 'cleanup refs/callbacks')
        require(all(clean[k] for k in ('destroyed','unregistered','free_d3d8','free_d3d9','guest_freed')) and not any(clean[k] for k in ('window_valid','d3d8_loaded','d3d9_loaded')), 'cleanup')
        require(E.base.one(rows,'resource-summary') == dict(kind='resource-summary',calls=114,synthetic_only=True,game_scene=False), 'summary')
        require(E.base.one(rows,'semantic-summary') == dict(kind='semantic-summary',calls=114,translated=plan['variant']=='translated',group=1), 'variant')
        reports.append(dict(parameters=spec['parameters'], capture=str(capture), adapter=adapter,
            original_verdict=response, physical_checks_passed=True, operations=114, strict_failures=failures,
            all_call_fpu_observations=observations, pixels=pixels, copy_pixels=copy, ownership=own, cleanup=clean))
        sequences.append([{k:r[k] for k in ('kind','slot','nargs','hr','last_error','nonnull')} for r in calls])
    require(len(reports)==3, 'three variants')
    require(sequences[1]==sequences[2], 'native x64 / translated difference')
    diffs=[]
    for j,(a,b) in enumerate(zip(sequences[0],sequences[1])):
        for k in a:
            if a[k]!=b[k]: diffs.append(dict(index_1based=j+1,slot=a['slot'],field=k,x86=a[k],x64=b[k]))
    require(diffs==[dict(index_1based=14,slot=20,field='last_error',x86=0,x64=0x13572468)], 'unexpected three-way difference')
    return dict(reports=reports, differences=diffs, evidence_files=files,
                strict_native_x86='FAILED', functional_renderer='PASS_MEASURED_OPERATIONS_WITH_RECORDED_STATE_DIFFERENCES',
                experimental_execution_ready=False, genuine_launches=0, physical_launches=0)


def original_code():
    import capstone as cs
    import pefile
    source = W / 'sandbox_inputs/first-world/content/System/D3DDrv.dll'
    pe = pefile.PE(str(source)); base=0x6960000; pe.relocate_image(base)
    md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_32); md.detail=True; md.skipdata=True
    ins=[]
    for section in pe.sections:
        if section.Characteristics & 0x20000000:
            ins.extend(md.disasm(section.get_data(),base+section.VirtualAddress))
    fmt=lambda i:dict(address=hex(i.address),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str)
    imports=[dict(dll=d.dll.decode(),name=x.name.decode() if x.name else '#'+str(x.ordinal),iat=hex(x.address)) for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports]
    require(not any(x['name']=='GetLastError' for x in imports),'unexpected D3DDrv GetLastError')
    sites=[]
    for addr in (0x697afc3,0x697b51b,0x697b806):
        j=next(j for j,i in enumerate(ins) if i.address==addr)
        require(ins[j].mnemonic=='call' and ins[j].operands[0].mem.disp==0x50,'original texture call')
        require(ins[j+1].mnemonic=='test' and ins[j+1].op_str=='eax, eax','HRESULT consumer')
        sites.append(dict(site=hex(addr),context=[fmt(i) for i in ins[j:j+28]]))
    readers=[]
    for j,i in enumerate(ins):
        if i.mnemonic in ('fnstsw','fstsw','stmxcsr','fxsave','fnstenv','fstenv','fnsave','fsave','fldcw','ldmxcsr'):
            readers.append(dict(site=hex(i.address),context=[fmt(x) for x in ins[max(0,j-3):j+5]]))
            require(i.mnemonic=='fnstsw' and i.op_str=='ax' and ins[j+1].mnemonic=='test' and ins[j+1].op_str.startswith('ah,'),'unclassified D3DDrv FPU reader')
    require(len(readers)==19,'D3DDrv status-reader coverage')
    direct_tls=[]
    for i in ins:
        if i.id and any(o.type==cs.x86_const.X86_OP_MEM and o.mem.segment==cs.x86_const.X86_REG_FS for o in i.operands):
            direct_tls.append(fmt(i))
    return dict(original=str(source),sha256=sha(source),imports=imports,texture_calls=sites,
                fpu_readers=readers,fs_segment_instructions=direct_tls,
                limit='Linear executable-section disassembly cross-checked against generated instruction markers; not whole-program interprocedural reachability or dynamic path proof.')


def main():
    OUT.mkdir(exist_ok=False)
    protected={}
    for root in (P,I,RT,W/'tools/xrt/supervisor',H):
        for p in root.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:protected[str(p)]=sha(p)
    save('preservation-before.json',protected)
    result=physical();save('physical-audit.json',result)
    save('original-code-audit.json',original_code())
    design=read(I/'continuation-design.json')
    require(sha(design['candidate'])==design['sha256'],'candidate identity')
    require(sha(Path(design['candidate']).with_suffix('.pdb'))==design['pdb_sha256'],'PDB identity')
    require(sha(design['mapping_file'])==design['mapping_sha256'],'mapping identity')
    for p,d in design['observer_sources'].items():require(sha(p)==d,'observer identity')
    require(not design['execution_authorized'] and not design['observer_installed'],'staged status')
    design.update(status='PREPARED_REVIEW_ONLY_MONITORING_HOLD',execution_ready=False,
        exception_scope='Only exact observed resource/surface operations, backend, fixture configurations and precision-status bits; no general gameplay waiver.',
        retained_design=str(I/'continuation-design.json'),
        blocking_requirements=[
            'Compose and qualify complete native-entry/result/guest-return CPU+host-FPU and callback monitoring with permanent endpoint within four DR slots; existing staged endpoint-only composition does not meet this requirement.',
            'Observe guest last-error consumers and precision-status consumers, or prove nondependence on the actually reached path; current fixtures reset state per call and are not that proof.',
            'Separate exact-candidate, exact-observer and one-launch owner authorization; no active policy modification in this assessment.'],
        maximum_genuine_sessions=1,watchdog_seconds=60,retry=False,
        required_controls=['evidence before assertions','full guest CPU and host FPU at native boundaries','callback entry/exit and reentry rejection','typed COM identity and complete page-range checks','fresh isolated filesystem and protected assets','permanent endpoint on all threads with live DR readback','independent watchdog','Job assignment before resume and kill-on-close','terminate while stopped; no endpoint instruction or later world tick','fresh identity/nonconsumption/module/gamma verification'],
        genuine_launches=0,active_supervisor_changed=False)
    save('continuation-proposal.json',design)
    require(all(sha(p)==d for p,d in protected.items()),'preserved inputs changed')
    save('preservation-after.json',dict(passed=True,files=len(protected),manifest_sha256=sha(OUT/'preservation-before.json'),historical_results_changed=False,policy_changed=False))
    print(json.dumps(dict(output=str(OUT),variants=3,calls_per_variant=114,strict_failures_per_variant=7,
        strict='FAILED',functional='PASS within measured renderer scope',execution_ready=False,preserved_files=len(protected)),indent=2))


if __name__=='__main__':main()
