"""Derive the initial-return stop from original x86 PE and fresh x64 PE/PDB."""
import ctypes as C
from ctypes import wintypes as T
import struct
import pathlib
import sys
import re
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *

METHODS={18:('SetGammaRamp',3),37:('SetTransform',3),42:('SetMaterial',2),50:('SetRenderState',3),61:('SetTexture',3),63:('SetTextureStageState',4),76:('SetVertexShader',2),83:('SetStreamSource',4),85:('SetIndices',3)}


def sequence():
    # Frozen exact 238 tuples/order, copied from the consumed preparation.
    raw=(H/'profile_sequence.py').read_text()
    namespace={};exec(compile(raw,str(H/'profile_sequence.py'),'exec'),globals(),namespace)
    return namespace['sequence']()


def resolve():
    import pefile
    import capstone as CS
    l=legacy();api=l.D.api;d=C.WinDLL('dbghelp',use_last_error=True)
    h=api(l.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    core.require(api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(EXE.parent),False),'symbols init')
    symbols={}
    try:
        base=api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(EXE),None,0x140000000,0,None,0)
        core.require(base,'fresh candidate symbols')
        names=['f_111049b0','f_696d260','f_696e890','f_11104f20','xrt_icall','xrt_badret','batch_frame','d8_render_ready','events','event_seq','xrt_g','xrt_fatal','invoke_gui_proc','d8_profile_renderer']
        names+=['d8_device_'+v[0] for v in METHODS.values()]
        for name in names:
            s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            core.require(api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,name.encode(),C.byref(s)),'symbol absent: '+name)
            symbols[name]=dict(rva=s.Address-base,size=s.Size)
    finally:core.require(api(d,'SymCleanup',[T.HANDLE])(h),'symbols cleanup')
    pe=pefile.PE(str(EXE));md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_64);md.detail=True
    def follow(rva):
        seen=set()
        while pe.get_data(rva,1)==b'\xe9':
            core.require(rva not in seen,'thunk cycle');seen.add(rva)
            rva+=5+struct.unpack('<i',pe.get_data(rva+1,4))[0]
        return rva
    begin=follow(symbols['f_111049b0']['rva'])
    extent=next(e.struct for e in pe.DIRECTORY_ENTRY_EXCEPTION if e.struct.BeginAddress==begin)
    ins=list(md.disasm(pe.get_data(begin,extent.EndAddress-begin),base+begin))
    from nativeflow import propagate
    states=propagate(ins,md)
    candidates=[]
    for i,x in enumerate(ins):
        if x.mnemonic=='call' and x.operands[0].type==CS.x86_const.X86_OP_IMM and follow(x.operands[0].imm-base)==follow(symbols['xrt_icall']['rva']):
            state=states.get(x.address,{})
            if state.get('r8')==0x11104bf5 and state.get('guest_pc')==0x11104bf5:
                cmp=ins[i+1];reg=cmp.op_str.split(', ')[-1]
                full={'eax':'rax','ebx':'rbx','esi':'rsi','edi':'rdi'}.get(reg,reg.removesuffix('d'))
                core.require(state.get(full)==GUEST,'initial return comparison constant')
                # Stop at the unique successful native edge BEFORE its PC store.
                candidates.append((i,i+3,reg))
    if len(candidates)!=1:
        save(O/'mapping-diagnostic.json',dict(matches=candidates,begin=begin,symbol=symbols['f_111049b0'],symbols=symbols,count=len(ins),prefix=pe.get_data(begin,64).hex(),
            last=[dict(rva=v.address-base,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for v in ins[-10:]],
            calls=[dict(rva=x.address-base,state=states.get(x.address,{})) for x in ins if x.mnemonic=='call'],
            near=[dict(rva=v.address-base,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for i,x in enumerate(ins) if '0x11104bf8' in x.op_str for v in ins[max(0,i-6):i+35]]))
    core.require(len(candidates)==1,'unique initial-return mapping; inspect mapping-diagnostic.json')
    i,j,reg=candidates[0];stop=ins[j]
    cpu_reg=ins[j-2].op_str.split('[')[1].split(' +')[0]
    core.require(ins[j-2].mnemonic=='cmp' and ins[j-2].op_str==f'dword ptr [{cpu_reg} + 0x40], {reg}' and ins[j-1].mnemonic=='jne','checked guest return immediately before initial stop')
    call=ins[j-3]
    core.require(call.mnemonic=='call' and follow(call.operands[0].imm-base)==follow(symbols['xrt_icall']['rva']),'xrt_icall before initial checked continuation')
    core.require(stop.mnemonic in ('mov','jmp'),'success edge before next guest instruction')
    destination=stop.operands[0].imm if stop.mnemonic=='jmp' else stop.address
    nextins=list(md.disasm(pe.get_data(destination-base,8),destination))[0]
    core.require(nextins.mnemonic=='mov' and nextins.op_str==f'dword ptr [{cpu_reg} + 0x44], {reg}','success edge leads directly to next guest PC assignment')
    branch=ins[j-1].operands[0].imm
    fail=list(md.disasm(pe.get_data(branch-base,80),branch))
    core.require(any(v.mnemonic=='call' and v.operands[0].type==CS.x86_const.X86_OP_IMM and follow(v.operands[0].imm-base)==follow(symbols['xrt_badret']['rva']) for v in fail if v.operands),'badret trap retained')
    # Prove every admitted renderer wrapper still calls the common unsupported guard.
    for name in ['batch_frame',*['d8_device_'+v[0] for v in METHODS.values()]]:
        symbol=symbols[name];rva=follow(symbol['rva']);body=list(md.disasm(pe.get_data(rva,symbol['size']),base+rva))
        core.require(any(v.mnemonic=='call' and v.operands[0].type==CS.x86_const.X86_OP_IMM and follow(v.operands[0].imm-base)==follow(symbols['d8_render_ready']['rva']) for v in body),'renderer readiness guard absent: '+name)
    original=[]
    for name,base32,ranges in [('WinDrv.dll',0x11100000,[(0x4bca,0x30)]),('D3DDrv.dll',0x6960000,[(0xd29a,0x35),(0xf4d4,0x18)])]:
        path=W/'sandbox_inputs/first-world/content/System'/name;p=pefile.PE(str(path));x86=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_32)
        rows=[dict(address=v.address,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for rva,size in ranges for v in x86.disasm(p.get_data(rva,size),base32+rva)]
        original.append(dict(path=str(path),sha256=core.sha(path),instructions=rows));p.close()
    allrows=[v for q in original for v in q['instructions']]
    core.require(any(v['address']==GUEST and v['bytes']=='85c0' for v in allrows),'original initial TEST EAX,EAX')
    core.require(any(v['address']==0x696d2cd and v['bytes']=='3bc7' for v in allrows),'original Lock CMP EAX,EDI')
    core.require(any(v['address']==0x696f4e9 and v['bytes']=='c21400' for v in allrows),'original SetRes RET20')
    # Verify the unchanged lift's real initial call and the next guest instruction.
    source=W/'experiments/xrt/gen/windrv/WinDrv_000.c';text=source.read_text()
    core.require('ICALL(rd32((uint32_t)(c->r[7] + 0x78u)), 0x11104bf8u, 0x11104bf5u);' in text and 'P(0x11104bf8u); /* test eax, eax */' in text,'initial lift callsite/continuation')
    register64={'eax':'rax','ebx':'rbx','ecx':'rcx','edx':'rdx','esi':'rsi','edi':'rdi','ebp':'rbp','esp':'rsp'}
    result=dict(passed=True,executable=str(EXE),sha256=SHA,pdb_sha256=PDB,symbols=symbols,guest_stop=GUEST,stop_rva=stop.address-base,
         stop_bytes=stop.bytes.hex(),stop_registers=dict(cpu=cpu_reg,return_value=register64.get(reg,reg.replace('d',''))),
         function='f_111049b0',source_sha256=core.sha(source),original=original,
         context=[dict(rva=v.address-base,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for v in ins[j-12:j+12]],
         meaning='After checked initial SetRes return; before P(11104BF8) and original TEST EAX,EAX',
         constant_propagation=states[call.address],next_pc_store=dict(rva=destination-base,bytes=nextins.bytes.hex(),instruction=nextins.mnemonic+' '+nextins.op_str),
         no_candidate_execution=True,production_stop_unchanged=True,separate_owner_stop_authorization_required=True)
    pe.close();return result


if __name__=='__main__':
    import re
    save(O/'stop-mapping.json',resolve())
    print('Exact fresh PE/PDB initial-return stop mapped without candidate execution.',flush=True)
