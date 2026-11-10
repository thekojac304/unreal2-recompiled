"""Read-only original WinDrv import closure and current binding coverage."""
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import pefile
import capstone as CS

def main():
    registered={}
    for p in RT.glob('*'):
        if p.suffix not in ('.c','.inc'):continue
        for m in re.finditer(r'\{\s*"([^"]+\.dll)"\s*,\s*"([^"]+)"\s*,\s*(\w+)',p.read_text()):
            registered[(m[1].lower(),m[2])]=dict(source=str(p),line=p.read_text().count('\n',0,m.start())+1,adapter=m[3])
    output=[]
    for module,base,regions in [('WinDrv.dll',0x11100000,[(0x3390,0x49b0,'OpenWindow'),(0x49b0,0x4f20,'TryRenderDevice'),(0x4f20,0x5760,'ResizeViewport')]),
                               ('Window.dll',0x11000000,[(0x18c0,0x1900,'MoveWindow wrapper')])]:
        path=A.source()/'System'/module;pe=pefile.PE(str(path));iat={x.address:(d.dll.decode().lower(),x.name.decode() if x.name else '#'+str(x.ordinal)) for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports}
        md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_32);md.detail=True;md.skipdata=True
        for start,end,fn in regions:
            calls=[]
            for ins in md.disasm(pe.get_data(start,end-start),base+start):
                if ins.mnemonic not in ('call','jmp') or not ins.operands:continue
                op=ins.operands[0]
                if op.type!=CS.x86_const.X86_OP_MEM:continue
                imported=iat.get(op.mem.disp)
                if imported:
                    binding=registered.get(imported)
                    calls.append(dict(site=hex(ins.address),bytes=ins.bytes.hex(),module=imported[0],name=imported[1],binding=binding,
                        status='implemented_typed_boundary' if binding else 'not_bound_or_translated_module_dependency'))
            output.append(dict(module=module,source=str(path),sha256=core.sha(path),function=fn,range=[hex(base+start),hex(base+end)],imports=calls))
    save(O/'windows-import-audit.json',dict(passed=True,rows=output,
        limitations='Static direct IAT call closure covers all branches in these original function ranges. A listed unsupported import is not proof that the expected windowed path executes it. Relative calls/virtual methods retain their own translated dispatch guards.',
        genuine_launches=0))
    print('Original Windows import audit:',sum(len(r['imports']) for r in output),'direct import call sites',flush=True)
if __name__=='__main__':main()
