"""Independent semantic schema audit of saved physical collector evidence."""
import argparse
import struct
from pathlib import Path
from recheck import OUT, PRIOR, core
from supervisor import fixture_profiles as F


def expected_cpu(call):
    raw=bytearray(416)
    regs=[0x76543210+i for i in range(8)];regs[4]=0x2000
    if not call['rejected']:
        regs[0]=0x76543210 if call['slot']==18 else call['hr'];regs[4]+=4*((7 if call['slot']==36 else 4 if call['slot'] in (63,83) else 2 if call['slot'] in (42,76) else 3)+1)
        struct.pack_into('<I',raw,64,0x98765432)
    struct.pack_into('<8I',raw,0,*regs)
    struct.pack_into('<I',raw,32,1);struct.pack_into('<I',raw,52,1)
    struct.pack_into('<I',raw,68,0x12345678)
    struct.pack_into('<8d',raw,72,*[i+.5 for i in range(8)])
    struct.pack_into('<IHH',raw,136,6,0x27f,0x4020)
    return raw.hex()


def audit(ident):
    response=core.read(F.HOME/'responses'/(ident+'.json'))
    root=Path(response['evidence']);request=core.read(root/'request.json')
    F.validate_candidate(request)
    spec=core.read(OUT/('fixture-'+request['candidate_id']+'.json'))
    for name,digest in spec['adapter_sources'].items():
        core.require(core.sha(name)==digest,'adapter source drift')
    values=request['parameters'];arch=values['arch'];translated=values['variant']=='translated'
    E,A,_=F.modules();item=F.plan('renderer-group',values,F.candidate_path(request['candidate_id']).parent)[0]
    path=root/'captures'/item['name'];pair=E.P.G.verified_pair(arch)
    rows,snap,events=A.process(path,physical=True,expected_exe=item['exe'],expected_args=['--physical',pair],
        expected_build=F.candidate_path(request['candidate_id']).parent/'build/build-record.json',expected_backend=[pair/'d3d8.dll',pair/'d3d9.dll'])
    gpu=A.adapter(rows,snap,path,arch);A.need(gpu['adapter']['vendor']==0x10de,'NVIDIA GPU required')
    assurance=core.read(root/'assurance.json');A.need(assurance['cleanup_verified'] and assurance['integrity_verified'],'independent containment assurance')
    A.need(A.one(rows,'semantic-create')==dict(kind='semantic-create',hr=0,width=800,height=600),'fixture creation result')
    A.need(A.one(rows,'semantic-ownership')==dict(kind='semantic-ownership',add=2,balance=1,parent_hr=0,same_parent=True,parent_release=2,creation_hr=0,same_window=True,flags=66),'COM identity/references')
    clean=A.one(rows,'semantic-cleanup')
    A.need(all(clean[k] is True for k in ('destroyed','unregistered','free_d3d8','free_d3d9','guest_freed')),'cleanup resources')
    A.need(all(clean[k] in (0,False) for k in ('device_release','parent_release','window_valid','d3d8_loaded','d3d9_loaded')),'cleanup references/modules')
    A.need(clean['callbacks']>0,'real owned window callbacks absent')
    count=len(spec['samples'])*4
    A.need(A.one(rows,'semantic-summary')==dict(kind='semantic-summary',calls=count,translated=translated,group=values['group']),'sample coverage summary')
    A.need([r['kind'] for r in rows]==['semantic-create','semantic-ownership','semantic-caps','backend-adapter']+['semantic-call','semantic-readback']*count+['semantic-cleanup','semantic-summary'],'exact stream completeness')
    calls=rows[4:-2:2];reads=rows[5:-2:2];observed=[];strict=[];rejections=[]
    for ordinal,(c,r) in enumerate(zip(calls,reads)):
        index,seed=divmod(ordinal,4);sample=spec['samples'][index]
        A.need([c[k] for k in ('slot','a','b','c','input_kind','invalid')]==sample and c['index']==index and c['seed']==[0,18,0x13572468,0xffffffff][seed],'sample/seed identity')
        try:A.abi(c,arch)
        except A.Incomplete as error:
            # Status differences are evidence, never a waiver of control/ABI.
            pre,post=bytes.fromhex(c['pre']),bytes.fromhex(c['post'])
            A.need(len(pre)==len(post)==512,'raw FPU length')
            A.need(pre[:2]==post[:2] and (struct.unpack_from('<I',pre,24)[0]&~63)==(struct.unpack_from('<I',post,24)[0]&~63),'FPU controls changed')
            A.need(c['stack_delta']==0,'stack changed')
            expected=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
            A.need(c['regs']==expected,'nonvolatile registers changed')
            A.need(bytes.fromhex(c['xmm'])==(bytes(160) if arch=='x86' else struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10),'XMM changed')
            A.need(pre[32:42]==post[32:42] and pre[48:58]==post[48:58],'x87 values changed')
            strict.append(dict(ordinal=ordinal,reason=str(error),pre=c['pre'],post=c['post']))
        if translated:A.need(c['cpu']==c['expected_cpu']==expected_cpu(c),'independently reconstructed guest CPU preservation')
        if c['rejected']:
            A.need(translated and c['hr'] is None and c['rejection_utf8_hex'],'guard rejection evidence')
            rejections.append(dict(index=index,sample=sample,seed=c['seed'],reason=bytes.fromhex(c['rejection_utf8_hex']).decode()))
        else:
            A.need(type(c['hr']) is int,'actual HRESULT missing')
            if not c['invalid']:
                A.need(c['hr']==0 and r['hr']==0,'valid sample failed')
                if c['slot'] in (37,42):A.need(r['bytes']==c['input'],'typed input/readback mismatch')
                if c['slot'] in (61,83,85):A.need(not r['nonnull'],'NULL resource readback')
                if c['slot']==36:A.need(r['value']==0x123456,'actual cleared backbuffer pixel')
        observed.append(dict(sample=sample,seed=c['seed'],error=c['error'],hr=c['hr'],rejected=c['rejected'],readback=r,input=c['input']))
    if translated:
        entries=[e for e in events if e['event']=='d3d8_semantic_entry'];A.need(len(entries)==count,'runtime entry completeness')
        checkpoints=[e['payload'] for e in events if e['event']=='d3d8_checkpoint']
        position=0
        for c in calls:
            phases=[0] if c['rejected'] else [0,1,2,3]
            chunk=checkpoints[position:position+len(phases)];position+=len(phases)
            A.need([e['phase'] for e in chunk]==phases and all(e['slot']==c['slot'] for e in chunk),'paired runtime checkpoint phases')
            if not c['rejected']:A.need(chunk[2]['result']==chunk[3]['result']==c['hr'] and chunk[2]['error']==chunk[3]['error']==c['error'],'runtime/native result error transfer')
        A.need(position==len(checkpoints),'unexpected native checkpoint')
    else:A.need(not events,'native variant unexpectedly emitted translated telemetry')
    result=dict(passed=True,scope='sampled semantic methods; no game',request=ident,candidate=spec['candidate_id'],parameters=values,
        physical_nvidia=True,gpu=gpu,observations=observed,strict_differences=strict,rejections=rejections,
        callback_scope='real owned USER32 window procedure; production registered guest WNDPROC is not exercised',
        cleanup=clean,events=len(events),historical_service_verdict=response,production_accepted=False,
        semantic_candidate_sha256=spec['semantic_candidate_sha256'],mode=spec.get('mode','scalar'),native_abi_scope=spec.get('native_abi_scope','direct native call / outer translated adapter'))
    core.atomic(OUT/('audit-'+ident+'.json'),result)
    print('AUDIT PASS',values,'calls',count,'rejections',len(rejections),'strict differences',len(strict),'GPU',gpu['adapter']['name'],flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('request');audit(p.parse_args().request)
