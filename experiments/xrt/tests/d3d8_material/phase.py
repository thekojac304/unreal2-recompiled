"""Offline preservation, exact disassembly and disposable material qualification.

Never submits a genuine request or executes a game. Production files stay pinned.
"""
import argparse, importlib.util, json, os, re, shutil, struct, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent; W=H.parents[3]
O=W/'out/recovery/d3d8-material-20261029-01'
RT=O/'runtime'
sys.path.insert(0,str(W/'tools/xrt'))
from supervisor import core, service
from supervisor.environment import load
import asset_boundary as A
R=load('material_fixture_runner',H.parent/'d3d8_render/run.py')

def save(name,value):core.atomic(O/name,value)
def read(path):return json.loads(Path(path).read_text())

def preserve():
    O.mkdir()
    q=core.read_large(core.HOME/'qualification.json');service.verify_seal(q)
    evidence=core.HOME/'evidence/e62b0e3f611c42bea7948306e7e083af'
    items=[evidence, W/'out/recovery/windowae9-20261029-01',
           W/'out/recovery/queryclass-ae9-20261029-01',
           W/'out/recovery/viewport-getobject-20261028-01/strict-failures-retained.json']
    dest=O/'preserved';dest.mkdir()
    inventory={}
    for p in items:
        target=dest/p.name
        if p.is_dir():shutil.copytree(p,target)
        else:shutil.copy2(p,target)
        inventory[str(p)]=core.tree(p) if p.is_dir() else core.sha(p)
        assert (core.tree(target) if p.is_dir() else core.sha(target))==inventory[str(p)]
    consumed=[]
    ledger=core.Ledger(core.HOME/'ledger.jsonl')
    for rid in ['08948b51-fb97-44f3-a9ba-9d0f4687eec3','e0918440-44d2-415c-8aa6-769e7960d30e']:
        response=read(core.HOME/'responses'/f'{rid}.json')
        ev=Path(response['evidence']);m=read(ev/'candidate.json')
        assert any(r['kind']=='launch-claimed' and r['sha256']==m['sha256'] for r in ledger.rows)
        exe=W/m['executable']; assert core.sha(exe)==m['sha256']
        d=dest/rid;d.mkdir();shutil.copy2(core.HOME/'responses'/f'{rid}.json',d/'response.json')
        for p in [exe,exe.with_suffix('.pdb'),W/m['build_record']]:shutil.copy2(p,d/p.name)
        consumed.append(m)
    for name in ['ledger.jsonl','qualification.json','status.json']:
        shutil.copy2(core.HOME/name,dest/name)
    shutil.copytree(W/'experiments/xrt/runtime',RT)
    b=read(W/'out/recovery/queryclass-ae9-20261029-01/build.json')
    assert core.tree(Path(b['root']))==b['outputs']
    save('preservation.json',dict(passed=True,trees=inventory,consumed=consumed,
        ledger_sha256=core.sha(core.HOME/'ledger.jsonl'),ledger_rows=len(ledger.rows),
        ledger_prefix=(core.HOME/'ledger.jsonl').read_text(),qualification=q,
        production_runtime=core.tree(W/'experiments/xrt/runtime'),
        production_enforcement=core.tree(W/'tools/xrt/supervisor'),
        protected=A.verify(),strict_failures=read(items[-1]),genuine_launches=0))
    print('PRESERVED complete second evidence and both consumed identities',flush=True)

