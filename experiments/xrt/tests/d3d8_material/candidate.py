"""Fresh staged-runtime candidate. Compilation and offline inspection only."""
import ctypes as C
from ctypes import wintypes as T
import re,shutil,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
import phase as P
W,O,RT=P.W,P.O,P.RT

def build():
    assert P.read(O/'translated-audit.json')['passed']
    old=P.read(W/'out/recovery/queryclass-ae9-20261029-01/build.json');previous=Path(old['root'])
    assert P.core.tree(previous)==old['outputs']
    assert P.core.tree(W/'experiments/xrt/gen')==old['generated']
    target=W/'experiments/xrt/build/d3d8-material-20261029-01/client';target.mkdir(parents=True)
    envhelper=P.load('material_client_compiler',W/'experiments/xrt/tests/getobject_boundary/phase.py');envhelper.O=O/'client-build';envhelper.O.mkdir();env=envhelper.env()
    copied={};commands=[]
    for rel,h in old['outputs'].items():
        if rel.endswith('.obj') and not rel.startswith('obj/rt/'):
            dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous/rel,dest);assert P.core.sha(dest)==h;copied[rel]=h
    for row in old['commands']:
        original=row['command'];link=Path(original[0]).name.lower()=='link.exe'
        cmd=[x.replace(str(previous),str(target)) for x in original]
        if link:
            (target/'link-objects.rsp').write_text((previous/'link-objects.rsp').read_text().replace(str(previous),str(target)))
            name='link'
        else:
            cmd=[('/I'+str(RT)) if x=='/Iruntime' else str(RT/Path(x.replace('\\','/')).name) if x.startswith('runtime\\') or x.startswith('runtime/') else x for x in cmd]
            obj=Path(next(x[3:]for x in cmd if x.startswith('/Fo')));obj.parent.mkdir(parents=True,exist_ok=True);name=obj.stem
        P.R.execute(cmd,envhelper.O,name,env,180,W/'experiments/xrt');commands.append(P.read(envhelper.O/(name+'.json')))
    outputs=P.core.tree(target);assert len(copied)==265 and sum(n.endswith('.obj')for n in outputs)==279
    sha=P.core.sha(target/'xrt_ucc.exe');assert not any(r['kind']=='launch-claimed'and r['sha256']==sha for r in P.core.Ledger(P.core.HOME/'ledger.jsonl').rows)
    P.save('build.json',dict(passed=True,root=str(target),outputs=outputs,runtime=P.core.tree(RT),runtime_root=str(RT),
        generated=old['generated'],binary_sha256=sha,pdb_sha256=P.core.sha(target/'xrt_ucc.pdb'),commands=commands,
        compiled_objects=14,reused_objects=265,reused_object_hashes=copied,
        inherited_build='out/recovery/queryclass-ae9-20261029-01/build.json',inherited_build_sha256=P.core.sha(W/'out/recovery/queryclass-ae9-20261029-01/build.json'),
        production_runtime_unchanged=True,genuine_launches=0))
    print('FRESH UNEXECUTED CANDIDATE',sha,flush=True)

def mapping():
    import capstone as CS,pefile
    from capstone.x86_const import X86_OP_IMM
    b=P.read(O/'build.json');exe=Path(b['root'])/'xrt_ucc.exe'
    assert P.core.tree(exe.parent)==b['outputs']and P.core.sha(exe.with_suffix('.pdb'))==b['pdb_sha256']
    legacy=P.load('material_mapping_dependencies',W/'out/recovery/viewport-getobject-20261028-01/bounded_genuine.py')
    d=C.WinDLL('dbghelp',use_last_error=True);api=legacy.D.api;h=api(legacy.D.K,'GetCurrentProcess',[],T.HANDLE)()
    api(d,'SymSetOptions',[T.DWORD],T.DWORD)(0x81202)
    assert api(d,'SymInitializeW',[T.HANDLE,C.c_wchar_p,T.BOOL])(h,str(exe.parent),False)
    base=api(d,'SymLoadModuleExW',[T.HANDLE,T.HANDLE,C.c_wchar_p,C.c_wchar_p,C.c_ulonglong,T.DWORD,C.c_void_p,T.DWORD],C.c_ulonglong)(h,None,str(exe),None,0x140000000,0,None,0);assert base
    source=W/'experiments/xrt/gen/d3ddrv/D3DDrv_000.c';text=source.read_text();pos=text.index('    P(0x696f323u);')
    name=re.findall(r'^void (f_[0-9a-f]+)\(CPU\* c\)',text[:pos],re.M)[-1];next_name=re.search(r'^void (f_[0-9a-f]+)\(CPU\* c\)',text[pos:],re.M)[1]
    symbols={}
    try:
        for n in [name,next_name,'xrt_icall','d8_CreateDevice','d8_device_SetRenderState','d8_device_SetMaterial','xrt_fatal','events','event_seq']:
            s=legacy.D.Symbol();s.SizeOfStruct=88;s.MaxNameLen=1023;assert api(d,'SymFromName',[T.HANDLE,C.c_char_p,C.POINTER(legacy.D.Symbol)])(h,n.encode(),C.byref(s))and s.Address
            symbols[n]=dict(rva=s.Address-base,size=s.Size)
    finally:assert api(d,'SymCleanup',[T.HANDLE])(h)
    pe=pefile.PE(str(exe));md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_64);md.detail=True
    r=symbols[name];ins=list(md.disasm(pe.get_data(r['rva'],symbols[next_name]['rva']-r['rva']),base+r['rva']))
    def row(x):return dict(rva=x.address-base,mnemonic=x.mnemonic,operands=x.op_str,bytes=x.bytes.hex())
    markers=[i for i,x in enumerate(ins)if any(o.type==X86_OP_IMM and o.imm==0x696f323 for o in x.operands)];assert len(markers)==1
    i=markers[0];P.save('mapping-context.json',dict(symbols=symbols,marker_index=i,context=[row(x)for x in ins[i-12:i+45]],image_base=base))
    print('MAPPING CONTEXT',O/'mapping-context.json',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
