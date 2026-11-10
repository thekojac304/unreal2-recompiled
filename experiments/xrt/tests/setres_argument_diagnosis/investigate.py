"""Offline only: preserve the consumed state and decode existing evidence."""
import collections
import json
import pathlib
import shutil
import struct
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import *


def preserve():
    core.require(not O.exists(), 'existing investigation must be retained')
    O.mkdir()
    roots = [OLD, SANDBOX, EXE.parent, core.HOME,
             W/'experiments/xrt/tests/setres_import_continuation',
             W/'tools/xrt/supervisor', W/'experiments/xrt/runtime',
             W/'experiments/xrt/gen', W/'out/recovery/attachthread-setres-20261029-01',
             W/'out/recovery/setres-completion-20261029-01']
    inventories = {str(p): core.tree(p) for p in roots}
    save(O/'preservation.json', dict(trees=inventories, in_place_preservation=True,
         description='Complete content inventories; every original tree is retained untouched. Raw attempt, ledger, candidate and PDB additionally copied.',
         genuine_launches=0))
    shutil.copytree(ATTEMPT, O/'consumed-attempt-copy')
    dest = O/'consumed-identity-copy'; dest.mkdir()
    for p in [EXE, EXE.with_suffix('.pdb'), core.HOME/'ledger.jsonl',
              OLD/'HALTED.json', OLD/'OWNER-ATTEMPT-CONSUMED.json']:
        shutil.copy2(p, dest/p.name)
        core.require(core.sha(p)==core.sha(dest/p.name), 'preservation copy differs')
    core.require(core.sha(EXE)==SHA, 'consumed identity differs')
    print('Original trees inventoried; complete raw attempt, ledger, candidate/PDB and failure copied.', flush=True)


def disassemble():
    import pefile
    import capstone
    md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    source=W/'sandbox_inputs/first-world/content/System'
    ranges={'WinDrv.dll': (0x11100000, [(0x1090,0xc4),(0x3390,0x4bc),(0x49b0,0x24a)]),
            'D3DDrv.dll': (0x06960000, [(0xd29a,0x35),(0xe890,0x20),(0xe8e9,0x13),(0xe926,0x30),(0xf4d4,0x18)])}
    result={}
    for name,(base,spans) in ranges.items():
        p=source/name; pe=pefile.PE(str(p)); rows=[]
        for rva,size in spans:
            rows += [dict(address=i.address,hex_address=f'0x{i.address:08x}',bytes=i.bytes.hex(),
                          instruction=i.mnemonic+' '+i.op_str) for i in md.disasm(pe.get_data(rva,size),base+rva)]
        exports=[dict(name=s.name.decode(),rva=s.address) for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name and
                 any(t in s.name for t in (b'SetRes@',b'TryRenderDevice@',b'OpenWindow@',b'StaticConstructor@UWindowsClient'))]
        result[name]=dict(path=str(p),sha256=core.sha(p),preferred_base=pe.OPTIONAL_HEADER.ImageBase,exports=exports,
                          effective_base=base, instructions=rows,
                          relocation_note='Code decoded at translated base; absolute operands in original bytes retain preferred-base values.')
        pe.close()
    wind={i['address']:i for i in result['WinDrv.dll']['instructions']}
    d3d={i['address']:i for i in result['D3DDrv.dll']['instructions']}
    core.require(wind[0x11104bf5]['bytes']=='ff5778' and wind[INITIAL]['instruction']=='test eax, eax', 'initial original callsite')
    core.require(d3d[0x696d2ca]['bytes']=='ff5278' and d3d[PRIMARY]['instruction']=='cmp eax, edi', 'Lock original callsite')
    core.require(d3d[0x696f4e9]['bytes']=='c21400', 'SetRes ret20')
    save(O/'original-x86-decode.json',result)
    return result


