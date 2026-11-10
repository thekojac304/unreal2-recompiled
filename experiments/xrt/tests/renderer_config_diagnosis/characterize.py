"""Original PE/source provenance and native/lifted owned Boolean/sampler fixture."""
import pathlib
import shutil
import struct
import sys
import uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from common import *


def decode():
    import pefile,capstone
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    source=W/'sandbox_inputs/first-world/content/System'
    snippets={};evidence=[]
    ranges={'Core.dll':[(0x56c70,0x18e),(0x54ef0,0xa2),(0xe6f0,0x2e)],
            'D3DDrv.dll':[(0xaa60,0x58),(0xdf17,0x5f),(0xf3ef,0x1c),(0xf31d,6)]}
    for name,spans in ranges.items():
        pe=pefile.PE(str(source/name));base=0x10100000 if name=='Core.dll' else 0x6960000
        rows=[dict(va=i.address,bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str) for rva,n in spans for i in md.disasm(pe.get_data(rva,n),base+rva)]
        evidence.append(dict(path=str(source/name),sha256=core.sha(source/name),preferred_base=pe.OPTIONAL_HEADER.ImageBase,effective_base=base,instructions=rows))
        if name=='Core.dll':snippets['true']=pe.get_data(0x56de4,5);snippets['false']=pe.get_data(0x56dc1,11)
        else:
            snippets['mip']=pe.get_data(0xf3ef,0x1c)
            namebytes=pe.get_data(0x28a1c,26);core.require(namebytes.decode('utf-16le').split('\0')[0]=='UseTrilinear','original property name')
    core.require(snippets['true'].hex()=='8b566c0910','original Boolean true OR mask')
    core.require(snippets['false'].hex()=='8b4e6c8b10f7d123d18910','original Boolean false clear mask')
    core.require(snippets['mip'].hex()=='8b88d440000085c974108bb8d040000033c985ff0f95c141eb0233c9','original sampler truth conversion')
    save(O/'original-pe-analysis.json',dict(passed=True,images=evidence,snippets={k:v.hex() for k,v in snippets.items()},
        Boolean_representation='Core ImportText ORs property.BitMask into a DWORD; it does not canonicalize enabled values to 1. Link can shift BitMask. The live property object/mask itself was not captured.',
        downstream='Original sampler MIPFILTER code uses TEST/SETNE/INC: any nonzero UseTrilinear with mipmaps enabled selects value 2. The revised profile will admit only independently observed raw 0x20.'))
    entry=read(O/'raw-entry-verification.json');rows=[__import__('json').loads(s) for s in (ATTEMPT/'debug-observations.jsonl').read_text().splitlines()]
    renderer_raw=bytes.fromhex(next(r for r in rows if r['kind']=='setres_renderer_raw')['raw'])
    viewport_raw=bytes.fromhex(next(r for r in rows if r['kind']=='setres_viewport_raw')['raw'])
    vt=struct.unpack_from('<I',renderer_raw)[0];pe=pefile.PE(str(source/'D3DDrv.dll'))
    preferred_setres=struct.unpack('<I',pe.get_data(vt-0x6960000+0x78,4))[0]
    core.require(preferred_setres-pe.OPTIONAL_HEADER.ImageBase+0x6960000==0x696e890,'renderer original vtable SetRes identity')
    core.require(struct.unpack_from('<I',viewport_raw,0x5c)[0]==entry['renderer'],'viewport renderer identity')
    failure=read(O/'renderer-fields.json')['failed_boundary'];stack=next(r for r in rows if r['kind']=='raw_boundary_stack' and r.get('tag')=='profile_entry')
    offset=stack['cpu']['registers']['ebp']-0x14-stack['address']
    core.require(struct.unpack_from('<I',bytes.fromhex(stack['raw']),offset)[0]==entry['renderer'],'SetRes stack-local renderer identity')
    save(O/'object-layout-verification.json',dict(passed=True,renderer=entry['renderer'],viewport=entry['entry_frame'][1],vtable=vt,
        original_vtable_setres=hex(preferred_setres),effective_setres='0x0696e890',failure_stack_local_renderer_offset=offset,
        reads='u32 is little-endian 4-byte ReadProcessMemory at xrt_g + unsigned guest renderer + offset; generated rd32 uses the same G2H convention',
        source_files={str(p):core.sha(p) for p in [W/'experiments/xrt/runtime/xrt.h',W/'experiments/xrt/gen/d3ddrv/D3DDrv_000.c',H.parent/'setres_initial_completion/observer.py']},
        evidence_limit='The numeric host xrt_g value was not saved in the consumed entry log. Guest identities and independent runtime/debugger raw CPU/frame match; no wrong-base or width evidence is found.'))
    profile=read(PRIOR/'configuration-profile.json')
    sources={
      '0x40d0':dict(name='UseTrilinear',ini='[D3DDrv.D3DRenderDevice] UseTrilinear=True',registration='D3DDrv 0696AA78 name; 0696AAA3 DWORD offset 40d0',expectation='phase.py:95 hardcoded 1; unmeasured canonical Boolean assumption',consumer='0696F3F9..0696F407 nonzero selects sampler MIPFILTER=2'),
      '0x40d4':dict(name='mipmap-enable flag',expectation='literal 1 supported by original capability branch',initialization='0696DF4B writes DWORD 1; DF70 may clear UseTrilinear if mip capability absent'),
      '0x4124':dict(name='LevelOfAnisotropy',ini='LevelOfAnisotropy=1',expectation='literal 1 matches INI; static property registration in D3DDrv'),
      '0x412c':dict(name='DefaultTexMipBias',ini='DefaultTexMipBias=-0.500000',expectation='literal IEEE float32 bits BF000000'),
      '0x41a0':dict(name='D3DCAPS8 raw word 27 / MaxAnisotropy',expectation='measured GetDeviceCaps destination renderer+4134, word 27 =16'),
      '0x41c8':dict(name='D3DCAPS8 raw word 37 / MaxTextureBlendStages',expectation='measured word 37 =8; original Init may reduce; observed entry is 8'),
      '0x41cc':dict(name='D3DCAPS8 raw word 38 / MaxSimultaneousTextures',expectation='measured word 38 =8; original Init may reduce; observed entry is 8'),
      '0x41f0':dict(name='D3DCAPS8 raw word 47 / MaxStreams',expectation='measured word 47 =16 and original clamp to16'),
      '0x4650':dict(name='NVIDIA address-mode selector',expectation='original vendor branch at RVA e472 assigns1'),
      '0x60':dict(name='base renderer stencil flag',ini='UseStencil=False',expectation='literal0 matches windowed stencil-disabled profile')}
    ini=pathlib.Path(read(ATTEMPT/'launch-profile.json')['cwd'])/'Unreal2.ini'
    core.require(core.sha(ini)==profile['ini_sha256'],'genuine INI differs from profile source')
    before=read(ATTEMPT/'launch-profile.json')['sandbox_before']['System/Unreal2.ini']
    after=read(ATTEMPT/'sandbox-after.json')['System/Unreal2.ini']
    core.require(before==after==core.sha(ini),'genuine INI changed during attempt')
    save(O/'field-sources.json',dict(passed=True,fields=sources,ini=str(ini),ini_sha256=core.sha(ini),profile_generator=str(H.parent/'renderer_prerequisites/phase.py'),
       before_ini_sha256=before,after_ini_sha256=after,caps_source=profile['caps_evidence'],caps_sha256=profile['caps_evidence_sha256']))
    return snippets


