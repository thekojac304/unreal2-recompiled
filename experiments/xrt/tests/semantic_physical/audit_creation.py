import argparse
import struct
from pathlib import Path
from recheck import OUT,core
from supervisor import fixture_profiles as F


def audit(ident):
    response=core.read(F.HOME/'responses'/(ident+'.json'));root=Path(response['evidence']);request=core.read(root/'request.json');F.validate_candidate(request)
    spec=core.read(OUT/('fixture-'+request['candidate_id']+'.json'));A=None
    for name,digest in spec['adapter_sources'].items():core.require(core.sha(name)==digest,'source drift')
    values=request['parameters'];arch=values['arch'];translated=values['variant']=='translated';cfg=spec['configuration']
    E,A,_=F.modules();item=F.plan('renderer-group',values,F.candidate_path(request['candidate_id']).parent)[0];pair=E.P.G.verified_pair(arch);directory=root/'captures'/item['name']
    rows,snapshot,events=A.process(directory,physical=True,expected_exe=item['exe'],expected_args=['--physical',pair],expected_build=F.candidate_path(request['candidate_id']).parent/'build/build-record.json',expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
    gpu=A.adapter(rows,snapshot,directory,arch);A.need(gpu['adapter']['vendor']==0x10de,'physical NVIDIA')
    call=A.one(rows,'creation-call');own=A.one(rows,'creation-ownership');clean=A.one(rows,'creation-cleanup');strict=[]
    try:A.abi(call,arch)
    except A.Incomplete as error:
        pre,post=bytes.fromhex(call['pre']),bytes.fromhex(call['post'])
        controls_equal=pre[:2]==post[:2] and struct.unpack_from('<I',pre,24)[0]&~63==struct.unpack_from('<I',post,24)[0]&~63
        # x86 is a comparison oracle, never this x64 runtime's backend. Preserve
        # its measured control failure as a FAILED strict verdict. The assembly
        # fixture restores its saved host FXSAVE state after recording the call.
        # An x64 backend control violation still blocks runtime qualification.
        A.need(controls_equal or arch=='x86','x64 backend control preservation')
        expected=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
        A.need(call['regs']==expected and call['stack_delta']==0,'creation GPR/stack ABI')
        A.need(bytes.fromhex(call['xmm'])==(bytes(160) if arch=='x86' else struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10),'creation XMM ABI')
        A.need(pre[32:42]==post[32:42] and pre[48:58]==post[48:58],'creation x87 values')
        strict.append(dict(reason=str(error),controls_preserved=controls_equal,
            before_control=pre[:2].hex(),after_control=post[:2].hex(),
            before_status=pre[2:5].hex(),after_status=post[2:5].hex(),
            before_mxcsr=pre[24:28].hex(),after_mxcsr=post[24:28].hex(),verdict='FAILED'))
    A.need(call['hr']==0 and call['nonnull'] and call['pending']==0 and call['refs']==1,'creation result/parent ownership')
    A.need(struct.unpack('<13I',bytes.fromhex(call['pp_before']))==tuple(cfg[:6]+[cfg[7],cfg[8],cfg[9],cfg[10],0,0,0]),'creation input configuration')
    A.need(own==dict(kind='creation-ownership',add=2,balance=1,parent_hr=0,same_parent=True,parent_release=2,creation_hr=0,focus=cfg[6],flags=cfg[11]),'created COM identity/creation parameters')
    A.need(all(clean[k] in (0,False) for k in ('device_release','parent_release','window_valid','d3d8_loaded','d3d9_loaded')) and clean['pins']==[0,0] and clean['callbacks']>0,'creation cleanup')
    if translated:
        before=bytearray.fromhex(call['cpu_before']);after=bytes.fromhex(call['cpu_after']);struct.pack_into('<I',before,0,call['hr']);struct.pack_into('<I',before,16,0x2020);struct.pack_into('<I',before,64,0x98765432);A.need(before==after,'creation guest CPU/RET28')
        A.need(call['guest_output']==0x11000 and call['children']==1,'typed device output')
        raw=[r for r in rows if r['kind']=='creation-event'];phases=[r['payload'] for r in raw if r['event']=='d3d8_checkpoint'];A.need([p['phase'] for p in phases]==[0,1,2,3] and all(p['slot']==100 for p in phases),'creation runtime pairing')
        A.need(phases[2]['result']==phases[3]['result']==call['hr'] and phases[2]['error']==phases[3]['error']==call['error'],'creation HRESULT/last-error propagation')
        A.need(any(r['event']=='d3d8_device_audit' and r['payload']['typed_slots']==97 and r['payload']['passed'] for r in raw),'actual adapter vtable audit')
        release=[e['payload'] for e in events if e['event']=='d3d8_device_release'];A.need(len(release)==1 and release[0]['guest_refs']==release[0]['native_count']==0,'actual adapter final Release')
    else:A.need(not events and not any(r['kind']=='creation-event' for r in rows),'native creation scope')
    queries=[]
    if spec.get('mode')=='parent-queries':
        qrows=[r for r in rows if r['kind']=='parent-query'];A.need(len(qrows)==24,'complete public capability queries')
        for i,q in enumerate(qrows):
            A.abi(q,arch);A.need(q['index']==i//4 and q['slot']==(209 if i//4<3 else 211) and q['seed']==[0,18,0x13572468,0xffffffff][i%4],'query/sample binding')
            if translated:
                expected=bytearray.fromhex(q['cpu_before']);struct.pack_into('<I',expected,0,q['hr']);struct.pack_into('<I',expected,16,0x201c);struct.pack_into('<I',expected,64,0x98765432);A.need(expected.hex()==q['cpu_after'],'query CPU/stack preservation')
            queries.append({k:q[k] for k in ('index','slot','seed','error','hr')})
    result=dict(passed=True,functional_verdict='PASSED',strict_verdict='FAILED' if strict else 'PASSED_THIS_SAMPLE_ONLY',request=ident,creation_config=spec['creation_config'],configuration=cfg,parameters=values,gpu=gpu,
        observation={k:call[k] for k in ('hr','error','seed','nonnull','pp_before','pp_after')},strict_differences=strict,
        native_abi_scope='outer creation wrapper; semantic runtime checkpoints additionally pair the actual native HRESULT/error',
        callbacks=clean['callbacks'],active_callbacks=clean['active_callbacks'],production_accepted=False,historical_service_verdict=response,mode=spec.get('mode','creation'),queries=queries)
    core.atomic(OUT/('creation-audit-'+ident+'.json'),result)
    print('CREATION PASS',spec['creation_config'],values,'error',call['error'],'strict',strict,flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('request');audit(p.parse_args().request)
