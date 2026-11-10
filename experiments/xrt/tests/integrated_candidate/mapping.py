"""Offline exact Init return endpoint and linked HLE verification."""
import sys,ctypes as C,struct,re
from ctypes import wintypes as T
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import pefile,capstone as CS

def main():
    exe,sha,pdb=identity();l=legacy();api=l.D.api;dll=C.WinDLL('dbghelp',use_last_error=True)
    h=api(l.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(dll,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    assert api(dll,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False)
    methods=['TestCooperativeLevel','BeginScene','EndScene','SetViewport','GetViewport','DrawPrimitiveUP','DrawIndexedPrimitiveUP']
    wanted={'D8Device.'+n:'d8_device_'+n for n in methods}
    prior_integrate=load('retained_resource_integrate',H.parent/'resource_frame/integrate.py')
    NEW_METHODS=load('surface_transfer_integrate',H/'integrate.py').METHODS
    METHODS=prior_integrate.METHODS+list(NEW_METHODS);RESOURCE_METHODS=prior_integrate.RESOURCE_METHODS
    wanted.update({'D8Device.'+n:'d8_device_'+n for n in METHODS+['SetTexture','SetStreamSource','SetIndices']})
    wanted.update({'D8R.'+n:'d8_resource_'+n for n in RESOURCE_METHODS})
    wanted.update({'DID.'+n:'did_'+n for n in ('Acquire','Unacquire','SetCooperativeLevel')})
    gui_wanted={n:'hle_'+n for n in ('SetWindowLongA','SetWindowLongW','SetMenu','PostMessageA','PostMessageW')}
    names=['events','event_seq','xrt_g','xrt_fatal','d8_CreateDevice','f_1038f460','xrt_hle_gui',*gui_wanted.values(),'f_1090e170','xrt_icall','xrt_badret','xrt_hle_misc','d8_api_entry','d8_semantic_frame','did_lifecycle_frame',*wanted.values()]
    names=list(dict.fromkeys(names+['d8_device_Clear','d8_device_Present','d8_device_SetRenderState',
        'd8_device','d8_objects','windows','device_window_pins','d8_attempted','d8_creating',
        'd8_native_failed','d8_rendering','invoke_gui_proc']))
    symbols={}
    try:
        base=api(dll,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0)
        assert base
        for name in names:
            s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            assert api(dll,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,name.encode(),C.byref(s)),name
            symbols[name]=dict(rva=s.Address-base,size=s.Size)
            if name=='d8_device':device_type=s.TypeIndex
        get=api(dll,'SymGetTypeInfo',[T.HANDLE,C.c_ulonglong,T.ULONG,C.c_int,C.c_void_p])
        def query(tid,what,typ=C.c_uint32):
            value=typ();assert get(h,base,tid,what,C.byref(value));return value.value
        if query(device_type,0)==7:device_type=query(device_type,4)
        size=query(device_type,2,C.c_ulonglong);count=query(device_type,13)
        children=(C.c_uint32*(count+2))();children[0]=count;children[1]=0
        assert get(h,base,device_type,7,children)
        fields={};free=api(l.D.K,'LocalFree',[C.c_void_p],C.c_void_p)
        for child in children[2:]:
            pointer=query(child,1,C.c_void_p);name=C.wstring_at(pointer);free(pointer);fields[name]=query(child,10)
        layout=dict(size=size,fields=fields)
        assert layout==dict(size=280,fields=dict(guest=0,refs=4,focus=8,window=12,presents=16,children=20,
            host=24,parent=32,caps=40,caps_valid=252,width=256,height=260,depth=264,depthformat=268,behavior=272)),layout
    finally:assert api(dll,'SymCleanup',[T.HANDLE])(h)
    pe=pefile.PE(str(exe));md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_64);md.detail=True
    def follow(rva):
        seen=set()
        while pe.get_data(rva,1)==b'\xe9':
            assert rva not in seen;seen.add(rva);rva+=5+struct.unpack('<i',pe.get_data(rva+1,4))[0]
        return rva
    rva=follow(symbols['f_1090e170']['rva'])
    extent=next(e.struct for e in pe.DIRECTORY_ENTRY_EXCEPTION if e.struct.BeginAddress==rva)
    ins=list(md.disasm(pe.get_data(rva,extent.EndAddress-rva),base+rva))
    nativeflow=load('bringup_nativeflow',H.parent/'renderer_config_diagnosis/nativeflow.py')
    states=nativeflow.propagate(ins,md);matches=[]
    for i,x in enumerate(ins):
        if x.mnemonic=='call' and x.operands[0].type==CS.x86_const.X86_OP_IMM and follow(x.operands[0].imm-base)==follow(symbols['xrt_icall']['rva']):
            state=states.get(x.address,{})
            if state.get('r8')==0x1090ed59:matches.append(i)
    if len(matches)!=1:
        save(O/'mapping-diagnostic.json',dict(symbol=symbols['f_1090e170'],
            calls=[dict(rva=x.address-base,state=states.get(x.address,{})) for x in ins if x.mnemonic=='call' and x.operands[0].type==CS.x86_const.X86_OP_IMM and follow(x.operands[0].imm-base)==follow(symbols['xrt_icall']['rva'])],
            contexts=[[dict(rva=v.address-base,bytes=v.bytes.hex(),instruction=v.mnemonic+' '+v.op_str) for v in ins[max(0,i-8):i+16]] for i,x in enumerate(ins) if '0x1090ed59' in x.op_str]))
    assert len(matches)==1, matches
    i=matches[0];context=[dict(rva=x.address-base,bytes=x.bytes.hex(),instruction=x.mnemonic+' '+x.op_str) for x in ins[i-6:i+14]]
    save(O/'mapping-context.json',dict(symbol=symbols['f_1090e170'],state=states[ins[i].address],context=context))
    # Validate the concrete compiler sequence as well as the call argument.
    # Whole-function propagation loses the CPU alias at a control-flow join;
    # require the actual adjacent rcx assignment and preceding guest P store.
    assert ins[i-1].mnemonic=='mov' and ins[i-1].op_str=='rcx, rdi'
    pcstores=[x for x in ins[max(0,i-24):i] if x.mnemonic=='mov' and
        x.operands[0].type==CS.x86_const.X86_OP_MEM and
        x.reg_name(x.operands[0].mem.base)=='rdi' and x.operands[0].mem.disp==0x44]
    assert len(pcstores)==1 and pcstores[0].op_str=='dword ptr [rdi + 0x44], 0x1090ed59'
    retload,cmp,jump,stop=ins[i+1:i+5]
    assert retload.mnemonic=='mov' and retload.op_str=='ebx, 0x1090ed5c'
    assert cmp.mnemonic=='cmp' and jump.mnemonic=='jne',(cmp.op_str,jump.mnemonic)
    assert cmp.operands[0].type==CS.x86_const.X86_OP_MEM and cmp.operands[0].mem.disp==0x40
    cpu=cmp.reg_name(cmp.operands[0].mem.base)
    if cmp.operands[1].type==CS.x86_const.X86_OP_IMM:assert cmp.operands[1].imm==GUEST
    else:
        reg=cmp.reg_name(cmp.operands[1].reg)
        wide={'eax':'rax','ebx':'rbx','ecx':'rcx','edx':'rdx','esi':'rsi','edi':'rdi','ebp':'rbp'}.get(reg,reg.removesuffix('d'))
        assert wide=='rbx'
    destination=stop.operands[0].imm if stop.mnemonic=='jmp' else stop.address
    nextins=list(md.disasm(pe.get_data(destination-base,16),destination))[0]
    assert nextins.mnemonic=='mov' and nextins.operands[0].type==CS.x86_const.X86_OP_MEM
    assert nextins.reg_name(nextins.operands[0].mem.base)==cpu and nextins.operands[0].mem.disp==0x44
    failure=list(md.disasm(pe.get_data(jump.operands[0].imm-base,100),jump.operands[0].imm))
    assert any(x.mnemonic=='call' and x.operands[0].type==CS.x86_const.X86_OP_IMM and follow(x.operands[0].imm-base)==follow(symbols['xrt_badret']['rva']) for x in failure)
    bound={};table=symbols['xrt_hle_misc']['rva']
    for off in range(0,32768,32):
        d,n,fn=struct.unpack('<3Q',pe.get_data(table+off,24))
        if not d:break
        name=pe.get_data(n-base,256).split(b'\0')[0].decode('ascii')
        if name in wanted:
            assert follow(fn-base)==follow(symbols[wanted[name]]['rva'])
            bound[name]=dict(table_rva=table+off,implementation_rva=follow(fn-base))
    assert set(bound)==set(wanted)
    gui_bound={};table=symbols['xrt_hle_gui']['rva']
    for off in range(0,32768,32):
        d,n,fn=struct.unpack('<3Q',pe.get_data(table+off,24))
        if not d:break
        name=pe.get_data(n-base,256).split(b'\0')[0].decode('ascii')
        if name in gui_wanted:
            assert follow(fn-base)==follow(symbols[gui_wanted[name]]['rva'])
            gui_bound[name]=dict(table_rva=table+off,implementation_rva=follow(fn-base))
    assert set(gui_bound)==set(gui_wanted)
    bound.update(gui_bound)
    original=A.source()/'System/Unreal2.exe'
    if not original.exists():original=A.source()/'System/Unreal2.dll'
    p=pefile.PE(str(original));p.relocate_image(0x10900000)
    original_bytes=p.get_data(0xed59,8)
    assert original_bytes[:3]==b'\xff\x50\x74' and original_bytes[3]==0xe8
    source=W/'experiments/xrt/gen/unreal2/Unreal2_001.c';text=source.read_text()
    assert 'ICALL(rd32((uint32_t)(c->r[0] + 0x74u)), 0x1090ed5cu, 0x1090ed59u);' in text
    save(O/'stop-mapping.json',dict(passed=True,executable=str(exe),sha256=sha,pdb_sha256=pdb,guest_stop=GUEST,
        stop_rva=stop.address-base,stop_bytes=stop.bytes.hex(),stop_registers=dict(cpu=cpu),context=context,symbols=symbols,
        entry_rva=follow(symbols['f_1038f460']['rva']),entry_bytes=pe.get_data(follow(symbols['f_1038f460']['rva']),8).hex(),
        device_layout=layout,device_layout_verified=True,
        original=dict(path=str(original),sha256=core.sha(original),call_and_next_bytes=original_bytes.hex()),generated=dict(path=str(source),sha256=core.sha(source)),
        meaning='After checked UGameEngine::Init return; before guest 1090ED5C CALL 10901370. No first main-loop tick admitted.',
        candidate_instructions_executed=0,production_supervisor_unchanged=True,separate_owner_authorization_required=True))
    save(O/'linked-adapters.json',dict(passed=True,sha256=sha,bindings=bound,source=core.tree(RT)))
    print('Init-return endpoint',hex(stop.address-base),stop.mnemonic,stop.op_str,'linked adapters',len(bound),flush=True)
if __name__=='__main__':main()
