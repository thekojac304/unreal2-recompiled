"""Retained exact PE/PDB stop mapping; parameterized candidate identity only. No launches."""
import ctypes as C
from ctypes import wintypes as T
import re
import struct
from pathlib import Path
from .core import ROOT as W

def resolve(S, E, V, pdb_sha256):
    import pefile
    import capstone as CS
    from capstone.x86_const import X86_OP_IMM, X86_OP_MEM
    assert E.sha(V.EXE)==V.EXPECTED
    assert E.sha(V.EXE.with_suffix('.pdb'))==pdb_sha256
    source=W/'experiments/xrt/gen/d3ddrv/D3DDrv_000.c'
    text=source.read_text()
    pos=text.index('    P(0x696f292u); /* lea edx, [ebp - 0xbc] */')
    name=re.findall(r'^void (f_[0-9a-f]+)\(CPU\* c\)',text[:pos],re.M)[-1]
    next_name=re.search(r'^void (f_[0-9a-f]+)\(CPU\* c\)',text[pos:],re.M)[1]
    d=C.WinDLL('dbghelp',use_last_error=True)
    api=S.D.api
    h=api(S.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    assert api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(V.EXE.parent),False)
    base=api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(V.EXE),None,0x140000000,0,None,0)
    assert base
    result={}
    try:
        find=api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(S.D.Symbol)])
        for n in [name,next_name,'xrt_icall','d8_CreateDevice','d8_device_SetRenderState','d8_device_SetMaterial','xrt_fatal','events','event_seq']:
            s=S.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023
            assert find(h,n.encode(),C.byref(s)) and s.Address,n
            result[n]=dict(rva=s.Address-base,size=s.Size)
    finally:
        assert api(d,'SymCleanup',[T.HANDLE])(h)
    pe=pefile.PE(str(V.EXE),fast_load=True)
    md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_64);md.detail=True
    r=result[name]; extent=result[next_name]['rva']-r['rva']
    assert 0 < extent < 0x40000
    code=pe.get_data(r['rva'],extent)
    ins=list(md.disasm(code,base+r['rva']))
    rows=[]
    for i,x in enumerate(ins):
        if any(o.type==X86_OP_IMM and o.imm==0x696f292 for o in x.operands):
            rows.append(dict(index=i,rva=x.address-base,mnemonic=x.mnemonic,operands=x.op_str,
                             bytes=x.bytes.hex(),context=[dict(rva=y.address-base,mnemonic=y.mnemonic,operands=y.op_str,bytes=y.bytes.hex()) for y in ins[max(0,i-10):i+8]]))
    assert len(rows)==1
    i=rows[0]['index']
    forward=ins[i:i+32]
    stop=next(x for x in forward if x.mnemonic=='mov' and x.op_str=='dword ptr [rsi + 0x44], edi')
    j=ins.index(stop)
    expected=[('cmp','dword ptr [rsi + 0x40], edi'),('jne',None),
              ('mov','dword ptr [rsi + 0x44], edi'),('lea','rdx, [rbp + 0xd58]'),
              ('mov','eax, dword ptr [rsi + 0x14]'),('mov','r8, r15'),
              ('sub','eax, 0xbc'),('mov','dword ptr [rsi + 8], eax')]
    actual=ins[j-2:j+6]
    assert len(actual)==len(expected)
    assert all(x.mnemonic==a and (b is None or x.op_str==b) for x,(a,b) in zip(actual,expected))
    call=ins[j-3]
    assert call.mnemonic=='call' and ins[j-4].op_str=='rcx, rsi'
    # MSVC's public call thunk must resolve to the identified xrt_icall.
    thunk=pe.get_data(call.operands[0].imm-base,5)
    assert thunk[0]==0xe9
    destination=call.operands[0].imm+5+struct.unpack('<i',thunk[1:])[0]
    assert destination-base==result['xrt_icall']['rva']
    return dict(executable=str(V.EXE),sha256=V.EXPECTED,pdb_sha256=E.sha(V.EXE.with_suffix('.pdb')),
                source_sha256=E.sha(source),function=name,symbols=result,candidates=rows,
                guest_stop=0x696f292,stop_rva=stop.address-base,stop_bytes=stop.bytes.hex(),
                stop_registers=dict(cpu='rsi',return_value='edi'),
                static_mapping_verified=True,live_target_breakpoint_verified=False,
                meaning='Before P(0x0696f292) and before its LEA writes guest EDX; checked xrt_icall return immediately precedes it.',
                client_launched=False)

