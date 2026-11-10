"""Read original PEs, independently bound Init/InitAudio bodies and vtables."""
import sys,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import pefile,capstone

def main():
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    p=A.source()/'System/Engine.dll';pe=pefile.PE(str(p));base=pe.OPTIONAL_HEADER.ImageBase
    exports={e.name.decode():base+e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    reverse={v:k for k,v in exports.items()}
    def span(start,end):
        return [dict(address=hex(i.address),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str)
                for i in md.disasm(pe.get_data(start-base,end-start),start)]
    vtables=[]
    for name,addr in exports.items():
        if name=='??_7UGameEngine@@6BUObject@@@':
            entries=[]
            for slot in (0x74,):
                target=struct.unpack('<I',pe.get_data(addr-base+slot,4))[0]
                entries.append(dict(offset=hex(slot),target=hex(target),symbol=reverse.get(target)))
            vtables.append(dict(name=name,address=hex(addr),entries=entries))
    imports={i.address:i.name.decode() if i.name else str(i.ordinal) for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports}
    assert pe.get_data(0x1038fba9-base,1)==b'\xc3'
    assert pe.get_data(0x10383a31-base,1)==b'\xc3'
    assert imports[0x105046cc].startswith('?ParseParam')
    raw=pe.get_data(0x1051f7b8-base,64)
    word=raw.decode('utf-16le').split('\0')[0]
    assert word.lower()=='nosound',repr(word)
    audio=span(0x10383950,0x10383a32)
    tail=span(0x1038faf0,0x1038fbaa)
    save(O/'control-flow.json',dict(passed=True,original=str(p),sha256=core.sha(p),
        init_tail=tail,init_audio=audio,vtables=vtables,
        nosound=dict(parameter=word,import_symbol=imports[0x105046cc],call='0x103839a1',branch='0x103839ac',skip='0x10383a21'),
        findings=[
          'UGameEngine::Init original normal return is RET at 1038FBA9, not the next exported function boundary.',
          'InitAudio body ends at 10383A31; the previous export-range audit included neighboring functions.',
          'InitAudio is called at 1038FB33. Its own ParseParam(nosound) branch skips audio construction. This does not skip prior DirectMusic map initialization.',
          'Viewport OpenWindow at 1038FB16 precedes virtual +FC on the object at engine+11C at 1038FB2B, InitAudio, optional audio +78 and final destructors. The +FC interface is not inferred from the slot alone.',
          'No new definite runtime blocker is established by these original bodies; indirect paths and conditional callbacks are not a completeness proof.'
        ],runtime_changes=[],genuine_execution=False))
    print('Original Init/InitAudio body boundaries, nosound branch and exported vtables audited',flush=True)
    print(vtables,flush=True)

if __name__=='__main__':main()
