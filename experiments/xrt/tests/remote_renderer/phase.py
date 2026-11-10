"""Remote-only renderer development. No game launch or enforcement mutation path."""
import argparse, ctypes, difflib, importlib.util, json, os, re, shutil, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W/'out/recovery/d3d8-remote-20261029-01'
OLD = W/'out/recovery/d3d8-material-20261029-01'
RT = O/'runtime'
sys.path.insert(0, str(W/'tools/xrt'))
from supervisor import core
import asset_boundary as A
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
R=load('remote_render_driver',H.parent/'d3d8_render/run.py')
S=load('remote_state_driver',H.parent/'d3d8_state/run.py')
def read(p):return json.loads(Path(p).read_text())
def save(n,v):core.atomic(O/n,v)
def preserve():
    O.mkdir()
    prior=read(OLD/'build.json'); assert core.tree(Path(prior['root']))==prior['outputs']
    assert prior['binary_sha256']=='0b07e58ade8bd2c4ecb5502054366b93b25aa28e75bf1dc3ebcb525598dd5c6e'
    assert core.tree(OLD/'runtime')==prior['runtime']
    ledger=core.Ledger(core.HOME/'ledger.jsonl')
    consumed=[r for r in ledger.rows if r['kind']=='launch-claimed']
    saved={str(p):core.tree(p) for p in [OLD,Path(prior['root']),core.HOME,W/'tools/xrt/supervisor',W/'experiments/xrt/runtime',W/'experiments/xrt/gen']}
    (O/'preserved').mkdir()
    for n in ['ledger.jsonl','qualification.json','status.json']:
        shutil.copy2(core.HOME/n,O/'preserved'/n)
    for n in ['build.json','final-integrity.json','strict-failures.json','consumed-denylist.json']:
        shutil.copy2(OLD/n,O/'preserved'/('material-'+n))
    shutil.copytree(OLD/'runtime',RT)
    session=ctypes.c_ulong();ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(session))
    save('preservation.json',dict(passed=True,trees=saved,protected=A.verify(),consumed=consumed,
        git_status=subprocess.run(['git','status','--porcelain=v1'],cwd=W,capture_output=True,text=True).stdout,
        session_id=session.value,remote_session=bool(ctypes.windll.user32.GetSystemMetrics(0x1000)),
        strict_failures=read(OLD/'strict-failures.json'),genuine_launches=0,genuine_requests=0))
    print('PRESERVED material package, original evidence, production runtime, generated sources and supervisor history',flush=True)
def inspect():
    import pefile,capstone
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    targets=[('D3DDrv.dll','SetRes',0xe890,0xf690,0x6960000),
             ('D3DDrv.dll','state-cache-init',0x17800,0x17e00,0x6960000)]
    for dll in ['WinDrv.dll','Engine.dll','D3DDrv.dll']:
        pe=pefile.PE(str(A.source()/'System'/dll))
        exports=sorted([(e.address,e.name.decode(errors='replace'))for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name])
        for a,n in exports:
            if ('TryRenderDevice@'in n or 'OpenWindow@UWindowsViewport' in n or '?Init@UGameEngine' in n or '?Init@UEngine' in n or '?UpdateGamma@UD3DRenderDevice' in n):
                end=next((b for b,_ in exports if b>a),a+0x1000)
                targets.append((dll,n,a,end,pe.OPTIONAL_HEADER.ImageBase))
    summary=[]
    for ordinal,(dll,name,start,end,base) in enumerate(targets):
        path=A.source()/'System'/dll;pe=pefile.PE(str(path));ins=list(md.disasm(pe.get_data(start,end-start),base+start))
        key=f'{ordinal:02d}-{dll}-{start:x}'
        (O/(key+'.asm.txt')).write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():20} {i.mnemonic} {i.op_str}'for i in ins)+'\n')
        gen=list((W/'experiments/xrt/gen'/dll.split('.')[0].lower()).glob('*.c'))
        # Generated bases come from actual P markers; retain the whole corresponding source files by hash.
        row=dict(module=dll,symbol=name,rva_start=hex(start),rva_end=hex(end),display_base=hex(base),
            original=str(path),sha256=core.sha(path),instructions=len(ins),disassembly=key+'.asm.txt',
            generated={str(p.relative_to(W)):core.sha(p)for p in gen},
            calls=[dict(address=hex(i.address),bytes=i.bytes.hex(),target=i.op_str)for i in ins if i.mnemonic=='call'])
        summary.append(row)
    save('static-inspection.json',dict(passed=True,functions=summary,
        absolute_operands_use_original_preferred_base=True,relative_branches_use_display_base=True,
        genuine_launches=0))
    print('STATIC',[(r['symbol'],len(r['calls']))for r in summary],flush=True)