def audit_prior():
    p=read(O/'preservation.json');d=O/'preserved/e62b0e3f611c42bea7948306e7e083af'
    ev=read(d/'runtime-events.json')['events'];debug=[json.loads(s)for s in (d/'debug-observations.jsonl').read_text().splitlines()]
    assert (d/'runtime-events.raw.bin').read_bytes()==(d/'runtime-stream.raw.bin').read_bytes()
    assert [e['seq']for e in ev]==list(range(1,75899))
    def es(k):return [e for e in ev if e['kind']==k]
    def ds(k):return [e for e in debug if e['kind']==k]
    paired=[];device=es('d3d8_device_return')[0]['device']
    for ck,rk,pop in [('d3d8_device_call','d3d8_device_return',32),('d3d8_render_call','d3d8_render_return',None),('d3d8_state_call','d3d8_state_return',16)]:
        cs,rs=es(ck),es(rk);assert len(cs)==len(rs)=={'d3d8_device_call':1,'d3d8_render_call':2,'d3d8_state_call':8}[ck]
        for c,r in zip(cs,rs):
            n=pop or (32 if c['method']=='Clear' else 24)
            assert r['result']==0 and r['esp_before']==c['esp'] and r['esp_after']==c['esp']+n
            assert c['return']==r['return']==r['actual_return'] and c['seq']<r['seq']
            if ck!='d3d8_device_call':assert c['this']==r['this']==device
            paired.append(dict(call=c,returned=r))
    assert [[e['state'],e['value']]for e in es('d3d8_state_call')]==[[7,1],[9,2],[29,0],[26,1],[143,1],[48,0],[35,3],[136,1]]
    for a,b in zip(ds('state_native_entry'),ds('state_native_return')):
        assert b['hresult']==0 and b['suspended_cpu_unchanged'] and b['guest_frame_unchanged']
        assert a['arguments']['device']==ds('native_return')[0]['native_device']
    stop=read(d/'hard-stop.json');assert stop['hit'] and not stop['instruction_executed'] and not stop['SetMaterial_reached']
    assert len(ds('terminated_before_continue'))==1 and len(ds('hard_stop_0696f292'))==1
    readbacks=ds('breakpoints_readback');assert readbacks and all(r['permanent_stop_present'] and stop['native_address'] in r['addresses'] for r in readbacks)
    assert read(d/'cleanup.json')['passed'] and read(d/'cleanup.json')['remaining_job_processes']==0
    # Run the retained, stronger ABI/CPU audit on a disposable evidence copy.
    audit=O/'prior-recheck';audit.mkdir()
    for n in ['debug-observations.jsonl','runtime-events.json','hard-stop.json']:shutil.copy2(d/n,audit/n)
    legacy=load('material_prior_retained',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py');legacy.audit(audit)
    assert read(audit/'result.json')['passed']
    from supervisor.plan import resolve
    consumed=read(d/'candidate.json');legacy.V.EXE=W/consumed['executable'];legacy.V.EXPECTED=consumed['sha256']
    mapping=resolve(legacy.S,legacy.E,legacy.V,consumed['pdb_sha256'])
    assert mapping['static_mapping_verified']and mapping['stop_rva']==read(d/'debugger-plan.json')['stop_rva']
    save('prior-mapping.json',mapping)
    save('prior-audit.json',dict(passed=True,events=75898,pairs=paired,hardware_readbacks=len(readbacks),
        guest_device=device,native_device=ds('native_return')[0]['native_device'],stop=stop,
        stronger_retained_audit_passed=True,strict_failures=p['strict_failures'],genuine_launches=0))
    print('INDEPENDENT PRIOR AUDIT PASS',flush=True)

def inspect():
    import pefile,capstone
    original=A.source()/'System/D3DDrv.dll'
    pe=pefile.PE(str(original));base=pe.OPTIONAL_HEADER.ImageBase
    assert base==0x10000000
    guest_base=0x6960000
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    ins=list(md.disasm(pe.get_data(0xf292,0xb0),guest_base+0xf292))
    call=next(x for x in ins if x.address==0x696f31d)
    assert call.bytes.hex()=='ff91a8000000' and call.op_str=='dword ptr [ecx + 0xa8]'
    assert next(x for x in ins if x.address==0x696f323).op_str=='eax, dword ptr [ebp - 0x14]'
    rows=[dict(address=hex(x.address),bytes=x.bytes.hex(),instruction=x.mnemonic+' '+x.op_str) for x in ins]
    words=[0x3f000000]*3+[0x3f800000]+[0x3f800000]*4+[0]*9
    assert len(words)==17
    save('guest-disassembly.json',dict(passed=True,path=str(original),sha256=core.sha(original),preferred_image_base=hex(base),guest_image_base=hex(guest_base),
         instructions=rows,call='0x0696f31d',return_address='0x0696f323',slot=42,offset=168,
         material_words=words,material_bytes=struct.pack('<17I',*words).hex(),
         object='[render_device + 0x4698], same field as all eight states',
         interface='IDirect3DDevice8',guest_abi='x86 COM stdcall; this, const D3DMATERIAL8*; ret 8; caller ESP advances 12 including return',
         next_unmeasured='SetRenderState(148,1) at 0x0696f336; must not execute',genuine_launches=0))
    print('EXACT ORIGINAL PE confirms SetMaterial slot 42; next stop 0x0696f323',flush=True)

def native_build():
    B=O/'fixtures';B.mkdir()
    for arch in ['x86','x64']:
        d=B/arch;d.mkdir();s=(H.parent/'d3d8_device'/('abi32.asm'if arch=='x86'else'abi64.asm')).read_text().replace('device_abi','material_abi').replace('cwseed WORD 077fh','cwseed WORD 027fh')
        start=s.index('    push DWORD PTR [eax+28]'if arch=='x86'else'    mov rcx,[r10+8]');end=s.index('    mov edx,[esp+516]'if arch=='x86'else'    mov r10,[rsp+72]',start)
        call='    push DWORD PTR [eax+8]\n    push DWORD PTR [eax+4]\n    call DWORD PTR [eax]\n'if arch=='x86'else'    mov rcx,[r10+8]\n    mov rdx,[r10+16]\n    call QWORD PTR [r10]\n'
        (d/'abi.asm').write_text(s[:start]+call+s[end:])
        R.script(B,'native-build-'+arch,arch,f'{"ml"if arch=="x86"else"ml64"} /nologo /c /Fo"{d}/abi.obj" "{d}/abi.asm" || exit /b 1\ncl /nologo /O2 /W4 /Zi /Fo"{d}/native.obj" /Fd"{d}/compile.pdb" /Fe"{d}/native.exe" "{H}/native.c" "{d}/abi.obj" user32.lib /link /DEBUG /PDB:"{d}/native.pdb" || exit /b 1')

def native_run():
    B=O/'fixtures';runs=[]
    for arch in ['x86','x64']:
        for case,seed in [(0,18),(1,18),(2,18),(0,0),(0,0x13572468),(0,0xffffffff)]:
            d=B/f'native-{arch}-{case}-{seed}';d.mkdir();env=os.environ.copy();R.G.environment(env,d)
            r=R.execute([B/arch/'native.exe',R.G.verified_pair(arch),case,seed],d,'run',env,60,d)
            runs.append(dict(arch=arch,case=case,seed=seed,rows=[json.loads(s)for s in r.stdout.splitlines()if s.startswith('{')]))
            R.save(B/'native-results.json',runs)

def native_audit():
    runs=read(O/'fixtures/native-results.json');assert len(runs)==12
    for r in runs:
        calls=[x for x in r['rows']if x['kind']=='call'];assert len(calls)==4
        for c in calls:
            assert c['hr']==(0x8876086c if r['case']==2 else 0) and c['last_error']==r['seed'] and c['delta']==0 and c['input_unchanged']
            a,b=bytes.fromhex(c['pre']),bytes.fromhex(c['post']);assert a[:5]==b[:5] and a[24:28]==b[24:28] and a[32:42]==b[32:42] and a[48:58]==b[48:58]
            if r['arch']=='x86':assert c['regs']==[0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0]
            else:
                assert c['regs']==[0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]
                assert bytes.fromhex(c['xmm'])==struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10
        assert [x for x in r['rows']if x['kind']=='cleanup']==[dict(kind='cleanup',device_release=0,parent_release=0,window_valid=False,d3d8_loaded=False,d3d9_loaded=False,callbacks=0,foreign_callbacks=0)]
        assert [x for x in r['rows']if x['kind']=='identity']==[dict(kind='identity',parent_hr=0,same_parent=True,add=2,balance=1,parent_release=2,creation_hr=0,same_window=True,flags=66)]
        states=[x for x in r['rows']if x['kind']=='material']
        assert len(states)==5 and all(x==dict(kind='material',ordinal=i,hr=0,words=states[1]['words']) for i,x in enumerate(states[1:],1))
        if r['case']!=2:assert states[1]['words']==(read(O/'guest-disassembly.json')['material_words'] if not r['case'] else [0]*17)
        if r['case']==0:assert states[0]['words']!=states[1]['words']
        if r['case']==2:assert states[0]['words']==states[1]['words']
    for a in runs[:6]:
        b=next(r for r in runs if r['arch']=='x64' and r['case']==a['case'] and r['seed']==a['seed'])
        assert [x for x in a['rows']if x['kind']=='material']==[x for x in b['rows']if x['kind']=='material']
    save('native-audit.json',dict(passed=True,processes=12,calls=48,material_bytes=68,slot=42,
         exact_tuple_s_ok=True,input_unchanged=True,getmaterial_readback_equal=True,null_invalidcall_measured=True,
         last_error_four_seeds_preserved=True,x86_stdcall=True,x64_abi=True,x87_mxcsr_live_values_preserved=True,
         nonvolatile_registers_preserved=True,cleanup=True,genuine_launches=0))
    print('NATIVE MATERIAL DIFFERENTIAL PASS',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action');a=ap.parse_args();globals()[a.action.replace('-','_')]()
