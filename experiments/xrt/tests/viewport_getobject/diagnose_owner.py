"""Preserve the consumed viewport continuation and diagnose its next guard. No launches."""
import collections,importlib.util,json,subprocess,sys,zipfile
from pathlib import Path
import capstone,pefile
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('queryclass_diagnosis_retained_checks',H/'prepare.py')
Q=importlib.util.module_from_spec(spec);spec.loader.exec_module(Q)
P=Q.P;W=P.W
CONSUMED=P.O
O=W/'out/recovery/viewport-queryclass-diagnosis-20261029-02'
SB=W/'sandbox_cmp/viewport-getobject-20261028-01'

def save(name,value):P.save(O/name,value)

def archive(name,paths):
    entries={p.relative_to(W).as_posix():P.sha(p) for p in paths}
    dest=O/name
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for rel,h in sorted(entries.items()):
            assert P.sha(W/rel)==h,rel;z.write(W/rel,rel)
    with zipfile.ZipFile(dest) as z:
        for rel,h in entries.items():
            with z.open(rel) as f:assert P.C.hashlib.file_digest(f,'sha256').hexdigest()==h,rel
    print('ARCHIVED / READBACK VERIFIED',name,len(entries),flush=True)
    return dict(path=name,sha256=P.sha(dest),files=entries)

