"""Original PE and generated-source call inventory; no machine code execution."""
import re,sys
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
import capstone,pefile
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM
BASE={'D3DDrv.dll':0x6960000,'WinDrv.dll':0x11100000,'Engine.dll':0x10300000}
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);md.detail=True
def function(dll,start,end,label):
    path=P.A.source()/'System'/dll;pe=pefile.PE(str(path));base=BASE[dll]
    ins=list(md.disasm(pe.get_data(start,end-start),base+start))
    texts={p:p.read_text()for p in (P.W/'experiments/xrt/gen'/dll.split('.')[0].lower()).glob('*.c')}
    imports={x.address:(d.dll.decode()+'!'+(x.name.decode()if x.name else '#'+str(x.ordinal)))for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports}
    export={e.address: e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    rows=[]
    for j,i in enumerate(ins):
        if i.mnemonic!='call':continue
        mark=f'P(0x{i.address:x}u);'
        match=[(p,t.index(mark))for p,t in texts.items()if mark in t];assert len(match)==1,(label,hex(i.address))
        source,at=match[0];t=texts[source];line=t.count('\n',0,at)+1
        context=[dict(guest=hex(x.address),bytes=x.bytes.hex(),asm=x.mnemonic+' '+x.op_str)for x in ins[max(0,j-14):j+2]]
        symbol=None
        if i.operands[0].type==X86_OP_MEM and not i.operands[0].mem.base:
            symbol=imports.get(i.operands[0].mem.disp)
        elif i.operands[0].type==X86_OP_IMM:symbol=export.get(i.operands[0].imm-base)
        rows.append(dict(address=hex(i.address),bytes=i.bytes.hex(),target=i.op_str,symbol=symbol,
            generated_source=str(source.relative_to(P.W)),line=line,generated_call=t[at:t.index('\n',t.index('\n',at)+1)],context=context))
    key=label.replace(' ','-')
    (P.O/(key+'.asm.txt')).write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():20} {i.mnemonic} {i.op_str}'for i in ins)+'\n')
    P.save(key+'.json',dict(module=dll,rva=[hex(start),hex(end)],original_sha256=P.core.sha(path),
       generated={str(p.relative_to(P.W)):P.core.sha(p)for p in texts},calls=rows,all_call_sites_have_generated_markers=True))
    return ins,rows
