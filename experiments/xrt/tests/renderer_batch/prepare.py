"""Offline renderer preparation. This module has no game or GPU execution path."""
import difflib, hashlib, importlib.util, json, re, shutil, struct, sys
from pathlib import Path
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
W = H.parents[3]
O = W/'out/recovery/d3d8-batch-20261029-01'
PRIOR = W/'out/recovery/d3d8-remote-20261029-01'
sys.path.insert(0, str(W/'tools/xrt'))
from supervisor import core
import asset_boundary as A
import graphics_backend as G

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
R=load('batch_runner',H.parent/'d3d8_render/run.py')
GROUPS={1:'post-material-states',2:'initial-samplers',3:'cache-states',
        4:'identity-transforms',5:'cache-stages',6:'null-bindings',7:'fvf',
        8:'gamma',9:'resize-contract'}
def read(p): return json.loads(Path(p).read_text())
def save(n,v): core.atomic(O/n,v)

def preserve():
    O.mkdir()
    prior=read(PRIOR/'preservation.json')
    for p,expected in prior['trees'].items():
        assert core.tree(Path(p))==expected,p
    assert A.verify()==prior['protected']
    b=read(PRIOR/'build.json')
    assert core.tree(Path(b['root']))==b['outputs']
    paths=[PRIOR,W/'out/recovery/d3d8-material-20261029-01',Path(b['root']),
           W/'experiments/xrt/runtime',W/'experiments/xrt/gen',
           W/'tools/xrt/supervisor',core.HOME,H.parent/'remote_renderer',
           H.parent/'d3d8_material']
    save('preservation.json',dict(trees={str(p):core.tree(p) for p in paths},
         protected=A.verify(),strict_failures=read(PRIOR/'preserved/material-strict-failures.json'),
         existing_candidate=read(PRIOR/'candidate-verification.json'),genuine_launches=0))
    print('Preserved accepted material, prior snapshots, candidates, runtime, generated source and supervisor',flush=True)

def static():
    # Re-disassemble the actual PEs and regenerate the full source correspondence.
    p=load('batch_prior_phase',H.parent/'remote_renderer/phase.py');p.O=O
    sys.modules['phase']=p
    s=load('batch_static',H.parent/'remote_renderer/static_plan.py');s.P=p;s.main()
    c=load('batch_coverage',H.parent/'remote_renderer/coverage.py');c.P=p;c.main()
    for name in ['SetRes-remaining','state-cache-complete','UpdateGamma','ResizeViewport']:
        now=read(O/(name+'.json')); old=read(PRIOR/(name+'.json'))
        assert now==old,('static discrepancy',name)
    import pefile
    pe=pefile.PE(str(A.source()/'System/D3DDrv.dll'))
    imports={x.address:(d.dll.decode()+'!'+(x.name.decode() if x.name else str(x.ordinal)))
             for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports}
    constants={hex(a):pe.get_data(a-pe.OPTIONAL_HEADER.ImageBase,n).hex()
               for a,n in [(0x1001ee44,4),(0x1001ee40,4),(0x1001e760,4),
                           (0x1001ee38,8),(0x1001ee30,4),(0x1001ee28,8)]}
    resize=read(O/'ResizeViewport.json')
    save('extended-contracts.json',dict(passed=True,
        d3d_abi='x86 stdcall: explicit this on stack, callee pops 4*N; x64 Windows register ABI',
        transforms=dict(bytes=64,rows=4,columns=4,element='IEEE754 float32',identity_words=[0x3f800000 if i%5==0 else 0 for i in range(16)]),
        gamma=dict(bytes=1536,channels=['red','green','blue'],elements_per_channel=256,
            element='little-endian uint16',offsets=[0,512,1024],flags=1,slot=18,
            return_type='void; EAX is unspecified, never interpret as HRESULT',
            conditional='renderer+0x4698 != 0 AND renderer+0x4140 has 0x20000',
            fields={'client+0x5c':'gamma','client+0x54':'brightness','client+0x58':'contrast'},
            constants=constants,imports={hex(a):imports[a] for a in [0x1001e074,0x1001e078]},
            algorithm='pow(i * float[ee40], float[ee44]/gamma); intermediate stored as double; ((contrast + float[e760])*pow*double[ee38] + (brightness-float[e760])*float[ee30] - contrast*float[ee30] + double[ee28]) stored as float; appRound then signed clamp 0..65535; same WORD in all channels',
            input_computation_qualification='PENDING original x86/math and translated byte differential; no replacement of generated x87 computation'),
        resize=dict(call='0x0696f48d',target='0x11104f20',vtable_byte_offset=136,
            calling_convention='x86 thiscall: ECX=viewport, stack=[return,flags,width,height], ret 12; EAX=UBOOL',
            dimensions='signed int32; -1 means recover dimensions from fullscreen/windowed viewport/client fields in the original method',
            setres_flags=[16,17],success='EAX != 0; zero must propagate as failure',
            native_contract_thunk='x86 ECX thunk / x64 four integer register arguments; protocol probe only',
            actual_generated_resize='unchanged; no synthetic resize success bridge',
            calls=resize['calls'],windows_effects='PENDING real original/generated callback sequence, window styles, client rectangle, focus, messages and return under physical desktop')))
    print('Static PE/generated contracts independently match checkpoint',flush=True)