def native_build():S.native_build(O/'state-fixtures')
def native_probe():
    b=O/'state-fixtures';runs=[]
    for arch in ['x86','x64']:
        d=b/('environment-'+arch);d.mkdir();env=os.environ.copy();R.G.environment(env,d)
        cmd=[b/arch/'native.exe',R.G.verified_pair(arch),148,1,18,0]
        r=subprocess.run(list(map(str,cmd)),cwd=d,env=env,capture_output=True,text=True,timeout=45)
        (d/'stdout.txt').write_text(r.stdout);(d/'stderr.txt').write_text(r.stderr)
        runs.append(dict(arch=arch,exit=r.returncode,rows=[json.loads(x)for x in r.stdout.splitlines()if x.startswith('{')],directory=str(d)))
        save('environment-probe.json',dict(runs=runs,genuine_launches=0))
        print('ENVIRONMENT',arch,r.returncode,flush=True)
def native_run():
    assert all(r['exit']==0 for r in read(O/'environment-probe.json')['runs'])
    S.native_run(O/'state-fixtures',148,1)
def contracts():
    b=O/(sys.argv[2] if len(sys.argv)>2 else 'contracts');b.mkdir()
    shutil.copy2(H/'adapter_contract.c',b/'source.c')
    traps=re.findall(r'^static void (d8_device_\w+)\(CPU\*c\).*unsupported slot ',(RT/'d3d8_device_slots.inc').read_text(),re.M)
    assert len(traps)==88
    (b/'contract_traps.inc').write_text('static XrtFn traps[]={'+','.join(traps)+'};\n')
    for arch in ['x86','x64']:
        d=b/arch;d.mkdir()
        R.script(b,'build-'+arch,arch,f'cl /nologo /O1 /Gy /fp:strict /W4 /I"{RT}" /I"{b}" /Fo"{d}/contract.obj" /Fe"{d}/contract.exe" "{H}/adapter_contract.c" /link /OPT:REF || exit /b 1')
        r=R.execute([d/'contract.exe'],b,'run-'+arch)
        result=json.loads(r.stdout.strip());assert result['passed']
    save('contract-audit.json',dict(passed=True,architectures=['x86','x64'],unsupported_slots=88,
        scope='exact staged bridge source with synthetic COM and GUI services; no DXVK or OS callback qualification',
        runtime=core.tree(RT),source=core.sha(H/'adapter_contract.c'),graphics_calls=0,genuine_launches=0))
def verify():
    p=read(O/'preservation.json')
    for path,expected in p['trees'].items():assert core.tree(Path(path))==expected,path
    assert A.verify()==p['protected']
    save('final-integrity.json',dict(passed=True,all_preserved_trees_equal=True,
        protected=p['protected'],material_candidate_unchanged=True,supervisor_history_policy_breakpoints_unchanged=True,
        production_runtime_and_generated_unchanged=True,strict_failures=p['strict_failures'],genuine_launches=0,genuine_requests=0))
    print('FINAL INTEGRITY PASS',flush=True)
if __name__=='__main__':globals()[sys.argv[1].replace('-','_')]()
