"""Preserve and diagnose the consumed owner attempt; never executes the game."""
import collections
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import capstone
import pefile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('consumed_continuation_checks', HERE / 'checks.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
W = C.W
CONSUMED = W / 'out/recovery/renderer-continuation-20261028-01'
O = W / 'out/recovery/viewport-getobject-diagnosis-20261028-01'
SB = W / 'sandbox_cmp/renderer-continuation-20261028-01'


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def archive(name, paths):
    identities = {p.relative_to(W).as_posix(): C.sha(p) for p in paths}
    path = O / name
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as target:
        for rel, expected in identities.items():
            target.write(W / rel, rel)
            assert C.sha(W / rel) == expected, rel
    with zipfile.ZipFile(path) as target:
        for rel, expected in identities.items():
            with target.open(rel) as stream:
                assert C.hashlib.file_digest(stream, 'sha256').hexdigest() == expected, rel
    print('ARCHIVED AND READBACK VERIFIED', name, len(identities), flush=True)
    return dict(path=name, sha256=C.sha(path), files=identities)


def main():
    assert not sys.flags.optimize
    C.check(CONSUMED, C.read(CONSUMED / 'final-seal.json'))
    C.inputs()
    assert (CONSUMED / 'GENUINE-ATTEMPT-CONSUMED.json').exists()
    assert not (CONSUMED / 'genuine-owner-run/completed.json').exists()
    O.mkdir()
    run = CONSUMED / 'genuine-owner-run'
    session = run / 'session'
    debug = [json.loads(line) for line in (session / 'debug-observations.jsonl').read_text().splitlines()]
    fatal, = [r for r in debug if r['kind'] == 'fatal_entry']
    created, = [r for r in debug if r['kind'] == 'process_created']
    launch = C.read(session / 'launch.json')
    plan = C.read(session / 'debugger-plan.json')
    base = created['base']
    assert launch['pid'] == created['pid']
    exe = Path(launch['executable'])
    assert C.sha(exe) == launch['sha256'] == plan['sha256']
    assert C.sha(exe.with_suffix('.pdb')) == plan['pdb_sha256']
    assert fatal['host']['registers']['rip'] == base + plan['symbols']['xrt_fatal']['rva']
    assert fatal['code'] == 76 and not fatal['runtime_fatal_body_executed']
    assert fatal['format'] == 'WM_GETOBJECT: unmeasured dialog/arguments (wp=%llx lp=%llx)'
    assert fatal['decoded_arguments'] == dict(message=61, wp=0xffffffff, lp=0xfffffffc)
    assert not fatal['diagnostic_read_errors']
    assert fatal['cpu']['pc'] == 0x111071e2
    windrv = pefile.PE(str(SB / 'System/WinDrv.dll'))
    imported, = [i.name.decode() for entry in windrv.DIRECTORY_ENTRY_IMPORT for i in entry.imports
                 if i.address == 0x1110b32c]
    assert imported == 'DefWindowProcW'
    assert windrv.get_data(0x71e2, 6).hex() == 'ff152cb31011'
    ev = C.read(session / 'runtime-events.json')
    raw = (session / 'runtime-events.raw.bin').read_bytes()
    assert len(raw) % 448 == 0
    events = [json.loads(raw[i:i+448].split(b'\0', 1)[0]) for i in range(0, len(raw), 448)]
    assert events == ev['events'] and len(events) == ev['events_recorded'] == 74407
    assert ev['events_dropped'] == 0 and [r['seq'] for r in events] == list(range(1, len(events)+1))
    assert not any(r.get('truncated') for r in events)
    kinds = collections.Counter(r['kind'] for r in events)
    def es(kind):
        return [r for r in events if r['kind'] == kind]
    assert any(r['module'] == 'Window.dll' and r['base'] == '0x11000000' for r in es('dll_mapped'))
    init, = [r for r in es('dmusic_backend') if r['sequence'] == 4]
    assert (init['op'], init['id'], init['result'], init['out_id'], init['type']) == (6, 2, 0, 3, 3)
    assert es('dmusic_backend_start')[0]['timeout_ms'] == 10000
    startup, = es('gui_get_object_callback_return')
    assert startup['result'] == 0 and startup['hwnd'] == 4116 and startup['proc'] == 0x10901000
    maps = []
    pending = []
    for row in events:
        if row['kind'] == 'engine_loadmap_call':
            pending.append(row)
        elif row['kind'] == 'engine_loadmap_return':
            call = pending.pop()
            assert call['return'] == row['return'] == row['actual_return']
            assert call['this'] == row['this'] and call['esp'] == row['esp_before']
            assert row['esp_after'] == call['esp'] + 20 and row['result']
            maps.append(dict(call=call, returned=row))
    assert not pending and len(maps) == 2
    selected = maps[-1]['returned']['result']
    lifecycle = {}
    for stage in ['PreBeginPlay', 'BeginPlay', 'PostBeginPlay']:
        stack = []
        pairs = []
        for row in events:
            if row['kind'] == 'actor_lifecycle_call' and row['stage'] == stage:
                stack.append(row)
            elif row['kind'] == 'actor_lifecycle_return' and row['stage'] == stage:
                call = stack.pop()
                assert all(call[k] == row[k] for k in ['this', 'world', 'return'])
                assert call['esp'] == row['esp_before'] and row['actual_return'] == call['return']
                pairs.append((call, row))
        assert not stack
        lifecycle[stage] = dict(paired_returns=len(pairs), selected_world_paired_returns=sum(r['world'] == selected for c, r in pairs))
    hard = base + plan['stop_rva']
    readbacks = [r for r in debug if r['kind'] == 'breakpoints_readback']
    for row in readbacks:
        assert row['permanent_stop_present'] and hard in row['addresses']
        assert row['dr'] == row['addresses'] + [0] * (4-len(row['addresses']))
        assert row['dr7'] & 0xffff00ff == sum(1 << (2*i) for i in range(len(row['addresses'])))
    assert not [r for r in debug if r['kind'] == 'hard_stop_0696f292']
    assert not es('d3d8_device_call') and not es('d3d8_render_call') and not es('d3d8_state_call')
    assert not es('engine_init_return') and not es('engine_tick_call') and not es('level_tick_call')
    # PDB and the exact compiled data flow identify the otherwise unprinted
    # guard operand. R12D still holds invoke_gui_proc's fifth explicit_proc arg.
    lookup = C.load('viewport_diagnosis_symbols', W / 'experiments/xrt/tests/getobject_boundary/debugger_test.py')
    symbols = lookup.symbols(exe, ['invoke_gui_proc', 'xrt_fatal'])
    pe = pefile.PE(str(exe), fast_load=True)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    sym = symbols['invoke_gui_proc']
    ins = list(md.disasm(pe.get_data(sym['rva'], sym['size']), base + sym['rva']))
    caller = fatal['native_caller_return'] - base
    assert sym['rva'] <= caller < sym['rva'] + sym['size']
    rows = [dict(rva=x.address-base, bytes=x.bytes.hex(), mnemonic=x.mnemonic, operands=x.op_str) for x in ins]
    load_arg, = [r for r in rows if r['rva'] == 0x6f03ac2]
    assert load_arg['mnemonic'] == 'mov' and load_arg['operands'] == 'r12d, dword ptr [rbp + 0x230]'
    guard_index = next(i for i, r in enumerate(rows) if r['rva'] == 0x6f03c70)
    guard = rows[guard_index:guard_index+2]
    assert guard[0]['mnemonic'] == 'test' and guard[0]['operands'] == 'r12d, r12d'
    assert guard[1]['mnemonic'] == 'jne' and int(guard[1]['operands'], 16) == base + 0x6f0457b
    regs = fatal['host']['registers']
    assert regs['r12'] == 0x1100b060 and caller == 0x6f04598
    assert not [r for r in rows[guard_index:next(i for i,r in enumerate(rows) if r['rva'] == caller)]
                if r['rva'] < 0x6f040c9 and r['mnemonic'] == 'mov' and r['operands'].startswith('r12')]
    save(O / 'native-disassembly.json', dict(base=base, symbols=symbols, caller_rva=caller, guard=guard, instructions=rows))
    cleanup = C.read(run / 'cleanup.json')
    initial = C.read(run / 'initial-state.json')
    assert cleanup['passed'] and cleanup['process_cleanup'] and cleanup['locks_reacquired']
    assert cleanup['state'] == initial['state'] and cleanup['physical_clip'] == initial['physical_clip']
    assert not cleanup['state']['processes']
    environment = C.load('viewport_diagnosis_environment', W / 'out/recovery/session-aware-136-20261026-01/owner.py')
    baseline = C.read(CONSUMED / 'owner-evidence-audit.json')['baseline']
    environment_files = sorted(run.glob('*-environment.json'))
    for path in environment_files:
        assert environment.environment_gate(C.read(path)) == baseline
    raw_meta = [p for p in (W / 'experiments/xrt/results/raw/level').glob('*/meta.json')
                if C.read(p).get('sandbox') == str(SB)]
    meta_path, = raw_meta
    meta = C.read(meta_path)
    sandbox = C.tree(SB)
    def mutable(rel):
        name = rel.lower()
        return name.startswith(('save/', 'cache/')) or name == 'system/golem.u' or (name.startswith('system/') and name.endswith(('.ini', '.log')))
    changes = {rel: dict(before=meta['before'].get(rel), after=sandbox.get(rel))
               for rel in meta['before'].keys() | sandbox.keys() if meta['before'].get(rel) != sandbox.get(rel)}
    assert all(mutable(rel) for rel in changes), changes
    save(O / 'sandbox-manifest.json', dict(root=str(SB), files=sandbox, changes=changes))
    metadata = {p.relative_to(SB).as_posix(): dict(directory=p.is_dir(), size=p.stat().st_size,
                mtime_ns=p.stat().st_mtime_ns, attributes=getattr(p.stat(), 'st_file_attributes', None))
                for p in sorted(SB.rglob('*'))}
    save(O / 'sandbox-metadata.json', metadata)
    archives = [archive('consumed-owner-evidence.zip', C.files(CONSUMED) + C.files(meta_path.parent)),
                archive('complete-consumed-sandbox.zip', C.files(SB))]
    save(O / 'preservation.json', dict(passed=True, archives=archives,
         inherited_source_and_exact_build_archive_root=str(C.PRIOR),
         inherited_archives=C.read(C.PRIOR / 'preservation.json')['archives'],
         consumed_marker_sha256=C.sha(CONSUMED / 'GENUINE-ATTEMPT-CONSUMED.json'),
         no_consumed_files_changed=True, runtime_changes=False, genuine_sessions_launched=0))
    diagnosis = dict(passed=True, owner_attempt_consumed=True, retry_permitted=False,
         actual_guest_InitAudio=init, production_timeout_ms=10000, startup_dialog_getobject=startup,
         loadmap_pairs=maps, selected_world=hex(selected), lifecycle=lifecycle,
         fatal_message=fatal['formatted_message'], fatal_code=76,
         guest_pc=hex(fatal['cpu']['pc']), guest_pending_import='USER32!DefWindowProcW',
         outer_pending_import='USER32!SetFocus during viewport creation',
         explicit_proc=hex(regs['r12']), explicit_proc_module='Window.dll+0xb060',
         rejection_reason='nonzero explicit_proc: ordinary registered-class WNDPROC dispatch is outside the measured dialog-only WM_GETOBJECT adapter',
         native_caller_rva=hex(caller), events_recorded=len(events), events_dropped=0,
         permanent_stop_readbacks=len(readbacks), permanent_stop_hit=False,
         CreateDevice=0, Clear=0, Present=0, SetRenderState=0, engine_init_returned=False,
         engine_ticks=0, selected_world_ticks=0, environment_observations_verified=len(environment_files),
         cleanup_passed=True, strict_x87='FAILED; retained separately', strict_wndproc_equality='FAILED; retained separately',
         next_work='Measure the ordinary Unicode window WNDPROC/default-processing WM_GETOBJECT path in non-game native x86/x64 and translated fixtures before changing the dialog-only guard.',
         new_genuine_sessions_launched=0)
    save(O / 'diagnosis.json', diagnosis)
    current = environment.V.state()
    assert not current['processes']
    C.check(CONSUMED, C.read(CONSUMED / 'final-seal.json'))
    C.inputs()
    assert C.tree(SB) == sandbox
    report = f'''Consumed owner continuation diagnosis — October 28, 2026 (US Eastern)

The attempt advanced past DirectMusic and stopped at a later, distinct WM_GETOBJECT
boundary. Actual guest InitAudio completed: sequence 4, operation 6, S_OK, object 3,
DirectSound type 3. The 10-second production transport deadline was unchanged.
The startup dialog WM_GETOBJECT completed (procedure 0x10901000, result 0).
Both LoadMap calls have paired returns; selected world {selected:#x} completed
{lifecycle['PreBeginPlay']['selected_world_paired_returns']} actor lifecycle returns per stage.

New stop: nested inside USER32 DefWindowProcW at guest 0x111071e2, while the outer
SetFocus during viewport creation is pending. The registered-class
WNDPROC is Window.dll+0xb060 (explicit_proc=0x1100b060). The exact EXE/PDB and
native register/data-flow evidence prove the nonzero explicit_proc guard branch,
before dispatching this WM_GETOBJECT to the guest. wp=0xffffffff, lp=0xfffffffc.
The identical printed scalar tuple does not make this the measured dialog path.
The observer captured the actual fatal and CPU/stack successfully; its Python
RuntimeError reports the intentional unsupported-method stop.

No CreateDevice, Clear, Present, SetRenderState, Engine Init return, or world tick.
All {len(events):,} runtime records match stopped-memory raw bytes, contiguous,
with zero drops. All {len(readbacks)} hardware-stop readbacks retain 0x0696f292;
it was not reached. Cleanup and all {len(environment_files)} environment records
pass; no remaining game/helper processes. Strict x87/WNDPROC equality failures
remain separate and unwaived.

The old owner command is CONSUMED and must not be rerun. No retry or new launcher
was prepared. No runtime/helper/source-bound behavior was changed. New genuine
sessions during this diagnosis: zero. Prior sealed package, owner records, raw
output, complete sandbox and metadata are preserved with readback-verified ZIPs.

Next work: characterize ordinary Unicode registered-window WM_GETOBJECT through
the actual WNDPROC and Windows default processing in native x86/x64/translated
non-game fixtures. Do not simply remove the dialog-only explicit_proc guard or
supply an accessibility result. DirectMusic investigation need not be reopened.
'''
    (O / 'REPORT.txt').write_text(report, encoding='utf-8')
    save(O / 'artifact-manifest.json', C.tree(O))
    print('DIAGNOSIS AND PRESERVATION PASS; NO RETRY; NO GAME LAUNCHED', flush=True)


if __name__ == '__main__':
    main()