def cases():
    plan=read(O/'initialization-plan.json'); rows=[]
    def add(g,slot,a=0,b=0,c=0,site=0,config=0):
        rows.append(dict(group=g,slot=slot,a=a,b=b,c=c,site=int(site,16) if isinstance(site,str) else site,config=config))
    for c in plan['post_material_states']:add(1,50,c['state'],c['value'],site=c['address'])
    # Explicit measurement samples, not inferred runtime configuration or accepted domains.
    for config,(bias,aniso,mip,address) in enumerate([(0,1,0,1),(0x3f000000,2,2,3),(0xbf000000,1,1,1)]):
        for stage in range(8):
            for (state,value),site in zip([(19,bias),(16,2 if aniso==1 else 3),(17,2 if aniso==1 else 3),(18,mip),(21,aniso)],plan['sampler_loop']['call_addresses']):
                add(2,63,stage,state,value,site,config)
            for call in [c for c in plan['cache_calls'] if c['method']=='SetTextureStageState']:
                value=call['value']
                if isinstance(value,str):value=address if '4650' in value else 0 # _ftol(+/-0.5) = 0; not raw float bits.
                add(5,63,stage,call['type'],value,call['address'],config)
    for call in plan['cache_calls']:
        if call['slot']==50:
            for value in ([call['value']] if isinstance(call['value'],int) else [0,1]):
                add(3,50,call['state'],value,site=call['address'])
        elif call['slot']==37:add(4,37,call['transform'],site=call['address'])
        elif call['slot']==61:
            for i in range(8):add(6,61,i,site=call['address'])
        elif call['slot']==83:
            for i in range(16):add(6,83,i,site=call['address'])
        elif call['slot']==85:add(6,85,site=call['address'])
        elif call['slot']==76:add(7,76,2,site=call['address'])
    # Boundary/ABI fixture inputs. Their generation is NOT a claim about appRound/pow equality.
    add(8,18,1,site='0x0696cb68')
    add(9,0,16,1540,945,'0x0696f48d')
    add(9,0,17,1540,945,'0x0696f48d')
    save('cases.json',dict(cases=rows,sample_configuration_only=True,stage_sample_bound=8,stream_sample_bound=16,
        native_caps_and_actual_renderer_configuration_must_match_before_production=True))
    header='typedef struct BatchCase { unsigned group,slot,a,b,c,site,config; } BatchCase;\n'
    header+='static const BatchCase batch_cases[]={\n'+''.join(' {%d,%d,%du,%du,%du,%du,%d},\n'%tuple(r.values()) for r in rows)+'};\n'
    (O/'batch_cases.inc').write_text(header)

