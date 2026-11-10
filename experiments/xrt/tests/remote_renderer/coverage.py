"""Compare every non-padding original instruction address with generated P markers."""
import re,sys
sys.dont_write_bytecode=True
import phase as P
def main():
    results=[]
    for label in ['SetRes-remaining','state-cache-complete','UpdateGamma','ResizeViewport','TryRenderDevice','OpenWindow','UEngine-Init','UGameEngine-Init']:
        data=P.read(P.O/(label+'.json'));text='\n'.join((P.W/p).read_text()for p in data['generated'])
        markers=set(int(x,16)for x in re.findall(r'P\(0x([0-9a-f]+)u\)',text))
        count=0;excluded=[];lines=(P.O/(label+'.asm.txt')).read_text().splitlines()
        for i,line in enumerate(lines):
            addr=int(line[:8],16);asm=line[30:].strip()
            if asm.split()[0]in ['nop','int3']:continue
            if addr==0x6978309:
                assert asm=='lea esp, [esp]'and 'jmp 0x6978310'in lines[i-1]
                excluded.append(dict(address=hex(addr),reason='unreachable identity LEA used as alignment after unconditional forward jump'))
                continue
            count+=1;assert addr in markers,(label,hex(addr),asm)
        results.append(dict(function=label,verified_instruction_markers=count,excluded_alignment=excluded,passed=True))
    P.save('static-coverage.json',dict(passed=True,functions=results,total_verified=sum(r['verified_instruction_markers']for r in results),
        scope='all non-padding original instruction addresses, normal and failure paths; generated source files hash-pinned',genuine_launches=0))
if __name__=='__main__':main()