def analyze():
    original=disassemble()
    debug=[json.loads(s) for s in (ATTEMPT/'debug-observations.jsonl').read_text().splitlines()]
    raw=(ATTEMPT/'runtime-events.raw.bin').read_bytes()
    core.require(raw==(ATTEMPT/'runtime-stream.raw.bin').read_bytes() and len(raw)%448==0, 'saved raw evidence differs')
    events=[json.loads(raw[i:i+448].split(b'\0',1)[0]) for i in range(0,len(raw),448)]
    core.require(events==read(ATTEMPT/'runtime-events.json')['events'], 'raw decoder mismatch')
    core.require([r['seq'] for r in events]==list(range(1,len(events)+1)), 'raw sequence gaps')
    process=next(r for r in debug if r['kind']=='process_created')
    bp=[r for r in debug if r['kind']=='exception'][-1]
    symbols=read(ATTEMPT/'debugger-plan.json')['symbols']
    core.require(bp['address']==process['base']+symbols['f_696e890']['rva'], 'failure address differs from SetRes function entry')
    # DEBUG_EVENT has an EXCEPTION_RECORD, not a CONTEXT or ReadProcessMemory payload.
    raw_event=next(r for r in debug if r['kind']=='debug_event' and r['index']==bp['index']-1)
    ev=bytes.fromhex(raw_event['raw'])
    core.require(struct.unpack_from('<I',ev,16)[0]==0x80000004 and struct.unpack_from('<Q',ev,32)[0]==bp['address'], 'raw exception decode')
    core.require(not any('cpu' in r or 'frame' in r or 'guest_stack' in r or 'context' in r for r in debug), 'unexpected recoverable frame exists; inspect it')
    viewport=next(e for e in events if e['kind']=='viewport_try_render_call')
    geom=next(e for e in events if e['kind']=='gui_adjust_window_rect_input')
    counts=collections.Counter(e['kind'] for e in events)
    operations={k:counts[k] for k in ('d3d8_device_call','d3d8_device_return','d3d8_render_call','d3d8_render_return','d3d8_state_call','d3d8_state_return','d3d8_batch_call','d3d8_gamma_return','d3d8_material_return')}
    core.require(not any(operations.values()), 'renderer/device operation occurred; characterize independently')
    profile=read(ATTEMPT/'launch-profile.json')
    ini=SANDBOX/'System/Unreal2.ini'
    before=profile['sandbox_before']; after=read(ATTEMPT/'sandbox-after.json')
    core.require(before['System/Unreal2.ini']==after['System/Unreal2.ini']==core.sha(ini), 'INI identity differs')
    save(O/'config-integrity.json',dict(ini_sha256=core.sha(ini),before=before.get('System/Unreal2.ini'),after=after.get('System/Unreal2.ini'),
         profile_source_sha256=read(W/'out/recovery/attachthread-setres-20261029-01/configuration-profile.json')['ini_sha256'],
         command=profile['command']))
    # Separate recorded facts from call-flow reconstruction. None of these are a saved SetRes stack dump.
    words=[dict(index=0,role='return address',value=INITIAL,status='inferred from the unique initial TryRenderDevice virtual call; not captured at rejection'),
           dict(index=1,role='viewport',value=viewport['this'],status='recorded TryRenderDevice this, forwarded by PUSH ESI; no SetRes stack dump'),
           dict(index=2,role='width',value=geom['right']-geom['left'],status='recorded window input width and matching INI; SetRes word not captured'),
           dict(index=3,role='height',value=geom['bottom']-geom['top'],status='recorded window input height and matching INI; SetRes word not captured'),
           dict(index=4,role='fullscreen',value=None,status='not recorded: original computes renderer[+0x70] OR qualified TryRenderDevice fullscreen request; configuration predicts zero'),
           dict(index=5,role='color depth',value=32,status='immediate PUSH 0x20 at initial original caller; not captured at rejection')]
    outcome=dict(classification='observer caller-expectation defect with missing failure-frame evidence',
        exact_observed_setres_frame=None, exact_failed_component_from_saved_frame=None,
        necessary_failed_component_under_original_call_flow='frame[0]: initial 0x11104bf8 versus Lock continuation 0x0696d2cd',
        argument_words=words, layout=['return','viewport','width','height','fullscreen','color_bits'],
        calling_convention='x86 thiscall: renderer in ECX; five stack arguments; RET 20; total guest ESP delta 24',
        raw_debug_records=len(debug),raw_runtime_records=len(events),
        raw_exception=raw_event,stop_exception=bp,entry_symbol_rva=symbols['f_696e890']['rva'],
        evidence_gap='Assertion precedes setres_entry log. Exception handler only snapshots runtime events; raw DEBUG_EVENT has no CPU context or guest memory. No dump exists in the complete consumed attempt.',
        recorded_viewport=viewport,recorded_window_input=geom,device_operations=operations,
        native_adapter_operations=[e for e in events if e['kind'] in ('d3d8_create','d3d8')],
        last_verified_milestone='First SetRes translated function-entry hardware exception, before its guest prologue and before CreateDevice/device rendering. Earlier native adapter discovery and GetDeviceCaps succeeded.',
        endpoint_problem='0x0696d2cd is in Lock device-null recovery, not initial SetRes return. Normal successful initial creation leaves +0x4698 nonzero and Lock skips this call. Do not claim this later endpoint is the first SetRes completion.',
        strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained',
        genuine_launches=0,retry=False,consumed_candidate_executable=False,
        readiness='Non-game validated first-entry diagnostic observer only. Completion launch is not ready: exact historical frame was not saved and consumed candidate must not be retried. A separately prepared fresh candidate and explicit later authorization remain required.')
    save(O/'diagnosis.json',outcome)
    from attach_audit import audit
    attach=audit(events)
    attach['latent_prior_observer_defect']='Prior owner.audit_attach accepts at most one attach=1 pair, but this unchanged genuine path records attach=1 and attach=0. That later audit would also reject this valid original branch.'
    save(O/'attach-detach-audit.json',attach)
    save(O/'config-sources.json',dict(
        width_height=dict(ini='[WinDrv.WindowsClient] WindowedViewportX=1540, WindowedViewportY=945',
            ini_sha256=core.sha(ini),recorded_rectangle=[geom[k] for k in ('left','top','right','bottom')],
            initial_source='WinDrv OpenWindow +34e1..3517 resolves -1 sizes from client +3c/+40; TryRenderDevice +4ad6..4b48 resolves -1 using windowed +3c/+40 or fullscreen +4c/+50; +4bf3 PUSH EAX width, +4bf2 PUSH EBX height',
            lock_source='D3DDrv +d2c1/+d2c5 reads viewport +78/+74 (height/width)'),
        fullscreen=dict(config='StartupFullscreen=false; literal -windowed command argument',
            initial_source='WinDrv +4bcd..4bee: qualified request at [EBP-14], request argument [EBP+14], viewport [+b4], then renderer [+70] OR request',
            lock_source='D3DDrv +d2b3 reads renderer +4674',
            actual_word_captured=False,expected_windowed=0),
        color_bits=dict(initial_source='WinDrv +4bea PUSH 0x20',lock_source='D3DDrv +d2bb PUSH 0x20',
            effective_mode_note='SetRes later rewrites [EBP+18] using renderer +64/+6c and selects renderer +4690 for windowed mode; entry depth is a request, not proof of a created native format',
            configuration='Use16bit=False; no D3D8 presentation parameters were generated in this attempt'),
        identity=dict(recorded_try_render_this=viewport['this'],recorded_try_render_this_hex=f"0x{viewport['this']:08x}",
            initial_source='WinDrv keeps viewport in ESI and PUSH ESI at +4bf4; renderer ECX comes from viewport +5c',
            captured_setres_renderer_this=None,identity_limit='TryRenderDevice receiver is recorded; SetRes stack and renderer receiver are not'),
        legitimacy='1540x945, windowed, requested 32 bits are consistent with the unchanged isolated configuration and native call instructions. Fullscreen source fields and exact live frame remain unobserved. No game/renderer configuration error is established.'))
    print(json.dumps(dict(classification=outcome['classification'],words=words,operations=operations),indent=2))


def verify():
    old=read(O/'preservation.json')
    for root,inventory in old['trees'].items():
        core.require(core.tree(pathlib.Path(root))==inventory,'preserved original changed: '+root)
    core.require(core.tree(ATTEMPT)==core.tree(O/'consumed-attempt-copy'),'raw attempt copy changed')
    import asset_boundary
    protected=asset_boundary.verify()
    core.require(protected==read(ATTEMPT/'launch-profile.json')['protected'],'protected input inventory differs from consumed attempt')
    save(O/'preservation-after.json',dict(passed=True,trees=len(old['trees']),genuine_launches=0,
         original_evidence_unchanged=True,sandbox_unchanged=True,global_ledger_unchanged=True,
         protected=protected,production_breakpoint_changes=0))
    print('All preserved original trees, sandbox, ledger and complete attempt copy unchanged.',flush=True)


if __name__=='__main__':
    core.require(sys.argv[1:] in (['preserve'],['analyze'],['verify']), 'offline subcommand only')
    globals()[sys.argv[1]]()
