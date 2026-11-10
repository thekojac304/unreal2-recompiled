"""Re-disassemble manifest-bound original PEs and compare generated markers."""
import sys,re,bisect
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import pefile,capstone as cs

def main():
    out=O/'static';out.mkdir(exist_ok=True);records=[];catalog={}
    wanted={'WinDrv.dll':['TryRenderDevice','OpenWindow','UpdateWindowFrame','Repaint','ResizeViewport'],
      'Engine.dll':['?Init@UEngine','?Init@UGameEngine','?Tick@UGameEngine','?Tick@ULevel','?Draw@UGameEngine','?UpdateDetailSettings@UGameEngine'],
      'D3DDrv.dll':['?Lock@','?Unlock@','?SetTexture@','?DrawPrimitive@','?SetRenderTarget@','?SetVertexStreams@','?SetIndexBuffer@']}
    runtime='\n'.join(p.read_text(errors='replace') for p in RT.glob('*') if p.suffix in ('.c','.h','.inc'))
    md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_32);md.detail=True
    for dll,patterns in wanted.items():
        path=A.source()/'System'/dll;pe=pefile.PE(str(path));base=0x6960000 if dll=='D3DDrv.dll' else pe.OPTIONAL_HEADER.ImageBase
        pe.relocate_image(base)
        exports={}
        for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if e.name:exports.setdefault(e.address,[]).append(e.name.decode(errors='replace'))
        addresses=sorted(exports);catalog[dll]={hex(base+r):n for r,n in exports.items()}
        imports={base+(x.address-pe.OPTIONAL_HEADER.ImageBase):(d.dll.decode(),x.name.decode() if x.name else '#'+str(x.ordinal)) for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports}
        genroot=W/'experiments/xrt/gen'/dll[:-4].lower();texts={p:p.read_text() for p in genroot.glob('*.c')}
        all_markers=set(int(x,16) for text in texts.values() for x in re.findall(r'P\(0x([0-9a-f]+)u\)',text))
        selected=[r for r,names in exports.items() if any(p in name for p in patterns for name in names)]
        if dll=='Engine.dll':selected+= [0x83950]
        for rva in sorted(set(selected)):
            end=addresses[bisect.bisect_right(addresses,rva)]
            ins=list(md.disasm(pe.get_data(rva,end-rva),base+rva));label=dll[:-4]+'-'+hex(rva)
            (out/(label+'.asm.txt')).write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():24} {i.mnemonic} {i.op_str}' for i in ins)+'\n')
            sources={str(p):core.sha(p) for p,text in texts.items() if f'void f_{base+rva:x}(' in text}
            markers=set(int(x,16) for p in sources for x in re.findall(r'P\(0x([0-9a-f]+)u\)',texts[Path(p)]))
            missing=[];excluded=[]
            for i in ins:
                if i.mnemonic in ('nop','int3') or i.address in all_markers:continue
                row=dict(address=hex(i.address),instruction=i.mnemonic+' '+i.op_str)
                if dll=='WinDrv.dll' and 0x11102bb9<=i.address<0x11102be0:
                    row['reason']='unwind terminator alignment and switch target/selector tables referenced by this function'
                    excluded.append(row)
                elif i.address in (0x103b5dc9,0x103b5fdd) and i.mnemonic=='lea':
                    row['reason']='identity LEA alignment after unconditional forward branch'
                    excluded.append(row)
                else:missing.append(row)
            calls=[]
            for j,i in enumerate(ins):
                if i.mnemonic!='call':continue
                operand=i.operands[0];row=dict(address=hex(i.address),instruction=i.op_str,preceding=[x.mnemonic+' '+x.op_str for x in ins[max(0,j-8):j]])
                if operand.type==cs.x86_const.X86_OP_IMM:row.update(target=hex(operand.imm),exports=exports.get(operand.imm-base,[]),kind='direct')
                elif operand.type==cs.x86_const.X86_OP_MEM and not operand.mem.base and operand.mem.disp in imports:
                    imported,symbol=imports[operand.mem.disp];row.update(kind='import',dll=imported,symbol=symbol,adapter_name_present=('"'+symbol+'"') in runtime)
                else:row.update(kind='indirect',vtable_offset=operand.mem.disp if operand.type==cs.x86_const.X86_OP_MEM else None)
                calls.append(row)
            records.append(dict(module=dll,original_sha256=core.sha(path),address=hex(base+rva),end=hex(base+end),exports=exports.get(rva,[]),generated=sources,
                missing_markers=missing,excluded_data_alignment=excluded,original_instructions=len(ins),calls=calls,assembly=str(out/(label+'.asm.txt'))))
    save(out/'export-catalog.json',catalog)
    save(O/'static-audit.json',dict(passed=all(not r['missing_markers'] for r in records),functions=records,genuine_execution=False,
        note='Indirect slot numbers are not automatically assumed to be D3D slots; original register/object provenance must establish the interface. Export-end ranges may contain outlined handlers.'))
    for r in records:print(r['module'],r['address'],r['exports'][:1],len(r['calls']),'calls',len(r['missing_markers']),'missing',flush=True)
if __name__=='__main__':main()