def fixtures():
    snippets=decode();out=O/('boolean-fixture-'+str(uuid.uuid4()));out.mkdir()
    body=''
    for name,raw in snippets.items():
        prefix='push esi\nmov eax,[esp+8]\nmov esi,[esp+12]\n' if name!='mip' else 'push edi\nmov eax,[esp+8]\n'
        suffix='pop esi\nret 8' if name!='mip' else 'mov eax,ecx\npop edi\nret 4'
        body+=f'__declspec(naked) static DWORD {name}_fragment(void) {{ __asm {{\n'+prefix+'\n'.join('_emit 0x%02x'%v for v in raw)+'\n'+suffix+'\n}}\n'
    (out/'original_fragments.inc').write_text(body)
    helper=load('configuration_fixture_tools',H.parent/'getobject_boundary/phase.py');helper.O=out;env=helper.env('x86')
    d=out/'x86';d.mkdir()
    helper.run(['cl','/nologo','/c','/O2','/GS-','/W4','/I'+str(out),'/Fo'+str(d/'probe.obj'),H/'probe.c'],'compile-x86',environment=env)
    helper.run(['link','/nologo','/DLL','/NOENTRY','/NODEFAULTLIB','/DYNAMICBASE:NO','/BASE:0x12000000','/OUT:'+str(d/'cfgprobe.dll'),d/'probe.obj'],'dll',environment=env)
    helper.run(['cl','/nologo','/O1','/W4','/Fo'+str(d/'native.obj'),'/Fe'+str(d/'native.exe'),H/'native.c'],'native-host',environment=env)
    native=helper.run([d/'native.exe',d/'cfgprobe.dll'],'native',cwd=out)
    gen=out/'gen';helper.run([W/'.venv/Scripts/python.exe','-B','-I',W/'tools/xrt/xlift.py',d/'cfgprobe.dll','--out',gen],'lift')
    translated=out/'translated';translated.mkdir();env=helper.env()
    runtime=LAST/'runtime';names=['hle_kernel32.c','hle_misc.c','hle_gui.c','hle_msvcr70.c','xrt_cpu.c','xrt_diag.c','xrt_eh.c','xrt_events.c','xrt_fmt.c','xrt_loader.c','xrt_mem.c','xrt_thread.c']
    helper.run(['cl','/nologo','/O1','/Zi','/fp:strict','/W3','/wd4102','/wd4146','/wd4100','/D_CRT_SECURE_NO_WARNINGS','/DSTUB_LOADLIB','/DSTUB_POW','/I'+str(runtime),'/Fo'+str(translated)+'\\','/Fd'+str(translated/'compile.pdb'),'/Fe'+str(translated/'translated.exe'),H/'host.c',*sorted(gen.glob('*.c')),*[runtime/n for n in names],H.parent/'common/xrt_test_stubs.c','winmm.lib','advapi32.lib','ole32.lib','oleacc.lib','oleaut32.lib','bcrypt.lib','user32.lib','gdi32.lib','imm32.lib','/link','/DEBUG','/STACK:0x10000000'],'translated-build',environment=env,timeout=60)
    lifted=helper.run([translated/'translated.exe',d/'cfgprobe.dll',out/'translated-report.json'],'translated',cwd=out)
    core.require(native.stdout==lifted.stdout,'original native/lifted Boolean or sampler behavior differs')
    import json
    rows=[json.loads(s) for s in native.stdout.splitlines()]
    core.require(len(rows)==12 and all(r['filter']==(0 if not r['mips'] else 2 if r['word'] else 1) for r in rows),'original branch characterization')
    save(O/'boolean-characterization.json',dict(passed=True,evidence=str(out),cases=rows,original_instruction_bytes_embedded=True,actual_x86_lifted=True,
       native_translated_equal=True,raw32_with_mips1_selects2=True,raw1_not_admitted_by_revised_profile=True,
       scope='Owned replicas of exact original Boolean store and sampler decision instructions; no original game EXE/DLL is executed and no native D3D device is created. Native D3D tuples are already measured unchanged.',genuine_launches=0))
    print('12 native/lifted original-instruction Boolean/sampler cases PASS; raw32 selects existing tuple2.',flush=True)


if __name__=='__main__':fixtures()
