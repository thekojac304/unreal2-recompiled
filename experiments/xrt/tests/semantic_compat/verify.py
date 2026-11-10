"""Independent PE/PDB, object lineage and endpoint verification. Never launches EXE."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def generated_module(name,source,changes):
    for before,after in changes:
        assert before in source,('verification source correspondence',before[:100]);source=source.replace(before,after)
    path=O/(name+'.py');path.write_text(source)
    return load('semantic_'+name,path)

def main():
    exe,sha,pdb=identity()
    # Retain the complete independent lineage verifier (including transitive
    # headers/toolchain/dependencies/consumption), with this package's globals.
    m=generated_module('identity_verifier',(H.parent/'renderer_config_diagnosis/identity.py').read_text(),[
        ('from common import *','from common import *\nEXE,SHA,PDB=identity()'),
        ('reused == 278 and len(objects)-reused == 1','reused == 277 and len(objects)-reused == 2'),
        ("len(b['commands']) == 2","len(b['commands']) == 3"),
        ('reused_runtime_objects=13, compiled_runtime_objects=1','reused_runtime_objects=12, compiled_runtime_objects=2')])
    result=m.verify();save(O/'candidate-identity.json',result)
    # Retain the verified original-x86/candidate-x64 control-flow proof and
    # change only the new renderer symbol/guard checks in the isolated verifier.
    source=(H.parent/'renderer_config_diagnosis/mapping.py').read_text()
    old=source[source.index('    # Prove every admitted renderer wrapper'):source.index('    original=[]')]
    new='''    # Inspect actual linked machine code, not source assertions.
    checks=[]
    for name in ['d8_device_'+v[0] for v in METHODS.values()]+['d8_device_Clear']:
        symbol=symbols[name];rva=follow(symbol['rva']);body=list(md.disasm(pe.get_data(rva,symbol['size']),base+rva))
        calls=[follow(v.operands[0].imm-base) for v in body if v.mnemonic=='call' and v.operands[0].type==CS.x86_const.X86_OP_IMM]
        core.require(follow(symbols['d8_semantic_frame']['rva']) in calls,'semantic readiness missing: '+name)
        core.require(any(v.mnemonic=='call' and v.operands[0].type!=CS.x86_const.X86_OP_IMM for v in body),'native COM dispatch missing: '+name)
        checks.append(dict(symbol=name,rva=rva,bytes=pe.get_data(rva,symbol['size']).hex(),live_identity_caps_guard=True,native_indirect_dispatch=True))
    for name in ['d8_CreateDevice','d8_device_Present','d8_CheckDeviceType','d8_CheckDeviceMultiSampleType']:
        symbol=symbols[name];rva=follow(symbol['rva']);body=list(md.disasm(pe.get_data(rva,symbol['size']),base+rva))
        calls=[follow(v.operands[0].imm-base) for v in body if v.mnemonic=='call' and v.operands[0].type==CS.x86_const.X86_OP_IMM]
        core.require(follow(symbols['d8_api_entry']['rva']) in calls,'entry evidence missing: '+name)
        core.require(any(v.mnemonic=='call' and v.operands[0].type!=CS.x86_const.X86_OP_IMM for v in body),'native COM dispatch missing: '+name)
        checks.append(dict(symbol=name,rva=rva,bytes=pe.get_data(rva,symbol['size']).hex(),entry_evidence=True,native_indirect_dispatch=True))
    # Verify actual dispatch-table pointers bind those exact new implementations.
    bound={}
    wanted={'D8Device.'+v[0]:'d8_device_'+v[0] for v in METHODS.values()}
    wanted.update({'D8.CheckDeviceType':'d8_CheckDeviceType','D8.CheckDeviceMultiSampleType':'d8_CheckDeviceMultiSampleType',
        'D8.CreateDevice':'d8_CreateDevice','D8Device.Clear':'d8_device_Clear','D8Device.Present':'d8_device_Present'})
    def string(va):return pe.get_data(va-base,512).split(b'\\0',1)[0].decode('ascii')
    start=symbols['xrt_hle_misc']['rva']
    for offset in range(0,32768,32):
        dll,name,fn=struct.unpack('<3Q',pe.get_data(start+offset,24))
        if not dll:break
        text=string(name)
        if text in wanted:
            symbol=wanted[text]
            core.require(follow(fn-base)==follow(symbols[symbol]['rva']),'linked HLE points at another implementation: '+text)
            bound[text]=dict(table_rva=start+offset,implementation_rva=follow(fn-base))
    core.require(len(bound)==len(wanted),'incomplete actual linked HLE binding census')
    core.atomic(O/'linked-adapter-audit.json',dict(passed=True,sha256=SHA,wrappers=checks,hle_bindings=bound,execution=False))
'''
    extra="'d8_semantic_frame','d8_semantic_checkpoint','d8_api_entry','d8_render_domain','d8_stage_domain','d8_device','d8_objects','d8_attempted','d8_creating','d8_native_failed','d8_rendering','windows','device_window_pins','d8_CreateDevice','d8_device_Clear','d8_device_Present','xrt_hle_misc','d8_CheckDeviceType','d8_CheckDeviceMultiSampleType'"
    mapping=generated_module('mapping_verifier',source,[
        ('from common import *','from common import *\nEXE,SHA,PDB=identity()'),
        ("'batch_frame','d8_render_ready'",extra+",'d8_render_ready'"),
        (",'d8_profile_renderer'",''),(old,new)])
    # nativeflow is pure disassembly analysis, copied with its exact identity.
    import shutil
    shutil.copy2(H.parent/'renderer_config_diagnosis/nativeflow.py',O/'nativeflow.py')
    sys.path.insert(0,str(O));plan=mapping.resolve()
    import ctypes as C
    from ctypes import wintypes as T
    l=legacy();api=l.D.api;dll=C.WinDLL('dbghelp',use_last_error=True);h=api(l.D.K,'GetCurrentProcess',[],T.HANDLE)()
    core.require(api(dll,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False),'layout symbols init')
    try:
        base=api(dll,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0)
        s=l.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
        core.require(api(dll,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(l.D.Symbol)])(h,b'd8_device',C.byref(s)),'device symbol')
        get=api(dll,'SymGetTypeInfo',[T.HANDLE,C.c_ulonglong,T.ULONG,C.c_int,C.c_void_p])
        def query(tid,what,typ=C.c_uint32):
            v=typ();core.require(get(h,base,tid,what,C.byref(v)),'PDB type query');return v.value
        tid=s.TypeIndex
        if query(tid,0)==7:tid=query(tid,4)
        size=query(tid,2,C.c_ulonglong);count=query(tid,13);children=(C.c_uint32*(count+2))();children[0]=count
        core.require(get(h,base,tid,7,children),'PDB members');fields={}
        for member in children[2:]:
            p=query(member,1,C.c_void_p);name=C.wstring_at(p);api(l.D.K,'LocalFree',[C.c_void_p],C.c_void_p)(p);fields[name]=query(member,10)
        expected=dict(guest=0,refs=4,focus=8,window=12,presents=16,host=24,parent=32,caps=40,caps_valid=252,width=256,height=260,depth=264,depthformat=268,behavior=272)
        core.require(size==280 and fields==expected,'actual linked device layout differs')
        plan.update(device_layout_verified=True,device_layout=dict(size=size,fields=fields))
    finally:api(dll,'SymCleanup',[T.HANDLE])(h)
    save(O/'stop-mapping.json',plan)
    print('Independent lineage, actual linked semantic adapters, PDB layout and 11104BF8 endpoint PASS.',flush=True)

if __name__=='__main__':main()