def stage():
    cases(); root=O/'snapshots';root.mkdir()
    base=PRIOR/'runtime'
    for group,name in GROUPS.items():
        rt=root/name/'runtime';shutil.copytree(base,rt)
        # Extended typed vtable, with offsets asserted independently for both architectures.
        s=(rt/'d3d8_device_abi.h').read_text()
        s=s.replace('typedef struct D8DeviceVtable {','typedef struct D8Matrix { DWORD bits[16]; } D8Matrix;\ntypedef struct D8Gamma { WORD red[256],green[256],blue[256]; } D8Gamma;\ntypedef struct D8DeviceVtable {')
        s=s.replace('void* unsupported16_35[20];','void* unsupported16_17[2];\n    void (WINAPI *SetGammaRamp)(D8Device*,DWORD,const D8Gamma*);\n    void (WINAPI *GetGammaRamp)(D8Device*,D8Gamma*);\n    void* unsupported20_35[16];')
        s=s.replace('void* unsupported37_41[5];','HRESULT (WINAPI *SetTransform)(D8Device*,DWORD,const D8Matrix*);\n    HRESULT (WINAPI *GetTransform)(D8Device*,DWORD,D8Matrix*);\n    void* unsupported39_41[3];')
        tail='''
    HRESULT (WINAPI *GetRenderState)(D8Device*,DWORD,DWORD*);
    void* unsupported52_59[8];
    HRESULT (WINAPI *GetTexture)(D8Device*,DWORD,void**);
    HRESULT (WINAPI *SetTexture)(D8Device*,DWORD,void*);
    HRESULT (WINAPI *GetTextureStageState)(D8Device*,DWORD,DWORD,DWORD*);
    HRESULT (WINAPI *SetTextureStageState)(D8Device*,DWORD,DWORD,DWORD);
    void* unsupported64_75[12];
    HRESULT (WINAPI *SetVertexShader)(D8Device*,DWORD);
    HRESULT (WINAPI *GetVertexShader)(D8Device*,DWORD*);
    void* unsupported78_82[5];
    HRESULT (WINAPI *SetStreamSource)(D8Device*,DWORD,void*,DWORD);
    HRESULT (WINAPI *GetStreamSource)(D8Device*,DWORD,void**,DWORD*);
    HRESULT (WINAPI *SetIndices)(D8Device*,void*,DWORD);
    HRESULT (WINAPI *GetIndices)(D8Device*,void**,DWORD*);
'''
        s=s.replace('} D8DeviceVtable;',tail+'} D8DeviceVtable;')
        assertions='typedef char matrix_size[sizeof(D8Matrix)==64?1:-1];\ntypedef char gamma_size[sizeof(D8Gamma)==1536?1:-1];\ntypedef char gamma_green[offsetof(D8Gamma,green)==512?1:-1];\ntypedef char gamma_blue[offsetof(D8Gamma,blue)==1024?1:-1];\n'
        for method,slot in [('SetGammaRamp',18),('SetTransform',37),('GetRenderState',51),('SetTexture',61),('SetTextureStageState',63),('SetVertexShader',76),('SetStreamSource',83),('SetIndices',85)]:
            assertions+=f'typedef char slot_{method}[offsetof(D8DeviceVtable,{method})=={slot}*sizeof(void*)?1:-1];\n'
        (rt/'d3d8_device_abi.h').write_text(s.replace('#endif',assertions+'#endif'))
        bridge=(H/'bridge.inc').read_text().replace('BATCH_GROUP_VALUE',str(group))
        (rt/'batch_bridge.inc').write_text(bridge)
        shutil.copy2(O/'batch_cases.inc',rt/'batch_cases.inc')
        s=(rt/'hle_d3d8_device.inc').read_text()
        # Snapshots only: the accepted adapter is retained for already qualified tuples.
        if group in [1,3]:s=s.replace('static void d8_device_SetRenderState(CPU*c)', 'static void d8_device_AcceptedSetRenderState(CPU*c)')
        s=s.replace('#include "d3d8_device_slots.inc"','#include "batch_bridge.inc"\n#include "d3d8_device_slots.inc"')
        (rt/'hle_d3d8_device.inc').write_text(s)
        methods={2:['SetTextureStageState'],4:['SetTransform'],5:['SetTextureStageState'],6:['SetTexture','SetStreamSource','SetIndices'],7:['SetVertexShader'],8:['SetGammaRamp']}.get(group,[])
        p=rt/'d3d8_device_slots.inc';s=p.read_text()
        for method in methods:
            s,n=re.subn(r'^static void d8_device_'+method+r'\([^\n]*\n','',s,flags=re.M);assert n==1,method
        p.write_text(s)
        patch=''
        for p in rt.iterdir():
            if not p.is_file():continue
            before=(base/p.name).read_text() if (base/p.name).exists() else ''
            after=p.read_text()
            if before!=after:patch+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='accepted/'+p.name,tofile=name+'/'+p.name))
        (rt.parent/'provisional.patch').write_text(patch)
        core.atomic(rt.parent/'snapshot.json',dict(group=group,name=name,runtime=core.tree(rt),accepted_baseline=core.tree(base),production_accepted=False,graphics_measured=False))
    print('Nine independent provisional source snapshots prepared',flush=True)

