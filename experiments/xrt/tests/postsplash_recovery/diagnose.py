"""Offline PE/PDB and retained-record analysis; never replays a genuine client."""
import collections, ctypes as C, importlib.util, json, struct, sys
from pathlib import Path
import capstone, pefile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('post_preservation',HERE/'preserve.py');P=importlib.util.module_from_spec(s);s.loader.exec_module(P)
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    assert P.read(P.O/'preservation.json')['passed']
    P.check(P.W,P.read(P.O/'preservation.json')['consumed_evidence'])
    session=P.OLD/'genuine-owner-run/session';launch=P.read(session/'launch.json');plan=P.read(session/'debugger-plan.json')
    debug=[json.loads(l) for l in (session/'debug-observations.jsonl').read_text().splitlines()]
    fatal,=[r for r in debug if r['kind']=='fatal_entry'];created,=[r for r in debug if r['kind']=='process_created']
    base=created['base'];regs=fatal['host']['registers']
    assert created['pid']==launch['pid']==33704 and fatal['thread']==52376
    assert P.sha(P.B/'xrt_ucc.exe')==launch['sha256']==plan['sha256']
    assert P.sha(P.B/'xrt_ucc.pdb')==plan['pdb_sha256']
    assert regs['rip']==base+plan['symbols']['xrt_fatal']['rva'] and fatal['format']=='%s' and fatal['code']==76
    assert fatal['raw_integer_arguments'][0]==regs['r9']==regs['rdi']+64
    probe=load('post_debugger_symbol_helpers',P.W/'experiments/xrt/tests/getobject_boundary/debugger_test.py')
    names=['dm_backend_invoke','dmb_exchange','dmb_read','dmb_failed','dmb_disconnect','dmi_InitAudio','xrt_fatal']
    syms=probe.symbols(P.B/'xrt_ucc.exe',names)
    pe=pefile.PE(str(P.B/'xrt_ucc.exe'),fast_load=True);md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True
    caller=fatal['native_caller_return']-base
    match=[name for name,row in syms.items() if row['rva']<=caller<row['rva']+row['size']]
    assert match==['dm_backend_invoke']
    assembly={}
    for name,row in syms.items():
        assembly[name]=[dict(rva=i.address-base,bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in md.disasm(pe.get_data(row['rva'],row['size']),base+row['rva'])]
    P.save(P.O/'native-disassembly.json',dict(base=base,symbols=syms,caller_rva=caller,functions=assembly))
    guest=P.read(P.R/'meta.json');engine=pefile.PE(str(P.SB/'System/Engine.dll'),fast_load=True)
    cpu=fatal['cpu'];assert cpu['pc']==0x10481869
    code=engine.get_data(cpu['pc']-0x10300000,6);assert code[:6].hex()=='ff91b0000000'
    frame=fatal['guest_stack'];assert frame[:9]==[0x1048186f,86440,0,339503884,0,8,128,63,0]
    ev=P.read(session/'runtime-events.json');raw=(session/'runtime-events.raw.bin').read_bytes()
    rows=[json.loads(raw[i:i+448].split(b'\0',1)[0]) for i in range(0,len(raw),448)]
    assert rows==ev['events'] and len(rows)==ev['events_recorded']==25840 and not ev['events_dropped']
    assert [r['seq'] for r in rows]==list(range(1,len(rows)+1)) and not any(r.get('truncated') for r in rows)
    kinds=collections.Counter(r['kind'] for r in rows)
    relevant=[r for r in rows if r['kind'] in ['gui_get_object_callback_return','gui_create_dialog','engine_init_call','engine_init_return','engine_loadmap_call','engine_loadmap_return',
        'client_init_call','client_init_return','com_initialize','dmusic_backend_start','dmusic_backend','com_factory','d3d8_create','d3d8','d3d8_backend']]
    lifecycle={}
    for stage in ['PreBeginPlay','BeginPlay','PostBeginPlay']:
        calls=[r for r in rows if r['kind']=='actor_lifecycle_call' and r['stage']==stage]
        returns=[r for r in rows if r['kind']=='actor_lifecycle_return' and r['stage']==stage]
        stacks=[]
        for r in rows:
            if r['kind']=='actor_lifecycle_call' and r['stage']==stage:stacks.append(r)
            elif r['kind']=='actor_lifecycle_return' and r['stage']==stage:
                c=stacks.pop();assert all(c[k]==r[k] for k in ['this','world','return']) and c['esp']==r['esp_before'] and r['actual_return']==c['return']
        lifecycle[stage]=dict(calls=len(calls),returns=len(returns),unreturned=len(stacks),worlds={hex(w):sum(r['world']==w for r in returns) for w in {r['world'] for r in calls}})
    hard=base+plan['stop_rva'];readbacks=[r for r in debug if r['kind']=='breakpoints_readback']
    for r in readbacks:
        assert r['permanent_stop_present'] and hard in r['addresses'] and r['dr']==r['addresses']+[0]*(4-len(r['addresses']))
        assert r['dr7']&0xffff00ff==sum(1<<(2*i) for i in range(len(r['addresses'])))
    message_inventory=[]
    for path in [session/'runtime-events.json',P.R/'host-output.txt',P.R/'xrt.log',P.OLD/'genuine-owner-run/STOP.txt']:
        data=path.read_bytes();message_inventory.append(dict(path=str(path),contains_directmusic_deadline_literal=b'DirectMusic IPC deadline exceeded' in data))
    P.save(P.O/'diagnosis.json',dict(passed=True,format='%s',string_argument_address=regs['r9'],string_storage='thread-local dm_backend_connection.error, byte offset 64',
        string_bytes_retained=False,exact_formatted_string_recoverable_from_retained_records=False,
        known_error_format='%s (Win32 %lu)',error_reason_and_win32_code='Not captured; do not infer their values',
        fatal_source='runtime/dmusic_backend_pipe.inc:8; dm_backend_invoke after dmb_exchange returned false',native_caller_rva=caller,native_function='dm_backend_invoke',
        intended_exit=76,guest_pc='0x10481869',guest_module='Engine.dll',guest_module_offset='0x181869',guest_instruction=code.hex(),api='IDirectMusicPerformance8::InitAudio, vtable slot 44',
        guest_arguments=dict(this=frame[1],ppDirectMusic=frame[2],ppDirectSound=frame[3],hwnd=frame[4],default_path=frame[5],pchannels=frame[6],flags=frame[7],params=frame[8]),
        completed_WM_GETOBJECT=True,events_recorded=len(rows),events_dropped=0,kinds=dict(kinds),relevant_events=relevant,lifecycle=lifecycle,
        completed_selected_CS_Intro_LoadMap=False,engine_init_returned=False,engine_ticks=0,world_ticks=0,device_calls=0,Clear=0,Present=0,
        pending_directmusic_operation='InitAudio; no successful reply/HRESULT retained',Script_Init_reached=False,
        observed_helper_log='HELLO, Loader8 and Performance8 replies; repeated wdmaud.drv opens; no InitAudio completion',
        timeout_evidence='Approximately 10.004 seconds between last thread breakpoint readback and fatal; transport configured for 10000 ms. This supports but does not prove a specific deadline error text.',
        permanent_stop_readbacks=len(readbacks),hard_stop_hit=False,owner_splash='User-reported visual only, no captured rendered game frame',message_inventory=message_inventory,
        classification='DirectMusic transport/native-helper startup failure plus an observer string-dereference omission; not a new WM_GETOBJECT rejection',genuine_sessions_launched=0))
    print('OFFLINE BOUNDARY PROVED; TRANSIENT %s BYTES WERE NOT RETAINED',flush=True)
if __name__=='__main__':main()
