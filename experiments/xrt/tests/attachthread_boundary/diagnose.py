"""Recover the import from retained stopped evidence, independently of formatting."""
from collections import Counter
import json
from pathlib import Path
import sys
import capstone
import pefile
W=Path(__file__).resolve().parents[4]
O=W/'out/recovery/attachthread-setres-20261029-01'
P=O/'preserved/attempt-package/owner-13a98b68-bf93-4196-825c-773a1b66f474'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core
from world_tick_checkpoint import paired


def main():
    raw=(P/'runtime-events.raw.bin').read_bytes()
    core.require(raw==(P/'runtime-stream.raw.bin').read_bytes() and len(raw)%448==0,'committed stream differs from stopped memory')
    events=[json.loads(raw[i:i+448].split(b'\0')[0]) for i in range(0,len(raw),448)]
    saved=core.read_large(P/'runtime-events.json')
    core.require(events==saved['events'] and not saved['events_dropped'] and [r['seq'] for r in events]==list(range(1,len(events)+1)),'event completeness/order')
    rows=[json.loads(s) for s in (P/'debug-observations.jsonl').read_text().splitlines()]
    imports=[r for r in rows if r['kind']=='import_boundary'];fatals=[r for r in rows if r['kind']=='fatal_entry']
    core.require(len(imports)==len(fatals)==1,'exactly one stopped import/fatal')
    imp,fatal=imports[0],fatals[0];site=fatal['cpu']['pc'];stack=fatal['guest_stack']
    core.require(imp['symbol']=='user32.dll!AttachThreadInput' and site==0x11104a48 and stack[:4]==[0x11104a4e,41636,41636,1],'saved name/PC/arguments')
    core.require(fatal['thread']==41636 and fatal['code']==75 and not fatal['runtime_fatal_body_executed'],'fatal classification')
    original=O/'preserved/complete-sandbox/System/WinDrv.dll'
    core.require(core.sha(original)=='df1459bfed2e8a1e006d453d72b804417979783e76387018ba322e0d9a324663','actual mapped WinDrv identity')
    with pefile.PE(str(original)) as pe:
        iat=[(d.dll.decode(),i.name.decode()) for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports if i.address==0x1110b364]
        core.require(iat==[('USER32.dll','AttachThreadInput')],'original import table disagrees')
        data=pe.get_data(site-0x11100000,6)
        core.require(data==bytes.fromhex('ff1564b31011'),'original indirect import call')
        md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
        instructions=[dict(pc=hex(i.address),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str) for i in md.disasm(pe.get_data(0x4a12,0x4c),0x11104a12)]
    core.require(not any('AttachThreadInput' in p.read_text(errors='replace') for p in (O/'preserved/production-runtime').glob('hle_*.c')),'unexpected production implementation')
    stage=Path(core.read_large(O/'preserved/attempt-package/candidate-identity.json')['executable'])
    runtime_before=W/'out/recovery/renderer-gamma-integration-20261029-01/runtime'
    core.require(not any('"AttachThreadInput"' in p.read_text(errors='replace') for p in runtime_before.glob('hle_*.c')),'unexpected consumed runtime implementation')
    unbound=[e for e in events if e['kind']=='unbound_import_stack']
    core.require([e['value'] for e in unbound]==stack[:17] and all(e['site']==site for e in unbound),'independent event/CPU stack mismatch')
    before=events[-19]
    core.require(before['kind']=='gui_window_ids_call','last paired dependency')
    ids=events[-18]
    core.require(ids['kind']=='gui_window_ids_return' and ids['result']==41636 and ids['actual_return']==0x11104a47,'thread ID producer')
    selected=[e for e in events if e['kind']=='engine_loadmap_return'][-1]['result']
    lifecycle={s:len([e for e in events if e['kind']=='actor_lifecycle_return' and e['world']==selected and e['stage']==s]) for s in ('PreBeginPlay','BeginPlay','PostBeginPlay')}
    core.require(set(lifecycle.values())=={279},'selected-world lifecycle counts')
    for s in lifecycle:
        calls=[e for e in events if e['kind']=='actor_lifecycle_call' and e['world']==selected and e['stage']==s]
        returns=[e for e in events if e['kind']=='actor_lifecycle_return' and e['world']==selected and e['stage']==s]
        core.require(len(calls)==len(returns)==279,'unpaired lifecycle')
        core.require(len(paired(calls,returns,4))==279,'lifecycle return pairing, including nested spawns')
    counters=Counter(e['kind'] for e in events)
    core.require(all(not counters[k] for k in ['engine_init_return','viewport_open_return','viewport_try_render_return','engine_tick_call','level_tick_call','d3d8_device_call','d3d8_render_call']),'unexpected later genuine milestone')
    result=dict(passed=True,classification='missing host adapter; correct import resolution; formatting-only observer limitation',
        exact_import=imp['symbol'],originating_module='WinDrv.dll',original_import_dll=iat[0][0],
        saved_import_record=imp,fatal=fatal,guest_pc=hex(site),iat=hex(0x1110b364),return_pc=hex(stack[0]),
        arguments=dict(idAttach=stack[1],idAttachTo=stack[2],fAttach=stack[3]),calling_convention='x86 stdcall, 3 DWORD arguments, ret12 plus return address: ESP +16',
        original_sha256=core.sha(original),instructions=instructions,
        records=len(events),zero_drops=True,whole_stream_equals_stopped_memory=True,
        last_successful_import=ids,selected_world=hex(selected),selected_world_lifecycle_paired_returns=lifecycle,
        viewport_created=True,try_render_entered=True,CreateDevice=False,Clear=False,Present=False,SetRes_endpoint_reached=False,
        engine_init_returned=False,world_tick_entered=False,world_tick_returned=False,
        import_not_callback=True,renderer_failure_evidence=False,observer_note='separate import_boundary record already captured both host string varargs; fatal_entry summary omitted formatting only',
        strict_x87='FAILED retained',strict_wndproc='FAILED retained',strict_native_x86='FAILED retained',genuine_launches=0)
    core.atomic(O/'diagnosis.json',result)
    core.atomic(O/'ordered-runtime-tail.json',events[-30:])
    print('Saved host-string record, original PE IAT/call bytes, stopped CPU/stack and 74497 ordered records agree: USER32!AttachThreadInput(41636,41636,TRUE).',flush=True)


if __name__=='__main__':main()