def main():
    _,tail=function('D3DDrv.dll',0xf292,0xf690,'SetRes-remaining')
    ins,cache=function('D3DDrv.dll',0x17800,0x18401,'state-cache-complete')
    _,gamma=function('D3DDrv.dll',0xca30,0xcbb0,'UpdateGamma')
    pe=pefile.PE(str(P.A.source()/'System/WinDrv.dll'))
    es=sorted(set(e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols))
    _,resize=function('WinDrv.dll',0x4f20,next(x for x in es if x>0x4f20),'ResizeViewport')
    for dll,start,label in [('WinDrv.dll',0x49b0,'TryRenderDevice'),('WinDrv.dll',0x3390,'OpenWindow'),('Engine.dll',0x84010,'UEngine-Init'),('Engine.dll',0x8f460,'UGameEngine-Init')]:
        p=pefile.PE(str(P.A.source()/'System'/dll));exports=sorted(set(e.address for e in p.DIRECTORY_ENTRY_EXPORT.symbols))
        function(dll,start,next(x for x in exports if x>start),label)
    # All cache COM calls are on the object loaded through renderer+0x4698.
    names={int(n):name for n,name in re.findall(r'unsupported slot (\d+) (\w+)',(P.RT/'d3d8_device_slots.inc').read_text())}
    names.update({37:'SetTransform',50:'SetRenderState',63:'SetTextureStageState',61:'SetTexture',76:'SetVertexShader',83:'SetStreamSource',85:'SetIndices'})
    calls=[]
    for j,i in enumerate(ins):
        if i.mnemonic=='call'and i.operands[0].type==X86_OP_MEM:
            slot=i.operands[0].mem.disp//4;assert slot in names,(hex(i.address),slot)
            calls.append(dict(address=hex(i.address),slot=slot,method=names[slot],
                push_order=[x.op_str for x in ins[max(0,j-15):j]if x.mnemonic=='push'][-(4 if slot in [63,83]else 2 if slot==76 else 3):]))
    states=[(8,3),(14,1),(15,0),(19,2),(20,1),(22,1),(23,4),(24,0),(25,5),(27,0),(28,0),(34,0),(36,0),(37,0),(47,0),(52,'renderer[0x60] || GIsEditor'),(53,1),(54,1),(55,1),(56,8),(57,0),(58,255),(59,255),(60,0),(137,0),(139,0),(141,1),(156,0),(157,0),(158,0),(159,0),(160,0),(145,0),(146,2),(147,0),(148,1),(29,0),(9,2)]
    rs=[c for c in calls if c['slot']==50];assert len(rs)==len(states)==38
    for c,(s,v) in zip(rs,states):
        assert int(c['push_order'][-2],0)==s
        c.update(state=s,value=v,currently_supported=(s,v)in [(29,0),(9,2)])
    transforms=[c for c in calls if c['slot']==37]
    assert len(transforms)==11
    for c,s in zip(transforms,[2,3,*range(16,24),256]):
        ref=c['push_order'][-2];assert ref=='edi'and s==2 or int(ref,0)==s
        c.update(transform=s,matrix='Core!FMatrix::Identity (64 bytes)',supported=False)
    tss=[c for c in calls if c['slot']==63];assert len(tss)==15
    types=[1,2,3,4,5,6,11,13,14,24,25,19,26,27,28]
    vals=[1,2,1,1,0,1,0,'renderer[0x4650]','renderer[0x4650]',0,'renderer[0x4650]','_ftol(renderer float[0x412c])',1,1,1]
    for c,s,v in zip(tss,types,vals):
        ref=c['push_order'][-3];assert ref=='ebp'and s==1 or int(ref,0)==s
        c.update(stage='0 <= stage < renderer[0x41c8]',type=s,value=v,supported=False)
    assert {c['slot']for c in calls}=={50,37,63,61,76,83,85}
    summary=dict(passed=True,post_material_states=[dict(address='0x0696f336',state=148,value=1,supported=False),dict(address='0x0696f350',state=145,value=0,supported=False)],
        sampler_loop=dict(stage_bound='renderer[0x41c8]',order=[
            [19,'raw DWORD renderer[0x412c]'],[16,'2 if max_anisotropy==1 else 3'],[17,'same filter'],
            [18,'0 if !renderer[0x40d4] else 1 + bool(renderer[0x40d0])'],[21,'max(1,min(renderer[0x4124],renderer[0x41a0]))']],
            call_addresses=['0x0696f3ac','0x0696f3d0','0x0696f3e6','0x0696f418','0x0696f42e']),
        viewport_resize=dict(address='0x0696f48d',vtable_offset='0x88',implementation='WinDrv!UWindowsViewport::ResizeViewport',arguments='flags=0x10 | bool(fullscreen), X, Y',success_assertion='nonzero'),
        cache_call='0x0696f4bd -> 0x06977800',cache_return='0x069783fe ret 4',cache_calls=calls,
        cache_counts={name:sum(c['method']==name for c in calls)for name in sorted(set(c['method']for c in calls))},
        resource_bindings=dict(texture='each stage: NULL texture, slot 61',vertex_shader='FVF 2, slot 76',streams='0..min(renderer[0x41f0],16)-1: NULL buffer, stride 0, slot 83',indices='NULL buffer and base vertex 0, slot 85'),
        gamma=dict(call='0x0696f4ce',renderer_vtable_offset='0x88',implementation='D3DDrv!UpdateGamma RVA 0xca30',
            conditional='device exists && renderer[0x4140] & 0x20000',native_call='0x0696cb68',slot=18,method='SetGammaRamp',flags=1,
            input='1536 bytes: 3 x 256 WORD entries computed from gamma/brightness/contrast',supported=False,return_type='void'),
        SetRes_success_return='0x0696f4e9 ret 20 with EAX=1',
        unsupported_methods=['SetRenderState new tuples','SetTextureStageState','SetTransform','SetTexture','SetVertexShader','SetStreamSource','SetIndices','SetGammaRamp'],
        original_and_generated_sources_verified=True,genuine_execution=False)
    P.save('initialization-plan.json',summary)
    print('COMPLETE CACHE',summary['cache_counts'],flush=True)
if __name__=='__main__':main()