def main():
    assert not sys.flags.optimize
    P.check(CONSUMED,P.read(CONSUMED/'artifact-manifest.json'))
    P.check(W,P.read(CONSUMED/'current-sources.json'))
    Q.integrity()
    assert (CONSUMED/'GENUINE-ATTEMPT-CONSUMED.json').exists()
    run=CONSUMED/'genuine-owner-run';session=run/'session'
    assert not (run/'completed.json').exists()
    O.mkdir()
    debug=[json.loads(l) for l in (session/'debug-observations.jsonl').read_text().splitlines()]
    fatal,=[r for r in debug if r['kind']=='fatal_entry']
    created,=[r for r in debug if r['kind']=='process_created']
    plan=P.read(session/'debugger-plan.json');launch=P.read(session/'launch.json');base=created['base']
    assert plan==P.read(CONSUMED/'candidate-debugger-plan.json') and launch['pid']==created['pid']
    exe=Path(launch['executable']);assert P.sha(exe)==launch['sha256']==plan['sha256']
    assert P.sha(exe.with_suffix('.pdb'))==plan['pdb_sha256']
    assert fatal['host']['registers']['rip']==base+plan['symbols']['xrt_fatal']['rva']
    assert fatal['code']==76 and not fatal['runtime_fatal_body_executed'] and not fatal['diagnostic_read_errors']
    assert fatal['decoded_arguments']==dict(message=61,wp=0,lp=0xfffffffffffffff4)
    assert fatal['formatted_message']=='WM_GETOBJECT: unmeasured dialog/arguments (wp=0 lp=fffffffffffffff4)'
    assert fatal['cpu']['pc']==0x111071e2
    windrv=pefile.PE(str(SB/'System/WinDrv.dll'))
    assert windrv.get_data(0x71e2,6).hex()=='ff152cb31011'
    imported,=[i.name.decode() for entry in windrv.DIRECTORY_ENTRY_IMPORT for i in entry.imports if i.address==0x1110b32c]
    assert imported=='DefWindowProcW'
    ev=P.read(session/'runtime-events.json');raw=(session/'runtime-events.raw.bin').read_bytes()
    assert len(raw)%448==0
    events=[json.loads(raw[i:i+448].split(b'\0',1)[0]) for i in range(0,len(raw),448)]
    assert events==ev['events'] and len(events)==ev['events_recorded']==74407 and ev['events_dropped']==0
    assert [r['seq'] for r in events]==list(range(1,len(events)+1)) and not any(r.get('truncated') for r in events)
    def es(kind):return [r for r in events if r['kind']==kind]
    returns=es('gui_get_object_callback_return');assert len(returns)==2
    startup,viewport=returns
    assert startup['proc']==0x10901000 and startup['result']==0
    assert viewport==dict(seq=74407,thread=0,kind='gui_get_object_callback_return',hwnd=4716,
        proc=0x1100b060,wparam=0xffffffff,object_id=0xfffffffc,result=0,last_error=0)
    assert events[-1]==viewport
    assert es('gui_callback')[-1]['message']==61 and es('gui_callback')[-1]['proc']==viewport['proc']
    fixture=P.read(CONSUMED/'oracle/queryclass-report.json')
    fixture_fatal,=[r for r in fixture['events'] if r['kind']=='fatal']
    assert fixture_fatal['message']==fatal['formatted_message']
    init,=[r for r in es('dmusic_backend') if r['sequence']==4]
    assert (init['op'],init['id'],init['result'],init['out_id'],init['type'])==(6,2,0,3,3)
    assert es('dmusic_backend_start')[0]['timeout_ms']==10000
    maps=[];pending=[]
    for r in events:
        if r['kind']=='engine_loadmap_call':pending.append(r)
        elif r['kind']=='engine_loadmap_return':
            call=pending.pop();assert call['return']==r['return']==r['actual_return']
            assert call['this']==r['this'] and call['esp']==r['esp_before'] and r['esp_after']==call['esp']+20 and r['result']
            maps.append(dict(call=call,returned=r))
    assert not pending and len(maps)==2;selected=maps[-1]['returned']['result'];lifecycle={}
    for stage in ['PreBeginPlay','BeginPlay','PostBeginPlay']:
        stack=[];pairs=[]
        for r in events:
            if r['kind']=='actor_lifecycle_call' and r['stage']==stage:stack.append(r)
            elif r['kind']=='actor_lifecycle_return' and r['stage']==stage:
                call=stack.pop();assert all(call[k]==r[k] for k in ['this','world','return'])
                assert call['esp']==r['esp_before'] and call['return']==r['actual_return'];pairs.append((call,r))
        assert not stack
        lifecycle[stage]=dict(paired_returns=len(pairs),selected_world_paired_returns=sum(r['world']==selected for c,r in pairs))
        assert lifecycle[stage]['selected_world_paired_returns']==279
    readbacks=[r for r in debug if r['kind']=='breakpoints_readback'];assert len(readbacks)==36
    for r in readbacks:
        assert r['permanent_stop_present'] and base+plan['stop_rva'] in r['addresses']
        assert r['dr']==r['addresses']+[0]*(4-len(r['addresses']))
        assert r['dr7']&0xffff00ff==sum(1<<(2*i) for i in range(len(r['addresses'])))
    assert not [r for r in debug if r['kind']=='hard_stop_0696f292']
    absent=['d3d8_device_call','d3d8_render_call','d3d8_state_call','engine_init_return','engine_tick_call','level_tick_call']
    assert not any(es(kind) for kind in absent)
    lookup=P.load('queryclass_native_symbols',H/'../getobject_boundary/debugger_test.py')
    symbols=lookup.symbols(exe,['invoke_gui_proc','xrt_fatal']);pe=pefile.PE(str(exe),fast_load=True)
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);sym=symbols['invoke_gui_proc']
    instructions=list(md.disasm(pe.get_data(sym['rva'],sym['size']),base+sym['rva']))
    rows=[dict(rva=i.address-base,bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in instructions]
    arg,=[r for r in rows if r['rva']==0x6f03aac]
    assert arg['mnemonic']=='mov' and arg['operands']=='r12d, dword ptr [rbp + 0x240]'
    assert not [r for r in rows if arg['rva']<r['rva']<0x6f03d6d and r['mnemonic'] in ['mov','lea','xor','add','sub'] and r['operands'].split(',')[0] in ['r12','r12d']]
    regs=fatal['host']['registers'];assert regs['r12']==0x1100b060 and regs['r14']==0 and regs['rdi']==0xfffffffffffffff4
    compare,=[r for r in rows if r['rva']==0x6f03d64]
    branch,=[r for r in rows if r['rva']==0x6f03d67]
    assert compare['mnemonic']=='cmp' and compare['operands']=='r14, rax' and regs['rax']==0xffffffff
    assert branch['mnemonic']=='jne' and int(branch['operands'],16)==base+0x6f04659
    caller=fatal['native_caller_return']-base;assert caller==0x6f04676
    save('native-disassembly.json',dict(base=base,symbols=symbols,explicit_proc_argument=arg,caller_rva=caller,instructions=rows))
    cleanup=P.read(run/'cleanup.json');initial=P.read(run/'initial-state.json')
    assert cleanup['passed'] and cleanup['process_cleanup'] and cleanup['locks_reacquired']
    assert cleanup['state']==initial['state'] and cleanup['physical_clip']==initial['physical_clip'] and not cleanup['state']['processes']
    environment=P.load('queryclass_owner_environment',W/'out/recovery/session-aware-136-20261026-01/owner.py')
    baseline=P.read(CONSUMED/'owner-evidence-audit.json')['baseline'];environment_files=sorted(run.glob('*-environment.json'))
    assert len(environment_files)==5
    for p in environment_files:assert environment.environment_gate(P.read(p))==baseline
    meta_path,=[p for p in (W/'experiments/xrt/results/raw/level').glob('*/meta.json') if P.read(p).get('sandbox')==str(SB)]
    meta=P.read(meta_path);sandbox=P.tree(SB)
    changes={rel:dict(before=meta['before'].get(rel),after=sandbox.get(rel)) for rel in meta['before'].keys()|sandbox.keys() if meta['before'].get(rel)!=sandbox.get(rel)}
    def mutable(rel):
        n=rel.lower();return n.startswith(('save/','cache/')) or n=='system/golem.u' or (n.startswith('system/') and n.endswith(('.ini','.log')))
    assert all(mutable(rel) for rel in changes),changes
    save('sandbox-manifest.json',dict(root=str(SB),files=sandbox,changes=changes));save('sandbox-metadata.json',P.metadata(SB))
    assert P.sha(W/'debug-symbols.json')==P.sha(session/'debug-symbols.json')
    print('GENUINE REGISTERED OBJID_CLIENT RETURN / NEXT GUARDED QUERYCLASS REQUEST VERIFIED',flush=True)
    archives=[archive('consumed-owner-evidence.zip',P.C.files(CONSUMED)+P.C.files(meta_path.parent)+[W/'debug-symbols.json']),
        archive('complete-consumed-sandbox.zip',P.C.files(SB)),archive('exact-consumed-client-build.zip',P.C.files(exe.parent))]
    save('preservation.json',dict(passed=True,archives=archives,consumed_marker_sha256=P.sha(CONSUMED/'GENUINE-ATTEMPT-CONSUMED.json'),
        inherited_source_archives=[dict(path=str(CONSUMED/n),sha256=P.sha(CONSUMED/n)) for n in ['pending-source-state.zip','pending-source-state-v2.zip']],
        consumed_files_modified=False,runtime_changes=False,genuine_sessions_launched=0))
    diagnosis=dict(passed=True,owner_attempt_consumed=True,retry_permitted=False,registered_OBJID_CLIENT_recovery_genuinely_completed=viewport,
        startup_dialog_completed=startup,actual_guest_InitAudio=init,loadmap_pairs=maps,selected_world=hex(selected),lifecycle=lifecycle,
        next_stop=dict(message='WM_GETOBJECT',wparam=0,object_id='OBJID_QUERYCLASSNAMEIDX',lparam_x64='0xfffffffffffffff4',lparam_x86='0xfffffff4',
            signed_object_id=-12,guest_pc=hex(fatal['cpu']['pc']),guest_pending_import='USER32!DefWindowProcW',explicit_proc=hex(regs['r12']),
            procedure='Window.dll+0xb060',matches_retained_fixture_guard=True,diagnostic_word_dialog='Shared error wording; this remains the registered WNDPROC path'),
        events_recorded=len(events),events_dropped=0,raw_records_equal=True,permanent_stop_readbacks=len(readbacks),permanent_stop_hit=False,
        CreateDevice=0,Clear=0,Present=0,SetRenderState=0,engine_init_returned=False,engine_ticks=0,world_ticks=0,
        environment_observations=len(environment_files),cleanup_passed=True,strict_x87='FAILED; retained separately',strict_wndproc_equality='FAILED; retained separately',
        new_genuine_sessions_launched=0,new_launcher_prepared=False,
        next_work='Separately characterize and implement the registered-window OBJID_QUERYCLASSNAMEIDX protocol, including the real accessibility fallback, while preserving unrelated IDs/arguments/results. No rerun of the consumed owner command.')
    save('diagnosis.json',diagnosis)
    assert not environment.V.state()['processes']
    P.check(CONSUMED,P.read(CONSUMED/'artifact-manifest.json'));P.check(W,P.read(CONSUMED/'current-sources.json'));Q.integrity()
    assert P.tree(SB)==sandbox and P.metadata(SB)==P.read(O/'sandbox-metadata.json')
    for a in archives:P.check(W,a['files']);assert P.sha(O/a['path'])==a['sha256']
    report=f'''Consumed viewport continuation diagnosis — October 29, 2026 (US Eastern)

The registered-window OBJID_CLIENT fix genuinely completed. Actual Window.dll+0xb060
returned 0, last-error 0, for WM_GETOBJECT(0xffffffff, 0xfffffffc), HWND token 4716.
The startup dialog also returned 0. The later fatal is a separate, deliberately
retained request: WM_GETOBJECT(0, OBJID_QUERYCLASSNAMEIDX=-12), x64 lParam
0xfffffffffffffff4 / x86 0xfffffff4. It matches the previously recorded native
accessibility fallback and translated fixture rejection exactly.

The shared diagnostic still says "dialog/arguments"; exact new EXE/PDB data flow
confirms explicit_proc=0x1100b060, the registered WNDPROC. Guest PC remains
0x111071e2 at USER32!DefWindowProcW during viewport focus. This is not a recurrence
of the rejected OBJID_CLIENT tuple and is not a Python startup failure.

Existing startup progress remains: actual InitAudio S_OK; both LoadMap calls paired;
279 paired selected-world lifecycle returns per stage. No CreateDevice, Clear,
Present, SetRenderState, engine-init return or world tick. All {len(events):,} events
match raw stopped-memory records with contiguous sequence numbers and zero drops.
All {len(readbacks)} permanent-stop readbacks retain the stop before guest 0x0696f292;
it was not reached. Five owner environment records and cleanup pass; processes empty.

The owner command is CONSUMED. Do not rerun it. No new launcher or genuine session
was created by this diagnosis. No runtime, source-bound candidate, helper, renderer
or x87 behavior changed. Strict x87 and full WNDPROC equality remain separately FAILED.

Preservation: sealed preparation, all owner/raw evidence, observer's matching root
debug-symbols byproduct, exact 279-object EXE/PDB build and complete sandbox/metadata
are retained and archived with SHA-256/readback verification. Original protected
assets and pinned dependencies pass; prior sources/builds/evidence remain unchanged.

Next work: a separate, bounded OBJID_QUERYCLASSNAMEIDX recovery with real registered
WNDPROC/default processing and accessibility oracles. Preserve unrelated object IDs,
argument combinations, message variants and nonzero-result guards. Do not reopen
DirectMusic or general x87 investigations; no genuine game launch during that work.
'''
    (O/'REPORT.txt').open('x',encoding='utf-8').write(report);save('artifact-manifest.json',P.tree(O))
    print('CONSUMED RUN PRESERVED / NEXT BOUNDARY CLASSIFIED / NO RETRY OR GAME LAUNCH',flush=True)

if __name__=='__main__':main()
