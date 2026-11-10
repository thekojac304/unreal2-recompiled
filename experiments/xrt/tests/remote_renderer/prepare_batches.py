"""Build future native batches and run only the non-graphical ABI self-test."""
import struct,sys
sys.dont_write_bytecode=True
import phase as P
def main():
    b=P.O/'prepared-batches';b.mkdir()
    plan=P.read(P.O/'initialization-plan.json')
    states=[(148,1),(145,0)]+[(c['state'],v)for c in plan['cache_calls']if c['method']=='SetRenderState'for v in ([c['value']]if isinstance(c['value'],int)else [0,1])]
    header='static DWORD state_cases[][2]={'+','.join('{%d,%d}'%t for t in states)+'};\nstatic DWORD transform_cases[]={2,3,16,17,18,19,20,21,22,23,256};\n'
    (b/'batch_cases.inc').write_text(header)
    results=[]
    for arch in ['x86','x64']:
        d=b/arch;d.mkdir();s=(P.H.parent/'d3d8_device'/('abi32.asm'if arch=='x86'else'abi64.asm')).read_text().replace('device_abi','batch_abi').replace('cwseed WORD 077fh','cwseed WORD 027fh')
        start=s.index('    push DWORD PTR [eax+28]'if arch=='x86'else'    mov rcx,[r10+8]');end=s.index('    mov edx,[esp+516]'if arch=='x86'else'    mov r10,[rsp+72]',start)
        call='''    cmp DWORD PTR [eax+20],4
    jne args3
    push DWORD PTR [eax+16]
args3:
    cmp DWORD PTR [eax+20],3
    jb args2
    push DWORD PTR [eax+12]
args2:
    push DWORD PTR [eax+8]
    push DWORD PTR [eax+4]
    call DWORD PTR [eax]
'''if arch=='x86'else'''    mov rcx,[r10+8]
    mov rdx,[r10+16]
    mov r8,[r10+24]
    mov r9,[r10+32]
    call QWORD PTR [r10]
'''
        (d/'abi.asm').write_text(s[:start]+call+s[end:])
        P.R.script(b,'build-'+arch,arch,f'{"ml"if arch=="x86"else"ml64"} /nologo /c /Fo"{d}/abi.obj" "{d}/abi.asm" || exit /b 1\ncl /nologo /O2 /W4 /I"{b}" /Fo"{d}/oracle.obj" /Fe"{d}/oracle.exe" "{P.H}/batch_oracle.c" "{d}/abi.obj" user32.lib || exit /b 1')
        r=P.R.execute([d/'oracle.exe','--abi-only'],b,'abi-only-'+arch)
        import json
        rows=[json.loads(s)for s in r.stdout.splitlines()if s.startswith('{')];calls=[x for x in rows if x['kind']=='call'];assert len(calls)==12
        expected=[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0]if arch=='x86'else[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
        assert all(c['regs']==expected and c['fpu_preserved']and not c['stack_delta']and c['last_error']==c['seed']for c in calls)
        if arch=='x64':assert all(bytes.fromhex(c['xmm'])==struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10 for c in calls)
        assert rows[-1]==dict(kind='summary',calls=12,failures=0,graphics=False)
        results.append(dict(arch=arch,calls=12,abi_passed=True,graphics_executed=False))
    P.save('prepared-batch-audit.json',dict(passed=True,results=results,native_graphics_execution_deferred=True,
        groups=['states: 41 site/configuration tuples, transition + exact readback, four seeds',
            'samplers: stage 0..7 scalar settings and readbacks (fixture domain only)',
            'bindings: identity transforms, NULL textures/streams/indices and FVF 2'],
        gamma_not_exercised=True,sources={str(p.relative_to(P.W)):P.core.sha(p)for p in [P.H/'batch_oracle.c',P.H/'prepare_batches.py',b/'batch_cases.inc']},genuine_launches=0))
if __name__=='__main__':main()
