"""Original resource callsites, with explicit distinction from execution evidence."""
import sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import pefile,capstone as cs
SLOTS={20:'CreateTexture',23:'CreateVertexBuffer',24:'CreateIndexBuffer',29:'UpdateTexture',31:'SetRenderTarget',32:'GetRenderTarget',33:'GetDepthStencilSurface',61:'SetTexture',70:'DrawPrimitive',71:'DrawIndexedPrimitive',75:'CreateVertexShader',76:'SetVertexShader',83:'SetStreamSource',85:'SetIndices',87:'CreatePixelShader',88:'SetPixelShader'}
def main():
    path=A.source()/'System/D3DDrv.dll';pe=pefile.PE(str(path));pe.relocate_image(0x6960000)
    md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_32);md.detail=True;md.skipdata=True;rows=[]
    generated=W/'experiments/xrt/gen/d3ddrv';texts={str(p):p.read_text() for p in generated.glob('*.c')}
    for section in pe.sections:
        if not section.Characteristics&0x20000000:continue
        ins=list(md.disasm(section.get_data(),0x6960000+section.VirtualAddress))
        for j,op in enumerate(ins):
            if op.mnemonic!='call' or op.operands[0].type!=cs.x86_const.X86_OP_MEM:continue
            operand=op.operands[0].mem;slot=operand.disp//4
            if not operand.base or operand.index or operand.disp%4 or slot not in SLOTS:continue
            before=ins[max(0,j-24):j]
            provenance=any(x.mnemonic=='mov' and len(x.operands)==2 and x.operands[1].type==cs.x86_const.X86_OP_MEM and x.operands[1].mem.disp==0x4698 for x in before)
            if not provenance and op.address not in (0x696fbcc,0x696fbfb):continue
            sources=[p for p,s in texts.items() if f'P(0x{op.address:x}u)' in s]
            assert len(sources)==1
            rows.append(dict(site=hex(op.address),possible_device_slot=slot,method=SLOTS[slot],renderer_device_field_in_preceding_window=provenance,
                context=[dict(address=hex(x.address),bytes=x.bytes.hex(),instruction=x.mnemonic+' '+x.op_str) for x in before]+[dict(address=hex(op.address),bytes=op.bytes.hex(),instruction=op.mnemonic+' '+op.op_str)],generated=sources[0]))
    for site,slot in [('0x696fbcc',32),('0x696fbfb',33)]:
        assert len([r for r in rows if r['site']==site and r['possible_device_slot']==slot])==1
    save(O/'resource-path-audit.json',dict(passed=True,original=str(path),original_sha256=core.sha(path),generated={p:core.sha(p) for p in texts},calls=rows,
        limitation='Static callsite inventory, not dynamic reachability. +4698 in a preceding instruction window is evidence to inspect, not a complete dataflow proof for every row. First Lock helper 0696FB70 explicitly loads the device field before slots 32/33.',
        game_executed=False,first_frame_verified=False))
    print('Static resource-related callsite contexts',len(rows),flush=True)
if __name__=='__main__':main()