def build():
    build=O/'fixtures';build.mkdir(exist_ok=True)
    results=[]
    # The already verified trampoline is byte-pinned and reused; only fixture C is recompiled.
    for arch in ['x86','x64']:
        d=build/arch;d.mkdir(exist_ok=True)
        orig=PRIOR/'prepared-batches'/arch
        for n in ['abi.obj','abi.asm']:
            if not (d/n).exists():shutil.copy2(orig/n,d/n)
            assert core.sha(d/n)==core.sha(orig/n)
    for group,name in GROUPS.items():
        rt=O/'snapshots'/name/'runtime'
        for arch,translated in [('x86',0),('x64',0),('x86',1),('x64',1)]:
            d=build/f'{name}-{arch}-{"translated" if translated else "native"}'
            d.mkdir(exist_ok=True)
            outputs=[d/'fixture.exe',d/'fixture.obj']
            inputs=[H/'fixture.c',H/'support.inc',H/'resize32.asm',*rt.glob('*')]
            stamp=core.digest({str(p):core.sha(p) for p in inputs if p.is_file()})
            record=d/'build-record.json'
            if record.exists() and read(record)['inputs']==stamp and all(p.exists() for p in outputs):
                assert {str(p):core.sha(p) for p in outputs}==read(record)['outputs']
            else:
                resize=''
                extra=''
                if group==9 and arch=='x86':
                    resize=f'ml /nologo /c /Fo"{d}/resize.obj" "{H}/resize32.asm" || exit /b 1\n'
                    extra=f' "{d}/resize.obj" /alternatename:_resize_adapter@16=_resize_adapter'
                R.script(d,'compile-link',arch,resize+f'cl /nologo /c /O1 /Gy /fp:strict /W4 /wd4100 /wd4102 /wd4505 /D_CRT_SECURE_NO_WARNINGS /DBATCH_TRANSLATED={translated} /DBATCH_GROUP={group} /I"{rt}" /Fo"{d}/fixture.obj" "{H}/fixture.c" || exit /b 1\nlink /nologo /OPT:REF /OUT:"{d}/fixture.exe" "{d}/fixture.obj" "{build/arch}/abi.obj"'+extra+' kernel32.lib user32.lib || exit /b 1')
                core.atomic(record,dict(inputs=stamp,outputs={str(p):core.sha(p) for p in outputs},fp='/fp:strict',reused_trampoline_sha256=core.sha(build/arch/'abi.obj')))
            # Only the explicitly non-graphical mode is executed by preparation.
            r=R.execute([d/'fixture.exe','--contract-only'],d,'contract',timeout=60)
            rows=[json.loads(s) for s in r.stdout.splitlines() if s.startswith('{')]
            assert rows[-1]['passed'] and rows[-1]['graphics']==False
            results.append(dict(group=group,arch=arch,translated=bool(translated),summary=rows[-1],directory=str(d)))
            save('contract-results.json',results)
        print('Group complete:',name,flush=True)

