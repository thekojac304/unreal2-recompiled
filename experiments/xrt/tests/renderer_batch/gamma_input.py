"""CPU-only original x86 gamma arithmetic / generated C byte differential.

No device, window, game module initialization, or replacement pow implementation.
The x86 oracle calls the hash-pinned original MSVCR70 _CIpow/floor exports.
"""
import json, struct, sys
from pathlib import Path
sys.dont_write_bytecode=True
import prepare as P
import capstone,pefile

def main():
    out=P.O/'gamma-input';out.mkdir()
    root=P.A.source()/'System'
    pe=pefile.PE(str(root/'D3DDrv.dll'));core=pefile.PE(str(root/'Core.dll'))
    code=bytearray(4096); md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);md.detail=True
    # Addresses below become offsets in a single RX arena after a documented relocation.
    data={};cursor=800
    constants=P.read(P.O/'extended-contracts.json')['gamma']['constants']
    for address,value in constants.items():
        data[int(address,16)]=cursor;v=bytes.fromhex(value);code[cursor:cursor+len(v)]=v;cursor+=8
    data[0x1016a560]=cursor;code[cursor:cursor+8]=core.get_data(0x6a560,8);cursor+=8
    data[0x1016a12c]=900 # floor pointer
    data[0x1001e074]=904 # original appRound copy
    data[0x1001e078]=908 # original appPow copy
    patches=[];blocks=[]
    for image,start,end,dest,label in [(core,0x17020,0x1702d,0,'appPow'),
            (core,0x17210,0x1722e,64,'appRound'),(core,0x5d510,0x5d585,128,'ftol'),
            (pe,0xcaa8,0xcb56,1024,'gamma-loop')]:
        raw=image.get_data(start,end-start);code[dest:dest+len(raw)]=raw
        base=image.OPTIONAL_HEADER.ImageBase
        ins=list(md.disasm(raw,base+start))
        blocks.append(dict(name=label,rva=hex(start),bytes=raw.hex(),arena_offset=dest))
        for insn in ins:
            off=dest+insn.address-base-start
            if insn.disp_size==4 and insn.disp in data:
                patches.append((off+insn.disp_offset,data[insn.disp],0))
            if insn.mnemonic in ['jmp','call'] and insn.imm_size==4:
                target=insn.operands[0].imm
                if target==0x1015d636:new=512
                elif target==0x1015d510:new=128
                else:continue # Relative branches within the unchanged loop/ftol block.
                struct.pack_into('<i',code,off+insn.imm_offset,new-(off+insn.size))
    code[1024+0xcb56-0xcaa8]=0xc3 # loop exit, before any device access
    code[512:518]=b'\xff\x25'+struct.pack('<I',912);patches.append((514,912,0))
    patches += [(904,64,0),(908,0,0)]
    header='static unsigned char native_bytes[]={'+','.join(str(x) for x in code)+'};\n'
    header+='static const unsigned relocations[][2]={'+','.join('{%d,%d}'%(a,b) for a,b,_ in patches)+'};\n'
    # Exact generated loop; only constant/import addresses are rebased into the small fixture arena.
    source=P.W/'experiments/xrt/gen/d3ddrv/D3DDrv_000.c';text=source.read_text()
    start=text.index('    P(0x696caa8u);');end=text.index('L_696cb56:;',start)
    generated=text[start:end]+'L_696cb56:;\nreturn;\n'
    generated=rebase(generated)
    header+='static void generated_gamma(CPU*c){\n'+generated+'}\n'
    header+='static const struct {unsigned address;unsigned char bytes[8];unsigned size;} constants[]={'+','.join('{%d,{%s},%d}'%(int(a,16)-0x10000000,','.join(str(x) for x in bytes.fromhex(v)),len(bytes.fromhex(v))) for a,v in constants.items())+'};\n'
    (out/'gamma_generated.inc').write_text(header)
    P.core.atomic(out/'extraction.json',dict(original_x86_blocks=blocks,relocations=patches,
        source_sha256=P.core.sha(source),generated_loop_sha256=P.core.sha(out/'gamma_generated.inc'),
        original_d3ddrv_sha256=P.core.sha(root/'D3DDrv.dll'),original_core_sha256=P.core.sha(root/'Core.dll'),
        original_math_runtime_sha256=P.core.sha(root/'MSVCR70.dll'),native_game_modules_loaded=False,
        scope='original arithmetic and generated input bytes only; no native graphics or strict x87 qualification'))
    runs=[]
    for arch in ['x86','x64']:
        d=out/arch;d.mkdir()
        asm=f'ml /nologo /c /Fo"{d}/gamma.obj" "{P.H}/gamma32.asm" || exit /b 1\n' if arch=='x86' else ''
        obj=f' "{d}/gamma.obj"' if arch=='x86' else ''
        P.R.script(d,'build',arch,asm+f'cl /nologo /O1 /fp:strict /W4 /wd4100 /wd4505 /D_CRT_SECURE_NO_WARNINGS /I"{out}" /I"{P.PRIOR}/runtime" /Fo"{d}/input.obj" /Fe"{d}/input.exe" "{P.H}/gamma_input.c"'+obj+' || exit /b 1')
        r=P.R.execute([d/'input.exe',root/'MSVCR70.dll'],d,'run')
        rows=[json.loads(s) for s in r.stdout.splitlines() if s.startswith('{')];assert len(rows)==5
        runs.append(rows)
    for native,translated in zip(*runs):
        assert native['case']==translated['case'] and native['ramp']==translated['ramp'],('unexplained gamma byte differential',native,translated)
    P.save('gamma-input-audit.json',dict(passed=True,cases=5,words_compared=5*768,
        native_x86='relocated original PE arithmetic, original Core appPow/appRound/ftol bytes and pinned MSVCR70 math',
        generated_x64='exact extracted generated arithmetic, existing host math calling model',
        gamma_sample_domain='(gamma,brightness,contrast): (1,.5,.5),(2.2,.5,.5),(.5,.5,.5),(1,0,1),(1,1,1)',
        strict_x87='FAILED unchanged; byte agreement does not establish status/control equality',
        graphics=False,conditional_device_call_not_executed=True))
    print('Original x86 / generated x64 gamma input bytes match for five CPU-only cases',flush=True)

def rebase(s):
    import re
    return re.sub(r'0x697([0-9a-f]{4})u',lambda m:hex(0x10000+int(m[1],16))+'u',s)
if __name__=='__main__':main()
