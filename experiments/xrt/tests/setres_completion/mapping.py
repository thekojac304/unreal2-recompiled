"""Resolve the checked caller continuation from the exact PE and PDB."""
import ctypes as C
from ctypes import wintypes as T
import re
import struct
from common import *

METHODS = {18: ('SetGammaRamp',3), 37: ('SetTransform',3), 42: ('SetMaterial',2),
           50: ('SetRenderState',3), 61: ('SetTexture',3), 63: ('SetTextureStageState',4),
           76: ('SetVertexShader',2), 83: ('SetStreamSource',4), 85: ('SetIndices',3)}


def resolve():
    import pefile
    import capstone as CS
    l = legacy(); api = l.D.api
    d = C.WinDLL('dbghelp', use_last_error=True)
    h = api(l.D.K, 'GetCurrentProcess', [], T.HANDLE)()
    api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    core.require(api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(EXE.parent),False),'symbol init')
    symbols = {}
    try:
        base = api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(EXE),None,0x140000000,0,None,0)
        core.require(base, 'exact candidate symbols load')
        names = ['f_696d260','f_696e890','f_11104f20','xrt_icall','xrt_badret','batch_frame','d8_render_ready','events','event_seq','xrt_g','xrt_fatal','invoke_gui_proc','d8_profile_renderer']
        names += ['d8_device_'+v[0] for v in METHODS.values()]
        for name in names:
            s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            core.require(api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,name.encode(),C.byref(s)), 'symbol absent: '+name)
            symbols[name]=dict(rva=s.Address-base,size=s.Size)
    finally:
        core.require(api(d,'SymCleanup',[T.HANDLE])(h), 'symbol cleanup')
    source=W/'experiments/xrt/gen/d3ddrv/D3DDrv_000.c';text=source.read_text()
    core.require('ICALL(rd32((uint32_t)(c->r[2] + 0x78u)), 0x696d2cdu, 0x696d2cau);' in text,'generated primary SetRes call')
    core.require('P(0x696d2cdu); /* cmp eax, edi */' in text and 'XRT_EH_POP(); RET(20u);' in text,'return/next guest instruction')
    pe=pefile.PE(str(EXE));md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_64);md.detail=True
    def follow(rva):
        seen=set()
        while pe.get_data(rva,1)==b'\xe9':
            core.require(rva not in seen,'thunk cycle');seen.add(rva)
            rva += 5+struct.unpack('<i',pe.get_data(rva+1,4))[0]
        return rva
    begin=follow(symbols['f_696d260']['rva'])
    for slot,(name,n) in METHODS.items():
        symbol=symbols['d8_device_'+name]
        body=list(md.disasm(pe.get_data(follow(symbol['rva']),symbol['size']),base+follow(symbol['rva'])))
        core.require(any(v.mnemonic=='call' and v.operands[0].type==CS.x86_const.X86_OP_IMM and follow(v.operands[0].imm-base)==follow(symbols['d8_render_ready']['rva']) for v in body),'common renderer readiness hook was inlined/removed: '+name)
    for name in ('batch_frame','d8_device_SetMaterial'):
        symbol=symbols[name];begin_hook=follow(symbol['rva'])
        body=list(md.disasm(pe.get_data(begin_hook,symbol['size']),base+begin_hook))
        core.require(any(v.mnemonic=='call' and v.operands[0].type==CS.x86_const.X86_OP_IMM and follow(v.operands[0].imm-base)==follow(symbols['d8_render_ready']['rva']) for v in body),'common renderer readiness trap absent: '+name)
    ins=list(md.disasm(pe.get_data(begin,0x20000),base+begin))
    matches=[]
    for i,x in enumerate(ins):
        if x.mnemonic=='mov' and x.op_str=='edi, 0x696d2cd':
            for j in range(i+1,min(i+65,len(ins))):
                if ins[j].mnemonic=='mov' and ins[j].op_str=='dword ptr [rbx + 0x44], edi':
                    matches.append((i,j));break
    core.require(len(matches)==1,'unique caller continuation mapping')
    i,j=matches[0];stop=ins[j]
    core.require(stop.address-base==RVA and stop.bytes.hex()=='897b44','expected exact stop bytes')
    core.require([(v.mnemonic,v.op_str) for v in ins[j-2:j]]==[('cmp','dword ptr [rbx + 0x40], edi'),('jne',hex(ins[j-1].operands[0].imm))], 'checked guest return branch')
    call=ins[j-3]
    core.require(call.mnemonic=='call' and follow(call.operands[0].imm-base)==follow(symbols['xrt_icall']['rva']), 'checked xrt_icall immediately before stop')
    branch=ins[j-1].operands[0].imm
    fail=list(md.disasm(pe.get_data(branch-base,64),branch))
    core.require(any(v.mnemonic=='call' and follow(v.operands[0].imm-base)==follow(symbols['xrt_badret']['rva']) for v in fail if v.operands and v.operands[0].type==CS.x86_const.X86_OP_IMM),'bad-return branch trap')
    original=W/'sandbox_inputs/first-world/content/System/D3DDrv.dll'
    with pefile.PE(str(original)) as guest:
        rows=[]
        for start,size in [(0x696d2b0,0x21),(0x696f4d4,0x18)]:
            data=guest.get_data(start-0x6960000,size)
            x86=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_32)
            rows += [dict(guest=v.address,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for v in x86.disasm(data,start)]
        core.require(any(v['guest']==GUEST and v['instruction']=='cmp eax, edi' for v in rows),'original next guest instruction')
        core.require(any(v['guest']==0x696f4e9 and v['bytes']=='c21400' for v in rows),'original ret20')
    result=dict(executable=str(EXE),sha256=SHA,pdb_sha256=PDB,symbols=symbols,
        guest_stop=GUEST,stop_rva=RVA,stop_bytes='897b44',stop_registers=dict(cpu='rbx',return_value='edi'),
        function='f_696d260',source_sha256=core.sha(source),original=str(original),original_sha256=core.sha(original),original_instructions=rows,
        context=[dict(rva=v.address-base,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for v in ins[j-12:j+12]],
        static_mapping_verified=True,client_launched=False,live_candidate_execution=False,
        meaning='After checked SetRes ret20; before P(0696D2CD) and CMP guest flags/operands take effect')
    pe.close()
    return result


def sequence():
    raw=(PRIOR/'runtime/batch_cases.inc').read_text()
    calls=[]
    for line in raw.splitlines():
        if not line.startswith(' {'): continue
        v=[int(t.removesuffix('u'),0) for t in line.strip(' {},\n').split(',')]
        group,slot,a,b,c,site,config=v
        calls.append(dict(group=group,slot=slot,a=a,b=b,c=c,site=site,config=config))
    core.require(len(calls)==238,'238 configured tuples required')
    # The tuple inventory groups cache calls by callsite. The actual original
    # cache loop executes all sampler/texture sites for stage 0, then stage 1.
    # Keep its observed execution order separate from the admitted tuple set.
    cache=calls[42:-1]
    stage=[q for q in cache if q['slot'] in (63,61)]
    ordered=[];emitted=False
    for q in cache:
        if q['slot'] in (63,61):
            if not emitted:
                ordered += sorted(stage,key=lambda v:(v['a'],v['site']))
                emitted=True
        else:ordered.append(q)
    result=[dict(slot=42,site=0x696f31d)] + calls[:42] + [dict(kind='resize',slot=-1)] + ordered + calls[-1:]
    for q in result:
        if q['slot']>0:
            q['method'],q['n']=METHODS[q['slot']]
    returns={}
    for p in (W/'experiments/xrt/gen/d3ddrv').glob('*.c'):
        for ret,site in re.findall(r'ICALL\([^;]*?, (0x[0-9a-f]+)u, (0x[0-9a-f]+)u\);',p.read_text()):returns[int(site,0)]=int(ret,0)
    for q in result:
        if q['slot']>0:q['return_pc']=returns[q['site']]
    return result