def verify():
    p=read(O/'preservation.json')
    for path,expected in p['trees'].items():assert core.tree(Path(path))==expected,path
    assert A.verify()==p['protected']
    save('final-integrity.json',dict(passed=True,all_preserved_trees_equal=True,protected_inputs_equal=True,
        strict_failures=p['strict_failures'],production_unchanged=True,genuine_launches=0,graphics_calls=0,
        supervisor_policy_and_breakpoints_unchanged=True))
    print('Protected inputs and all prior package/candidate identities unchanged',flush=True)

def integration():
    """Compile only the changed integration unit; no client/candidate relink."""
    outputs=[]
    for group,name in GROUPS.items():
        rt=O/'snapshots'/name/'runtime';d=O/'integration'/name;d.mkdir(parents=True)
        R.script(d,'compile','x64',f'cl /nologo /c /O1 /fp:strict /Gy /W3 /wd4100 /wd4102 /wd4146 /D_CRT_SECURE_NO_WARNINGS /I"{rt}" /Fo"{d}/hle_misc.obj" "{rt}/hle_misc.c" || exit /b 1')
        p=d/'hle_misc.obj';assert struct.unpack('<H',p.read_bytes()[:2])[0]==0x8664
        outputs.append(dict(group=group,source_sha256=core.sha(rt/'hle_misc.c'),runtime_sha256=core.digest(core.tree(rt)),object_sha256=core.sha(p),flags='/O1 /fp:strict /Gy',game_candidate_created=False))
        save('integration-build.json',dict(passed=True,compiled_units=outputs,accepted_objects_changed=False))

def extended_static():
    import pefile
    vtables=read(PRIOR/'vtable-resolution.json')['entries'];checked=[]
    for row in vtables:
        pe=pefile.PE(str(A.source()/'System'/row['module']))
        at=int(row['vtable_rva'],16)+int(row['offset'],16)
        value=struct.unpack('<I',pe.get_data(at,4))[0]
        assert value-pe.OPTIONAL_HEADER.ImageBase==int(row['target_rva'],16)
        checked.append(dict(row,raw_target=hex(value)))
    core_pe=pefile.PE(str(A.source()/'System/Core.dll'))
    identity=[e for e in core_pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name and e.name.decode().startswith('?Identity@FMatrix@@')]
    assert len(identity)==1
    expected=struct.pack('<16I',*[0x3f800000 if i%5==0 else 0 for i in range(16)])
    assert core_pe.get_data(identity[0].address,64)==expected
    PEs={dll:pefile.PE(str(A.source()/'System'/dll)) for dll in ['D3DDrv.dll','WinDrv.dll']}
    resize=read(O/'ResizeViewport.json')
    save('callback-contracts.json',dict(passed=True,scope='original PE/generated dispatch and argument contexts, not real Windows effects',
        vtables=checked,identity_export=dict(name=identity[0].name.decode(),rva=hex(identity[0].address),bytes=expected.hex()),
        resize_thiscall_stack=dict(return_address=0,flags=4,width=8,height=12,this_register='ECX',callee_pop_bytes=12),
        resize_calls=resize['calls'],actual_windows_sequence_pending=True,
        known_strict_failures=read(O/'preservation.json')['strict_failures']))
    print('Vtable ownership, original identity bytes and callback contexts verified',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
